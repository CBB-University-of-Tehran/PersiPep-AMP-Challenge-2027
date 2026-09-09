#!/usr/bin/env python3
from pathlib import Path
import argparse
from _notebook_runner import run_notebook

def main():
    p = argparse.ArgumentParser(description="PersiPep external known-AMP near-match scoring")
    p.add_argument("--input-csv", type=Path, required=True)
    p.add_argument("--references", type=Path, nargs="+", required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()

    repo = Path(__file__).resolve().parents[2]
    nb = repo / "notebooks/01_external_novelty/01_external_known_amp_nearmatch_scoring.ipynb"

    run_notebook(
        nb,
        upload_groups=[[a.input_csv], a.references],
        output_dir=a.output_dir,
    )

if __name__ == "__main__":
    main()
