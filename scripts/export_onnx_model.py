"""
Merge the CodeBERT + LoRA adapter (models/codebert_lora/) into a standalone
model, export it to ONNX, and quantize to INT8 for bundling with the VS Code
extension (extension/model/).

Requires: transformers, peft, optimum-onnx, onnxruntime (not part of
server/requirements.txt — install into a separate venv to avoid touching the
server's pinned dependency versions).

Usage:
    python scripts/export_onnx_model.py

Validated (2026-07-14): the quantized ONNX export agrees with the original
PyTorch + LoRA model on 499/499 rows of data/processed/test.csv (99.00%
accuracy, matching the reported baseline).
"""
from pathlib import Path

from onnxruntime.quantization import quantize_dynamic, QuantType
from optimum.exporters.onnx import main_export
from peft import PeftModel
from transformers import AutoModelForSequenceClassification, AutoTokenizer

REPO_ROOT = Path(__file__).resolve().parent.parent
ADAPTER_PATH = REPO_ROOT / "models" / "codebert_lora"
BASE_MODEL = "microsoft/codebert-base"
LABELS = ["Perfect", "SecurityError", "SemanticError", "StyleError", "SyntaxError"]

OUT_DIR = REPO_ROOT / "extension" / "model"
ONNX_SUBDIR = OUT_DIR / "onnx"
MERGED_SCRATCH = REPO_ROOT / ".scratch_merged_model"  # deleted at the end


def main():
    print("Loading tokenizer + base model + LoRA adapter...")
    tokenizer = AutoTokenizer.from_pretrained(str(ADAPTER_PATH))
    base = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=len(LABELS),
        id2label={i: l for i, l in enumerate(LABELS)},
        label2id={l: i for i, l in enumerate(LABELS)},
    )
    peft_model = PeftModel.from_pretrained(base, str(ADAPTER_PATH))
    peft_model.eval()

    print("Merging LoRA weights into base model...")
    merged = peft_model.merge_and_unload()

    MERGED_SCRATCH.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(str(MERGED_SCRATCH))
    tokenizer.save_pretrained(str(MERGED_SCRATCH))

    print("Exporting to ONNX...")
    ONNX_SUBDIR.mkdir(parents=True, exist_ok=True)
    main_export(model_name_or_path=str(MERGED_SCRATCH), output=str(OUT_DIR), task="text-classification")

    # main_export writes model.onnx directly into OUT_DIR; move the small
    # config/tokenizer files stay where they are (extension/model/), the
    # binary goes under extension/model/onnx/ to match transformers.js's
    # expected layout.
    onnx_file = OUT_DIR / "model.onnx"
    quantized_file = ONNX_SUBDIR / "model_quantized.onnx"
    print("Quantizing to INT8...")
    quantize_dynamic(str(onnx_file), str(quantized_file), weight_type=QuantType.QInt8)
    onnx_file.unlink()  # only the quantized version ships

    print(f"\nDone. Model files in {OUT_DIR}, quantized weights at {quantized_file}")
    print(f"Quantized size: {quantized_file.stat().st_size / 1e6:.1f} MB")

    import shutil
    shutil.rmtree(MERGED_SCRATCH, ignore_errors=True)


if __name__ == "__main__":
    main()
