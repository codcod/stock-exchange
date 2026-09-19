from admin import render


def test_spark_empty_input():
    out = render.spark([], 'var(--submitted)', 'spark-submitted')
    assert 'id="spark-submitted"' in out
    assert '<svg' in out


def test_spark_root_id():
    out = render.spark([1.0, 2.0, 3.0], 'var(--submitted)', 'spark-submitted')
    assert 'id="spark-submitted"' in out
    assert '<path' in out


def test_chart_empty_input():
    out = render.chart({'submitted': [], 'executed': [], 'filled': []})
    assert 'id="chart"' in out


def test_chart_with_data():
    out = render.chart(
        {'submitted': [1.0, 2.0], 'executed': [0.5, 1.5], 'filled': [0.0, 1.0]}
    )
    assert 'id="chart"' in out
    assert out.count('<path') == 3  # one polyline per stage


def test_ticker_bars_empty_input():
    out = render.ticker_bars({})
    assert out == '<div id="tickers"></div>'


def test_ticker_bars_root_id():
    out = render.ticker_bars({'AAPL': {'buy': 60, 'sell': 40}})
    assert 'id="tickers"' in out
    assert 'AAPL' in out


def test_feed_rows_empty_input():
    out = render.feed_rows([])
    assert 'id="feed-body"' in out


def test_feed_rows_root_id():
    out = render.feed_rows(
        [
            {
                'ticker': 'AAPL',
                'side': 'BUY',
                'quantity': 150,
                'price': 228.41,
                'status': 'FILLED',
                'at': '2026-09-19T14:32:05+00:00',
            }
        ]
    )
    assert 'id="feed-body"' in out
    assert 'AAPL' in out
    assert 'pill filled' in out


def test_service_card_root_id_and_status():
    out = render.service_card(
        'svc-gateway',
        'Gateway',
        8000,
        'Entry point',
        True,
        [('Requests/s', '12.3')],
        'note',
    )
    assert 'id="svc-gateway"' in out
    assert 'status-pill up' in out
    assert '>UP<' in out


def test_service_card_down_status():
    out = render.service_card(
        'svc-gateway',
        'Gateway',
        8000,
        'Entry point',
        False,
        [('Requests/s', '—')],
        'note',
    )
    assert 'status-pill down' in out
    assert '>DOWN<' in out
