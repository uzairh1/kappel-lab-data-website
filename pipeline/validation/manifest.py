import hashlib
import json
from pathlib import Path


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(root: Path) -> dict:
    files = []
    for rel in [Path('data.json'), Path('diseases.json')]:
        p = root / rel
        if p.exists():
            files.append({'path': rel.as_posix(), 'sha256': sha256_file(p), 'bytes': p.stat().st_size})
    for dirname in ('protein_details', 'tissues', 'mutations'):
        base = root / dirname
        if not base.exists():
            continue
        for p in sorted(base.rglob('*.json')):
            rel = p.relative_to(root)
            files.append({'path': rel.as_posix(), 'sha256': sha256_file(p), 'bytes': p.stat().st_size})
    return {'files': files, 'file_count': len(files)}


def write_manifest(root: Path, output: Path) -> None:
    output.write_text(json.dumps(build_manifest(root), indent=2) + '\n')
