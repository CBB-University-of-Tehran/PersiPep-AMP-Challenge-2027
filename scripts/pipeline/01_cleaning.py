#!/usr/bin/env python3
"""
PersiPep — Step 2
Multi-batch cleaning and reference screening.

This is a command-line version of:
notebooks/00_cleaning/AMP_Challenge_MultiBatch_Clean_Pool_Builder.ipynb

Scientific logic is preserved from the notebook. Colab-specific upload/download
calls and display helpers are replaced with explicit CLI arguments and file
outputs.
"""

from __future__ import annotations

import argparse
import math
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process
from tqdm import tqdm


OFFICIAL_THRESHOLD = 80.0
MIN_LENGTH = 8
MAX_LENGTH = 50
STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")


def read_fasta(filename: Path):
    """Read FASTA while preserving headers and empty records."""
    records = []
    current_id = None
    seq_parts = []

    def flush_record():
        nonlocal current_id, seq_parts
        if current_id is not None:
            seq = "".join(seq_parts).upper().strip()
            records.append((current_id, seq))

    with filename.open("r", encoding="utf-8", errors="ignore") as f:
        for raw_line in f:
            line = raw_line.strip()

            if line.startswith(">"):
                flush_record()
                current_id = line[1:].strip() or f"unnamed_{len(records)+1}"
                seq_parts = []
            elif line:
                seq_parts.append(re.sub(r"\s+", "", line))

        flush_record()

    return records


def clean_name(filename: Path | str):
    name = os.path.basename(str(filename))
    for ext in [".fasta", ".fa", ".faa", ".fas", ".txt", ".csv", ".tsv"]:
        if name.lower().endswith(ext):
            name = name[:-len(ext)]
            break
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")


def parse_args():
    p = argparse.ArgumentParser(
        description="PersiPep multi-batch cleaning and reference screening"
    )
    p.add_argument(
        "--generated",
        nargs="+",
        required=True,
        type=Path,
        help="Generated FASTA batches, in the intended provenance order.",
    )
    p.add_argument(
        "--references",
        nargs="+",
        required=True,
        type=Path,
        help=(
            "Reference FASTA files. Exactly one filename must contain "
            "'antibacterial'; the others are external AMP references."
        ),
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for cleaning outputs.",
    )
    p.add_argument(
        "--official-threshold",
        type=float,
        default=OFFICIAL_THRESHOLD,
        help="RapidFuzz pre-screen threshold. Default: 80.0",
    )
    return p.parse_args()


