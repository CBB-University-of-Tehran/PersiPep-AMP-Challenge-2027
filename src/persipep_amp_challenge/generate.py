from pathlib import Path

GENERATION_SEEDS = [42, 44, 46, 48, 50]


def main():
    out_dir = Path("generate")
    out_dir.mkdir(parents=True, exist_ok=True)

    library_path = out_dir / "library.fasta"
    top_path = out_dir / "top.fasta"

    print("PersiPep generation entrypoint")
    print(f"Generation seeds: {GENERATION_SEEDS}")
    print(f"Expected library output: {library_path}")
    print(f"Expected Top100 output: {top_path}")


if __name__ == "__main__":
    main()
