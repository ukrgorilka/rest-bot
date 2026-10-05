from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import sys
import types
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / 'rest-bot-main.pre_v03'
PROTECTED_HASHES = {
    'rests_data.json': '8218f30c5dce8031739eaf67d3af067c142c0f3e6397b0e8e476b9f70d8adcae',
    'handlers/None': '01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b',
    'miniapp/None': 'fcf33dfbe13c2354bf0e1b063f9fb422747a46cee00b7420bceff2b81457b345',
}


def module_assignments(path: Path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:
                pass
    return out, tree

new_vals, new_tree = module_assignments(ROOT / 'newfile.py')

assert 'BUSINESSES' in new_vals
assert 'DONOR_BUSINESSES' in new_vals
assert 'VEHICLES' in new_vals
assert 'LEGACY_BUSINESS_REPLACEMENTS' in new_vals

biz = new_vals['BUSINESSES']
donor = new_vals['DONOR_BUSINESSES']
vehicles = new_vals['VEHICLES']
legacy = new_vals['LEGACY_BUSINESS_REPLACEMENTS']

# Final business numbering is ordinary 1..16 and donor 17..19.
assert len(biz) == 16, len(biz)
assert len(donor) == 3, len(donor)
assert list(biz)[-4:] == ['mars_colony', 'lunar_corporation', 'solar_station', 'intergalactic_port']
assert 'bottles' not in biz and 'lemonade' not in biz and 'shawarma' not in biz
assert legacy == {'bottles': 'smoothie_bar', 'lemonade': 'food_truck', 'shawarma': 'pizzeria'}
assert biz['mars_colony']['price'] == 80_000_000
assert biz['mars_colony']['base_income'] == 220_000
post = [biz[k] for k in ('lunar_corporation','solar_station','intergalactic_port')]
assert all(x['price'] > 80_000_000 for x in post)
assert [x['base_income'] for x in post] == sorted(x['base_income'] for x in post)
assert post[-1]['base_income'] == 300_000

# All cars have classes and secondary work utility while preserving cooldown stat.
classes = {v.get('class') for v in vehicles.values()}
assert classes >= {'economy','sport','luxury','hyper','galactic'}
assert all('cd_cut' in v and 'work_bonus' in v for v in vehicles.values())
assert vehicles['slippers']['price'] == 100 and vehicles['slippers']['work_bonus'] == 0.01
assert vehicles['star_cruiser']['price'] == 10_000_000 and vehicles['star_cruiser']['cd_cut'] == 0.75

# Compile function-level migration behavior without importing the Telegram stack.
func_nodes = {n.name:n for n in new_tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
ns = {
    'time': time,
    'LEGACY_BUSINESS_REPLACEMENTS': legacy,
    'LEGACY_BUSINESS_INFO': {
        'bottles': {'name':'🥫 Приём стеклотары','price':200},
        'lemonade': {'name':'🍋 Лоток с лимонадом','price':450},
        'shawarma': {'name':'🌯 Ларек с Шаурмой','price':800},
    },
    'BUSINESS_SELL_RATE': 0.80,
    'mark_dirty': lambda: None,
}
exec(compile(ast.Module(body=[func_nodes['_migrate_legacy_businesses']], type_ignores=[]), '<migration>', 'exec'), ns)
migrate = ns['_migrate_legacy_businesses']

econ = {
    'balance': 5000,
    'businesses': {'bottles': 123.0},
    'biz_levels': {'bottles': 3},
    'biz_purchase_price': {'bottles': 200},
    'biz_last_collect': {'bottles': 321.0},
    'biz_income_carry': {'bottles': 2.5},
}
assert migrate(econ) is True
assert 'bottles' not in econ['businesses'] and 'smoothie_bar' in econ['businesses']
assert econ['biz_levels']['smoothie_bar'] == 3
assert econ['biz_purchase_price']['smoothie_bar'] == 200
assert econ['biz_last_collect']['smoothie_bar'] == 321.0

# Overlap case refunds 80% and does not duplicate on second pass.
econ2 = {
    'balance': 1000,
    'businesses': {'lemonade': 1.0, 'food_truck': 2.0},
    'biz_levels': {'lemonade': 2},
    'biz_purchase_price': {'lemonade': 450},
}
assert migrate(econ2) is True
assert econ2['balance'] == 1360
assert 'lemonade' not in econ2['businesses']
before = copy.deepcopy(econ2)
assert migrate(econ2) is False
assert econ2 == before

# New business detail helpers have the intended level curve.
ns2 = dict(ns)
ns2['_business_info'] = lambda b_id: biz.get(b_id) or donor.get(b_id)
ns2['BUSINESSES'] = biz
ns2['DONOR_BUSINESSES'] = donor
exec(compile(ast.Module(body=[func_nodes['_business_hourly_income']], type_ignores=[]), '<income>', 'exec'), ns2)
income = ns2['_business_hourly_income']
assert income('mars_colony',1) == 220_000
assert income('mars_colony',5) > income('mars_colony',1)
assert income('intergalactic_port',1) == 300_000

# Neon must be authoritative when a local JSON snapshot is old/stale.
# Import core.database with a minimal psycopg2 stub so no external service is contacted.
fake_psy = types.ModuleType('psycopg2')
fake_extras = types.ModuleType('psycopg2.extras')
fake_extras.Json = lambda x: x
fake_psy.extras = fake_extras
sys.modules['psycopg2'] = fake_psy
sys.modules['psycopg2.extras'] = fake_extras
sys.path.insert(0, str(ROOT))
import core.database as dbmod
live = {'economy': {'id_1': {'balance': 999}}, '_meta': {'saved_at': 200}}
stale = {'economy': {'id_1': {'balance': 1}}, '_meta': {'saved_at': 100}}
dbmod.DATABASE_URL = 'neon-test'
dbmod._pg_load = lambda: live
dbmod._load_local_json = lambda: stale
def norm(x): return x
assert dbmod._load_data_from_sources({'economy':{}}, norm)['economy']['id_1']['balance'] == 999

# Ensure the archival JSON and protected odd files were not touched by v0.3 edits.
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
for rel, expected_hash in PROTECTED_HASHES.items():
    after = ROOT / rel
    assert after.exists(), rel
    assert sha(after) == expected_hash, f'protected file changed: {rel}'
    # When this test is run beside the pre-v0.3 audit copy, compare the source too.
    before = BASE / rel
    if before.exists():
        assert sha(before) == expected_hash, f'baseline protected file changed: {rel}'

# No `non/` path exists in either tree; never create or edit it.
assert not any(p.parts and 'non' in p.parts for p in ROOT.rglob('*'))
if BASE.exists():
    assert not any(p.parts and 'non' in p.parts for p in BASE.rglob('*'))

print('v0.3 integrity: PASS')
