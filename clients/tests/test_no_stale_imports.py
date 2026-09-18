import re
from pathlib import Path

STALE = re.compile(r'^\s*(from|import)\s+(services|shared)(\.|\s)')


def test_no_stale_service_or_shared_imports():
    offenders = []
    for path in Path(__file__).parent.parent.rglob('*.py'):
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if STALE.match(line):
                offenders.append(f'{path}:{lineno}: {line.strip()}')
    assert not offenders, 'stale services./shared. import(s):\n' + '\n'.join(offenders)
