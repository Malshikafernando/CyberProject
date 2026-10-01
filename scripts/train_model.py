"""Train the role-based cybersecurity risk model and deployment package."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = BASE_DIR / "Role_Based_Cybersecurity_Risk_Dataset_5500.xlsx"
DEFAULT_MODEL = BASE_DIR / "role_based_cybersecurity_risk_model.pkl"
DEFAULT_REPORT = BASE_DIR / "role_based_model_report.json"
TARGET = "risk_level"
GROUP_COLUMN = "organization_id"
RANDOM_STATE = 42

EXCLUDED_COLUMNS = [
    "record_id",
    "organization_id",
    "assessment_date",
    "data_source",
    "overall_risk_score",
    "role_risk_score",
    "risk_level",
    "primary_risk_category",
    "recommendation_priority",
    "recommended_action_codes",
    "training_focus_area",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--model-output", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def load_data(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    employee_data = pd.read_excel(path, sheet_name="Employee_Risk_Data")
    dictionary = pd.read_excel(path, sheet_name="Data_Dictionary")
    recommendation_rules = pd.read_excel(path, sheet_name="Recommendation_Rules")

    required = set(EXCLUDED_COLUMNS + [GROUP_COLUMN, TARGET])
    missing = sorted(required.difference(employee_data.columns))
    if missing:
        raise ValueError(f"Employee_Risk_Data is missing columns: {missing}")

    X = employee_data.drop(columns=EXCLUDED_COLUMNS).copy()
    y = employee_data[TARGET].astype("string").str.strip().str.title()
    groups = employee_data[GROUP_COLUMN].astype("string")

    if set(y.unique()) != {"Low", "Medium", "High"}:
        raise ValueError(f"Unexpected risk labels: {sorted(y.unique())}")
    if X.columns.duplicated().any():
        raise ValueError("Duplicate input feature names were found.")
    if X.isna().all(axis=0).any():
        raise ValueError("At least one input feature contains no usable values.")

    return employee_data, X, y, groups, dictionary, recommendation_rules


def make_preprocessor(X: pd.DataFrame) -> tuple[ColumnTransformer, list[str], list[str]]:
    numerical = X.select_dtypes(include="number").columns.tolist()
    categorical = X.select_dtypes(exclude="number").columns.tolist()
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numerical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numerical,
            ),
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical,
            ),
        ]
    )
    return preprocessor, numerical, categorical


def candidate_models(preprocessor: ColumnTransformer) -> dict[str, Pipeline]:
    return {
        "logistic_regression": Pipeline(
            [
                ("preprocessor", clone(preprocessor)),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=3000,
                        class_weight="balanced",
                        solver="saga",
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
        "random_forest": Pipeline(
            [
                ("preprocessor", clone(preprocessor)),
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=600,
                        max_features="sqrt",
                        min_samples_leaf=1,
                        class_weight="balanced_subsample",
                        random_state=RANDOM_STATE,
                        n_jobs=1,
                    ),
                ),
            ]
        ),
        "extra_trees": Pipeline(
            [
                ("preprocessor", clone(preprocessor)),
                (
                    "classifier",
                    ExtraTreesClassifier(
                        n_estimators=600,
                        max_features="sqrt",
                        min_samples_leaf=1,
                        class_weight="balanced",
                        random_state=RANDOM_STATE,
                        n_jobs=1,
                    ),
                ),
            ]
        ),
    }


def evaluate_candidates(
    models: dict[str, Pipeline],
    X_train: pd.DataFrame,
    y_train: pd.Series,
    train_groups: pd.Series,
) -> tuple[str, dict]:
    group_cv = GroupKFold(n_splits=5)
    scoring = {
        "accuracy": "accuracy",
        "balanced_accuracy": "balanced_accuracy",
        "macro_f1": "f1_macro",
    }
    results = {}
    for name, model in models.items():
        scores = cross_validate(
            model,
            X_train,
            y_train,
            groups=train_groups,
            cv=group_cv,
            scoring=scoring,
            n_jobs=-1,
            error_score="raise",
        )
        results[name] = {
            metric.removeprefix("test_"): {
                "mean": round(float(values.mean()), 6),
                "std": round(float(values.std()), 6),
            }
            for metric, values in scores.items()
            if metric.startswith("test_")
        }

    best_name = max(
        results,
        key=lambda name: (
            results[name]["macro_f1"]["mean"],
            results[name]["balanced_accuracy"]["mean"],
        ),
    )
    return best_name, results


def friendly_label(name: str) -> str:
    replacements = {"Mfa": "MFA", "Vpn": "VPN", "Edr": "EDR", "12m": "12 months", "30d": "30 days"}
    label = name.replace("_", " ").title()
    for original, replacement in replacements.items():
        label = label.replace(original, replacement)
    return label


def build_field_schema(
    X: pd.DataFrame,
    dictionary: pd.DataFrame,
    numerical: list[str],
    categorical: list[str],
) -> list[dict]:
    lookup = dictionary.set_index("column_name")
    schema = []
    for name in X.columns:
        metadata = lookup.loc[name]
        data_type = str(metadata["data_type"])
        field = {
            "name": name,
            "label": friendly_label(name),
            "group": str(metadata["category"]),
            "description": str(metadata["description"]),
        }
        if data_type == "Binary":
            field.update(
                input_kind="binary",
                options=[{"value": "1", "label": "Yes"}, {"value": "0", "label": "No"}],
                default=str(int(X[name].mode().iloc[0])),
            )
        elif name in categorical:
            options = sorted(str(value) for value in X[name].dropna().unique())
            field.update(input_kind="select", options=options, default=str(X[name].mode().iloc[0]))
        elif name in numerical:
            integer = pd.api.types.is_integer_dtype(X[name])
            median = float(X[name].median())
            field.update(
                input_kind="number",
                minimum=float(X[name].min()),
                maximum=float(X[name].max()),
                step=1 if integer else 0.1,
                default=int(round(median)) if integer else round(median, 1),
                numeric_type="int" if integer else "float",
            )
        schema.append(field)
    return schema


def extract_feature_importance(model: Pipeline) -> list[dict]:
    classifier = model.named_steps["classifier"]
    if not hasattr(classifier, "feature_importances_"):
        return []
    names = model.named_steps["preprocessor"].get_feature_names_out()
    rows = sorted(
        zip(names, classifier.feature_importances_),
        key=lambda item: item[1],
        reverse=True,
    )[:30]
    return [
        {
            "feature": name.replace("numerical__", "").replace("categorical__", ""),
            "importance": round(float(importance), 8),
        }
        for name, importance in rows
    ]


def main() -> None:
    args = parse_args()
    dataset_path = args.dataset.resolve()
    model_path = args.model_output.resolve()
    report_path = args.report_output.resolve()
    employee_data, X, y, groups, dictionary, rules = load_data(dataset_path)
    preprocessor, numerical, categorical = make_preprocessor(X)

    splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=RANDOM_STATE)
    train_index, test_index = next(splitter.split(X, y, groups))
    X_train, X_test = X.iloc[train_index], X.iloc[test_index]
    y_train, y_test = y.iloc[train_index], y.iloc[test_index]
    train_groups, test_groups = groups.iloc[train_index], groups.iloc[test_index]
    overlap = set(train_groups).intersection(test_groups)
    if overlap:
        raise RuntimeError("Organization leakage detected between train and test data.")

    models = candidate_models(preprocessor)
    best_name, cv_results = evaluate_candidates(models, X_train, y_train, train_groups)
    holdout_model = clone(models[best_name]).fit(X_train, y_train)
    predictions = holdout_model.predict(X_test)
    class_order = ["Low", "Medium", "High"]
    holdout_metrics = {
        "accuracy": round(float(accuracy_score(y_test, predictions)), 6),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_test, predictions)), 6),
        "macro_f1": round(float(f1_score(y_test, predictions, average="macro")), 6),
        "confusion_matrix_labels": class_order,
        "confusion_matrix": confusion_matrix(y_test, predictions, labels=class_order).tolist(),
        "classification_report": classification_report(
            y_test, predictions, labels=class_order, output_dict=True, zero_division=0
        ),
    }

    final_model = clone(models[best_name]).fit(X, y)
    field_schema = build_field_schema(X, dictionary, numerical, categorical)
    role_department_map = (
        employee_data.groupby("employee_role")["department"].first().astype(str).to_dict()
    )
    package = {
        "model_name": "Role-Based Cybersecurity Risk Prediction Model",
        "model_version": "2.0.0",
        "pipeline": final_model,
        "target_column": TARGET,
        "class_labels": final_model.named_steps["classifier"].classes_.tolist(),
        "feature_columns": X.columns.tolist(),
        "numerical_features": numerical,
        "categorical_features": categorical,
        "excluded_columns": EXCLUDED_COLUMNS,
        "field_schema": field_schema,
        "role_department_map": role_department_map,
        "recommendation_rules": rules.replace({np.nan: None}).to_dict(orient="records"),
        "selected_model": best_name,
        "evaluation_metrics": holdout_metrics,
        "training_records_final": int(len(X)),
        "holdout_records": int(len(X_test)),
        "training_organizations": int(train_groups.nunique()),
        "testing_organizations": int(test_groups.nunique()),
        "random_state": RANDOM_STATE,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_notice": "Trained on a synthetic academic research dataset.",
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(package, model_path, compress=3)
    checksum = hashlib.sha256(model_path.read_bytes()).hexdigest()

    report = {
        "model_name": package["model_name"],
        "model_version": package["model_version"],
        "dataset": str(dataset_path),
        "dataset_rows": int(len(employee_data)),
        "input_features": int(X.shape[1]),
        "target_distribution": {key: int(value) for key, value in y.value_counts().items()},
        "organization_group_split": {
            "training_organizations": package["training_organizations"],
            "testing_organizations": package["testing_organizations"],
            "overlap": 0,
        },
        "selected_model": best_name,
        "selection_metric": "macro_f1",
        "cross_validation_on_training_organizations": cv_results,
        "unseen_organization_holdout": holdout_metrics,
        "top_feature_importance": extract_feature_importance(final_model),
        "model_sha256": checksum,
        "library_versions": {
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
        "trained_at_utc": package["trained_at_utc"],
        "data_notice": package["data_notice"],
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Dataset rows: {len(X):,}; input features: {X.shape[1]}")
    print(f"Train/test organizations: {train_groups.nunique()}/{test_groups.nunique()}; overlap: 0")
    for name, metrics in cv_results.items():
        print(
            f"{name}: CV macro-F1={metrics['macro_f1']['mean']:.4f} "
            f"(+/- {metrics['macro_f1']['std']:.4f})"
        )
    print(f"Selected: {best_name}")
    print(
        f"Unseen-organization holdout: accuracy={holdout_metrics['accuracy']:.4f}, "
        f"balanced accuracy={holdout_metrics['balanced_accuracy']:.4f}, "
        f"macro-F1={holdout_metrics['macro_f1']:.4f}"
    )
    print(classification_report(y_test, predictions, labels=class_order, zero_division=0))
    print(f"Saved model package: {model_path}")
    print(f"SHA-256: {checksum}")


if __name__ == "__main__":
    main()
