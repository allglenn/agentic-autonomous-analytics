import pytest
from semantic_layer.resolver import resolve_query


def test_resolve_revenue_by_channel():
    sql = resolve_query(metric="revenue", dimensions=["channel"], time_range="last_7_days")
    assert "SUM(amount)" in sql
    assert "marketing_channel" in sql
    assert "GROUP BY" in sql


def test_blocked_metric_raises():
    with pytest.raises(ValueError, match="not in the allowed list"):
        resolve_query(metric="raw_cost", dimensions=["channel"], time_range="last_7_days")


def test_pii_dimension_raises():
    with pytest.raises(ValueError, match="PII protection"):
        resolve_query(metric="revenue", dimensions=["email"], time_range="last_7_days")


def test_unknown_time_range_raises():
    with pytest.raises(ValueError, match="Unknown time_range"):
        resolve_query(metric="revenue", dimensions=["channel"], time_range="next_century")
