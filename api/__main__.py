"""CLI: python -m api (runs the FastAPI app with uvicorn)."""
from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "api.app:app",
        host=os.environ.get("API_HOST", "127.0.0.1"),
        port=int(os.environ.get("API_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
