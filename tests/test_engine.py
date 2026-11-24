from ledger.db.engine import _normalize_database_url


def test_postgres_url_names_the_psycopg_driver():
    neon = "postgresql://user:secret@ep-example-pooler.neon.tech/neondb?sslmode=require"
    normalized = _normalize_database_url(neon)
    assert normalized.startswith("postgresql+psycopg://")
    assert "secret" in normalized
    assert _normalize_database_url("sqlite:///./data/ledger.sqlite").startswith("sqlite:")
