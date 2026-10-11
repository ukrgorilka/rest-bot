"""Extracted Telegram handlers for staged NyaBot architecture.

The handlers keep their original function bodies. During migration, register(ctx)
receives the legacy newfile.py globals so business logic and shared state remain
unchanged.
"""

from __future__ import annotations

import time


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
    """Create custom titles through a 4-Star invoice; manage owned titles for free."""
    if not can_process_user_message(message):
        return

    user = message.from_user
    user_id = int(user.id)
    user_name = (f"{user.first_name or ''} {user.last_name or ''}").strip() or user.username or 'Пользователь'
    econ = get_user_econ(user_id, user_name, username=user.username)
    parts = (message.text or '').split(maxsplit=1)
    arg = parts[1].strip() if len(parts) > 1 else ''
    action = arg.casefold()
    if action.startswith('set '):
        arg = arg[4:].strip()
        action = ''

    titles = econ.setdefault('custom_titles', [])
    if not isinstance(titles, list):
        titles = []
        econ['custom_titles'] = titles

    # Migrate a legacy single-title save without dropping the equipped title.
    legacy_text = econ.get('custom_title_text') or econ.get('custom_title')
    if legacy_text and not econ.get('custom_title_text'):
        econ['custom_title_text'] = str(legacy_text)
        mark_dirty()
    if legacy_text and not any(isinstance(t, dict) and t.get('text') == str(legacy_text) for t in titles):
        legacy_id = str(econ.get('custom_title_id') or 'ct_legacy')
        titles.append({'id': legacy_id, 'text': str(legacy_text), 'created_at': 0, 'legacy': True})
        econ['custom_title_id'] = legacy_id
        econ['custom_title_credit_used'] = True
        mark_dirty()

    def save_changes(changes, reason):
        before = {key: __import__('copy').deepcopy(econ.get(key)) for key in changes}
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
            if value is None and key not in econ:
                continue
            econ[key] = value
        mark_dirty()
        bot.reply_to(message, '⚠️ Не удалось надёжно сохранить изменение в Neon. Изменение отменено, попробуйте позже.')
        return False

    current = econ.get('custom_title')
    saved_title = econ.get('custom_title_text')

    if not arg:
        from html import escape
        equipped = escape(str(current)) if current else 'нет'
        saved = escape(str(saved_title)) if saved_title else 'не выбран'
        lines = [
            '🌟 <b>КАСТОМНЫЕ ТИТУЛЫ</b>',
            '━━━━━━━━━━━━━━━━━━━━',
            f'📚 Создано титулов: <b>{len(titles)}</b>',
            f'👑 Сейчас надет: <b>{equipped}</b>',
            f'💾 Выбранный титул: <b>{saved}</b>',
            '',
            'Создать новый титул за <b>4 ⭐</b>:',
            '<code>/create_tittle Ваш титул</code>',
            'Снять текущий: <code>/create_tittle off</code>',
            'Снова надеть выбранный: <code>/create_tittle on</code>',
            'Удалить выбранный из коллекции: <code>/create_tittle delete</code>',
            '',
            'Каждый новый титул оплачивается отдельно. Уже созданные титулы можно менять бесплатно в <code>/инвентарь</code>.'
        ]
        bot.reply_to(message, '\n'.join(lines), parse_mode='HTML')
        return

    if action in {'off', 'none', 'remove', 'снять', 'выключить', '-'}:
        if not current:
            bot.reply_to(message, 'ℹ️ Кастомный титул не надет. Его текст сохранён; вернуть можно командой <code>/create_tittle on</code>.', parse_mode='HTML')
            return
        if save_changes({'custom_title': None}, 'custom title unequip'):
            bot.reply_to(message, '✅ Кастомный титул снят, но оставлен в коллекции. Вернуть его можно командой <code>/create_tittle on</code>.', parse_mode='HTML')
        return

    if action in {'on', 'включить', 'надеть'}:
        selected_id = econ.get('custom_title_id')
        selected = next((t for t in titles if isinstance(t, dict) and t.get('id') == selected_id), None)
        if not selected and saved_title:
            selected = next((t for t in titles if isinstance(t, dict) and t.get('text') == saved_title), None)
        if not selected and titles:
            selected = titles[-1] if isinstance(titles[-1], dict) else None
        if not selected:
            bot.reply_to(message, '❌ У вас пока нет созданных кастомных титулов. Создание нового стоит 4 ⭐: <code>/create_tittle Ваш титул</code>', parse_mode='HTML')
            return
        title_id, title_text = str(selected.get('id')), str(selected.get('text', ''))
        changes = {'custom_title_id': title_id, 'custom_title_text': title_text, 'custom_title': title_text, 'active_title': None}
        if save_changes(changes, 'custom title equip'):
            bot.reply_to(message, f'✅ Надет титул: <b>{__import__("html").escape(title_text)}</b>', parse_mode='HTML')
        return

    if action in {'delete', 'удалить', 'стереть', 'clear'}:
        selected_id = econ.get('custom_title_id')
        selected = next((t for t in titles if isinstance(t, dict) and t.get('id') == selected_id), None)
        if not selected and saved_title:
            selected = next((t for t in titles if isinstance(t, dict) and t.get('text') == saved_title), None)
        if not selected:
            bot.reply_to(message, 'ℹ️ Выбранного кастомного титула нет в коллекции.', parse_mode='HTML')
            return
        new_titles = [t for t in titles if not (isinstance(t, dict) and t.get('id') == selected.get('id'))]
        changes = {'custom_titles': new_titles}
        if selected.get('id') == econ.get('custom_title_id'):
            changes.update({'custom_title': None, 'custom_title_text': None, 'custom_title_id': None})
        if save_changes(changes, 'custom title delete'):
            bot.reply_to(message, '✅ Выбранный титул удалён из коллекции. Ранее оплаченные другие титулы сохранены.', parse_mode='HTML')
        return

    title = ' '.join(arg.split())
    if not title or len(title) > 40:
        bot.reply_to(message, '❌ Титул должен содержать от 1 до 40 символов.')
        return
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in title):
        bot.reply_to(message, '❌ Титул содержит недопустимые управляющие символы.')
        return

    # A certificate paid for in the old version grants exactly one title credit.
    # This preserves purchases while requiring 4 Stars for every subsequent title.
    has_legacy_credit = bool(econ.get('has_custom_title_cert')) and not bool(econ.get('custom_title_credit_used'))
    if has_legacy_credit:
        import secrets
        title_id = 'ct_' + secrets.token_hex(4)
        new_item = {'id': title_id, 'text': title, 'created_at': time.time(), 'legacy_credit': True}
        changes = {
            'custom_titles': list(titles) + [new_item],
            'custom_title_id': title_id,
            'custom_title_text': title,
            'custom_title': title,
            'active_title': None,
            'has_custom_title_cert': False,
            'custom_title_credit_used': True,
        }
        if save_changes(changes, 'legacy custom title credit redeemed'):
            bot.reply_to(message, f'🌟 <b>Титул создан!</b>\n\n<b>{__import__("html").escape(title)}</b>\n\nСледующий новый титул будет стоить 4 ⭐. Надевать и снимать созданные титулы можно бесплатно в <code>/инвентарь</code>.', parse_mode='HTML')
        return

    import secrets
    token = secrets.token_hex(8)
    now_ts = time.time()
    pending = econ.setdefault('pending_custom_title_orders', {})
    if not isinstance(pending, dict):
        pending = {}
        econ['pending_custom_title_orders'] = pending
    # Keep only live orders and cap open invoices to prevent unbounded stale data.
    for old_token, old_order in list(pending.items()):
        try:
            old_created = float((old_order or {}).get('created_at', 0) or 0)
        except (TypeError, ValueError, AttributeError):
            old_created = 0
        if old_created <= 0 or now_ts - old_created > 172800:
            pending.pop(old_token, None)
    if len(pending) >= 5:
        mark_dirty()
        critical_save('prune expired custom title orders', retries=2)
        bot.reply_to(message, '⚠️ У вас уже 5 неоплаченных счетов на кастомные титулы. Оплатите один из них или подождите 48 часов, пока старые заказы истекут.')
        return
    pending[token] = {'text': title, 'created_at': now_ts, 'amount': 4}
    mark_dirty()
    if not critical_save('create custom title payment order', retries=3):
        pending.pop(token, None)
        mark_dirty()
        bot.reply_to(message, '⚠️ Не удалось сохранить заказ в Neon. Ничего не списано, попробуйте ещё раз.')
        return
    try:
        bot.send_invoice(
            chat_id=message.chat.id,
            title='Создание кастомного титула',
            description=f'Создание титула: {title}',
            invoice_payload=f'ctitle:{user_id}:{token}',
            provider_token='',
            currency='XTR',
            prices=[LabeledPrice(label='Кастомный титул', amount=4)],
        )
        bot.reply_to(message, '⭐ Счёт на 4 Telegram Stars создан. Титул будет сохранён и надет после успешной оплаты.')
    except Exception as exc:
        print(f'[CUSTOM TITLE INVOICE ERROR] {exc}')
        pending.pop(token, None)
        mark_dirty()
        critical_save('cancel custom title invoice', retries=2)
        bot.reply_to(message, '❌ Не удалось выставить счёт. Заказ отменён, повторите команду позже.')

def cmd_stars(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_stars_shop(message.chat.id, user_id, user_name, category='main')

def cmd_inventory(message):
    if not can_process_user_message(message):
        return
    uid = int(message.from_user.id)
    name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username or 'Пользователь'
    render_inventory_view(message.chat.id, uid, name, category='main')

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
