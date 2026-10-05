"""Extracted Telegram handlers for staged NyaBot architecture.

The handlers keep their original function bodies. During migration, register(ctx)
receives the legacy newfile.py globals so business logic and shared state remain
unchanged.
"""

from __future__ import annotations

from core.locks import serialized_multi_user_action, TRANSFER_LOCK


def _inject(ctx):
    for _name, _value in ctx.items():
        if _name not in {"__name__", "__package__", "__loader__", "__spec__", "__cached__", "__builtins__"}:
            globals()[_name] = _value


HANDLER_NAMES = ['cmd_marry', 'cmd_family', 'cmd_gift', 'cmd_divorce', 'cmd_personal_home', 'cmd_house', 'cmd_sheriff', 'cmd_jail', 'cmd_escape', 'cmd_bail']


def cmd_marry(message):
    if not can_process_user_message(message):
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    if econ.get('marriage'):
        bot.reply_to(message, "❌ Вы уже состоите в браке! Чтобы развестись, введите: <code>развод</code> 😿", parse_mode='HTML')
        return

    target_user, target_user_id, _ = parse_target_and_args(message, '/marry')
    if not target_user: target_user, target_user_id, _ = parse_target_and_args(message, 'брак')

    if not target_user:
        bot.reply_to(message, "❌ Укажите пользователя! 😾\nПример: <code>брак @username</code> или ответом на сообщение.", parse_mode='HTML')
        return

    if not target_user_id or int(target_user_id) <= 0:
        bot.reply_to(message, "❌ Не удалось определить Telegram ID соперника. Ответьте на его сообщение или укажите @username. 😾", parse_mode='HTML')
        return

    if target_user_id == user_id:
        bot.reply_to(message, "❌ Нельзя заключить брак с самим собой! 🙀")
        return

    try:
        bot_me = bot.get_me()
    except Exception:
        bot_me = None

    is_bot_target = False
    if bot_me:
        if target_user_id and target_user_id == bot_me.id:
            is_bot_target = True
        elif target_user and clean_tag(target_user).lower() in [bot_me.username.lower(), 'бот', 'bot', 'ня']:
            is_bot_target = True
        elif message.reply_to_message and message.reply_to_message.from_user.id == bot_me.id:
            is_bot_target = True
    elif target_user and clean_tag(target_user).lower() in ['бот', 'bot', 'ня']:
        is_bot_target = True

    if is_bot_target:
        rings = econ.get('rings', [])
        chosen_ring = rings[0] if rings else 'copper'
        ring_emoji = RINGS.get(chosen_ring, {}).get('emoji', '💍')
        bot_id = bot_me.id if bot_me else 0
        bot_name = bot_me.first_name if bot_me else "Ня-Бот"

        m_time = time.time()
        econ['marriage'] = {
            'partner_id': bot_id,
            'partner_name': f"🤖 {bot_name}",
            'ring': chosen_ring,
            'married_at': m_time,
            'vault': 0
        }
        check_achievements(user_id, user_name, 'marriages', 1, chat_id, username=message.from_user.username)
        mark_dirty()

        u_link = make_link(chat_id, user_name, user_id, ping=True)
        bot.send_message(
            chat_id,
            f"😳👉👈 <b>Ох, семпай... Это так неожиданно и приятно!</b> 😻\n\n"
            f"Я согласна стать твоей вайфу! {ring_emoji}\n\n"
            f"💒 <b>Горько!</b> {u_link} и <b>🤖 {bot_name}</b> теперь официально в браке! 💖🌸 😺",
            parse_mode='HTML'
        )
        return
        
    target_econ = get_user_econ(target_user_id, target_user)
    if target_econ.get('marriage'):
        bot.reply_to(message, f"❌ Пользователь <b>{html.escape(target_user)}</b> уже состоит в браке! 😿", parse_mode='HTML')
        return

    rings = econ.get('rings', [])
    chosen_ring = rings[0] if rings else 'copper'

    prop_id = f"{user_id}_{target_user_id}_{time.time_ns()}"
    with CALLBACK_STATE_LOCK:
        # Recheck both sides before storing the proposal. Two parallel proposals
        # to one target must not be able to create inconsistent marriages later.
        fresh_from = get_user_econ(user_id, user_name, username=message.from_user.username)
        fresh_to = get_user_econ(target_user_id, target_user)
        if fresh_from.get('marriage'):
            bot.reply_to(message, "❌ Вы уже состоите в браке! 😿")
            return
        if fresh_to.get('marriage'):
            bot.reply_to(message, f"❌ Пользователь <b>{html.escape(target_user)}</b> уже состоит в браке! 😿", parse_mode='HTML')
            return
        pending_marriages[prop_id] = {
            'from_id': user_id, 'from_tag': user_name,
            'to_id': target_user_id, 'to_tag': target_user,
            'ring': chosen_ring, 'start_time': time.time()
        }

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("💍 Согласиться", callback_data=f"m_yes_{prop_id}:{target_user_id or 0}"),
        InlineKeyboardButton("❌ Отказать", callback_data=f"m_no_{prop_id}:{target_user_id or 0}")
    )

    from_link = make_link(chat_id, user_name, user_id, ping=True)
    to_link = make_link(chat_id, target_user, target_user_id, ping=True)
    ring_name = RINGS.get(chosen_ring, {}).get('name', 'Медное колечко')
    ring_emoji = RINGS.get(chosen_ring, {}).get('emoji', '💍')

    bot.send_message(
        chat_id,
        f"💖 {to_link}, вам делает предложение руки и сердца {from_link}! 😻\n"
        f"💍 Преподнесенное кольцо: {ring_emoji} <b>{ring_name}</b>\n\n"
        f"Вы согласны соединить свои сердца? 😺",
        reply_markup=markup, parse_mode='HTML'
    )

