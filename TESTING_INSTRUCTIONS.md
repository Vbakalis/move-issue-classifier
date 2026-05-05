# Testing Instructions — Move Issue Classifier

## Overview

This extension classifies Move (Sui) smart-contract code using a locally-running
CodeBERT + LoRA model and displays diagnostics inside VS Code. When an issue is
detected, the extension underlines the code and shows the error category
(SecurityError, SemanticError, StyleError, SyntaxError) with a confidence score.

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.10+ |
| Node.js | 18+ |
| VS Code | 1.85+ |
| macOS / Linux / Windows (WSL) | any |

> **Note:** On Apple Silicon Macs the model runs on MPS (GPU). On other machines
> it falls back to CPU — inference takes ~1–2 seconds either way.

---

## Step 1 — Clone the Repository

```bash
git clone https://github.com/Vbakalis/move-issue-classifier.git
cd move-issue-classifier
```

---

## Step 2 — Set Up the Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate
pip install -r server/requirements.txt
```

This installs PyTorch, Transformers, PEFT, FastAPI, and Uvicorn.

---

## Step 3 — Start the Classifier Server

```bash
cd server
python app.py
```

You should see output ending with:

```
INFO:     Uvicorn running on http://127.0.0.1:8765
```

Leave this terminal running.

### Verify the Server (Optional)

In a new terminal:

```bash
curl http://127.0.0.1:8765/health
```

Expected response:

```json
{"status":"ok","device":"mps","labels":["Perfect","SecurityError","SemanticError","StyleError","SyntaxError"]}
```

---

## Step 4 — Install the VS Code Extension

### Option A: Install from VSIX (Recommended)

1. Open VS Code.
2. Go to the Extensions panel (left sidebar, puzzle piece icon).
3. Click the `…` menu at the top-right of the panel.
4. Select **"Install from VSIX…"**
5. Navigate to `extension/move-issue-classifier-0.2.0.vsix` inside the cloned repo.
6. Click **Install** and reload if prompted.

### Option B: Run from Source (Development Mode)

```bash
cd extension
npm install
npm run compile
```

Then press **F5** in VS Code to launch an Extension Development Host.

---

## Step 5 — Configure the Extension

Open VS Code Settings (`Cmd+,` on Mac / `Ctrl+,` on Windows) and search for
`move classifier`. Set:

| Setting | Value |
|---------|-------|
| `moveClassifier.pythonPath` | Path to the Python in your venv, e.g. `/path/to/move-issue-classifier/.venv/bin/python` |
| `moveClassifier.serverUrl` | `http://127.0.0.1:8765` (default, usually no change needed) |
| `moveClassifier.anthropicApiKey` | *(Optional)* Your Anthropic API key — enables the "Suggest fix with Claude" feature |

---

## Step 6 — Test the Extension

### 6.1 Create a Test File

Create a file named `test.move` with this content (a known SecurityError — missing access control):

```move
module security::admin {
  public entry fun set_admin(cfg: &mut Config, new_admin: address, _ctx: &mut TxContext) {
    cfg.admin = new_admin;
  }
}
```

### 6.2 Run the Classifier

1. Open `test.move` in VS Code.
2. Select all code (`Cmd+A` / `Ctrl+A`).
3. Open Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`).
4. Type **"Move: Diagnose Selection"** and press Enter.

### 6.3 Expected Result

- A notification appears: **"Move Classifier: SecurityError (100.0% confidence)"**
- Red/yellow squiggly underline appears under the code.
- The Problems panel (`Cmd+Shift+M`) shows the diagnostic.
- Hovering over the underline shows the classification details.

### 6.4 Additional Test Snippets

**SyntaxError example** (missing semicolon):

```move
module example::broken {
  public fun add(a: u64, b: u64): u64 {
    a + b
  }
}
```

**Perfect code** (no issues expected):

```move
module example::counter {
  struct Counter has key {
    id: UID,
    value: u64,
  }

  public entry fun increment(counter: &mut Counter, _ctx: &mut TxContext) {
    counter.value = counter.value + 1;
  }
}
```

---

## Step 7 — (Optional) Test the Claude Fix Suggestion

If you have an Anthropic API key configured:

1. After a diagnostic appears (red underline), click the lightbulb icon (💡) or press `Cmd+.`.
2. Select **"Fix … with Claude"**.
3. A side panel opens showing Claude's streaming fix suggestion.

---

## Keyboard Shortcut

`Cmd+Alt+M` (Mac) / `Ctrl+Alt+M` (Windows/Linux) — runs "Diagnose Selection" on the current selection.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Connection refused" | Make sure the server is running (`python app.py` in `server/`) |
| No command found in palette | Reload VS Code window after installing the extension |
| Classification always says "Perfect" | Use realistic multi-line Move snippets — single-line toy code is out-of-distribution |
| Server won't start (SSL error in logs) | Harmless background thread; the server still works. Verify with `curl /health` |

---

## Architecture Diagram

```
┌─────────────────────────────────────┐
│        VS Code Extension (TS)       │
│  • Diagnostics (squiggles)          │
│  • Quick Fix code actions           │
│  • Streaming Claude panel           │
│  • OOD guard (Move-likeness check)  │
└──────────────┬──────────────────────┘
               │ POST /classify (localhost)
               ▼
┌─────────────────────────────────────┐
│     FastAPI Server (Python)         │
│  • CodeBERT base model              │
│  • LoRA adapter (4.7 MB)            │
│  • 5-class softmax                  │
│  • MPS / CPU inference              │
└─────────────────────────────────────┘
```

---

## Repository Structure

```
move-issue-classifier/
├── extension/          # VS Code extension source (TypeScript)
├── server/             # FastAPI classifier server
│   └── app.py
├── models/
│   └── codebert_lora/  # Trained LoRA adapter weights
├── data/               # Dataset (train/val/test splits)
├── src/                # Training & evaluation scripts
├── paper/              # Thesis (LaTeX)
└── notebooks/          # Jupyter experiments
```
