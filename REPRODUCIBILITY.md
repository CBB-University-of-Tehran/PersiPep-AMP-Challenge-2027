# PersiPep Reproducibility Guide

This document describes the actual computational workflow used to produce the PersiPep AMP Challenge submission.

The workflow is multi-environment:
- University server for HydrAMP generation, APEX scoring, and HemoPI2 scoring.
- Google Colab for cleaning, novelty analysis, physicochemical scoring, ESM-2 analyses, PepSySco integration, diversity analysis, and final selection.
- External PepSySco web service for PepSySco synthesizability inference.

The steps below should be executed in order.

## Final repository outputs

Challenge-facing FASTA outputs:

```text
generate/library.fasta
generate/top.fasta
```

These correspond to the scientific Step 12 FASTA outputs:

```text
STEP12_FINAL_LIBRARY_50K.fasta
STEP12_FINAL_TOP100.fasta
```

Preserved final-selection artifacts used by the root challenge entry point:

```text
artifacts/final_selection/STEP12_FINAL_LIBRARY_50K_FULL.zip
artifacts/final_selection/STEP12_FINAL_TOP100_FULL.csv
```

`STEP12_FINAL_LIBRARY_50K_FULL.zip` contains:

```text
STEP12_FINAL_LIBRARY_50K_FULL.csv
```

The root command:

```bash
uv run generate
```

deterministically reconstructs `generate/library.fasta` and `generate/top.fasta` from these preserved final-selection artifacts. The reconstructed FASTA files reproduce the original submitted files byte-for-byte.

Recorded SHA-256 values:

```text
92cb18fa4b138dd689d3761b0c93d8cc31123269e00d3f76db7db2315f054f26  generate/library.fasta
a75a0916d02eb87a1b058c06e7851bc4c329b25f0ab2db40bae1664753706fa5  generate/top.fasta
```

## Required reference data

Distributed in this repository:

```text
data/antibacterial.fasta
```

External AMP databases used by the workflow:

```text
ADP6.fasta
DBAASP.fasta
dbAMP3.fasta
```

These external database dumps are not redistributed in this repository. Obtain them from their original sources and place them under the filenames documented in `data/README.md`.

# Workflow

## Step 1 — HydrAMP generation

Environment: University server

HydrAMP resources in this repository:

```text
checkpoint/
inference/hydramp/
```

The `checkpoint/` tree preserves the pretrained HydrAMP model resources used by PersiPep. The repository-side inference snapshot is kept separately under:

```text
inference/hydramp/
├── .python-version
├── LICENSE
├── README.md
├── STARTER_KIT_COMMIT.txt
├── UPSTREAM_README.md
├── pyproject.toml
├── uv.lock
└── src/
    └── hydramp_starter_kit/
        ├── __init__.py
        └── generate.py
```

The inference subproject is intentionally isolated from the root challenge environment because the HydrAMP starter kit uses Python 3.8-era dependencies, while the root challenge package uses its own environment.

In the current repository snapshot, the preserved model payload is stored under `checkpoint/model/`, with the serialized model tree and `pca_decomposer.joblib` retained there. For the isolated upstream-style smoke test, those resources were staged into the starter kit's expected runtime paths `checkpoint/model` and `checkpoint/pca_decomposer.joblib`; no model parameters were altered.

HydrAMP Starter Kit commit used:

```text
7804df862872ccc6d09fe01c41bafbca194cfa31
```

Underlying HydrAMP package commit:

```text
6590d2f4c2963f25d30669052a4c4a857e0e7279
```

Five 50,000-sequence batches were generated with starting seeds 42, 44, 46, 48, and 50.

Original commands:

```bash
cd ~/AMP/01_models/hydramp

nohup uv run generate_broad_spectrum \
  --n-sequences 50000 \
  --top-k 100 \
  --seed 42 \
  > ~/AMP/03_generation/hydramp/hydramp_50k.log 2>&1 &

uv run generate_broad_spectrum --n-sequences 50000 --top-k 100 --seed 44
uv run generate_broad_spectrum --n-sequences 50000 --top-k 100 --seed 46
uv run generate_broad_spectrum --n-sequences 50000 --top-k 100 --seed 48
uv run generate_broad_spectrum --n-sequences 50000 --top-k 100 --seed 50
```

