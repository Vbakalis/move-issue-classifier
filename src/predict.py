"""CLI demo: classify a Move snippet with the trained CodeBERT+LoRA model.

Usage:
  # Interactive (paste code, Ctrl-D to submit):
  python src/predict.py

  # Single file:
  python src/predict.py --file path/to/snippet.move

  # Inline:
  python src/predict.py --code 'module demo::x { public fun f() { abort 0 } }'

Shows predicted class, confidence, and the full per-class probability table.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
import torch.nn.functional as F
from peft import PeftModel
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_DIR = ROOT / "models" / "codebert_lora"
BASE_MODEL = "microsoft/codebert-base"
LABELS = ["Perfect", "SecurityError", "SemanticError", "StyleError", "SyntaxError"]


def load_model(adapter_dir: Path = ADAPTER_DIR):
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(adapter_dir)
    base = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=len(LABELS),
        id2label={i: l for i, l in enumerate(LABELS)},
        label2id={l: i for i, l in enumerate(LABELS)},
    )
    model = PeftModel.from_pretrained(base, adapter_dir)
    model.to(device).eval()
    return model, tokenizer, device


@torch.inference_mode()
def predict(code: str, model, tokenizer, device: str) -> dict:
    inputs = tokenizer(
        code, return_tensors="pt", truncation=True, max_length=256,
    ).to(device)
    logits = model(**inputs).logits[0]
    probs = F.softmax(logits, dim=-1).cpu().tolist()
    ranked = sorted(zip(LABELS, probs), key=lambda p: -p[1])
    return {"top": ranked[0][0], "probs": dict(ranked)}


def format_report(result: dict) -> str:
    lines = [f"  Predicted class : {result['top']}  (p={result['probs'][result['top']]:.3f})", ""]
    lines.append(f"  {'Class':<15} {'Probability':>12}")
    lines.append(f"  {'-' * 15} {'-' * 12}")
    for cls, p in result["probs"].items():
        bar = "█" * int(round(p * 40))
        lines.append(f"  {cls:<15} {p:>12.4f}  {bar}")
    return "\n".join(lines)


def read_code(args: argparse.Namespace) -> str:
    if args.code:
        return args.code
    if args.file:
        return Path(args.file).read_text()
    if not sys.stdin.isatty():
        return sys.stdin.read()
    print("Paste Move code, then press Ctrl-D (EOF):\n", file=sys.stderr)
    return sys.stdin.read()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--file", help="Path to a .move file to classify")
    p.add_argument("--code", help="Inline Move snippet")
    p.add_argument("--adapter", default=str(ADAPTER_DIR),
                   help="Path to LoRA adapter directory")
    args = p.parse_args()

    code = read_code(args).strip()
    if not code:
        sys.exit("No code provided.")

    print(f"Loading {BASE_MODEL} + LoRA adapter from {args.adapter} ...",
          file=sys.stderr)
    model, tokenizer, device = load_model(Path(args.adapter))
    print(f"Running on {device}\n", file=sys.stderr)

    result = predict(code, model, tokenizer, device)
    print(format_report(result))


if __name__ == "__main__":
    main()
