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


HANDLER_NAMES = ['cmd_garage', 'cmd_custom_title', 'cmd_stars', 'cmd_inventory', 'cmd_shop', 'cmd_tasks', 'cmd_halloween_pass', 'cmd_pharmacy', 'cmd_gift_stars']


def cmd_garage(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_garage_view(message.chat.id, user_id, user_name)

def cmd_custom_title(message):
    """Manage the permanent custom-title entitlement bought for 4 Telegram Stars."""
    if not can_process_user_message(message):
        return

    user = message.from_user
    user_id = user.id
    user_name = (f"{user.first_name or ''} {user.last_name or ''}").strip() or user.username or 'Пользователь'
    econ = get_user_econ(user_id, user_name, username=user.username)
    if not econ.get('has_custom_title_cert'):
        bot.reply_to(
            message,
            '❌ У вас нет права на кастомный титул. Купите «Кастомный титул навсегда» за 4 ⭐ в <code>/stars</code>.',
            parse_mode='HTML'
        )
        return

    # Backwards-compatible migration for players who set a title before this update.
    if not econ.get('custom_title_text') and econ.get('custom_title'):
        econ['custom_title_text'] = str(econ['custom_title'])
        mark_dirty()

    parts = (message.text or '').split(maxsplit=1)
    arg = parts[1].strip() if len(parts) > 1 else ''
    action = arg.casefold()
    # Prefix with 'set ' to use reserved words (on/off/delete) as the title itself.
    if action.startswith('set '):
        arg = arg[4:].strip()
        action = ''

    def save_changes(changes, reason):
        before = {key: econ.get(key) for key in changes}
        for key, value in changes.items():
            econ[key] = value
        mark_dirty()
        try:
            saved = critical_save(reason, retries=3)
        except Exception as exc:
            print(f'[CUSTOM TITLE SAVE ERROR] {reason}: {exc}')
            saved = False
        if saved:
            return True
        for key, value in before.items():
            econ[key] = value
        mark_dirty()
        bot.reply_to(
            message,
            '⚠️ Не удалось надёжно сохранить изменение в Neon. Изменение отменено, попробуйте позже.',
            parse_mode='HTML'
        )
        return False

    current = econ.get('custom_title')
    saved_title = econ.get('custom_title_text')
    if not arg:
        equipped_text = html.escape(str(current)) if current else 'нет'
        saved_text = html.escape(str(saved_title)) if saved_title else 'не создан'
        active_title_id = econ.get('active_title')
        active_text = html.escape(str(TITLES.get(active_title_id, {}).get('name', active_title_id))) if active_title_id else 'нет'
        bot.reply_to(
            message,
            '🌟 <b>ВАШ КАСТОМНЫЙ ТИТУЛ</b>\n━━━━━━━━━━━━━━━━━━━━\n'
            f'Сохранённый текст: <b>{saved_text}</b>\n'
            f'Сейчас надет: <b>{equipped_text}</b>\n'
            f'Обычный титул: <b>{active_text}</b>\n\n'
            'Создать или изменить: <code>/create_tittle Ваш титул</code>\n'
            'Для текста on/off/delete: <code>/create_tittle set off</code>\n'
            'Снять, не удаляя: <code>/create_tittle off</code>\n'
            'Надеть сохранённый: <code>/create_tittle on</code>\n'
            'Удалить сохранённый текст: <code>/create_tittle delete</code>',
            parse_mode='HTML'
        )
        return

    if action in {'off', 'none', 'remove', 'снять', 'выключить', '-'}:
        if not current:
            bot.reply_to(message, 'ℹ️ Кастомный титул уже снят. Сохранённый текст можно вернуть командой <code>/create_tittle on</code>.', parse_mode='HTML')
            return
        if save_changes({'custom_title': None}, 'custom title unequip'):
            bot.reply_to(message, '✅ Кастомный титул снят, но текст сохранён. Вернуть его можно командой <code>/create_tittle on</code>.', parse_mode='HTML')
        return

    if action in {'on', 'включить', 'надеть'}:
        saved_title = econ.get('custom_title_text') or current
        if not saved_title:
            bot.reply_to(message, '❌ У вас ещё нет сохранённого титула. Напишите <code>/create_tittle Ваш титул</code>.', parse_mode='HTML')
            return
        if current == saved_title and not econ.get('active_title'):
            bot.reply_to(message, f'ℹ️ Уже надет ваш титул: <b>{html.escape(str(saved_title))}</b>.', parse_mode='HTML')
            return
        if save_changes({'custom_title_text': saved_title, 'custom_title': saved_title, 'active_title': None}, 'custom title equip'):
            bot.reply_to(message, f'✅ Кастомный титул снова надет: <b>{html.escape(str(saved_title))}</b>', parse_mode='HTML')
        return

    if action in {'delete', 'удалить', 'стереть', 'clear'}:
        if not saved_title and not current:
            bot.reply_to(message, 'ℹ️ Сохранённого кастомного титула уже нет.', parse_mode='HTML')
            return
        if save_changes({'custom_title_text': None, 'custom_title': None}, 'custom title delete'):
            bot.reply_to(message, '✅ Текст кастомного титула удалён. Право на создание нового у вас осталось.', parse_mode='HTML')
        return

    title = ' '.join(arg.split())
    if len(title) < 1 or len(title) > 40:
        bot.reply_to(message, '❌ Титул должен содержать от 1 до 40 символов. Попробуйте ещё раз.')
        return
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in title):
        bot.reply_to(message, '❌ Титул содержит недопустимые управляющие символы.')
        return

    if save_changes({'custom_title_text': title, 'custom_title': title, 'active_title': None}, 'custom title create/equip'):
        bot.reply_to(
            message,
            f'🌟 <b>Кастомный титул сохранён и надет!</b>\n\n<b>{html.escape(title)}</b>\n\n'
            'Снять без удаления: <code>/create_tittle off</code>\n'
            'Надеть снова: <code>/create_tittle on</code>',
            parse_mode='HTML'
        )
