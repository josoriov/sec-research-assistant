"""Read-only PostgreSQL connection for the questions API (gold role only).

Uses GOLD_API_DB_USER/GOLD_API_DB_PASSWORD, which `db/init/01-init.sh` grants
read access to `gold` and denies to `bronze`/`silver`. Enforcing the restricted
role at the database (not only in the application) is what keeps the API on
published gold datasets.
"""
from __future__ import annotations

import os

import psycopg


def connect():
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        # The Compose app sets PGDATABASE; a shell sourcing .env has POSTGRES_DB.
        dbname=os.environ.get("PGDATABASE") or os.environ["POSTGRES_DB"],
        user=os.environ["GOLD_API_DB_USER"],
        password=os.environ["GOLD_API_DB_PASSWORD"],
    )
