# PersiPep Reproducibility Guide

This document describes the actual computational workflow used to produce the PersiPep AMP Challenge submission.

The workflow is multi-environment:
- University server for HydrAMP generation, APEX scoring, and HemoPI2 scoring.
- Google Colab for cleaning, novelty analysis, physicochemical scoring, ESM-2 analyses, PepSySco, diversity analysis, and final selection.

The steps below should be executed in order.

## Final repository outputs

```text
generate/library.fasta
generate/top.fasta
```

These correspond to:
```text
STEP12_FINAL_LIBRARY_50K.fasta
STEP12_FINAL_TOP100.fasta
```

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
├── model/
├── pca_decomposer.joblib
└── README.md
```

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

## Step 2 — Cleaning and reference screening

Environment: Google Colab

Notebook:
```text
notebooks/00_cleaning/AMP_Challenge_MultiBatch_Clean_Pool_Builder_v2.ipynb
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

Environment: Google Colab

Notebook:
```text
notebooks/05_synthesizability/05_pepsysco_synthesizability.ipynb
```

Output:
```text
STEP10_60K_WITH_PEPSYSCO_SYNTHESIZABILITY.csv
```

## Step 11 — Diversity assessment

Environment: Google Colab

Notebook:
```text
notebooks/06_diversity/06_diversity_clustering_assessment.ipynb
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

Finally, run the official AMP Challenge repository/submission verifier and the official known-reference compliance procedure required by the organizers.

# Reproducibility notes

1. This guide preserves the actual multi-environment workflow used during the project.
2. HydrAMP generation, APEX, and HemoPI2 were server stages; the remaining analysis stages were executed in Google Colab.
3. External AMP databases that are not redistributed must be obtained separately as documented in `data/README.md`.
4. RapidFuzz near-match similarity is a project diagnostic, not the official Challenge novelty implementation.
5. The Step 12 internal Top100 diversity pruning is distinct from the organizer's final official known-reference compliance check.
6. Competition-specific single-command packaging, if required by the final official repository specification, is a separate release-engineering layer and should not be confused with the scientific workflow documented here.
