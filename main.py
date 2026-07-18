"""
IDR·ATLAS REST API
===================
A real REST API over the protein metadata, with search/filter/pagination.

Architecture note on the 2TB of bulk data:
    This API serves METADATA only (small, structured — the protein records).
    The large files (imaging, sequencing, structural data) should live in
    object storage (S3 / GCS / institutional storage), NOT on this server's
    disk and NOT in the git repo. The /proteins/{uniprot}/files endpoint
    below is where you'd return signed URLs or direct links into that
    storage once it's set up — it's stubbed out with placeholder metadata
    for now so the frontend and API contract are already correct.

Run locally:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

Then visit:
    http://localhost:8000/docs   <- interactive API docs (auto-generated)
    http://localhost:8000/api/proteins
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from pydantic import BaseModel
import json
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data.json"
DISEASES_PATH = Path(__file__).parent / "diseases.json"

app = FastAPI(
    title="IDR·ATLAS API",
    description="Intrinsic disorder, sequence biophysics, and condensate membership for a curated protein set.",
    version="0.1.0-pilot",
)

# Allow the static frontend (GitHub Pages, or localhost during dev) to call this API.
# Tighten this list to your actual site's domain before going to production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # e.g. ["https://<your-username>.github.io"] in production
    allow_methods=["GET"],
    allow_headers=["*"],
)

with open(DATA_PATH) as f:
    PROTEINS: List[dict] = json.load(f)
BY_UNIPROT = {p["uniprot"]: p for p in PROTEINS}

with open(DISEASES_PATH) as f:
    DISEASES_BY_UNIPROT: dict = json.load(f)


# ---------- response models (also power the auto-generated /docs) ----------

class ProteinSummary(BaseModel):
    uniprot: str
    gene: str
    ensg: str
    dominant: Optional[bool]
    isoform_number: Optional[int]
    isoform_label: Optional[str]
    length: int
    disorder_fraction: Optional[float]
    condensate_forming: bool
    condensates: List[str]
    ppi_partner_count: int
    disease_count: int
    top_diseases: List[dict]
    variant_stats: Optional[dict]

class ProteinDetail(ProteinSummary):
    idr_count: int
    idr_total_size: int
    fold_total_size: int
    idr_ranges: List[List[int]]
    fold_ranges: List[List[int]]
    domains: List[dict]
    condensate_types: List[str]
    condensate_confidence: List[int]
    fcr: Optional[float]
    ncpr: Optional[float]
    kappa: Optional[float]
    mean_hydropathy: Optional[float]
    isoelectric_point: Optional[float]
    molecular_weight: Optional[float]
    saturation_conc_uM: Optional[float]
    delta_g_kt: Optional[float]

class PaginatedProteins(BaseModel):
    count: int
    limit: int
    offset: int
    results: List[ProteinSummary]

class DataFile(BaseModel):
    name: str
    size_estimate: str
    status: str
    url: Optional[str] = None

class DiseaseAssociation(BaseModel):
    disease_id: str
    score: float
    evidence_count: int
    datatypes: List[str]

class PaginatedDiseases(BaseModel):
    count: int
    limit: int
    offset: int
    results: List[DiseaseAssociation]

class StatsResponse(BaseModel):
    total_proteins: int
    condensate_forming: int
    distinct_condensates: int
    mean_disorder_fraction: float


# ---------------------------- endpoints ----------------------------

@app.get("/api/stats", response_model=StatsResponse, tags=["meta"])
def get_stats():
    """Summary statistics over the current pilot dataset."""
    n = len(PROTEINS)
    condensate_forming = sum(1 for p in PROTEINS if p["condensate_forming"])
    distinct = len({c for p in PROTEINS for c in p["condensates"]})
    mean_disorder = sum(p["disorder_fraction"] or 0 for p in PROTEINS) / n if n else 0
    return StatsResponse(
        total_proteins=n,
        condensate_forming=condensate_forming,
        distinct_condensates=distinct,
        mean_disorder_fraction=round(mean_disorder, 4),
    )


@app.get("/api/condensates", tags=["meta"])
def list_condensates():
    """Distinct condensates in the dataset, with member counts."""
    counts = {}
    for p in PROTEINS:
        for c in p["condensates"]:
            counts[c] = counts.get(c, 0) + 1
    return [{"name": k, "protein_count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]


@app.get("/api/proteins", response_model=PaginatedProteins, tags=["proteins"])
def list_proteins(
    q: Optional[str] = Query(None, description="Search gene symbol or UniProt ID (substring match)"),
    condensate_forming: Optional[bool] = Query(None, description="Filter to proteins with/without a reported condensate"),
    condensate: Optional[str] = Query(None, description="Filter to proteins reported in this specific condensate"),
    dominant: Optional[bool] = Query(None, description="Filter to dominant (true) or alternative (false) isoforms"),
    min_disorder: float = Query(0, ge=0, le=1, description="Minimum predicted disorder fraction (0-1)"),
    sort: str = Query("gene", description="Sort field: gene, disorder_fraction, ppi_partner_count, length"),
    order: str = Query("asc", description="asc or desc"),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List and filter proteins. This is the main search endpoint — mirrors the
    filters available in the web UI (search box, condensate filter, dominant
    filter, disorder slider) so the frontend and API stay in sync.
    """
    results = PROTEINS

    if q:
        ql = q.lower()
        results = [p for p in results if ql in p["gene"].lower() or ql in p["uniprot"].lower()]
    if condensate_forming is not None:
        results = [p for p in results if p["condensate_forming"] == condensate_forming]
    if condensate:
        results = [p for p in results if condensate in p["condensates"]]
    if dominant is not None:
        results = [p for p in results if p["dominant"] == dominant]
    if min_disorder:
        results = [p for p in results if (p["disorder_fraction"] or 0) >= min_disorder]

    valid_sorts = {"gene", "disorder_fraction", "ppi_partner_count", "length"}
    if sort not in valid_sorts:
        raise HTTPException(400, f"sort must be one of {valid_sorts}")
    reverse = order == "desc"
    results = sorted(results, key=lambda p: (p[sort] is None, p[sort]), reverse=reverse)

    total = len(results)
    page = results[offset: offset + limit]

    return PaginatedProteins(count=total, limit=limit, offset=offset, results=page)


