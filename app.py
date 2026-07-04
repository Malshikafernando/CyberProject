from datetime import datetime
from io import BytesIO
import os
from pathlib import Path

import joblib
from flask import Flask, flash, redirect, render_template, request, send_file, session, url_for

app = Flask(__name__, static_folder="public", static_url_path="/static")
app.secret_key = os.getenv("SECRET_KEY", "cyber_risk_secret_2026")

BASE_DIR = Path(__file__).parent
MODEL_PATH = BASE_DIR / "cyber_model.pkl"
SCALER_PATH = BASE_DIR / "scaler.pkl"

model = None
scaler = None
model_load_attempted = False
scaler_load_attempted = False


def load_model():
    global model, model_load_attempted
    if model_load_attempted:
        return model

    model_load_attempted = True
    if not MODEL_PATH.exists():
        print(f"Warning: Model file not found at {MODEL_PATH}")
        return None

    try:
        model = joblib.load(MODEL_PATH)
    except Exception as error:
        print(f"Warning: Unable to load model: {error}")
        model = None
    return model


def load_scaler():
    global scaler, scaler_load_attempted
    if scaler_load_attempted:
        return scaler

    scaler_load_attempted = True
    if not SCALER_PATH.exists():
        return None

    try:
        scaler = joblib.load(SCALER_PATH)
    except Exception as error:
        print(f"Warning: Unable to load scaler: {error}")
        scaler = None
    return scaler


def normalize_yes_no(value):
    return 1 if str(value).strip().lower() in ("yes", "y", "1", "true", "on") else 0


def yes_no_label(value):
    return "Yes" if normalize_yes_no(value) else "No"


def default_form_values():
    return {
        "organization_name": "",
        "industry_sector": "Technology",
        "organization_size": "Small (1-50 employees)",
        "assessment_owner": "",
        "remote_workforce_level": "Moderate",
        "critical_data_exposure": "Medium",
        "firewall_status": "Yes",
        "mfa_usage": "Yes",
        "encryption_usage": "Yes",
        "employee_training_score": 60,
        "phishing_test_score": 55,
        "unpatched_vulnerabilities": 2,
        "incident_history_count": 1,
        "password_policy_strength": 7,
        "backup_frequency_days": 14,
        "network_monitoring_level": 6,
    }


def build_feature_vector(form_data):
    features = [
        normalize_yes_no(form_data.get("firewall_status")),
        normalize_yes_no(form_data.get("mfa_usage")),
        int(form_data.get("employee_training_score", 0)),
        int(form_data.get("unpatched_vulnerabilities", 0)),
        int(form_data.get("password_policy_strength", 1)),
        int(form_data.get("incident_history_count", 0)),
        normalize_yes_no(form_data.get("encryption_usage")),
        int(form_data.get("backup_frequency_days", 0)),
        int(form_data.get("network_monitoring_level", 1)),
        int(form_data.get("phishing_test_score", 0)),
    ]
    active_scaler = load_scaler()
    if active_scaler is not None:
        features = active_scaler.transform([features])[0].tolist()
    return features


def build_input_snapshot(form_data):
    return {
        "organization_name": str(form_data.get("organization_name", "")).strip() or "Not specified",
        "industry_sector": str(form_data.get("industry_sector", "Not specified")).strip() or "Not specified",
        "organization_size": str(form_data.get("organization_size", "Not specified")).strip() or "Not specified",
        "assessment_owner": str(form_data.get("assessment_owner", "")).strip() or "Not specified",
        "remote_workforce_level": str(form_data.get("remote_workforce_level", "Not specified")).strip() or "Not specified",
        "critical_data_exposure": str(form_data.get("critical_data_exposure", "Not specified")).strip() or "Not specified",
        "firewall_status": yes_no_label(form_data.get("firewall_status")),
        "mfa_usage": yes_no_label(form_data.get("mfa_usage")),
        "encryption_usage": yes_no_label(form_data.get("encryption_usage")),
        "employee_training_score": int(form_data.get("employee_training_score", 0)),
        "phishing_test_score": int(form_data.get("phishing_test_score", 0)),
        "unpatched_vulnerabilities": int(form_data.get("unpatched_vulnerabilities", 0)),
        "incident_history_count": int(form_data.get("incident_history_count", 0)),
        "password_policy_strength": int(form_data.get("password_policy_strength", 1)),
        "backup_frequency_days": int(form_data.get("backup_frequency_days", 0)),
        "network_monitoring_level": int(form_data.get("network_monitoring_level", 1)),
    }


def normalize_prediction(prediction):
    return str(prediction).strip().capitalize()


def recommendation_for_level(level):
    if level == "High":
        return "Immediate action required. Enable MFA, fix vulnerabilities, and strengthen policies."
    if level == "Medium":
        return "Improve awareness and monitoring for stronger protection."
    return "Maintain current security practices and continue strengthening your defenses."


