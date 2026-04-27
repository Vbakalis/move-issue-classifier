"""
Dataset consolidation: merge 5 Excel files, clean, stratified split.

Expected Excel schema per file:
    - code   : Move smart-contract snippet
    - label  : Primary or Primary/SubLabel  (e.g. StyleError/NamingConvention)
    - output : 1-2 sentences of human-written guidance
"""

import argparse
import hashlib
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split


def _fingerprint(code: str) -> str:
    """SHA-256 of whitespace-normalised code for deduplication."""
    normed = " ".join(code.split())
    return hashlib.sha256(normed.encode("utf-8")).hexdigest()


def load_excel_files(raw_dir: str | Path) -> pd.DataFrame:
    """Read every .xlsx / .xls in *raw_dir* and concatenate."""
    raw_dir = Path(raw_dir)
    frames = []
    for p in sorted(raw_dir.glob("*.xls*")):
        df = pd.read_excel(p)
        df.columns = [c.strip().lower() for c in df.columns]
                                                   
        if "output/fix" in df.columns and "output" not in df.columns:
            df = df.rename(columns={"output/fix": "output"})
        assert {"code", "label", "output"}.issubset(df.columns), (
            f"{p.name}: expected columns 'code', 'label', 'output'; got {list(df.columns)}"
        )
        df["source_file"] = p.name
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"No Excel files found in {raw_dir}")
    return pd.concat(frames, ignore_index=True)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Basic cleaning: drop nulls, strip whitespace, extract primary label."""
    df = df.dropna(subset=["code", "label"]).copy()
    df["code"] = df["code"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip()
    df["output"] = df["output"].astype(str).str.strip()

                                                            
    header_mask = (df["code"] == "Code") & (df["label"] == "Label")
    n_headers = header_mask.sum()
    if n_headers:
        print(f"  Removed {n_headers} leaked header rows")
        df = df[~header_mask]

                              
    df["primary_label"] = df["label"].str.split("/").str[0].str.strip()
    df["sublabel"] = df["label"].apply(
        lambda x: x.split("/", 1)[1].strip() if "/" in x else None
    )

                                                            
    df["primary_label"] = df["primary_label"].str.replace(" ", "", regex=False)

                                    
    df["_fp"] = df["code"].apply(_fingerprint)
    n_before = len(df)
    df = df.drop_duplicates(subset="_fp").drop(columns="_fp")
    n_after = len(df)
    if n_before != n_after:
        print(f"  Removed {n_before - n_after} duplicate snippets")

    df = df.reset_index(drop=True)
    return df


def split_dataset(
    df: pd.DataFrame,
    test_size: float = 0.15,
    val_size: float = 0.15,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Stratified train / val / test split on primary_label."""
    train_df, test_df = train_test_split(
        df, test_size=test_size, random_state=seed, stratify=df["primary_label"]
    )
    relative_val = val_size / (1 - test_size)
    train_df, val_df = train_test_split(
        train_df, test_size=relative_val, random_state=seed,
        stratify=train_df["primary_label"],
    )
    return (
        train_df.reset_index(drop=True),
        val_df.reset_index(drop=True),
        test_df.reset_index(drop=True),
    )


def print_stats(df: pd.DataFrame, name: str = "Full") -> None:
    print(f"\n{'='*50}")
    print(f"  {name} set — {len(df)} samples")
    print(f"{'='*50}")
    print(df["primary_label"].value_counts().to_string())
    if "sublabel" in df.columns:
        n_sub = df["sublabel"].notna().sum()
        print(f"  ({n_sub} samples have sublabels)")


def consolidate(
    raw_dir: str = "data/raw",
    out_dir: str = "data/processed",
    test_size: float = 0.15,
    val_size: float = 0.15,
    seed: int = 42,
) -> None:
    raw_dir = Path(raw_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading Excel files …")
    df = load_excel_files(raw_dir)
    print(f"  Loaded {len(df)} rows from {df['source_file'].nunique()} files")

    print("Cleaning …")
    df = clean(df)

    labels = sorted(df["primary_label"].unique())
    print(f"  {len(labels)} primary classes: {labels}")

    print("Splitting …")
    train_df, val_df, test_df = split_dataset(df, test_size, val_size, seed)

    for split_name, split_df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        print_stats(split_df, split_name)
        split_df.to_csv(out_dir / f"{split_name}.csv", index=False)
        split_df.to_json(out_dir / f"{split_name}.jsonl", orient="records", lines=True)

                                        
    df.to_csv(out_dir / "full_clean.csv", index=False)
    print(f"\nSaved to {out_dir}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Consolidate Move-issue dataset")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--out-dir", default="data/processed")
    parser.add_argument("--test-size", type=float, default=0.15)
    parser.add_argument("--val-size", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    consolidate(args.raw_dir, args.out_dir, args.test_size, args.val_size, args.seed)
