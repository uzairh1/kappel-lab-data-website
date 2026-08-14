"""Semantic comparison of generated JSON against a known-good tree."""
import json
from pathlib import Path


def _json(path: Path):
    return json.loads(path.read_text())


def compare_trees(expected_root: Path, actual_root: Path):
    expected = []
    for rel in [Path("data.json"), Path("diseases.json")]:
        if (expected_root / rel).exists():
            expected.append(rel)
    for dirname in ("protein_details", "tissues", "mutations"):
        base = expected_root / dirname
        if base.exists():
            expected.extend(sorted(p.relative_to(expected_root) for p in base.rglob("*.json")))

    mismatches = []
    missing = []
    for rel in expected:
        e = expected_root / rel
        a = actual_root / rel
        if not a.exists():
            missing.append(rel.as_posix())
            continue
        try:
            if _json(e) != _json(a):
                mismatches.append(rel.as_posix())
        except Exception:
            if e.read_bytes() != a.read_bytes():
                mismatches.append(rel.as_posix())
    return missing, mismatches


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("expected", type=Path)
    parser.add_argument("actual", type=Path)
    args = parser.parse_args()
    missing, mismatches = compare_trees(args.expected, args.actual)
    print(f"Expected JSON files checked: {len(missing) + len(mismatches) + 0}")
    print(f"Missing: {len(missing)}")
    print(f"Mismatched: {len(mismatches)}")
    if missing:
        print("Missing files:", *missing, sep="\n  ")
    if mismatches:
        print("Mismatched files:", *mismatches[:20], sep="\n  ")
    return 1 if missing or mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
