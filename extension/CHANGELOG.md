# Changelog

All notable changes to the Move Issue Classifier extension are documented here.

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
