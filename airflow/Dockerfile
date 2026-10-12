# Airflow runtime for the T007 pipeline.
#
# Built from the official image so the metadata database, entrypoint, CLI, and
# provider versions stay supported. The repo's own pipeline dependencies (the
# same requirements.txt the app service installs) and dbt-postgres are added on
# top; the repo itself is mounted at runtime, not baked in.
FROM docker.io/apache/airflow:3.3.2-python3.12

USER airflow

COPY requirements.txt /tmp/repo-requirements.txt
COPY requirements-cpu.txt /tmp/requirements-cpu.txt
COPY airflow/requirements.txt /tmp/airflow-requirements.txt
# Fetch only torch from the CPU index; resolve all other packages from PyPI.
RUN python -m pip install --no-cache-dir --no-deps \
      --index-url https://download.pytorch.org/whl/cpu \
      -r /tmp/requirements-cpu.txt \
    && python -m pip install --no-cache-dir \
      "apache-airflow==${AIRFLOW_VERSION}" \
      -r /tmp/airflow-requirements.txt \
      -r /tmp/repo-requirements.txt \
    && python -m pip check

# Wrapper that builds the metadata URL with URL-encoded credentials for every
# `airflow` invocation (compose puts it first on PATH; see compose.yaml).
COPY --chown=airflow:root airflow/bin/airflow /opt/airflow/bin/airflow
RUN chmod +x /opt/airflow/bin/airflow
