"""FastAPI server: classify Move snippets with CodeBERT + LoRA adapter."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import torch
import torch.nn.functional as F
from fastapi import FastAPI, HTTPException
from peft import PeftModel
from pydantic import BaseModel
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ADAPTER = REPO_ROOT / "models" / "codebert_lora"
ADAPTER_PATH = Path(os.environ.get("MOVE_ADAPTER_PATH", str(DEFAULT_ADAPTER)))
BASE_MODEL = os.environ.get("MOVE_BASE_MODEL", "microsoft/codebert-base")

# 5 classes, matching training order (sorted alphabetically).
LABELS = ["Perfect", "SecurityError", "SemanticError", "StyleError", "SyntaxError"]


# ---------------------------------------------------------------------------
# Model holder
# ---------------------------------------------------------------------------
class _State:
    tokenizer = None
    model = None
    device = "cpu"


def _select_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _load() -> None:
    if not ADAPTER_PATH.exists():
        raise RuntimeError(f"Adapter not found at {ADAPTER_PATH}")
    _State.device = _select_device()
    _State.tokenizer = AutoTokenizer.from_pretrained(str(ADAPTER_PATH))
    base = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=len(LABELS),
        id2label={i: l for i, l in enumerate(LABELS)},
        label2id={l: i for i, l in enumerate(LABELS)},
    )
    _State.model = PeftModel.from_pretrained(base, str(ADAPTER_PATH))
    _State.model.to(_State.device)
    _State.model.eval()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load()
    yield


app = FastAPI(title="Move Issue Classifier", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ClassifyRequest(BaseModel):
    code: str
    max_length: Optional[int] = 512


class TopLabel(BaseModel):
    label: str
    confidence: float


class ClassifyResponse(BaseModel):
    label: str
    confidence: float
    top_2: list[TopLabel]
    device: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> dict:
    return {
        "status": "ok" if _State.model is not None else "loading",
        "device": _State.device,
        "labels": LABELS,
        "adapter": str(ADAPTER_PATH),
    }


@app.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest) -> ClassifyResponse:
    if _State.model is None:
        raise HTTPException(503, "Model not loaded")
    if not req.code.strip():
        raise HTTPException(400, "Empty code")

    inputs = _State.tokenizer(
        req.code,
        truncation=True,
        max_length=req.max_length or 512,
        return_tensors="pt",
    ).to(_State.device)

    with torch.no_grad():
        logits = _State.model(**inputs).logits[0]
        probs = F.softmax(logits, dim=-1).cpu().tolist()

    pairs = sorted(zip(LABELS, probs), key=lambda x: -x[1])
    return ClassifyResponse(
        label=pairs[0][0],
        confidence=float(pairs[0][1]),
        top_2=[TopLabel(label=l, confidence=float(c)) for l, c in pairs[:2]],
        device=_State.device,
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8765"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
