from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
import os
from pathlib import Path

import joblib
import pandas as pd
from flask import Flask, flash, redirect, render_template, request, send_file, session, url_for

from reporting import build_risk_report_pdf


# Vercel serves files from ``public/`` at the site root.  Using the same URL
# layout in Flask keeps generated asset links working locally and in production.
app = Flask(__name__, static_folder="public", static_url_path="")
app.secret_key = os.getenv("SECRET_KEY", "cyber_risk_secret_2026")

BASE_DIR = Path(__file__).parent
MODEL_PATH = BASE_DIR / "role_based_cybersecurity_risk_model.pkl"

model_package = None
model_load_attempted = False


def load_model_package():
    global model_package, model_load_attempted
    if model_load_attempted:
        return model_package
    model_load_attempted = True
    if not MODEL_PATH.exists():
        print(f"Warning: Model package not found at {MODEL_PATH}")
        return None
    try:
        loaded = joblib.load(MODEL_PATH)
        required_keys = {"pipeline", "feature_columns", "field_schema", "class_labels"}
        if not isinstance(loaded, dict) or not required_keys.issubset(loaded):
            raise ValueError("The model package has an unsupported structure.")
        model_package = loaded
    except Exception as error:
        print(f"Warning: Unable to load model package: {error}")
        model_package = None
    return model_package


def grouped_form_fields(package):
    groups = OrderedDict()
    for field in package["field_schema"]:
        groups.setdefault(field["group"], []).append(field)
    return [{"title": title, "fields": fields} for title, fields in groups.items()]


def default_form_values(package=None):
    package = package or load_model_package()
    if package is None:
        return {}
    defaults = {field["name"]: field["default"] for field in package["field_schema"]}
    selected_role = defaults.get("employee_role")
    expected_department = package.get("role_department_map", {}).get(selected_role)
    if expected_department:
        defaults["department"] = expected_department
    defaults["assessment_reference"] = ""
    return defaults


def parse_assessment(form_data, package) -> tuple[pd.DataFrame, dict]:
    parsed = {}
    for field in package["field_schema"]:
        name = field["name"]
        raw_value = form_data.get(name)
        if raw_value is None or str(raw_value).strip() == "":
            raise ValueError(f"{field['label']} is required.")
        value = str(raw_value).strip()

        if field["input_kind"] == "binary":
            normalized = value.lower()
            if normalized in {"1", "yes", "true", "on"}:
                parsed[name] = 1
            elif normalized in {"0", "no", "false", "off"}:
                parsed[name] = 0
            else:
                raise ValueError(f"{field['label']} must be Yes or No.")
        elif field["input_kind"] == "select":
            if value not in field["options"]:
                raise ValueError(f"Invalid value for {field['label']}.")
            parsed[name] = value
        else:
            try:
                numeric_value = float(value)
            except ValueError as error:
                raise ValueError(f"{field['label']} must be numeric.") from error
            if numeric_value < field["minimum"] or numeric_value > field["maximum"]:
                raise ValueError(
                    f"{field['label']} must be between {field['minimum']:g} and {field['maximum']:g}."
                )
            parsed[name] = int(numeric_value) if field["numeric_type"] == "int" else numeric_value

    frame = pd.DataFrame([parsed]).reindex(columns=package["feature_columns"])
    expected_department = package.get("role_department_map", {}).get(parsed.get("employee_role"))
    if expected_department and parsed.get("department") != expected_department:
        raise ValueError(
            f"Department must be {expected_department} for the selected employee role."
        )
    if frame.columns.tolist() != package["feature_columns"]:
        raise ValueError("Assessment fields do not match the trained model schema.")
    return frame, parsed


