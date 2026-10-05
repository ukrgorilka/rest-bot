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


HANDLER_NAMES = ['cmd_global_stats', 'cmd_economy_stats', 'cmd_game_stats', 'cmd_bot_status', 'cmd_dashboard', 'admin_force_save_command', 'admin_give_gif_command', 'admin_give_stars_all_command', 'admin_give_command', 'dragon_audio_file_id']


def cmd_global_stats(message):
    if not _owner_only(message): return
    total,users=_global_message_stats(); active=len(_bot_chat_items(True)); all_groups=len(db.get('bot_chats',{})); profiles=len(db.get('economy',{}))
    bot.reply_to(message,f"📊 <b>ОБЩАЯ СТАТИСТИКА БОТА</b>\n━━━━━━━━━━━━━━━━━━━━\n🟢 Активных групп: <b>{active}</b>\n📋 Сохранённых групп: <b>{all_groups}</b>\n👤 Профилей: <b>{profiles}</b>\n💬 Сообщений в учёте: <b>{total:,}</b>\n👥 Пользователей с активностью: <b>{users}</b>\n⏱ Аптайм: <b>{_fmt_duration(time.time()-BOT_STARTED_AT)}</b>",parse_mode='HTML')

def cmd_economy_stats(message):
    if not _owner_only(message): return
    total_coins=total_bank=total_stars=0
    for econ in db.get('economy',{}).values():
        if isinstance(econ,dict): total_coins+=int(econ.get('balance',0) or 0); total_bank+=int(econ.get('bank_deposit',0) or 0); total_stars+=int(econ.get('stars_donated',0) or 0)
    bot.reply_to(message,f'💰 <b>ЭКОНОМИКА БОТА</b>\n━━━━━━━━━━━━━━━━━━━━\n🪙 Монет на руках: <b>{total_coins:,}</b>\n🏦 Монет в банках: <b>{total_bank:,}</b>\n💎 Stars в статистике донатов: <b>{total_stars:,}</b>',parse_mode='HTML')

def cmd_game_stats(message):
    if not _owner_only(message): return
    totals={k:0 for k in ('games','wheel_spins','cases_opened','mines_wins','fish','hunt')}
    for econ in db.get('economy',{}).values():
        stats=econ.get('stats',{}) if isinstance(econ,dict) else {}
        if isinstance(stats,dict):
            for k in totals: totals[k]+=int(stats.get(k,0) or 0)
    bot.reply_to(message,f'🎮 <b>СТАТИСТИКА ИГР</b>\n━━━━━━━━━━━━━━━━━━━━\n🎲 Всего игр: <b>{totals["games"]:,}</b>\n🎡 Колесо: <b>{totals["wheel_spins"]:,}</b>\n📦 Кейсов: <b>{totals["cases_opened"]:,}</b>\n💣 Побед в сапёре: <b>{totals["mines_wins"]:,}</b>\n🎣 Рыбалка: <b>{totals["fish"]:,}</b>\n🏹 Охота: <b>{totals["hunt"]:,}</b>',parse_mode='HTML')

def cmd_bot_status(message):
    if not _owner_only(message): return
    bot_state='🟢 работает' if db.get('bot_active',True) else '🔴 спящий режим'; neon='🟢 подключена' if DATABASE_URL else '🟡 локальный fallback'
    bot.reply_to(message,f"🤖 <b>NYABOT STATUS</b>\n━━━━━━━━━━━━━━━━━━━━\n🤖 Состояние: <b>{bot_state}</b>\n💾 Neon: <b>{neon}</b>\n🏢 Активных групп: <b>{len(_bot_chat_items(True))}</b>\n💾 Несохранённых изменений: <b>{'да' if db_dirty else 'нет'}</b>\n⏱ Аптайм: <b>{_fmt_duration(time.time()-BOT_STARTED_AT)}</b>\n⚡ Версия: <b>v{BOT_VERSION}</b>",parse_mode='HTML')

def cmd_dashboard(message):
    if not _owner_only(message): return
    total,_=_global_message_stats(); active=len(_bot_chat_items(True)); all_groups=len(db.get('bot_chats',{}))
    bot.reply_to(message,f"📊 <b>ПАНЕЛЬ МОНИТОРИНГА</b>\n━━━━━━━━━━━━━━━━━━━━\n🟢 Групп сейчас: <b>{active}</b>\n📋 Записей групп: <b>{all_groups}</b>\n💬 Сообщений: <b>{total:,}</b>\n⏱ Аптайм: <b>{_fmt_duration(time.time()-BOT_STARTED_AT)}</b>\n\n📋 /groups — все группы\n📈 /activity — активность\n📊 /stats — статистика\n🟢 /status — состояние\n🔎 /findgroup ID — найти группу\n👤 /user ID — найти пользователя\n💰 /economystats — экономика\n🎮 /gamestats — игры\n🔎 /groupinfo — текущая группа",parse_mode='HTML')

