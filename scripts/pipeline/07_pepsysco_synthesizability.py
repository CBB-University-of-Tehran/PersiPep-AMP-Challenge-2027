#!/usr/bin/env python3
"""
PersiPep Step 10 — PepSySco synthesizability integration.

This script reproduces the computational part of the executed Step 10 notebook
without Google Colab upload/download cells.

The original PepSySco inference was performed through the external PepSySco
web service. The exact returned result is preserved in the repository at:

    artifacts/pepsysco/result.csv

This script:
  1. loads the 60K Step 9B candidate table;
  2. validates AMP-Challenge-compatible sequences;
  3. calculates the synthesis diagnostic columns used in the notebook;
  4. exports the PepSySco input sequence list;
  5. loads the preserved PepSySco web-service result;
  6. merges PepSySco scores one-to-one by sequence;
  7. creates the Step 10 output CSV and manifest.

It does NOT re-run PepSySco inference locally.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


ALLOWED = set("ACDEFGHIKLMNPQRSTVWY")

ALIPHATIC_HYDROPHOBIC = set("ILMV")
AROMATIC = set("FWY")
ACIDIC = set("DE")
BASIC = set("HKR")
SMALL_POLAR = set("CST")
SMALL = set("AGP")
LARGE_POLAR = set("NQ")

EXPECTED_ROWS = 60_000

OUTPUT_CSV_NAME = "STEP10_60K_WITH_PEPSYSCO_SYNTHESIZABILITY.csv"
PEPSYSCO_INPUT_NAME = "STEP10_PEPSYSCO_INPUT_8_25.txt"
MANIFEST_NAME = "STEP10_manifest.json"


def repo_root() -> Path:
    """Return repository root from scripts/pipeline/<this_file>.py."""
    return Path(__file__).resolve().parents[2]


def normalize_sequences(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.upper()
    )


def longest_stretch(seq: str, residue_set: set[str]) -> int:
    best = 0
    current = 0

    for aa in seq:
        if aa in residue_set:
            current += 1
            best = max(best, current)
        else:
            current = 0

    return best


def validate_input(df: pd.DataFrame) -> None:
    if "sequence" not in df.columns:
        raise ValueError("Input CSV must contain a 'sequence' column.")

    if len(df) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS:,} input rows, found {len(df):,}."
        )

    unique = df["sequence"].nunique()
    if unique != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS:,} unique sequences, found {unique:,}."
        )

    invalid = df["sequence"].map(
        lambda s: (
            len(s) < 8
            or len(s) > 50
            or not set(s).issubset(ALLOWED)
        )
    )

    if invalid.any():
        examples = df.loc[invalid, "sequence"].head(5).tolist()
        raise ValueError(
            f"Found {int(invalid.sum())} invalid sequences. "
            f"Examples: {examples}"
        )


def add_synthesis_diagnostics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["peptide_length"] = df["sequence"].str.len()

    df["pepsysco_in_validated_length_domain"] = (
        df["peptide_length"].between(8, 25)
    )

    df["synth_aliphatic_hydrophobic_count_ILMV"] = (
        df["sequence"].map(
            lambda s: sum(aa in ALIPHATIC_HYDROPHOBIC for aa in s)
        )
    )

    df["synth_longest_ILMV_stretch"] = (
        df["sequence"].map(
            lambda s: longest_stretch(s, ALIPHATIC_HYDROPHOBIC)
        )
    )

    df["synth_n_terminal_residue"] = df["sequence"].str[0]

    df["synth_acidic_count_DE"] = (
        df["sequence"].map(lambda s: sum(aa in ACIDIC for aa in s))
    )

    df["synth_basic_count_HKR"] = (
        df["sequence"].map(lambda s: sum(aa in BASIC for aa in s))
    )

    df["synth_aromatic_count_FWY"] = (
        df["sequence"].map(lambda s: sum(aa in AROMATIC for aa in s))
    )

    df["synth_small_polar_count_CST"] = (
        df["sequence"].map(lambda s: sum(aa in SMALL_POLAR for aa in s))
    )

    df["synth_small_count_AGP"] = (
        df["sequence"].map(lambda s: sum(aa in SMALL for aa in s))
    )

    df["synth_large_polar_count_NQ"] = (
        df["sequence"].map(lambda s: sum(aa in LARGE_POLAR for aa in s))
    )

    # Audit/diagnostic residue counts retained from the executed notebook.
    df["synth_cys_count"] = df["sequence"].str.count("C")
    df["synth_met_count"] = df["sequence"].str.count("M")
    df["synth_pro_count"] = df["sequence"].str.count("P")
    df["synth_trp_count"] = df["sequence"].str.count("W")

    return df


def load_pepsysco_results(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            "PepSySco web-service artifact not found: "
            f"{path}\n"
            "Expected the preserved result at "
            "artifacts/pepsysco/result.csv unless --pepsysco-results "
            "is supplied explicitly."
        )

    pep = pd.read_csv(path)

    seq_candidates = [
        c for c in pep.columns
        if "peptide" in c.lower() or "sequence" in c.lower()
    ]

    score_candidates = [
        c for c in pep.columns
        if "score" in c.lower()
    ]

    if len(seq_candidates) != 1:
        raise ValueError(
            "Could not uniquely identify the peptide/sequence column "
            f"in PepSySco result. Candidates: {seq_candidates}"
        )

    if len(score_candidates) != 1:
        raise ValueError(
            "Could not uniquely identify the PepSySco score column. "
            f"Candidates: {score_candidates}"
        )

    pep = pep[[seq_candidates[0], score_candidates[0]]].copy()
    pep.columns = ["sequence", "pepsysco_score"]

    pep["sequence"] = normalize_sequences(pep["sequence"])
    pep["pepsysco_score"] = pd.to_numeric(
        pep["pepsysco_score"],
        errors="coerce",
    )

    if pep["sequence"].duplicated().any():
        raise ValueError(
            "PepSySco result contains duplicate peptide sequences."
        )

    if pep["pepsysco_score"].isna().any():
        raise ValueError(
            "PepSySco result contains missing or non-numeric scores."
        )

    if not pep["pepsysco_score"].between(0, 1).all():
        raise ValueError(
            "PepSySco scores must be within the range [0, 1]."
        )

    return pep


def merge_pepsysco_scores(
    df: pd.DataFrame,
    pep: pd.DataFrame,
) -> pd.DataFrame:
    valid_sequences = set(
        df.loc[
            df["pepsysco_in_validated_length_domain"],
            "sequence",
        ]
    )

    pep_sequences = set(pep["sequence"])

    missing = valid_sequences - pep_sequences
    extra = pep_sequences - valid_sequences

    if missing:
        raise ValueError(
            f"PepSySco result is missing {len(missing):,} expected sequences."
        )

    if extra:
        raise ValueError(
            f"PepSySco result contains {len(extra):,} unexpected sequences."
        )

    df = df.merge(
        pep,
        on="sequence",
        how="left",
        validate="one_to_one",
    )

    # Use nullable BooleanDtype so out-of-domain rows can cleanly carry NA.
    df["pepsysco_ge_0_85"] = (
        df["pepsysco_score"].ge(0.85).astype("boolean")
    )
    df["pepsysco_ge_0_99"] = (
        df["pepsysco_score"].ge(0.99).astype("boolean")
    )

    outside = ~df["pepsysco_in_validated_length_domain"]

    df.loc[outside, "pepsysco_score"] = np.nan
    df.loc[outside, "pepsysco_ge_0_85"] = pd.NA
    df.loc[outside, "pepsysco_ge_0_99"] = pd.NA

    return df


def validate_output(df: pd.DataFrame) -> None:
    if len(df) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS:,} output rows, found {len(df):,}."
        )

    if df["sequence"].nunique() != EXPECTED_ROWS:
        raise ValueError("Output sequence uniqueness check failed.")

    inside = df["pepsysco_in_validated_length_domain"]

    missing_inside = int(
        df.loc[inside, "pepsysco_score"].isna().sum()
    )
    if missing_inside != 0:
        raise ValueError(
            f"{missing_inside:,} PepSySco scores are missing inside "
            "the validated 8–25 aa domain."
        )

    if not (
        df.loc[inside, "pepsysco_score"]
        .dropna()
        .between(0, 1)
        .all()
    ):
        raise ValueError("PepSySco score range validation failed.")

    if not df.loc[~inside, "pepsysco_score"].isna().all():
        raise ValueError(
            "Out-of-domain PepSySco scores must remain missing."
        )


def print_summary(df: pd.DataFrame) -> None:
    inside = df["pepsysco_in_validated_length_domain"]

    print("=" * 70)
    print("STEP 10 VALIDATION")
    print("=" * 70)
    print("Total rows:", len(df))
    print("Unique sequences:", df["sequence"].nunique())
    print("Inside PepSySco validated domain:", int(inside.sum()))
    print("Outside validated domain:", int((~inside).sum()))
    print(
        "PepSySco scores present inside domain:",
        int(df.loc[inside, "pepsysco_score"].notna().sum()),
    )
    print(
        "PepSySco scores missing inside domain:",
        int(df.loc[inside, "pepsysco_score"].isna().sum()),
    )

    print("\nPepSySco score summary:")
    print(
        df.loc[inside, "pepsysco_score"].describe(
            percentiles=[0.05, 0.25, 0.5, 0.75, 0.95]
        )
    )

    print(
        "\nPepSySco >= 0.85:",
        int((df.loc[inside, "pepsysco_score"] >= 0.85).sum()),
    )
    print(
        "PepSySco >= 0.99:",
        int((df.loc[inside, "pepsysco_score"] >= 0.99).sum()),
    )

    print("\nLongest ILMV stretch:")
    print(df["synth_longest_ILMV_stretch"].describe())

    print("\nCys count:")
    print(df["synth_cys_count"].describe())


def write_manifest(
    path: Path,
    df: pd.DataFrame,
    input_csv: Path,
    pepsysco_results: Path,
) -> None:
    manifest = {
        "step": "10",
        "method": "PepSySco + literature-defined synthesis diagnostics",
        "primary_predictor": "PepSySco",
        "pepsysco_execution": "external web service",
        "pepsysco_artifact": str(pepsysco_results),
        "input_csv": str(input_csv),
        "pepsysco_model": "Gaussian Naive Bayes",
        "pepsysco_final_features": [
            "peptide_length",
            "Janin_hydrophobicity_index",
        ],
        "validated_length_domain": "8-25 aa",
        "published_reference_thresholds": {
            "0.85": {
                "reported_coverage": "~51%",
                "reported_accuracy": "~95%",
            },
            "0.99": {
                "reported_coverage": "~12%",
                "reported_accuracy": "~98%",
            },
        },
        "additional_diagnostics": [
            "ILMV_count",
            "longest_ILMV_stretch",
            "N_terminal_residue",
            "DE_count",
            "HKR_count",
            "FWY_count",
            "CST_count",
            "AGP_count",
            "NQ_count",
            "Cys_count",
            "Met_count",
            "Pro_count",
            "Trp_count",
        ],
        "hard_filter_applied": False,
        "rows": int(len(df)),
        "unique_sequences": int(df["sequence"].nunique()),
    }

    path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    root = repo_root()

    parser = argparse.ArgumentParser(
        description=(
            "PersiPep Step 10: merge the preserved PepSySco web-service "
            "scores with the 60K Step 9B candidate table."
        )
    )

    parser.add_argument(
        "--input-csv",
        type=Path,
        required=True,
        help=(
            "Step 9B 60K input CSV, normally "
            "STEP9B_60K_WITH_BIOLOGICAL_EMBEDDING_SCORES.csv"
        ),
    )

    parser.add_argument(
        "--pepsysco-results",
        type=Path,
        default=root / "artifacts" / "pepsysco" / "result.csv",
        help=(
            "Preserved PepSySco web-service result CSV. "
            "Default: artifacts/pepsysco/result.csv"
        ),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory for Step 10 outputs. Default: current directory.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_csv = args.input_csv.expanduser().resolve()
    pepsysco_results = args.pepsysco_results.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    print("PersiPep Step 10 — PepSySco synthesizability")
    print(f"Input CSV: {input_csv}")
    print(f"PepSySco artifact: {pepsysco_results}")
    print(f"Output directory: {output_dir}")

    df = pd.read_csv(input_csv, low_memory=False)
    df["sequence"] = normalize_sequences(df["sequence"])

    print(f"Rows: {len(df):,}")
    print(f"Unique sequences: {df['sequence'].nunique():,}")
    print(
        "Length range:",
        int(df["sequence"].str.len().min()),
        "-",
        int(df["sequence"].str.len().max()),
    )

    validate_input(df)

    df = add_synthesis_diagnostics(df)

    valid_subset = df.loc[
        df["pepsysco_in_validated_length_domain"],
        ["sequence"],
    ].copy()

    pepsysco_input = output_dir / PEPSYSCO_INPUT_NAME
    valid_subset.to_csv(
        pepsysco_input,
        index=False,
        header=False,
    )

    print(
        "Sequences for PepSySco:",
        len(valid_subset),
    )
    print(f"Saved: {pepsysco_input}")

    pep = load_pepsysco_results(pepsysco_results)

    print(f"PepSySco rows: {len(pep):,}")
    print(f"PepSySco unique sequences: {pep['sequence'].nunique():,}")
    print(
        "PepSySco missing scores:",
        int(pep["pepsysco_score"].isna().sum()),
    )

    df = merge_pepsysco_scores(df, pep)

    validate_output(df)
    print_summary(df)

    output_csv = output_dir / OUTPUT_CSV_NAME
    df.to_csv(output_csv, index=False)

    manifest_path = output_dir / MANIFEST_NAME
    write_manifest(
        manifest_path,
        df,
        input_csv,
        pepsysco_results,
    )

    print("\nAll Step 10 validation checks passed.")
    print(f"Saved: {output_csv}")
    print(f"Saved: {manifest_path}")


if __name__ == "__main__":
    main()
