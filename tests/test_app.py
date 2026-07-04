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
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield client


def test_home_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Cybersecurity Risk Prediction System" in response.data


def test_predict_page_loads(client):
    response = client.get("/predict-risk")
    assert response.status_code == 200
    assert b"Predict Cybersecurity Risk" in response.data
    assert b"Assessment Profile" in response.data


def test_results_redirect_without_session(client):
    response = client.get("/results")
    assert response.status_code == 302
    assert "/predict-risk" in response.headers["Location"]


def test_download_report_redirect_without_prediction(client):
    response = client.get("/download-report", follow_redirects=True)
    assert response.status_code == 200
    assert b"Please generate a prediction before downloading a report." in response.data


def test_download_report_with_prediction_in_session(client):
    with client.session_transaction() as session:
        session["prediction_result"] = {
            "risk_level": "Medium",
            "recommendation": "Improve awareness and monitoring for stronger protection.",
            "explanation": "The model uses security inputs to determine risk.",
            "inputs": {
                "firewall_status": "Yes",
                "mfa_usage": "Yes",
                "encryption_usage": "Yes",
                "employee_training_score": 75,
                "phishing_test_score": 70,
                "unpatched_vulnerabilities": 1,
                "incident_history_count": 0,
                "password_policy_strength": 8,
                "backup_frequency_days": 7,
                "network_monitoring_level": 8,
            },
        }

    response = client.get("/download-report")
    assert response.status_code == 200
    assert response.mimetype == "application/msword"
    assert b"Cyber Risk Assessment Report" in response.data
    assert b"Priority Recommendations" in response.data
    assert b"Human Awareness" in response.data


def test_predict_redirects_when_model_unavailable(client, monkeypatch):
    monkeypatch.setattr(app_module, "load_model", lambda: None)

    response = client.post(
        "/predict",
        data={
            "firewall_status": "Yes",
            "mfa_usage": "Yes",
            "encryption_usage": "Yes",
            "employee_training_score": 75,
            "phishing_test_score": 70,
            "unpatched_vulnerabilities": 1,
            "incident_history_count": 0,
            "password_policy_strength": 8,
            "backup_frequency_days": 7,
            "network_monitoring_level": 8,
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Prediction model is unavailable." in response.data


def test_predict_success_with_mock_model(client, monkeypatch):
    class DummyModel:
        def predict(self, rows):
            assert rows[0] == [1, 1, 75, 1, 8, 0, 1, 7, 8, 70]
            return ["medium"]

    monkeypatch.setattr(app_module, "load_model", lambda: DummyModel())
    monkeypatch.setattr(app_module, "load_scaler", lambda: None)

    response = client.post(
        "/predict",
        data={
            "firewall_status": "Yes",
            "mfa_usage": "Yes",
            "encryption_usage": "Yes",
            "employee_training_score": 75,
            "phishing_test_score": 70,
            "unpatched_vulnerabilities": 1,
            "incident_history_count": 0,
            "password_policy_strength": 8,
            "backup_frequency_days": 7,
            "network_monitoring_level": 8,
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Medium" in response.data
    assert b"Improve awareness and monitoring for stronger protection." in response.data


def test_predict_page_prefills_last_assessment_inputs(client):
    with client.session_transaction() as session:
        session["last_assessment_inputs"] = {
            "organization_name": "ABC Finance",
            "industry_sector": "Finance",
            "organization_size": "Medium (51-250 employees)",
            "assessment_owner": "Security Lead",
            "remote_workforce_level": "High",
            "critical_data_exposure": "High",
            "firewall_status": "No",
            "mfa_usage": "Yes",
            "encryption_usage": "No",
            "employee_training_score": 45,
            "phishing_test_score": 40,
            "unpatched_vulnerabilities": 9,
            "incident_history_count": 3,
            "password_policy_strength": 5,
            "backup_frequency_days": 21,
            "network_monitoring_level": 4,
        }

    response = client.get("/predict-risk")
    assert response.status_code == 200
    assert b"ABC Finance" in response.data
    assert b"Security Lead" in response.data
    assert b'value="No" selected' in response.data
