# Kappel Lab Data Website

A full-stack web application for organizing and accessing large-scale bioinformatics datasets for researchers in the UCLA Kappel Lab.

## Features

- Organize and browse experimental datasets
- Search dataset metadata
- Backend support for researcher data management
- Full-stack architecture for scientific data access

## Tech Stack

- JavaScript
- PostgreSQL
- HTML/CSS
- Python / Pandas / Jupyter Notebook (data processing)

## Repository Structure

```
app.js                 Main server
main.py                Main app
ingest_to_postgres.py  Database ingestion
data_prep_scripts/     Dataset preprocessing
check_scripts          Check processed data against raw internal data
mutations/             Per-protein mutation data per protein, loaded for one isoform at a time
protein_details/       Per protein metadata, loaded for one protein at a time
data.json              Powers browse table, search, and filters
diseases.json          Full disease association list for all proteins, loaded on demand
```

## Status

This project is under active development as part of the UCLA Kappel Lab.

## License

Research software. Not intended for clinical or commercial use.
