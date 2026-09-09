import sys
import time
import json
import hashlib
import pandas as pd
from pathlib import Path

from ampdiffusion_starter_kit.scoring import apex_mean_mic, APEX_PANEL

INPUT = Path("../STEP5B_PRESELECTED_120K.csv").resolve()
OUTPUT = Path("../STEP7_120K_WITH_APEX_POTENCY.csv").resolve()

CHUNK_SIZE = 1000
APEX_DIR = Path("apex").resolve()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_colname(text):
    return (
        text.replace(" ", "_")
        .replace(".", "")
        .replace("(", "")
        .replace(")", "")
        .replace("/", "_")
        .replace("-", "_")
    )


print("=" * 70, flush=True)
print("STEP 7 — FULL APEX POTENCY SCORING", flush=True)
print("=" * 70, flush=True)

df = pd.read_csv(INPUT, low_memory=False)

if "sequence" not in df.columns:
    raise ValueError("Missing sequence column.")

df["sequence"] = df["sequence"].astype(str).str.strip().str.upper()

if df["sequence"].duplicated().any():
    raise ValueError(
        f"Input contains {df['sequence'].duplicated().sum()} duplicate sequences."
    )

input_hash = sha256_file(INPUT)
short_hash = input_hash[:12]

RUN_DIR = Path(f"../apex_full_run_{short_hash}").resolve()
CHECKPOINT_DIR = RUN_DIR / "checkpoints"

RUN_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

n = len(df)
n_chunks = (n + CHUNK_SIZE - 1) // CHUNK_SIZE

manifest = {
    "input_file": str(INPUT),
    "input_sha256": input_hash,
    "rows": n,
    "chunk_size": CHUNK_SIZE,
    "chunks": n_chunks,
    "apex_panel": list(APEX_PANEL),
}

manifest_path = RUN_DIR / "run_manifest.json"

if manifest_path.exists():
    old = json.loads(manifest_path.read_text())

    if old != manifest:
        raise RuntimeError("Existing checkpoint manifest does not match this run.")

    print("Existing manifest validated.", flush=True)

else:
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print("New manifest created.", flush=True)

print(f"Input: {INPUT}", flush=True)
print(f"Rows: {n:,}", flush=True)
print(f"SHA256: {input_hash}", flush=True)
print(f"Chunks: {n_chunks}", flush=True)
print(f"Run directory: {RUN_DIR}", flush=True)

all_chunks = []
inference_times = []

