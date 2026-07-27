"""
Kappel Lab Data Website REST API
===================
Queries Postgres directly -- this replaces the earlier version that loaded
data.json into memory. That worked fine for a 101-protein static demo, but
couldn't support real cross-table filtering (by IDR segment kappa, PPI
partner, condensate name, GO term, etc.) without eagerly loading every
protein's full detail into every request -- exactly the problem the
Postgres migration exists to solve.

R2 note (still fully separate, still on hold): this API serves METADATA
from Postgres. The big per-protein detail/mutation files stay wherever
they currently live (git/GitHub Pages for now) -- this file doesn't touch
that at all. See ingest_to_postgres.py's docstring for the same note.

Setup:
    export DATABASE_URL="postgresql://user:password@host:port/dbname"
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

Then visit:
    http://localhost:8000/docs
"""

import os
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from pydantic import BaseModel
import psycopg2
import psycopg2.extras

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable not set -- see this file's docstring.")

def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn

app = FastAPI(
    title="Kappel Lab Data Website API",
    description="Intrinsic disorder, sequence biophysics, and condensate membership for a curated protein set -- backed by Postgres.",
    version="0.2.0-postgres",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the real site's domain before production
    allow_methods=["GET"],
    allow_headers=["*"],
)

# numeric fields on the proteins table that support min_/max_ query params --
# same 14 fields as the frontend's "Metric filters" dropdown, kept in sync
# deliberately so the API and UI offer the same filtering surface
NUMERIC_FIELDS = [
    "length", "idr_count", "idr_total_size", "fold_total_size", "ppi_partner_count",
    "fcr", "ncpr", "kappa", "mean_hydropathy", "isoelectric_point", "molecular_weight",
    "saturation_conc_uM", "delta_g_kt", "disease_count",
]


# ---------- response models ----------

class ProteinSummary(BaseModel):
    uniprot: str
    gene: str
    ensg: Optional[str]
    dominant: Optional[bool]
    isoform_number: Optional[int]
    isoform_label: Optional[str]
    length: Optional[int]
    condensate_forming: Optional[bool]
    condensates: Optional[List[str]]
    ppi_partner_count: Optional[int]
    disease_count: Optional[int]

class PaginatedProteins(BaseModel):
    count: int
    limit: int
    offset: int
    results: List[dict]

class StatsResponse(BaseModel):
    total_proteins: int
    condensate_forming: int
    distinct_condensates: int


# ---------------------------- endpoints ----------------------------

@app.get("/api/stats", response_model=StatsResponse, tags=["meta"])
def get_stats():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT count(*) AS n, count(*) FILTER (WHERE condensate_forming) AS forming FROM proteins")
    row = cur.fetchone()
    cur.execute("SELECT count(DISTINCT condensate_name) AS n FROM condensate_details")
    distinct = cur.fetchone()["n"]
    conn.close()
    return StatsResponse(total_proteins=row["n"], condensate_forming=row["forming"], distinct_condensates=distinct)


