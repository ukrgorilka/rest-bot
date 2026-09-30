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


HANDLER_NAMES = ['send_welcome', 'cmd_settings', 'cmd_profile_settings', 'cmd_biometry', 'cmd_profile', 'cmd_achievements', 'cmd_balance', 'cmd_top_daily', 'cmd_top_weekly', 'cmd_top', 'cmd_activity']


def send_welcome(message):
    if not can_process_user_message(message):
        return
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📚 ЧИТАТЬ ПОЛНЫЙ ГАЙД В TELETYPE 🌐", url="https://teletype.in/@ukrgorilka/Nya")
    )
    
    welcome_text = (
        "🤖 <b>ГЛАВНЫЙ НАВИГАТОР НЯ-БОТА</b> 😺\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Добро пожаловать! Все команды, механики экономики, рестов, бизнесов и игр собраны в официальном руководстве: 😻\n\n"
        "📖 <b>Официальный Teletype гайд:</b>\n"
        "👉 https://teletype.in/@ukrgorilka/Nya\n\n"
        "🎁 <b>Активируйте промокод:</b> <code>/promo FIX</code> на <b>5,000 🪙</b>!\n"
        "\n💰 <b>БЫСТРЫЕ РУССКИЕ КОМАНДЫ</b>\n"
        "• <code>баланс</code> / <code>профиль</code> / <code>магазин</code>\n"
        "• <code>передать 10000</code> — ответом на сообщение\n"
        "• <code>передать @username 10000</code> — перевод игроку\n"
        "• <code>банк</code> / <code>банк положить 5000</code> / <code>банк снять 5000</code>\n"
        "• <code>кредит 5000</code> / <code>погасить</code> / <code>кейс</code> / <code>задания</code>\n"
        "• <code>работа</code> / <code>бизнес</code> / <code>прибыль</code> / <code>сад</code>\n"
        "• <code>топ</code> / <code>ачивки</code> / <code>инвентарь</code>\n"
        "\n💡 <i>Есть крутые идеи или нашли баг? Напишите создателю:</i> @ukrgorilka ✨\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👇 <i>Нажмите кнопку ниже, чтобы открыть статью:</i> 😸"
    )
    try:
        bot.reply_to(message, welcome_text, parse_mode='HTML')
    except Exception:
        pass

def cmd_settings(message):
    if not can_process_user_message(message): return
    if getattr(message.chat,'type','') == 'private':
        render_private_settings(message.chat.id,message.from_user.id)
        return
    if not is_admin(message.chat.id,message.from_user.id):
        bot.reply_to(message,'❌ Настройки группы доступны только администраторам чата! 😾')
        return
    render_settings_view(message.chat.id,message.from_user.id)

