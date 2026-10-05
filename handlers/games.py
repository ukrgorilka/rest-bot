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


HANDLER_NAMES = ['cmd_coinflip', 'cmd_mini_games', 'cmd_fact_vd', 'cmd_trash', 'cmd_promo', 'cmd_brick', 'cmd_crash', 'cmd_stream', 'cmd_monopoly', 'cmd_garden', 'cmd_football', 'cmd_basketball', 'cmd_darts', 'cmd_bowling', 'cmd_magic_ball', 'cmd_chance', 'cmd_detector', 'cmd_daily_heroes', 'cmd_backpack', 'cmd_wheel', 'cmd_mines', 'cmd_classic_mines', 'cmd_durak', 'cmd_dick', 'cmd_fap', 'cmd_bj', 'cmd_rps', 'cmd_memes', 'cmd_meme', 'cmd_story', 'cmd_resources_command', 'cmd_guild_command', 'cmd_player_market_command', 'cmd_raid_command', 'cmd_season_command', 'cmd_world_command']


def cmd_mini_games(message):
    if not can_process_user_message(message): return
    if not MINIAPP_URL:
        bot.reply_to(message, '❌ MINIAPP_URL не настроен в Render. Укажи URL Mini App в переменной окружения.')
        return
    kb=InlineKeyboardMarkup(); kb.add(InlineKeyboardButton('🎮 Открыть Nya Mini Games', web_app=WebAppInfo(url=MINIAPP_URL + '/minigames')))
    bot.reply_to(message, '🎮 <b>Nya Mini Games · v0.3</b>\nСапёр • Змейка • 2048 • Реакция • Тир\n\n👤 Профиль, 🏆 рейтинг, 🎁 бонусы и ⚙️ настройки внутри Mini App.', reply_markup=kb, parse_mode='HTML')

def cmd_fact_vd(message):
    if not can_process_user_message(message):
        return
    title, desc = random.choice(VD_FACTS)
    msg_text = (
        "🩸 <b>ИНТЕРЕСНЫЙ ФАКТ | VIOLENCE DISTRICT</b> 🔪 😺\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>{title}</b>\n"
        f"📖 <i>{desc}</i>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Хотите еще? Напишите:</i> <code>факт вд</code> 😸"
    )
    try:
        bot.reply_to(message, msg_text, parse_mode='HTML')
    except Exception:
        pass

