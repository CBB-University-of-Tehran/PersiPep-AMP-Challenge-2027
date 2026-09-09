# Data and Reference Resources

This directory contains the reference data required by the PersiPep AMP Challenge pipeline.

## Included file

### `antibacterial.fasta`

Official AMP Challenge antibacterial reference set.

This file is used for challenge-specific similarity screening and final compliance validation. In the PersiPep workflow, candidates with sequence similarity greater than the challenge threshold are removed during the cleaning stage.

Source:
https://github.com/szczurek-lab/amp-challenge-2027

---

## External AMP databases used in the pipeline

The following external AMP databases were used during cleaning, novelty assessment, and physicochemical benchmarking:

### APD6 / ADP6

File used during development:

`ADP6.fasta`

Purpose:
- exact-overlap screening during the clean-pool stage
- external known-AMP comparison
- physicochemical realism benchmarking

Database:
Antimicrobial Peptide Database (APD)

Website:
https://aps.unmc.edu/

The database is used for research and educational purposes. The complete FASTA file is not redistributed in this repository because the database content is copyright-protected and no sufficiently explicit permission for public redistribution of the full dataset was identified.

Users should obtain the corresponding APD release directly from the official APD website.

---

### DBAASP

File used during development:

`DBAASP.fasta`

Purpose:
- exact-overlap screening
- external known-AMP near-match scoring

Database:
Database of Antimicrobial Activity and Structure of Peptides (DBAASP)

Website:
https://dbaasp.org/

The complete database export is not redistributed in this repository because the published DBAASP terms contain restrictions related to redistribution.

Users should obtain the relevant database export directly from DBAASP and follow the database terms and citation requirements.

---

### dbAMP 3.0

File used during development:

`dbAMP3.fasta`

Purpose:
- exact-overlap screening
- external known-AMP near-match scoring

Database:
dbAMP 3.0

Website:
https://ycclab.cuhk.edu.cn/dbAMP/

The complete FASTA export is not redistributed in this repository because the redistribution license for the database dump was not sufficiently explicit for inclusion in a public repository.

Users should download the corresponding dbAMP release directly from the official dbAMP website.

---

## Reproducibility note

The PersiPep pipeline records the exact filenames and roles of all external reference databases used during candidate screening and scoring.

Because some third-party databases have redistribution restrictions or unclear redistribution terms, they are not bundled directly with this repository.

For full reproduction, users should obtain the corresponding database releases from their official sources and place them in this directory using the following filenames:

```text
data/
├── antibacterial.fasta
├── ADP6.fasta
├── DBAASP.fasta
└── dbAMP3.fasta
