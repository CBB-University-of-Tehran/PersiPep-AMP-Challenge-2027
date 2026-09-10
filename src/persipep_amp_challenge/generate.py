from pathlib import Path
import csv
import hashlib
import zipfile

GENERATION_SEEDS = [42, 44, 46, 48, 50]

STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")

EXPECTED_LIBRARY_SHA256 = (
    "92cb18fa4b138dd689d3761b0c93d8cc31123269e00d3f76db7db2315f054f26"
)

EXPECTED_TOP100_SHA256 = (
    "a75a0916d02eb87a1b058c06e7851bc4c329b25f0ab2db40bae1664753706fa5"
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def read_fasta(path: Path):
    sequences = []
    current = []

    with path.open("r", encoding="utf-8") as f:
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
        raise RuntimeError(f"{name} contains duplicate sequences")


def write_fasta(sequences, output_path: Path, prefix: str):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="\n") as f:
        for i, seq in enumerate(sequences, start=1):
            f.write(f">{prefix}_{i:05d}\n")
            f.write(f"{seq}\n")


def read_sequences_from_csv(csv_path: Path):
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise RuntimeError(f"No columns found in {csv_path}")

        if "sequence" not in reader.fieldnames:
            raise RuntimeError(
                f"'sequence' column not found in {csv_path}. "
                f"Available columns: {reader.fieldnames}"
            )

        sequences = []

        for row in reader:
            seq = (row.get("sequence") or "").strip().upper()
            if seq:
                sequences.append(seq)

    return sequences


def read_library_from_zip(zip_path: Path):
    if not zip_path.exists():
        raise FileNotFoundError(
            f"Missing library artifact: {zip_path}"
        )

    with zipfile.ZipFile(zip_path, "r") as z:
        csv_files = [
            name for name in z.namelist()
            if name.lower().endswith(".csv")
        ]

        if len(csv_files) != 1:
            raise RuntimeError(
                f"Expected exactly one CSV inside {zip_path}, "
                f"found {len(csv_files)}"
            )

        csv_name = csv_files[0]

        with z.open(csv_name) as raw:
            import io

            text = io.TextIOWrapper(raw, encoding="utf-8-sig")
            reader = csv.DictReader(text)

            if not reader.fieldnames:
                raise RuntimeError(
                    f"No columns found in {csv_name}"
                )

            if "sequence" not in reader.fieldnames:
                raise RuntimeError(
                    f"'sequence' column not found in {csv_name}"
                )

            rows = list(reader)

    # Prefer explicit final_library_rank if available
    if rows and "final_library_rank" in rows[0]:
        try:
            rows.sort(
                key=lambda r: int(float(r["final_library_rank"]))
            )
        except Exception as e:
            raise RuntimeError(
                "Could not sort by final_library_rank"
            ) from e

    sequences = [
        (row.get("sequence") or "").strip().upper()
        for row in rows
        if (row.get("sequence") or "").strip()
    ]

    return sequences


def build_outputs_from_artifacts(root: Path):
    artifact_dir = root / "artifacts" / "final_selection"

    library_zip = (
        artifact_dir / "STEP12_FINAL_LIBRARY_50K_FULL.zip"
    )

    top_csv = (
        artifact_dir / "STEP12_FINAL_TOP100_FULL.csv"
    )

    output_dir = root / "generate"
    library_fasta = output_dir / "library.fasta"
    top_fasta = output_dir / "top.fasta"

    print("\nRebuilding outputs from final-selection artifacts...")

    library_sequences = read_library_from_zip(library_zip)
    top_sequences = read_sequences_from_csv(top_csv)

    if len(library_sequences) != 50_000:
        raise RuntimeError(
            f"Expected 50000 library sequences in artifact, "
            f"found {len(library_sequences)}"
        )

    if len(top_sequences) != 100:
        raise RuntimeError(
            f"Expected 100 Top100 sequences in artifact, "
            f"found {len(top_sequences)}"
        )

    validate_sequences(
        library_sequences,
        "library artifact"
    )

    validate_sequences(
        top_sequences,
        "Top100 artifact"
    )

    library_set = set(library_sequences)

    missing_top = [
        seq for seq in top_sequences
        if seq not in library_set
    ]

    if missing_top:
        raise RuntimeError(
            f"{len(missing_top)} Top100 sequences are not "
            "present in the library artifact"
        )

    write_fasta(
        library_sequences,
        library_fasta,
        "PersiPep"
    )

    write_fasta(
        top_sequences,
        top_fasta,
        "PersiPep_TOP"
    )

    print("Generated:")
    print(f"  {library_fasta}")
    print(f"  {top_fasta}")


def main():
    print("=" * 60)
    print("PersiPep AMP Challenge 2027")
    print("Generation entrypoint")
    print("=" * 60)

    print(f"Generation seeds: {GENERATION_SEEDS}")

    root = Path(__file__).resolve().parents[2]

    library = root / "generate" / "library.fasta"
    top100 = root / "generate" / "top.fasta"

    #
    # Build outputs if missing
    #
    if not library.exists() or not top100.exists():
        build_outputs_from_artifacts(root)
    else:
        print(
            "\nExisting FASTA outputs found; "
            "validating committed outputs."
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

    library_set = set(library_sequences)

    missing_top = [
        seq for seq in top_sequences
        if seq not in library_set
    ]

    if missing_top:
        raise RuntimeError(
            f"{len(missing_top)} Top100 sequences are not "
            "present in library.fasta"
        )

    library_hash = sha256(library)
    top100_hash = sha256(top100)

    print("\nValidation successful")
    print("-" * 60)
    print(f"Library sequences : {len(library_sequences):,}")
    print(f"Top100 sequences  : {len(top_sequences):,}")
    print("Top100 subset     : PASS")
    print(f"library SHA256     : {library_hash}")
    print(f"top100 SHA256      : {top100_hash}")

    if library_hash != EXPECTED_LIBRARY_SHA256:
        print(
            "\nWARNING: rebuilt library FASTA content is valid "
            "but byte-level SHA256 differs from the committed artifact."
        )

    if top100_hash != EXPECTED_TOP100_SHA256:
        print(
            "\nWARNING: rebuilt Top100 FASTA content is valid "
            "but byte-level SHA256 differs from the committed artifact."
        )

    print("\nPersiPep generation completed successfully.")


if __name__ == "__main__":
    main()