def cmd_stars(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_stars_shop(message.chat.id, user_id, user_name, category='main')

def cmd_inventory(message):
    if not can_process_user_message(message): return
    uid=message.from_user.id; name=(f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ=get_user_econ(uid,name,username=message.from_user.username); pet=econ.get('pet'); pet_inventory=econ.get('pet_inventory',[]) or []
    titles=[TITLES[t]['text'] for t in econ.get('titles',[]) if t in TITLES]
    lines=['🎒 <b>ИНВЕНТАРЬ И КОЛЛЕКЦИЯ</b>','━━━━━━━━━━━━━━━━━━━━',f"🐾 Активный питомец: <b>{pet.get('name')}</b>" if pet else '🐾 Активный питомец: <i>нет</i>',f"🏅 Значки: {', '.join(map(str,econ.get('inventory',[]))) if econ.get('inventory') else 'нет'}",f"👑 Титулы: {', '.join(titles) if titles else 'нет'}",f"🎨 Темы: {', '.join(econ.get('purchased_themes',['default']))}",f"⭐️ Stars-предметы: {', '.join(econ.get('paid_stars_items',[])) if econ.get('paid_stars_items') else 'нет'}",f"🐾 Коллекция питомцев: <b>{len(pet_inventory)}</b> — {', '.join(PETS_DATA[x]['name'] for x in pet_inventory if x in PETS_DATA) if pet_inventory else 'нет'}",'━━━━━━━━━━━━━━━━━━━━','💡 Питомцев можно менять в зоомагазине без повторной покупки.']
    bot.reply_to(message,'\n'.join(lines),parse_mode='HTML')

def cmd_shop(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    send_shop_menu(message.chat.id, message.from_user.id, user_name)

def cmd_tasks(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    bot.reply_to(message, format_daily_tasks(message.from_user.id, user_name), parse_mode='HTML')

def cmd_halloween_pass(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_halloween_bp_view(message.chat.id, user_id, user_name)

def cmd_pharmacy(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_pharmacy_view(message.chat.id, user_id, user_name)

def cmd_gift_stars(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    chat_id = message.chat.id

    target_user, target_user_id, _ = parse_target_and_args(message, '/gift_stars')
    if not target_user:
        target_user, target_user_id, _ = parse_target_and_args(message, 'подарить_звезды')

    if not target_user or not target_user_id:
        bot.reply_to(message, "🎁 <b>КАК ПОДАРИТЬ УСЛУГУ ЗА ЗВЁЗДЫ ДРУГУ:</b>\n━━━━━━━━━━━━━━━━━━━━\nУкажите друга: <code>/gift_stars @username</code> или ответом на его сообщение! 😺", parse_mode='HTML')
        return

    if target_user_id == user_id:
        bot.reply_to(message, "❌ Для покупки себе используйте <code>/stars</code>! 😸", parse_mode='HTML')
        return

    t_link = make_link(chat_id, target_user, target_user_id, ping=False)
    markup = InlineKeyboardMarkup(row_width=1)
    # Все платные товары Stars можно подарить. Callback хранит тип + ID товара + получателя + плательщика.
    for item_key, item in STARS_COIN_PACKS.items():
        stars = int(item.get('stars', 0))
        if stars >= 1:
            markup.add(InlineKeyboardButton(
                f"🎁 {item['name']} — {stars} ⭐️",
                callback_data=f"gift2|coins|{item_key}|{target_user_id}|{user_id}"
            ))
    for item_key, item in STARS_VIP_PASS.items():
        stars = int(item.get('stars', 0))
        if stars >= 1:
            markup.add(InlineKeyboardButton(
                f"🎁 {item['name']} — {stars} ⭐️",
                callback_data=f"gift2|pass|{item_key}|{target_user_id}|{user_id}"
            ))
    for item_key, item in STARS_COSMETICS.items():
        if item_key in STARS_HARD_LIMITED_ITEMS:
            continue
        stars = int(item.get('stars', 0))
        if stars >= 1:
            markup.add(InlineKeyboardButton(
                f"🎁 {item['name']} — {stars} ⭐️",
                callback_data=f"gift2|cosm|{item_key}|{target_user_id}|{user_id}"
            ))
    # Три новые позиции с общим лимитом 5.
    for item_key in STARS_HARD_LIMITED_ITEMS:
        item = STARS_COSMETICS.get(item_key, STARS_HARD_LIMITED_ITEMS[item_key])
        stars = int(item.get('stars', 0))
        remaining = stars_hard_limited_available(item_key)
        if stars >= 1 and remaining > 0:
            markup.add(InlineKeyboardButton(
                f"🎁 {item['name']} — {stars} ⭐️ (осталось {remaining}/5)",
                callback_data=f"gift2|cosm|{item_key}|{target_user_id}|{user_id}"
            ))
    # Десять визуальных эффектов всегда доступны и тоже можно дарить.
    for item_key, item in STARS_LIMITED_ITEMS.items():
        stars = int(item.get('stars', 0))
        if stars >= 1:
            markup.add(InlineKeyboardButton(
                f"🎁 {item['name']} — {stars} ⭐️",
                callback_data=f"gift2|cosm|{item_key}|{target_user_id}|{user_id}"
            ))

    bot.reply_to(
        message,
        f"🎁 <b>ВЫБЕРИТЕ ПОДАРОК ЗА ЗВЁЗДЫ ДЛЯ {t_link}</b> ⭐️ 😻\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Оплата спишется с вашего баланса Telegram Stars, а товар мгновенно поступит на аккаунт друга! 😸",
        reply_markup=markup,
        parse_mode='HTML'
    )

def register(ctx, only=None):
    """Register selected handlers from this feature module."""
    _inject(ctx)
    bot = ctx["bot"]
    wanted = set(only) if only is not None else set(HANDLER_NAMES)
    registered = []
    if "cmd_garage" in wanted:
        _handler = cmd_garage
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['garage', 'гараж'])(_handler)
        ctx["cmd_garage"] = _handler
        globals()["cmd_garage"] = _handler
        registered.append("cmd_garage")
    if "cmd_custom_title" in wanted:
        _handler = cmd_custom_title
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['create_tittle', 'create_title', 'custom_title', 'кастомный_титул'])(_handler)
        ctx["cmd_custom_title"] = _handler
        globals()["cmd_custom_title"] = _handler
        registered.append("cmd_custom_title")
    if "cmd_stars" in wanted:
        _handler = cmd_stars
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['stars', 'donate', 'vip', 'донат', 'звезды', 'пасс'])(_handler)
        ctx["cmd_stars"] = _handler
        globals()["cmd_stars"] = _handler
        registered.append("cmd_stars")
    if "cmd_inventory" in wanted:
        _handler = cmd_inventory
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['inventory', 'инвентарь', 'инв'])(_handler)
        ctx["cmd_inventory"] = _handler
        globals()["cmd_inventory"] = _handler
        registered.append("cmd_inventory")
    if "cmd_shop" in wanted:
        _handler = cmd_shop
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['shop', 'магазин'])(_handler)
        ctx["cmd_shop"] = _handler
        globals()["cmd_shop"] = _handler
        registered.append("cmd_shop")
    if "cmd_tasks" in wanted:
        _handler = cmd_tasks
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['tasks', 'задания', 'квесты'])(_handler)
        ctx["cmd_tasks"] = _handler
        globals()["cmd_tasks"] = _handler
        registered.append("cmd_tasks")
    if "cmd_halloween_pass" in wanted:
        _handler = cmd_halloween_pass
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['pass', 'bp', 'хеллоуин', 'battle_pass'])(_handler)
        ctx["cmd_halloween_pass"] = _handler
        globals()["cmd_halloween_pass"] = _handler
        registered.append("cmd_halloween_pass")
    if "cmd_pharmacy" in wanted:
        _handler = cmd_pharmacy
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['pharmacy', 'аптека', 'больница'])(_handler)
        ctx["cmd_pharmacy"] = _handler
        globals()["cmd_pharmacy"] = _handler
        registered.append("cmd_pharmacy")
    if "cmd_gift_stars" in wanted:
        _handler = cmd_gift_stars
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['gift_stars', 'подарить_звезды', 'подарок_звезды'])(_handler)
        ctx["cmd_gift_stars"] = _handler
        globals()["cmd_gift_stars"] = _handler
        registered.append("cmd_gift_stars")
    return registered
