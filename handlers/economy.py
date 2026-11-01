"""Extracted Telegram handlers for staged NyaBot architecture.

The handlers keep their original function bodies. During migration, register(ctx)
receives the legacy newfile.py globals so business logic and shared state remain
unchanged.
"""

from __future__ import annotations

import copy
import html
import math


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
        _adjust_balance(owner, -(salary), reason='Выплата зарплаты сотрудникам')
        _adjust_balance(econ, salary, reason='Зарплата за работу')
        _adjust_balance(owner, profit, reason='Прибыль бизнеса от сотрудников')
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
    per-user action lock plus the canonical BALANCE_TX_LOCK -> db_lock order,
    and no Telegram network call happens while the DB lock is held. A malformed
    job therefore becomes a safe
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

    # Monetary operations must always acquire BALANCE_TX_LOCK before db_lock.
    # Otherwise this handler can deadlock against a payout that holds the balance
    # lock while waiting for db_lock. add_account_exp() may enter both as well.
    with BALANCE_TX_LOCK:
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
                _adjust_balance(econ, pay, reason='Оплата за работу')
                econ['work_exp'] = int(econ.get('work_exp', 0) or 0) + exp_gain
                gained_exp = exp_gain
                result_text = f'✅ Зарплата: +{pay} 🪙 (+{exp_gain} EXP)! 😻'
            else:
                econ['work_exp'] = int(econ.get('work_exp', 0) or 0) + 2
                gained_exp = 2
                pay = 0
                result_text = '❌ Вы ошиблись на смене! Получено +2 EXP. 😿'
            add_account_exp(user_id, user_name, gained_exp, username=user_username, source=f'job:{job_id}')
            mark_dirty()
    check_achievements(user_id, user_name, 'work_shifts', 1, chat_id, username=user_username) if success else None
    return success, result_text, pay, job


def _job_catalog_entries():
    """Return stable, one-based job numbers in the order shown to players."""
    return [(number, job_id, job) for number, (job_id, job) in enumerate(JOBS.items(), 1)]


def _job_number_for_id(job_id):
    for number, current_id, _job in _job_catalog_entries():
        if current_id == job_id:
            return number
    return None


def _parse_work_number(text):
    """Parse `работа 1`, `/work 1`, and common #/№ variants."""
    parts = str(text or '').strip().split()
    if len(parts) != 2:
        return None
    raw_number = parts[1].strip().lstrip('#№')
    if not raw_number.isdigit():
        return None
    try:
        number = int(raw_number)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if number > 0 else None


def render_job_catalog(chat_id, user_id, user_name, message_id=None, page=0):
    """Render a compact, paginated work catalogue; numeric commands open cards."""
    econ = get_user_econ(user_id, user_name)
    try:
        work_exp = max(0, int(econ.get('work_exp', 0) or 0))
    except (TypeError, ValueError, OverflowError):
        work_exp = 0

    entries = _job_catalog_entries()
    page_size = 6
    page_count = max(1, (len(entries) + page_size - 1) // page_size)
    try:
        page = max(0, int(page))
    except (TypeError, ValueError, OverflowError):
        page = 0
    page = min(page, page_count - 1)
    current = entries[page * page_size:(page + 1) * page_size]

    lines = [
        '💼 <b>БИРЖА ТРУДА NYABOT</b> 😺',
        f'📄 Страница <b>{page + 1}/{page_count}</b> · Всего профессий: <b>{len(entries)}</b>',
        f'👤 Ваш опыт работы: <b>{work_exp:,} EXP</b>',
        '━━━━━━━━━━━━━━━━━━━━',
    ]
    for number, _job_id, job in current:
        try:
            req_exp = max(0, int(job.get('req_exp', 0) or 0))
            min_pay = max(0, int(job.get('min_pay', 0) or 0))
            max_pay = max(min_pay, int(job.get('max_pay', min_pay) or min_pay))
            chance = min(100, max(0, int(job.get('chance', 0) or 0)))
        except (TypeError, ValueError, OverflowError):
            req_exp, min_pay, max_pay, chance = 0, 0, 0, 0
        expected_pay = int(round(((min_pay + max_pay) / 2) * chance / 100))
        status = '✅ доступна' if work_exp >= req_exp else f'🔒 нужно ещё {req_exp - work_exp:,} EXP'
        lines.append(
            f"<b>{number}. {html.escape(str(job.get('name', 'Профессия')))}</b> — {status}\n"
            f'   💵 {min_pay:,}–{max_pay:,} 🪙 при успехе · шанс {chance}% · в среднем ≈{expected_pay:,} 🪙/смену'
        )
    lines.extend([
        '━━━━━━━━━━━━━━━━━━━━',
        'Нажмите профессию или напишите <code>работа 1</code> (можно <code>робота 1</code>).',
        '<i>Средний заработок рассчитан без бонусов питомца, транспорта, титула и VIP.</i>',
    ])

    markup = InlineKeyboardMarkup(row_width=2)
    buttons = []
    for number, _job_id, job in current:
        name = str(job.get('name', 'Профессия'))
        buttons.append(InlineKeyboardButton(
            f'{number}. {name[:24]}', callback_data=f'job_detail:{number}:{user_id}'
        ))
    for index in range(0, len(buttons), 2):
        markup.add(*buttons[index:index + 2])
    if page_count > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton('⬅️ Назад', callback_data=f'job_page:{page - 1}:{user_id}'))
        nav.append(InlineKeyboardButton(f'{page + 1}/{page_count}', callback_data='noop'))
        if page + 1 < page_count:
            nav.append(InlineKeyboardButton('Далее ➡️', callback_data=f'job_page:{page + 1}:{user_id}'))
        markup.add(*nav)
    markup.add(InlineKeyboardButton('🎓 Тренировка (+EXP)', callback_data=f'train_job_catalog:{page}:{user_id}'))

    text = '\n'.join(lines)
    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id,
                                  reply_markup=markup, parse_mode='HTML')
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')