def admin_force_save_command(message):
    """Owner-only: немедленно сохраняет актуальную базу в JSON + Neon и отправляет JSON-бэкап в DB_CHANNEL_ID."""
    if not _is_owner_admin(message):
        return
    try:
        save_data(send_backup=True)
        bot.reply_to(
            message,
            f"💾 <b>ПРИНУДИТЕЛЬНОЕ СОХРАНЕНИЕ ВЫПОЛНЕНО</b>\n"
            f"📄 <code>{html.escape(DATA_FILE)}</code>\n"
            f"☁️ Neon: {'сохранён' if DATABASE_URL else 'не настроен'}\n"
            f"📦 Telegram-бэкап: {'отправлен в DB_CHANNEL_ID' if DB_CHANNEL_ID else 'DB_CHANNEL_ID не задан'}",
            parse_mode='HTML'
        )
    except Exception as e:
        bot.reply_to(message, f"❌ <b>Ошибка принудительного сохранения:</b> <code>{html.escape(str(e))}</code>", parse_mode='HTML')

def admin_give_gif_command(message):
    if not _is_owner_admin(message):
        return
    parts = (message.text or '').strip().split()
    if len(parts) < 3:
        bot.reply_to(message, "❌ Формат: <code>/give_gif @username gulya</code>\n\nДоступные GIF: <code>gulya</code>, <code>sakura_gif</code>, <code>mogger</code>, <code>cat</code>.", parse_mode='HTML')
        return
    target_raw, gif_id = parts[1], parts[2].lower()
    if gif_id not in PROFILE_GIFS:
        bot.reply_to(message, "❌ Такой GIF не найден. Используй: <code>gulya</code>, <code>sakura_gif</code>, <code>mogger</code>, <code>cat</code>.", parse_mode='HTML')
        return
    if message.reply_to_message and target_raw.lower() in ('reply', '.', '-', '@reply', 'this'):
        target = message.reply_to_message.from_user
        target_id = target.id
        target_name = target.username or target.first_name or f'ID:{target_id}'
    else:
        target_id, target_name = resolve_user_from_string(message.chat.id, target_raw)
    if not target_id:
        bot.reply_to(message, "❌ Не удалось найти пользователя. Укажи @username, ID или используй ответ на сообщение.")
        return
    econ = get_user_econ(target_id, target_name)
    owned = econ.setdefault('profile_gifs', [])
    if gif_id not in owned:
        owned.append(gif_id)
    econ['profile_gif'] = gif_id
    mark_dirty()
    gif = PROFILE_GIFS[gif_id]
    bot.reply_to(message, f"✅ Выдан GIF <b>{html.escape(gif['name'])}</b> пользователю <b>{html.escape(str(target_name))}</b>.\n🎞 GIF сразу установлен в профиль.", parse_mode='HTML')

def admin_give_stars_all_command(message):
    """Owner-only: выдаёт пользователю все постоянные товары Stars-магазина."""
    if not _is_owner_admin(message):
        return
    raw = (message.text or '').strip()
    parts = raw.split()
    target_id = None
    target_name = None
    if message.reply_to_message and (len(parts) < 2 or parts[1].lower() in ('reply', '.', '-', '@reply', 'this')):
        target = message.reply_to_message.from_user
        target_id = target.id
        target_name = target.username or target.first_name or f'ID:{target_id}'
    elif len(parts) >= 2:
        target_id, target_name = resolve_user_from_string(message.chat.id, parts[1])
    if not target_id:
        bot.reply_to(message, '❌ Формат: <code>/give_stars_all @username</code> или ответом на сообщение.', parse_mode='HTML')
        return
    econ = get_user_econ(user_id=target_id, user_tag=target_name)
    _grant_all_donations(econ)
    mark_dirty()
    bot.reply_to(
        message,
        f'✅ <b>ВСЕ STARS-ТОВАРЫ ВЫДАНЫ</b>\n👤 {html.escape(str(target_name or target_id))}\n⭐️ Выданы VIP навсегда, все косметические товары, GIF, донатные машины и донатные бизнесы.',
        parse_mode='HTML'
    )

