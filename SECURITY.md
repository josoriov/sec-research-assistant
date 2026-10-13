# Security

This is a local development and portfolio application. The Compose services bind
to `127.0.0.1`. Keep Airflow, PostgreSQL, and MinIO private; the API currently has
no authentication, request quotas, or LLM spending controls for a public service.

The API image runs as a non-root user with a read-only filesystem and temporary
model cache. It has no checkout mount, pipeline password, or MinIO credentials.
Its database connection uses the gold-only role. Pipeline credentials remain in
the Airflow service, which runs the preparation commands.

Keep secrets in the ignored `.env`, restrict it with `chmod 600 .env`, and never
attach it or container environment dumps to issues. `.env.*` variants are also
ignored; `.env.example` contains placeholders only. If a credential is exposed,
revoke or rotate it before removing it from files or Git history.

CI scans Git history with Gitleaks and audits the pinned Python dependencies.
These checks do not prove that a deployment is secure or that credentials have
never been misused. Dependency upgrades should also exercise the real encoder,
check the Airflow image, and preserve the model/dimension contract in dbt.

Report suspected vulnerabilities privately through the repository's GitHub
Security advisories page when enabled. If private reporting is unavailable,
contact the maintainer through their GitHub profile without posting exploit
details, credentials, or private data in a public issue.
