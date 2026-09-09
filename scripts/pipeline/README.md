# PersiPep pipeline CLI wrappers

These files make the existing version-controlled notebooks callable from a
non-interactive command line without changing their scientific scoring logic.

## Files

- `01_cleaning.py` — standalone CLI implementation of the cleaning notebook.
- `_notebook_runner.py` — internal headless notebook runner.
- `02_external_novelty.py`
- `03_physchem_preselection.py`
- `04_apex_preselection.py`
- `05_esm2_embedding_extraction.py`
- `06_biological_embedding_scoring.py`
- `07_pepsysco_synthesizability.py`
- `08_diversity_assessment.py`
- `09_final_selection.py`

The existing production server wrappers remain separate:

- `scripts/apex/run_apex_120k.py`
- `scripts/hemopi2/run_hemopi2_60k.py`

## Important

These wrappers do **not** replace the notebooks. They execute the original
notebooks in the repository after substituting only Colab-specific upload,
download, `/content/`, and notebook-local pip-install behavior.

The root environment therefore needs `nbformat`, `nbclient`, and an IPython
kernel in addition to each notebook's scientific dependencies.

### PepSySco

The original Step 10 notebook is a two-part workflow: it exports peptide
sequences, then expects a PepSySco result CSV to be uploaded. Therefore the
CLI wrapper requires:

`--pepsysco-results <PepSySco result CSV>`

This is faithful to the current notebook. A fully unattended `uv run generate`
will still need either:
1. the exact PepSySco inference implementation packaged locally, or
2. a reproducibly supplied PepSySco result artifact.

Do not claim Step 10 is fully unattended until that dependency is resolved.

## Example

```bash
python scripts/pipeline/02_external_novelty.py \
  --input-csv work/cleaning/MULTIBATCH_5__filtered_against__ADP6__DBAASP__antibacterial__dbAMP3__ALL_CLEAN.csv \
  --references ADP6.fasta DBAASP.fasta dbAMP3.fasta \
  --output-dir work/external_novelty
```