def admin_give_command(message):
    _admin_grant(message)

def dragon_audio_file_id(message):
    try:
        if not message or not getattr(message, 'from_user', None):
            return
        if message.from_user.id != ADMIN_ID:
            return
        if getattr(message.chat, 'type', '') != 'private':
            return

        file_id = None
        file_name = ''
        if getattr(message, 'audio', None):
            file_id = message.audio.file_id
            file_name = getattr(message.audio, 'file_name', '') or 'audio'
        elif getattr(message, 'document', None):
            doc = message.document
            mime = (getattr(doc, 'mime_type', '') or '').lower()
            name = getattr(doc, 'file_name', '') or 'document'
            if not mime.startswith('audio/') and not name.lower().endswith(('.mp3', '.m4a', '.ogg', '.wav', '.aac', '.flac')):
                return
            file_id = doc.file_id
            file_name = name

        if not file_id:
            return

        bot.reply_to(
            message,
            f"🎵 <b>Аудио получено</b>\n"
            f"📄 {html.escape(str(file_name))}\n"
            f"🆔 <code>{html.escape(str(file_id))}</code>",
            parse_mode='HTML'
        )
    except Exception as e:
        print(f'[DRAGON AUDIO FILE_ID ERROR] {e}')

def register(ctx, only=None):
    """Register selected handlers from this feature module."""
    _inject(ctx)
    bot = ctx["bot"]
    wanted = set(only) if only is not None else set(HANDLER_NAMES)
    registered = []
    if "cmd_global_stats" in wanted:
        _handler = cmd_global_stats
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['stats', 'статистика'])(_handler)
        ctx["cmd_global_stats"] = _handler
        globals()["cmd_global_stats"] = _handler
        registered.append("cmd_global_stats")
    if "cmd_economy_stats" in wanted:
        _handler = cmd_economy_stats
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['economystats', 'экономика'])(_handler)
        ctx["cmd_economy_stats"] = _handler
        globals()["cmd_economy_stats"] = _handler
        registered.append("cmd_economy_stats")
    if "cmd_game_stats" in wanted:
        _handler = cmd_game_stats
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['gamestats', 'игрыстат'])(_handler)
        ctx["cmd_game_stats"] = _handler
        globals()["cmd_game_stats"] = _handler
        registered.append("cmd_game_stats")
    if "cmd_bot_status" in wanted:
        _handler = cmd_bot_status
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['status', 'статус'])(_handler)
        ctx["cmd_bot_status"] = _handler
        globals()["cmd_bot_status"] = _handler
        registered.append("cmd_bot_status")
    if "cmd_dashboard" in wanted:
        _handler = cmd_dashboard
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['dashboard', 'панель'])(_handler)
        ctx["cmd_dashboard"] = _handler
        globals()["cmd_dashboard"] = _handler
        registered.append("cmd_dashboard")
    if "admin_force_save_command" in wanted:
        _handler = admin_force_save_command
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['save_json', 'force_save', 'сохранить', 'сохранить_json'])(_handler)
        ctx["admin_force_save_command"] = _handler
        globals()["admin_force_save_command"] = _handler
        registered.append("admin_force_save_command")
    if "admin_give_gif_command" in wanted:
        _handler = admin_give_gif_command
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['give_gif', 'выдать_gif'])(_handler)
        ctx["admin_give_gif_command"] = _handler
        globals()["admin_give_gif_command"] = _handler
        registered.append("admin_give_gif_command")
    if "admin_give_stars_all_command" in wanted:
        _handler = admin_give_stars_all_command
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['give_stars_all', 'выдать_все_звезды', 'stars_all'])(_handler)
        ctx["admin_give_stars_all_command"] = _handler
        globals()["admin_give_stars_all_command"] = _handler
        registered.append("admin_give_stars_all_command")
    if "admin_give_command" in wanted:
        _handler = admin_give_command
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['give', 'выдать', 'grant'])(_handler)
        ctx["admin_give_command"] = _handler
        globals()["admin_give_command"] = _handler
        registered.append("admin_give_command")
    if "dragon_audio_file_id" in wanted:
        _handler = dragon_audio_file_id
        _handler = serialize_user_action(_handler)
        bot.message_handler(content_types=['audio', 'document'])(_handler)
        ctx["dragon_audio_file_id"] = _handler
        globals()["dragon_audio_file_id"] = _handler
        registered.append("dragon_audio_file_id")
    return registered
