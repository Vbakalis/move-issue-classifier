# Move Issue Classifier — VS Code Extension

A VS Code extension that classifies Move smart-contract code on Sui using a
local CodeBERT + LoRA model (trained as part of the MSc thesis), and then
asks Claude for a concrete fix when the classifier flags a real issue.

## Architecture

```
VS Code Extension (TS)
        │  POST /classify     (localhost only)
        ▼
Local FastAPI server (Python)  ← auto-spawned on activation
        │  CodeBERT + LoRA
        ▼
   {label, confidence}
        │  if label != "Perfect":
        ▼
Anthropic API  (your key, your billing)
        ▼
Fix suggestion shown in a side panel
```

## Setup

1. Install dependencies:
   ```bash
   cd extension && npm install && npm run compile
   cd ../server  && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
   ```
2. Open the `extension/` folder in VS Code and press **F5** to launch an
   Extension Development Host.
3. In the host window, set your Anthropic API key in
   *Settings → Extensions → Move Issue Classifier → Anthropic API Key*.
4. Open a `.move` file, select code (or none for the whole file), and run
   **Move: Diagnose Selection** (`Cmd+Alt+M` / `Ctrl+Alt+M`).

## Features

- **Inline diagnostics** — predictions appear as squiggles in the editor and
  entries in the Problems tab.
- **Quick Fix lightbulb** — every diagnostic carries a `Fix … with Claude`
  code action; trigger it with `Cmd+.`.
- **Streaming Claude output** — the side panel streams tokens as Claude
  generates them.
- **OOD guard** — a Move-likeness heuristic suppresses predictions on
  non-Move snippets so the model's over-confidence on out-of-distribution
  input does not surface as false diagnostics.
- **Auto-classify on save** *(opt-in)* — set
  `moveClassifier.classifyOnSave` to `true` to refresh diagnostics every time
  a `.move` file is saved.

## Settings

| Key | Default | Description |
|---|---|---|
| `moveClassifier.anthropicApiKey` | `""` | Your Anthropic API key. Required for fix suggestions. |
| `moveClassifier.claudeModel` | `claude-sonnet-4-5` | Claude model used for fix suggestions. |
| `moveClassifier.serverUrl` | `http://127.0.0.1:8765` | Local classifier server URL. |
| `moveClassifier.confidenceThreshold` | `0.6` | Below this, the prediction is treated as `uncertain`. |
| `moveClassifier.autoSpawnServer` | `true` | Launch the FastAPI server on activation. |
| `moveClassifier.classifyOnSave` | `false` | Auto-classify Move files on save. |
| `moveClassifier.pythonPath` | `""` | Python interpreter (auto-detected if empty). |

## Packaging

To produce a `.vsix` for sideloading or marketplace upload:

```bash
cd extension
npx @vscode/vsce package --no-yarn
```

## Privacy

- The classifier server binds to `127.0.0.1` only.
- Your code is sent to the local server (in-process) and, only when an issue
  is detected, to `api.anthropic.com` using *your* API key.
- The extension does not send telemetry, analytics, or code anywhere else.
- We never see your code or your key.

## Billing

You bring your own Anthropic API key. You are billed by Anthropic directly
based on your usage of their API. The maintainers of this extension do not
process payments and do not see your key or your invoices.
