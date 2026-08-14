"""Assemble a self-contained static GitHub Pages site in dist/.

This module does not rebuild scientific data. Run ``python -m pipeline.build``
first, then ``python -m pipeline.package`` to copy the current website assets
and generated JSON into a clean deployable directory.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from pipeline.config import default_paths


STATIC_FILES = (
    "index.html",
    "app.js",
    "styles.css",
    "data.json",
    "diseases.json",
)

DATA_DIRS = (
    "protein_details",
    "tissues",
    "mutations",
)

OPTIONAL_STATIC_FILES = (
    "CNAME",
    "404.html",
    "favicon.ico",
)


class PackageError(RuntimeError):
    """Raised when a deployable site cannot be assembled safely."""


def _count_files(path: Path) -> int:
    return sum(1 for item in path.rglob("*") if item.is_file())


def package_site(root: Path, *, output: Path | None = None) -> Path:
    """Create a fresh static-site bundle and return its output directory.

    Existing output is removed first so stale JSON cannot survive a package
    operation. Source website/data files are never modified.
    """
    root = Path(root).resolve()
    output = Path(output).resolve() if output else root / "dist"

    required = [root / name for name in STATIC_FILES]
    required.extend(root / name for name in DATA_DIRS)
    missing = [path for path in required if not path.exists()]
    if missing:
        formatted = "\n".join(f"  - {path}" for path in missing)
        raise PackageError(
            "Cannot package site because required build output is missing:\n"
            f"{formatted}\n"
            "Run `python -m pipeline.build` first."
        )

    # Protect against accidentally asking the packager to erase the repo.
    if output == root or root in output.parents and output.name in {"pipeline", "api"}:
        raise PackageError(f"Refusing unsafe package output directory: {output}")

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    for name in STATIC_FILES:
        shutil.copy2(root / name, output / name)

    for name in OPTIONAL_STATIC_FILES:
        source = root / name
        if source.exists():
            shutil.copy2(source, output / name)

    for name in DATA_DIRS:
        shutil.copytree(root / name, output / name)

    # GitHub Pages should serve this directory exactly as generated rather
    # than treating it as a Jekyll source tree.
    (output / ".nojekyll").write_text("", encoding="utf-8")

    print(f"Packaged static site: {output}")
    print("  website files: index.html, app.js, styles.css")
    print("  data files: data.json, diseases.json")
    for name in DATA_DIRS:
        print(f"  {name}/: {_count_files(output / name)} files")
    print(f"  total files: {_count_files(output)}")
    print("\nPreview locally with:")
    print(f"  cd {output}")
    print("  python -m http.server 8000")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Package the static website into dist/.")
    parser.add_argument("--root", type=Path, default=None, help="Repository root (default: auto-detected).")
    parser.add_argument("--output", type=Path, default=None, help="Output directory (default: <root>/dist).")
    args = parser.parse_args()

    root = args.root or default_paths().root
    try:
        package_site(root, output=args.output)
    except PackageError as exc:
        print(f"Package FAILED: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