def cmd_trash(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    now = time.time()
    cooldown = 1800
    left = cooldown_text(econ.get('last_trash_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Мусорные баки ещё не обновились! Ждите: <b>{left}</b>. 😿", parse_mode='HTML')
        return

    econ['last_trash_time'] = now
    loot = random.choice(TRASH_LOOT)
    l_type, l_desc, l_val = loot

    u_link = make_link(message.chat.id, user_name, user_id, ping=True)
    msg_text = f"🗑 <b>РАСКОПКИ В МУСОРКЕ</b> 😺\n━━━━━━━━━━━━━━━━━━━━\n{u_link} порылся(лась) в мусорных баках чата и нашёл(ла):\n👉 <b>{l_desc}</b>"

    if l_type.startswith('coins') or l_type in ['boots', 'watch']:
        _adjust_balance(econ, l_val)
    elif l_type == 'fertilizer':
        bp = econ.setdefault('backpack', {})
        bp['garden_fertilizer'] = bp.get('garden_fertilizer', 0) + 1
    elif l_type == 'energy':
        bp = econ.setdefault('backpack', {})
        bp['energy_drink'] = bp.get('energy_drink', 0) + 1
    elif l_type == 'fish':
        trophy = random.choice(FISH_TYPES)[0]
        add_inventory_item(econ['fish_inventory'], trophy)

    add_account_exp(user_id, user_name, 5, username=message.from_user.username)
    mark_dirty()
    msg_text += f"\n━━━━━━━━━━━━━━━━━━━━\n💰 Баланс: <b>{econ['balance']} 🪙</b> 😸"
    bot.reply_to(message, msg_text, parse_mode='HTML')

def cmd_promo(message):
    if not can_process_user_message(message):
        return

    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    parts = message.text.strip().split(maxsplit=1)
    
    if len(parts) < 2:
        bot.reply_to(message, "🎁 Введите промокод через пробел!\nПример: <code>/promo FIX</code> 😸", parse_mode='HTML')
        return

    code_entered = parts[1].strip()
    code_upper = code_entered.upper()

    promos = db.setdefault('promos', {})
    target_promo = promos.get(code_upper) or promos.get(code_entered)

    if not target_promo:
        bot.reply_to(message, f"❌ Промокода <b>{html.escape(code_entered)}</b> не существует или он истек! 😿", parse_mode='HTML')
        return

    claimed_list = target_promo.setdefault('claimed', [])
    if user_id in claimed_list:
        bot.reply_to(message, "❌ Вы уже активировали этот промокод ранее! 😾", parse_mode='HTML')
        return

    reward = target_promo.get('reward', 5000)
    exp_bonus = target_promo.get('exp', 100)

    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    _adjust_balance(econ, reward)
    add_account_exp(user_id, user_name, exp_bonus, username=message.from_user.username)
    claimed_list.append(user_id)
    mark_dirty()

    log_event('ПРОМОКОД АКТИВИРОВАН', f'Игрок {make_link(message.chat.id, user_name, user_id, ping=False)} активировал промокод <b>{code_upper}</b> на +{reward} 🪙!')

    bot.reply_to(
        message,
        f"🎉 <b>ПРОМОКОД УСПЕШНО АКТИВИРОВАН!</b> 😻\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Код: <b>{html.escape(code_upper)}</b>\n"
        f"💰 Начислено: <b>+{reward} Ня-коинов 🪙</b>!\n"
        f"⭐ Получено: <b>+{exp_bonus} EXP опыта профиля</b>!\n"
        f"💵 Новый баланс: <b>{econ['balance']} 🪙</b> 😸\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode='HTML'
    )

def cmd_brick(message):
    if not can_process_user_message(message):
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    m = re.search(r'(?:/brick|кирпич)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(m.group(1)) if m and m.group(1) else 50

    if bet <= 0:
        bot.reply_to(message, "❌ Ставка должна быть больше 0! 😾")
        return

    if econ['balance'] < bet:
        bot.reply_to(message, f"❌ Недостаточно средств! У вас: {econ['balance']} 🪙 😿")
        return

    _adjust_balance(econ, -(bet))
    process_casino_bet(bet, chat_id)
    
    game_id = f"brick_{user_id}_{time.time_ns()}"
    active_brick[game_id] = {
        'user_id': user_id,
        'user_name': user_name,
        'username': message.from_user.username,
        'chat_id': message.chat.id,
        'bet': bet,
        'step': 0,
        'mults': [1.0, 1.15, 1.35, 1.65, 2.1, 2.7, 3.5, 4.5],
        'risks': [0.0, 0.12, 0.22, 0.32, 0.42, 0.52, 0.65, 0.78],
        'start_time': time.time(),
        'finished': False
    }

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🏗 Сделать шаг на стройке", callback_data=f"brick_step_{game_id}:{user_id}"))

    try:
        bot.send_message(
            message.chat.id,
            f"🧱 <b>ИГРА КИРПИЧ (СТРОЙКА)</b> 😺\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Строитель: {make_link(message.chat.id, user_name, user_id, ping=False)}\n"
            f"💰 Ставка: <b>{bet} 🪙</b>\n"
            f"📈 Текущий множитель: <b>1.00x</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Делайте шаги, чтобы увеличить множитель, но осторожно: кирпич может сорваться в любой момент!</i> 😸",
            reply_markup=markup,
            parse_mode='HTML'
        )
    except Exception as exc:
        active_brick.pop(game_id, None)
        _adjust_balance(econ, bet)
        reverse_casino_bet(bet, chat_id)
        print(f"[BRICK START SEND ERROR] {exc}")
        try:
            bot.reply_to(message, '❌ Не удалось запустить игру. Ставка возвращена. 😿', parse_mode='HTML')
        except Exception:
            pass

def cmd_crash(message):
    if not can_process_user_message(message):
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    m = re.search(r'(?:/crash|краш|ракета)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(m.group(1)) if m and m.group(1) else 50

    if bet <= 0:
        bot.reply_to(message, "❌ Ставка должна быть больше 0! 😾")
        return

    if econ['balance'] < bet:
        bot.reply_to(message, f"❌ Недостаточно средств! У вас: {econ['balance']} 🪙 😿")
        return

    _adjust_balance(econ, -(bet))
    process_casino_bet(bet, chat_id)

    game_id = f"cr_{user_id}_{time.time_ns()}"
    
    r = random.random()
    pool = db.get('casino_pool', 1000000)
    
    if pool < bet * 4:
        crash_point = round(random.uniform(1.00, 1.10), 2)
    else:
        if r < 0.20: crash_point = 1.00
        elif r < 0.55: crash_point = round(random.uniform(1.05, 1.55), 2)
        elif r < 0.80: crash_point = round(random.uniform(1.56, 2.50), 2)
        elif r < 0.93: crash_point = round(random.uniform(2.51, 4.50), 2)
        elif r < 0.98: crash_point = round(random.uniform(4.51, 7.50), 2)
        else: crash_point = round(random.uniform(7.51, 10.00), 2)

    active_crash[game_id] = {
        'user_id': user_id,
        'user_name': user_name,
        'username': message.from_user.username,
        'chat_id': message.chat.id,
        'bet': bet,
        'crash_point': crash_point,
        'current_mult': 1.00,
        'cashed_out': False,
        'exploded': False,
        'start_time': time.time(),
        'finished': False
    }

    if crash_point <= 1.00:
        active_crash[game_id]['exploded'] = True
        active_crash[game_id]['finished'] = True
        bot.send_message(
            message.chat.id,
            f"🚀 <b>ИГРА КРАШ (CRASH ROCKET)</b> 😺\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💥 <b>РАКЕТА ВЗОРВАЛАСЬ НА СТАРТЕ (1.00x)!</b> 🙀\n\n"
            f"👤 Пилот: {make_link(message.chat.id, user_name, user_id, ping=False)}\n"
            f"💸 Ваша ставка <b>{bet} Ня-коинов 🪙</b> моментально сгорела в атмосфере... 😿",
            parse_mode='HTML'
        )
        del active_crash[game_id]
        return

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"💰 Забрать куш ({bet} 🪙 | 1.00x) 😻", callback_data=f"crash_cashout_{game_id}:{user_id}"))

    try:
        sent_msg = bot.send_message(
            message.chat.id,
            f"🚀 <b>ИГРА КРАШ (CRASH ROCKET)</b> 😺\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Пилот: {make_link(message.chat.id, user_name, user_id, ping=False)}\n"
            f"💰 Ставка: <b>{bet} 🪙</b>\n"
            f"📈 Запуск двигателей... [🚀☁️☁️☁️☁️☁️☁️]\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Приготовьтесь забрать куш!</i> 😸",
            reply_markup=markup,
            parse_mode='HTML'
        )
    except Exception as exc:
        active_crash.pop(game_id, None)
        _adjust_balance(econ, bet)
        reverse_casino_bet(bet, chat_id)
        print(f"[CRASH START SEND ERROR] {exc}")
        try:
            bot.reply_to(message, '❌ Не удалось запустить Краш. Ставка возвращена. 😿', parse_mode='HTML')
        except Exception:
            pass
        return

    t = threading.Thread(target=crash_game_thread, args=(game_id, message.chat.id, sent_msg.message_id, user_id, user_name, bet, crash_point))
    t.daemon = True
    t.start()

def cmd_stream(message):
    if not can_process_user_message(message):
        return

    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    
    now = time.time()
    cooldown = 3600 * 2
    left = cooldown_text(econ.get('last_stream_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Стримить можно раз в 2 часа! Ждите: <b>{left}</b>. 😿", parse_mode='HTML')
        return
        
    parts = message.text.split(maxsplit=2)
    genre = parts[1].strip() if len(parts) > 1 else random.choice(STREAM_GENRES)
    fmt_key = parts[2].strip().lower() if len(parts) > 2 else 'обычный'
    if fmt_key not in STREAM_FORMATS:
        fmt_key = 'обычный'
    econ['stream_format'] = fmt_key
    
    econ['last_stream_time'] = now
    mark_dirty()
    
    msg = bot.reply_to(message, "🔴 <i>Настройка ОБС и запуск потока...</i> 😺", parse_mode='HTML')
    t = threading.Thread(target=stream_thread, args=(message.chat.id, user_id, user_name, genre, msg.message_id))
    t.daemon = True
    t.start()

def cmd_monopoly(message):
    if not can_process_user_message(message): return
    uid=message.from_user.id; name=(f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    with CALLBACK_STATE_LOCK:
        gid=f"mono_{message.chat.id}_{time.time_ns()}"
        active_monopoly[gid]={'id':gid,'chat_id':message.chat.id,'started':False,'turn':uid,'players':{uid:{'name':name,'money':30000,'pos':0}},'owners':{}}
        game = active_monopoly[gid]
    render_monopoly(message.chat.id,game)

def cmd_garden(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_garden_view(message.chat.id, user_id, user_name)

def cmd_football(message):
    if not can_process_user_message(message):
        return
    m = re.search(r'(?:/football|футбол|пенальти)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(m.group(1)) if m and m.group(1) else 50
    process_sport_dice_game(message, 'football', bet)

def cmd_basketball(message):
    if not can_process_user_message(message):
        return
    m = re.search(r'(?:/basketball|баскетбол)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(m.group(1)) if m and m.group(1) else 50
    process_sport_dice_game(message, 'basketball', bet)

def cmd_darts(message):
    if not can_process_user_message(message):
        return
    m = re.search(r'(?:/darts|дартс)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(m.group(1)) if m and m.group(1) else 50
    process_sport_dice_game(message, 'darts', bet)

def cmd_bowling(message):
    if not can_process_user_message(message):
        return
    m = re.search(r'(?:/bowling|боулинг)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(m.group(1)) if m and m.group(1) else 50
    process_sport_dice_game(message, 'bowling', bet)

def cmd_magic_ball(message):
    if not can_process_user_message(message):
        return
    q = re.sub(r'^(?:/ball|шар)\s*', '', message.text, flags=re.IGNORECASE).strip()
    if not q:
        bot.reply_to(message, "🔮 Задайте вопрос шару судьбы!\nПример: <code>шар пойду ли я сегодня спать вовремя?</code>", parse_mode='HTML')
        return
    ans = random.choice(BALL_RESPONSES)
    bot.reply_to(message, f"🔮 <b>Вопрос:</b> <i>«{html.escape(q)}»</i>\n\n{ans} 😺", parse_mode='HTML')

def cmd_chance(message):
    if not can_process_user_message(message):
        return
    q = re.sub(r'^(?:/chance|шанс)\s*', '', message.text, flags=re.IGNORECASE).strip()
    if not q:
        bot.reply_to(message, "📊 Укажите событие для замера вероятности!\nПример: <code>шанс выиграть джекпот</code>", parse_mode='HTML')
        return
    pct = random.randint(0, 100)
    filled = int(pct / 10)
    bar = "█" * filled + "░" * (10 - filled)
    if pct >= 85: verdict = "🔥 Практически гарантировано!"
    elif pct >= 50: verdict = "👌 Вполне вероятно!"
    elif pct >= 25: verdict = "🎲 Шанс невелик, но он есть."
    else: verdict = "🤏 Почти невозможно..."
    bot.reply_to(message, f"📊 <b>АНАЛИЗ ВЕРОЯТНОСТИ СОБЫТИЯ:</b> 😸\n<i>«{html.escape(q)}»</i>\n━━━━━━━━━━━━━━━━━━━━\nШанс: <b>{pct}%</b> [{bar}]\n💡 Вердикт: <i>{verdict}</i>\n━━━━━━━━━━━━━━━━━━━━", parse_mode='HTML')

def cmd_detector(message):
    if not can_process_user_message(message):
        return
    q = re.sub(r'^(?:/detector|детектор|правда\s+ли\s+что|правда)\s*', '', message.text, flags=re.IGNORECASE).strip()
    if not q:
        bot.reply_to(message, "🕵️‍♂️ Введите утверждение для проверки на полиграфе!\nПример: <code>детектор я самый красивый в чате</code>", parse_mode='HTML')
        return
    verdicts = [
        ("🟢 <b>СВЯТАЯ ИСТИНА!</b>", "Полиграф подтверждает: 100% чистая правда, без единой капли лжи! 🕊✨"),
        ("🟢 <b>ПРАВДА!</b>", "Датчики стабильны, пульс ровный — этому человеку можно верить! 👍"),
        ("🟡 <b>ПОЛУПРАВДА / ПРИУКРАШЕНО!</b>", "Датчики колеблются: доля правды есть, но фантазия разыгралась! 😏"),
        ("🔴 <b>ЛОЖЬ И ПРОВОКАЦИЯ!</b>", "Стрелка полиграфа зашкаливает! Кто-то явно пытается нас обмануть! 🛑"),
        ("🔴 <b>ЧИСТЕЙШАЯ БРЕХНЯ!</b>", "Даже кот семпая не поверил в эту историю! Ложь 10/10! 🤡💥")
    ]
    v_title, v_desc = random.choice(verdicts)
    bot.reply_to(message, f"🕵️‍♂️ <b>СКАНИРОВАНИЕ НА ПОЛИГРАФЕ:</b> 😺\n<i>«{html.escape(q)}»</i>\n━━━━━━━━━━━━━━━━━━━━\nВердикт: {v_title}\n📝 <i>{v_desc}</i>\n━━━━━━━━━━━━━━━━━━━━", parse_mode='HTML')

def cmd_daily_heroes(message):
    if not can_process_user_message(message):
        return
    chat_id = message.chat.id
    econ_items = db.get('economy', {})

    top_msg_user, top_msg_cnt = None, 0
    top_casino_user, top_casino_win = None, 0
    top_transfer_user, top_transfer_amt = None, 0

    for k, info in econ_items.items():
        if not isinstance(info, dict):
            continue
        if int(chat_id) < 0:
            chat_stats = (info.get('msg_stats_chats') or {}).get(str(int(chat_id)), {})
            m_day = chat_stats.get('day_count', 0) if isinstance(chat_stats, dict) else 0
        else:
            m_day = info.get('msg_stats', {}).get('day_count', 0)
        if m_day > top_msg_cnt: top_msg_cnt, top_msg_user = m_day, info
        c_win = info.get('daily_casino_win', 0)
        if c_win > top_casino_win: top_casino_win, top_casino_user = c_win, info
        t_amt = info.get('daily_transferred', 0)
        if t_amt > top_transfer_amt: top_transfer_amt, top_transfer_user = t_amt, info

    speaker_str = f"{make_link(chat_id, top_msg_user.get('display_name'), top_msg_user.get('user_id'), ping=False)} (<b>{top_msg_cnt} смс</b>)" if top_msg_user and top_msg_cnt > 0 else "<i>Никто пока не выделился</i>"
    casino_str = f"{make_link(chat_id, top_casino_user.get('display_name'), top_casino_user.get('user_id'), ping=False)} (<b>+{top_casino_win} 🪙</b>)" if top_casino_user and top_casino_win > 0 else "<i>Никто пока не сорвал куш</i>"
    transfer_str = f"{make_link(chat_id, top_transfer_user.get('display_name'), top_transfer_user.get('user_id'), ping=False)} (<b>{top_transfer_amt} 🪙</b>)" if top_transfer_user and top_transfer_amt > 0 else "<i>Переводов сегодня не было</i>"

    text = (
        "🏆 <b>ГЕРОИ И УДАРНИКИ СЕГОДНЯШНЕГО ДНЯ</b> 😺\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🗣 <b>Главный спикер дня:</b>\n👉 {speaker_str}\n\n"
        f"🎰 <b>Гроза казино и спорта:</b>\n👉 {casino_str}\n\n"
        f"💖 <b>Главный меценат чата:</b>\n👉 {transfer_str}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👑 <i>Герои дня получают почёт, уважение и статус в чате на 24 часа!</i> 😻"
    )
    bot.reply_to(message, text, parse_mode='HTML')

def cmd_backpack(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_backpack_view(message.chat.id, message.from_user.id, user_name)

def cmd_wheel(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    now = time.time()
    last_spin = econ.get('last_wheel_time', 0)
    cooldown = 43200

    left = cooldown_text(last_spin, cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ <b>Колесо Фортуны доступно раз в 12 часов!</b> 😿\nСледующее бесплатное вращение через: <b>{left}</b>.", parse_mode='HTML')
        return

    econ['last_wheel_time'] = now
    sectors = [
        ('coins_100', '💰 100 Ня-коинов', 30), ('coins_300', '💵 300 Ня-коинов', 20),
        ('jackpot', '💎 ДЖЕКПОТ 1,000 🪙', 5), ('fish', '🐟 Случайный редкий улов', 15),
        ('beast', '🏹 Охотничий трофей', 15), ('exp', '⭐ +80 Опыта профиля', 10),
        ('karma', '😇 +5 Кармы (Светлый путь)', 5)
    ]
    weights = [s[2] for s in sectors]
    win_sector = random.choices(sectors, weights=weights, k=1)[0]
    win_key = win_sector[0]

    prize_text = ""
    if win_key == 'coins_100':
        _adjust_balance(econ, 100)
        prize_text = "💰 Вы выиграли <b>+100 Ня-коинов 🪙</b>! 😸"
    elif win_key == 'coins_300':
        _adjust_balance(econ, 300)
        prize_text = "💵 Вы выиграли <b>+300 Ня-коинов 🪙</b>! 😻"
    elif win_key == 'jackpot':
        _adjust_balance(econ, 1000)
        prize_text = "💎👑 <b>МЕГА ДЖЕКПОТ! +1,000 Ня-коинов 🪙</b>! 🙀"
        log_event('КОЛЕСО: ДЖЕКПОТ', f'{make_link(message.chat.id, user_name, user_id, ping=False)} сорвал джекпот Колеса Фортуны (1,000 🪙)!')
    elif win_key == 'fish':
        trophy = random.choice(FISH_TYPES)[0]
        add_inventory_item(econ['fish_inventory'], trophy)
        prize_text = f"🐟 Вы выловили: <b>{trophy}</b>! 😺"
    elif win_key == 'beast':
        trophy = random.choice(HUNT_TYPES)[0]
        add_inventory_item(econ['hunt_inventory'], trophy)
        prize_text = f"🏹 Вы добыли: <b>{trophy}</b>! 😺"
    elif win_key == 'exp':
        add_account_exp(user_id, user_name, 80, username=message.from_user.username)
        prize_text = "⭐ Вы получили <b>+80 EXP опыта профиля</b>! 😸"
    elif win_key == 'karma':
        change_karma(user_id, user_name, 5)
        prize_text = "😇 Вы выиграли <b>+5 Кармы</b>! 😻"

    check_achievements(user_id, user_name, 'wheel_spins', 1, message.chat.id, username=message.from_user.username)
    mark_dirty()

    anim_text = (
        "🎡 <b>КОЛЕСО ФОРТУНЫ КРУТИТСЯ...</b> 😺\n\n"
        "▫️ [ 💰 100 🪙 ]\n▫️ [ 💵 300 🪙 ]\n▫️ [ 💎 ДЖЕКПОТ 1,000 🪙 ]\n▫️ [ 🐟 Рыба / 🏹 Дичь ]\n▫️ [ 😇 Карма +5 ]\n\n"
        f"🎉 <b>Стрелка остановилась на секторе:</b>\n👉 <b>{win_sector[1]}</b>!\n\n{prize_text}"
    )
    bot.reply_to(message, anim_text, parse_mode='HTML')

def cmd_mines(message):
    if not can_process_user_message(message):
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    match = re.search(r'(?:/mines|мины|сапер)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(match.group(1)) if match and match.group(1) else 50

    if bet <= 0:
        bot.reply_to(message, "❌ Ставка должна быть больше 0! 😾")
        return

    if econ['balance'] < bet:
        bot.reply_to(message, f"❌ Недостаточно средств! У вас: {econ['balance']} 🪙 😿")
        return

    _adjust_balance(econ, -(bet))
    process_casino_bet(bet, chat_id)

    game_id = f"m_{user_id}_{time.time_ns()}"
    active_mines[game_id] = {
        'user_id': user_id,
        'user_tag': user_name,
        'username': message.from_user.username,
        'chat_id': message.chat.id,
        'bet': bet,
        'size': 4,
        'bombs': set(),
        'revealed': set(),
        'current_multiplier': 1.0,
        'finished': False,
        'start_time': time.time()
    }

    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("3x3 (9 кл.)", callback_data=f"msz_{game_id}_3:{user_id}"),
        InlineKeyboardButton("4x4 (16 кл.)", callback_data=f"msz_{game_id}_4:{user_id}"),
        InlineKeyboardButton("5x5 (25 кл.)", callback_data=f"msz_{game_id}_5:{user_id}"),
        InlineKeyboardButton("6x6 (36 кл.) 🔥", callback_data=f"msz_{game_id}_6:{user_id}")
    )
    markup.add(InlineKeyboardButton("❌ Отмена (вернуть ставку)", callback_data=f"mcancel_{game_id}:{user_id}"))

    try:
        bot.reply_to(
            message,
            f"💣 <b>НАСТРОЙКА ИГРЫ «САПЁР»</b> 😺\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Ставка: <b>{bet} 🪙</b>\n\n"
            f"Шаг 1: <b>Выберите размер игрового поля:</b> 😸",
            reply_markup=markup,
            parse_mode='HTML'
        )
    except Exception as exc:
        active_mines.pop(game_id, None)
        _adjust_balance(econ, bet)
        reverse_casino_bet(bet, chat_id)
        print(f"[MINES START SEND ERROR] {exc}")
        try:
            bot.reply_to(message, '❌ Не удалось запустить Сапёра. Ставка возвращена. 😿', parse_mode='HTML')
        except Exception:
            pass

def cmd_classic_mines(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    
    markup = InlineKeyboardMarkup(row_width=1)
    for d_key, d_val in CSAPER_DIFFICULTIES.items():
        markup.add(InlineKeyboardButton(f"{d_val['name']} — приз {d_val['reward']} 🪙", callback_data=f"cstart_{d_key}:{user_id}"))
        
    bot.reply_to(
        message,
        "🕹 <b>КЛАССИЧЕСКИЙ САПЁР (БЕЗ СТАВОК)</b> 🧠 😺\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Игра полностью бесплатная и проверяет только вашу логику и ум!\n\n"
        "👇 <b>Выберите уровень сложности:</b>",
        reply_markup=markup,
        parse_mode='HTML'
    )

def cmd_durak(message):
    if not can_process_user_message(message):
        return

    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    m = re.search(r'(?:/durak|дурак)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(m.group(1)) if m and m.group(1) else 0

    if bet > 0 and econ['balance'] < bet:
        bot.reply_to(message, f"❌ Недостаточно коинов для ставки! Ваш баланс: {econ['balance']} 🪙 😿", parse_mode='HTML')
        return

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🤖 Соло (Против Бота)", callback_data=f"durak_mode_1_0:{user_id}"),
        InlineKeyboardButton("👥 2 Игрока", callback_data=f"durak_mode_2_{bet}:{user_id}")
    )
    markup.add(
        InlineKeyboardButton("👥 3 Игрока", callback_data=f"durak_mode_3_{bet}:{user_id}"),
        InlineKeyboardButton("👥 4 Игрока", callback_data=f"durak_mode_4_{bet}:{user_id}")
    )
    markup.add(
        InlineKeyboardButton("👥 5 Игроков", callback_data=f"durak_mode_5_{bet}:{user_id}"),
        InlineKeyboardButton("👥 6 Игроков", callback_data=f"durak_mode_6_{bet}:{user_id}")
    )

    bot.reply_to(
        message,
        f"🃏 <b>КАРТОЧНАЯ ИГРА «ДУРАК» (36 КАРТ)</b> 😺\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Ставка: <b>{bet} Ня-коинов 🪙</b>\n\n"
        f"Выберите режим игры на кнопках ниже: 😸",
        reply_markup=markup,
        parse_mode='HTML'
            )

def cmd_dick(message):
    if not can_process_user_message(message):
        return

    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    now = time.time()
    last_time = econ.get('last_dick_time', 0)
    cooldown = 1200

    left = cooldown_text(last_time, cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Замер писюна доступен раз в 20 минут! 😿\nПодождите: <b>{left}</b>.", parse_mode='HTML')
        return

    # Сбалансированное распределение изменений с околонулевым матожиданием
    change_pool = [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5]
    if random.random() < 0.05:
        change = random.choice([-8, 8])
    else:
        change = random.choice(change_pool)
    cur_size = econ.get('dick_size', 15)
    new_size = max(1, min(150, cur_size + change))

    econ['dick_size'] = new_size
    econ['last_dick_time'] = now
    mark_dirty()

    sign = "+" if change >= 0 else ""
    u_link = make_link(chat_id, user_name, user_id, ping=True)

    if new_size >= 100: comment = "🌌 Космический монумент масштабов галактики! Вселенная склоняет колени! 🙀"
    elif new_size >= 70: comment = "🗿 Колосс Родосский нервно курит в сторонке! Невероятный титан! 🙀"
    elif new_size >= 45: comment = "👑 Абсолютный повелитель и гигант чата! 😻"
    elif new_size >= 30: comment = "🍆 Внушительный и устрашающий размерчик! 😸"
    elif new_size >= 18: comment = "🔥 Крепкий и солидный инструмент! 😺"
    elif new_size >= 10: comment = "👌 Классический средний размер. 😽"
    else: comment = "🤏 Кажется, на улице было слишком морозно... 😿"

    bot.reply_to(
        message,
        f"🍆 <b>АНАТОМИЧЕСКИЙ ЗАМЕР:</b> {u_link}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Размер писюна: <b>{new_size} см ({sign}{change} см) 📏</b>\n"
        f"📝 <i>{comment}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode='HTML'
    )

def cmd_fap(message):
    if not can_process_user_message(message):
        return

    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    today = daily_task_date()
    if econ.get('fap_date') != today:
        econ['fap_date'] = today
        econ['fap_count'] = 0

    now = time.time()
    last_fap = econ.get('last_fap_time', 0)
    cooldown = 600
    left = cooldown_text(last_fap, cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Рука должна отдохнуть! Подождите: <b>{left}</b>. 😿", parse_mode='HTML')
        return

    econ['fap_count'] = econ.get('fap_count', 0) + 1
    econ['last_fap_time'] = now
    count = econ['fap_count']
    mark_dirty()

    if count == 1: rank = "🌱 Начинающий любитель"
    elif count <= 3: rank = "🥋 Уверенный практик"
    elif count <= 6: rank = "🔥 Магистр мозолей"
    elif count <= 10: rank = "⚡️ Скоростной виртуоз"
    else: rank = "💀 Кибер-рука (Остановись, отвалится!)"

    u_link = make_link(message.chat.id, user_name, user_id, ping=True)
    bot.reply_to(
        message,
        f"💦 <b>СЕАНС ФАПА УСПЕШНО ЗАВЕРШЕН!</b> 😺\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Участник: {u_link}\n"
        f"📊 Подходов за сегодня: <b>{count} раз(а)</b>\n"
        f"🎖 Ранг: <b>{rank}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode='HTML'
    )

def cmd_coinflip(message):
    if not can_process_user_message(message): return
    parts=(message.text or '').split()
    bet=50
    side=random.choice(('орёл','решка'))
    for part in parts[1:]:
        if part.isdigit(): bet=int(part); continue
        if part.lower() in ('орел','орёл','heads','h','о'): side='орёл'
        elif part.lower() in ('решка','tails','t','р'): side='решка'
    if bet<10:
        bot.reply_to(message,'❌ Минимальная ставка — 10 🪙.'); return
    uid=message.from_user.id; name=(f'{message.from_user.first_name or ""} {message.from_user.last_name or ""}').strip() or message.from_user.username or 'Игрок'
    with _get_user_action_lock(uid):
        econ=get_user_econ(uid,name,username=message.from_user.username)
        with BALANCE_TX_LOCK:
            with db_lock:
                balance=int(econ.get('balance',0) or 0)
                if balance < bet:
                    bot.reply_to(message,f'❌ Недостаточно средств. Баланс: {balance:,} 🪙'); return
                econ['balance']=balance-bet
                mark_dirty()
        process_casino_bet(bet,message.chat.id)
        result=random.choice(('орёл','решка'))
        if result==side:
            win=process_casino_win(int(bet*1.9))
            with BALANCE_TX_LOCK:
                with db_lock:
                    econ['balance']=int(econ.get('balance',0) or 0)+win
                    mark_dirty()
            bot.reply_to(message,f'🪙 <b>МОНЕТКА</b>\nВаша ставка: <b>{bet} 🪙</b> на <b>{side}</b>\nВыпало: <b>{result}</b> 🪙\n🎉 Вы получили <b>+{win} 🪙</b>!',parse_mode='HTML')
        else:
            bot.reply_to(message,f'🪙 <b>МОНЕТКА</b>\nВаша ставка: <b>{bet} 🪙</b> на <b>{side}</b>\nВыпало: <b>{result}</b>\n😿 Ставка проиграна.',parse_mode='HTML')

def cmd_bj(message):
    if not can_process_user_message(message):
        return
    match = re.search(r'(?:/bj|blackjack|блэкджек|21)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(match.group(1)) if match and match.group(1) else 50
    process_bj_game(message, bet)

def cmd_rps(message):
    if not can_process_user_message(message):
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    target_user, target_user_id, raw_args = parse_target_and_args(message, '/rps')
    if not target_user: target_user, target_user_id, raw_args = parse_target_and_args(message, 'цуефа')

    match = re.search(r'(\d+)', raw_args)
    bet = int(match.group(1)) if match else 50

    if not target_user or not target_user_id:
        bot.reply_to(message, "❌ Формат: <code>/rps @username 100</code> или ответом на сообщение. Соперник должен быть в чате! 😾", parse_mode='HTML')
        return

    if target_user_id == user_id:
        bot.reply_to(message, "❌ Нельзя играть с самим собой! 🙀")
        return
        
    if bet < 30:
        bot.reply_to(message, "❌ Минимальная ставка — 30 Ня-коинов! 😾")
        return

    game_id = f"rps_{user_id}_{target_user_id}_{time.time_ns()}"
    with serialized_multi_user_action(user_id, target_user_id):
        target_econ = get_user_econ(target_user_id, target_user)
        my_balance = int(econ.get('balance', 0) or 0)
        target_balance = int(target_econ.get('balance', 0) or 0)
        if my_balance < bet:
            bot.reply_to(message, f"❌ У вас недостаточно Ня-коинов! Ваш баланс: {my_balance} 🪙 😿")
            return
        if target_balance < bet:
            bot.reply_to(message, f"❌ У соперника недостаточно коинов для ставки ({target_balance} / {bet} 🪙)! 😿")
            return
        _adjust_balance(econ, -bet)
        _adjust_balance(target_econ, -bet)
        active_rps_games[game_id] = {
        'p1_id': user_id, 'p1_tag': user_name,
        'p2_id': target_user_id, 'p2_tag': target_user,
            'bet': bet, 'p1_choice': None, 'p2_choice': None,
            'start_time': time.time(), 'finished': False
        }
        mark_dirty()

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🪨 Камень", callback_data=f"rps_r_{game_id}"),
        InlineKeyboardButton("✂️ Ножницы", callback_data=f"rps_s_{game_id}"),
        InlineKeyboardButton("📄 Бумага", callback_data=f"rps_p_{game_id}")
    )

    try:
        bot.send_message(
            chat_id,
            f"✌️ <b>ДУЭЛЬ: КАМЕНЬ-НОЖНИЦЫ-БУМАГА!</b> 😺\n━━━━━━━━━━━━━━━━━━━━\n"
            f"⚔️ {make_link(chat_id, user_name, user_id, ping=True)} VS {make_link(chat_id, target_user, target_user_id, ping=True)}\n"
            f"💰 Ставка: <b>{bet} 🪙</b> с каждого (Общий банк: <b>{bet * 2} 🪙</b>)!\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Оба дуэлянта, сделайте свой выбор на кнопках ниже:</i> 😸",
            reply_markup=markup, parse_mode='HTML'
        )
    except Exception as exc:
        active_rps_games.pop(game_id, None)
        # The action handler is already serialized for the initiating user;
        # use the ordered helper for the two-account refund.
        with serialized_multi_user_action(user_id, target_user_id):
            live_econ = get_user_econ(user_id, user_name, username=message.from_user.username)
            live_target = get_user_econ(target_user_id, target_user)
            _adjust_balance(live_econ, bet)
            _adjust_balance(live_target, bet)
            mark_dirty()
        print(f"[RPS START SEND ERROR] {exc}")
        try:
            bot.reply_to(message, '❌ Не удалось создать дуэль. Обе ставки возвращены. 😿', parse_mode='HTML')
        except Exception:
            pass

def cmd_memes(message):
    if not can_process_user_message(message): return
    finalize_meme_contests()
    chat_id=message.chat.id; today=daily_task_date()
    entries=[m for m in db.get('daily_memes',[]) if m.get('chat_id')==chat_id and m.get('date')==today]
    if not entries:
        bot.reply_to(message,'📸 <b>Мемов сегодня ещё нет.</b>\nОпубликуйте первый через <code>/meme</code>! 😸',parse_mode='HTML'); return
    entries.sort(key=lambda m: len(m.get('likes',[]))-len(m.get('dislikes',[])), reverse=True)
    lines=['📸 <b>МЕМЫ ДНЯ</b>','━━━━━━━━━━━━━━━━━━━━']
    for i,m in enumerate(entries[:10],1):
        score=len(m.get('likes',[]))-len(m.get('dislikes',[]))
        lines.append(f"{i}. {make_link(chat_id,m.get('author_name','Пользователь'),m.get('author_id'),ping=False)} — 🔥 {len(m.get('likes',[]))} / 💩 {len(m.get('dislikes',[]))} — <b>{score:+d}</b>")
    lines.append('━━━━━━━━━━━━━━━━━━━━'); lines.append('🏆 Победитель предыдущего дня получает 1 500 🪙 автоматически.')
    bot.reply_to(message,'\n'.join(lines),parse_mode='HTML')

def cmd_meme(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    chat_id = message.chat.id

    in_j, left_j = is_in_jail(user_id)
    if in_j:
        bot.reply_to(message, f"🔒 В КПЗ нельзя публиковать мемы! До выхода: <b>{left_j} мин.</b> 😿", parse_mode='HTML')
        return

    finalize_meme_contests()
    meme_id = f"m_{chat_id}_{message.message_id}"
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🔥 0", callback_data=f"meme_l_{meme_id}"),
        InlineKeyboardButton("💩 0", callback_data=f"meme_d_{meme_id}")
    )

    u_link = make_link(chat_id, user_name, user_id, ping=False)
    caption_text = f"🎭 <b>МЕМ ЧАТА</b> | Автор: {u_link}\n<i>Голосуйте реакциями ниже! Автор лучшего мема дня получит 1,500 🪙!</i> 😸"

    meme_entry = {'meme_id': meme_id, 'author_id': user_id, 'author_name': user_name, 'chat_id': chat_id, 'likes': [], 'dislikes': [], 'date': daily_task_date(), 'winner_paid': False}
    with MEME_LOCK:
        active_memes[meme_id] = {**meme_entry, 'likes': set(), 'dislikes': set()}
        db.setdefault('daily_memes', []).append(meme_entry)
    mark_dirty()

    add_bp_exp(user_id, user_name, 10, username=message.from_user.username)
    bot.reply_to(message, caption_text, reply_markup=markup, parse_mode='HTML')

def cmd_story(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    chat_id = message.chat.id

    target_user, target_user_id, _ = parse_target_and_args(message, '/story')
    if not target_user:
        target_user, target_user_id, _ = parse_target_and_args(message, 'история_дня')

    if not target_user or target_user_id == user_id:
        target_user = "Семпай"
        target_user_id = None

    u1_link = make_link(chat_id, user_name, user_id, ping=False)
    u2_link = make_link(chat_id, target_user, target_user_id, ping=False) if target_user_id else f"<b>{html.escape(target_user)}</b>"

    template = random.choice(STORY_TEMPLATES)
    story_text = template.format(u1=u1_link, u2=u2_link)

    add_account_exp(user_id, user_name, 10, username=message.from_user.username)
    bot.reply_to(message, story_text, parse_mode='HTML')

def cmd_resources_command(message):
    command_token = (message.text or '').split()[0].lower() if message.text else ''
    if command_token in ('/collection', '/коллекция'):
        cmd_collection(message)
    else:
        if not can_process_user_message(message): return
        uid = message.from_user.id
        name = (f'{message.from_user.first_name or ""} {message.from_user.last_name or ""}').strip() or message.from_user.username or 'Игрок'
        render_resources_view(message.chat.id, uid, name)

def cmd_guild_command(message):
    if not can_process_user_message(message):
        return
    cmd_guild(message)

def cmd_player_market_command(message):
    if not can_process_user_message(message):
        return
    cmd_player_market(message)

def cmd_raid_command(message):
    if not can_process_user_message(message):
        return
    cmd_raid(message)

def cmd_season_command(message):
    if not can_process_user_message(message):
        return
    cmd_season(message)

def cmd_world_command(message):
    if not can_process_user_message(message):
        return
    cmd_world(message)

def register(ctx, only=None):
    """Register selected handlers from this feature module."""
    _inject(ctx)
    bot = ctx["bot"]
    wanted = set(only) if only is not None else set(HANDLER_NAMES)
    registered = []
    if "cmd_mini_games" in wanted:
        _handler = cmd_mini_games
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['games', 'игры', 'миниигры'])(_handler)
        ctx["cmd_mini_games"] = _handler
        globals()["cmd_mini_games"] = _handler
        registered.append("cmd_mini_games")
    if "cmd_fact_vd" in wanted:
        _handler = cmd_fact_vd
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['fact_vd', 'vd_fact'])(_handler)
        ctx["cmd_fact_vd"] = _handler
        globals()["cmd_fact_vd"] = _handler
        registered.append("cmd_fact_vd")
    if "cmd_trash" in wanted:
        _handler = cmd_trash
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['trash', 'мусорка', 'помойка'])(_handler)
        ctx["cmd_trash"] = _handler
        globals()["cmd_trash"] = _handler
        registered.append("cmd_trash")
    if "cmd_promo" in wanted:
        _handler = cmd_promo
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['promo', 'промо', 'промокод'])(_handler)
        ctx["cmd_promo"] = _handler
        globals()["cmd_promo"] = _handler
        registered.append("cmd_promo")
    if "cmd_brick" in wanted:
        _handler = cmd_brick
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['brick', 'кирпич'])(_handler)
        ctx["cmd_brick"] = _handler
        globals()["cmd_brick"] = _handler
        registered.append("cmd_brick")
    if "cmd_crash" in wanted:
        _handler = cmd_crash
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['crash', 'краш', 'ракета'])(_handler)
        ctx["cmd_crash"] = _handler
        globals()["cmd_crash"] = _handler
        registered.append("cmd_crash")
    if "cmd_stream" in wanted:
        _handler = cmd_stream
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['stream', 'стрим'])(_handler)
        ctx["cmd_stream"] = _handler
        globals()["cmd_stream"] = _handler
        registered.append("cmd_stream")
    if "cmd_monopoly" in wanted:
        _handler = cmd_monopoly
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['monopoly', 'монополия'])(_handler)
        ctx["cmd_monopoly"] = _handler
        globals()["cmd_monopoly"] = _handler
        registered.append("cmd_monopoly")
    if "cmd_garden" in wanted:
        _handler = cmd_garden
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['garden', 'сад'])(_handler)
        ctx["cmd_garden"] = _handler
        globals()["cmd_garden"] = _handler
        registered.append("cmd_garden")
    if "cmd_football" in wanted:
        _handler = cmd_football
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['football', 'футбол', 'пенальти'])(_handler)
        ctx["cmd_football"] = _handler
        globals()["cmd_football"] = _handler
        registered.append("cmd_football")
    if "cmd_basketball" in wanted:
        _handler = cmd_basketball
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['basketball', 'баскетбол'])(_handler)
        ctx["cmd_basketball"] = _handler
        globals()["cmd_basketball"] = _handler
        registered.append("cmd_basketball")
    if "cmd_darts" in wanted:
        _handler = cmd_darts
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['darts', 'дартс'])(_handler)
        ctx["cmd_darts"] = _handler
        globals()["cmd_darts"] = _handler
        registered.append("cmd_darts")
    if "cmd_bowling" in wanted:
        _handler = cmd_bowling
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['bowling', 'боулинг'])(_handler)
        ctx["cmd_bowling"] = _handler
        globals()["cmd_bowling"] = _handler
        registered.append("cmd_bowling")
    if "cmd_magic_ball" in wanted:
        _handler = cmd_magic_ball
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['ball', 'шар'])(_handler)
        ctx["cmd_magic_ball"] = _handler
        globals()["cmd_magic_ball"] = _handler
        registered.append("cmd_magic_ball")
    if "cmd_chance" in wanted:
        _handler = cmd_chance
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['chance', 'шанс'])(_handler)
        ctx["cmd_chance"] = _handler
        globals()["cmd_chance"] = _handler
        registered.append("cmd_chance")
    if "cmd_detector" in wanted:
        _handler = cmd_detector
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['detector', 'детектор', 'правда'])(_handler)
        ctx["cmd_detector"] = _handler
        globals()["cmd_detector"] = _handler
        registered.append("cmd_detector")
    if "cmd_daily_heroes" in wanted:
        _handler = cmd_daily_heroes
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['daily_heroes', 'герои_дня', 'ударники'])(_handler)
        ctx["cmd_daily_heroes"] = _handler
        globals()["cmd_daily_heroes"] = _handler
        registered.append("cmd_daily_heroes")
    if "cmd_backpack" in wanted:
        _handler = cmd_backpack
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['backpack', 'рюкзак', 'инвентарь_баффов'])(_handler)
        ctx["cmd_backpack"] = _handler
        globals()["cmd_backpack"] = _handler
        registered.append("cmd_backpack")
    if "cmd_wheel" in wanted:
        _handler = cmd_wheel
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['wheel', 'рулетка', 'колесо'])(_handler)
        ctx["cmd_wheel"] = _handler
        globals()["cmd_wheel"] = _handler
        registered.append("cmd_wheel")
    if "cmd_mines" in wanted:
        _handler = cmd_mines
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['mines', 'мины', 'сапер'])(_handler)
        ctx["cmd_mines"] = _handler
        globals()["cmd_mines"] = _handler
        registered.append("cmd_mines")
    if "cmd_classic_mines" in wanted:
        _handler = cmd_classic_mines
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['minesweeper', 'csaper', 'сапер_классик', 'сапёр_классик'])(_handler)
        ctx["cmd_classic_mines"] = _handler
        globals()["cmd_classic_mines"] = _handler
        registered.append("cmd_classic_mines")
    if "cmd_durak" in wanted:
        _handler = cmd_durak
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['durak', 'дурак'])(_handler)
        ctx["cmd_durak"] = _handler
        globals()["cmd_durak"] = _handler
        registered.append("cmd_durak")
    if "cmd_dick" in wanted:
        _handler = cmd_dick
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['dick', 'писюн', 'замер'])(_handler)
        ctx["cmd_dick"] = _handler
        globals()["cmd_dick"] = _handler
        registered.append("cmd_dick")
    if "cmd_fap" in wanted:
        _handler = cmd_fap
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['fap', 'дроч', 'подрочить'])(_handler)
        ctx["cmd_fap"] = _handler
        globals()["cmd_fap"] = _handler
        registered.append("cmd_fap")
    if "cmd_coinflip" in wanted:
        _handler = cmd_coinflip
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['coinflip', 'монетка'])(_handler)
        ctx['cmd_coinflip'] = _handler; globals()['cmd_coinflip'] = _handler; registered.append('cmd_coinflip')
    if "cmd_bj" in wanted:
        _handler = cmd_bj
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['bj', 'blackjack', 'блэкджек', '21'])(_handler)
        ctx["cmd_bj"] = _handler
        globals()["cmd_bj"] = _handler
        registered.append("cmd_bj")
    if "cmd_rps" in wanted:
        _handler = cmd_rps
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['rps', 'цуефа'])(_handler)
        ctx["cmd_rps"] = _handler
        globals()["cmd_rps"] = _handler
        registered.append("cmd_rps")
    if "cmd_memes" in wanted:
        _handler = cmd_memes
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['memes', 'мемы'])(_handler)
        ctx["cmd_memes"] = _handler
        globals()["cmd_memes"] = _handler
        registered.append("cmd_memes")
    if "cmd_meme" in wanted:
        _handler = cmd_meme
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['meme', 'мем'])(_handler)
        ctx["cmd_meme"] = _handler
        globals()["cmd_meme"] = _handler
        registered.append("cmd_meme")
    if "cmd_story" in wanted:
        _handler = cmd_story
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['story', 'fanfic', 'история_дня'])(_handler)
        ctx["cmd_story"] = _handler
        globals()["cmd_story"] = _handler
        registered.append("cmd_story")
    if "cmd_resources_command" in wanted:
        _handler = cmd_resources_command
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['resources', 'ресурсы', 'collection', 'коллекция'])(_handler)
        ctx["cmd_resources_command"] = _handler
        globals()["cmd_resources_command"] = _handler
        registered.append("cmd_resources_command")
    if "cmd_guild_command" in wanted:
        _handler = cmd_guild_command
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['guild', 'гильдия', 'клан'])(_handler)
        ctx["cmd_guild_command"] = _handler
        globals()["cmd_guild_command"] = _handler
        registered.append("cmd_guild_command")
    if "cmd_player_market_command" in wanted:
        _handler = cmd_player_market_command
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['pmarket', 'рынок_игроков'])(_handler)
        ctx["cmd_player_market_command"] = _handler
        globals()["cmd_player_market_command"] = _handler
        registered.append("cmd_player_market_command")
    if "cmd_raid_command" in wanted:
        _handler = cmd_raid_command
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['raid', 'рейд'])(_handler)
        ctx["cmd_raid_command"] = _handler
        globals()["cmd_raid_command"] = _handler
        registered.append("cmd_raid_command")
    if "cmd_season_command" in wanted:
        _handler = cmd_season_command
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['season', 'сезон', 'рейтинг_сезона'])(_handler)
        ctx["cmd_season_command"] = _handler
        globals()["cmd_season_command"] = _handler
        registered.append("cmd_season_command")
    if "cmd_world_command" in wanted:
        _handler = cmd_world_command
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['world', 'мир', 'карта'])(_handler)
        ctx["cmd_world_command"] = _handler
        globals()["cmd_world_command"] = _handler
        registered.append("cmd_world_command")
    return registered
