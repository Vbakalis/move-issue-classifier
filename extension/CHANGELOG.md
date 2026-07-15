# Changelog

All notable changes to the NiceMove extension are documented here.

## [0.4.0] - 2026-07-16

### Added
- **Local ONNX inference**: classification now runs entirely in-process via
  `transformers.js` and a quantized ONNX export of the CodeBERT+LoRA model.
  No Python server, no venv, no manual setup — install the extension and it
  works. Validated 499/499 prediction agreement with the original PyTorch
  model on the full test set, both before and after quantization.
- `scripts/export_onnx_model.py` (repo root): regenerates the bundled model
  from `models/codebert_lora/` for anyone who needs to rebuild it.
- "Move: Reload Local Classifier Model" command (was "Move: Restart Local
  Classifier Server") — clears the cache and forces a fresh model load.

### Fixed
- Apply Fix could patch in the wrong snippet when Claude's response included
  a bonus alternative fix after the primary one; it now always applies the
  first code block, matching the "Fix" heading.
- Whole-file diagnosis, workspace scan, and auto-classify-on-save could
  misbehave on files longer than the model's token window; classification
  now truncates at 512 tokens, matching the original server's behavior.

### Removed
- `moveClassifier.serverUrl`, `autoSpawnServer`, and `pythonPath` settings —
  no longer meaningful now that there's no server to configure or spawn.

## [0.3.0] - 2026-05-11

### Added
- **Status bar indicator**: shows `✓ NiceMove` when idle, a spinner while classifying, and `⚠ NiceMove` when issues are detected. Click to trigger diagnosis.
- **Classification cache**: unchanged code is not re-classified, making repeated diagnoses instant.
- **Workspace-wide scan**: new command "Move: Scan All Move Files" classifies every `.move` file in the workspace with a progress bar.
- **Apply Fix inline**: after Claude suggests a fix, an "Apply Fix" button in the panel patches the code directly in the editor.
- **Multi-label diagnostics**: when the classifier's second prediction exceeds 15% confidence and is non-Perfect, it appears as a Hint-level diagnostic alongside the primary.
- **Marketplace badges**: version and install count badges in the listing.

## [0.2.0] - 2026-05-04

### Added
- **Inline diagnostics**: classifier predictions now appear as squiggles in the editor and entries in the Problems tab. Severity is mapped per label (`SecurityError`/`SyntaxError`/`SemanticError` → Error, `StyleError` → Warning).
- **Quick Fix lightbulb**: each Move Classifier diagnostic exposes a `Fix <Label> with Claude` code action, marked as the preferred fix. Triggered with `Cmd+.` or the lightbulb.
- **Streaming Claude output**: the side panel now streams tokens chunk-by-chunk while Claude is generating, with a blinking cursor and live markdown rendering.
- **Out-of-distribution guard**: a lightweight Move-likeness heuristic suppresses predictions on snippets that do not look like Sui Move (random text, Python, plain English), so the model's over-confidence on OOD input does not surface as false diagnostics.
- **Auto-classify on save** (opt-in): when `moveClassifier.classifyOnSave` is true, the extension classifies any saved `.move` file with a 400 ms debounce and refreshes its diagnostic.

### Changed
- The diagnose flow now publishes a diagnostic before opening the fix panel, so users keep a persistent indicator even after dismissing the panel.
- The fix panel uses scripts and `retainContextWhenHidden` to support live streaming.

## [0.1.0] - 2026-05-03

- Initial release. Cmd+Alt+M classifies the current Move selection via a local CodeBERT+LoRA server and asks Claude for a fix when the prediction is not `Perfect`.
