from pathlib import Path
import hashlib

GENERATION_SEEDS = [42, 44, 46, 48, 50]

STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")


def read_fasta(path: Path):
    sequences = []

    current = []
    with path.open("r") as f:
        for line in f:
            line = line.strip()

            if line.startswith(">"):
                if current:
                    sequences.append("".join(current))
                    current = []
            elif line:
                current.append(line)

        if current:
            sequences.append("".join(current))

    return sequences


def sha256(path: Path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)

    return h.hexdigest()


def validate_sequences(sequences, name):
    if len(sequences) == 0:
        raise RuntimeError(f"{name} is empty")

    for seq in sequences:
        if not set(seq).issubset(STANDARD_AA):
            raise RuntimeError(
                f"{name} contains non-standard amino acids"
            )

        if not (8 <= len(seq) <= 50):
            raise RuntimeError(
                f"{name} contains invalid sequence length"
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

    root = Path.cwd()

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


    if len(library_sequences) != 50000:
        raise RuntimeError(
            f"Expected 50000 library sequences, found {len(library_sequences)}"
        )

    if len(top_sequences) != 100:
        raise RuntimeError(
            f"Expected 100 Top100 sequences, found {len(top_sequences)}"
        )


    print("\nValidation successful")
    print("-" * 60)

    print(
        f"Library sequences : {len(library_sequences):,}"
    )

    print(
        f"Top100 sequences  : {len(top_sequences):,}"
    )

    print(
        f"library SHA256     : {sha256(library)}"
    )

    print(
        f"top100 SHA256      : {sha256(top100)}"
    )

    print("\nPersiPep generation completed successfully.")


if __name__ == "__main__":
    main()