def recommendation_list_for_level(level):
    if level == "High":
        return [
            "Enforce MFA across all remote access, email, and privileged accounts immediately.",
            "Reduce unpatched vulnerabilities through a prioritized remediation plan within the next review cycle.",
            "Increase monitoring coverage and alert review frequency for critical assets.",
            "Run focused phishing awareness drills and incident response walkthroughs.",
        ]
    if level == "Medium":
        return [
            "Strengthen employee awareness and phishing simulation frequency.",
            "Improve security monitoring maturity and escalation procedures.",
            "Review backup cadence and validate restoration readiness.",
            "Address medium-priority vulnerabilities before they accumulate into larger exposure.",
        ]
    return [
        "Maintain the current baseline of controls and awareness training.",
        "Continue periodic patching, backup validation, and monitoring reviews.",
        "Track emerging threats and repeat risk assessment regularly.",
        "Use the current posture as a benchmark for future comparisons.",
    ]


def input_sections(snapshot):
    return [
        {
            "title": "Assessment Profile",
            "items": [
                ("Organization Name", snapshot["organization_name"]),
                ("Industry Sector", snapshot["industry_sector"]),
                ("Organization Size", snapshot["organization_size"]),
                ("Assessment Owner", snapshot["assessment_owner"]),
                ("Remote Workforce Level", snapshot["remote_workforce_level"]),
                ("Critical Data Exposure", snapshot["critical_data_exposure"]),
            ],
        },
        {
            "title": "Security Controls",
            "items": [
                ("Firewall Status", snapshot["firewall_status"]),
                ("MFA Usage", snapshot["mfa_usage"]),
                ("Encryption Usage", snapshot["encryption_usage"]),
            ],
        },
        {
            "title": "Human Awareness",
            "items": [
                ("Employee Training Score", snapshot["employee_training_score"]),
                ("Phishing Test Score", snapshot["phishing_test_score"]),
            ],
        },
        {
            "title": "Vulnerabilities and Incidents",
            "items": [
                ("Unpatched Vulnerabilities", snapshot["unpatched_vulnerabilities"]),
                ("Incident History Count", snapshot["incident_history_count"]),
            ],
        },
        {
            "title": "Policies and Monitoring",
            "items": [
                ("Password Policy Strength", snapshot["password_policy_strength"]),
                ("Backup Frequency (days)", snapshot["backup_frequency_days"]),
                ("Network Monitoring Level", snapshot["network_monitoring_level"]),
            ],
        },
    ]


def derive_strengths(snapshot):
    strengths = []
    if snapshot["firewall_status"] == "Yes":
        strengths.append("Firewall protection is active.")
    if snapshot["mfa_usage"] == "Yes":
        strengths.append("Multi-factor authentication is enabled.")
    if snapshot["encryption_usage"] == "Yes":
        strengths.append("Encryption is being used to protect data.")
    if snapshot["employee_training_score"] >= 70:
        strengths.append("Employee awareness training score is comparatively strong.")
    if snapshot["phishing_test_score"] >= 70:
        strengths.append("Phishing readiness indicates better user awareness.")
    if snapshot["network_monitoring_level"] >= 7:
        strengths.append("Monitoring maturity is above the minimum baseline.")
    if snapshot["backup_frequency_days"] <= 7:
        strengths.append("Backup frequency supports stronger recovery readiness.")
    return strengths or ["The environment shows some baseline controls, but improvement opportunities remain."]


def derive_concerns(snapshot):
    concerns = []
    if snapshot["firewall_status"] == "No":
        concerns.append("Firewall protection is not active.")
    if snapshot["mfa_usage"] == "No":
        concerns.append("MFA is not enabled, increasing account compromise risk.")
    if snapshot["encryption_usage"] == "No":
        concerns.append("Encryption is not enabled for broader data protection.")
    if snapshot["employee_training_score"] < 60:
        concerns.append("Training score suggests awareness maturity is below target.")
    if snapshot["phishing_test_score"] < 60:
        concerns.append("Phishing readiness is below the preferred defensive threshold.")
    if snapshot["unpatched_vulnerabilities"] > 10:
        concerns.append("The number of unpatched vulnerabilities is high.")
    if snapshot["incident_history_count"] > 2:
        concerns.append("Incident history suggests repeated operational exposure.")
    if snapshot["password_policy_strength"] < 6:
        concerns.append("Password policy strength is weaker than recommended.")
    if snapshot["backup_frequency_days"] > 14:
        concerns.append("Backup intervals may be too infrequent for reliable recovery.")
    if snapshot["network_monitoring_level"] < 6:
        concerns.append("Monitoring maturity is below the recommended operating level.")
    return concerns or ["No major red-flag indicators were detected from the submitted inputs."]


