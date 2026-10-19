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
    'mechanic': {'name': '🔧 Автомеханик', 'req_exp': 600, 'chance': 78, 'min_pay': 400, 'max_pay': 850, 'exp_gain': 28},
    'medic': {'name': '🩺 Фельдшер', 'req_exp': 1200, 'chance': 73, 'min_pay': 700, 'max_pay': 1450, 'exp_gain': 35},
    'designer': {'name': '🎨 Дизайнер', 'req_exp': 2500, 'chance': 67, 'min_pay': 1200, 'max_pay': 2500, 'exp_gain': 45},
    'analyst': {'name': '📊 Аналитик', 'req_exp': 4000, 'chance': 60, 'min_pay': 1900, 'max_pay': 3600, 'exp_gain': 55},
    'engineer': {'name': '⚙️ Инженер', 'req_exp': 6500, 'chance': 55, 'min_pay': 2700, 'max_pay': 4900, 'exp_gain': 65},
    'lawyer': {'name': '⚖️ Юрист', 'req_exp': 10000, 'chance': 48, 'min_pay': 3600, 'max_pay': 6500, 'exp_gain': 75},
    'architect': {'name': '🏗 Архитектор', 'req_exp': 16000, 'chance': 42, 'min_pay': 5200, 'max_pay': 9000, 'exp_gain': 90},
    'astronaut': {'name': '🚀 Космонавт', 'req_exp': 25000, 'chance': 35, 'min_pay': 7600, 'max_pay': 12500, 'exp_gain': 110},
    'researcher': {'name': '🧪 ИИ-исследователь', 'req_exp': 40000, 'chance': 28, 'min_pay': 10000, 'max_pay': 16000, 'exp_gain': 130},
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
