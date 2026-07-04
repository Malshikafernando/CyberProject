from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split


BASE_DIR = Path(__file__).resolve().parents[1]
DATASET_PATH = BASE_DIR.parent / "cybersecurity_dataset.xlsx"
MODEL_PATH = BASE_DIR / "cyber_model.pkl"

FEATURE_COLUMNS = [
    "firewall_status",
    "mfa_usage",
    "employee_training_score",
    "unpatched_vulnerabilities",
    "password_policy_strength",
    "incident_history_count",
    "encryption_usage",
    "backup_frequency_days",
    "network_monitoring_level",
    "phishing_test_score",
]
TARGET_COLUMN = "security_risk_level"


def main():
    df = pd.read_excel(DATASET_PATH)
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN].astype(str).str.lower()

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=250,
        max_depth=12,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)

    print(f"Dataset shape: {df.shape}")
    print(f"Model accuracy: {accuracy:.4f}")
    print("Classification report:")
    print(classification_report(y_test, predictions))

    joblib.dump(model, MODEL_PATH, compress=3)
    print(f"Saved model to {MODEL_PATH}")


if __name__ == "__main__":
    main()
