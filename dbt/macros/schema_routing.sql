-- Schema routing for the medallion layers.
--
-- 1. Use the custom schema name verbatim: models configured with
--    `+schema: silver` / `+schema: gold` land in exactly `silver` and `gold`,
--    not the dbt default `<target_schema>_<custom_schema>`.
-- 2. Suppress dbt's own schema creation. The schemas are provisioned once by
--    db/init/01-init.sh (T001); the pipeline role has CREATE on each schema but
--    not on the database, which PostgreSQL requires even for
--    `CREATE SCHEMA IF NOT EXISTS` of an existing schema. Overriding the
--    Postgres adapter macro keeps least privilege instead of granting
--    database-wide CREATE.

{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}

{% macro postgres__create_schema(relation) -%}
{%- endmacro %}

{% macro postgres__drop_schema(relation) -%}
{%- endmacro %}
