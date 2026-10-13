"""Extract source-linked passages from archived SEC filings."""

# Active extraction version. Bump when the parser changes; dbt serves only this
# version (see dbt_project.yml `active_processing_version`), while older versions
# stay in bronze/silver for lineage.
PROCESSING_VERSION = "extract-v3"
