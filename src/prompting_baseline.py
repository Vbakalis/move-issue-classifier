"""Prompting baseline (zero-shot and few-shot) using Qwen2.5-Coder-7B-Instruct
with 4-bit MLX quantisation. No fine-tuning.

Usage:
  python src/prompting_baseline.py --mode zeroshot
  python src/prompting_baseline.py --mode fewshot --k 1
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd
from mlx_lm import generate, load

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.evaluate import compute_metrics, plot_confusion_matrix, print_metrics, save_results  # noqa: E402

LABELS = ["Perfect", "SecurityError", "SemanticError", "StyleError", "SyntaxError"]
LABELS_STR = ", ".join(LABELS)
LABEL_PATTERN = re.compile(r"\b(Perfect|SecurityError|SemanticError|StyleError|SyntaxError)\b")

SYSTEM = (
    "You are a classifier for Move smart-contract code. "
    f"Classify each code snippet into exactly one of: {LABELS_STR}. "
    "Reply with only the class name, nothing else."
)


def select_few_shot(train_df: pd.DataFrame, k_per_class: int = 1, seed: int = 42) -> list[dict]:
    """Pick k_per_class examples per class deterministically."""
    rng = pd.Series(range(len(train_df))).sample(frac=1, random_state=seed).tolist()
    train_df = train_df.iloc[rng].reset_index(drop=True)
    examples = []
    for label in LABELS:
        sub = train_df[train_df["primary_label"] == label].head(k_per_class)
        for _, row in sub.iterrows():
            examples.append({"code": str(row["code"]), "label": label})
    return examples


def build_messages(code: str, examples: list[dict] | None = None) -> list[dict]:
    msgs = [{"role": "system", "content": SYSTEM}]
    if examples:
        for ex in examples:
            msgs.append({"role": "user", "content": f"Code:\n```move\n{ex['code'].strip()}\n```\n\nClass:"})
            msgs.append({"role": "assistant", "content": ex["label"]})
    msgs.append({"role": "user", "content": f"Code:\n```move\n{code.strip()}\n```\n\nClass:"})
    return msgs


def parse_label(raw: str) -> str:
    m = LABEL_PATTERN.search(raw)
    return m.group(1) if m else "Perfect"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit")
    p.add_argument("--mode", choices=["zeroshot", "fewshot"], default="zeroshot")
    p.add_argument("--k", type=int, default=1, help="few-shot examples per class")
    p.add_argument("--test-csv", default="data/processed/test.csv")
    p.add_argument("--train-csv", default="data/processed/train.csv")
    p.add_argument("--max-tokens", type=int, default=12)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()

    print(f"Loading {args.model} (no adapter)")
    model, tokenizer = load(args.model)

    examples = None
    tag = args.mode
    if args.mode == "fewshot":
        train_df = pd.read_csv(args.train_csv)
        examples = select_few_shot(train_df, k_per_class=args.k)
        print(f"Few-shot: {len(examples)} examples ({args.k} per class)")
        tag = f"fewshot_k{args.k}"

    df = pd.read_csv(args.test_csv)
    if args.limit:
        df = df.head(args.limit)

    y_true: list[str] = []
    y_pred: list[str] = []
    raw_outputs: list[str] = []

    t0 = time.time()
    for i, row in df.iterrows():
        msgs = build_messages(str(row["code"]), examples)
        prompt = tokenizer.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        out = generate(model, tokenizer, prompt=prompt, max_tokens=args.max_tokens, verbose=False)
        pred = parse_label(out)
        y_true.append(str(row["primary_label"]))
        y_pred.append(pred)
        raw_outputs.append(out)
        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            print(f"  {i+1}/{len(df)} ({rate:.2f} ex/s, {(len(df)-i-1)/rate:.0f}s left)")
    total = time.time() - t0
    print(f"Eval done: {len(df)} samples in {total:.1f}s ({len(df)/total:.2f} ex/s)")

    metrics = compute_metrics(y_true, y_pred, labels=LABELS)
    metrics["eval_seconds"] = total
    metrics["n_test"] = len(df)
    metrics["mode"] = args.mode
    metrics["k"] = args.k if args.mode == "fewshot" else 0
    print_metrics(metrics)

    out_dir = ROOT / "results"
    save_results(metrics, f"prompting_{tag}", out_dir=out_dir)
    plot_confusion_matrix(
        y_true, y_pred, LABELS,
        title=f"Qwen-7B Prompting ({tag}) - Test Confusion Matrix",
        save_path=out_dir / f"cm_prompting_{tag}.png",
    )
    pred_path = out_dir / f"prompting_{tag}_predictions.jsonl"
    with pred_path.open("w") as f:
        for t, pr, raw in zip(y_true, y_pred, raw_outputs):
            f.write(json.dumps({"true": t, "pred": pr, "raw": raw}) + "\n")
    print(f"  Saved predictions to {pred_path}")


if __name__ == "__main__":
    main()
