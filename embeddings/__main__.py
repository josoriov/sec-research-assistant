"""CLI: python -m embeddings (embeds validated silver passages)."""
from __future__ import annotations

from embeddings.pipeline import run


def main() -> None:
    summary = run()
    print(
        f"embeddings: {summary['embedded']} embedded, {summary['reused']} reused "
        f"of {summary['total']} (model={summary['model_version']} dim={summary['dim']})"
    )


if __name__ == "__main__":
    main()
