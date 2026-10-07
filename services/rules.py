"""Small data-driven rule/law engine.

The .ru files are deliberately simple text data, not executable code. This
keeps law content out of newfile.py and makes future rule packs easy to add.
"""
from __future__ import annotations

from pathlib import Path
import random


ROOT = Path(__file__).resolve().parent.parent
LAW_FILE = ROOT / 'data' / 'laws.ru'


def _parse_blocks(path: Path):
    entries = []
    current = {}
    if not path.exists():
        return entries
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line == '[law]':
            if current:
                entries.append(current)
            current = {}
            continue
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        current[key.strip()] = value.strip()
    if current:
        entries.append(current)
    return entries


def load_laws(path=LAW_FILE):
    """Load and validate the compact law data file."""
    result = []
    for item in _parse_blocks(Path(path)):
        country = item.get('country', '').upper()
        article = item.get('article', '').strip()
        title = item.get('title', '').strip()
        code = item.get('code', '').strip()
        source = item.get('source', '').strip()
        if country not in {'UA', 'RU'} or not article or not title or not code:
            continue
        result.append({
            'country': country,
            'article': article,
            'title': title,
            'code': code,
            'source': source,
        })
    return result


_LAWS = None


def get_laws(country):
    global _LAWS
    if _LAWS is None:
        _LAWS = load_laws()
    country = str(country or '').upper()
    return [law for law in _LAWS if law['country'] == country]


def random_law(country, rng=None):
    laws = get_laws(country)
    if not laws:
        return None
    return (rng or random).choice(laws).copy()


def game_sentence(rng=None):
    """Return a deliberately fictional NyaBot punishment for the joke."""
    minutes = (5, 10, 15, 30, 45, 60, 120, 180)
    value = (rng or random).choice(minutes)
    if value < 60:
        return f'{value} мин.'
    hours = value // 60
    return f'{hours} ч.'


def validate_laws(path=LAW_FILE):
    laws = load_laws(Path(path))
    errors = []
    if not laws:
        errors.append('law database is empty')
    for country in ('UA', 'RU'):
        if not any(item['country'] == country for item in laws):
            errors.append(f'no laws for {country}')
    return errors, laws
