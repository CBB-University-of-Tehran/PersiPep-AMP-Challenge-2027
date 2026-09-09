import os
import time
import json
import hashlib
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd


INPUT = Path("../STEP7B_PRESELECTED_60K.csv").resolve()
OUTPUT = Path("../STEP8_60K_WITH_HEMOPI2_HC50.csv").resolve()

HEMOPI2_SCRIPT = Path("hemopi2_regression.py").resolve()
CHUNK_SIZE = 1000


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


print("=" * 72, flush=True)
print("STEP 8 — HemoPI2 HC50 SAFETY SCORING", flush=True)
print("=" * 72, flush=True)

df = pd.read_csv(INPUT, low_memory=False)

if "sequence" not in df.columns:
    raise ValueError("Missing required column: sequence")

df["sequence"] = df["sequence"].astype(str).str.strip().str.upper()

if len(df) != 60_000:
    raise ValueError(f"Expected 60,000 rows, found {len(df):,}")

if df["sequence"].duplicated().any():
    raise ValueError(
        f"Duplicate sequences: {df['sequence'].duplicated().sum()}"
    )

allowed = set("ACDEFGHIKLMNPQRSTVWY")

bad = df["sequence"].map(
    lambda s: len(s) < 8 or len(s) > 50 or not set(s).issubset(allowed)
)

if bad.any():
    raise ValueError(f"Invalid Challenge sequences found: {bad.sum()}")

# HemoPI2 internally truncates sequences >40 aa.
df["hemopi2_truncated_to_40aa"] = df["sequence"].str.len() > 40

print(f"Rows: {len(df):,}", flush=True)
print(f"Unique sequences: {df['sequence'].nunique():,}", flush=True)
print(
    "Sequences >40 aa (HemoPI2 truncation flag):",
    int(df["hemopi2_truncated_to_40aa"].sum()),
    flush=True,
)

input_hash = sha256_file(INPUT)
short_hash = input_hash[:12]

RUN_DIR = Path(f"../hemopi2_full_run_{short_hash}").resolve()
CHECKPOINT_DIR = RUN_DIR / "checkpoints"
WORK_DIR = RUN_DIR / "work"

CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
WORK_DIR.mkdir(parents=True, exist_ok=True)

n = len(df)
n_chunks = (n + CHUNK_SIZE - 1) // CHUNK_SIZE

manifest = {
    "input_file": str(INPUT),
    "input_sha256": input_hash,
    "rows": n,
    "chunk_size": CHUNK_SIZE,
    "chunks": n_chunks,
    "model": "HemoPI2 regression",
    "endpoint": "predicted HC50 uM",
    "note": "HemoPI2 internally truncates sequences longer than 40 aa",
}

manifest_path = RUN_DIR / "run_manifest.json"

if manifest_path.exists():
    previous = json.loads(manifest_path.read_text())
    if previous != manifest:
        raise RuntimeError("Existing manifest does not match current run.")
    print("Existing manifest validated.", flush=True)
else:
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print("New manifest created.", flush=True)

print(f"SHA256: {input_hash}", flush=True)
print(f"Chunks: {n_chunks}", flush=True)
print(f"Run directory: {RUN_DIR}", flush=True)

completed = []
inference_times = []

