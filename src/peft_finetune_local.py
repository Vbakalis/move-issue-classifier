"""
Local (Apple Silicon / MPS) fine-tuning of CodeBERT-base for 5-class classification.

Two modes:
  - full   : full fine-tuning (all parameters trainable)
  - lora   : LoRA adapters on attention q/v, base model frozen

No bitsandbytes (CUDA-only). Uses MPS if available, else CPU.

Usage:
  python -m src.peft_finetune_local --mode full
  python -m src.peft_finetune_local --mode lora
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from datasets import Dataset
from peft import LoraConfig, TaskType, get_peft_model
from sklearn.metrics import accuracy_score, f1_score
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

try:
    from src.evaluate import compute_metrics, plot_confusion_matrix, save_results
except ImportError:
    from evaluate import compute_metrics, plot_confusion_matrix, save_results


def get_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def prepare_datasets(train_path, val_path, test_path, tokenizer, max_length=512):
    train_df = pd.read_csv(train_path)
    val_df = pd.read_csv(val_path)
    test_df = pd.read_csv(test_path)

    labels = sorted(train_df["primary_label"].unique())
    label2id = {l: i for i, l in enumerate(labels)}

    def to_hf(df):
        ds = Dataset.from_pandas(
            df[["code", "primary_label"]].rename(
                columns={"code": "text", "primary_label": "label_str"}
            ),
            preserve_index=False,
        )
        ds = ds.map(lambda x: {"label": label2id[x["label_str"]]})
        ds = ds.map(
            lambda x: tokenizer(x["text"], truncation=True, max_length=max_length),
            batched=True,
            remove_columns=["text", "label_str"],
        )
        return ds

    return to_hf(train_df), to_hf(val_df), to_hf(test_df), labels, label2id


def hf_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "macro_f1": f1_score(labels, preds, average="macro"),
    }


def run(mode: str, model_name: str = "microsoft/codebert-base",
        epochs: int = 4, batch_size: int = 16, lr: float = 2e-5,
        max_length: int = 512, lora_r: int = 16, lora_alpha: int = 32):

    device = get_device()
    print(f"[device] {device}")
    print(f"[mode]   {mode}")
    print(f"[model]  {model_name}")

    run_name = f"codebert_{mode}"
    out_dir = Path("checkpoints") / run_name
    out_dir.mkdir(parents=True, exist_ok=True)

                                                                             
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    train_ds, val_ds, test_ds, labels, label2id = prepare_datasets(
        "data/processed/train.csv",
        "data/processed/val.csv",
        "data/processed/test.csv",
        tokenizer,
        max_length=max_length,
    )
    id2label = {v: k for k, v in label2id.items()}
    print(f"[data] train={len(train_ds)} val={len(val_ds)} test={len(test_ds)} classes={labels}")

                                                                             
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=len(labels), label2id=label2id, id2label=id2label
    )

    if mode == "lora":
        peft_config = LoraConfig(
            task_type=TaskType.SEQ_CLS,
            r=lora_r,
            lora_alpha=lora_alpha,
            lora_dropout=0.05,
            target_modules=["query", "value"],
            bias="none",
        )
        model = get_peft_model(model, peft_config)
        model.print_trainable_parameters()
    elif mode == "full":
        total = sum(p.numel() for p in model.parameters())
        trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
        print(f"[params] trainable={trainable:,} total={total:,} ({100*trainable/total:.2f}%)")
    else:
        raise ValueError(f"unknown mode: {mode}")

                                                                             
    use_fp16 = device == "cuda"
    args = TrainingArguments(
        output_dir=str(out_dir),
        run_name=run_name,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size * 2,
        learning_rate=lr,
        weight_decay=0.01,
        warmup_ratio=0.1,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        logging_steps=25,
        report_to="none",
        save_total_limit=1,
        fp16=use_fp16,
        seed=42,
        use_cpu=(device == "cpu"),
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        processing_class=tokenizer,
        data_collator=DataCollatorWithPadding(tokenizer),
        compute_metrics=hf_metrics,
    )

    print("[train] starting")
    trainer.train()

                                                                            
    print("[eval] test set")
    preds_output = trainer.predict(test_ds)
    y_pred = np.argmax(preds_output.predictions, axis=-1)
    y_true = np.array(preds_output.label_ids)

                                                                               
    y_true_str = np.array([id2label[i] for i in y_true])
    y_pred_str = np.array([id2label[i] for i in y_pred])

    metrics = compute_metrics(y_true_str, y_pred_str, labels=labels)
    metrics["model"] = model_name
    metrics["mode"] = mode
    metrics["epochs"] = epochs
    metrics["batch_size"] = batch_size
    metrics["lr"] = lr

    method_tag = f"codebert_{mode}"
    save_results(metrics, method_tag, out_dir="results")
    plot_confusion_matrix(y_true_str, y_pred_str, labels=labels,
                          save_path=f"results/cm_{method_tag}.png",
                          title=f"CodeBERT {mode.upper()}")

    print("\n=== FINAL ===")
    print(f"accuracy : {metrics['accuracy']:.4f}")
    print(f"macro_f1 : {metrics['macro_f1']:.4f}")
    per_f1 = {c: v['f1-score'] for c, v in metrics['per_class'].items()
              if c in labels}
    print(f"per-class F1: {per_f1}")
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "lora"], required=True)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--model", default="microsoft/codebert-base")
    parser.add_argument("--max_length", type=int, default=512)
    args = parser.parse_args()

    run(
        mode=args.mode,
        model_name=args.model,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        max_length=args.max_length,
    )
