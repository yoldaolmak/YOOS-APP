"""Minimal, private, collision-safe writes for user-derived text artifacts."""
import os
import tempfile
from pathlib import Path


def write_private_text(path: str | os.PathLike[str], content: str, *,
                       overwrite: bool = False) -> None:
    """Write UTF-8 text without exposing partial replacements.

    New files have 0600 permissions where supported. With overwrite=True a
    same-directory temporary file is replaced atomically; with overwrite=False
    exclusive creation prevents a concurrent process from replacing an output.
    """
    if not isinstance(content, str):
        raise TypeError("Private output must be text")

    target = Path(path)
    if not overwrite:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                output.write(content)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return

    descriptor, temporary = tempfile.mkstemp(
        prefix=".pennovia-", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(content)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
