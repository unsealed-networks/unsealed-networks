"""Safe file I/O utilities with atomic writes."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any


def atomic_write(
    path: Path | str,
    write_func: Callable[[Path], None],
) -> None:
    """Atomically write a file using write-then-rename pattern.

    Args:
        path: Destination file path
        write_func: Function that takes a Path and writes content to it

    The write_func should write to the provided path. This function handles
    the temporary file creation and atomic rename.

    Example:
        def write_content(p: Path):
            with open(p, 'w') as f:
                f.write("data")

        atomic_write(Path("output.txt"), write_content)
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temporary file first
    tmp_path = path.with_suffix(path.suffix + ".tmp")

    try:
        write_func(tmp_path)
        # Atomically replace the old file with the new one
        tmp_path.replace(path)
    except Exception:
        # Clean up temp file if write failed
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def atomic_write_json(
    path: Path | str,
    data: Any,
    indent: int = 2,
    **json_kwargs: Any,
) -> None:
    """Atomically write JSON data to a file.

    Args:
        path: Destination file path
        data: Data to serialize as JSON
        indent: JSON indentation (default: 2)
        **json_kwargs: Additional arguments for json.dump()

    Example:
        atomic_write_json("output.json", {"key": "value"})
    """

    def write_json(tmp_path: Path) -> None:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, **json_kwargs)

    atomic_write(path, write_json)
