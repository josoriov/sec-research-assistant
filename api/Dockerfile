FROM docker.io/library/python:3.12-slim

WORKDIR /app
COPY requirements-cpu.txt requirements.lock ./
RUN python -m pip install --no-cache-dir --no-deps \
      --index-url https://download.pytorch.org/whl/cpu -r requirements-cpu.txt \
    && python -m pip install --no-cache-dir -r requirements.lock \
    && python -m pip check

COPY api ./api
COPY sql ./sql
COPY embeddings ./embeddings
COPY extraction ./extraction
COPY ingestion ./ingestion

ENV PYTHONDONTWRITEBYTECODE=1 HF_HOME=/tmp/huggingface
USER 10001:10001
CMD ["python", "-m", "api"]
