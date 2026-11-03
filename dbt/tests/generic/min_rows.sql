{% test min_rows(model, n) %}
-- catches an empty or truncated download that still "succeeded"
select count(*) as rows from {{ model }} having count(*) < {{ n }}
{% endtest %}
