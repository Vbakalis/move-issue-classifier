"""
Simple baseline: TF-IDF features + classical classifiers (LogReg, SVM, RF).
"""

import argparse
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline

try:
    from src.evaluate import compute_metrics, print_metrics, plot_confusion_matrix, error_analysis, save_results
except ImportError:
    from evaluate import compute_metrics, print_metrics, plot_confusion_matrix, error_analysis, save_results


CLASSIFIERS = {
    "logreg": lambda cw: LogisticRegression(max_iter=1000, C=1.0, random_state=42, class_weight=cw),
    "svm": lambda cw: LinearSVC(max_iter=2000, C=1.0, random_state=42, dual="auto", class_weight=cw),
    "rf": lambda cw: RandomForestClassifier(n_estimators=200, random_state=42, class_weight=cw),
}


def run_simple_baseline(
    train_path: str = "data/processed/train.csv",
    val_path: str = "data/processed/val.csv",
    test_path: str = "data/processed/test.csv",
    classifier_name: str = "logreg",
    max_features: int = 10_000,
    ngram_range: tuple[int, int] = (1, 2),
    results_dir: str = "results",
    class_weight: str | None = None,
) -> dict:
    train_df = pd.read_csv(train_path)
    val_df = pd.read_csv(val_path)
    test_df = pd.read_csv(test_path)

    labels = sorted(train_df["primary_label"].unique())
    print(f"Classes: {labels}")

    clf_factory = CLASSIFIERS.get(classifier_name)
    if clf_factory is None:
        raise ValueError(f"Unknown classifier: {classifier_name}. Choose from {list(CLASSIFIERS)}")

    cw = "balanced" if class_weight == "balanced" else None
    suffix = f"_{class_weight}" if class_weight else ""

    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=max_features,
            ngram_range=ngram_range,
            sublinear_tf=True,
            strip_accents="unicode",
        )),
        ("clf", clf_factory(cw)),
    ])

    print(f"\nTraining TF-IDF + {classifier_name}{suffix} …")
    pipe.fit(train_df["code"], train_df["primary_label"])

                     
    val_pred = pipe.predict(val_df["code"])
    print("\n--- Validation ---")
    val_metrics = compute_metrics(val_df["primary_label"].tolist(), val_pred.tolist(), labels)
    print_metrics(val_metrics)

                      
    test_pred = pipe.predict(test_df["code"])
    print("\n--- Test ---")
    test_metrics = compute_metrics(test_df["primary_label"].tolist(), test_pred.tolist(), labels)
    print_metrics(test_metrics)

                      
    run_tag = f"tfidf_{classifier_name}{suffix}"
    plot_confusion_matrix(
        test_df["primary_label"].tolist(), test_pred.tolist(), labels,
        save_path=Path(results_dir) / f"cm_{run_tag}.png",
        title=f"TF-IDF + {classifier_name}{suffix}",
    )

                    
    test_df = test_df.copy()
    test_df["predicted"] = test_pred
    error_analysis(test_df)

    save_results(
        {"val": val_metrics, "test": test_metrics},
        model_name=run_tag,
        out_dir=results_dir,
    )

    return {"val": val_metrics, "test": test_metrics, "pipeline": pipe}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--classifier", default="logreg", choices=list(CLASSIFIERS))
    parser.add_argument("--max-features", type=int, default=10_000)
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--class-weight", default=None, choices=["balanced"])
    args = parser.parse_args()
    run_simple_baseline(
        classifier_name=args.classifier, max_features=args.max_features,
        results_dir=args.results_dir, class_weight=args.class_weight,
    )
