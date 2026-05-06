# Claude vs Local Model Comparison Report

**Date:** 6 May 2025  
**Author:** Vasilis Bakalis  
**Task:** Move Smart-Contract Issue Classification (5 classes)

---

## Experiment Summary

We compared our fine-tuned local model (CodeBERT + LoRA adapter, 4.7 MB) against
Anthropic's Claude Sonnet 4.6 (frontier LLM) in a zero-shot classification setup.

**Goal:** Determine whether a large, state-of-the-art general-purpose LLM can match
the performance of a small, task-specific fine-tuned model on this domain-specific task.

---

## Setup

| Parameter | Local Model | Claude Sonnet 4.6 |
|-----------|-------------|-------------------|
| Architecture | CodeBERT-base (125M) + LoRA | ~Unknown (frontier LLM) |
| Training | Fine-tuned on ~2,300 Move snippets | No training (zero-shot) |
| Adapter size | 4.7 MB | N/A (API) |
| Inference | Local (Apple M-series, MPS) | Cloud API |
| Cost per call | ~0 (local compute) | ~$0.003 per snippet |
| Latency | ~50ms | ~500ms |

**Test sample:** 239 stratified samples from the test set (50 per class, 39 SyntaxError)

**Prompt used for Claude:**
> "You are a classifier for Move smart-contract code on the Sui blockchain.
> Classify each code snippet into exactly one of: Perfect, SecurityError,
> SemanticError, StyleError, SyntaxError. Reply with ONLY the class name, nothing else."

---

## Results

### Overall Accuracy

| Model | Accuracy | Macro-F1 | Samples |
|-------|----------|----------|---------|
| **CodeBERT + LoRA (local)** | **99.2%** | **0.992** | 239 |
| Claude Sonnet 4.6 (zero-shot) | 64.4% | 0.648 | 239 |

**Difference: +34.7 percentage points in favor of the local model.**

### Per-Class Breakdown

#### Local Model (CodeBERT + LoRA)

| Class | Precision | Recall | F1-Score | Support |
|-------|-----------|--------|----------|---------|
| Perfect | 0.96 | 1.00 | 0.98 | 50 |
| SecurityError | 1.00 | 1.00 | 1.00 | 50 |
| SemanticError | 1.00 | 1.00 | 1.00 | 50 |
| StyleError | 1.00 | 0.96 | 0.98 | 50 |
| SyntaxError | 1.00 | 1.00 | 1.00 | 39 |
| **Weighted avg** | **0.99** | **0.99** | **0.99** | **239** |

#### Claude Sonnet 4.6 (Zero-Shot)

| Class | Precision | Recall | F1-Score | Support |
|-------|-----------|--------|----------|---------|
| Perfect | 0.67 | 0.62 | 0.65 | 50 |
| SecurityError | 0.84 | 0.64 | 0.73 | 50 |
| SemanticError | 0.71 | 0.64 | 0.67 | 50 |
| StyleError | 0.53 | 0.56 | 0.54 | 50 |
| SyntaxError | 0.54 | 0.79 | 0.65 | 39 |
| **Weighted avg** | **0.67** | **0.64** | **0.65** | **239** |

---

## Key Findings

1. **The local fine-tuned model outperforms Claude by nearly 35 percentage points.**
   A 4.7 MB LoRA adapter trained in under 10 minutes on a laptop decisively beats
   a frontier LLM that costs ~$3 per 1,000 API calls.

2. **Claude struggles most with StyleError (F1=0.54).** Style conventions are
   project-specific and cannot be learned from a generic system prompt. This is
   consistent with the known difficulty of the StyleError/Perfect boundary.

3. **Claude's best class is SecurityError (F1=0.73).** This aligns with the
   model's general training on code security patterns, but it still falls far
   short of the local model's perfect F1=1.00 on the same class.

4. **Claude over-predicts SyntaxError** (high recall 0.79, low precision 0.54),
   confusing semantic-level issues with syntax problems.

5. **The ordering holds across model scales:** Prompting any model (local 7B or
   frontier) < TF-IDF baseline < Fine-tuned encoders. This confirms that for
   narrow, domain-specific classification tasks with labeled data, fine-tuning
   is categorically superior to prompting.

---

## Full Comparison Across All Methods

| Method | Accuracy | Macro-F1 |
|--------|----------|----------|
| Qwen 7B zero-shot (local) | 49.9% | 0.369 |
| Qwen 7B few-shot k=1 (local) | 59.1% | 0.512 |
| **Claude Sonnet 4.6 zero-shot (API)** | **64.4%** | **0.648** |
| TF-IDF + LinearSVC | 97.2% | 0.965 |
| Qwen 7B + 4-bit MLX LoRA | 97.2% | 0.978 |
| CodeBERT full fine-tune | 98.8% | 0.992 |
| **CodeBERT + LoRA** | **99.0%** | **0.993** |

---

## Conclusion

This experiment conclusively demonstrates the thesis's core argument:
**for domain-specific classification of Move smart-contract issues,
a small task-aligned encoder with a parameter-efficient adapter
dominates both local and frontier LLMs by a wide margin.**

The result validates the practical deployment choice of packaging
the CodeBERT+LoRA model into a VS Code extension for real-time
developer feedback, rather than relying on expensive API calls
to a cloud LLM that would still produce inferior results.

---

## Artifacts

- Raw results CSV: `data/processed/claude_comparison_results.csv`
- Comparison script: `src/compare_claude.py`
- Model used: Claude Sonnet 4.6 (`claude-sonnet-4-6`) via Anthropic API