def rule_matches(rule, inputs, risk_level) -> bool:
    if rule["applicable_industry"] not in {"All", inputs.get("industry")}:
        return False
    if rule["employee_role"] not in {"All", inputs.get("employee_role")}:
        return False
    if rule["risk_level"] == "Medium or High" and risk_level not in {"Medium", "High"}:
        return False
    if rule["risk_level"] not in {"Any", "Medium or High", risk_level}:
        return False

    actual = inputs.get(rule["trigger_feature"])
    expected_text = str(rule["trigger_value"])
    operator = rule["trigger_operator"]
    try:
        expected = float(expected_text)
        actual_comparable = float(actual)
    except (TypeError, ValueError):
        expected = expected_text
        actual_comparable = str(actual)

    if operator == "equals":
        return actual_comparable == expected
    if operator == "greater than":
        return actual_comparable > expected
    if operator == "less than":
        return actual_comparable < expected
    if operator == "greater than or equal to":
        return actual_comparable >= expected
    return False


def matched_recommendations(package, inputs, risk_level):
    priority_order = {"Immediate": 0, "High": 1, "Medium": 2, "Preventive": 3}
    matches = [
        rule
        for rule in package.get("recommendation_rules", [])
        if rule_matches(rule, inputs, risk_level)
    ]
    matches.sort(key=lambda rule: (priority_order.get(rule["priority"], 99), rule["recommendation_id"]))
    return matches[:8]


def risk_badge_meta(level):
    if level == "High":
        return {"label": "High Risk", "accent": "#ff6b6b", "panel": "panel-high"}
    if level == "Medium":
        return {"label": "Medium Risk", "accent": "#ffbf47", "panel": "panel-medium"}
    return {"label": "Low Risk", "accent": "#26d07c", "panel": "panel-low"}


def display_value(field, value):
    if field["input_kind"] == "binary":
        return "Yes" if int(value) == 1 else "No"
    return value


def report_input_sections(package, inputs):
    sections = []
    for group in grouped_form_fields(package):
        sections.append(
            {
                "title": group["title"],
                "items": [
                    (field["label"], display_value(field, inputs[field["name"]]))
                    for field in group["fields"]
                    if field["name"] in inputs
                ],
            }
        )
    return sections


def build_report_context(prediction, package):
    probabilities = prediction["probabilities"]
    recommendations = prediction.get("recommendation_details", [])
    concerns = [item["recommendation_title"] for item in recommendations]
    strengths = []
    inputs = prediction.get("inputs", {})
    for field_name, label in (
        ("mfa_enabled", "Multi-factor authentication is enabled."),
        ("endpoint_protection_enabled", "Endpoint protection is enabled."),
        ("device_encryption_enabled", "Device encryption is enabled."),
        ("network_monitoring_enabled", "Network monitoring is enabled."),
        ("security_training_completed", "Security training is complete."),
    ):
        if inputs.get(field_name) == 1:
            strengths.append(label)
    if not strengths:
        strengths.append("No major control strength was identified from the selected baseline checks.")
    if not concerns:
        concerns.append("No recommendation rule was triggered by the submitted assessment.")

    return {
        "generated_at": datetime.now().strftime("%B %d, %Y %I:%M %p"),
        "risk_level": prediction["risk_level"],
        "recommendation": prediction["recommendation"],
        "recommendations": [item["recommendation_description"] for item in recommendations]
        or [prediction["recommendation"]],
        "explanation": prediction["explanation"],
        "input_sections": report_input_sections(package, inputs),
        "strengths": strengths,
        "concerns": concerns,
        "bars": {label: round(probability * 100) for label, probability in probabilities.items()},
        "badge": risk_badge_meta(prediction["risk_level"]),
        "confidence": prediction.get("confidence"),
        "action_priority": prediction.get("action_priority"),
        "training_focus": prediction.get("training_focus"),
        "assessment_reference": prediction.get("assessment_reference"),
        "model_version": prediction.get("model_version"),
        "recommendation_details": recommendations,
    }


@app.route("/")
def home():
    return render_template("index.html", title="Home", active="home")


