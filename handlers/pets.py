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


HANDLER_NAMES = ['cmd_pet', 'cmd_walk_pet', 'cmd_gear', 'cmd_pet_clothes', 'cmd_catch', 'cmd_pet_fight']


def cmd_pet(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_pet_view(message.chat.id, user_id, user_name)

def cmd_walk_pet(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    process_pet_walk(message.chat.id, user_id, user_name)

def cmd_gear(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username or 'Игрок'
    lines = [
        "🎣 <b>МАГАЗИН ПРОФЕССИОНАЛЬНЫХ СНАСТЕЙ</b> 😺",
        "━━━━━━━━━━━━━━━━━━━━",
        "<i>Удочки и луки многократно увеличивают шанс на легендарную и мифическую добычу!</i>\n",
        "<b>Доступные снасти:</b> 😸"
    ]
    for r_id, r in RODS.items(): lines.append(f"• <b>{r['name']}</b> — <code>{r['price']} 🪙</code> (+{r['luck']}% к удаче)")
    for b_id, b in BOWS.items(): lines.append(f"• <b>{b['name']}</b> — <code>{b['price']} 🪙</code> (+{b['luck']}% к удаче)")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    econ = get_user_econ(user_id, user_name)
    owned_rods = set(econ.get('rod_inventory', []) or [])
    owned_bows = set(econ.get('bow_inventory', []) or [])
    markup = InlineKeyboardMarkup(row_width=2)
    rod_btns = []
    for r_id, r_info in RODS.items():
        label = f"✅ Надеть {r_info['short']}" if r_id in owned_rods else f"🛒 Купить {r_info['short']} — {r_info['price']} 🪙"
        rod_btns.append(InlineKeyboardButton(label, callback_data=f"buy_rod_{r_id}:{user_id}"))
    bow_btns = []
    for b_id, b_info in BOWS.items():
        label = f"✅ Надеть {b_info['short']}" if b_id in owned_bows else f"🏹 Купить {b_info['short']} — {b_info['price']} 🪙"
        bow_btns.append(InlineKeyboardButton(label, callback_data=f"buy_bow_{b_id}:{user_id}"))
    
    for i in range(0, len(rod_btns), 2):
        markup.add(*rod_btns[i:i+2])
    for i in range(0, len(bow_btns), 2):
        markup.add(*bow_btns[i:i+2])

    bot.reply_to(message, "\n".join(lines), reply_markup=markup, parse_mode='HTML')

def cmd_pet_clothes(message):
    if not can_process_user_message(message): return
    name=(f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_pet_clothes(message.chat.id,message.from_user.id,name)

def cmd_catch(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    chat_id = message.chat.id

    if not econ.get('is_sheriff'):
        bot.reply_to(message, "❌ Ловить преступников могут только шерифы! Устройтесь на службу: <code>/sheriff</code> 👮‍♂️", parse_mode='HTML')
        return

    in_j, left_j = is_in_jail(user_id)
    if in_j:
        bot.reply_to(message, f"❌ Вы сами находитесь под стражей в КПЗ! 😿", parse_mode='HTML')
        return

    target_user, target_user_id, _ = parse_target_and_args(message, '/catch')
    if not target_user:
        target_user, target_user_id, _ = parse_target_and_args(message, 'поймать')

    if not target_user or not target_user_id:
        bot.reply_to(message, "❌ Укажите вора: <code>поймать @вор</code> или ответом на сообщение! 😾", parse_mode='HTML')
        return

    if target_user_id == user_id:
        bot.reply_to(message, "❌ Шериф не может арестовать самого себя! 🙀", parse_mode='HTML')
        return

    now = time.time()
    u_link = make_link(chat_id, user_name, user_id, ping=True)
    t_link = make_link(chat_id, target_user, target_user_id, ping=True)

    # Шанс задержания 75%. The wanted entry is consumed atomically so two
    # different sheriffs cannot both receive the reward for one fugitive.
    with CALLBACK_STATE_LOCK:
        wanted_info = active_wanted.get((chat_id, target_user_id))
        if not wanted_info or wanted_info.get('expire', 0) < now:
            bot.reply_to(message, f"❌ Пользователь <b>{html.escape(target_user)}</b> сейчас не находится в оперативном розыске! 😾", parse_mode='HTML')
            return
        t_econ = get_user_econ(target_user_id, target_user)
        if random.random() < 0.75:
            with TRANSFER_LOCK:
                fine = min(max(0, int(t_econ.get('balance', 0) or 0)), 200)
                t_econ['balance'] = max(0, int(t_econ.get('balance', 0) or 0) - fine)
                t_econ['jail_until'] = now + 900
                reward = 250
                econ['balance'] = max(0, int(econ.get('balance', 0) or 0)) + reward
                active_wanted.pop((chat_id, target_user_id), None)
                add_account_exp(user_id, user_name, 35, username=message.from_user.username)
                change_karma(user_id, user_name, 3)
                mark_dirty()

            log_event('ПОЛИЦИЯ: АРЕСТ', f'Шериф {u_link} задержал вора {t_link}! Вор отправлен в КПЗ на 15 мин.')
            bot.send_message(
                chat_id,
                f"🚨🚔 <b>ГРАБИТЕЛЬ ОБЕЗВРЕЖЕН И ЗАДЕРЖАН!</b> 👮‍♂️\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Шериф {u_link} мастерски скрутил вора {t_link}! 💥\n"
                f"⚖️ С вора списан штраф: <b>-{fine} 🪙</b>\n"
                f"🔒 Вор отправлен в КПЗ на <b>15 минут</b> (команды заработка заблокированы)!\n"
                f"💰 Награда шерифу за службу: <b>+{reward} 🪙</b> (+35 EXP, +3 Кармы)! 😻\n"
                f"━━━━━━━━━━━━━━━━━━━━",
                parse_mode='HTML'
            )
        else:
            bot.send_message(
                chat_id,
                f"💨 <b>ОПЕРАЦИЯ ПРОВАЛЕНА!</b> 🙀\n\n"
                f"Вор {t_link} бросил дымовую шашку под ноги шерифу {u_link} и ловко скрылся во дворах! Погоня продолжается!",
                parse_mode='HTML'
            )

def cmd_pet_fight(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    chat_id = message.chat.id

    in_j, left_j = is_in_jail(user_id)
    if in_j:
        bot.reply_to(message, f"🔒 Вы в КПЗ! До выхода: <b>{left_j} мин.</b> 😿", parse_mode='HTML')
        return

    pet1 = econ.get('pet')
    if not pet1:
        bot.reply_to(message, "❌ У вас нет питомца! Купите его в <code>/shop</code>. 😿", parse_mode='HTML')
        return

    target_user, target_user_id, raw_args = parse_target_and_args(message, '/pet_fight')
    if not target_user:
        target_user, target_user_id, raw_args = parse_target_and_args(message, 'бой_питомцев')

    if not target_user or not target_user_id:
        bot.reply_to(message, "❌ Формат: <code>/pet_fight @соперник [ставка]</code> или ответом на сообщение! 😾", parse_mode='HTML')
        return

    if target_user_id == user_id:
        bot.reply_to(message, "❌ Нельзя драться питомцем с самим собой! 🙀", parse_mode='HTML')
        return

    t_econ = get_user_econ(target_user_id, target_user)
    pet2 = t_econ.get('pet')
    if not pet2:
        bot.reply_to(message, f"❌ У соперника <b>{html.escape(target_user)}</b> нет питомца! 😿", parse_mode='HTML')
        return

    m_bet = re.search(r'\b(\d+)\b', raw_args)
    bet = int(m_bet.group(1)) if m_bet else 50
    if bet < 30:
        bot.reply_to(message, "❌ Минимальная ставка — 30 Ня-коинов! 😾", parse_mode='HTML')
        return

    with TRANSFER_LOCK:
        my_balance = int(econ.get('balance', 0) or 0)
        opp_balance = int(t_econ.get('balance', 0) or 0)
        if my_balance < bet:
            bot.reply_to(message, f"❌ У вас недостаточно коинов! Ваш баланс: {my_balance} 🪙. 😿", parse_mode='HTML')
            return
        if opp_balance < bet:
            bot.reply_to(message, f"❌ У соперника недостаточно коинов ({opp_balance}/{bet} 🪙)! 😿", parse_mode='HTML')
            return
        econ['balance'] = my_balance - bet
        t_econ['balance'] = opp_balance - bet

    # Расчет боевой мощи
    p1_pow = pet1.get('power', 15) + (pet1.get('pet_exp', 0) // 20) + random.randint(1, 15)
    p2_pow = pet2.get('power', 15) + (pet2.get('pet_exp', 0) // 20) + random.randint(1, 15)

    u_link = make_link(chat_id, user_name, user_id, ping=True)
    t_link = make_link(chat_id, target_user, target_user_id, ping=True)

    rounds_log = [
        f"🥊 <b>ПОДПОЛЬНЫЙ БОЙ ПИТОМЦЕВ!</b> 🐾 😺",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🔴 {pet1['name']} ({u_link}) VS 🔵 {pet2['name']} ({t_link})",
        f"💰 Банк арены: <b>{bet * 2} Ня-коинов 🪙</b>\n",
        "<b>Ход битвы:</b>"
    ]

    # Симуляция раундов
    if p1_pow >= p2_pow:
        winner_id, winner_name, win_pet, loser_pet = user_id, user_name, pet1, pet2
        loser_id, loser_name = target_user_id, target_user
        rounds_log.append(f"1️⃣ {pet1['name']} проводит молниеносный выпад когтями! (-35 HP)")
        rounds_log.append(f"2️⃣ {pet2['name']} пытается контратаковать, но промахивается!")
        rounds_log.append(f"3️⃣ 🔥 <b>КРИТИЧЕСКИЙ УДАР!</b> {pet1['name']} опрокидывает соперника!")
    else:
        winner_id, winner_name, win_pet, loser_pet = target_user_id, target_user, pet2, pet1
        loser_id, loser_name = user_id, user_name
        rounds_log.append(f"1️⃣ {pet2['name']} встречает соперника мощным рыком!")
        rounds_log.append(f"2️⃣ {pet1['name']} наносит удар, но натыкается на крепкий блок!")
        rounds_log.append(f"3️⃣ 🔥 <b>УЛЬТИМЕЙТ!</b> {pet2['name']} проводит решающий коронный приём!")

    total_pot = int(bet * 2 * 0.95)
    with TRANSFER_LOCK:
        w_econ = get_user_econ(winner_id, winner_name)
        w_econ['balance'] += total_pot
        win_pet['pet_exp'] = win_pet.get('pet_exp', 0) + 40
        win_pet['fights_won'] = win_pet.get('fights_won', 0) + 1
        loser_pet['pet_exp'] = loser_pet.get('pet_exp', 0) + 15
        mark_dirty()

    w_link = make_link(chat_id, winner_name, winner_id, ping=True)
    rounds_log.append("━━━━━━━━━━━━━━━━━━━━")
    rounds_log.append(f"🏆 <b>ПОБЕДИТЕЛЬ:</b> {win_pet['name']} (Тренер: {w_link})!")
    rounds_log.append(f"💸 Выигрыш: <b>+{total_pot} 🪙</b> | Опыт победителя: <b>+40 EXP</b>! 😻")

    bot.send_message(chat_id, "\n".join(rounds_log), parse_mode='HTML')

def register(ctx, only=None):
    """Register selected handlers from this feature module."""
    _inject(ctx)
    bot = ctx["bot"]
    wanted = set(only) if only is not None else set(HANDLER_NAMES)
    registered = []
    if "cmd_pet" in wanted:
        _handler = cmd_pet
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['pet', 'питомец', 'пет'])(_handler)
        ctx["cmd_pet"] = _handler
        globals()["cmd_pet"] = _handler
        registered.append("cmd_pet")
    if "cmd_walk_pet" in wanted:
        _handler = cmd_walk_pet
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['walk', 'гулять'])(_handler)
        ctx["cmd_walk_pet"] = _handler
        globals()["cmd_walk_pet"] = _handler
        registered.append("cmd_walk_pet")
    if "cmd_gear" in wanted:
        _handler = cmd_gear
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['gear', 'снасти'])(_handler)
        ctx["cmd_gear"] = _handler
        globals()["cmd_gear"] = _handler
        registered.append("cmd_gear")
    if "cmd_pet_clothes" in wanted:
        _handler = cmd_pet_clothes
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['petclothes', 'одежда_питомца'])(_handler)
        ctx["cmd_pet_clothes"] = _handler
        globals()["cmd_pet_clothes"] = _handler
        registered.append("cmd_pet_clothes")
    if "cmd_catch" in wanted:
        _handler = cmd_catch
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['catch', 'поймать'])(_handler)
        ctx["cmd_catch"] = _handler
        globals()["cmd_catch"] = _handler
        registered.append("cmd_catch")
    if "cmd_pet_fight" in wanted:
        _handler = cmd_pet_fight
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['pet_fight', 'бой_питомцев', 'битвы_питомцев'])(_handler)
        ctx["cmd_pet_fight"] = _handler
        globals()["cmd_pet_fight"] = _handler
        registered.append("cmd_pet_fight")
    return registered
