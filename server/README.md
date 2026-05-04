# Move Issue Classifier — Local Server

FastAPI server that loads the CodeBERT + LoRA adapter (from `../models/codebert_lora`)
and exposes a single `POST /classify` endpoint.

The VS Code extension auto-spawns this server on activation; you do not normally
need to run it by hand.

## Manual run (development)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py            # listens on 127.0.0.1:8765
```

## Endpoints

- `GET /health` — readiness, device, labels, adapter path.
- `POST /classify` — body `{"code": "..."}`, returns `{label, confidence, top_2, device}`.

## Environment

- `MOVE_ADAPTER_PATH` — override path to the LoRA adapter (default: `../models/codebert_lora`).
- `MOVE_BASE_MODEL` — override base model name (default: `microsoft/codebert-base`).
- `PORT` — TCP port (default: `8765`).

## Privacy

The server is bound to `127.0.0.1` only and does not log request bodies. No
telemetry, no outbound network calls.
