# Move Issue Classifier

LLM-based classification of issues in Move smart contracts for the
[Sui blockchain](https://sui.io). Companion code for the MSc thesis
*"LLM-Based Classification of Move Smart-Contract Issues in the Sui
Ecosystem: Dataset Consolidation and Baseline Model Comparison"*.

The thesis manuscript is being finalised separately; this repository
hosts only the code, configuration, and result artefacts.

## Overview

A consolidated dataset of ~3,300 Move code snippets is annotated across
five primary issue categories — `Perfect`, `SecurityError`, `SemanticError`,
`StyleError`, `SyntaxError` — and used to train and evaluate five baseline
configurations on identical splits.

| Method                                       | Trainable params  | Accuracy | Macro-F1 |
|----------------------------------------------|-------------------|---------:|---------:|
| Qwen2.5-Coder-7B zero-shot prompting         | 0                 |    0.499 |    0.369 |
| Qwen2.5-Coder-7B few-shot ($k=1$) prompting  | 0                 |    0.591 |    0.512 |
| TF-IDF + LinearSVC (balanced)                | —                 |    0.972 |    0.965 |
| Qwen2.5-Coder-7B + 4-bit MLX LoRA            | 11.5 M (0.15 %)   |    0.972 |    0.978 |
| CodeBERT full fine-tune                      | 125.8 M (100 %)   |    0.988 |    0.992 |
| **CodeBERT + LoRA ($r=16$)**                 | **1.2 M (0.94 %)**|**0.990** |**0.993** |

All experiments run on a single Apple Silicon laptop without CUDA.

## Layout

```
src/
  consolidate.py            # build train/val/test splits from raw .xlsx
  evaluate.py               # shared metrics + plotting helpers
  simple_baseline.py        # TF-IDF + LogReg / LinearSVC / RandomForest
  prompting_baseline.py     # zero-shot / few-shot via Qwen-7B (MLX)
  peft_finetune_local.py    # CodeBERT full fine-tune and LoRA fine-tune
  mlx_prepare_data.py       # JSONL conversion for MLX LoRA training
  mlx_evaluate.py           # MLX LoRA adapter evaluation
  predict.py                # CLI demo using the best CodeBERT+LoRA adapter
configs/
  config.yaml               # paths, label set, split ratios, seeds
notebooks/
  01_data_consolidation.ipynb
  02_simple_baseline.ipynb
  05_codebert_finetuning.ipynb
scripts/
  run_eda.py                # exploratory data plots
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

`mlx` and `mlx-lm` are required only for the Qwen prompting and MLX-LoRA
tracks; everything else (TF-IDF baselines and CodeBERT fine-tuning) runs
on CPU/MPS without them.

## Reproducing the results

```bash
# 1. Consolidate raw Excel exports into stratified train/val/test splits
python src/consolidate.py

# 2. Simple baselines (TF-IDF + classical classifiers)
python src/simple_baseline.py

# 3. Prompting baselines (Qwen2.5-Coder-7B-Instruct, 4-bit MLX, no training)
python src/prompting_baseline.py --mode zeroshot
python src/prompting_baseline.py --mode fewshot --k 1

# 4. CodeBERT full fine-tune and LoRA
python src/peft_finetune_local.py --mode full
python src/peft_finetune_local.py --mode lora

# 5. MLX LoRA on Qwen-7B (training + eval)
python src/mlx_prepare_data.py
mlx_lm.lora --config configs/qwen_lora.yaml
python src/mlx_evaluate.py
```

Metrics (`results/*_metrics.json`), confusion matrices
(`results/cm_*.png`), and per-prediction dumps
(`results/*_predictions.jsonl`, ignored by git) are written under
`results/`.

## Pretrained adapter

The best CodeBERT + LoRA adapter is shipped under
[`models/codebert_lora/`](models/codebert_lora/) (config and tokenizer
files only; the safetensors weights are distributed via the GitHub
release page to keep the repository slim).

A minimal demo:

```bash
python src/predict.py --code "module 0x1::foo { public fun bar() { let x = 1; } }"
```

## Dataset

The consolidated, deduplicated dataset of 3,321 labeled Move snippets is
published on Zenodo:

> *Sui Move Issues: A Labeled Dataset for Smart Contract Error Classification (v1).*
> [doi:10.5281/zenodo.19682589](https://doi.org/10.5281/zenodo.19682589)

Raw Excel exports under `data/raw/` and the processed splits under
`data/processed/` are gitignored; download the dataset from Zenodo and
place it under `data/processed/` (or run `src/consolidate.py` against
the raw exports) before reproducing the experiments.

## Citation

```bibtex
@mastersthesis{bakalis2026move,
  title  = {LLM-Based Classification of Move Smart-Contract Issues in the
            Sui Ecosystem: Dataset Consolidation and Baseline Model
            Comparison},
  author = {Bakalis, Vasileios},
  school = {Mediterranean College},
  year   = {2026}
}
```

## License

Code is released under the [MIT License](LICENSE).