@app.get("/api/proteins/{uniprot}", response_model=ProteinDetail, tags=["proteins"])
def get_protein(uniprot: str):
    """Full record for a single protein by UniProt ID."""
    p = BY_UNIPROT.get(uniprot.upper())
    if not p:
        raise HTTPException(404, f"No protein found with UniProt ID '{uniprot}'")
    return p


@app.get("/api/proteins/{uniprot}/files", response_model=List[DataFile], tags=["bulk-data"])
def get_protein_files(uniprot: str):
    """
    Bulk data files associated with this protein (imaging, structural, raw
    sequencing, etc). STUBBED for the pilot: once files are uploaded to
    object storage (S3/GCS/institutional server), replace the placeholder
    entries below with real signed URLs, e.g.:

        DataFile(name=..., size_estimate=..., status="available",
                 url=generate_presigned_url(bucket, key))
    """
    p = BY_UNIPROT.get(uniprot.upper())
    if not p:
        raise HTTPException(404, f"No protein found with UniProt ID '{uniprot}'")
    return [
        DataFile(name=f"{uniprot}.record.json", size_estimate="< 5 KB", status="available",
                 url=f"/api/proteins/{uniprot}"),
        DataFile(name=f"{uniprot}.fasta", size_estimate="< 2 KB", status="planned"),
        DataFile(name=f"condensate_microscopy/{uniprot}/", size_estimate="est. 40-300 GB",
                 status="planned — pending object storage setup"),
    ]


@app.get("/api/proteins/{uniprot}/diseases", response_model=PaginatedDiseases, tags=["diseases"])
def get_protein_diseases(
    uniprot: str,
    q: Optional[str] = Query(None, description="Filter by disease ID substring (e.g. 'EFO_0000' or 'MONDO')"),
    datatype: Optional[str] = Query(None, description="Filter to associations with at least this evidence type (e.g. 'genetic_association', 'literature')"),
    min_score: float = Query(0, ge=0, le=1, description="Minimum association score"),
    sort: str = Query("score", description="Sort field: score, evidence_count, disease_id"),
    order: str = Query("desc", description="asc or desc"),
    limit: int = Query(25, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Sourced from Open Targets association evidence, aggregated to one row
    per disease (max score across evidence records, summed evidence count,
    distinct contributing evidence types). Large per protein (up to ~1,400
    for some proteins here) — hence pagination/filter/sort rather than
    returning everything at once.
    """
    uid = uniprot.upper()
    if uid not in BY_UNIPROT:
        raise HTTPException(404, f"No protein found with UniProt ID '{uniprot}'")
    diseases = DISEASES_BY_UNIPROT.get(uid, [])

    if q:
        ql = q.lower()
        diseases = [d for d in diseases if ql in d["disease_id"].lower()]
    if datatype:
        diseases = [d for d in diseases if datatype in d["datatypes"]]
    if min_score:
        diseases = [d for d in diseases if d["score"] >= min_score]

    valid_sorts = {"score", "evidence_count", "disease_id"}
    if sort not in valid_sorts:
        raise HTTPException(400, f"sort must be one of {valid_sorts}")
    reverse = order == "desc"
    diseases = sorted(diseases, key=lambda d: d[sort], reverse=reverse)

    total = len(diseases)
    page = diseases[offset: offset + limit]
    return PaginatedDiseases(count=total, limit=limit, offset=offset, results=page)


@app.get("/", tags=["meta"])
def root():
    return {
        "name": "IDR·ATLAS API",
        "docs": "/docs",
        "endpoints": ["/api/stats", "/api/condensates", "/api/proteins", "/api/proteins/{uniprot}", "/api/proteins/{uniprot}/files"],
    }
