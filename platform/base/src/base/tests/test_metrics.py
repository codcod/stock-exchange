from base.metrics import RateCounter


def test_rate_last_counts_recorded_samples():
    c = RateCounter()
    for _ in range(10):
        c.record()
    assert c.rate_last(1.0) == 10.0


def test_rate_last_empty_is_zero():
    assert RateCounter().rate_last(60.0) == 0.0


def test_percentiles_last_matches_known_values():
    c = RateCounter()
    for v in [10.0, 20.0, 30.0, 40.0, 50.0]:
        c.record(v)
    result = c.percentiles_last(60.0, [0, 50, 100])
    assert result[0] == 10.0
    assert result[50] == 30.0
    assert result[100] == 50.0


def test_percentiles_last_empty_is_none():
    result = RateCounter().percentiles_last(60.0, [50, 95])
    assert result == {50: None, 95: None}


def test_percentiles_last_single_value():
    c = RateCounter()
    c.record(7.0)
    assert c.percentiles_last(60.0, [50])[50] == 7.0
