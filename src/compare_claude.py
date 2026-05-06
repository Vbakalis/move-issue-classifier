"""Compare CodeBERT+LoRA local model vs Claude Sonnet on test set samples.

Sends ~250 stratified samples from test.csv to both:
1. Local FastAPI server (CodeBERT+LoRA)
2. Claude API (claude-sonnet-4-6, zero-shot)

Produces accuracy, per-class F1, and a comparison table.
"""
import json
import os
import time
import sys
from pathlib import Path

import httpx
import pandas as pd
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
import anthropic

# ---------------------------------------------------------------------------
LABELS = ["Perfect", "SecurityError", "SemanticError", "StyleError", "SyntaxError"]
LOCAL_SERVER = "http://127.0.0.1:8765"
CLAUDE_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = (
    "You are a classifier for Move smart-contract code on the Sui blockchain. "
    f"Classify each code snippet into exactly one of: {', '.join(LABELS)}. "
    "Reply with ONLY the class name, nothing else. No explanations."
)

import re
LABEL_PATTERN = re.compile(r"\b(Perfect|SecurityError|SemanticError|StyleError|SyntaxError)\b")


def parse_label(raw: str) -> str:
    m = LABEL_PATTERN.search(raw)
    return m.group(1) if m else "Unknown"


def classify_local(code: str, client: httpx.Client) -> dict:
    """Classify via local CodeBERT+LoRA server."""
    resp = client.post(f"{LOCAL_SERVER}/classify", json={"code": code, "max_length": 512}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return {"label": data["label"], "confidence": data["confidence"]}


def classify_claude(code: str, client: anthropic.Anthropic) -> dict:
    """Classify via Claude API (zero-shot)."""
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=20,
        messages=[
            {"role": "user", "content": f"Code:\n```move\n{code.strip()}\n```\n\nClass:"}
        ],
        system=SYSTEM_PROMPT,
    )
    raw = msg.content[0].text.strip()
    label = parse_label(raw)
    return {"label": label, "raw": raw}


def main():
    # Load test data
    test_df = pd.read_csv("data/processed/test.csv")
    print(f"Full test set: {len(test_df)} samples")
    
    # Stratified sample of ~250
    sample_dfs = []
    for label in LABELS:
        sub = test_df[test_df["primary_label"] == label]
        n = min(len(sub), 50)  # up to 50 per class
        sample_dfs.append(sub.sample(n=n, random_state=42))
    
    sample_df = pd.concat(sample_dfs).reset_index(drop=True)
    print(f"Stratified sample: {len(sample_df)} samples")
    print(f"Distribution:\n{sample_df['primary_label'].value_counts().to_string()}\n")
    
    # Clients
    http_client = httpx.Client(verify=False)
    claude_client = anthropic.Anthropic(http_client=httpx.Client(verify=False))
    
    # Results
    results = []
    total = len(sample_df)
    
    for i, (_, row) in enumerate(sample_df.iterrows()):
        code = str(row["code"])
        true_label = row["primary_label"]
        
        # Local model
        try:
            local_result = classify_local(code, http_client)
            local_pred = local_result["label"]
            local_conf = local_result["confidence"]
        except Exception as e:
            local_pred = "ERROR"
            local_conf = 0.0
            print(f"  [LOCAL ERROR] {e}")
        
        # Claude
        try:
            claude_result = classify_claude(code, claude_client)
            claude_pred = claude_result["label"]
        except Exception as e:
            claude_pred = "ERROR"
            print(f"  [CLAUDE ERROR] {e}")
            time.sleep(5)  # rate limit backoff
        
        results.append({
            "true": true_label,
            "local_pred": local_pred,
            "local_conf": local_conf,
            "claude_pred": claude_pred,
        })
        
        # Progress
        if (i + 1) % 10 == 0:
            local_correct = sum(1 for r in results if r["local_pred"] == r["true"])
            claude_correct = sum(1 for r in results if r["claude_pred"] == r["true"])
            print(f"  [{i+1}/{total}] Local: {local_correct}/{i+1} ({100*local_correct/(i+1):.1f}%) | Claude: {claude_correct}/{i+1} ({100*claude_correct/(i+1):.1f}%)")
        
        # Small delay to avoid rate limiting
        time.sleep(0.5)
    
    # Save raw results
    results_df = pd.DataFrame(results)
    results_df.to_csv("data/processed/claude_comparison_results.csv", index=False)
    print(f"\nRaw results saved to data/processed/claude_comparison_results.csv")
    
    # Filter out errors
    valid = results_df[(results_df["local_pred"] != "ERROR") & (results_df["claude_pred"] != "ERROR")]
    print(f"Valid results: {len(valid)}/{len(results_df)}")
    
    # Metrics
    print("\n" + "="*60)
    print("LOCAL MODEL (CodeBERT + LoRA)")
    print("="*60)
    local_acc = accuracy_score(valid["true"], valid["local_pred"])
    print(f"Accuracy: {local_acc:.4f} ({local_acc*100:.1f}%)")
    print(classification_report(valid["true"], valid["local_pred"], labels=LABELS, zero_division=0))
    
    print("\n" + "="*60)
    print(f"CLAUDE ({CLAUDE_MODEL}, zero-shot)")
    print("="*60)
    claude_acc = accuracy_score(valid["true"], valid["claude_pred"])
    print(f"Accuracy: {claude_acc:.4f} ({claude_acc*100:.1f}%)")
    print(classification_report(valid["true"], valid["claude_pred"], labels=LABELS, zero_division=0))
    
    # Summary comparison
    print("\n" + "="*60)
    print("COMPARISON SUMMARY")
    print("="*60)
    print(f"{'Model':<30} {'Accuracy':<12} {'Samples'}")
    print(f"{'CodeBERT+LoRA (local)':<30} {local_acc*100:.1f}%{'':<7} {len(valid)}")
    print(f"{'Claude Sonnet 4.6 (zero-shot)':<30} {claude_acc*100:.1f}%{'':<7} {len(valid)}")
    print(f"\nDifference: {(local_acc - claude_acc)*100:+.1f} percentage points (local vs Claude)")


if __name__ == "__main__":
    main()