def render_job_detail(chat_id, user_id, user_name, number, message_id=None):
    """Show one job's requirements, approximate pay, and gated work action."""
    try:
        number = int(number)
    except (TypeError, ValueError, OverflowError):
        number = 0
    entries = _job_catalog_entries()
    target = next((entry for entry in entries if entry[0] == number), None)
    if target is None:
        text = '❌ Такой вакансии нет. Откройте каталог работ: <code>работа</code>.'
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('⬅️ Все работы', callback_data=f'job_catalog:{user_id}'))
        if message_id:
            try:
                bot.edit_message_text(text, chat_id=chat_id, message_id=message_id,
                                      reply_markup=markup, parse_mode='HTML')
                return
            except Exception:
                pass
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
        return

    _number, job_id, job = target
    econ = get_user_econ(user_id, user_name)
    try:
        work_exp = max(0, int(econ.get('work_exp', 0) or 0))
        req_exp = max(0, int(job.get('req_exp', 0) or 0))
        chance = min(100, max(0, int(job.get('chance', 0) or 0)))
        min_pay = max(0, int(job.get('min_pay', 0) or 0))
        max_pay = max(min_pay, int(job.get('max_pay', min_pay) or min_pay))
        exp_gain = max(0, int(job.get('exp_gain', 0) or 0))
    except (TypeError, ValueError, OverflowError):
        text = '❌ Данные этой вакансии временно недоступны.'
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('⬅️ Все работы', callback_data=f'job_catalog:{user_id}'))
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
        return

    expected_pay = int(round(((min_pay + max_pay) / 2) * chance / 100))
    eligible = work_exp >= req_exp
    try:
        left = cooldown_text(econ.get('last_work_time', 0), 1800, econ)
    except Exception:
        left = 'не удалось проверить кулдаун'
    available_now = eligible and not left

    lines = [
        f'💼 <b>РАБОТА #{number}: {html.escape(str(job.get("name", "Профессия")))}</b>',
        '━━━━━━━━━━━━━━━━━━━━',
        f'⭐ Требуемый опыт: <b>{req_exp:,} EXP</b>',
        f'📈 Ваш опыт работы: <b>{work_exp:,} EXP</b>',
        f'🎲 Шанс успешной смены: <b>{chance}%</b>',
        f'💵 При успехе: <b>{min_pay:,}–{max_pay:,} 🪙</b>',
        f'🧮 Приблизительно в среднем: <b>≈{expected_pay:,} 🪙 за смену</b> без бонусов',
        f'🎓 Опыт за смену: <b>+{exp_gain} EXP</b> при успехе; при неудаче +2 EXP',
        '⏱ Одна смена доступна раз в 30 минут.',
        '━━━━━━━━━━━━━━━━━━━━',
    ]
    if not eligible:
        lines.append(f'🔒 <b>Пока недоступна.</b> Не хватает <b>{req_exp - work_exp:,} EXP</b> опыта работы.')
    elif left:
        lines.append(f'⏳ <b>Сейчас работать нельзя.</b> Повторная смена будет доступна через {html.escape(str(left))}.')
    else:
        lines.append('✅ <b>Вы подходите и можете выйти на смену сейчас.</b>')

    markup = InlineKeyboardMarkup(row_width=2)
    if available_now:
        markup.add(InlineKeyboardButton('💼 Работать', callback_data=f'do_job_{job_id}:{user_id}'))
    elif not eligible:
        markup.add(InlineKeyboardButton('🎓 Получить опыт', callback_data=f'train_job_exp:{number}:{user_id}'))
    markup.add(InlineKeyboardButton('📋 Все работы', callback_data=f'job_page:{(number - 1) // 6}:{user_id}'))
    nav = []
    if number > 1:
        nav.append(InlineKeyboardButton('⬅️ Предыдущая', callback_data=f'job_detail:{number - 1}:{user_id}'))
    if number < len(entries):
        nav.append(InlineKeyboardButton('Следующая ➡️', callback_data=f'job_detail:{number + 1}:{user_id}'))
    if nav:
        markup.add(*nav)

    text = '\n'.join(lines)
    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id,
                                  reply_markup=markup, parse_mode='HTML')
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')


