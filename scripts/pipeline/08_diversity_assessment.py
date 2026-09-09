#!/usr/bin/env python3
from pathlib import Path
import argparse
from _notebook_runner import run_notebook

def main():
    p = argparse.ArgumentParser(description="PersiPep diversity and clustering assessment")
    p.add_argument("--input-csv", type=Path, required=True)
    p.add_argument("--embeddings-npz", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()

    repo = Path(__file__).resolve().parents[2]
    nb = repo / "notebooks/06_diversity/06_diversity_clustering_assessment.ipynb"

    run_notebook(
        nb,
        upload_groups=[[a.input_csv], [a.embeddings_npz]],
        output_dir=a.output_dir,
    )

if __name__ == "__main__":
    main()