@app.route("/predict-risk")
def predict_page():
    package = load_model_package()
    if package is None:
        flash("Prediction model is unavailable. Train or restore the role-based model package.")
        return render_template(
            "predict.html",
            title="Predict Risk",
            active="predict",
            form_defaults={},
            form_groups=[],
            role_department_map={},
        )
    form_defaults = default_form_values(package)
    form_defaults.update(session.get("last_assessment_inputs", {}))
    return render_template(
        "predict.html",
        title="Predict Risk",
        active="predict",
        form_defaults=form_defaults,
        form_groups=grouped_form_fields(package),
        model_version=package["model_version"],
        role_department_map=package.get("role_department_map", {}),
    )


@app.route("/predict", methods=["POST"])
def predict():
    package = load_model_package()
    if package is None:
        flash("Prediction model is unavailable.")
        return redirect(url_for("predict_page"))
    try:
        frame, parsed_inputs = parse_assessment(request.form, package)
        pipeline = package["pipeline"]
        risk_level = str(pipeline.predict(frame)[0]).title()
        probability_values = pipeline.predict_proba(frame)[0]
        probability_lookup = {
            str(label).title(): round(float(probability), 6)
            for label, probability in zip(package["class_labels"], probability_values)
        }
        probabilities = {
            label: probability_lookup[label] for label in ("Low", "Medium", "High")
        }
        confidence = max(probabilities.values())
        recommendations = matched_recommendations(package, parsed_inputs, risk_level)
        risk_categories = list(
            dict.fromkeys(item["risk_category"] for item in recommendations)
        )[:4]
        training_focus = (
            recommendations[0]["awareness_topic"] if recommendations else "General security awareness"
        )
        action_priority = recommendations[0]["priority"] if recommendations else "Preventive"
        primary_recommendation = (
            recommendations[0]["recommendation_description"]
            if recommendations
            else "Maintain existing controls and repeat the assessment after material security changes."
        )
        explanation = (
            f"The role-based model evaluated {len(package['feature_columns'])} organization, access, "
            f"control, awareness, vulnerability, and incident indicators. Its confidence in the "
            f"{risk_level} classification is {confidence * 100:.1f}%."
        )
        prediction_result = {
            "risk_level": risk_level,
            "confidence": round(confidence * 100, 1),
            "probabilities": probabilities,
            "recommendation": primary_recommendation,
            "recommendation_details": recommendations,
            "risk_categories": risk_categories,
            "training_focus": training_focus,
            "action_priority": action_priority,
            "explanation": explanation,
            "inputs": parsed_inputs,
            "assessment_reference": request.form.get("assessment_reference", "").strip(),
            "model_version": package["model_version"],
        }
        session["prediction_result"] = prediction_result
        session["last_assessment_inputs"] = parsed_inputs
        return redirect(url_for("results"))
    except ValueError as error:
        flash(str(error))
        return redirect(url_for("predict_page"))
    except Exception as error:
        app.logger.exception("Prediction failed")
        flash(f"Unable to process prediction: {error}")
        return redirect(url_for("predict_page"))


@app.route("/results")
def results():
    prediction = session.get("prediction_result")
    if not prediction:
        return redirect(url_for("predict_page"))
    color_map = {"Low": "green", "Medium": "yellow", "High": "red"}
    return render_template(
        "results.html",
        title="Results",
        active="results",
        color=color_map.get(prediction["risk_level"], "blue"),
        **prediction,
    )


@app.route("/download-report")
def download_report():
    prediction = session.get("prediction_result")
    package = load_model_package()
    if not prediction or package is None:
        flash("Please generate a prediction before downloading a report.")
        return redirect(url_for("predict_page"))
    report_pdf = build_risk_report_pdf(
        build_report_context(prediction, package),
        BASE_DIR / "public" / "images" / "cyberrisk-compass-logo.png",
    )
    return send_file(
        report_pdf,
        as_attachment=True,
        download_name="cyberrisk-compass-assessment-report.pdf",
        mimetype="application/pdf",
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
    email = request.form.get("email", "").strip()
    message = request.form.get("message", "").strip()
    if not email or not message:
        flash("Please provide both your email and message.")
        return redirect(url_for("contact"))
    flash(f"Thank you, {name}! Your message has been received. We will respond to {email} soon.")
    return redirect(url_for("contact"))


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
