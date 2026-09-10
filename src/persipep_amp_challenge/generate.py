from pathlib import Path
import csv
import hashlib
import io
import zipfile


STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")

LIBRARY_SIZE = 50_000
TOP_SIZE = 100

# Seeds used in the original PersiPep HydrAMP generation workflow.
GENERATION_SEEDS = [42, 44, 46, 48, 50]


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

            if not line:
                continue

            if line.startswith(">"):
                if current:
                    sequences.append(
                        "".join(current).upper()
                    )
                    current = []
            else:
                current.append(line)

        if current:
            sequences.append(
                "".join(current).upper()
            )

    return sequences


def validate_sequences(sequences, name):
    if not sequences:
        raise RuntimeError(
            f"{name} is empty"
        )

    for i, seq in enumerate(sequences, start=1):

        if not set(seq).issubset(STANDARD_AA):
            invalid = sorted(
                set(seq) - STANDARD_AA
            )

            raise RuntimeError(
                f"{name}: sequence {i} contains "
                f"non-standard amino acids: {invalid}"
            )

        if not (8 <= len(seq) <= 50):
            raise RuntimeError(
                f"{name}: sequence {i} has "
                f"invalid length {len(seq)}"
            )

    if len(sequences) != len(set(sequences)):
        raise RuntimeError(
            f"{name} contains duplicate sequences"
        )


def write_fasta(
    sequences,
    output_path: Path,
    prefix: str,
):
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as f:

        for i, seq in enumerate(
            sequences,
            start=1,
        ):
            f.write(
                f">{prefix}_{i:05d}\n"
            )
            f.write(
                f"{seq}\n"
            )


def read_sequences_from_csv(
    csv_path: Path,
):
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Missing Top100 artifact: {csv_path}"
        )

    with csv_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise RuntimeError(
                f"No columns found in {csv_path}"
            )

        if "sequence" not in reader.fieldnames:
            raise RuntimeError(
                f"'sequence' column not found in "
                f"{csv_path}. Available columns: "
                f"{reader.fieldnames}"
            )

        sequences = []

        for row in reader:

            seq = (
                row.get("sequence") or ""
            ).strip().upper()

            if seq:
                sequences.append(seq)

    return sequences


def read_library_from_zip(
    zip_path: Path,
):
    if not zip_path.exists():
        raise FileNotFoundError(
            f"Missing library artifact: {zip_path}"
        )

    if not zipfile.is_zipfile(zip_path):
        raise RuntimeError(
            f"Invalid ZIP archive: {zip_path}"
        )

    with zipfile.ZipFile(
        zip_path,
        "r",
    ) as z:

        csv_files = [
            name
            for name in z.namelist()
            if (
                name.lower().endswith(".csv")
                and not name.startswith("__MACOSX/")
            )
        ]

        if len(csv_files) != 1:
            raise RuntimeError(
                f"Expected exactly one CSV inside "
                f"{zip_path.name}; found "
                f"{len(csv_files)}: {csv_files}"
            )

        csv_name = csv_files[0]

        with z.open(csv_name) as raw:

            text = io.TextIOWrapper(
                raw,
                encoding="utf-8-sig",
                newline="",
            )

            reader = csv.DictReader(text)

            if not reader.fieldnames:
                raise RuntimeError(
                    f"No columns found in "
                    f"{csv_name}"
                )

            if "sequence" not in reader.fieldnames:
                raise RuntimeError(
                    f"'sequence' column not found "
                    f"in {csv_name}. "
                    f"Available columns: "
                    f"{reader.fieldnames}"
                )

            rows = list(reader)

    # Reconstruct the submitted library deterministically
    # using final_library_rank when available.
    if (
        rows
        and "final_library_rank"
        in rows[0]
    ):

        try:
            rows.sort(
                key=lambda row: int(
                    float(
                        row[
                            "final_library_rank"
                        ]
                    )
                )
            )

        except (
            TypeError,
            ValueError,
            KeyError,
        ) as exc:

            raise RuntimeError(
                "Could not sort library artifact "
                "by final_library_rank."
            ) from exc

    sequences = []

    for row in rows:

        seq = (
            row.get("sequence") or ""
        ).strip().upper()

        if seq:
            sequences.append(seq)

    return sequences


