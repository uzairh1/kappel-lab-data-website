"""Load and verify the frozen legacy website catalog archive."""
from __future__ import annotations

import hashlib
import json
import tarfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


class LegacyCatalogError(RuntimeError):
    """Raised when the frozen snapshot is missing, altered, or incomplete."""


@dataclass
class LegacyProtein:
    """Canonical-record-compatible wrapper around a frozen legacy protein."""

    uniprot: str
    summary: dict[str, Any]
    diseases: list[dict[str, Any]]
    details: dict[str, Any]
    tissues: dict[str, Any]
    isoforms: list[dict[str, Any]]
    variant_stats: dict[str, Any] | None
    source_row: dict[str, Any]
    expanded_annotations: dict[str, Any]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_member_json(archive: tarfile.TarFile, name: str) -> Any:
    try:
        member = archive.getmember(name)
    except KeyError as exc:
        raise LegacyCatalogError(f"Legacy catalog is missing {name}") from exc
    handle = archive.extractfile(member)
    if handle is None:
        raise LegacyCatalogError(f"Legacy catalog member is not readable: {name}")
    try:
        return json.load(handle)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LegacyCatalogError(f"Invalid JSON in legacy catalog member {name}: {exc}") from exc


def _validate_members(archive: tarfile.TarFile) -> None:
    allowed_roots = {"data.json", "diseases.json", "protein_details", "tissues"}
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise LegacyCatalogError(f"Unsafe path in legacy catalog: {member.name}")
        if not path.parts or path.parts[0] not in allowed_roots:
            raise LegacyCatalogError(f"Unexpected member in legacy catalog: {member.name}")
        if not (member.isfile() or member.isdir()):
            raise LegacyCatalogError(f"Unsupported member type in legacy catalog: {member.name}")


def load_legacy_catalog(archive_path: Path, manifest_path: Path) -> list[LegacyProtein]:
    archive_path = Path(archive_path)
    manifest_path = Path(manifest_path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LegacyCatalogError(f"Could not read legacy catalog manifest: {exc}") from exc

    actual_hash = _sha256(archive_path)
    expected_hash = str(manifest.get("archive_sha256", "")).lower()
    if actual_hash != expected_hash:
        raise LegacyCatalogError(
            f"Legacy catalog SHA-256 mismatch: expected {expected_hash}, got {actual_hash}"
        )

    try:
        archive = tarfile.open(archive_path, mode="r:gz")
    except (OSError, tarfile.TarError) as exc:
        raise LegacyCatalogError(f"Could not open legacy catalog archive: {exc}") from exc

    with archive:
        _validate_members(archive)
        summaries = _read_member_json(archive, "data.json")
        diseases = _read_member_json(archive, "diseases.json")
        if not isinstance(summaries, list) or not isinstance(diseases, dict):
            raise LegacyCatalogError("Legacy data.json or diseases.json has an invalid top-level shape")

        summary_by_id = {
            item.get("uniprot"): item
            for item in summaries
            if isinstance(item, dict) and item.get("uniprot")
        }
        if len(summary_by_id) != len(summaries):
            raise LegacyCatalogError("Legacy data.json has a missing or duplicate UniProt ID")

        detail_names = {
            PurePosixPath(member.name).stem: member.name
            for member in archive.getmembers()
            if member.isfile()
            and len(PurePosixPath(member.name).parts) == 2
            and PurePosixPath(member.name).parts[0] == "protein_details"
            and PurePosixPath(member.name).suffix == ".json"
        }
        tissue_names = {
            PurePosixPath(member.name).stem: member.name
            for member in archive.getmembers()
            if member.isfile()
            and len(PurePosixPath(member.name).parts) == 2
            and PurePosixPath(member.name).parts[0] == "tissues"
            and PurePosixPath(member.name).suffix == ".json"
        }
        ids = set(summary_by_id)
        for label, available in (
            ("diseases", set(diseases)),
            ("protein details", set(detail_names)),
            ("tissues", set(tissue_names)),
        ):
            if available != ids:
                raise LegacyCatalogError(
                    f"Legacy {label} IDs differ from data.json: "
                    f"missing={sorted(ids - available)}, extra={sorted(available - ids)}"
                )

        expected_count = manifest.get("counts", {}).get("proteins")
        if len(ids) != expected_count:
            raise LegacyCatalogError(
                f"Legacy protein count mismatch: expected {expected_count}, got {len(ids)}"
            )
        id_hash = hashlib.sha256(
            "".join(f"{value}\n" for value in sorted(ids)).encode("ascii")
        ).hexdigest()
        if id_hash != manifest.get("uniprot_ids_sha256"):
            raise LegacyCatalogError("Legacy UniProt ID-set hash does not match the manifest")

        records = []
        for uniprot in sorted(ids):
            summary = deepcopy(summary_by_id[uniprot])
            detail = _read_member_json(archive, detail_names[uniprot])
            tissue = _read_member_json(archive, tissue_names[uniprot])
            if not isinstance(detail, dict) or not isinstance(tissue, dict):
                raise LegacyCatalogError(f"Legacy detail/tissue shape is invalid for {uniprot}")

            summary["catalog_source"] = "legacy_snapshot"
            summary["isoform_count"] = 0
            detail["catalog_source"] = "legacy_snapshot"
            detail.setdefault("isoforms", [])
            detail.setdefault("expanded_annotations", {})
            records.append(
                LegacyProtein(
                    uniprot=uniprot,
                    summary=summary,
                    diseases=deepcopy(diseases[uniprot]),
                    details=detail,
                    tissues=tissue,
                    isoforms=[],
                    variant_stats=summary.get("variant_stats"),
                    source_row={},
                    expanded_annotations={},
                )
            )
    return records