def score_bars(snapshot):
    security_controls = round(
        (
            normalize_yes_no(snapshot["firewall_status"])
            + normalize_yes_no(snapshot["mfa_usage"])
            + normalize_yes_no(snapshot["encryption_usage"])
            + min(snapshot["password_policy_strength"], 10) / 10
        )
        / 4
        * 100
    )
    awareness = round((snapshot["employee_training_score"] + snapshot["phishing_test_score"]) / 2)
    monitoring = round(
        (
            min(snapshot["network_monitoring_level"], 10) / 10 * 0.6
            + max(0, (30 - min(snapshot["backup_frequency_days"], 30))) / 30 * 0.4
        )
        * 100
    )
    return {
        "Security Controls": security_controls,
        "Human Awareness": awareness,
        "Monitoring Readiness": monitoring,
    }


def risk_badge_meta(level):
    if level == "High":
        return {"label": "High Risk", "accent": "#ff6b6b", "panel": "panel-high"}
    if level == "Medium":
        return {"label": "Medium Risk", "accent": "#ffbf47", "panel": "panel-medium"}
    return {"label": "Low Risk", "accent": "#26d07c", "panel": "panel-low"}


def build_report_context(prediction):
    snapshot = default_form_values()
    snapshot.update(prediction.get("inputs", {}))
    level = prediction["risk_level"]
    return {
        "generated_at": datetime.now().strftime("%B %d, %Y %I:%M %p"),
        "risk_level": level,
        "recommendation": prediction["recommendation"],
        "recommendations": recommendation_list_for_level(level),
        "explanation": prediction["explanation"],
        "input_sections": input_sections(snapshot),
        "strengths": derive_strengths(snapshot),
        "concerns": derive_concerns(snapshot),
        "bars": score_bars(snapshot),
        "badge": risk_badge_meta(level),
    }


@app.route("/")
def home():
    return render_template("index.html", title="Home", active="home")


@app.route("/predict-risk")
def predict_page():
    saved_inputs = session.get("last_assessment_inputs", {})
    form_defaults = default_form_values()
    form_defaults.update(saved_inputs)
    return render_template("predict.html", title="Predict Risk", active="predict", form_defaults=form_defaults)


@app.route("/predict", methods=["POST"])
def predict():
    active_model = load_model()
    if active_model is None:
        flash("Prediction model is unavailable. Please verify cyber_model.pkl or use a smaller trained model.")
        return redirect(url_for("predict_page"))

    try:
        features = build_feature_vector(request.form)
        prediction = active_model.predict([features])[0]
        risk_level = normalize_prediction(prediction)
        recommendation = recommendation_for_level(risk_level)
        explanation = (
            "The model uses your security controls, awareness metrics, and incident history "
            "to determine the likely risk category for your environment."
        )

        session["prediction_result"] = {
            "risk_level": risk_level,
            "recommendation": recommendation,
            "explanation": explanation,
            "inputs": build_input_snapshot(request.form),
        }
        session["last_assessment_inputs"] = {
            key: request.form.get(key, default_form_values().get(key, ""))
            for key in default_form_values().keys()
        }
        return redirect(url_for("results"))
    except Exception as error:
        flash(f"Unable to process prediction: {error}")
        return redirect(url_for("predict_page"))


@app.route("/results")
def results():
    prediction = session.get("prediction_result")
    if not prediction:
        return redirect(url_for("predict_page"))

    color_map = {
        "Low": "green",
        "Medium": "yellow",
        "High": "red",
    }
    prediction["color"] = color_map.get(prediction["risk_level"], "blue")
    return render_template("results.html", title="Results", active="results", **prediction)


@app.route("/download-report")
def download_report():
    prediction = session.get("prediction_result")
    if not prediction:
        flash("Please generate a prediction before downloading a report.")
        return redirect(url_for("predict_page"))

    report_html = render_template("report_download.html", **build_report_context(prediction))
    report_bytes = BytesIO(report_html.encode("utf-8"))
    return send_file(
        report_bytes,
        as_attachment=True,
        download_name="cyber-risk-report.doc",
        mimetype="application/msword",
    )


@app.route("/insights")
def insights():
    return render_template("insights.html", title="Insights", active="insights")


@app.route("/research")
def research():
    return render_template("research.html", title="Research", active="research")


@app.route("/awareness")
def awareness():
    return render_template("awareness.html", title="Awareness Hub", active="awareness")


@app.route("/faq")
def faq():
    return render_template("faq.html", title="FAQ", active="faq")


@app.route("/contact")
def contact():
    return render_template("contact.html", title="Contact", active="contact")


@app.route("/submit-contact", methods=["POST"])
def submit_contact():
    name = request.form.get("name", "Visitor").strip()
    email = request.form.get("email", "not provided").strip()
    message = request.form.get("message", "").strip()

    if not email or not message:
        flash("Please provide both your email and message.")
        return redirect(url_for("contact"))

    flash(f"Thank you, {name}! Your message has been received. We will respond to {email} soon.")
    return redirect(url_for("contact"))


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
