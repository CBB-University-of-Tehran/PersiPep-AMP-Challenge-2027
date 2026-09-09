#!/usr/bin/env python3
from pathlib import Path
import argparse
from _notebook_runner import run_notebook

def main():
    p = argparse.ArgumentParser(description="PersiPep PepSySco synthesizability stage")
    p.add_argument("--input-csv", type=Path, required=True)
    p.add_argument(
        "--pepsysco-results",
        type=Path,
        required=True,
        help=(
            "PepSySco result CSV corresponding to the sequences exported by the notebook. "
            "The original notebook used a manual upload at this point."
        ),
    )
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()

    repo = Path(__file__).resolve().parents[2]
    nb = repo / "notebooks/05_synthesizability/05_pepsysco_synthesizability.ipynb"

    run_notebook(
        nb,
        upload_groups=[[a.input_csv], [a.pepsysco_results]],
        output_dir=a.output_dir,
    )

if __name__ == "__main__":
    main()
