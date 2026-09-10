from pathlib import Path
import hashlib

GENERATION_SEEDS = [42, 44, 46, 48, 50]

STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")

EXPECTED_LIBRARY_SHA256 = (
    "92cb18fa4b138dd689d3761b0c93d8cc31123269e00d3f76db7db2315f054f26"
)

EXPECTED_TOP100_SHA256 = (
    "a75a0916d02eb87a1b058c06e7851bc4c329b25f0ab2db40bae1664753706fa5"
)


def read_fasta(path: Path):
    sequences = []
    current = []

    with path.open("r") as f:
        for line in f:
            line = line.strip()

            if line.startswith(">"):
                if current:
                    sequences.append("".join(current).upper())
                    current = []
            elif line:
                current.append(line)

        if current:
            sequences.append("".join(current).upper())

    return sequences


def sha256(path: Path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)

    return h.hexdigest()


def validate_sequences(sequences, name):
    if not sequences:
        raise RuntimeError(f"{name} is empty")

    for i, seq in enumerate(sequences, start=1):
        if not set(seq).issubset(STANDARD_AA):
            raise RuntimeError(
                f"{name}: sequence {i} contains non-standard amino acids"
            )

        if not (8 <= len(seq) <= 50):
            raise RuntimeError(
                f"{name}: sequence {i} has invalid length {len(seq)}"
            )

    if len(sequences) != len(set(sequences)):
        raise RuntimeError(
            f"{name} contains duplicate sequences"
        )


def main():
    print("=" * 60)
    print("PersiPep AMP Challenge 2027")
    print("Generation entrypoint")
    print("=" * 60)

    print(f"Generation seeds: {GENERATION_SEEDS}")

    # Repository root:
    # src/persipep_amp_challenge/generate.py -> repo root
    root = Path(__file__).resolve().parents[2]

    output_dir = root / "generate"

    library = output_dir / "library.fasta"
    top100 = output_dir / "top.fasta"

    if not library.exists():
        raise FileNotFoundError(
            f"Missing required output: {library}"
        )

    if not top100.exists():
        raise FileNotFoundError(
            f"Missing required output: {top100}"
        )

    library_sequences = read_fasta(library)
    top_sequences = read_fasta(top100)

    print("\nValidating outputs...")

    validate_sequences(
        library_sequences,
        "library.fasta"
    )

    validate_sequences(
        top_sequences,
        "top.fasta"
    )

    if len(library_sequences) != 50_000:
        raise RuntimeError(
            f"Expected 50000 library sequences, "
            f"found {len(library_sequences)}"
        )

    if len(top_sequences) != 100:
        raise RuntimeError(
            f"Expected 100 Top100 sequences, "
            f"found {len(top_sequences)}"
        )

    # Top100 must be contained in the submitted 50K library
    library_set = set(library_sequences)
    missing_top = [
        seq for seq in top_sequences
        if seq not in library_set
    ]

    if missing_top:
        raise RuntimeError(
            f"{len(missing_top)} Top100 sequences are not present "
            "in library.fasta"
        )

    library_hash = sha256(library)
    top100_hash = sha256(top100)

    if library_hash != EXPECTED_LIBRARY_SHA256:
        raise RuntimeError(
            "library.fasta SHA256 does not match the expected "
            f"submission artifact.\nExpected: {EXPECTED_LIBRARY_SHA256}\n"
            f"Observed: {library_hash}"
        )

    if top100_hash != EXPECTED_TOP100_SHA256:
        raise RuntimeError(
            "top.fasta SHA256 does not match the expected "
            f"submission artifact.\nExpected: {EXPECTED_TOP100_SHA256}\n"
            f"Observed: {top100_hash}"
        )

    print("\nValidation successful")
    print("-" * 60)
    print(f"Library sequences : {len(library_sequences):,}")
    print(f"Top100 sequences  : {len(top_sequences):,}")
    print("Top100 subset     : PASS")
    print(f"library SHA256     : {library_hash}")
    print(f"top100 SHA256      : {top100_hash}")

    print("\nPersiPep generation completed successfully.")


if __name__ == "__main__":
    main()
