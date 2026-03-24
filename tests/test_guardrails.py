from config.guardrails import guardrails


def test_allowed_metrics_not_empty():
    assert len(guardrails.allowed_metrics) > 0


def test_pii_fields_blocked():
    for field in ["user_id", "email", "phone", "ip_address"]:
        assert field in guardrails.blocked_dimensions
        assert field not in guardrails.allowed_dimensions


def test_max_steps_positive():
    assert guardrails.max_executor_steps > 0


def test_max_rows_positive():
    assert guardrails.max_query_rows > 0
