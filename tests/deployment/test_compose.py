"""The local API must not inherit the preparation environment's authority."""
from pathlib import Path

import yaml


def test_local_ports_and_api_isolation():
    root = Path(__file__).resolve().parents[2]
    services = yaml.safe_load((root / "compose.yaml").read_text())["services"]
    for service in services.values():
        assert all(port.startswith("127.0.0.1:") for port in service.get("ports", []))
    app = services["app"]
    assert app["read_only"] is True
    assert not app.get("volumes")
    assert app["cap_drop"] == ["ALL"]
    assert app["security_opt"] == ["no-new-privileges:true"]
    assert not any(key.startswith(("PIPELINE_", "MINIO_", "POSTGRES_"))
                   for key in app["environment"])
    assert "GOLD_API_DB_PASSWORD" in app["environment"]
    assert "MINIO_ROOT_PASSWORD" in services["airflow"]["environment"]


def test_environment_variants_are_ignored(tmp_path):
    import subprocess

    root = Path(__file__).resolve().parents[2]
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text((root / ".gitignore").read_text())
    for name in (".env", ".env.local", ".env.production", ".env.backup"):
        assert subprocess.run(["git", "check-ignore", "-q", name],
                              cwd=tmp_path).returncode == 0
    assert subprocess.run(["git", "check-ignore", "-q", ".env.example"],
                          cwd=tmp_path).returncode == 1