def cmd_work(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    number = _parse_work_number(getattr(message, 'text', ''))
    if number is not None:
        render_job_detail(message.chat.id, user_id, user_name, number)
    else:
        render_job_catalog(message.chat.id, user_id, user_name)

def cmd_train(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    _, text_resp = train_work_exp(user_id, user_name, username=message.from_user.username)
    bot.reply_to(message, text_resp, parse_mode='HTML')

def cmd_sell(message):
    """Sell only known fish/hunt items as one durable inventory transaction."""
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id

    total_earned = 0
    items_sold = 0
    sold_fish = {}
    sold_hunt = {}
    price_multiplier = 2.0 if gold_rush_event.get('active') else 1.0
    econ_event = get_economic_event() if 'get_economic_event' in globals() else None

    def _safe_multiplier(value):
        try:
            number = float(value)
            return number if math.isfinite(number) and 0 < number <= 10 else 1.0
        except (TypeError, ValueError, OverflowError):
            return 1.0

    fish_mult = _safe_multiplier(econ_event.get('fish_sell', 1.0)) if econ_event else 1.0
    hunt_mult = _safe_multiplier(econ_event.get('hunt_sell', 1.0)) if econ_event else 1.0
    fish_prices = {}
    hunt_prices = {}
    for item in FISH_TYPES:
        try:
            fish_prices[str(item[0])] = max(1, int(item[2]))
        except (TypeError, ValueError, IndexError, OverflowError):
            continue
    for item in HUNT_TYPES:
        try:
            hunt_prices[str(item[0])] = max(1, int(item[2]))
        except (TypeError, ValueError, IndexError, OverflowError):
            continue

    with BALANCE_TX_LOCK:
        with db_lock:
            econ = get_user_econ(user_id, user_name, username=message.from_user.username)
            fish_inventory = econ.get('fish_inventory', {})
            hunt_inventory = econ.get('hunt_inventory', {})

            # Unknown/legacy inventory keys are left untouched instead of being
            # silently sold at a fallback price or erased by a catalog mismatch.
            if isinstance(fish_inventory, dict):
                for item_name, raw_count in list(fish_inventory.items()):
                    if item_name not in fish_prices:
                        continue
                    try:
                        count = int(raw_count or 0)
                    except (TypeError, ValueError, OverflowError):
                        continue
                    if count <= 0:
                        continue
                    unit_price = max(1, int(fish_prices[item_name] * price_multiplier * fish_mult))
                    total_earned += unit_price * count
                    items_sold += count
                    sold_fish[item_name] = count
                for item_name in sold_fish:
                    fish_inventory.pop(item_name, None)

            if isinstance(hunt_inventory, dict):
                for item_name, raw_count in list(hunt_inventory.items()):
                    if item_name not in hunt_prices:
                        continue
                    try:
                        count = int(raw_count or 0)
                    except (TypeError, ValueError, OverflowError):
                        continue
                    if count <= 0:
                        continue
                    unit_price = max(1, int(hunt_prices[item_name] * price_multiplier * hunt_mult))
                    total_earned += unit_price * count
                    items_sold += count
                    sold_hunt[item_name] = count
                for item_name in sold_hunt:
                    hunt_inventory.pop(item_name, None)

            if items_sold > 0:
                _adjust_balance(econ, total_earned, reason='Продажа рыбы и охотничьих трофеев')
                mark_dirty()

    if items_sold == 0:
        bot.reply_to(message, "🎒 У вас нет рыбы или охотничьих трофеев из каталога для продажи! 😿")
        return

    if not critical_save('fish and hunt inventory sale', retries=3):
        # Reverse only this transaction's fields. A full-profile snapshot would
        # overwrite unrelated profile changes that occurred during disk/network IO.
        with BALANCE_TX_LOCK:
            with db_lock:
                for inv_key, sold in (('fish_inventory', sold_fish), ('hunt_inventory', sold_hunt)):
                    if not sold:
                        continue
                    current = econ.get(inv_key)
                    if not isinstance(current, dict):
                        current = {}
                        econ[inv_key] = current
                    for item_name, count in sold.items():
                        try:
                            existing = max(0, int(current.get(item_name, 0) or 0))
                        except (TypeError, ValueError, OverflowError):
                            existing = 0
                        current[item_name] = existing + count
                _adjust_balance(econ, -total_earned, reason='Откат не сохранённой продажи добычи')
                mark_dirty()
        critical_save('rollback fish and hunt inventory sale', retries=2)
        bot.reply_to(message, '⚠️ Не удалось сохранить продажу в Neon. Добыча и баланс восстановлены, попробуйте позже.')
        return

    rush_note = " (🌟 Золотая лихорадка x2.0!)" if gold_rush_event.get('active') else ""
    bot.reply_to(message, f"💰 Вы успешно продали добычу на сумму <b>+{total_earned:,} Ня-коинов 🪙</b>{rush_note}! 😻\nБаланс: <b>{econ['balance']:,} 🪙</b>", parse_mode='HTML')

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
