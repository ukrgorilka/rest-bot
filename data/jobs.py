"""Job/vacancy definitions used by the work system.

Keeping these definitions outside newfile.py makes balancing safer: changing a
salary or requirement does not require editing the large runtime module.
"""

JOBS = {
    'fermer': {'name': '👨‍🌾 Фермер', 'req_exp': 0, 'chance': 95, 'min_pay': 25, 'max_pay': 55, 'exp_gain': 10},
    'janitor': {'name': '🧹 Дворник', 'req_exp': 0, 'chance': 90, 'min_pay': 35, 'max_pay': 65, 'exp_gain': 12},
    'courier': {'name': '🛵 Курьер', 'req_exp': 50, 'chance': 80, 'min_pay': 75, 'max_pay': 145, 'exp_gain': 15},
    'cook': {'name': '👨‍🍳 Повар', 'req_exp': 150, 'chance': 70, 'min_pay': 145, 'max_pay': 290, 'exp_gain': 20},
    'office': {'name': '👨‍💻 Офисный клерк', 'req_exp': 350, 'chance': 60, 'min_pay': 280, 'max_pay': 550, 'exp_gain': 25},
    'programmer': {'name': '💻 Программист', 'req_exp': 800, 'chance': 45, 'min_pay': 650, 'max_pay': 1300, 'exp_gain': 35},
    'boss': {'name': '💼 Бизнесмен', 'req_exp': 1800, 'chance': 30, 'min_pay': 1500, 'max_pay': 3800, 'exp_gain': 50},
}

REQUIRED_FIELDS = ('name', 'req_exp', 'chance', 'min_pay', 'max_pay', 'exp_gain')


def validate_jobs(jobs=JOBS):
    """Return validation errors instead of allowing malformed job data to crash a shift."""
    errors = []
    if not isinstance(jobs, dict) or not jobs:
        return ['JOBS must be a non-empty mapping']
    for job_id, job in jobs.items():
        if not isinstance(job_id, str) or not job_id.strip():
            errors.append('empty job id')
            continue
        if not isinstance(job, dict):
            errors.append(f'{job_id}: definition is not a mapping')
            continue
        missing = [key for key in REQUIRED_FIELDS if key not in job]
        if missing:
            errors.append(f'{job_id}: missing {", ".join(missing)}')
            continue
        try:
            req = int(job['req_exp']); chance = int(job['chance'])
            min_pay = int(job['min_pay']); max_pay = int(job['max_pay']); exp_gain = int(job['exp_gain'])
            if req < 0 or exp_gain < 0 or min_pay < 0 or max_pay < min_pay or not 0 <= chance <= 100:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f'{job_id}: invalid numeric values')
    return errors
