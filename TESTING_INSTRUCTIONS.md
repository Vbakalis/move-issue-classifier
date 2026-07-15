# Testing Instructions — Move Issue Classifier

## Overview

This extension classifies Move (Sui) smart-contract code using a local
CodeBERT + LoRA model (bundled as a quantized ONNX export) and displays
diagnostics inside VS Code. When an issue is detected, the extension
underlines the code and shows the error category (SecurityError,
SemanticError, StyleError, SyntaxError) with a confidence score. Classification
runs entirely in-process — no server, no Python environment to set up.

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Node.js | 18+ |
| VS Code | 1.85+ |
| macOS / Linux / Windows | any |

> **Note:** inference runs on CPU via `onnxruntime-node`; a single classification
> takes well under 100ms.

---

## Step 1 — Clone the Repository

```bash
git clone https://github.com/Vbakalis/move-issue-classifier.git
cd move-issue-classifier
```

---

## Step 2 — Install the VS Code Extension

### Option A: Install from VSIX (Recommended)

1. Open VS Code.
2. Go to the Extensions panel (left sidebar, puzzle piece icon).
3. Click the `…` menu at the top-right of the panel.
4. Select **"Install from VSIX…"**
5. Navigate to `extension/nicemove-0.4.0.vsix` inside the cloned repo (build it
   yourself with `cd extension && npm install && npx @vscode/vsce package --no-yarn`
   if it isn't present — this bundles the model file, so it's not committed to git).
6. Click **Install** and reload if prompted.

### Option B: Run from Source (Development Mode)

```bash
cd extension
npm install
npm run compile
```

Then press **F5** in VS Code to launch an Extension Development Host.

> If `extension/model/onnx/model_quantized.onnx` is missing, regenerate it with
> `python scripts/export_onnx_model.py` from the repo root (needs `transformers`,
> `peft`, `optimum-onnx`, `onnxruntime` — see that script's docstring).

---

## Step 3 — Configure the Extension

Open VS Code Settings (`Cmd+,` on Mac / `Ctrl+,` on Windows) and search for
`move classifier`. Set:

| Setting | Value |
|---------|-------|
| `moveClassifier.anthropicApiKey` | *(Optional)* Your Anthropic API key — enables the "Fix with Claude" feature |

Classification itself needs no configuration — it runs locally with no
network access.

---

## Step 4 — Test the Extension

### 4.1 Create a Test File

Create a file named `test.move` with this content (a known SecurityError — missing access control):

```move
module security::admin {
  public entry fun set_admin(cfg: &mut Config, new_admin: address, _ctx: &mut TxContext) {
    cfg.admin = new_admin;
  }
}
```

### 4.2 Run the Classifier

1. Open `test.move` in VS Code.
2. Select all code (`Cmd+A` / `Ctrl+A`).
3. Open Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`).
4. Type **"Move: Diagnose Selection"** and press Enter.

### 4.3 Expected Result

- Red/yellow squiggly underline appears under the code.
- The Problems panel (`Cmd+Shift+M`) shows the diagnostic
  (`SecurityError (100.0% confidence). Use the Quick Fix lightbulb to ask Claude.`).
- If an Anthropic API key is configured, a side panel opens automatically and
  streams Claude's diagnosis and suggested fix. If not, a toast prompts you to
  configure one.
- Hovering over the underline shows the same classification details.

### 4.4 Additional Test Snippets

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

> Note: very short, hand-typed snippets can be out-of-distribution for the
> model and misclassify with high confidence — this is a known limitation
> unrelated to the extension itself. Prefer realistic, multi-line snippets
> (or real examples from `data/processed/test.csv`) when testing.

---

## Step 5 — (Optional) Test the Claude Fix Suggestion

If you have an Anthropic API key configured, diagnosing an issue (Step 4.2)
already opens the fix panel automatically. To re-trigger it later on an
existing diagnostic without re-running the full diagnosis:

1. Click the lightbulb icon (💡) or press `Cmd+.` on the diagnostic.
2. Select **"Move Classifier: Fix … with Claude"**.
3. The side panel streams Claude's fix suggestion; click **Apply Fix** to
   patch the code directly.

---

## Keyboard Shortcut

`Cmd+Alt+M` (Mac) / `Ctrl+Alt+M` (Windows/Linux) — runs "Diagnose Selection" on the current selection.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No command found in palette | Reload VS Code window after installing the extension |
| Classification always says "Perfect" | Use realistic multi-line Move snippets — single-line toy code is out-of-distribution |
| Fix panel never opens | Anthropic API key isn't set — Settings → Extensions → NiceMove → Anthropic API Key |
| "Move: Reload Local Classifier Model" does nothing visible | Expected — it just clears the cache and forces a fresh model load on the next diagnosis |

---

## Architecture Diagram

```
┌─────────────────────────────────────┐
│        VS Code Extension (TS)       │
│  • Diagnostics (squiggles)          │
│  • Quick Fix code actions           │
│  • Streaming Claude panel           │
│  • OOD guard (Move-likeness check)  │
│  • In-process ONNX inference        │
│    (transformers.js + onnxruntime)  │
└──────────────┬──────────────────────┘
               │ only when label != "Perfect"
               ▼
┌─────────────────────────────────────┐
│         Anthropic API               │
│  (your key, your billing)           │
└─────────────────────────────────────┘
```

No local server, no separate Python process — the CodeBERT + LoRA model
(merged and exported to a quantized ONNX file, see
`scripts/export_onnx_model.py`) runs directly inside the extension host.
`server/` still exists in this repo as a standalone FastAPI reference
implementation (useful for reproducing the Python-side accuracy numbers), but
the extension no longer uses it.

---

## Repository Structure

```
move-issue-classifier/
├── extension/          # VS Code extension source (TypeScript)
│   └── model/           # Quantized ONNX export bundled with the extension
├── server/             # Standalone FastAPI reference server (not used by the extension)
│   └── app.py
├── models/
│   └── codebert_lora/  # Trained LoRA adapter weights
├── scripts/
│   └── export_onnx_model.py  # Regenerates extension/model/ from models/codebert_lora/
├── data/               # Dataset (train/val/test splits)
├── src/                # Training & evaluation scripts
├── paper/              # Thesis (LaTeX)
└── notebooks/          # Jupyter experiments
```
