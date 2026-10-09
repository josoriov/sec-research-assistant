-- Check shape and calendar validity before casting so malformed dates quarantine.
{% macro safe_date(column) -%}
case
    when {{ column }} ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
     and pg_input_is_valid({{ column }}, 'date')
    then {{ column }}::date
end
{%- endmacro %}

-- Renders the supported-unit list as a SQL IN list from the `supported_units`
-- var, so the staging model and the accepted_values test cannot drift.
{% macro supported_units_in_list() -%}
({% for unit in var('supported_units') %}'{{ unit }}'{% if not loop.last %}, {% endif %}{% endfor %})
{%- endmacro %}