def cmd_family(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    if not econ.get('marriage'):
        bot.reply_to(message, "💔 Вы пока не состоите в браке! 😿 Сделайте предложение через <code>брак @username</code>.", parse_mode='HTML')
        return

    m = econ['marriage']
    ring_emoji = RINGS.get(m.get('ring'), {}).get('emoji', '💍')
    ring_name = RINGS.get(m.get('ring'), {}).get('name', 'Кольцо')
    days_together = max(1, int((time.time() - m.get('married_at', time.time())) / 86400))
    partner_link = make_link(message.chat.id, m.get('partner_name'), m.get('partner_id'), ping=False)
    vault = m.get('vault', 0)

    text = (
        f"💒 <b>ИНФОРМАЦИЯ О СЕМЬЕ:</b> 😺\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💍 Кольцо: {ring_emoji} <b>{ring_name}</b>\n"
        f"👫 Супруг(а): {partner_link}\n"
        f"⏳ Дней в браке: <b>{days_together} дн.</b>\n"
        f"💰 Семейный сейф: <b>{vault} Ня-коинов 🪙</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>Команды семьи:</b> 😸\n"
        f"• <code>подарок</code> — романтический букет (100 🪙)\n"
        f"• <code>семейный сейф положить 100</code>\n"
        f"• <code>семейный сейф снять 100</code>\n"
        f"• <code>развод</code> — расторгнуть брак"
    )
    bot.reply_to(message, text, parse_mode='HTML')

def cmd_gift(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    if not econ.get('marriage'):
        bot.reply_to(message, "❌ Подарки супругу доступны только тем, кто состоит в браке! 😿")
        return

    m = econ['marriage']
    p_id = m.get('partner_id')
    p_tag = m.get('partner_name')

    cost = 100
    if not p_id or int(p_id) < 0:
        bot.reply_to(message, "❌ Не удалось определить супруга для подарка. Попробуйте открыть /family. 😿")
        return

    with serialized_multi_user_action(user_id, int(p_id)):
        with TRANSFER_LOCK:
            fresh_econ = get_user_econ(user_id, user_name, username=message.from_user.username)
            if int(fresh_econ.get('balance', 0) or 0) < cost:
                bot.reply_to(message, f"❌ На роскошный букет нужно <b>{cost} 🪙</b>! 😿")
                return
            fresh_partner = get_user_econ(int(p_id), p_tag)
            _adjust_balance(fresh_econ, -cost)
            _adjust_balance(fresh_partner, 80)
            change_karma(user_id, user_name, 3)
            mark_dirty()

    sender_l = make_link(message.chat.id, user_name, user_id, ping=True)
    partner_l = make_link(message.chat.id, p_tag, p_id, ping=True)

    bot.send_message(
        message.chat.id,
        f"💐 <b>РОМАНТИЧЕСКИЙ ПОДАРОК!</b> 😻\n\n"
        f"{sender_l} преподнес(ла) роскошный букет цветов и сладости для {partner_l}! 💖🍫\n"
        f"Любовь крепнет с каждым днем! (+80 🪙 на счет любимого человека, +3 Карма)",
        parse_mode='HTML'
    )

def cmd_divorce(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    if not econ.get('marriage'):
        bot.reply_to(message, "❌ Вы не состоите в браке! 😿")
        return

    with CALLBACK_STATE_LOCK:
        m = econ.get('marriage')
        if not m:
            bot.reply_to(message, "❌ Вы больше не состоите в браке! 😿")
            return
        p_id = m.get('partner_id')
        p_tag = m.get('partner_name')
        vault = max(0, int(m.get('vault', 0) or 0))
        split_coins = vault // 2
        if p_id is not None and int(p_id) >= 0:
            with serialized_multi_user_action(user_id, int(p_id)):
                with TRANSFER_LOCK:
                    fresh_econ = get_user_econ(user_id, user_name, username=message.from_user.username)
                    fresh_m = fresh_econ.get('marriage') or m
                    vault = max(0, int(fresh_m.get('vault', vault) or 0))
                    split_coins = vault // 2
                    p_econ = get_user_econ(int(p_id), p_tag)
                    _adjust_balance(fresh_econ, split_coins)
                    _adjust_balance(p_econ, vault - split_coins)
                    p_marriage = p_econ.get('marriage')
                    if isinstance(p_marriage, dict) and p_marriage.get('partner_id') == user_id:
                        p_econ['marriage'] = None
                    fresh_econ['marriage'] = None
                    mark_dirty()
        else:
            _adjust_balance(econ, split_coins)
            econ['marriage'] = None
            mark_dirty()

    bot.reply_to(message, f"💔 <b>Брак расторгнут.</b> 😿\nСемейный сейф ({vault} 🪙) разделен поровну между бывшими супругами (+{split_coins} 🪙 каждому).", parse_mode='HTML')

def cmd_personal_home(message):
    if not can_process_user_message(message): return
    name=(f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_personal_home(message.chat.id,message.from_user.id,name)

def cmd_house(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    if not econ.get('marriage'):
        render_personal_home(message.chat.id, user_id, user_name)
    else:
        render_house_view(message.chat.id, user_id, user_name)

def cmd_sheriff(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    if econ.get('is_sheriff'):
        econ['is_sheriff'] = False
        mark_dirty()
        bot.reply_to(message, "👮‍♂️ Вы сдали жетон и уволились из полиции чата. Теперь вы обычный гражданин! 😸", parse_mode='HTML')
        return

    lvl, _, _, _ = get_account_level(econ.get('account_exp', 0))
    if lvl < 2:
        bot.reply_to(message, "❌ Для службы в полиции чата требуется минимум <b>2-й уровень</b> профиля! 😾", parse_mode='HTML')
        return

    econ['is_sheriff'] = True
    mark_dirty()
    u_link = make_link(message.chat.id, user_name, user_id, ping=True)
    bot.reply_to(
        message,
        f"👮‍♂️⭐ <b>ДОБРО ПОЖАЛОВАТЬ НА СЛУЖБУ, ШЕРИФ!</b> 😺\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Офицер: {u_link}\n"
        f"Ваша задача — ловить грабителей по горячим следам!\n\n"
        f"Когда кто-то совершит ограбление, у вас будет 15 минут, чтобы поймать преступника командой:\n"
        f"👉 <code>поймать @вор</code> или <code>/catch @вор</code>\n\n"
        f"💰 Награда за поимку: <b>+250 🪙</b>, +30 EXP и +3 к Карме! 😻\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode='HTML'
    )

def cmd_jail(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    chat_id = message.chat.id

    in_j, left_j = is_in_jail(user_id)
    wanted_count = len([w for w in active_wanted.values() if w.get('expire', 0) > time.time()])

    status_str = f"🔒 <b>ВЫ В КАМЕРЕ КПЗ!</b> До выхода: <b>{left_j} мин.</b>\nПопробуйте сбежать: <code>/escape</code> или попросите друга внести залог: <code>/bail</code>!" if in_j else "🕊 <b>Вы на свободе!</b> За вами нет правонарушений."

    text = (
        f"🏢 <b>ГОРОДСКОЕ ОТДЕЛЕНИЕ ПОЛИЦИИ И КПЗ</b> 👮‍♂️ 😺\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Статус: {status_str}\n\n"
        f"🚨 Преступников в розыске: <b>{wanted_count} чел.</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>Команды полиции и арестантов:</b> 😸\n"
        f"• <code>/sheriff</code> — поступить на службу шерифом\n"
        f"• <code>поймать @вор</code> — задержать преступника из розыска\n"
        f"• <code>/escape</code> — совершить попытку побега из КПЗ (шанс 35%)\n"
        f"• <code>/bail @вор</code> — выкупить друга под залог (300 🪙)"
    )
    bot.reply_to(message, text, parse_mode='HTML')

def cmd_escape(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    chat_id = message.chat.id

    in_j, left_j = is_in_jail(user_id)
    if not in_j:
        bot.reply_to(message, "Вы не находитесь в КПЗ, побег не требуется! 😸")
        return

    u_link = make_link(chat_id, user_name, user_id, ping=True)
    if random.random() < 0.35:
        econ['jail_until'] = 0
        mark_dirty()
        bot.send_message(
            chat_id,
            f"🏃‍♂️💨 <b>ДЕРЗКИЙ ПОБЕГ УДАЛСЯ!</b> 🙀\n\n"
            f"{u_link} отогнул решётку ложкой и сбежал через вентиляцию! Вы снова на свободе! 😻",
            parse_mode='HTML'
        )
    else:
        econ['jail_until'] = econ.get('jail_until', time.time()) + 600
        mark_dirty()
        bot.send_message(
            chat_id,
            f"🚨🐕 <b>ПОБЕГ ПРОВАЛЕН!</b> 😾\n\n"
            f"{u_link} застрял в форточке и был пойман дежурным с собаками! Срок в КПЗ увеличен на <b>+10 минут</b>! 😿",
            parse_mode='HTML'
        )

def cmd_bail(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    chat_id = message.chat.id

    target_user, target_user_id, _ = parse_target_and_args(message, '/bail')
    if not target_user:
        target_user, target_user_id, _ = parse_target_and_args(message, 'залог')

    if not target_user or not target_user_id:
        bot.reply_to(message, "❌ Укажите заключённого: <code>/bail @user</code> или ответом на сообщение! 😾", parse_mode='HTML')
        return

    t_in_j, _ = is_in_jail(target_user_id)
    if not t_in_j:
        bot.reply_to(message, f"❌ Пользователь <b>{html.escape(target_user)}</b> не сидит в КПЗ! 😸", parse_mode='HTML')
        return

    bail_cost = 300
    with serialized_multi_user_action(user_id, int(target_user_id)):
        with TRANSFER_LOCK:
            fresh_econ = get_user_econ(user_id, user_name, username=message.from_user.username)
            if int(fresh_econ.get('balance', 0) or 0) < bail_cost:
                bot.reply_to(message, f"❌ На внесение залога нужно <b>{bail_cost} 🪙</b>! У вас: {fresh_econ.get('balance', 0)} 🪙. 😿", parse_mode='HTML')
                return
            t_econ = get_user_econ(target_user_id, target_user)
            if t_econ.get('jail_until', 0) <= time.time():
                bot.reply_to(message, f"❌ Пользователь <b>{html.escape(target_user)}</b> уже вышел из КПЗ! 😸", parse_mode='HTML')
                return
            _adjust_balance(fresh_econ, -bail_cost)
            t_econ['jail_until'] = 0
            change_karma(user_id, user_name, 2)
            mark_dirty()

    u_link = make_link(chat_id, user_name, user_id, ping=True)
    t_link = make_link(chat_id, target_user, target_user_id, ping=True)
    bot.send_message(
        chat_id,
        f"🤝🔓 <b>ЗАЛОГ ВНЕСЁН!</b> 😻\n\n"
        f"{u_link} заплатил залог <b>{bail_cost} 🪙</b> и освободил {t_link} из КПЗ! Настоящая дружба познаётся в беде! 😸",
        parse_mode='HTML'
    )

def register(ctx, only=None):
    """Register selected handlers from this feature module."""
    _inject(ctx)
    bot = ctx["bot"]
    wanted = set(only) if only is not None else set(HANDLER_NAMES)
    registered = []
    if "cmd_marry" in wanted:
        _handler = cmd_marry
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['marry', 'брак'])(_handler)
        ctx["cmd_marry"] = _handler
        globals()["cmd_marry"] = _handler
        registered.append("cmd_marry")
    if "cmd_family" in wanted:
        _handler = cmd_family
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['family', 'семья'])(_handler)
        ctx["cmd_family"] = _handler
        globals()["cmd_family"] = _handler
        registered.append("cmd_family")
    if "cmd_gift" in wanted:
        _handler = cmd_gift
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['gift', 'подарок'])(_handler)
        ctx["cmd_gift"] = _handler
        globals()["cmd_gift"] = _handler
        registered.append("cmd_gift")
    if "cmd_divorce" in wanted:
        _handler = cmd_divorce
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['divorce', 'развод'])(_handler)
        ctx["cmd_divorce"] = _handler
        globals()["cmd_divorce"] = _handler
        registered.append("cmd_divorce")
    if "cmd_personal_home" in wanted:
        _handler = cmd_personal_home
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['home', 'жильё', 'жилье'])(_handler)
        ctx["cmd_personal_home"] = _handler
        globals()["cmd_personal_home"] = _handler
        registered.append("cmd_personal_home")
    if "cmd_house" in wanted:
        _handler = cmd_house
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['house', 'дом'])(_handler)
        ctx["cmd_house"] = _handler
        globals()["cmd_house"] = _handler
        registered.append("cmd_house")
    if "cmd_sheriff" in wanted:
        _handler = cmd_sheriff
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['sheriff', 'шериф'])(_handler)
        ctx["cmd_sheriff"] = _handler
        globals()["cmd_sheriff"] = _handler
        registered.append("cmd_sheriff")
    if "cmd_jail" in wanted:
        _handler = cmd_jail
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['jail', 'кпз', 'тюрьма'])(_handler)
        ctx["cmd_jail"] = _handler
        globals()["cmd_jail"] = _handler
        registered.append("cmd_jail")
    if "cmd_escape" in wanted:
        _handler = cmd_escape
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['escape', 'побег'])(_handler)
        ctx["cmd_escape"] = _handler
        globals()["cmd_escape"] = _handler
        registered.append("cmd_escape")
    if "cmd_bail" in wanted:
        _handler = cmd_bail
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['bail', 'залог'])(_handler)
        ctx["cmd_bail"] = _handler
        globals()["cmd_bail"] = _handler
        registered.append("cmd_bail")
    return registered
