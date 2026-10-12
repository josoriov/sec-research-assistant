"""F037: the Airflow metadata URL must survive credentials with reserved chars.

Compose previously pasted the raw password into the SQLAlchemy URL, so a valid
password containing ``@`` (or ``:``, ``%``, space) broke parsing and stopped
Airflow from starting. ``metadata_url`` percent-encodes the credentials; this
checks they round-trip back to the originals.
"""
from __future__ import annotations

from urllib.parse import unquote, urlsplit

from airflow_pipeline import metadata_url


def _parts(url: str):
    split = urlsplit(url)
    return unquote(split.username), unquote(split.password), split.hostname, split.port, split.path


def test_metadata_url_encodes_reserved_password_characters():
    env = {
        "POSTGRES_USER": "sec_admin",
        "POSTGRES_PASSWORD": "p@ss:word%with space/and+plus",
    }
    user, password, host, port, path = _parts(metadata_url(env))
    assert user == "sec_admin"
    assert password == env["POSTGRES_PASSWORD"]
    assert host == "postgres"
    assert port == 5432
    assert path == "/airflow"


def test_metadata_url_defaults_and_overrides():
    assert metadata_url({"POSTGRES_USER": "u", "POSTGRES_PASSWORD": "p"}) == (
        "postgresql+psycopg2://u:p@postgres:5432/airflow"
    )
    overridden = metadata_url({
        "POSTGRES_USER": "u", "POSTGRES_PASSWORD": "p",
        "AIRFLOW_DB_HOST": "db", "AIRFLOW_DB_PORT": "5555", "AIRFLOW_DB_NAME": "meta",
    })
    assert overridden == "postgresql+psycopg2://u:p@db:5555/meta"
