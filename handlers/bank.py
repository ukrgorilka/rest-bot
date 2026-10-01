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


HANDLER_NAMES = ['cmd_loan', 'cmd_repay', 'cmd_bank', 'cmd_case', 'cmd_lottery', 'cmd_history', 'cmd_safe']


def cmd_loan(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    
    loan = econ.setdefault('loan', {'amount': 0, 'due': 0, 'defaulted': False})
    
    if loan.get('amount', 0) > 0:
        due_date = datetime.fromtimestamp(loan['due'], tz=MSK_TZ).strftime('%d.%m.%Y %H:%M')
        bot.reply_to(message, f"❌ У вас уже есть активный кредит на <b>{loan['amount']} 🪙</b>! 😾\nОплатите его до {due_date} (команда: <code>/repay</code>).", parse_mode='HTML')
        return
        
    if loan.get('defaulted'):
        bot.reply_to(message, "❌ Ваша кредитная история испорчена (Вы в черном списке банка)! 🙀", parse_mode='HTML')
        return

    m = re.search(r'(?:/loan|кредит)\s*(\d+)?', message.text, re.IGNORECASE)
    amount = int(m.group(1)) if m and m.group(1) else 0
    
    lvl, _, _, _ = get_account_level(econ.get('account_exp', 0))
    max_loan = lvl * 1500
    
    if amount <= 0:
        bot.reply_to(message, f"🏦 <b>КРЕДИТНЫЙ ОТДЕЛ НЯ-БАНКА</b> 😺\n\nВам доступен кредит до <b>{max_loan} 🪙</b> (на 24 часа).\nСумма возврата будет на 15% больше!\n\nДля оформления введите: <code>/loan {max_loan}</code> 😸", parse_mode='HTML')
        return
        
    if amount > max_loan:
        bot.reply_to(message, f"❌ Банк не одобрил такую сумму! Максимум для вашего {lvl} уровня: <b>{max_loan} 🪙</b>. 😿", parse_mode='HTML')
        return
        
    repay_amount = int(amount * 1.15)
    _adjust_balance(econ, amount)
    econ['loan'] = {
        'amount': repay_amount,
        'due': time.time() + 86400,
        'defaulted': False
    }
    mark_dirty()
    
    bot.reply_to(message, f"✅ <b>КРЕДИТ ОДОБРЕН!</b> 😸\n\nВы получили <b>{amount} 🪙</b>.\nВам нужно вернуть <b>{repay_amount} 🪙</b> в течение 24 часов (команда <code>/repay</code>), иначе вмешаются коллекторы! 🙀", parse_mode='HTML')

def cmd_repay(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    
    loan = econ.get('loan', {})
    if loan.get('amount', 0) <= 0:
        bot.reply_to(message, "У вас нет активных кредитов! 😸")
        return
        
    amount_to_pay = loan['amount']
    if econ['balance'] < amount_to_pay:
        bot.reply_to(message, f"❌ Недостаточно средств для погашения! Нужно <b>{amount_to_pay} 🪙</b>, у вас: {econ['balance']}. 😿", parse_mode='HTML')
        return
        
    _adjust_balance(econ, -(amount_to_pay))
    econ['loan'] = {'amount': 0, 'due': 0, 'defaulted': False}
    mark_dirty()
    bot.reply_to(message, f"✅ Кредит успешно погашен! Списано <b>{amount_to_pay} 🪙</b>. Ваша кредитная история чиста. 😻", parse_mode='HTML')

def cmd_bank(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_bank_view(message.chat.id, message.from_user.id, user_name)

def cmd_case(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    now = time.time()
    last_case = econ.get('last_case_time', 0)
    chest_claims = db.setdefault('chest_claims', {})
    previous = chest_claims.get(str(user_id), {}).get('date')
    cooldown = 86400

    left = cooldown_text(last_case, cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Бесплатный кейс доступен раз в 24 часа!\nДо следующего открытия: <b>{left}</b>. 😿", parse_mode='HTML')
        return

    econ['last_case_time'] = now
    today = daily_task_date()
    yesterday = (now_msk() - timedelta(days=1)).strftime('%Y-%m-%d')
    econ['chest_streak'] = econ.get('chest_streak', 0) + 1 if previous == yesterday else 1
    chest_claims[str(user_id)] = {'date': today, 'streak': econ['chest_streak']}

    roll = random.random()
    if roll < 0.50:
        coins_reward = random.randint(80, 250)
        _adjust_balance(econ, coins_reward)
        prize_str = f"💰 <b>+{coins_reward} Ня-коинов 🪙</b>"
    elif roll < 0.75:
        exp_reward = random.randint(30, 80)
        econ['work_exp'] = econ.get('work_exp', 0) + exp_reward
        prize_str = f"🎓 <b>+{exp_reward} EXP опыта работы</b>"
    elif roll < 0.90:
        trophy = random.choice(FISH_TYPES)[0]
        add_inventory_item(econ['fish_inventory'], trophy)
        prize_str = f"🐟 Редкий улов: <b>{trophy}</b>"
    else:
        trophy = random.choice(HUNT_TYPES)[0]
        add_inventory_item(econ['hunt_inventory'], trophy)
        prize_str = f"🏹 Охотничий трофей: <b>{trophy}</b>!"

    add_account_exp(user_id, user_name, 20, username=message.from_user.username)
    if econ.get('chest_streak', 0) >= 3:
        streak_bonus = min(1000, econ['chest_streak'] * 100)
        _adjust_balance(econ, streak_bonus)
        prize_str += f"\n🔥 Серия сундуков {econ['chest_streak']} дн.: <b>+{streak_bonus} 🪙</b>"
    check_achievements(user_id, user_name, 'cases_opened', 1, message.chat.id, username=message.from_user.username)
    mark_dirty()

    bot.reply_to(
        message,
        f"📦 <b>ВЫ ОТКРЫЛИ ЕЖЕДНЕВНЫЙ СУНДУК!</b> 😺\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎉 Ваша награда: {prize_str}\n"
        f"⭐ Опыт аккаунта: <b>+20 EXP</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Возвращайтесь за новым сундуком завтра! 😸",
        parse_mode='HTML'
    )

def cmd_lottery(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_lottery_view(message.chat.id, message.from_user.id, user_name)

def cmd_history(message):
    if not can_process_user_message(message):
        return
    chat_id = message.chat.id
    str_chat = str(chat_id)
    target_user, target_user_id, _ = parse_target_and_args(message, '/history')
    if not target_user: target_user, target_user_id, _ = parse_target_and_args(message, 'история')

    if not target_user:
        target_user = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
        target_user_id = message.from_user.id

    clean_u = clean_tag(target_user)
    hist_entries = db.get('history', {}).get(str_chat, {}).get(clean_u, [])

    if not hist_entries:
        bot.reply_to(message, f"📜 История рестов для <b>{html.escape(clean_u)}</b> в этом чате пуста! 😿", parse_mode='HTML')
        return

    lines = [f"📜 <b>ИСТОРИЯ РЕСТОВ: {make_link(chat_id, clean_u, target_user_id, ping=False)}</b> 😺", "━━━━━━━━━━━━━━━━━━━━"]
    for idx, item in enumerate(reversed(hist_entries[-8:]), 1):
        lines.append(
            f"<b>{idx}. {item.get('action', 'Рест')}</b> ({item.get('date', '—')})\n"
            f"⏱ Срок: <code>{item.get('duration', '—')}</code> | Причина: <i>{item.get('reason', 'Не указана')}</i>\n"
        )
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')

def cmd_safe(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    chat_id = message.chat.id

    in_j, left_j = is_in_jail(user_id)
    if in_j:
        bot.reply_to(message, f"🔒 Вы отбываете срок в КПЗ! До выхода: <b>{left_j} мин.</b> 😿", parse_mode='HTML')
        return

    safe = get_chat_safe(chat_id)
    pot = safe.get('pot', 30000)
    tried = safe.setdefault('tried_codes', [])

    parts = message.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(
            message,
            f"🔒 <b>СЕЙФ ЧАТА (4-ЗНАЧНЫЙ ШИФР)</b> 🏦 😺\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Накопленный банк сейфа: <b>{pot:,} Ня-коинов 🪙</b>!\n"
            f"<i>(В сейф отчисляется 50% от всех проигрышей чата в казино и спорте!)</i> 😻\n\n"
            f"📝 Уже опробовано комбинаций: <b>{len(tried)}</b>\n"
            f"💡 Чтобы попробовать угадать шифр (раз в 20 мин):\n"
            f"👉 <code>/safe 4815</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode='HTML'
        )
        return

    code_entered = parts[1].strip()
    if not (len(code_entered) == 4 and code_entered.isdigit()):
        bot.reply_to(message, "❌ Код сейфа должен состоять ровно из 4 цифр (от 0000 до 9999)!\nПример: <code>/safe 4815</code> 😾", parse_mode='HTML')
        return

    now = time.time()
    u_link = make_link(chat_id, user_name, user_id, ping=True)
    result, value, pot_after = atomic_safe_attempt(
        chat_id, econ, code_entered, user_id, user_name, message.from_user.username, now
    )
    if result == 'cooldown':
        bot.reply_to(message, f"⏳ Руки дрожат от отмычек! Следующая попытка через: <b>{value}</b>. 😿", parse_mode='HTML')
        return
    if result == 'duplicate':
        bot.reply_to(message, f"❌ <b>Этот код уже писали!</b> Комбинацию <code>{code_entered}</code> уже кто-то вводил, и она оказалась неверной. Попробуйте другой код! 😿\n💰 В сейфе: <b>{pot_after:,} 🪙</b>", parse_mode='HTML')
        return
    if result == 'win':
        won_pot = int(value or 0)
        log_event('СЕЙФ ВЗЛОМАН', f'Игрок {u_link} подобрал шифр <b>{code_entered}</b> и сорвал джекпот <b>{won_pot:,} 🪙</b>!')
        win_msg = (
            f"🎉💥🔓 <b>СЕЙФ УСПЕШНО ВЗЛОМАН!</b> 😻\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Мега-медвежатник: {u_link}\n"
            f"🔑 Верный шифр: <b>{code_entered}</b>\n"
            f"💰 Сорванный куш: <b>+{won_pot:,} Ня-коинов 🪙</b>! 🙀\n"
            f"⭐ Опыт: <b>+200 EXP</b> | Карма: <b>+5</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Замки заменены на новые, в сейф заложен стартовый фонд 15,000 🪙! Охота продолжается!</i> 😸"
        )
        bot.send_message(chat_id, win_msg, parse_mode='HTML')
        return

    bot.reply_to(
        message,
        f"❌ <b>Щёлк! Код {code_entered} не подошёл!</b> 😿\n"
        f"Этот код добавлен в список неудачных попыток.\n"
        f"💰 Текущий банк сейфа: <b>{pot_after:,} 🪙</b> (ждёт своего победителя!)\n"
        f"⏳ Повторная попытка доступна через 20 минут.",
        parse_mode='HTML'
    )

def register(ctx, only=None):
    """Register selected handlers from this feature module."""
    _inject(ctx)
    bot = ctx["bot"]
    wanted = set(only) if only is not None else set(HANDLER_NAMES)
    registered = []
    if "cmd_loan" in wanted:
        _handler = cmd_loan
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['loan', 'кредит'])(_handler)
        ctx["cmd_loan"] = _handler
        globals()["cmd_loan"] = _handler
        registered.append("cmd_loan")
    if "cmd_repay" in wanted:
        _handler = cmd_repay
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['repay', 'погасить'])(_handler)
        ctx["cmd_repay"] = _handler
        globals()["cmd_repay"] = _handler
        registered.append("cmd_repay")
    if "cmd_bank" in wanted:
        _handler = cmd_bank
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['bank', 'банк', 'депозит'])(_handler)
        ctx["cmd_bank"] = _handler
        globals()["cmd_bank"] = _handler
        registered.append("cmd_bank")
    if "cmd_case" in wanted:
        _handler = cmd_case
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['case', 'кейс', 'сундук', 'chest', 'чест'])(_handler)
        ctx["cmd_case"] = _handler
        globals()["cmd_case"] = _handler
        registered.append("cmd_case")
    if "cmd_lottery" in wanted:
        _handler = cmd_lottery
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['lottery', 'лотерея'])(_handler)
        ctx["cmd_lottery"] = _handler
        globals()["cmd_lottery"] = _handler
        registered.append("cmd_lottery")
    if "cmd_history" in wanted:
        _handler = cmd_history
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['history', 'история'])(_handler)
        ctx["cmd_history"] = _handler
        globals()["cmd_history"] = _handler
        registered.append("cmd_history")
    if "cmd_safe" in wanted:
        _handler = cmd_safe
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['safe', 'сейф'])(_handler)
        ctx["cmd_safe"] = _handler
        globals()["cmd_safe"] = _handler
        registered.append("cmd_safe")
    return registered