for chunk_idx in range(n_chunks):

    start = chunk_idx * CHUNK_SIZE
    end = min(start + CHUNK_SIZE, n)

    chunk = df.iloc[start:end].copy().reset_index(drop=True)

    # Stable IDs allow exact row validation even when >40 aa peptides
    # are truncated internally by HemoPI2.
    ids = [
        f"row_{start + i:06d}"
        for i in range(len(chunk))
    ]

    checkpoint = CHECKPOINT_DIR / f"chunk_{chunk_idx:04d}.csv"

    if checkpoint.exists():
        scored = pd.read_csv(checkpoint, low_memory=False)

        if len(scored) != len(chunk):
            raise RuntimeError(f"Checkpoint row mismatch: {checkpoint}")

        if not scored["sequence"].astype(str).equals(chunk["sequence"]):
            raise RuntimeError(f"Checkpoint sequence mismatch: {checkpoint}")

        if scored["hemopi2_hc50_uM"].isna().any():
            raise RuntimeError(f"Missing HC50 in checkpoint: {checkpoint}")

        print(
            f"[{chunk_idx+1}/{n_chunks}] RESUME {checkpoint.name}",
            flush=True,
        )

        completed.append(scored)
        continue

    chunk_work = WORK_DIR / f"chunk_{chunk_idx:04d}"
    chunk_work.mkdir(parents=True, exist_ok=True)

    fasta = chunk_work / "input.fasta"

    with open(fasta, "w") as f:
        for sid, seq in zip(ids, chunk["sequence"]):
            f.write(f">{sid}\n{seq}\n")

    print(
        f"[{chunk_idx+1}/{n_chunks}] "
        f"Scoring rows {start:,}-{end-1:,}",
        flush=True,
    )

    t0 = time.time()

    proc = subprocess.run(
        [
            "python",
            str(HEMOPI2_SCRIPT),
            "-i", str(fasta),
            "-j", "1",
            "-d", "2",
            "-wd", str(chunk_work),
        ],
        cwd=HEMOPI2_SCRIPT.parent,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    if proc.returncode != 0:
        print(proc.stdout, flush=True)
        raise RuntimeError(
            f"HemoPI2 failed in chunk {chunk_idx} "
            f"with return code {proc.returncode}"
        )

    result_file = chunk_work / "final_output.csv"

    if not result_file.exists():
        print(proc.stdout, flush=True)
        raise FileNotFoundError(
            f"HemoPI2 final_output.csv missing for chunk {chunk_idx}"
        )

    pred = pd.read_csv(result_file, low_memory=False)

    if len(pred) != len(chunk):
        raise RuntimeError(
            f"HemoPI2 output rows {len(pred)} != expected {len(chunk)}"
        )

    if "SeqID" not in pred.columns:
        raise RuntimeError(
            f"SeqID missing. Columns: {pred.columns.tolist()}"
        )

    if pred["SeqID"].astype(str).tolist() != ids:
        raise RuntimeError(
            f"HemoPI2 SeqID/order mismatch in chunk {chunk_idx}"
        )

    hc_cols = [c for c in pred.columns if "HC50" in str(c)]

    if len(hc_cols) != 1:
        raise RuntimeError(
            f"Could not uniquely identify HC50 column: {pred.columns.tolist()}"
        )

    hc_col = hc_cols[0]

    chunk["hemopi2_hc50_uM"] = pd.to_numeric(
        pred[hc_col],
        errors="coerce",
    )

    if chunk["hemopi2_hc50_uM"].isna().any():
        raise RuntimeError(
            f"Missing/non-numeric HC50 in chunk {chunk_idx}"
        )

    if "Prediction" in pred.columns:
        chunk["hemopi2_prediction"] = pred["Prediction"].astype(str).values
    else:
        chunk["hemopi2_prediction"] = np.where(
            chunk["hemopi2_hc50_uM"] < 100,
            "Hemolytic",
            "Non-Hemolytic",
        )

    # Preserve exactly what sequence HemoPI2 actually scored.
    chunk["hemopi2_sequence_used"] = pred["Sequence"].astype(str).values

    expected_used = chunk["sequence"].str[:40]

    if not chunk["hemopi2_sequence_used"].equals(expected_used):
        raise RuntimeError(
            f"HemoPI2 scored-sequence validation failed in chunk {chunk_idx}"
        )

    chunk.to_csv(checkpoint, index=False)
    completed.append(chunk)

    elapsed = time.time() - t0
    inference_times.append(elapsed)

    avg = sum(inference_times) / len(inference_times)

    remaining = sum(
        not (CHECKPOINT_DIR / f"chunk_{j:04d}.csv").exists()
        for j in range(chunk_idx + 1, n_chunks)
    )

    eta = avg * remaining

    print(
        f"  completed: {elapsed/60:.2f} min | "
        f"HC50 range: "
        f"{chunk['hemopi2_hc50_uM'].min():.3f}-"
        f"{chunk['hemopi2_hc50_uM'].max():.3f} uM | "
        f"ETA: {eta/3600:.2f} h",
        flush=True,
    )


# ============================================================
# Final combine
# ============================================================

result = pd.concat(completed, ignore_index=True)

if len(result) != len(df):
    raise RuntimeError(
        f"Final row mismatch: {len(result)} != {len(df)}"
    )

if not result["sequence"].equals(df["sequence"].reset_index(drop=True)):
    raise RuntimeError("Final sequence order mismatch.")

if result["sequence"].duplicated().any():
    raise RuntimeError("Duplicate sequences in final output.")

if result["hemopi2_hc50_uM"].isna().any():
    raise RuntimeError("Missing HC50 values in final output.")

# Higher HC50 = safer according to this prediction endpoint.
result["hemopi2_safety_rank"] = (
    result["hemopi2_hc50_uM"]
    .rank(method="min", ascending=False)
    .astype(int)
)

result["hemopi2_safety_percentile"] = (
    100
    * result["hemopi2_hc50_uM"]
      .rank(method="average", pct=True)
).round(4)

# Descriptive selectivity diagnostic using APEX mean MIC.
# This is NOT equivalent to experimental HC50/MIC50.
if "apex_mean_mic_uM" in result.columns:
    result["predicted_safety_window_diagnostic"] = (
        result["hemopi2_hc50_uM"]
        / result["apex_mean_mic_uM"]
    )

result.to_csv(OUTPUT, index=False)

summary = {
    **manifest,
    "output_file": str(OUTPUT),
    "unique_sequences": int(result["sequence"].nunique()),
    "duplicates": int(result["sequence"].duplicated().sum()),
    "missing_hc50": int(result["hemopi2_hc50_uM"].isna().sum()),
    "truncated_gt40aa": int(result["hemopi2_truncated_to_40aa"].sum()),
    "mean_hc50_uM": float(result["hemopi2_hc50_uM"].mean()),
    "median_hc50_uM": float(result["hemopi2_hc50_uM"].median()),
    "min_hc50_uM": float(result["hemopi2_hc50_uM"].min()),
    "max_hc50_uM": float(result["hemopi2_hc50_uM"].max()),
}

(RUN_DIR / "final_manifest.json").write_text(
    json.dumps(summary, indent=2)
)

print("", flush=True)
print("=" * 72, flush=True)
print("HEMOPI2 FULL RUN COMPLETE", flush=True)
print("=" * 72, flush=True)
print(f"Candidates: {len(result):,}", flush=True)
print(
    f"Unique sequences: {result['sequence'].nunique():,}",
    flush=True,
)
print(
    f"Truncated >40 aa: "
    f"{result['hemopi2_truncated_to_40aa'].sum():,}",
    flush=True,
)
print(
    f"Mean HC50: {result['hemopi2_hc50_uM'].mean():.3f} uM",
    flush=True,
)
print(
    f"Median HC50: {result['hemopi2_hc50_uM'].median():.3f} uM",
    flush=True,
)
print(
    f"Minimum HC50: {result['hemopi2_hc50_uM'].min():.3f} uM",
    flush=True,
)
print(
    f"Maximum HC50: {result['hemopi2_hc50_uM'].max():.3f} uM",
    flush=True,
)
print(f"OUTPUT: {OUTPUT}", flush=True)
