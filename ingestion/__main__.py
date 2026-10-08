"""CLI: python -m ingestion --company AAPL --years 3"""
import argparse

from ingestion.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m ingestion")
    parser.add_argument("--company", required=True, help="ticker from the CIK mapping")
    parser.add_argument("--years", type=int, default=3, help="annual filings to fetch")
    args = parser.parse_args()
    run(args.company, args.years)


if __name__ == "__main__":
    main()
