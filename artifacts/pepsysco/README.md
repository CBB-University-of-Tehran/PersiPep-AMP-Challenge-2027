# PepSySco Artifact

This directory contains the PepSySco web-service output used in the PersiPep AMP Challenge workflow.

## File

- `result.csv`

## Provenance

The input sequences were exported from the PersiPep Step 10 notebook as:

`STEP10_PEPSYSCO_INPUT_8_25.txt`

The file contained 60,000 peptide sequences.

These sequences were submitted to the PepSySco web service, and the resulting CSV output was downloaded and preserved here as:

`result.csv`

The returned columns were:

- `peptide`
- `score`

The preserved result is used by the downstream PersiPep pipeline to merge PepSySco synthesizability scores with the 60,000-candidate dataset.

## Reproducibility Note

PepSySco scoring was performed through the external PepSySco web service rather than through a locally executed model.

Therefore, `result.csv` is retained as the exact intermediate artifact used in the submitted PersiPep workflow.