for chunk_idx in range(n_chunks):

    start = chunk_idx * CHUNK_SIZE
    end = min(start + CHUNK_SIZE, n)

    chunk = df.iloc[start:end].copy().reset_index(drop=True)

    cp = CHECKPOINT_DIR / f"chunk_{chunk_idx:04d}.csv"

    # -----------------------------
    # Resume checkpoint
    # -----------------------------
    if cp.exists():

        scored = pd.read_csv(cp, low_memory=False)

        if len(scored) != len(chunk):
            raise RuntimeError(f"Row mismatch in {cp}")

        if not scored["sequence"].astype(str).equals(chunk["sequence"]):
            raise RuntimeError(f"Sequence mismatch in {cp}")

        if scored["apex_mean_mic_uM"].isna().any():
            raise RuntimeError(f"Missing MIC in {cp}")

        print(
            f"[{chunk_idx+1}/{n_chunks}] RESUME {cp.name}",
            flush=True
        )

        all_chunks.append(scored)
        continue

    print(
        f"[{chunk_idx+1}/{n_chunks}] "
        f"Scoring rows {start:,}-{end-1:,}",
        flush=True
    )

    t0 = time.time()

    seqs = chunk["sequence"].tolist()

    workdir = RUN_DIR / f"work_chunk_{chunk_idx:04d}"

    scores = apex_mean_mic(
        seqs=seqs,
        apex_dir=APEX_DIR,
        workdir=workdir,
    )

    chunk["apex_mean_mic_uM"] = chunk["sequence"].map(scores)

    if chunk["apex_mean_mic_uM"].isna().any():
        raise RuntimeError(
            f"Missing mean MIC in chunk {chunk_idx}"
        )

    # -----------------------------
    # Load raw 11-pathogen matrix
    # -----------------------------
    apex_file = workdir / "apex_pred.csv"

    if not apex_file.exists():
        raise FileNotFoundError(apex_file)

    apex_matrix = pd.read_csv(apex_file, index_col=0)

    chunk_set = set(chunk["sequence"])
    apex_set = set(apex_matrix.index.astype(str))

    if chunk_set != apex_set:
        missing = chunk_set - apex_set
        extra = apex_set - chunk_set

        raise RuntimeError(
            f"APEX sequence mismatch chunk {chunk_idx}: "
            f"missing={len(missing)}, extra={len(extra)}"
        )

    if len(apex_matrix) != len(chunk):
        raise RuntimeError(
            f"APEX row mismatch chunk {chunk_idx}: "
            f"{len(apex_matrix)} != {len(chunk)}"
        )

    pathogen_cols = []

    for pathogen in APEX_PANEL:

        if pathogen not in apex_matrix.columns:
            raise RuntimeError(
                f"Missing pathogen column: {pathogen}"
            )

        col = f"APEX_MIC_{safe_colname(pathogen)}_uM"
        pathogen_cols.append(col)

        mic_map = apex_matrix[pathogen].to_dict()

        chunk[col] = chunk["sequence"].map(mic_map)

    if chunk[pathogen_cols].isna().any().any():
        raise RuntimeError(
            f"Missing pathogen MIC in chunk {chunk_idx}"
        )

    # -----------------------------
    # Cross-check mean MIC
    # -----------------------------
    recalculated = chunk[pathogen_cols].mean(axis=1)

    diff = (
        recalculated - chunk["apex_mean_mic_uM"]
    ).abs().max()

    if diff > 1e-6:
        raise RuntimeError(
            f"Mean MIC verification failed: {diff}"
        )

    # -----------------------------
    # Save checkpoint
    # -----------------------------
    chunk.to_csv(cp, index=False)
    all_chunks.append(chunk)

    elapsed = time.time() - t0
    inference_times.append(elapsed)

    mean_time = sum(inference_times) / len(inference_times)

    remaining = sum(
        not (
            CHECKPOINT_DIR / f"chunk_{j:04d}.csv"
        ).exists()
        for j in range(chunk_idx + 1, n_chunks)
    )

    eta = mean_time * remaining

    print(
        f"  completed: {elapsed/60:.2f} min | "
        f"MIC range: "
        f"{chunk['apex_mean_mic_uM'].min():.2f}-"
        f"{chunk['apex_mean_mic_uM'].max():.2f} uM | "
        f"ETA: {eta/3600:.2f} h",
        flush=True
    )


# ============================================================
# Final combine
# ============================================================

result = pd.concat(all_chunks, ignore_index=True)

if len(result) != len(df):
    raise RuntimeError(
        f"Final row mismatch: {len(result)} != {len(df)}"
    )

if not result["sequence"].equals(
    df["sequence"].reset_index(drop=True)
):
    raise RuntimeError("Final sequence order mismatch.")

if result["sequence"].duplicated().any():
    raise RuntimeError("Duplicate sequences found in final output.")

result["apex_potency_rank"] = (
    result["apex_mean_mic_uM"]
    .rank(method="min", ascending=True)
    .astype(int)
)

result["apex_potency_percentile"] = (
    100
    * (
        1
        - result["apex_mean_mic_uM"]
        .rank(method="average", pct=True)
    )
).round(4)

result.to_csv(OUTPUT, index=False)

summary = {
    **manifest,
    "output_file": str(OUTPUT),
    "mean_mic_uM": float(result["apex_mean_mic_uM"].mean()),
    "median_mic_uM": float(result["apex_mean_mic_uM"].median()),
    "min_mic_uM": float(result["apex_mean_mic_uM"].min()),
    "max_mic_uM": float(result["apex_mean_mic_uM"].max()),
}

(RUN_DIR / "final_manifest.json").write_text(
    json.dumps(summary, indent=2)
)

print("", flush=True)
print("=" * 70, flush=True)
print("APEX FULL RUN COMPLETE", flush=True)
print("=" * 70, flush=True)

print(f"Candidates: {len(result):,}", flush=True)
print(
    f"Mean MIC: {result['apex_mean_mic_uM'].mean():.3f} uM",
    flush=True
)
print(
    f"Median MIC: {result['apex_mean_mic_uM'].median():.3f} uM",
    flush=True
)
print(
    f"Minimum MIC: {result['apex_mean_mic_uM'].min():.3f} uM",
    flush=True
)
print(
    f"Maximum MIC: {result['apex_mean_mic_uM'].max():.3f} uM",
    flush=True
)
print(f"OUTPUT: {OUTPUT}", flush=True)