Preserved production files:

```text
hydramp_batch1_seed42.fasta
hydramp_batch2_seed44.fasta
hydramp_batch3_seed46.fasta
hydramp_batch4_seed48.fasta
hydramp_batch5_seed50.fasta
```

The HydrAMP model-specific Top100 outputs were retained only for traceability and were not used as the final PersiPep Top100.

### HydrAMP repository-side inference smoke test

The vendored inference snapshot under `inference/hydramp/` was tested independently from the root challenge reconstruction entry point.

A clean isolated Python 3.8 environment was created with `uv`. For the smoke test, the preserved HydrAMP model directory and PCA decomposer were staged in the layout expected by the upstream starter kit:

```text
checkpoint/
├── model/
└── pca_decomposer.joblib
```

and the official competition reference was staged as:

```text
data/antibacterial.fasta
```

The inference implementation sets:

```python
os.environ["MPLBACKEND"] = "Agg"
```

before importing HydrAMP/TensorFlow/Matplotlib. This avoids notebook-backend import failures in Colab and other headless environments.

Successful smoke-test command:

```bash
uv run --no-sync generate_broad_spectrum \
  --n-sequences 100 \
  --top-k 1 \
  --seed 42
```

Observed result:

```text
Generating 100 sequences (seed=42)
...
seed 42: 100/100 collected
Wrote 100 sequences -> generate_broad_spectrum/library.fasta
Wrote top 1 sequences -> generate_broad_spectrum/top.fasta
```

This smoke test confirms that the preserved HydrAMP inference code can load the model/PCA resources and perform real sequence generation. It is not a rerun of the five 50,000-sequence production batches and does not replace the production provenance above.


## Step 2 — Cleaning and reference screening

Environment: Google Colab

Notebook:

```text
notebooks/00_cleaning/AMP_Challenge_MultiBatch_Clean_Pool_Builder.ipynb
```

Pipeline script:

```text
scripts/pipeline/01_cleaning.py
```

Inputs:

```text
hydramp_batch1_seed42.fasta
hydramp_batch2_seed44.fasta
hydramp_batch3_seed46.fasta
hydramp_batch4_seed48.fasta
hydramp_batch5_seed50.fasta
antibacterial.fasta
ADP6.fasta
DBAASP.fasta
dbAMP3.fasta
```

Outputs:

```text
MULTIBATCH_5__filtered_against__ADP6__DBAASP__antibacterial__dbAMP3__ALL_CLEAN.csv
MULTIBATCH_5__filtered_against__ADP6__DBAASP__antibacterial__dbAMP3__ALL_CLEAN.fasta
```

Expected retained count:

```text
246,795
```

## Step 3 — External known-AMP near-match scoring

Environment: Google Colab

Notebook:

```text
notebooks/01_external_novelty/01_external_known_amp_nearmatch_scoring.ipynb
```

Pipeline script:

```text
scripts/pipeline/02_external_novelty.py
```

Input:

```text
MULTIBATCH_5__filtered_against__ADP6__DBAASP__antibacterial__dbAMP3__ALL_CLEAN.csv
```

References:

```text
ADP6.fasta
DBAASP.fasta
dbAMP3.fasta
```

Output:

```text
ALL_CLEAN_WITH_EXTERNAL_NEARMATCH.csv
```

This step uses a 3-mer shortlist followed by RapidFuzz similarity scoring. It is a project-level diagnostic, not the official Challenge `seqme` implementation.

## Step 4 — Physicochemical scoring and 120K preselection

Environment: Google Colab

Notebook:

```text
notebooks/02_physchem_and_preselection/02_physicochemical_realism_and_120k_preselection.ipynb
```

Pipeline script:

```text
scripts/pipeline/03_physchem_preselection.py
```

Input:

```text
ALL_CLEAN_WITH_EXTERNAL_NEARMATCH.csv
```

Outputs:

```text
ALL_CLEAN_WITH_NEARMATCH_AND_PHYSCHEM.csv
STEP5B_PRESELECTED_120K.csv
```

Expected preselected pool:

```text
120,000 sequences
```

## Step 5 — APEX potency scoring

Environment: University server

Wrapper:

```text
scripts/apex/run_apex_120k.py
```

Input:

```text
STEP5B_PRESELECTED_120K.csv
```

