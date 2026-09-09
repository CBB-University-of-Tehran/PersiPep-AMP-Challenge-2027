#!/usr/bin/env python3
from pathlib import Path
import argparse
from _notebook_runner import run_notebook

def main():
    p = argparse.ArgumentParser(description="PersiPep final 50K library and Top100 selection")
    p.add_argument("--input-csv", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()

    repo = Path(__file__).resolve().parents[2]
    nb = repo / "notebooks/07_final_selection/07_final_50k_and_top100_selection.ipynb"

    run_notebook(nb, upload_groups=[[a.input_csv]], output_dir=a.output_dir)

if __name__ == "__main__":
    main()
