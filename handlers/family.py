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


HANDLER_NAMES = ['cmd_personal_home', 'cmd_house', 'cmd_sheriff', 'cmd_jail', 'cmd_escape', 'cmd_bail']


def cmd_personal_home(message):
    if not can_process_user_message(message): return
    name=(f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_personal_home(message.chat.id,message.from_user.id,name)

def cmd_house(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    # Couple housing now belongs to the independent `отн` relationship system.
    # This legacy command remains as a personal-home shortcut only.
    render_personal_home(message.chat.id, user_id, user_name)

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
