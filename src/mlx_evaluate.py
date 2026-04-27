"""Evaluate MLX LoRA adapter on the test set.

Loads the base model + trained LoRA adapter, generates a label for each
test snippet, parses it, and reports accuracy/macro-F1 plus a confusion
matrix, matching the format of the other baselines.
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
from src.evaluate import (  # noqa: E402
    compute_metrics,
    plot_confusion_matrix,
    print_metrics,
    save_results,
)
from src.mlx_prepare_data import LABELS, build_user  # noqa: E402

LABEL_PATTERN = re.compile(
    r"\b(Perfect|SecurityError|SemanticError|StyleError|SyntaxError)\b"
)


def parse_label(raw: str) -> str:
    m = LABEL_PATTERN.search(raw)
    return m.group(1) if m else "Perfect"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit")
    p.add_argument("--adapter-path", default="results/qwen_lora")
    p.add_argument("--test-csv", default="data/processed/test.csv")
    p.add_argument("--tag", default="qwen_lora")
    p.add_argument("--max-tokens", type=int, default=12)
    p.add_argument("--limit", type=int, default=0, help="0 = all")
    args = p.parse_args()

    print(f"Loading {args.model} with adapter {args.adapter_path}")
    model, tokenizer = load(args.model, adapter_path=args.adapter_path)

    df = pd.read_csv(args.test_csv)
    if args.limit:
        df = df.head(args.limit)

    y_true: list[str] = []
    y_pred: list[str] = []
    raw_outputs: list[str] = []

    t0 = time.time()
    for i, row in df.iterrows():
        user_msg = build_user(str(row["code"]))
        messages = [{"role": "user", "content": user_msg}]
        prompt = tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=False
        )
        out = generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=args.max_tokens,
            verbose=False,
        )
        pred = parse_label(out)
        y_true.append(str(row["primary_label"]))
        y_pred.append(pred)
        raw_outputs.append(out)
        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            print(
                f"  {i + 1}/{len(df)} "
                f"({rate:.2f} ex/s, {(len(df) - i - 1) / rate:.0f}s left)"
            )
    total = time.time() - t0
    print(f"Eval done: {len(df)} samples in {total:.1f}s ({len(df)/total:.2f} ex/s)")

    metrics = compute_metrics(y_true, y_pred, labels=LABELS)
    metrics["eval_seconds"] = total
    metrics["n_test"] = len(df)
    print_metrics(metrics)

    out_dir = ROOT / "results"
    save_results(metrics, f"codellama_{args.tag}" if args.tag == "qwen_lora" else args.tag, out_dir=out_dir)
                                
    save_results(metrics, args.tag, out_dir=out_dir)

                      
    plot_confusion_matrix(
        y_true, y_pred, LABELS,
        title=f"MLX LoRA ({args.tag}) — Test Confusion Matrix",
        save_path=out_dir / f"cm_{args.tag}.png",
    )

                                                  
    pred_path = out_dir / f"{args.tag}_predictions.jsonl"
    with pred_path.open("w") as f:
        for t, pr, raw in zip(y_true, y_pred, raw_outputs):
            f.write(json.dumps({"true": t, "pred": pr, "raw": raw}) + "\n")
    print(f"  Saved predictions to {pred_path}")


if __name__ == "__main__":
    main()
