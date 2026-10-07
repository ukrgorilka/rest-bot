"""Extracted Telegram handlers for staged NyaBot architecture.

The handlers keep their original function bodies. During migration, register(ctx)
receives the legacy newfile.py globals so business logic and shared state remain
unchanged.
"""

from __future__ import annotations


def _inject(ctx):
    for _name, _value in ctx.items():
        if _name not in {"__name__", "__package__", "__loader__", "__spec__", "__cached__", "__builtins__"}:
            globals()[_name] = _value


HANDLER_NAMES = ['cmd_public_salary', 'cmd_public_jobs', 'cmd_cook', 'cmd_market', 'cmd_portfolio', 'cmd_work', 'cmd_train', 'cmd_sell', 'cmd_iq', 'cmd_fat', 'cmd_foot', 'cmd_chromosomes']


def cmd_public_salary(message):
    if not can_process_user_message(message): return
    uid=message.from_user.id; name=(f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ=get_user_econ(uid,name,username=message.from_user.username); es=econ.get('employer_salary')
    if not es or not es.get('owner_id'):
        bot.reply_to(message,'💼 Вы сейчас не работаете в публичном бизнесе. Вакансии: /вакансии'); return
    if time.time()<es.get('next_due',0):
        left=cooldown_text(es.get('next_due',0),0,econ)
        bot.reply_to(message,f'⏳ Следующая зарплата будет через <b>{left}</b>.',parse_mode='HTML'); return
    owner=get_user_econ(es['owner_id']); pb=owner.get('public_business')
    if not pb:
        econ['employer_salary']=None; mark_dirty(); bot.reply_to(message,'❌ Бизнес больше не существует.'); return
    salary=int(pb.get('salary_per_worker',100)*(1+pet_bonus(owner,'business_bonus')))
    profit=max(1,int(salary*0.25))
    owner_id = int(es['owner_id'])
    with serialized_multi_user_action(uid, owner_id):
        owner = get_user_econ(owner_id)
        pb = owner.get('public_business')
        if not pb:
            econ['employer_salary']=None; mark_dirty(); bot.reply_to(message,'❌ Бизнес больше не существует.'); return
        salary=int(pb.get('salary_per_worker',100)*(1+pet_bonus(owner,'business_bonus')))
        profit=max(1,int(salary*0.25))
        if owner.get('balance',0)<salary:
            bot.reply_to(message,'⏳ У владельца пока недостаточно средств для выплаты зарплаты.'); return
        _adjust_balance(owner, -(salary))
        _adjust_balance(econ, salary)
        _adjust_balance(owner, profit)
        es['next_due']=time.time()+3*86400; econ['employer_salary']=es; mark_dirty()
    bot.reply_to(message,f'💵 <b>Зарплата получена!</b> +{salary:,} 🪙\n🏢 Владелец получил прибыль +{profit:,} 🪙.',parse_mode='HTML')

def cmd_public_jobs(message):
    if not can_process_user_message(message): return
    name=(f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_public_jobs(message.chat.id,message.from_user.id,name)

def cmd_cook(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    fish_count = sum(econ.get('fish_inventory', {}).values())
    hunt_count = sum(econ.get('hunt_inventory', {}).values())

    if fish_count == 0 and hunt_count == 0:
        bot.reply_to(message, "🎒 У вас нет пойманной рыбы или мяса дичи для приготовления! 😿\nСходите на <code>/fish</code> или <code>/hunt</code>.", parse_mode='HTML')
        return

    econ['fish_inventory'] = {}
    econ['hunt_inventory'] = {}
    total_items = fish_count + hunt_count
    econ['cooked_meals'] = econ.get('cooked_meals', 0) + total_items

    if econ.get('pet'):
        p = econ['pet']
        p['hunger'] = 100
        p['cleanliness'] = min(100, p.get('cleanliness', 100) + 20)

    mark_dirty()
    bot.reply_to(
        message,
        f"🍳 <b>КУЛИНАРНЫЙ ШЕДЕВР ГОТОВ!</b> 😺\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Вы приготовили <b>{total_items} порций</b> изысканных блюд! 🍲🍖\n"
        f"🐾 Питомец накормлен до отвала (Сытость: <b>100%</b>) без трат коинов! 😻\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode='HTML'
    )

def cmd_market(message):
    if not can_process_user_message(message):
        return
    market = get_market_data()
    lines = [
        "📈 <b>НЯ-БИРЖА КРИПТОВАЛЮТ И АКЦИЙ</b> 😺",
        "━━━━━━━━━━━━━━━━━━━━",
        "<i>Курсы обновляются автоматически каждые 30 минут:</i>\n"
    ]
    for ticker, info in market.items():
        price = info['price']
        old_price = info.get('old_price', price)
        diff = price - old_price
        pct = (diff / old_price * 100) if old_price > 0 else 0
        trend = "🟢 📈 +" if diff >= 0 else "🔴 📉 "
        lines.append(f"• <b>{info['name']}</b> [{ticker}]\n  Курс: <b>{price:.2f} 🪙</b> ({trend}{pct:.1f}%)\n")

    lines.append("━━━━━━━━━━━━━━━━━━━━\n💡 <b>Как торговать:</b> 😸")
    lines.append("• <code>купить крипту NYA 5</code>\n• <code>продать крипту NYA 5</code>\n• <code>портфель</code> — посмотреть свои активы")
    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')

def cmd_portfolio(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    market = get_market_data()

    portfolio = econ.get('crypto_portfolio', {})
    total_val = 0.0
    lines = [f"💼 <b>ИНВЕСТИЦИОННЫЙ ПОРТФЕЛЬ: {make_link(message.chat.id, user_name, user_id, ping=False)}</b> 😺", "━━━━━━━━━━━━━━━━━━━━"]

    has_assets = False
    for ticker, amount in portfolio.items():
        if amount > 0.0001:
            has_assets = True
            cur_price = market.get(ticker, {}).get('price', 1.0)
            val = amount * cur_price
            total_val += val
            lines.append(f"• <b>{ticker}</b>: {amount:.2f} шт. (Оценка: <b>{val:.2f} 🪙</b>)")

    if not has_assets: lines.append("🎒 Ваш крипто-портфель пока пуст! Купите активы в <code>биржа</code>. 😿")
    else: lines.extend(["━━━━━━━━━━━━━━━━━━━━", f"📊 <b>Общая стоимость: {total_val:.2f} Ня-коинов 🪙</b> 😻"])
    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')

def _perform_job_shift(user_id, user_name, user_username, job_id, chat_id):
    """Execute one work shift atomically and return a UI result tuple.

    The job table is validated before use, all state mutation happens under the
    per-user callback lock plus the shared DB lock, and no Telegram network call
    happens while the DB lock is held. A malformed job therefore becomes a safe
    user-facing error instead of an exception escaping a work callback.
    """
    job = JOBS.get(job_id)
    if not isinstance(job, dict):
        return False, '❌ Эта вакансия больше недоступна. 😿', None, None
    required = ('name', 'req_exp', 'chance', 'min_pay', 'max_pay', 'exp_gain')
    if any(key not in job for key in required):
        return False, '❌ Данные вакансии повреждены. Администратор получит сообщение в логах.', None, None
    try:
        req_exp = int(job['req_exp']); chance = int(job['chance'])
        min_pay = int(job['min_pay']); max_pay = int(job['max_pay']); exp_gain = int(job['exp_gain'])
        if req_exp < 0 or exp_gain < 0 or min_pay < 0 or max_pay < min_pay or not 0 <= chance <= 100:
            raise ValueError
    except (TypeError, ValueError):
        print(f'[WORK DATA ERROR] Invalid job definition: {job_id!r} {job!r}')
        return False, '❌ Эта вакансия временно недоступна из-за ошибки данных. 😿', None, None

    with db_lock:
        econ = get_user_econ(user_id, user_name, username=user_username)
        if int(econ.get('work_exp', 0) or 0) < req_exp:
            return False, f'❌ Нужно минимум {req_exp} EXP опыта! 😿', None, None
        now = time.time()
        left = cooldown_text(econ.get('last_work_time', 0), 1800, econ)
        if left:
            return False, f'⏳ Отдохните еще: {left} 😿', None, None

        success = random.randint(1, 100) <= chance
        econ['last_work_time'] = now
        if success:
            pay = random.randint(min_pay, max_pay)
            pay = int(pay * (1 + pet_bonus(econ, 'work_bonus') + get_vehicle_work_bonus(econ) + get_title_work_bonus(econ) + get_vip_work_bonus(econ)))
            _adjust_balance(econ, pay)
            econ['work_exp'] = int(econ.get('work_exp', 0) or 0) + exp_gain
            gained_exp = exp_gain
            result_text = f'✅ Зарплата: +{pay} 🪙 (+{exp_gain} EXP)! 😻'
        else:
            econ['work_exp'] = int(econ.get('work_exp', 0) or 0) + 2
            gained_exp = 2
            pay = 0
            result_text = '❌ Вы ошиблись на смене! Получено +2 EXP. 😿'
        add_account_exp(user_id, user_name, gained_exp, username=user_username)
        mark_dirty()
    check_achievements(user_id, user_name, 'work_shifts', 1, chat_id, username=user_username) if success else None
    return success, result_text, pay, job


def cmd_work(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    lines = [
        "💼 <b>БИРЖА ТРУДА И ВАКАНСИЙ</b> 😺",
        "━━━━━━━━━━━━━━━━━━━━",
        f"👤 Ваш опыт работы: <b>{econ.get('work_exp', 0)} EXP</b>\n",
        "<b>Доступные вакансии:</b> 😸"
    ]
    for j_id, j in JOBS.items():
        lines.append(f"• <b>{j['name']}</b>: от <code>{j['req_exp']} EXP</code> (З/П: {j['min_pay']}-{j['max_pay']} 🪙)")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    markup = InlineKeyboardMarkup()
    for job_id, job in JOBS.items():
        btn_text = f"{job['name']} ({job['req_exp']} EXP)"
        markup.add(InlineKeyboardButton(btn_text, callback_data=f"do_job_{job_id}:{user_id}"))

    markup.add(InlineKeyboardButton("🎓 Пройти тренировку (+EXP)", callback_data=f"train_exp_btn:{user_id}"))
    bot.reply_to(message, "\n".join(lines), reply_markup=markup, parse_mode='HTML')

def cmd_train(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    _, text_resp = train_work_exp(user_id, user_name, username=message.from_user.username)
    bot.reply_to(message, text_resp, parse_mode='HTML')

def cmd_sell(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    total_earned = 0
    items_sold = 0
    price_multiplier = 2.0 if gold_rush_event.get('active') else 1.0
    econ_event = get_economic_event() if 'get_economic_event' in globals() else None
    fish_mult = float(econ_event.get('fish_sell', 1.0)) if econ_event else 1.0
    hunt_mult = float(econ_event.get('hunt_sell', 1.0)) if econ_event else 1.0

    for fish_name, count in list(econ.get('fish_inventory', {}).items()):
        price = 20
        for f_item in FISH_TYPES:
            if f_item[0] == fish_name: price = int(f_item[2] * price_multiplier * fish_mult); break
        total_earned += price * count
        items_sold += count
    econ['fish_inventory'] = {}

    for hunt_name, count in list(econ.get('hunt_inventory', {}).items()):
        price = 25
        for h_item in HUNT_TYPES:
            if h_item[0] == hunt_name: price = int(h_item[2] * price_multiplier * hunt_mult); break
        total_earned += price * count
        items_sold += count
    econ['hunt_inventory'] = {}

    if items_sold == 0:
        bot.reply_to(message, "🎒 У вас нет рыбы или охотничьих трофеев для продажи! 😿")
        return

    _adjust_balance(econ, total_earned)
    mark_dirty()
    rush_note = " (🌟 Золотая лихорадка x2.0!)" if gold_rush_event.get('active') else ""
    bot.reply_to(message, f"💰 Вы успешно продали добычу на сумму <b>+{total_earned} Ня-коинов 🪙</b>{rush_note}! 😻\nБаланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')

def cmd_iq(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    now_ts = time.time()
    cooldown = 1800
    left = cooldown_text(econ.get('last_iq_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Тест на IQ доступен раз в 30 минут! 😿\nПодождите: <b>{left}</b>.", parse_mode='HTML')
        return

    change = random.randint(-5, 15)
    econ['iq'] = max(0, econ.get('iq', 100) + change)
    econ['last_iq_time'] = now_ts
    mark_dirty()
    completed = track_daily_task(user_id, user_name, 'iq', 1, chat_id, username=message.from_user.username)
    sign = "+" if change >= 0 else ""
    bot.reply_to(message, f"🧠 {make_link(chat_id, user_name, user_id, ping=True)}, ваш IQ: <b>{econ['iq']} ({sign}{change}) 📊</b> 😺", parse_mode='HTML')
    for task_name, task_reward in completed: bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙 😻', parse_mode='HTML')

def cmd_fat(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    now_ts = time.time()
    cooldown = 1800
    left = cooldown_text(econ.get('last_fat_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Замер жира доступен раз в 30 минут! 😿\nПодождите: <b>{left}</b>.", parse_mode='HTML')
        return

    change = random.randint(-4, 6)
    econ['fat'] = max(0, min(100, econ.get('fat', 20) + change))
    econ['last_fat_time'] = now_ts
    mark_dirty()
    completed = track_daily_task(user_id, user_name, 'fat', 1, chat_id, username=message.from_user.username)
    sign = "+" if change >= 0 else ""
    bot.reply_to(message, f"🥩 {make_link(chat_id, user_name, user_id, ping=True)}, процент жира: <b>{econ['fat']}% ({sign}{change}%) 🍔</b> 😺", parse_mode='HTML')
    for task_name, task_reward in completed: bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙 😻', parse_mode='HTML')

def cmd_foot(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    now_ts = time.time()
    cooldown = 1200
    left = cooldown_text(econ.get('last_foot_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Измерить пятку можно раз в 20 минут! 😿\nПодождите: <b>{left}</b>.", parse_mode='HTML')
        return

    change = random.randint(-3, 4)
    econ['foot_size'] = max(5, min(80, econ.get('foot_size', 25) + change))
    econ['last_foot_time'] = now_ts
    mark_dirty()
    sign = "+" if change >= 0 else ""
    bot.reply_to(message, f"🦶 {make_link(chat_id, user_name, user_id, ping=True)}, размер пятки: <b>{econ['foot_size']} см ({sign}{change} см) 🦶</b> 😺", parse_mode='HTML')

def cmd_chromosomes(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    now_ts = time.time()
    cooldown = 1200
    left = cooldown_text(econ.get('last_chromosomes_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"🧬 Генетический анализ доступен раз в 20 минут! 😿\nПодождите: <b>{left}</b>.", parse_mode='HTML')
        return

    change = random.choice([-2, -1, 0, 1, 1, 2, 3])
    cur_chr = econ.get('chromosomes', 46)
    new_chr = max(38, min(100, cur_chr + change))
    econ['chromosomes'] = new_chr
    econ['last_chromosomes_time'] = now_ts
    mark_dirty()

    completed = track_daily_task(user_id, user_name, 'chromosomes', 1, chat_id, username=message.from_user.username)
    check_achievements(user_id, user_name, 'chromosomes_check', 1, chat_id, username=message.from_user.username)
    sign = "+" if change >= 0 else ""

    if new_chr == 46: comment = "Идеальный человеческий баланс! ✨ 😻"
    elif new_chr == 47: comment = "Обнаружена экстра-хромосома сверхразума! ⚡️ 🙀"
    elif new_chr > 47: comment = "Межгалактический уровень ДНК! 👽🚀 😹"
    else: comment = "Кажется, пара хромосом взяли отгул... 🔍 😿"

    u_link = make_link(chat_id, user_name, user_id, ping=True)
    bot.reply_to(message, f"🧬 <b>ГЕНЕТИЧЕСКИЙ ТЕСТ:</b> {u_link}\n━━━━━━━━━━━━━━━━━━━━\nКоличество хромосом: <b>{new_chr} ({sign}{change}) 🧬</b>\n📝 <i>{comment}</i>\n━━━━━━━━━━━━━━━━━━━━ 😺", parse_mode='HTML')
    for task_name, task_reward in completed: bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙 😻', parse_mode='HTML')

def register(ctx, only=None):
    """Register selected handlers from this feature module."""
    _inject(ctx)
    bot = ctx["bot"]
    wanted = set(only) if only is not None else set(HANDLER_NAMES)
    registered = []
    if "cmd_public_salary" in wanted:
        _handler = cmd_public_salary
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['salary', 'зарплата'])(_handler)
        ctx["cmd_public_salary"] = _handler
        globals()["cmd_public_salary"] = _handler
        registered.append("cmd_public_salary")
    if "cmd_public_jobs" in wanted:
        _handler = cmd_public_jobs
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['jobs', 'вакансии'])(_handler)
        ctx["cmd_public_jobs"] = _handler
        globals()["cmd_public_jobs"] = _handler
        registered.append("cmd_public_jobs")
    if "cmd_cook" in wanted:
        _handler = cmd_cook
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['cook', 'кулинария', 'приготовить'])(_handler)
        ctx["cmd_cook"] = _handler
        globals()["cmd_cook"] = _handler
        registered.append("cmd_cook")
    if "cmd_market" in wanted:
        _handler = cmd_market
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['market', 'биржа', 'crypto', 'крипта'])(_handler)
        ctx["cmd_market"] = _handler
        globals()["cmd_market"] = _handler
        registered.append("cmd_market")
    if "cmd_portfolio" in wanted:
        _handler = cmd_portfolio
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['portfolio', 'портфель'])(_handler)
        ctx["cmd_portfolio"] = _handler
        globals()["cmd_portfolio"] = _handler
        registered.append("cmd_portfolio")
    if "cmd_work" in wanted:
        _handler = cmd_work
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['work', 'работа'])(_handler)
        ctx["cmd_work"] = _handler
        globals()["cmd_work"] = _handler
        registered.append("cmd_work")
    if "cmd_train" in wanted:
        _handler = cmd_train
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['train', 'опыт'])(_handler)
        ctx["cmd_train"] = _handler
        globals()["cmd_train"] = _handler
        registered.append("cmd_train")
    if "cmd_sell" in wanted:
        _handler = cmd_sell
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['sell', 'продать'])(_handler)
        ctx["cmd_sell"] = _handler
        globals()["cmd_sell"] = _handler
        registered.append("cmd_sell")
    if "cmd_iq" in wanted:
        _handler = cmd_iq
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['iq'])(_handler)
        ctx["cmd_iq"] = _handler
        globals()["cmd_iq"] = _handler
        registered.append("cmd_iq")
    if "cmd_fat" in wanted:
        _handler = cmd_fat
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['fat'])(_handler)
        ctx["cmd_fat"] = _handler
        globals()["cmd_fat"] = _handler
        registered.append("cmd_fat")
    if "cmd_foot" in wanted:
        _handler = cmd_foot
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['foot'])(_handler)
        ctx["cmd_foot"] = _handler
        globals()["cmd_foot"] = _handler
        registered.append("cmd_foot")
    if "cmd_chromosomes" in wanted:
        _handler = cmd_chromosomes
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['chromosomes', 'хромосомы', 'хромосома'])(_handler)
        ctx["cmd_chromosomes"] = _handler
        globals()["cmd_chromosomes"] = _handler
        registered.append("cmd_chromosomes")
    return registered