@app.get("/api/condensates", tags=["meta"])
def list_condensates():
    """Distinct condensates, with member counts -- now from the real condensate_details table."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT condensate_name AS name, count(DISTINCT uniprot) AS protein_count
        FROM condensate_details WHERE condensate_name IS NOT NULL
        GROUP BY condensate_name ORDER BY protein_count DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


@app.get("/api/proteins", response_model=PaginatedProteins, tags=["proteins"])
def list_proteins(
    request: Request,
    q: Optional[str] = Query(None, description="Search gene symbol or UniProt ID (substring match)"),
    condensate_forming: Optional[bool] = Query(None),
    condensate: Optional[str] = Query(None, description="Filter to proteins reported in this specific condensate"),
    condensatopathy: Optional[str] = Query(None, description="Filter by condensatopathy flag on any of the protein's condensates (e.g. 'Yes')"),
    dominant: Optional[bool] = Query(None),
    ppi_partner: Optional[str] = Query(None, description="Filter to proteins that interact with this UniProt ID"),
    go_term: Optional[str] = Query(None, description="Substring search across GO term descriptions"),
    min_idr_kappa: Optional[float] = Query(None, description="Filter to proteins with at least one IDR segment above this kappa"),
    max_idr_kappa: Optional[float] = Query(None),
    sort: str = Query("gene", description="gene, disease_count, ppi_partner_count, length, or any NUMERIC_FIELDS entry"),
    order: str = Query("asc"),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Main search/filter endpoint. Supports:
      - text search, condensate-forming, specific condensate, dominant isoform (as before)
      - min_<field>/max_<field> for any of NUMERIC_FIELDS (e.g. ?min_kappa=0.3&max_kappa=0.5) --
        these aren't declared as explicit params since there are 28 of them;
        read directly from request.query_params instead (FastAPI has no
        native **kwargs support for arbitrary query params -- confirmed by
        testing, not assumed: an earlier version of this used **kwargs in
        the signature and FastAPI treated it as a single required param
        named "numeric_range_kwargs", a 422 on every request)
      - condensatopathy, ppi_partner, go_term, min/max_idr_kappa -- cross-table filters
        that used to be impossible without loading every protein's full detail
    """
    conn = get_conn()
    cur = conn.cursor()

    where, params = ["1=1"], []

    if q:
        where.append("(LOWER(gene) LIKE %s OR LOWER(uniprot) LIKE %s)")
        params += [f"%{q.lower()}%", f"%{q.lower()}%"]
    if condensate_forming is not None:
        where.append("condensate_forming = %s"); params.append(condensate_forming)
    if condensate:
        where.append("%s = ANY(condensates)"); params.append(condensate)
    if dominant is not None:
        where.append("dominant = %s"); params.append(dominant)

    for field in NUMERIC_FIELDS:
        min_val = request.query_params.get(f"min_{field}")
        max_val = request.query_params.get(f"max_{field}")
        if min_val is not None:
            where.append(f"{field} >= %s"); params.append(float(min_val))
        if max_val is not None:
            where.append(f"{field} <= %s"); params.append(float(max_val))

    if condensatopathy:
        where.append("EXISTS (SELECT 1 FROM condensate_details cd WHERE cd.uniprot = proteins.uniprot AND cd.condensatopathy = %s)")
        params.append(condensatopathy)
    if ppi_partner:
        where.append("EXISTS (SELECT 1 FROM ppi_partners pp WHERE pp.uniprot = proteins.uniprot AND pp.partner_uniprot = %s)")
        params.append(ppi_partner.upper())
    if go_term:
        where.append("EXISTS (SELECT 1 FROM go_terms g WHERE g.uniprot = proteins.uniprot AND LOWER(g.description) LIKE %s)")
        params.append(f"%{go_term.lower()}%")
    if min_idr_kappa is not None:
        where.append("EXISTS (SELECT 1 FROM idr_segments s WHERE s.uniprot = proteins.uniprot AND s.kappa >= %s)")
        params.append(min_idr_kappa)
    if max_idr_kappa is not None:
        where.append("EXISTS (SELECT 1 FROM idr_segments s WHERE s.uniprot = proteins.uniprot AND s.kappa <= %s)")
        params.append(max_idr_kappa)

    valid_sorts = {"gene", "disease_count", "ppi_partner_count", "length"} | set(NUMERIC_FIELDS)
    if sort not in valid_sorts:
        conn.close()
        raise HTTPException(400, f"sort must be one of {sorted(valid_sorts)}")
    order_sql = "DESC" if order == "desc" else "ASC"

    where_sql = " AND ".join(where)
    cur.execute(f"SELECT count(*) AS n FROM proteins WHERE {where_sql}", params)
    total = cur.fetchone()["n"]

    cur.execute(
        f"SELECT * FROM proteins WHERE {where_sql} ORDER BY {sort} {order_sql} NULLS LAST LIMIT %s OFFSET %s",
        params + [limit, offset],
    )
    rows = cur.fetchall()
    conn.close()
    return PaginatedProteins(count=total, limit=limit, offset=offset, results=rows)


@app.get("/api/proteins/{uniprot}", tags=["proteins"])
def get_protein(uniprot: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM proteins WHERE uniprot = %s", (uniprot.upper(),))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, f"No protein found with UniProt ID '{uniprot}'")
    conn.close()
    return row


@app.get("/api/proteins/{uniprot}/diseases", tags=["diseases"])
def get_protein_diseases(
    uniprot: str,
    q: Optional[str] = Query(None),
    min_score: float = Query(0, ge=0, le=1),
    sort: str = Query("score", description="score, evidence_count, or disease_id"),
    order: str = Query("desc"),
    limit: int = Query(25, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM proteins WHERE uniprot = %s", (uniprot.upper(),))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(404, f"No protein found with UniProt ID '{uniprot}'")

    where, params = ["uniprot = %s"], [uniprot.upper()]
    if q:
        where.append("LOWER(disease_id) LIKE %s"); params.append(f"%{q.lower()}%")
    if min_score:
        where.append("score >= %s"); params.append(min_score)

    valid_sorts = {"score", "evidence_count", "disease_id"}
    if sort not in valid_sorts:
        conn.close()
        raise HTTPException(400, f"sort must be one of {valid_sorts}")
    order_sql = "DESC" if order == "desc" else "ASC"
    where_sql = " AND ".join(where)

    cur.execute(f"SELECT count(*) AS n FROM diseases WHERE {where_sql}", params)
    total = cur.fetchone()["n"]
    cur.execute(f"SELECT * FROM diseases WHERE {where_sql} ORDER BY {sort} {order_sql} LIMIT %s OFFSET %s",
                params + [limit, offset])
    rows = cur.fetchall()
    conn.close()
    return {"count": total, "limit": limit, "offset": offset, "results": rows}


@app.get("/api/proteins/{uniprot}/ppi", tags=["interactions"])
def get_protein_ppi(uniprot: str, limit: int = Query(50, ge=1, le=1000)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT partner_uniprot, score, partner_in_pilot_set FROM ppi_partners WHERE uniprot = %s ORDER BY score DESC LIMIT %s",
                (uniprot.upper(), limit))
    rows = cur.fetchall()
    conn.close()
    return rows


@app.get("/api/proteins/{uniprot}/idr-segments", tags=["biophysics"])
def get_protein_idr_segments(uniprot: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM idr_segments WHERE uniprot = %s ORDER BY segment_index", (uniprot.upper(),))
    rows = cur.fetchall()
    conn.close()
    return rows


@app.get("/", tags=["meta"])
def root():
    return {
        "name": "Kappel Lab Data Website API",
        "docs": "/docs",
        "endpoints": ["/api/stats", "/api/condensates", "/api/proteins", "/api/proteins/{uniprot}",
                      "/api/proteins/{uniprot}/diseases", "/api/proteins/{uniprot}/ppi", "/api/proteins/{uniprot}/idr-segments"],
    }