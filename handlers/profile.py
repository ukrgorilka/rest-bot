"""Extracted Telegram handlers for staged NyaBot architecture.

The handlers keep their original function bodies. During migration, register(ctx)
receives the legacy newfile.py globals so business logic and shared state remain
unchanged.
"""

from __future__ import annotations

from core.ui import badge_prefix, card, progress_bar


def _inject(ctx):
    for _name, _value in ctx.items():
        if _name not in {"__name__", "__package__", "__loader__", "__spec__", "__cached__", "__builtins__"}:
            globals()[_name] = _value


HANDLER_NAMES = ['send_welcome', 'cmd_settings', 'cmd_profile_settings', 'cmd_biometry', 'cmd_profile', 'cmd_achievements', 'cmd_balance', 'cmd_top_daily', 'cmd_top_weekly', 'cmd_top', 'cmd_activity']


def send_welcome(message):
    if not can_process_user_message(message):
        return
    try:
        record_started_user(message.from_user.id, getattr(message.from_user, 'username', None), getattr(message.from_user, 'first_name', None))
    except Exception:
        pass
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📚 Полный гайд в Teletype", url="https://teletype.in/@ukrgorilka/Nya")
    )
    markup.row(
        InlineKeyboardButton("📖 Меню команд", callback_data="v1:help:econ"),
        InlineKeyboardButton("🚀 Обновление v1.0", callback_data="v1:upd:latest"),
    )

    welcome_text = card(
        "🤖 <b>Добро пожаловать в NyaBot!</b> 😺",
        body=[
            "Все механики экономики, рестов, бизнесов, игр и отношений собраны здесь.",
            "🎁 Стартовый промокод: <code>/promo FIX</code> → <b>+5,000 🪙</b>",
            "📖 Гайд: https://teletype.in/@ukrgorilka/Nya",
        ],
        expandable=[
            "💰 <b>Быстрые русские команды (нажми, чтобы раскрыть):</b>",
            "• <code>баланс</code> · <code>профиль</code> · <code>дейли</code> · <code>собрать всё</code>",
            "• <code>передать 10000</code> (ответом) или <code>передать @username 10000</code>",
            "• <code>банк</code> · <code>банк положить 5000</code> · <code>банк снять 5000</code>",
            "• <code>работа</code> · <code>бизнес</code> · <code>биржа</code> · <code>торговец</code> · <code>сад</code>",
            "• <code>отн</code> · <code>дуэль @user 500</code> · <code>ограбление</code> · <code>+реп</code>",
            "• <code>/help</code> · <code>/update</code> · <code>чек</code> · <code>бейдж</code>",
        ],
        footer="💡 Идеи или баги — @ukrgorilka · Открой меню кнопками ниже 👇",
    )
    try:
        bot.reply_to(message, welcome_text, parse_mode='HTML', reply_markup=markup, disable_web_page_preview=True)
    except Exception:
        pass

def cmd_settings(message):
    if not can_process_user_message(message): return
    if getattr(message.chat,'type','') == 'private':
        render_private_settings(message.chat.id,message.from_user.id)
        return
    if not can_admin_action(message.chat.id,message.from_user.id,'settings'):
        bot.reply_to(message,'❌ Недостаточно прав для настроек или функции админов отключены! 😾')
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
    text = card(
        "📊 <b>Биометрия и замеры</b>",
        body=[
            f"🍆 Писюн: <b>{econ.get('dick_size',15)} см</b> · 🍒 Сиськи: <b>{econ.get('boobs_size',2)} разм.</b>",
            f"💦 Фап: <b>{econ.get('fap_count',0)}</b> · 😎 Могнул: <b>{econ.get('mog_count',0)}</b> раз(а)",
            f"🧬 Хромосомы: <b>{econ.get('chromosomes',46)}</b> · 🧠 IQ: <b>{econ.get('iq',100)}</b>",
            f"🥩 Жир: <b>{econ.get('fat',20)}%</b> · 🦶 Пятка: <b>{econ.get('foot_size',25)} см</b>",
        ],
        footer="<i>Здесь собраны биометрия и симулятор Могера.</i>",
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

    unlocked_lines = []
    locked_lines = []
    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id in unlocked:
            unlocked_lines.append(f"✅ <b>{ach['title']}</b> — {ach['desc']} (+{ach['reward']} 🪙)")
        else:
            locked_lines.append(f"🔒 <b>{ach['title']}</b> — {ach['desc']} (+{ach['reward']} 🪙)")
    bar = progress_bar(len(unlocked), max(1, len(ACHIEVEMENTS)), width=10)
    body = [f"Прогресс: <b>{len(unlocked)}/{len(ACHIEVEMENTS)}</b> · {bar}"]
    if unlocked_lines:
        body.append("")
        body.extend(unlocked_lines)
    else:
        body.append("Пока нет открытых достижений — всё впереди!")
    exp = ["🔒 <b>Закрытые достижения (нажми, чтобы раскрыть):</b>", *locked_lines] if locked_lines else None
    text = card(
        f"🏆 <b>Достижения: {make_link(message.chat.id, user_name, user_id, ping=False)}</b>",
        body=body,
        expandable=exp,
        footer="🏅 Выбрать значок для профиля: <code>бейдж</code>",
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🏅 Выбрать бейдж", callback_data=f"v1:badge:menu:{user_id}"))
    bot.reply_to(message, text, parse_mode='HTML', reply_markup=markup)

def cmd_balance(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(message.from_user.id, user_name, username=message.from_user.username)
    badge = badge_prefix(econ, globals().get('ACHIEVEMENTS'))
    rep = int(econ.get('reputation', 0) or 0)
    bal_text = card(
        f"💳 <b>{badge}Кошелёк и банк</b>",
        body=[
            f"💵 На руках: <b>{int(econ.get('balance', 0)):,} 🪙</b>",
            f"🏦 В банке: <b>{int(econ.get('bank_deposit', 0)):,} 🪙</b>",
            f"🔥 Стрик бонуса: <b>{int(econ.get('bonus_streak', 0))} дн.</b> · ⭐ Репутация: <b>{rep}</b>",
        ],
        footer="💡 Быстро: <code>банк положить 5000</code> · <code>банк снять 5000</code>",
    )
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("📥 В банк", callback_data=f"v1:bal:dep:{message.from_user.id}"),
        InlineKeyboardButton("📤 Снять", callback_data=f"v1:bal:wd:{message.from_user.id}"),
    )
    markup.row(
        InlineKeyboardButton("📋 Дейли", callback_data=f"v1:daily:open:{message.from_user.id}"),
        InlineKeyboardButton("🧾 Чек 24ч", callback_data=f"v1:check:open:{message.from_user.id}"),
    )
    bot.reply_to(message, bal_text, parse_mode='HTML', reply_markup=markup)

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
        bot.message_handler(commands=['start', 'menu', 'info'])(_handler)
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
