# PersiPep — HydrAMP inference subproject

This directory preserves the HydrAMP starter-kit inference code used for the PersiPep AMP Challenge workflow as a separate Python 3.8 subproject.

## Provenance

- Upstream starter kit: `https://github.com/szczurek-lab/hydramp-starter-kit`
- Starter-kit commit: `7804df862872ccc6d09fe01c41bafbca194cfa31`
- HydrAMP source revision pinned by the starter kit: `6590d2f4c2963f25d30669052a4c4a857e0e7279`
- Upstream license: MIT (`LICENSE`)
- The vendored `src/hydramp_starter_kit/generate.py`, `pyproject.toml`, `uv.lock`, and `.python-version` are copied from that starter-kit snapshot.

The uploaded upstream ZIP used to create this bundle identifies commit `7804df862872ccc6d09fe01c41bafbca194cfa31` in its archive metadata.

## PersiPep model resources

To avoid duplicating large files, this subproject uses the model resources already stored at the repository root:

```text
checkpoint/model/
checkpoint/pca_decomposer.joblib
data/antibacterial.fasta
```

## Environment

HydrAMP has an older dependency stack and is therefore intentionally isolated from the root PersiPep Python 3.10 environment. This subproject declares Python 3.8 through `.python-version` and its own `pyproject.toml` / `uv.lock`.

## Inference smoke test

From `inference/hydramp/`, create the HydrAMP environment and generate a small deterministic test library using the root repository resources:

```bash
uv sync

uv run generate_broad_spectrum \
  --n-sequences 100 \
  --top-k 10 \
  --seed 42 \
  --model-path ../../checkpoint/model \
  --decomposer-path ../../checkpoint/pca_decomposer.joblib \
  --antibacterial-fasta ../../data/antibacterial.fasta
```

The command writes:

```text
generate_broad_spectrum/library.fasta
generate_broad_spectrum/top.fasta
```

For the historical PersiPep production run, HydrAMP was executed on the university server in five 50,000-target batches with starting seeds `42, 44, 46, 48, 50`. See the root `REPRODUCIBILITY.md` for the actual production workflow. This inference subproject preserves executable model-inference code and does **not** claim that the root `uv run generate` command reruns the complete multi-environment scientific pipeline.

## Upstream documentation

The original starter-kit README is retained verbatim as `UPSTREAM_README.md`.
