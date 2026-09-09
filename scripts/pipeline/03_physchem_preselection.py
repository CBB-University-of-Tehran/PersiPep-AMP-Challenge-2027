#!/usr/bin/env python3
from pathlib import Path
import argparse
from _notebook_runner import run_notebook

def main():
    p = argparse.ArgumentParser(description="PersiPep physicochemical scoring and 120K preselection")
    p.add_argument("--input-csv", type=Path, required=True)
    p.add_argument("--apd6-fasta", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()

    repo = Path(__file__).resolve().parents[2]
    nb = repo / "notebooks/02_physchem_and_preselection/02_physicochemical_realism_and_120k_preselection.ipynb"

    run_notebook(
        nb,
        upload_groups=[[a.input_csv], [a.apd6_fasta]],
        output_dir=a.output_dir,
    )

if __name__ == "__main__":
    main()
