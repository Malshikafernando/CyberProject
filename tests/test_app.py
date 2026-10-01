from pathlib import Path
import importlib.util

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"

spec = importlib.util.spec_from_file_location("cyberproject_app", APP_PATH)
app_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(app_module)


@pytest.fixture()
def client():
    app_module.app.config.update(TESTING=True, SECRET_KEY="test-secret")
    with app_module.app.test_client() as test_client:
        yield test_client


@pytest.fixture()
def package():
    loaded = app_module.load_model_package()
    assert loaded is not None
    return loaded


def valid_assessment(package):
    values = app_module.default_form_values(package)
    values["assessment_reference"] = "TEST-001"
    return values


def test_model_package_has_expected_deployment_contract(package):
    assert package["model_version"] == "2.0.0"
    assert len(package["feature_columns"]) == 63
    assert set(package["class_labels"]) == {"Low", "Medium", "High"}
    assert package["selected_model"] == "logistic_regression"


def test_home_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Turn security signals into clear, prioritized action" in response.data


def test_predict_page_renders_model_fields(client):
    response = client.get("/predict-risk")
    assert response.status_code == 200
    assert b"Guided assessment" in response.data
    assert b"Review and predict" in response.data
    assert b'name="employee_role"' in response.data
    assert b'name="mfa_enabled"' in response.data
    assert b'name="security_training_score"' in response.data


def test_assessment_parser_preserves_exact_feature_order(package):
    frame, parsed = app_module.parse_assessment(valid_assessment(package), package)
    assert frame.columns.tolist() == package["feature_columns"]
    assert len(parsed) == 63


def test_out_of_range_value_is_rejected(client, package):
    data = valid_assessment(package)
    data["remote_work_percentage"] = "101"
    response = client.post("/predict", data=data, follow_redirects=True)
    assert response.status_code == 200
    assert b"Remote Work Percentage must be between" in response.data


def test_role_department_mismatch_is_rejected(client, package):
    data = valid_assessment(package)
    data["department"] = "Academic"
    response = client.post("/predict", data=data, follow_redirects=True)
    assert response.status_code == 200
    assert b"Department must be" in response.data


def test_prediction_runs_through_real_saved_model(client, package):
    response = client.post("/predict", data=valid_assessment(package), follow_redirects=True)
    assert response.status_code == 200
    assert b"Predicted risk level" in response.data
    assert b"Prediction confidence" in response.data
    assert b"Recommended actions" in response.data


def test_prediction_session_cookie_remains_within_browser_limit(client, package):
    response = client.post("/predict", data=valid_assessment(package))
    assert response.status_code == 302
    assert len(response.headers.get("Set-Cookie", "")) < 4093


def test_results_redirect_without_session(client):
    response = client.get("/results")
    assert response.status_code == 302
    assert "/predict-risk" in response.headers["Location"]


def test_report_download_after_real_prediction(client, package):
    client.post("/predict", data=valid_assessment(package))
    response = client.get("/download-report")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF-")
    assert "cyberrisk-compass-assessment-report.pdf" in response.headers["Content-Disposition"]
    assert len(response.data) > 20_000


def test_recommendation_rule_engine_matches_known_gap(package):
    inputs = valid_assessment(package)
    inputs["mfa_enabled"] = 0
    matches = app_module.matched_recommendations(package, inputs, "High")
    identifiers = {item["recommendation_id"] for item in matches}
    assert "REC_ACCESS_MFA" in identifiers


def test_missing_model_is_handled(client, monkeypatch):
    monkeypatch.setattr(app_module, "load_model_package", lambda: None)
    response = client.post("/predict", data={}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Prediction model is unavailable" in response.data
