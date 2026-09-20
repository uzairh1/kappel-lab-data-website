-- Idempotent migration for the combined legacy + expanded catalog.
-- Apply this once before the first authoritative ingestion.
BEGIN;

ALTER TABLE proteins
    ADD COLUMN IF NOT EXISTS isoform_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE proteins
    ADD COLUMN IF NOT EXISTS catalog_source TEXT NOT NULL DEFAULT 'legacy_snapshot';

ALTER TABLE tissue_expression
    ADD COLUMN IF NOT EXISTS protein_cell_type_details JSONB NOT NULL DEFAULT '[]'::jsonb;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'proteins_catalog_source_check'
          AND conrelid = 'proteins'::regclass
    ) THEN
        ALTER TABLE proteins
            ADD CONSTRAINT proteins_catalog_source_check
            CHECK (catalog_source IN ('legacy_snapshot', 'expanded_dataset'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS protein_isoforms (
    dataset_isoform_id   TEXT PRIMARY KEY,
    uniprot              TEXT NOT NULL REFERENCES proteins(uniprot) ON DELETE CASCADE,
    dominant             BOOLEAN NOT NULL,
    row_kind             TEXT NOT NULL,
    length               INTEGER NOT NULL,
    sequence_sha256      TEXT,
    sequence_source      TEXT,
    identifiers          JSONB NOT NULL DEFAULT '{}'::jsonb,
    expanded_annotations JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_protein_isoforms_uniprot
    ON protein_isoforms (uniprot);
CREATE INDEX IF NOT EXISTS idx_protein_isoforms_dominant
    ON protein_isoforms (uniprot, dominant);

COMMIT;
