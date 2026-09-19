"""AMP Challenge 2027 baseline generator (HydrAMP).

Produces a default-settings 50,000-sequence library and a ranked top-100 using the
published HydrAMP conditional VAE. Output goes to ``generate_broad_spectrum/``:

    generate_broad_spectrum/library.fasta   full 50,000-sequence library
    generate_broad_spectrum/top.fasta       top-100 ranked candidates

HydrAMP is a competition baseline (excluded from rankings), so generation uses
HydrAMP's default AMP settings; only the challenge's hard sequence rules are
enforced on top (20 canonical residues, length 8-50, uniqueness, no overlap with
the antibacterial reference, and <80% top-100 similarity to it).
"""

from __future__ import annotations

import os

# Must be set before importing HydrAMP (pulls TensorFlow + matplotlib at import time).
os.environ["MPLBACKEND"] = "Agg"
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import argparse
import sys
from pathlib import Path

import Levenshtein


CATEGORY = "generate_broad_spectrum"

REPO_ROOT = Path(__file__).resolve().parents[4]

MODEL_PATH = REPO_ROOT / "checkpoint" / "model" / "model"
DECOMPOSER_PATH = REPO_ROOT / "checkpoint" / "model" / "pca_decomposer.joblib"
ANTIBACTERIAL_FASTA = REPO_ROOT / "data" / "antibacterial.fasta"

STANDARD_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")

MIN_LENGTH = 8
MAX_LENGTH = 50

SIMILARITY_THRESHOLD = 0.8


def _read_fasta_sequences(path: Path) -> list[str]:
    sequences = []
    parts = []

    for line in path.read_text().splitlines():
        line = line.strip()

        if not line:
            continue

        if line.startswith(">"):
            if parts:
                sequences.append("".join(parts))
                parts = []
        else:
            parts.append(line.upper())

    if parts:
        sequences.append("".join(parts))

    return sequences


def _write_fasta(
    sequences: list[str],
    path: Path,
) -> None:
    with open(path, "w") as f:
        for i, seq in enumerate(
            sequences,
            start=1,
        ):
            f.write(
                f">seq{i}\n{seq}\n"
            )


def _is_valid(seq: str) -> bool:
    return (
        MIN_LENGTH
        <= len(seq)
        <= MAX_LENGTH
        and not (
            set(seq)
            - STANDARD_AMINO_ACIDS
        )
    )


def generate_library(
    generator,
    n_sequences: int,
    seed: int,
    references: set[str],
) -> dict[str, float]:
    """Accumulate unique valid HydrAMP sequences.

    Each accepted sequence is mapped to its HydrAMP MIC score.

    HydrAMP decoding is deterministic per seed. If additional
    generation rounds are needed, the seed is increased
    deterministically by one for each round.
    """

    collected: dict[str, float] = {}

    round_seed = seed

    while len(collected) < n_sequences:
        need = (
            n_sequences
            - len(collected)
        )

        batch = (
            generator
            .unconstrained_generation(
                mode="amp",
                n_target=need,
                seed=round_seed,
                filter_out=True,
                properties=True,
                n_attempts=1,
            )
        )

        # HydrAMP output is a list of dictionaries.
        # The "mic" field represents the predicted
        # probability of low MIC; higher is better.
        for item in batch:
            seq = str(
                item["sequence"]
            )

            if seq in collected:
                continue

            if seq in references:
                continue

            if not _is_valid(seq):
                continue

            collected[seq] = float(
                item["mic"]
            )

        print(
            f"  seed {round_seed}: "
            f"{len(collected)}/"
            f"{n_sequences} collected"
        )

        round_seed += 1

    return dict(
        list(
            collected.items()
        )[:n_sequences]
    )


def _passes_biological_filters(
    seq: str,
) -> bool:
    """Apply HydrAMP biological synthesizability filters.

    Criteria follow the HydrAMP filtering implementation:
    - no cysteines;
    - no >=3 positive residues in a 5-residue window;
    - no three identical residues in a row;
    - no three identical hydrophobic residues in a row.
    """

    from amp.inference.filtering import (
        check_for_cysteins,
        check_sequence_for_hydrophobic_clusters,
        check_sequence_for_positive_clusters,
        check_sequence_for_repetitive_clusters,
    )

    return (
        check_for_cysteins(seq)
        and
        check_sequence_for_positive_clusters(
            seq
        )
        and
        check_sequence_for_repetitive_clusters(
            seq
        )
        and
        check_sequence_for_hydrophobic_clusters(
            seq
        )
    )


def select_top(
    library: dict[str, float],
    top_k: int,
    references: set[str],
) -> list[str]:
    """Select ranked HydrAMP candidates.

    Candidates are ranked by HydrAMP MIC score and must:

    - pass the HydrAMP biological filters;
    - remain at or below 80% Levenshtein similarity
      to every antibacterial reference sequence.

    The paper's additional classifier-consensus and
    molecular-dynamics stages are not reproduced here.
    """

    ranked = sorted(
        library,
        key=lambda s: library[s],
        reverse=True,
    )

    top: list[str] = []

    for seq in ranked:
        if not _passes_biological_filters(
            seq
        ):
            continue

        if all(
            Levenshtein.ratio(
                seq,
                ref,
            )
            <= SIMILARITY_THRESHOLD
            for ref in references
        ):
            top.append(seq)

            if len(top) == top_k:
                break

    if len(top) < top_k:
        raise RuntimeError(
            f"Only {len(top)} of "
            f"{top_k} sequences passed "
            f"the biological + <"
            f"{SIMILARITY_THRESHOLD} "
            "similarity filters; "
            "increase --n-sequences."
        )

    return top


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--n-sequences",
        type=int,
        default=50_000,
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    parser.add_argument(
        "--model-path",
        default=MODEL_PATH,
    )

    parser.add_argument(
        "--decomposer-path",
        default=DECOMPOSER_PATH,
    )

    parser.add_argument(
        "--antibacterial-fasta",
        default=ANTIBACTERIAL_FASTA,
    )

    args = parser.parse_args()

    required_paths = (
        args.model_path,
        args.decomposer_path,
        args.antibacterial_fasta,
    )

    for path in required_paths:
        if not Path(path).exists():
            sys.exit(
                "ERROR: required path not found "
                f"(cwd: {os.getcwd()}): "
                f"{path}"
            )

    from amp.inference.inference import (
        HydrAMPGenerator
    )

    references = set(
        _read_fasta_sequences(
            Path(
                args.antibacterial_fasta
            )
        )
    )

    generator = HydrAMPGenerator(
        model_path=args.model_path,
        decomposer_path=args.decomposer_path,
        softmax=True,
    )

    out_dir = Path(
        CATEGORY
    )

    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        f"Generating "
        f"{args.n_sequences} sequences "
        f"(seed={args.seed})"
    )

    library = generate_library(
        generator,
        args.n_sequences,
        args.seed,
        references,
    )

    sequences = list(
        library
    )

    library_path = (
        out_dir
        / "library.fasta"
    )

    _write_fasta(
        sequences,
        library_path,
    )

    print(
        f"Wrote "
        f"{len(sequences)} sequences "
        f"-> {library_path}"
    )

    top = select_top(
        library,
        args.top_k,
        references,
    )

    top_path = (
        out_dir
        / "top.fasta"
    )

    _write_fasta(
        top,
        top_path,
    )

    print(
        f"Wrote top "
        f"{len(top)} sequences "
        f"-> {top_path}"
    )


if __name__ == "__main__":
    main()