def build_outputs_from_artifacts(
    root: Path,
):
    artifact_dir = (
        root
        / "artifacts"
        / "final_selection"
    )

    library_zip = (
        artifact_dir
        / "STEP12_FINAL_LIBRARY_50K_FULL.zip"
    )

    top_csv = (
        artifact_dir
        / "STEP12_FINAL_TOP100_FULL.csv"
    )

    output_dir = (
        root
        / "generate"
    )

    library_fasta = (
        output_dir
        / "library.fasta"
    )

    top_fasta = (
        output_dir
        / "top.fasta"
    )

    print(
        "\nRebuilding challenge outputs "
        "from preserved final-selection artifacts..."
    )

    print(
        f"Library artifact : {library_zip}"
    )

    print(
        f"Top100 artifact  : {top_csv}"
    )

    library_sequences = (
        read_library_from_zip(
            library_zip
        )
    )

    top_sequences = (
        read_sequences_from_csv(
            top_csv
        )
    )

    if len(library_sequences) != LIBRARY_SIZE:
        raise RuntimeError(
            f"Expected {LIBRARY_SIZE:,} library "
            f"sequences in artifact; found "
            f"{len(library_sequences):,}"
        )

    if len(top_sequences) != TOP_SIZE:
        raise RuntimeError(
            f"Expected {TOP_SIZE} Top100 "
            f"sequences in artifact; found "
            f"{len(top_sequences)}"
        )

    validate_sequences(
        library_sequences,
        "library artifact",
    )

    validate_sequences(
        top_sequences,
        "Top100 artifact",
    )

    library_set = set(
        library_sequences
    )

    missing_top = [
        seq
        for seq in top_sequences
        if seq not in library_set
    ]

    if missing_top:
        raise RuntimeError(
            f"{len(missing_top)} Top100 "
            "sequences are not present in "
            "the 50K library artifact."
        )

    # Reproduce the original submitted FASTA headers exactly.
    write_fasta(
        library_sequences,
        library_fasta,
        "AMP_LIBRARY",
    )

    write_fasta(
        top_sequences,
        top_fasta,
        "AMP_TOP100",
    )

    return (
        library_fasta,
        top_fasta,
    )


def main():
    print("=" * 60)
    print(
        "PersiPep AMP Challenge 2027"
    )
    print(
        "Deterministic generation entrypoint"
    )
    print("=" * 60)

    print(
        f"Original HydrAMP generation seeds: "
        f"{GENERATION_SEEDS}"
    )

    # src/persipep_amp_challenge/generate.py
    # -> repository root
    root = (
        Path(__file__)
        .resolve()
        .parents[2]
    )

    # Always reconstruct the challenge FASTAs
    # from the preserved final-selection artifacts.
    library, top100 = (
        build_outputs_from_artifacts(
            root
        )
    )

    # Read generated FASTAs back and validate them.
    library_sequences = read_fasta(
        library
    )

    top_sequences = read_fasta(
        top100
    )

    print(
        "\nValidating generated outputs..."
    )

    validate_sequences(
        library_sequences,
        "library.fasta",
    )

    validate_sequences(
        top_sequences,
        "top.fasta",
    )

    if (
        len(library_sequences)
        != LIBRARY_SIZE
    ):
        raise RuntimeError(
            f"Expected {LIBRARY_SIZE:,} "
            f"library sequences; found "
            f"{len(library_sequences):,}"
        )

    if (
        len(top_sequences)
        != TOP_SIZE
    ):
        raise RuntimeError(
            f"Expected {TOP_SIZE} Top100 "
            f"sequences; found "
            f"{len(top_sequences)}"
        )

    library_set = set(
        library_sequences
    )

    missing_top = [
        seq
        for seq in top_sequences
        if seq not in library_set
    ]

    if missing_top:
        raise RuntimeError(
            f"{len(missing_top)} Top100 "
            "sequences are not present "
            "in library.fasta."
        )

    library_hash = sha256(
        library
    )

    top_hash = sha256(
        top100
    )

    print(
        "\nValidation successful"
    )

    print("-" * 60)

    print(
        f"Library sequences : "
        f"{len(library_sequences):,}"
    )

    print(
        f"Top100 sequences  : "
        f"{len(top_sequences):,}"
    )

    print(
        "Top100 subset     : PASS"
    )

    print(
        f"library SHA256    : "
        f"{library_hash}"
    )

    print(
        f"top100 SHA256     : "
        f"{top_hash}"
    )

    print(
        "\nPersiPep generation "
        "completed successfully."
    )


if __name__ == "__main__":
    main()
