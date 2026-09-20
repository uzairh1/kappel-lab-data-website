"""Apply a SQL migration using DATABASE_URL and psycopg2; no psql required."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Apply one PostgreSQL migration file.")
    parser.add_argument(
        "migration",
        nargs="?",
        type=Path,
        default=root / "migrations" / "001_combined_catalog.sql",
    )
    args = parser.parse_args()

    try:
        import psycopg2
    except ImportError:
        print(
            "ERROR: psycopg2 is not installed. Run "
            "`python -m pip install -r api/requirements.txt` first."
        )
        return 1

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL is not set. Add it to .env or the current shell.")
        return 1

    migration = args.migration.resolve()
    if not migration.is_file():
        print(f"ERROR: Migration file not found: {migration}")
        return 1
    sql = migration.read_text(encoding="utf-8")
    if not sql.strip():
        print(f"ERROR: Migration file is empty: {migration}")
        return 1

    try:
        with psycopg2.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
    except psycopg2.Error as exc:
        print(f"Migration FAILED; PostgreSQL rolled back the transaction: {exc}")
        return 1

    print(f"Migration applied successfully: {migration}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