def main():
    args = parse_args()

    generated_files = [p.resolve() for p in args.generated]
    reference_files = [p.resolve() for p in args.references]
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for path in generated_files + reference_files:
        if not path.is_file():
            raise FileNotFoundError(path)

    official_candidates = [
        f for f in reference_files if "antibacterial" in f.name.lower()
    ]

    if len(official_candidates) != 1:
        raise ValueError(
            "Exactly one reference filename must contain 'antibacterial'."
        )

    official_file = official_candidates[0]
    external_files = [f for f in reference_files if f != official_file]

    print("=" * 70)
    print("PERSIPEP — MULTI-BATCH CLEANING")
    print("=" * 70)
    print("Generated batches:")
    for f in generated_files:
        print(" -", f)
    print("Official reference:")
    print(" -", official_file)
    print("External references:")
    for f in external_files:
        print(" -", f)

    generated_records = []
    for upload_order, filename in enumerate(generated_files, start=1):
        batch_name = clean_name(filename)
        records = read_fasta(filename)

        for within_batch_index, (record_id, sequence) in enumerate(records, start=1):
            generated_records.append(
                {
                    "upload_order": upload_order,
                    "batch": batch_name,
                    "source_filename": filename.name,
                    "within_batch_index": within_batch_index,
                    "original_id": record_id,
                    "sequence": sequence.upper().strip(),
                }
            )

    generated_df = pd.DataFrame(generated_records)
    print(f"Total generated sequences loaded: {len(generated_df):,}")

    reference_data = {
        filename: read_fasta(filename) for filename in reference_files
    }

    print("\nReference database summary")
    for filename, records in reference_data.items():
        seqs = [seq.upper().strip() for _, seq in records if seq.strip()]
        print(
            f"{clean_name(filename):20s} "
            f"| total={len(records):7d} "
            f"| unique={len(set(seqs)):7d}"
        )

    official_seq_to_id = {}
    for ref_id, seq in reference_data[official_file]:
        seq = seq.upper().strip()
        if seq and seq not in official_seq_to_id:
            official_seq_to_id[seq] = ref_id

    official_sequences = list(official_seq_to_id.keys())
    official_exact_set = set(official_sequences)

    official_length_buckets = defaultdict(list)
    for seq in official_sequences:
        official_length_buckets[len(seq)].append(seq)

    external_sets = {}
    external_ids = {}

    for filename in external_files:
        seq_set = set()
        seq_to_id = {}

        for ref_id, seq in reference_data[filename]:
            seq = seq.upper().strip()
            if not seq:
                continue
            seq_set.add(seq)
            if seq not in seq_to_id:
                seq_to_id[seq] = ref_id

        external_sets[filename] = seq_set
        external_ids[filename] = seq_to_id

    results = []
    seen_sequences = set()

    for row in tqdm(
        generated_df.itertuples(index=False),
        total=len(generated_df),
        desc="Screening candidates",
    ):
        sequence = row.sequence.upper().strip()

        result = {
            "upload_order": row.upload_order,
            "batch": row.batch,
            "source_filename": row.source_filename,
            "within_batch_index": row.within_batch_index,
            "original_id": row.original_id,
            "sequence": sequence,
            "length": len(sequence),
            "valid_alphabet": True,
            "valid_length": True,
            "internal_duplicate": False,
            "official_exact_match": False,
            "official_similarity_pct": None,
            "official_match_id": None,
            "official_match_sequence": None,
            "external_exact_overlap": False,
            "external_database": None,
            "external_match_id": None,
            "keep": True,
            "removal_reason": "PASS",
        }

        if not sequence:
            result["keep"] = False
            result["removal_reason"] = "EMPTY_SEQUENCE"
            results.append(result)
            continue

        invalid = set(sequence) - STANDARD_AA
        if invalid:
            result["valid_alphabet"] = False
            result["keep"] = False
            result["removal_reason"] = "INVALID_AA_" + "".join(sorted(invalid))
            results.append(result)
            continue

        if not MIN_LENGTH <= len(sequence) <= MAX_LENGTH:
            result["valid_length"] = False
            result["keep"] = False
            result["removal_reason"] = "INVALID_LENGTH"
            results.append(result)
            continue

        if sequence in seen_sequences:
            result["internal_duplicate"] = True
            result["keep"] = False
            result["removal_reason"] = "INTERNAL_DUPLICATE"
            results.append(result)
            continue

        seen_sequences.add(sequence)

        if sequence in official_exact_set:
            result["official_exact_match"] = True
            result["official_similarity_pct"] = 100.0
            result["official_match_id"] = official_seq_to_id[sequence]
            result["official_match_sequence"] = sequence
            result["keep"] = False
            result["removal_reason"] = "OFFICIAL_EXACT_MATCH"
            results.append(result)
            continue

        L = len(sequence)
        min_ref_len = max(1, math.ceil(L * 2 / 3))
        max_ref_len = math.floor(L * 1.5)

        candidate_refs = []
        for ref_len in range(min_ref_len, max_ref_len + 1):
            candidate_refs.extend(official_length_buckets.get(ref_len, []))

        best_hit = (
            process.extractOne(
                sequence,
                candidate_refs,
                scorer=fuzz.ratio,
                score_cutoff=args.official_threshold,
            )
            if candidate_refs
            else None
        )

        if best_hit:
            matched_seq, similarity, _ = best_hit
            result["official_similarity_pct"] = round(float(similarity), 3)
            result["official_match_sequence"] = matched_seq
            result["official_match_id"] = official_seq_to_id.get(matched_seq)

            if similarity > args.official_threshold:
                result["keep"] = False
                result["removal_reason"] = "OFFICIAL_ABOVE_80"
                results.append(result)
                continue

        for filename in external_files:
            if sequence in external_sets[filename]:
                result["external_exact_overlap"] = True
                result["external_database"] = clean_name(filename)
                result["external_match_id"] = external_ids[filename].get(sequence)
                result["keep"] = False
                result["removal_reason"] = "EXACT_OVERLAP_" + clean_name(filename)
                break

        results.append(result)

    audit_df = pd.DataFrame(results)
    clean_df = audit_df[audit_df["keep"] == True].copy()
    removed_df = audit_df[audit_df["keep"] == False].copy()

    clean_df = (
        clean_df.sort_values(["upload_order", "within_batch_index"])
        .reset_index(drop=True)
    )
    clean_df["clean_pool_id"] = [
        f"CLEAN_{i:07d}" for i in range(1, len(clean_df) + 1)
    ]

    batch_rows = []
    for upload_order, batch, source_filename in (
        generated_df[["upload_order", "batch", "source_filename"]]
        .drop_duplicates()
        .sort_values("upload_order")
        .itertuples(index=False, name=None)
    ):
        sub = audit_df[audit_df["batch"] == batch]
        batch_rows.append(
            {
                "upload_order": upload_order,
                "batch": batch,
                "source_filename": source_filename,
                "input_count": len(sub),
                "kept_count": int(sub["keep"].sum()),
                "removed_count": int((~sub["keep"]).sum()),
                "internal_duplicates": int(sub["internal_duplicate"].sum()),
                "official_exact_matches": int(sub["official_exact_match"].sum()),
                "official_above_80": int(
                    (sub["removal_reason"] == "OFFICIAL_ABOVE_80").sum()
                ),
                "external_exact_overlaps": int(
                    sub["external_exact_overlap"].sum()
                ),
                "retention_pct": (
                    round(sub["keep"].mean() * 100.0, 3) if len(sub) else 0.0
                ),
            }
        )

    batch_summary_df = pd.DataFrame(batch_rows)

    reference_tag = "__".join(sorted(clean_name(f) for f in reference_files))
    prefix = (
        f"MULTIBATCH_{len(generated_files)}"
        f"__filtered_against__{reference_tag}"
    )

    audit_file = output_dir / f"{prefix}__FULL_AUDIT.csv"
    removed_file = output_dir / f"{prefix}__REMOVED.csv"
    clean_file = output_dir / f"{prefix}__ALL_CLEAN.csv"
    clean_fasta = output_dir / f"{prefix}__ALL_CLEAN.fasta"
    batch_summary_file = output_dir / f"{prefix}__BATCH_SUMMARY.csv"
    manifest_file = output_dir / f"{prefix}__SCREENING_MANIFEST.txt"

    audit_df.to_csv(audit_file, index=False)
    removed_df.to_csv(removed_file, index=False)
    clean_df.to_csv(clean_file, index=False)
    batch_summary_df.to_csv(batch_summary_file, index=False)

    with clean_fasta.open("w") as f:
        for row in clean_df.itertuples(index=False):
            f.write(
                f">{row.clean_pool_id}"
                f"|batch={row.batch}"
                f"|original_id={row.original_id}\n"
            )
            f.write(row.sequence + "\n")

    with manifest_file.open("w") as f:
        f.write("PersiPep — Multi-Batch Clean Pool Builder\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Run timestamp: {datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"Generated files: {len(generated_files)}\n")
        for x in generated_files:
            f.write(f"  - {x}\n")

        f.write("\nOfficial Challenge reference:\n")
        f.write(f"  - {official_file}\n")

        f.write("\nExternal exact-overlap references:\n")
        for x in external_files:
            f.write(f"  - {x}\n")

        f.write("\nConfiguration:\n")
        f.write(f"  MIN_LENGTH={MIN_LENGTH}\n")
        f.write(f"  MAX_LENGTH={MAX_LENGTH}\n")
        f.write(f"  OFFICIAL_THRESHOLD={args.official_threshold}\n")
        f.write("  STANDARD_AA=ACDEFGHIKLMNPQRSTVWY\n")

        f.write("\nInterpretation:\n")
        f.write(
            "RapidFuzz fuzz.ratio is used only as a project pre-screen. "
            "Final official identity validation must use the organizer's "
            "official validation implementation.\n"
        )
        f.write(
            "This step creates a clean candidate pool only; it does not "
            "select the final 50,000 library or Top-100.\n"
        )

    print("\n" + "=" * 70)
    print("CLEANING COMPLETE")
    print("=" * 70)
    print(f"Input sequences        : {len(audit_df):,}")
    print(f"Unique clean sequences : {len(clean_df):,}")
    print(f"Removed sequences      : {len(removed_df):,}")
    if len(audit_df):
        print(
            f"Overall retention rate : "
            f"{len(clean_df)/len(audit_df)*100:.2f}%"
        )

    print("\nPer-batch summary:")
    print(batch_summary_df.to_string(index=False))

    print("\nRemoval reasons:")
    print(audit_df["removal_reason"].value_counts().to_string())

    print("\nOutputs:")
    for p in [
        audit_file,
        removed_file,
        clean_file,
        clean_fasta,
        batch_summary_file,
        manifest_file,
    ]:
        print(" -", p)


if __name__ == "__main__":
    main()
