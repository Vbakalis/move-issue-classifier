"""Convert processed train/val/test CSVs into MLX chat JSONL format.

Output: data/processed/mlx/{train,valid,test}.jsonl
Each line: {"messages": [{"role": "user", ...}, {"role": "assistant", ...}]}
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "processed"
DST = SRC / "mlx"
DST.mkdir(exist_ok=True)

LABELS = ["Perfect", "SecurityError", "SemanticError", "StyleError", "SyntaxError"]
LABELS_STR = ", ".join(LABELS)

SYSTEM = (
    "You are a classifier for Move smart-contract code. "
    f"Classify each code snippet into exactly one of: {LABELS_STR}. "
    "Reply with only the class name, nothing else."
)


def build_user(code: str) -> str:
    return f"{SYSTEM}\n\nCode:\n```move\n{code.strip()}\n```\n\nClass:"


def convert(split_in: str, split_out: str) -> int:
    df = pd.read_csv(SRC / f"{split_in}.csv")
    path = DST / f"{split_out}.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            rec = {
                "messages": [
                    {"role": "user", "content": build_user(str(row["code"]))},
                    {"role": "assistant", "content": str(row["primary_label"])},
                ]
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(df)


if __name__ == "__main__":
    for s_in, s_out in [("train", "train"), ("val", "valid"), ("test", "test")]:
        n = convert(s_in, s_out)
        print(f"{s_out}.jsonl: {n} samples")
    print(f"Wrote to {DST}")
