"""Qualitative comparison: Claude-only vs Classifier+Claude on 10 Move snippets.

Picks 2 snippets per category from the test set, then for each:
  A) Claude-only: asks Claude "what's wrong with this code?" (no hints)
  B) Classifier+Claude: first classifies with local model, then asks Claude
     with the classifier's prediction as context

Saves all 20 responses to a CSV for human evaluation by Move developers.
"""
import os
import time
import json
from pathlib import Path

import httpx
import pandas as pd
import anthropic

# ---------------------------------------------------------------------------
LABELS = ["Perfect", "SecurityError", "SemanticError", "StyleError", "SyntaxError"]
LOCAL_SERVER = "http://127.0.0.1:8765"
CLAUDE_MODEL = "claude-sonnet-4-6"
SNIPPETS_PER_CLASS = 2
OUTPUT_CSV = "data/processed/qualitative_comparison.csv"

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PROMPT_A = (
    "You are an expert Move smart-contract auditor for the Sui blockchain.\n\n"
    "Analyze the following Move code snippet. Identify what type of issue it has "
    "(if any) and explain your reasoning. Be specific about the problem and suggest "
    "a fix if applicable.\n\n"
    "Code:\n```move\n{code}\n```"
)

PROMPT_B = (
    "You are an expert Move smart-contract auditor for the Sui blockchain.\n\n"
    "Our automated classifier analyzed the following Move code snippet and "
    "classified it as: **{label}** (confidence: {confidence:.1%}).\n\n"
    "Based on this classification, analyze the code in detail. Explain what "
    "the issue is (if any) and suggest a fix if applicable.\n\n"
    "Code:\n```move\n{code}\n```"
)


def classify_local(code: str, client: httpx.Client) -> dict:
    """Classify via local CodeBERT+LoRA server."""
    resp = client.post(
        f"{LOCAL_SERVER}/classify",
        json={"code": code, "max_length": 512},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return {"label": data["label"], "confidence": data["confidence"]}


def ask_claude(prompt: str, client: anthropic.Anthropic) -> str:
    """Send a prompt to Claude and return the response."""
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def pick_snippets(test_df: pd.DataFrame) -> pd.DataFrame:
    """Pick 2 snippets per class, preferring medium-length representative ones."""
    selected = []
    for label in LABELS:
        sub = test_df[test_df["primary_label"] == label].copy()
        sub["code_len"] = sub["code"].str.len()
        # Pick from the middle of the length distribution (not too short, not too long)
        median_len = sub["code_len"].median()
        sub["dist_from_median"] = (sub["code_len"] - median_len).abs()
        picks = sub.nsmallest(SNIPPETS_PER_CLASS, "dist_from_median")
        selected.append(picks)
    return pd.concat(selected).reset_index(drop=True)


def main():
    # Load test data
    test_df = pd.read_csv("data/processed/test.csv")
    print(f"Full test set: {len(test_df)} samples")

    # Pick 2 snippets per class
    snippets = pick_snippets(test_df)
    print(f"Selected {len(snippets)} snippets:")
    print(snippets["primary_label"].value_counts().to_string())
    print()

    # Clients
    http_client = httpx.Client(verify=False)
    claude_client = anthropic.Anthropic(
        http_client=httpx.Client(verify=False)
    )

    results = []

    for i, (_, row) in enumerate(snippets.iterrows()):
        code = str(row["code"])
        true_label = row["primary_label"]
        snippet_id = i + 1

        print(f"[{snippet_id}/{len(snippets)}] {true_label} (len={len(code)} chars)")

        # --- Condition A: Claude only ---
        prompt_a = PROMPT_A.format(code=code.strip())
        print("  Condition A (Claude only)...")
        response_a = ask_claude(prompt_a, claude_client)
        time.sleep(1)

        # --- Local classifier ---
        print("  Classifying with local model...")
        local_result = classify_local(code, http_client)
        local_label = local_result["label"]
        local_conf = local_result["confidence"]
        print(f"  -> Predicted: {local_label} ({local_conf:.1%})")

        # --- Condition B: Classifier + Claude ---
        prompt_b = PROMPT_B.format(
            code=code.strip(),
            label=local_label,
            confidence=local_conf,
        )
        print("  Condition B (Classifier + Claude)...")
        response_b = ask_claude(prompt_b, claude_client)
        time.sleep(1)

        results.append({
            "snippet_id": snippet_id,
            "true_label": true_label,
            "code": code,
            "classifier_prediction": local_label,
            "classifier_confidence": f"{local_conf:.1%}",
            "response_A_claude_only": response_a,
            "response_B_classifier_plus_claude": response_b,
        })

        print(f"  Done.\n")

    # Save to CSV
    results_df = pd.DataFrame(results)
    results_df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved {len(results_df)} rows to {OUTPUT_CSV}")

    # Also print a readable summary
    print("\n" + "=" * 70)
    print("QUALITATIVE COMPARISON SUMMARY")
    print("=" * 70)
    for r in results:
        print(f"\n--- Snippet {r['snippet_id']} (True: {r['true_label']}, "
              f"Classifier: {r['classifier_prediction']} {r['classifier_confidence']}) ---")
        print(f"\nCode:\n{r['code'][:200]}...")
        print(f"\n[A] Claude only:\n{r['response_A_claude_only'][:300]}...")
        print(f"\n[B] Classifier + Claude:\n{r['response_B_classifier_plus_claude'][:300]}...")
        print("-" * 70)


if __name__ == "__main__":
    main()
