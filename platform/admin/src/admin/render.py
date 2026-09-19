"""
Fragment builders for the markup pushed over SSE. Math (coordinates, colors,
percentages) stays in Python — Jinja templates just lay out the markup.
Ported from monolith's `stelo.admin.render` (same SVG-coordinate math,
`orjson.dumps` -> `json.dumps`); layout/classes/tokens match the approved
mockup (https://claude.ai/artifact/3pGrStBJuEZ2wWKt2rkjHC) exactly.
"""

import json
from pathlib import Path

import jinja2

# `templates/` sits next to the *package* in the Docker image (built by
# platform/admin/Dockerfile) but next to the *workspace member* (one level
# further up) in this src-layout checkout — a cwd-relative loader would only
# work when the caller happens to `cd` into platform/admin first (true for
# `docker run`'s WORKDIR, false for the repo-root `just test`), so resolve
# from this file's own location instead of trusting the process cwd.
_PKG_DIR = Path(__file__).resolve().parent
_TEMPLATES_DIR = next(
    (
        candidate
        for candidate in (
            _PKG_DIR.parent / 'templates',
            _PKG_DIR.parent.parent / 'templates',
        )
        if candidate.is_dir()
    ),
    _PKG_DIR.parent.parent / 'templates',
)

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(_TEMPLATES_DIR / 'fragments'),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)

STAGE_COLORS = {
    'submitted': 'var(--submitted)',
    'executed': 'var(--executed)',
    'filled': 'var(--filled)',
}

_PILL = {
    'FILLED': ('filled', 'FILLED'),
    'PARTIALLY_FILLED': ('partial', 'PARTIAL'),
    'REJECTED': ('rejected', 'REJECTED'),
}


def spark(
    values: list[float], color: str, elem_id: str, width: int = 240, height: int = 32
) -> str:
    """
    The returned <svg> carries `elem_id` so Datastar's default fragment merge
    (match by the fragment's own id) replaces the right element without
    needing an explicit selector.
    """
    if not values:
        return (
            f'<svg id="{elem_id}" class="spark" viewBox="0 0 {width} {height}" '
            f'preserveAspectRatio="none"></svg>'
        )
    pad = 3
    hi = max(values) * 1.15 or 1.0
    step = width / max(len(values) - 1, 1)
    path = ' '.join(
        f'{"M" if i == 0 else "L"}{i * step:.1f},'
        f'{height - pad - (v / hi) * (height - pad * 2):.1f}'
        for i, v in enumerate(values)
    )
    return _env.get_template('spark.html').render(
        elem_id=elem_id, width=width, height=height, color=color, path=path
    )


def chart(history: dict[str, list[float]], width: int = 560, height: int = 200) -> str:
    pad_l, pad_r, pad_t, pad_b = 34, 10, 8, 18
    inner_w, inner_h = width - pad_l - pad_r, height - pad_t - pad_b
    n = max((len(v) for v in history.values()), default=0)
    all_vals = [v for series in history.values() for v in series]
    hi = (max(all_vals) * 1.15 if all_vals else 0) or 1.0
    step = inner_w / max(n - 1, 1)

    def y_of(v: float) -> float:
        return pad_t + inner_h - (v / hi) * inner_h

    gridlines = [
        {
            'y': f'{pad_t + inner_h * g / 4:.1f}',
            'label_y': f'{pad_t + inner_h * g / 4 + 3:.1f}',
            'label': round(hi - hi * g / 4),
        }
        for g in range(5)
    ]
    series = [
        {
            'path': ' '.join(
                f'{"M" if i == 0 else "L"}{pad_l + i * step:.1f},{y_of(v):.1f}'
                for i, v in enumerate(values)
            ),
            'last_x': f'{pad_l + (len(values) - 1) * step:.1f}'
            if values
            else f'{pad_l:.1f}',
            'last_y': f'{y_of(values[-1]):.1f}' if values else f'{y_of(0):.1f}',
            'color': STAGE_COLORS[stage],
        }
        for stage, values in history.items()
    ]

    return _env.get_template('chart.html').render(
        width=width,
        height=height,
        pad_l=pad_l,
        pad_r=pad_r,
        gridlines=gridlines,
        series=series,
        series_json=json.dumps(history),
        step=f'{step:.4f}',
    )


def ticker_bars(volume: dict[str, dict[str, int]]) -> str:
    if not volume:
        return '<div id="tickers"></div>'
    rows = []
    for ticker, v in sorted(
        volume.items(), key=lambda kv: kv[1]['buy'] + kv[1]['sell'], reverse=True
    ):
        total = v['buy'] + v['sell']
        buy_pct = (v['buy'] / total * 100) if total else 0.0
        rows.append(
            {
                'ticker': ticker,
                'volume_fmt': f'{total:,} sh',
                'buy_pct': f'{buy_pct:.1f}',
                'sell_pct': f'{100 - buy_pct if total else 0.0:.1f}',
            }
        )
    return _env.get_template('ticker_bars.html').render(rows=rows)


def feed_rows(trade_tape: list[dict]) -> str:
    rows = [
        {
            'ticker': r['ticker'],
            'side_class': 'side-buy' if r['side'] == 'BUY' else 'side-sell',
            'side': r['side'],
            'quantity': f'{r["quantity"]:,}',
            'price': f'${r["price"]:.2f}' if r['price'] is not None else '—',
            'pill_class': _PILL.get(r['status'], ('', r['status']))[0],
            'pill_label': _PILL.get(r['status'], ('', r['status']))[1],
            'time': r['at'][11:19],
        }
        for r in trade_tape
    ]
    return _env.get_template('feed_rows.html').render(rows=rows)


def service_card(  # noqa: PLR0913
    elem_id: str,
    name: str,
    port: int,
    role: str,
    up: bool,
    stats: list[tuple[str, str]],
    note: str,
    warn: bool = False,
) -> str:
    return _env.get_template('service_card.html').render(
        elem_id=elem_id,
        name=name,
        port=port,
        role=role,
        status='up' if up else 'down',
        status_label='UP' if up else 'DOWN',
        stats=[{'label': label, 'value': value} for label, value in stats],
        note=note,
        warn=warn,
    )
