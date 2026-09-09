#!/usr/bin/env python3
from pathlib import Path
import argparse
from _notebook_runner import run_notebook

def main():
    p = argparse.ArgumentParser(description="PersiPep potent-reference ESM-2 biological embedding scoring")
    p.add_argument("--input-csv", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()

    repo = Path(__file__).resolve().parents[2]
    nb = repo / "notebooks/04_esm2_embeddings/04b_biological_embedding_scoring.ipynb"

    run_notebook(nb, upload_groups=[[a.input_csv]], output_dir=a.output_dir)

if __name__ == "__main__":
    main()
