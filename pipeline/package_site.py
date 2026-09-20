"""Assemble the compatibility-safe static website under ``build/site``.

Source files and generated data use descriptive internal paths. Packaging maps
them to the established public filenames so existing GitHub Pages URLs remain
unchanged.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from pipeline.config import default_paths


PUBLIC_FILES = {
    "frontend/index.html": "index.html",
    "frontend/application.js": "app.js",
    "frontend/styles.css": "styles.css",
    "data/generated/protein_catalog.json": "data.json",
    "data/generated/disease_associations.json": "diseases.json",
}

PUBLIC_DIRECTORIES = {
    "data/generated/protein_details": "protein_details",
    "data/generated/tissue_expression": "tissues",
    "data/generated/mutations": "mutations",
}

OPTIONAL_PUBLIC_FILES = ("CNAME", "404.html", "favicon.ico")


class PackageError(RuntimeError):
    """Raised when a deployable site cannot be assembled safely."""


def _count_files(path: Path) -> int:
    return sum(1 for item in path.rglob("*") if item.is_file())


def package_site(root: Path, *, output: Path | None = None) -> Path:
    """Create a fresh static-site bundle and return its output directory."""
    root = Path(root).resolve()
    output = Path(output).resolve() if output else root / "build" / "site"

    required = [root / source for source in (*PUBLIC_FILES, *PUBLIC_DIRECTORIES)]
    missing = [path for path in required if not path.exists()]
    if missing:
        formatted = "\n".join(f"  - {path}" for path in missing)
        raise PackageError(
            "Cannot package site because required source or generated data is missing:\n"
            f"{formatted}\n"
            "Run `python -m pipeline.build` first."
        )

    protected_directories = {
        root / "api",
        root / "data",
        root / "database",
        root / "docs",
        root / "frontend",
        root / "pipeline",
        root / "scripts",
    }
    if output == root or any(
        protected == output or protected in output.parents
        for protected in protected_directories
    ):
        raise PackageError(f"Refusing unsafe package output directory: {output}")

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    for source_name, public_name in PUBLIC_FILES.items():
        source = root / source_name
        destination = output / public_name
        if source_name == "frontend/index.html":
            # The source tree uses the descriptive application.js name. Keep
            # the established public app.js URL in deployable packages.
            html = source.read_text(encoding="utf-8")
            destination.write_text(
                html.replace('src="application.js"', 'src="app.js"'),
                encoding="utf-8",
            )
        else:
            shutil.copy2(source, destination)

    for name in OPTIONAL_PUBLIC_FILES:
        source = root / name
        if source.exists():
            shutil.copy2(source, output / name)

    for source_name, public_name in PUBLIC_DIRECTORIES.items():
        shutil.copytree(root / source_name, output / public_name)

    (output / ".nojekyll").write_text("", encoding="utf-8")

    print(f"Packaged static site: {output}")
    print("  website files: index.html, app.js, styles.css")
    print("  data files: data.json, diseases.json")
    for public_name in PUBLIC_DIRECTORIES.values():
        print(f"  {public_name}/: {_count_files(output / public_name)} files")
    print(f"  total files: {_count_files(output)}")
    print("\nPreview locally with:")
    print(f"  cd {output}")
    print("  python -m http.server 8000")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Package the static website into build/site/."
    )
    parser.add_argument(
        "--root", type=Path, default=None,
        help="Repository root (default: auto-detected).",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output directory (default: <root>/build/site).",
    )
    args = parser.parse_args()

    root = args.root or default_paths().root
    try:
        package_site(root, output=args.output)
    except PackageError as exc:
        print(f"Package FAILED: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