Original command:

```bash
nohup env OMP_NUM_THREADS=5 MKL_NUM_THREADS=5 OPENBLAS_NUM_THREADS=5 NUMEXPR_NUM_THREADS=5 \
  uv run python run_apex_120k.py > ../apex_120k.log 2>&1 &
```

Output:

```text
STEP7_120K_WITH_APEX_POTENCY.csv
```

Expected integrity:

```text
120,000 rows
120,000 unique sequences
0 missing apex_mean_mic_uM values
```

Recorded input SHA-256:

```text
c2c94f15415093e437128b0e82b91b6c82ee5a3395b04c0d2897244a8713e6f8
```

## Step 6 — APEX-informed 60K preselection

Environment: Google Colab

Notebook:

```text
notebooks/03_apex_preselection/03_apex_informed_preselection_120k_to_60k.ipynb
```

Pipeline script:

```text
scripts/pipeline/04_apex_preselection.py
```

Input:

```text
STEP7_120K_WITH_APEX_POTENCY.csv
```

Output:

```text
STEP7B_PRESELECTED_60K.csv
```

Expected size:

```text
60,000 unique sequences
```

## Step 7 — HemoPI2 safety scoring

Environment: University server

Wrapper:

```text
scripts/hemopi2/run_hemopi2_60k.py
```

Input:

```text
STEP7B_PRESELECTED_60K.csv
```

Original command:

```bash
nohup env OMP_NUM_THREADS=5 MKL_NUM_THREADS=5 OPENBLAS_NUM_THREADS=5 NUMEXPR_NUM_THREADS=5 \
  python run_hemopi2_60k.py > ../hemopi2_60k.log 2>&1 &
```

Output:

```text
STEP8_60K_WITH_HEMOPI2_HC50.csv
```

Expected integrity:

```text
60,000 rows
60,000 unique sequences
0 missing predicted HC50 values
```

Recorded input SHA-256:

```text
4d8bc6b53992afb127c842b3e1e55513833aeff9866c18f441ed1be0ef190231
```

## Step 8 — ESM-2 35M embedding extraction

Environment: Google Colab GPU

Notebook:

```text
notebooks/04_esm2_embeddings/04a_esm2_embedding_extraction_60k.ipynb
```

Pipeline script:

```text
scripts/pipeline/05_esm2_embedding_extraction.py
```

Input:

```text
STEP8_60K_WITH_HEMOPI2_HC50.csv
```

Model/settings:

```text
esm2_t12_35M_UR50D
layer 12
480-dimensional embedding
mean residue pooling
batch size 256
```

Outputs include:

```text
STEP9_ESM2_35M_EMBEDDINGS_60K.npz
STEP9_ESM2_manifest.json
```

## Step 9 — Biological embedding similarity scoring

Environment: Google Colab

Notebook:

```text
notebooks/04_esm2_embeddings/04b_biological_embedding_scoring.ipynb
```

Pipeline script:

```text
scripts/pipeline/06_biological_embedding_scoring.py
```

Model/settings:

```text
esm2_t6_8M_UR50D
layer 6
320-dimensional embedding
mean residue pooling
cosine similarity
```

Output:

```text
STEP9B_60K_WITH_BIOLOGICAL_EMBEDDING_SCORES.csv
```

Potent-reference criterion:

```text
MIC <= 16 µM in at least one tested strain
```

## Step 10 — PepSySco synthesizability

Environments:
- Google Colab for preparation, diagnostics, score integration, and output generation.
- External PepSySco web service for PepSySco inference.

Notebook:

```text
notebooks/05_synthesizability/05_pepsysco_synthesizability.ipynb
```

Executable integration script:

```text
scripts/pipeline/07_pepsysco_synthesizability.py
```

Input candidate table:

```text
STEP9B_60K_WITH_BIOLOGICAL_EMBEDDING_SCORES.csv
```

The executed notebook validated the 60,000 candidate sequences and exported the PepSySco input as:

```text
STEP10_PEPSYSCO_INPUT_8_25.txt
```

All 60,000 candidates used in this step were within the 8–25 residue PepSySco length domain used by the workflow.

PepSySco inference was performed through the external PepSySco web service. The exact returned web-service file used in the production workflow is preserved in this repository as:

```text
artifacts/pepsysco/result.csv
```

