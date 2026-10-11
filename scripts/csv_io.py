"""Atomic writes for pipeline artefacts (data/processed CSVs, JSON, includes, Pine).

Every artefact is written to a sibling temp file and moved into place with
os.replace(), so:

* readers never observe a partially-written file (the corr_phase -> regime
  read/write race class of bug),
* a failed or interrupted write never truncates the previous good output,
* writes survive transient open(..., "w") failures observed on external
  drives, where an in-place truncating open of an existing file can
  intermittently fail with EINVAL while fresh-file creation and rename-over
  keep working.

The temp file is removed when a write fails; a successful call leaves no
residue. All byte-level behaviour (line terminators, encoding) is identical
to the non-atomic calls this module replaces.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def _tmp_sibling(path) -> Path:
    dest = Path(path)
    return dest.with_name(dest.name + ".tmp")


def atomic_to_csv(df, path, **to_csv_kwargs):
    """df.to_csv(path, **kwargs) with write-tmp + os.replace semantics."""
    tmp = _tmp_sibling(path)
    try:
        df.to_csv(tmp, **to_csv_kwargs)
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        raise


def atomic_write_text(path, text, encoding="utf-8", errors=None, newline=None):
    """Path.write_text(text, encoding=...) with atomic replace semantics.

    The ``newline`` default (None) matches Path.write_text: open() translates
    "\\n" to the platform line ending, byte-identical to the plain call.
    """
    tmp = _tmp_sibling(path)
    try:
        with open(tmp, "w", encoding=encoding, errors=errors, newline=newline) as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        raise


def atomic_write_json(path, data, encoding="utf-8", **json_kwargs):
    """json.dump(data, f, **kwargs) to path, atomically."""
    tmp = _tmp_sibling(path)
    try:
        with open(tmp, "w", encoding=encoding) as f:
            json.dump(data, f, **json_kwargs)
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        raise
