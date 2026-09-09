# HydrAMP Model Resources

PersiPep uses the official HydrAMP Starter Kit for peptide sequence generation.

## Upstream repository

Official HydrAMP Starter Kit:

```text
https://github.com/szczurek-lab/hydramp-starter-kit
```

Exact starter-kit commit used for the PersiPep production workflow:

```text
7804df862872ccc6d09fe01c41bafbca194cfa31
```

Underlying HydrAMP package revision used:

```text
6590d2f4c2963f25d30669052a4c4a857e0e7279
```

## Included model resources

The HydrAMP model resources used by PersiPep are preserved in this repository under:

```text
checkpoint/
├── model/
├── pca_decomposer.joblib
└── README.md
```

The `model/` directory contains the pretrained HydrAMP model configuration and model-weight files required by the generation workflow.

The PCA decomposer used by the HydrAMP generation pipeline is preserved as:

```text
checkpoint/pca_decomposer.joblib
```

These files correspond to the HydrAMP resources used in the production PersiPep generation workflow.

## Production generation

The final PersiPep production pool was generated using HydrAMP in five independent runs initiated with the following starting seeds:

```text
42
44
46
48
50
```

Each run targeted:

```text
50,000 peptide sequences
```

for an initial production pool of approximately:

```text
250,000 generated peptides
```

The original server-side HydrAMP execution environment and generation commands are documented in:

```text
REPRODUCIBILITY.md
```

## Provenance

PersiPep does not claim authorship of HydrAMP or its pretrained model resources.

HydrAMP and its associated pretrained resources originate from the upstream HydrAMP project and remain subject to the upstream project's licensing and attribution requirements.

The exact source revisions are pinned above to support provenance and reproducibility.

## Licensing

The PersiPep project itself is distributed under the repository-level license.

Third-party HydrAMP source code, pretrained model resources, and associated files remain subject to their original upstream license and terms.

When redistributing the HydrAMP checkpoint files, the corresponding upstream license and attribution notice should be preserved alongside these resources.