The preserved result contains:

```text
peptide
score
```

The integration script does not re-run PepSySco inference locally. Instead, it:
- validates the 60,000-sequence Step 9B input;
- recreates the synthesis diagnostic columns used in the notebook;
- recreates `STEP10_PEPSYSCO_INPUT_8_25.txt`;
- loads `artifacts/pepsysco/result.csv`;
- validates one-to-one sequence coverage and score range;
- merges PepSySco scores back onto the candidate table;
- writes the Step 10 output and manifest.

Primary output:

```text
STEP10_60K_WITH_PEPSYSCO_SYNTHESIZABILITY.csv
```

Step 10 manifest:

```text
STEP10_manifest.json
```

Additional artifact provenance:

```text
artifacts/pepsysco/README.md
```

Example repository-script execution:

```bash
python scripts/pipeline/07_pepsysco_synthesizability.py \
  --input-csv STEP9B_60K_WITH_BIOLOGICAL_EMBEDDING_SCORES.csv \
  --output-dir .
```

By default, the script reads the preserved PepSySco result from:

```text
artifacts/pepsysco/result.csv
```

## Step 11 — Diversity assessment

Environment: Google Colab

Notebook:

```text
notebooks/06_diversity/06_diversity_clustering_assessment.ipynb
```

Pipeline script:

```text
scripts/pipeline/08_diversity_assessment.py
```

Recorded settings:

```text
Nearest-neighbor metric: cosine
UMAP n_neighbors: 30
UMAP min_dist: 0.1
UMAP random_state: 42
HDBSCAN min_cluster_size: 50
HDBSCAN min_samples: 10
```

This stage is diagnostic and does not impose a new hard Challenge filter.

## Step 12 — Final 50K and Top100 selection

Environment: Google Colab

Notebook:

```text
notebooks/07_final_selection/07_final_50k_and_top100_selection.ipynb
```

Pipeline script:

```text
scripts/pipeline/09_final_selection.py
```

Equal-percentile final aggregation uses six project scoring dimensions:

```text
1. APEX predicted potency — lower predicted MIC is better
2. HemoPI2 predicted HC50 — higher is better
3. APD6 physicochemical realism — higher is better
4. External novelty diagnostic — higher is better
5. ESM-2 potent-reference Top-5 similarity — higher is better
6. PepSySco synthesizability — higher is better
```

Primary outputs:

```text
STEP12_FINAL_LIBRARY_50K_FULL.csv
STEP12_FINAL_TOP100_FULL.csv
STEP12_FINAL_LIBRARY_50K_SUMMARY.csv
STEP12_FINAL_TOP100_SUMMARY.csv
STEP12_FINAL_LIBRARY_50K.fasta
STEP12_FINAL_TOP100.fasta
STEP12_FINAL_SELECTION_SUMMARY_STATS.csv
STEP12_SELECTION_MANIFEST.json
```

Repository mapping:

```text
STEP12_FINAL_LIBRARY_50K.fasta -> generate/library.fasta
STEP12_FINAL_TOP100.fasta      -> generate/top.fasta
```

Preserved final-selection artifacts:

```text
STEP12_FINAL_LIBRARY_50K_FULL.csv
    -> artifacts/final_selection/STEP12_FINAL_LIBRARY_50K_FULL.zip

STEP12_FINAL_TOP100_FULL.csv
    -> artifacts/final_selection/STEP12_FINAL_TOP100_FULL.csv
```

The full 50K CSV is stored as a ZIP archive to reduce repository size. The Top-100 full CSV is stored directly. Together they preserve the final ranked selection state used by the challenge-facing reconstruction entry point.

# Deterministic challenge-output reconstruction

The scientific workflow above records how the candidate pool was generated, scored, filtered, and ranked across the original server, Colab, and PepSySco web-service environments.

For challenge packaging, the repository also provides a deterministic root entry point:

```bash
uv run generate
```

implemented in:

```text
src/persipep_amp_challenge/generate.py
```

The entry point reads:

```text
artifacts/final_selection/STEP12_FINAL_LIBRARY_50K_FULL.zip
artifacts/final_selection/STEP12_FINAL_TOP100_FULL.csv
```

and reconstructs:

```text
generate/library.fasta
generate/top.fasta
```

