-- schema.sql
-- Core schema for the Kappel Lab Data Website at 20K-protein scale.
-- Run once against the Supabase Postgres instance to set up tables.
--
-- Design notes:
--   - proteins / diseases / variants mirror the generated website data in
--     queryable Postgres tables so the API can filter across proteins.
--   - Selected detail data used for cross-protein filters is normalized into
--     condensate_details, ppi_partners, idr_segments, go_terms, and
--     tissue_expression. Full classification history remains JSONB where it
--     is normally fetched as a whole.
--   - Full per-protein detail and per-isoform mutation JSON files are not
--     stored as database blobs. They remain part of the static site today.
--     r2_details_key is reserved for a possible future R2-backed detail path
--     and is currently left NULL by ingestion.

CREATE TABLE proteins (
    uniprot         TEXT PRIMARY KEY,
    gene            TEXT NOT NULL,
    ensg            TEXT,
    dominant        BOOLEAN,
    isoform_number  INTEGER,
    isoform_label   TEXT,
    length          INTEGER,

    -- IDR / domain summary (from data.json)
    idr_count       INTEGER,
    idr_total_size  INTEGER,
    fold_total_size INTEGER,
    disorder_fraction REAL,
    idr_ranges      JSONB,
    fold_ranges     JSONB,
    domains         JSONB,

    -- condensate summary
    condensates             TEXT[],
    condensate_types        TEXT[],
    condensate_confidence   INTEGER[],
    condensate_forming      BOOLEAN,

    -- biophysics summary (the small set already in data.json, not the
    -- full protein_details breakdown -- that stays in R2)
    fcr                 REAL,
    ncpr                REAL,
    kappa               REAL,
    mean_hydropathy     REAL,
    isoelectric_point   REAL,
    molecular_weight    REAL,
    saturation_conc_uM  REAL,
    delta_g_kt          REAL,

    ppi_partner_count   INTEGER,
    disease_count       INTEGER,
    variant_stats       JSONB,  -- the RBP/variant summary block, kept as-is

    -- pointer to the full deep-dive file in R2 (protein_details/{uniprot}.json)
    r2_details_key      TEXT,

    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

-- indexes for the filters the browse table actually uses
CREATE INDEX idx_proteins_gene ON proteins (gene);
CREATE INDEX idx_proteins_condensate_forming ON proteins (condensate_forming);
CREATE INDEX idx_proteins_disease_count ON proteins (disease_count DESC);
CREATE INDEX idx_proteins_condensates_gin ON proteins USING GIN (condensates);


CREATE TABLE diseases (
    id              BIGSERIAL PRIMARY KEY,
    uniprot         TEXT NOT NULL REFERENCES proteins(uniprot) ON DELETE CASCADE,
    disease_id      TEXT NOT NULL,       -- EFO/MONDO code
    score           REAL,
    evidence_count  INTEGER,
    datatypes       TEXT[]
);

CREATE INDEX idx_diseases_uniprot ON diseases (uniprot);
CREATE INDEX idx_diseases_score ON diseases (score DESC);
CREATE INDEX idx_diseases_disease_id ON diseases (disease_id);


CREATE TABLE variants (
    id                      BIGSERIAL PRIMARY KEY,
    uniprot                 TEXT NOT NULL REFERENCES proteins(uniprot) ON DELETE CASCADE,
    isoform_id              TEXT NOT NULL,        -- GeneIsoform (RefSeq NP accession)
    variation_id            TEXT NOT NULL,         -- ClinVar VariationID
    isoform_dominant        BOOLEAN,
    isoform_length          INTEGER,
    isoform_length_mismatch BOOLEAN,               -- flags the O95319-style disagreement, per the locked decision to surface not resolve

    position_start          INTEGER,
    position_end             INTEGER,
    is_range                BOOLEAN,
    mutated_from            TEXT,
    mutated_to               TEXT,
    molecular_consequence   TEXT,
    variant_type            TEXT,
    mutation_type            TEXT,

    primary_classification  TEXT,   -- worst-case, drives the marker color
    primary_condition       TEXT,   -- from the same worst-case entry, drives marker shape
    all_classifications      JSONB,  -- full multi-submitter history, fetched whole for the detail panel
    n_collapsed_rows        INTEGER
);

CREATE INDEX idx_variants_uniprot_isoform ON variants (uniprot, isoform_id);
CREATE INDEX idx_variants_classification ON variants (primary_classification);
CREATE INDEX idx_variants_position ON variants (uniprot, isoform_id, position_start);


-- Everything below supports filtering the browse table by data that used
-- to only live in lazy-loaded per-protein files (protein_details/,
-- mutations/) -- the whole point of moving to Postgres: real indexed
-- queries across this, instead of eagerly loading everything into every
-- browser just to filter on it.

CREATE TABLE condensate_details (
    id                  BIGSERIAL PRIMARY KEY,
    uniprot             TEXT NOT NULL REFERENCES proteins(uniprot) ON DELETE CASCADE,
    condensate_name     TEXT,
    condensate_type     TEXT,
    confidence          INTEGER,
    species_tax_id      TEXT,
    dna_associated      TEXT,
    rna_associated      TEXT,
    chemical_mods       TEXT,
    condensatopathy     TEXT
);
CREATE INDEX idx_condensate_details_uniprot ON condensate_details (uniprot);
CREATE INDEX idx_condensate_details_name ON condensate_details (condensate_name);
CREATE INDEX idx_condensate_details_condensatopathy ON condensate_details (condensatopathy);

CREATE TABLE ppi_partners (
    id                  BIGSERIAL PRIMARY KEY,
    uniprot             TEXT NOT NULL REFERENCES proteins(uniprot) ON DELETE CASCADE,
    partner_uniprot     TEXT NOT NULL,
    score               REAL,
    partner_in_pilot_set BOOLEAN  -- true if partner_uniprot is also one of our 101 proteins
);
CREATE INDEX idx_ppi_partners_uniprot ON ppi_partners (uniprot);
CREATE INDEX idx_ppi_partners_partner ON ppi_partners (partner_uniprot);
CREATE INDEX idx_ppi_partners_score ON ppi_partners (score DESC);

CREATE TABLE idr_segments (
    id                          BIGSERIAL PRIMARY KEY,
    uniprot                     TEXT NOT NULL REFERENCES proteins(uniprot) ON DELETE CASCADE,
    segment_index               INTEGER,  -- 1-based, matches the "IDR 1", "IDR 2" labeling on the site
    start_pos                   INTEGER,
    end_pos                     INTEGER,
    size                        INTEGER,
    fcr REAL, ncpr REAL, kappa REAL, delta REAL, delta_max REAL,
    isoelectric_point REAL, molecular_weight REAL,
    mean_net_charge REAL, mean_hydropathy REAL, uversky_hydropathy REAL, ppii_propensity REAL,
    fraction_negative REAL, fraction_positive REAL, fraction_expanding REAL, fraction_disorder_promoting REAL
);
CREATE INDEX idx_idr_segments_uniprot ON idr_segments (uniprot);
CREATE INDEX idx_idr_segments_kappa ON idr_segments (kappa);
CREATE INDEX idx_idr_segments_fcr ON idr_segments (fcr);
CREATE INDEX idx_idr_segments_size ON idr_segments (size);

CREATE TABLE go_terms (
    id              BIGSERIAL PRIMARY KEY,
    uniprot         TEXT NOT NULL REFERENCES proteins(uniprot) ON DELETE CASCADE,
    aspect          TEXT,  -- 'cellular_component' | 'biological_process' | 'molecular_function'
    go_id           TEXT,
    description     TEXT,
    evidence        TEXT
);
CREATE INDEX idx_go_terms_uniprot ON go_terms (uniprot);
CREATE INDEX idx_go_terms_description ON go_terms (description);
CREATE INDEX idx_go_terms_aspect ON go_terms (aspect);

CREATE TABLE tissue_expression (
    id                      BIGSERIAL PRIMARY KEY,
    uniprot                 TEXT NOT NULL REFERENCES proteins(uniprot) ON DELETE CASCADE,
    label                   TEXT,
    efo_code                TEXT,
    organs                  TEXT[],
    anatomical_systems      TEXT[],
    rna_value               REAL,
    rna_zscore              REAL,
    rna_level               INTEGER,
    protein_reliability     BOOLEAN,
    protein_level           INTEGER,
    protein_cell_types      TEXT[]
);
CREATE INDEX idx_tissue_expression_uniprot ON tissue_expression (uniprot);
CREATE INDEX idx_tissue_expression_label ON tissue_expression (label);
CREATE INDEX idx_tissue_expression_rna_value ON tissue_expression (rna_value DESC);
CREATE INDEX idx_tissue_expression_organs_gin ON tissue_expression USING GIN (organs);
