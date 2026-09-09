#!/usr/bin/env python3
"""
Internal helper for executing the original PersiPep Colab notebooks headlessly.

The scientific code remains in the version-controlled notebooks. This helper:
- removes Colab-only `!pip` cells;
- replaces google.colab.files.upload() with explicit CLI-supplied files;
- turns files.download() into a no-op;
- redirects `/content/...` outputs to a caller-supplied output directory.

It intentionally does not alter scoring formulas, thresholds, ranking logic,
or model settings in the notebooks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import nbformat
from nbclient import NotebookClient


def _helper_cell(upload_groups: list[list[str]]) -> str:
    groups_json = json.dumps(upload_groups)
    return f"""
from pathlib import Path as _PersiPepPath

_PERSIPEP_UPLOAD_GROUPS = {groups_json}
_PERSIPEP_UPLOAD_INDEX = 0

def _persipep_upload():
    global _PERSIPEP_UPLOAD_INDEX
    if _PERSIPEP_UPLOAD_INDEX >= len(_PERSIPEP_UPLOAD_GROUPS):
        raise RuntimeError(
            "Notebook requested more upload groups than were supplied by the CLI wrapper."
        )

    paths = _PERSIPEP_UPLOAD_GROUPS[_PERSIPEP_UPLOAD_INDEX]
    _PERSIPEP_UPLOAD_INDEX += 1

    payload = {{}}
    for raw in paths:
        p = _PersiPepPath(raw).resolve()
        if not p.is_file():
            raise FileNotFoundError(p)
        payload[p.name] = p.read_bytes()

    print("CLI upload group:", [str(_PersiPepPath(x).resolve()) for x in paths])
    return payload

def _persipep_download(path):
    print("Notebook download request retained on disk:", path)
    return None
"""


def _transform_source(source: str, output_dir: Path) -> str:
    lines = []
    for line in source.splitlines():
        stripped = line.lstrip()

        # Dependency installation belongs in the reproducible environment,
        # not inside the scientific notebook execution.
        if stripped.startswith("!pip ") or stripped.startswith("%pip "):
            lines.append("# [PersiPep CLI] Colab pip install removed; use project environment.")
            continue

        if stripped.startswith("from google.colab import files"):
            lines.append("# [PersiPep CLI] google.colab.files replaced by CLI helpers.")
            continue

        lines.append(line)

    source = "\n".join(lines)
    source = source.replace("files.upload()", "_persipep_upload()")
    source = source.replace("files.download(", "_persipep_download(")

    # Redirect Colab's fixed workspace to the stage output directory.
    content_prefix = output_dir.resolve().as_posix().rstrip("/") + "/"
    source = source.replace("/content/", content_prefix)

    return source


def run_notebook(
    notebook_path: Path,
    upload_groups: Iterable[Iterable[Path]],
    output_dir: Path,
    timeout: int = 86400,
) -> None:
    notebook_path = notebook_path.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not notebook_path.is_file():
        raise FileNotFoundError(notebook_path)

    normalized_groups: list[list[str]] = []
    for group in upload_groups:
        normalized = []
        for p in group:
            p = Path(p).resolve()
            if not p.is_file():
                raise FileNotFoundError(p)
            normalized.append(str(p))
        normalized_groups.append(normalized)

    nb = nbformat.read(notebook_path, as_version=4)

    helper = nbformat.v4.new_code_cell(_helper_cell(normalized_groups))
    transformed_cells = [helper]

    for cell in nb.cells:
        if cell.cell_type == "code":
            cell.source = _transform_source(cell.source, output_dir)
        transformed_cells.append(cell)

    nb.cells = transformed_cells

    print(f"Executing notebook: {notebook_path}")
    print(f"Output directory:   {output_dir}")

    client = NotebookClient(
        nb,
        timeout=timeout,
        kernel_name="python3",
        allow_errors=False,
        resources={"metadata": {"path": str(notebook_path.parent)}},
    )
    client.execute(cwd=str(notebook_path.parent))

    executed = output_dir / f"{notebook_path.stem}__executed.ipynb"
    nbformat.write(nb, executed)
    print(f"Executed notebook record: {executed}")
