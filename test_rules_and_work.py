"""Regression checks for the data-driven laws and work system."""
from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from data.jobs import JOBS, validate_jobs
from services.rules import load_laws, random_law, validate_laws


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f'PASS: {name}')


errors = validate_jobs()
check('job data validates', not errors)
check('all expected jobs exist', {'fermer', 'janitor', 'courier', 'cook', 'office', 'programmer', 'boss'} <= set(JOBS))
check('job pay ranges are sane', all(int(v['max_pay']) >= int(v['min_pay']) >= 0 for v in JOBS.values()))
check('job chances are 0..100', all(0 <= int(v['chance']) <= 100 for v in JOBS.values()))

law_errors, laws = validate_laws()
check('law data validates', not law_errors)
check('law pool is non-empty', len(laws) >= 20)
check('both countries have laws', bool([x for x in laws if x['country'] == 'UA']) and bool([x for x in laws if x['country'] == 'RU']))
check('random UA law comes from UA pool', random_law('UA')['country'] == 'UA')
check('random RU law comes from RU pool', random_law('RU')['country'] == 'RU')
check('law entries have article and title', all(x['article'] and x['title'] and x['code'] for x in laws))

newfile = (ROOT / 'newfile.py').read_text(encoding='utf-8')
module = ast.parse(newfile)
job_assignments = [node for node in ast.walk(module) if isinstance(node, (ast.Assign, ast.AnnAssign)) and any(getattr(t, 'id', None) == 'JOBS' for t in getattr(node, 'targets', []))]
check('JOBS is no longer hardcoded in newfile.py', not job_assignments)
check('newfile imports JOBS from data.jobs', 'from data.jobs import JOBS' in newfile)

callbacks = (ROOT / 'handlers' / 'callbacks.py').read_text(encoding='utf-8')
check('work callback uses safe shift helper', '_perform_job_shift(' in callbacks)
check('law callback exists', "action_data.startswith('law_country:')" in callbacks)

rules_handler = (ROOT / 'handlers' / 'rules.py').read_text(encoding='utf-8')
check('law phrase handler exists', 'под что я попал' in rules_handler and 'какой закон я нарушил' in rules_handler)

print(f'ALL RULE/WORK CHECKS PASS: laws={len(laws)}, jobs={len(JOBS)}')