def cmd_profile_settings(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_profile_settings_view(message.chat.id, user_id, user_name)

def cmd_biometry(message):
    if not can_process_user_message(message): return
    econ=get_user_econ(message.from_user.id, clean_tag(message.from_user.first_name or message.from_user.username), username=message.from_user.username)
    text=(
        "📊 <b>БИОМЕТРИЯ И ЗАМЕРЫ</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🍆 Писюн: <b>{econ.get('dick_size',15)} см</b> | 💦 Фап: <b>{econ.get('fap_count',0)}</b>\n"
        f"🧬 Хромосомы: <b>{econ.get('chromosomes',46)}</b> | 🧠 IQ: <b>{econ.get('iq',100)}</b>\n"
        f"🥩 Жир: <b>{econ.get('fat',20)}%</b> | 🦶 Пятка: <b>{econ.get('foot_size',25)} см</b>\n"
        f"😎 Могнул: <b>{econ.get('mog_count',0)}</b> раз(а)\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Здесь собраны биометрия и симулятор Могера. Основной профиль теперь компактный."
    )
    bot.reply_to(message,text,parse_mode='HTML')

def cmd_profile(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    send_user_profile(message.chat.id, user_name, message.from_user.id, message_to_reply=message, username=message.from_user.username)

def cmd_achievements(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    unlocked = econ.get('achievements', [])

    lines = [f"🏆 <b>ДОСТИЖЕНИЯ: {make_link(message.chat.id, user_name, user_id, ping=False)}</b> 😺", "━━━━━━━━━━━━━━━━━━━━"]
    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id in unlocked: lines.append(f"✅ <b>{ach['title']}</b> — {ach['desc']} (+{ach['reward']} 🪙)")
        else: lines.append(f"🔒 <b>{ach['title']}</b> — {ach['desc']} (<b>+{ach['reward']} 🪙</b>)")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"Прогресс: <b>{len(unlocked)}/{len(ACHIEVEMENTS)}</b> открыто. 😸")
    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')

def cmd_balance(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(message.from_user.id, user_name, username=message.from_user.username)
    streak_info = f"\n🔥 <b>Ежедневный стрик:</b> {econ.get('bonus_streak', 0)} дн."
    bot.reply_to(message, f"💵 <b>Ваш кошелек:</b> <b>{econ['balance']} Ня-коинов 💸</b>\n🏦 <b>В банке:</b> <b>{econ.get('bank_deposit', 0)} 🪙</b>{streak_info} 😺", parse_mode='HTML')

def cmd_top_daily(message):
    if can_process_user_message(message): render_activity_leaderboard(message.chat.id,'day')

def cmd_top_weekly(message):
    if can_process_user_message(message): render_activity_leaderboard(message.chat.id,'week')

def cmd_top(message):
    if not can_process_user_message(message):
        return
    render_top_menu(message.chat.id, user_id=message.from_user.id, category='rich')

def cmd_activity(message):
    if not _owner_only(message): return
    items=_bot_chat_items(True)[:20]
    lines=['📈 <b>ПОСЛЕДНЯЯ АКТИВНОСТЬ ГРУПП</b>','━━━━━━━━━━━━━━━━━━━━']
    for i,x in enumerate(items,1):
        last=x.get('last_activity',x.get('last_seen',0)); ago=_fmt_duration(time.time()-last) if last else 'нет данных'
        lines.append(f"{i}. 🟢 <b>{html.escape(str(x.get('title') or 'Без названия'))}</b>\n   🕐 {ago} назад · 🆔 <code>{x.get('chat_id')}</code>")
    bot.reply_to(message,'\n'.join(lines) if items else '📈 <b>Активность</b>\n\nАктивных групп пока нет.',parse_mode='HTML')

def register(ctx, only=None):
    """Register selected handlers from this feature module."""
    _inject(ctx)
    bot = ctx["bot"]
    wanted = set(only) if only is not None else set(HANDLER_NAMES)
    registered = []
    if "send_welcome" in wanted:
        _handler = send_welcome
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['start', 'help', 'menu', 'info'])(_handler)
        ctx["send_welcome"] = _handler
        globals()["send_welcome"] = _handler
        registered.append("send_welcome")
    if "cmd_settings" in wanted:
        _handler = cmd_settings
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['settings', 'настройки'])(_handler)
        ctx["cmd_settings"] = _handler
        globals()["cmd_settings"] = _handler
        registered.append("cmd_settings")
    if "cmd_profile_settings" in wanted:
        _handler = cmd_profile_settings
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['profile_settings', 'set_profile', 'настройки_профиля', 'налаштування_профілю'])(_handler)
        ctx["cmd_profile_settings"] = _handler
        globals()["cmd_profile_settings"] = _handler
        registered.append("cmd_profile_settings")
    if "cmd_biometry" in wanted:
        _handler = cmd_biometry
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['biometry', 'биометрия', 'замеры'])(_handler)
        ctx["cmd_biometry"] = _handler
        globals()["cmd_biometry"] = _handler
        registered.append("cmd_biometry")
    if "cmd_profile" in wanted:
        _handler = cmd_profile
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['profile', 'профиль'])(_handler)
        ctx["cmd_profile"] = _handler
        globals()["cmd_profile"] = _handler
        registered.append("cmd_profile")
    if "cmd_achievements" in wanted:
        _handler = cmd_achievements
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['achievements', 'ачивки'])(_handler)
        ctx["cmd_achievements"] = _handler
        globals()["cmd_achievements"] = _handler
        registered.append("cmd_achievements")
    if "cmd_balance" in wanted:
        _handler = cmd_balance
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['balance', 'баланс'])(_handler)
        ctx["cmd_balance"] = _handler
        globals()["cmd_balance"] = _handler
        registered.append("cmd_balance")
    if "cmd_top_daily" in wanted:
        _handler = cmd_top_daily
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['top_daily', 'топ_день'])(_handler)
        ctx["cmd_top_daily"] = _handler
        globals()["cmd_top_daily"] = _handler
        registered.append("cmd_top_daily")
    if "cmd_top_weekly" in wanted:
        _handler = cmd_top_weekly
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['top_weekly', 'топ_неделя'])(_handler)
        ctx["cmd_top_weekly"] = _handler
        globals()["cmd_top_weekly"] = _handler
        registered.append("cmd_top_weekly")
    if "cmd_top" in wanted:
        _handler = cmd_top
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['top', 'топ'])(_handler)
        ctx["cmd_top"] = _handler
        globals()["cmd_top"] = _handler
        registered.append("cmd_top")
    if "cmd_activity" in wanted:
        _handler = cmd_activity
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['activity', 'активность'])(_handler)
        ctx["cmd_activity"] = _handler
        globals()["cmd_activity"] = _handler
        registered.append("cmd_activity")
    return registered
