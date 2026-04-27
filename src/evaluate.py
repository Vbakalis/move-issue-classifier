"""
Evaluation utilities: accuracy, macro-F1, per-class metrics, confusion matrix,
brief error analysis.
"""

import json
import os
from pathlib import Path

import matplotlib
if not os.environ.get("DISPLAY") or os.environ.get("MPLBACKEND"):
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)


def compute_metrics(
    y_true: list[str],
    y_pred: list[str],
    labels: list[str] | None = None,
) -> dict:
    """Return accuracy, macro-F1, and per-class precision/recall/F1."""
    acc = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, average="macro", labels=labels)
    report = classification_report(
        y_true, y_pred, labels=labels, output_dict=True, zero_division=0
    )
    return {"accuracy": acc, "macro_f1": macro_f1, "per_class": report}


def print_metrics(metrics: dict) -> None:
    print(f"  Accuracy : {metrics['accuracy']:.4f}")
    print(f"  Macro-F1 : {metrics['macro_f1']:.4f}")
    print()
    per_class = {
        k: v for k, v in metrics["per_class"].items()
        if k not in ("accuracy", "macro avg", "weighted avg")
    }
    header = f"{'Class':<30} {'Prec':>6} {'Rec':>6} {'F1':>6} {'Sup':>6}"
    print(header)
    print("-" * len(header))
    for cls, vals in sorted(per_class.items()):
        print(
            f"{cls:<30} {vals['precision']:>6.3f} {vals['recall']:>6.3f} "
            f"{vals['f1-score']:>6.3f} {vals['support']:>6.0f}"
        )


def plot_confusion_matrix(
    y_true: list[str],
    y_pred: list[str],
    labels: list[str],
    save_path: str | Path | None = None,
    title: str = "Confusion Matrix",
) -> None:
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(
        cm, annot=True, fmt="d", cmap="Blues",
        xticklabels=labels, yticklabels=labels, ax=ax,
    )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(title)
    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Saved confusion matrix to {save_path}")
    plt.show()


def error_analysis(
    df: pd.DataFrame,
    y_true_col: str = "primary_label",
    y_pred_col: str = "predicted",
    n_examples: int = 5,
) -> pd.DataFrame:
    """Return a DataFrame of misclassified examples for inspection."""
    errors = df[df[y_true_col] != df[y_pred_col]].copy()
    print(f"\n  Total errors: {len(errors)} / {len(df)} "
          f"({100 * len(errors) / len(df):.1f}%)")

                         
    if len(errors) > 0:
        errors["pair"] = errors[y_true_col] + " → " + errors[y_pred_col]
        pair_counts = errors["pair"].value_counts().head(10)
        print("\n  Top confused pairs:")
        for pair, cnt in pair_counts.items():
            print(f"    {pair}: {cnt}")

    return errors.head(n_examples)


def save_results(
    metrics: dict,
    model_name: str,
    out_dir: str | Path = "results",
) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{model_name}_metrics.json"
    with open(path, "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"  Saved metrics to {path}")
    return path