The 50K library is reconstructed in deterministic `final_library_rank` order from the full final-selection table. The Top-100 order is read from the preserved ranked Top-100 CSV. FASTA headers are reproduced using the original submission naming scheme:

```text
>AMP_LIBRARY_00001 ... >AMP_LIBRARY_50000
>AMP_TOP100_00001  ... >AMP_TOP100_00100
```

The entry point then validates sequence count, standard amino-acid alphabet, length range, uniqueness, and Top-100 membership in the 50K library.

The reconstructed FASTA files were compared against the original challenge-facing files. Sequence sets and sequence order were identical, and after restoring the original FASTA headers the reconstructed files matched the original submission byte-for-byte, including SHA-256.

The current packaging was also tested with the official AMP Challenge repository verifier. The staged repository was cloned by the verifier, dependencies were installed, `uv run generate` was executed, library and Top-100 checks passed, official reference overlap/similarity checks passed, and the generation command was rerun for reproducibility. The verifier reported:

```text
All checks passed. Submission is valid!
```

This root reconstruction command is a release-engineering layer over the completed scientific workflow. It does **not** claim to rerun HydrAMP generation, APEX, HemoPI2, ESM-2, PepSySco web-service inference, diversity analysis, or final ranking from raw inputs in a single environment. Those stages remain documented above with their actual execution environments and provenance.

# Final validation

Validate:

```text
library.fasta:
- exactly 50,000 sequences
- all sequences unique
- only 20 standard amino acids
- length 8–50 aa

top.fasta:
- exactly 100 sequences
- all Top100 sequences are members of library.fasta
- all sequences unique
- only 20 standard amino acids
- length 8–50 aa
```

Checksum verification:

```bash
sha256sum generate/library.fasta
sha256sum generate/top.fasta
```

Expected:

```text
92cb18fa4b138dd689d3761b0c93d8cc31123269e00d3f76db7db2315f054f26  generate/library.fasta
a75a0916d02eb87a1b058c06e7851bc4c329b25f0ab2db40bae1664753706fa5  generate/top.fasta
```

The current release packaging has been tested with the official AMP Challenge repository/submission verifier and passed all checks, including the verifier's known-reference overlap/similarity checks and reproducibility rerun.

Before final public submission, rerun the official verifier against the final public GitHub repository state to confirm that no later repository change has altered the validated behavior.

# Reproducibility notes

1. This guide preserves the actual multi-environment workflow used during the project.
2. HydrAMP generation, APEX, and HemoPI2 were university-server stages.
3. Cleaning, novelty analysis, physicochemical scoring, ESM-2 analyses, PepSySco integration, diversity assessment, and final selection were executed in Google Colab.
4. PepSySco inference itself was performed through the external PepSySco web service; the exact production result is preserved at `artifacts/pepsysco/result.csv`.
5. External AMP databases that are not redistributed must be obtained separately as documented in `data/README.md`.
6. RapidFuzz near-match similarity is a project diagnostic, not the official Challenge novelty implementation.
7. The Step 12 internal Top100 diversity pruning is distinct from the organizer's official known-reference compliance check.
8. The scripts under `scripts/pipeline/` provide repository-side executable implementations or wrappers for the documented analysis stages; component-specific dependencies and external services remain documented separately.
9. Final-selection state required for exact challenge-output reconstruction is preserved under `artifacts/final_selection/`.
10. `uv run generate` reconstructs the exact submitted FASTA files from those preserved final-selection artifacts and does not represent a single-environment rerun of the full scientific workflow.
11. The deterministic reconstruction reproduces the original `generate/library.fasta` and `generate/top.fasta` byte-for-byte, including the recorded SHA-256 values.
12. The current packaging passed the official AMP Challenge repository verifier in a clean staged clone, including installation, generation, library validation, Top-100 validation, reference overlap/similarity checks, and reproducibility rerun.
13. HydrAMP inference code and its isolated environment are preserved under `inference/hydramp/`; an independent Python 3.8 smoke test successfully generated 100 sequences with seed 42 and produced a filtered Top-1 FASTA.
14. The HydrAMP smoke test verifies executable inference and checkpoint loading, but it is intentionally smaller than the original five 50,000-sequence production runs.
15. The official verifier should be rerun once more against the final public repository state immediately before submission.
