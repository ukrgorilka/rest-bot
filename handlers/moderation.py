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


HANDLER_NAMES = ['handle_bot_chat_membership', 'welcome_new_members', 'cmd_groups', 'cmd_find_group', 'cmd_user_lookup', 'cmd_group_info', 'cmd_admins', 'cmd_admin_control', 'cmd_ban', 'cmd_mute', 'cmd_kick', 'cmd_warn', 'cmd_unban', 'cmd_unmute', 'cmd_bans', 'cmd_mutes', 'cmd_warns', 'handle_messages']


def handle_bot_chat_membership(update):
    try:
        chat = getattr(update, 'chat', None)
        if not chat or getattr(chat, 'type', '') not in ('group', 'supergroup'):
            return
        member = getattr(update, 'new_chat_member', None)
        status = getattr(member, 'status', '') if member else ''
        active = status in ('member', 'administrator')
        item = track_bot_chat(chat, status='active' if active else 'inactive', touch_activity=active)
        title = getattr(chat, 'title', None) or 'Без названия'; cid = getattr(chat, 'id', 0)
        if active and item and not item.get('join_notified_at'):
            item['join_notified_at'] = time.time(); mark_dirty()
            try: bot.send_message(ADMIN_ID, f"🟢 <b>Бот добавлен в группу!</b>\n📌 {html.escape(title)}\n🆔 <code>{cid}</code>\n📡 Тип: <b>{_chat_type_label(getattr(chat, 'type', 'group'))}</b>", parse_mode='HTML')
            except Exception as e: print(f'[GROUP JOIN NOTIFY ERROR] {e}')
        elif status in ('left', 'kicked'):
            try: bot.send_message(ADMIN_ID, f"🔴 <b>Бот покинул группу!</b>\n📌 {html.escape(title)}\n🆔 <code>{cid}</code>\n📡 Статус: <b>{'удалён/заблокирован' if status == 'kicked' else 'вышел'}</b>", parse_mode='HTML')
            except Exception as e: print(f'[GROUP LEAVE NOTIFY ERROR] {e}')
    except Exception as e:
        print(f'[MY CHAT MEMBER ERROR] {e}')

def welcome_new_members(message):
    if not can_process_user_message(message):
        return
    if not get_chat_settings(message.chat.id).get('welcome_enabled', True):
        return
    for member in message.new_chat_members:
        # Бот не приветствует самого себя и вообще не приветствует других ботов.
        if getattr(member, 'is_bot', False):
            continue
        user_name = (f"{member.first_name or ''} {member.last_name or ''}").strip() or member.username
        user_link = make_link(message.chat.id, user_name, member.id, ping=True)
        add_coins(member.id, user_name, 50, username=member.username)

        welcome_text = (
            f"🎉 <b>Добро пожаловать в наш чат, {user_link}!</b> 😺\n\n"
            f"🌸 Мы рады видеть тебя в нашей дружной семье! 😻\n"
            f"💵 Тебе начислен приветственный подарок: <b>50 Ня-коинов 🪙</b> 😽\n\n"
            f"💡 Введи <code>меню</code> или <code>/help</code>, чтобы открыть интерактивный путеводитель. 😸"
        )
        try:
            bot.send_message(message.chat.id, welcome_text, parse_mode='HTML')
        except Exception:
            pass

def cmd_groups(message):
    if not _owner_only(message): return
    items = _bot_chat_items(False); active = [x for x in items if x.get('status') == 'active']; inactive = [x for x in items if x.get('status') != 'active']
    if not items:
        bot.reply_to(message, '📋 <b>Группы</b>\n\nПока ни одной группы не обнаружено.', parse_mode='HTML'); return

    # /groups или /groups 2 — страницы по 10 групп, чтобы список не упирался в лимит Telegram.
    try:
        page = max(1, int((message.text or '').split(maxsplit=1)[1]))
    except (ValueError, IndexError, TypeError):
        page = 1
    per_page = 10
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = min(page, total_pages)
    page_items = items[(page - 1) * per_page: page * per_page]

    lines=[f'📋 <b>ГРУППЫ БОТА</b> · стр. <b>{page}/{total_pages}</b>',
           '━━━━━━━━━━━━━━━━━━━━',
           f'🟢 Активных: <b>{len(active)}</b>',
           f'🔴 Неактивных: <b>{len(inactive)}</b>',
           f'📊 Всего: <b>{len(items)}</b>','']
    start_index = (page - 1) * per_page
    for i,x in enumerate(page_items, start_index + 1):
        st='🟢' if x.get('status')=='active' else '🔴'
        title=html.escape(str(x.get('title') or 'Без названия'))
        uname=f" @{html.escape(str(x['username']))}" if x.get('username') else ''
        members = x.get('member_count')
        member_line = f"\n   👥 Участников: <b>{members}</b>" if members is not None else ''
        lines.append(f"{st} <b>{i}. {title}</b>{uname}\n   🆔 <code>{x.get('chat_id')}</code> · {_chat_type_label(x.get('type'))}{member_line}\n   🕐 Последнее обновление: {html.escape(_fmt_seen(x.get('last_seen')))}")
    lines.append('')
    if page < total_pages:
        lines.append(f'➡️ Следующая страница: <code>/groups {page + 1}</code>')
    if page > 1:
        lines.append(f'⬅️ Предыдущая страница: <code>/groups {page - 1}</code>')
    bot.send_message(message.chat.id,'\n'.join(lines),parse_mode='HTML')

def cmd_find_group(message):
    if not _owner_only(message): return
    parts = (message.text or '').split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, '🔎 <b>Поиск группы</b>\n\nИспользование: <code>/findgroup -1001234567890</code>', parse_mode='HTML'); return
    raw = parts[1].strip().split()[0]
    try: chat_id = int(raw)
    except ValueError:
        bot.reply_to(message, '❌ ID группы должен быть числом.', parse_mode='HTML'); return
    item = db.get('bot_chats', {}).get(str(chat_id))
    if not isinstance(item, dict):
        bot.reply_to(message, f'❌ Группа <code>{chat_id}</code> не найдена в реестре бота.', parse_mode='HTML'); return
    title=html.escape(str(item.get('title') or 'Без названия')); username=item.get('username')
    uname=f'🔗 @{html.escape(str(username))}' if username else '🔗 username отсутствует'
    members=item.get('member_count'); mem=f'👥 Участников: <b>{members}</b>' if members is not None else '👥 Участники: пока неизвестны'
    status='🟢 активна' if item.get('status')=='active' else '🔴 неактивна'
    bot.reply_to(message, f'🔎 <b>ГРУППА НАЙДЕНА</b>\n━━━━━━━━━━━━━━━━━━━━\n📌 <b>{title}</b>\n🆔 <code>{chat_id}</code>\n{uname}\n📡 Тип: <b>{_chat_type_label(item.get("type", "group"))}</b>\n{mem}\n🤖 Статус бота: <b>{status}</b>\n📅 Обнаружена: <b>{_fmt_seen(item.get("first_seen"))}</b>\n🕐 Последняя активность: <b>{_fmt_seen(item.get("last_activity", item.get("last_seen")))}</b>', parse_mode='HTML')

def cmd_user_lookup(message):
    if not _owner_only(message): return
    parts=(message.text or '').split(maxsplit=1)
    if len(parts)<2:
        bot.reply_to(message,'🔎 <b>Поиск пользователя</b>\n\n<code>/user 123456789</code> или <code>/user @username</code>',parse_mode='HTML'); return
    query=parts[1].strip().split()[0].lstrip('@').lower(); econ=None; found_id=None
    if query.isdigit(): found_id=int(query); econ=db.get('economy',{}).get(str(found_id))
    else:
        for uid,data in db.get('economy',{}).items():
            if isinstance(data,dict) and str(data.get('username','')).lower().lstrip('@')==query: found_id=uid; econ=data; break
    if not isinstance(econ,dict): bot.reply_to(message,f'❌ Пользователь <code>{html.escape(query)}</code> не найден.',parse_mode='HTML'); return
    name=html.escape(str(econ.get('name') or econ.get('user_name') or 'Без имени')); uname=econ.get('username'); uname=f'@{html.escape(str(uname))}' if uname else 'нет username'; stats=econ.get('stats',{}) if isinstance(econ.get('stats'),dict) else {}
    bot.reply_to(message,f'🔎 <b>ПОЛЬЗОВАТЕЛЬ НАЙДЕН</b>\n━━━━━━━━━━━━━━━━━━━━\n👤 <b>{name}</b> · {uname}\n🆔 <code>{found_id}</code>\n🪙 Баланс: <b>{int(econ.get("balance",0) or 0):,}</b>\n🏦 Банк: <b>{int(econ.get("bank_deposit",0) or 0):,}</b>\n🎮 Игр: <b>{int(stats.get("games",0) or 0):,}</b>\n🏆 Достижений: <b>{len(econ.get("achievements",[]) or [])}</b>\n⭐ Донатов Stars: <b>{int(econ.get("stars_donated",0) or 0):,}</b>',parse_mode='HTML')

def cmd_group_info(message):
    if not _owner_only(message): return
    chat=message.chat
    if getattr(chat,'type','') not in ('group','supergroup'):
        bot.reply_to(message,'❌ Эту команду нужно использовать внутри группы.'); return
    item=track_bot_chat(chat,'active',True) or {}; title=html.escape(str(getattr(chat,'title',None) or 'Без названия')); username=getattr(chat,'username',None) or item.get('username')
    try:
        members=bot.get_chat_member_count(chat.id)
        item['member_count']=members
        item['member_count_updated_at']=time.time()
        mark_dirty()
    except Exception:
        members=item.get('member_count')
    uname=f"🔗 @{html.escape(str(username))}" if username else '🔗 публичного username нет'; mem=f"👥 Участников: <b>{members}</b>" if members is not None else '👥 Участники: недоступно'
    settings=get_chat_settings(chat.id)
    flood='🟢 включён' if settings.get('flood_protection',False) else '🔴 выключен'
    welcome='🟢 включены' if settings.get('welcome_enabled',True) else '🔴 выключены'
    bot.reply_to(message,f"🔎 <b>ИНФОРМАЦИЯ О ГРУППЕ</b>\n━━━━━━━━━━━━━━━━━━━━\n📌 <b>{title}</b>\n🆔 <code>{chat.id}</code>\n{uname}\n{mem}\n📡 Тип: <b>{_chat_type_label(getattr(chat,'type','group'))}</b>\n🟢 Бот: <b>активен</b>\n🛡 Антифлуд: <b>{flood}</b>\n👋 Приветствия: <b>{welcome}</b>\n🕐 Последняя активность: <b>{_fmt_seen(item.get('last_activity'))}</b>",parse_mode='HTML')

def cmd_ban(message): _execute_moderation(message,'ban')

def cmd_mute(message): _execute_moderation(message,'mute')

def cmd_kick(message): _execute_moderation(message,'kick')

def cmd_warn(message): _execute_moderation(message,'warn')

def cmd_unban(message): _clear_moderation(message,'unban')

def cmd_unmute(message): _clear_moderation(message,'unmute')

def cmd_bans(message): _mod_list(message,'ban')

def cmd_mutes(message): _mod_list(message,'mute')

def cmd_warns(message): _mod_list(message,'warn')

def _admin_usage():
    return ('👮 <b>АДМИН-ПАНЕЛЬ ЧАТА</b>\n━━━━━━━━━━━━━━━━━━━━\n'
            '<code>!админы</code> — список админов\n'
            '<code>!взм админ @user 2</code> — назначить уровень\n'
            '<code>!взм снять @user</code> — снять роль\n'
            '<code>!взм варн 1</code> — минимальный уровень для варна\n'
            '<code>!взм мут 2</code> — минимальный уровень для мута\n'
            '<code>!взм кик 2</code> — минимальный уровень для кика\n'
            '<code>!взм бан 3</code> — минимальный уровень для бана\n'
            '<code>!взм настройки 2</code> — минимальный уровень для настроек\n'
            '<code>!взм взм 3</code> — минимальный уровень для управления ролями\n'
            '<code>!взм функции</code> — включить/выключить функции админов')

def cmd_admins(message):
    if getattr(message.chat, 'type', '') not in ('group','supergroup'):
        return
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, '❌ Список админов доступен только администраторам.')
        return
    cid = int(message.chat.id)
    rows=[]
    try:
        members = bot.get_chat_administrators(cid)
    except Exception:
        members=[]
    seen=set()
    for m in members:
        uid=int(m.user.id); seen.add(uid); level=get_admin_level(cid, uid)
        if level > 0:
            name=(f'{m.user.first_name or ""} {m.user.last_name or ""}').strip() or m.user.username or f'ID:{uid}'
            rows.append((level, uid, name, m.user.username))
    for uid_raw in db.setdefault('chat_admins', {}).get(str(cid), {}):
        try: uid=int(uid_raw)
        except: continue
        if uid in seen: continue
        level=get_admin_level(cid, uid)
        if level > 0:
            e=get_user_econ(uid); rows.append((level, uid, e.get('display_name') or e.get('name') or f'ID:{uid}', e.get('username')))
    rows.sort(key=lambda x:(-x[0], str(x[2]).lower()))
    lines=['👮 <b>АДМИНЫ ЧАТА</b>','━━━━━━━━━━━━━━━━━━━━']
    if not rows: lines.append('Администраторов пока нет.')
    for level,uid,name,uname in rows:
        tag=f'@{html.escape(str(uname))}' if uname else f'ID:{uid}'
        lines.append(f'{ADMIN_LEVEL_NAMES.get(level, "Админ")} <b>{level}</b> — {html.escape(str(name))} ({tag})')
    lines.append('━━━━━━━━━━━━━━━━━━━━')
    lines.append('0 — обычный участник; роли 1–4 показываются здесь.')
    bot.reply_to(message, '\n'.join(lines), parse_mode='HTML')

def cmd_admin_control(message):
    if getattr(message.chat, 'type', '') not in ('group','supergroup'):
        return
    text=(message.text or '').strip()
    body=re.sub(r'^!взм\s*', '', text, flags=re.I).strip()
    if not body:
        bot.reply_to(message, _admin_usage(), parse_mode='HTML'); return
    parts=body.split()
    action=parts[0].lower()
    cid=str(message.chat.id)
    if action in ('функции','функция','админфункции'):
        if get_admin_level(message.chat.id, message.from_user.id) != 4:
            bot.reply_to(message, '❌ Включать/выключать функции админов может только владелец чата.')
            return
    elif not can_admin_action(message.chat.id, message.from_user.id, 'admin_manage'):
        bot.reply_to(message, '❌ Недостаточно прав для управления ролями или функции админов отключены.')
        return
    if action in ('функции','функция','админфункции'):
        sett=get_chat_settings(message.chat.id); sett['admin_functions_enabled']=not sett.get('admin_functions_enabled',True); mark_dirty()
        state='включены' if sett['admin_functions_enabled'] else 'выключены'
        bot.reply_to(message, f'👮 Функции админов {state}.', parse_mode='HTML'); return
    if action in ('взм','admin_manage'):
        if len(parts)!=2 or not parts[1].isdigit() or not 1<=int(parts[1])<=4:
            bot.reply_to(message, '❌ Уровень должен быть от 1 до 4.'); return
        db.setdefault('admin_permissions',{}).setdefault(cid,{})['admin_manage']=int(parts[1]); mark_dirty()
        bot.reply_to(message, f'✅ Управление ролями теперь доступно с уровня {parts[1]}.'); return
    if action in ('варн','warn','мут','mute','бан','ban','кик','kick','настройки','settings'):
        key={'варн':'warn','warn':'warn','мут':'mute','mute':'mute','бан':'ban','ban':'ban','кик':'kick','kick':'kick','настройки':'settings','settings':'settings'}[action]
        if len(parts)!=2 or not parts[1].isdigit() or not 1<=int(parts[1])<=4:
            bot.reply_to(message, '❌ Уровень должен быть от 1 до 4.\n\n'+_admin_usage(), parse_mode='HTML'); return
        db.setdefault('admin_permissions',{}).setdefault(cid,{})[key]=int(parts[1]); mark_dirty()
        bot.reply_to(message, f'✅ Для «{key}» теперь нужен уровень {parts[1]}.', parse_mode='HTML'); return
    if action in ('админ','admin','снять','remove'):
        if len(parts)<2:
            bot.reply_to(message, _admin_usage(), parse_mode='HTML'); return
        target_id,target_name,_=_mod_target(message, '' if action in ('снять','remove') and getattr(message,'reply_to_message',None) else parts[1])
        if not target_id:
            bot.reply_to(message, '❌ Не удалось определить пользователя. Ответь на сообщение или укажи @username/ID.'); return
        if int(target_id)==int(message.from_user.id):
            bot.reply_to(message, '❌ Нельзя изменить собственную роль.'); return
        roles=db.setdefault('chat_admins',{}).setdefault(cid,{})
        if action in ('снять','remove'):
            roles.pop(str(target_id),None); mark_dirty(); bot.reply_to(message, f'✅ Роль снята с {html.escape(str(target_name))}.', parse_mode='HTML'); return
        if len(parts)<3 or not parts[2].isdigit() or not 1<=int(parts[2])<=3:
            bot.reply_to(message, '❌ Для назначения укажи уровень 1–3.\nПример: <code>!взм админ @user 2</code>', parse_mode='HTML'); return
        level=int(parts[2]); actor_level=get_admin_level(message.chat.id,message.from_user.id)
        if level >= actor_level:
            bot.reply_to(message, '❌ Нельзя назначить уровень, равный или выше собственного.')
            return
        roles[str(target_id)]=level; mark_dirty()
        bot.reply_to(message, f'✅ {html.escape(str(target_name))} назначен: <b>{ADMIN_LEVEL_NAMES[level]}</b> ({level}).', parse_mode='HTML'); return
    bot.reply_to(message, _admin_usage(), parse_mode='HTML')

def handle_messages(message):
    if not message or not getattr(message, 'from_user', None):
        return

    try:
        track_bot_chat(message.chat, status='active', touch_activity=True)
    except Exception as e:
        print(f'[GROUP TRACK ERROR] {e}')

    chat_id = message.chat.id
    if is_chat_banned(chat_id):
        return

    text = message.text.strip() if message.text else ''
    str_chat = str(chat_id)

    # Все зарегистрированные slash-команды обрабатываются отдельными handlers выше.
    # Если Telegram прислал неизвестную slash-команду, не запускаем её как обычный текст.
    if text.startswith('/'):
        command_token = text.split()[0].split('@')[0].lower()
        catchall_slash_commands = {
            '/add_promo', '/admin', '/admin_help', '/calc', '/dice', '/fish', '/force_divorce',
            '/give_item', '/hunt', '/inspect', '/pay', '/resume', '/set_karma', '/shutdown',
            '/slots', '/start_bot', '/stop_bot', '/wipe'
        }
        if command_token not in catchall_slash_commands:
            return
    user_id = message.from_user.id
    user_username = (message.from_user.username or '').lower()
    try:
        record_started_user(user_id, user_username, getattr(message.from_user, 'first_name', None))
    except Exception:
        pass
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username or 'Пользователь'
    text_lower = text.lower()
    now_ts = time.time()
    with QUIZ_LOCK:
        quiz = copy.deepcopy(current_quiz.get(chat_id))

    is_super_admin = (user_id == ADMIN_ID)

    # Полностью останавливаем обработку пользовательских сообщений. Владелец
    # остаётся единственным, кто может включить бота обратно.
    if not db.get('bot_active', True) and not is_super_admin:
        return

    # bot_active больше не блокирует обычных пользователей.
    # Старое значение False в Neon не должно переводить бота в режим "только владелец".
    if not db.get('bot_active', True) and is_super_admin and text_lower in ['/start_bot', '/resume', 'включить бота', 'запустить бота']:
        db['bot_active'] = True
        save_data()
        log_event('ВКЛЮЧЕНИЕ', f'Бот возобновил работу по команде ID:{user_id}')
        bot.reply_to(message, "🟢 <b>Бот успешно включен и возобновил работу!</b> 😻", parse_mode='HTML')
        return

    last_chat_activity[chat_id] = now_ts

    # Регистрируем пользователя в чатовых данных до текстовой маршрутизации.
    try:
        econ_for_chat = get_user_econ(user_id, user_name, username=user_username)
        chat_ids = econ_for_chat.setdefault('chat_ids', [])
        if chat_id not in chat_ids:
            chat_ids.append(chat_id)
            mark_dirty()
    except Exception as e:
        print(f'[GENERAL CHAT REGISTER ERROR] {e}')

    if text.startswith('/'):
        cmd_part = text.split()[0]
        if '@' in cmd_part:
            target_bot = cmd_part.split('@')[1].lower()
            my_bot_username = get_cached_bot_username()
            if my_bot_username and target_bot != my_bot_username:
                return
            # Очищаем суффикс @имя_бота из текста команды
            text = text.replace(f"@{cmd_part.split('@')[1]}", "", 1).strip()
            text_lower = text.lower()

    econ = get_user_econ(user_id, user_name, username=user_username)
    if text_lower.startswith('/') or any(kw in text_lower for kw in ['рест', 'профиль', 'баланс', 'топ', 'шанс']):
        if (now_ts - econ.get('last_cmd_time', 0)) < 2.0 and econ.get('last_cmd_text') == text_lower:
            return 
        econ['last_cmd_time'] = now_ts
        econ['last_cmd_text'] = text_lower

    if user_id in user_flood_muted:
        if now_ts < user_flood_muted[user_id]: return
        else: del user_flood_muted[user_id]

    chat_settings = get_chat_settings(chat_id)

    # Ставим тот же часовой лимит перед текстовыми экономическими роутерами,
    # которые Telegram не передаёт в отдельный command-handler (например,
    # «кости 100», «перевод @user 100», «ограбить @user», «семейный сейф положить 100»).
    raw_rate_limited_prefixes = (
        'бонус', 'коин', 'взять бонус', 'кости', 'кубик', 'слоты', 'казино',
        'рыбалка', 'рыба', 'охота', 'продать ', 'ограбить', 'перевод ',
        'передать ', 'отправить ', 'скинуть ', 'банк положить', 'банк снять',
        'депозит ', 'семейный сейф ', 'передать', '/pay ', '/dice', '/slots', '/fish', '/hunt'
    )
    raw_needs_rate_limit = any(text_lower == p.rstrip() or text_lower.startswith(p) for p in raw_rate_limited_prefixes)
    if raw_needs_rate_limit and not is_super_admin:
        # Перенаправляем в общий антифлуд только для обычных пользователей;
        # can_process_user_message не выполняется повторно для самого handle_messages.
        flood_key = f"{chat_id}:{user_id}"
        is_owner = is_chat_owner(chat_id, user_id)
        is_admin_user = is_admin(chat_id, user_id)
        admins_allowed = chat_settings.get('flood_admins', False)
        flood_applies = (not is_owner) and (not is_admin_user or admins_allowed)
        if flood_applies and chat_settings.get('flood_protection', False):
            now_flood = time.time()
            hist = [t for t in command_rate_history.get(flood_key, []) if now_flood - t < 3600]
            if len(hist) >= 5:
                remaining = max(1, int(3600 - (now_flood - hist[0])))
                mins = max(1, (remaining + 59) // 60)
                command_rate_history[flood_key] = hist
                bot.send_message(chat_id, f"🛡 <b>Антифлуд</b>: лимит 5 игровых/экономических команд в час исчерпан. Осталось примерно {mins} мин.", parse_mode='HTML')
                return
            hist.append(now_flood)
            command_rate_history[flood_key] = hist

    # Старый короткий антиспам оставляем только для одинаковых экономических команд.

    add_message_stat(user_id, user_name, username=user_username, chat_id=chat_id)
    activity_reward_allowed = (now_ts - float(econ.get('last_activity_reward_time', 0) or 0)) >= 5.0
    if activity_reward_allowed:
        econ['last_activity_reward_time'] = now_ts
        add_account_exp(user_id, user_name, 2, username=user_username)
        add_bp_exp(user_id, user_name, 2, username=user_username)
        mark_dirty()
    # МЕМНЫЕ БОЛЕЗНИ (СЛУЧАЙНОЕ ЗАРАЖЕНИЕ 2%)
    if random.random() < 0.02:
        d_got = try_infect_user(user_id, user_name, chance=1.0)
        if d_got:
            try: bot.send_message(chat_id, f"🤒 Ой-ой! {make_link(chat_id, user_name, user_id, ping=False)} подхватил(а) хворь: <b>{d_got}</b>! Загляните в <code>/pharmacy</code>! 🙀", parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")


    # ПОВТОРЯЛКА
    m_say = re.match(r'^(?:бот,?\s+)?скажи\s+(.+)$', text, re.IGNORECASE)
    if m_say:
        phrase = m_say.group(1).strip()
        bot.send_message(chat_id, phrase)
        return

    # РЕАКЦИИ
    if get_chat_settings(chat_id).get('auto_reactions', True) and random.random() < 0.04 and len(text) > 2:
        try:
            rx_list = ['🔥', '🗿', '❤️', '👍', '⚡️', '🎉', '👀', '👏']
            chosen_rx = random.choice(rx_list)
            bot.set_message_reaction(chat_id, message.message_id, [ReactionTypeEmoji(chosen_rx)])
        except Exception as e: print(f"[NONFATAL ERROR] {e}")

    # СИМУЛЯТОР ДЬЯКА: только ответом на сообщение.
    if text_lower == 'жмяк':
        if not message.reply_to_message or not getattr(message.reply_to_message,'from_user',None):
            bot.reply_to(message,'💡 Напишите <code>жмяк</code> ответом на сообщение человека.')
            return
        target=message.reply_to_message.from_user
        target_name=(f'{target.first_name or ""} {target.last_name or ""}').strip() or target.username or 'Пользователь'
        if int(target.id)==int(user_id):
            bot.reply_to(message,'❌ Себя жмякать нельзя 😹'); return
        sender_link=make_link(chat_id,user_name,user_id,ping=False)
        target_link=make_link(chat_id,target_name,target.id,ping=False)
        bot.send_message(chat_id,f'😼 {sender_link} пожмял вишеньки🍒 {target_link}',parse_mode='HTML')
        return

    # СИМУЛЯТОР МОГЕРА
    if re.fullmatch(r'(?:мог|могнуть)', text_lower):
        econ['mog_count'] = int(econ.get('mog_count', 0) or 0) + 1
        mark_dirty()
        bot.reply_to(message, f"😎 {make_link(chat_id, user_name, user_id, ping=False)} могнул!\n📊 Всего могнул: <b>{econ['mog_count']}</b> раз(а)", parse_mode='HTML')
        return

    # КАЛЬКУЛЯТОР
    m_calc_cmd = re.match(r'^(?:/calc|посчитай|вычисли|реши|сколько\s+будет)\s+([\d\s\+\-\*\/\%\(\)\.\:×÷]+)$', text, re.IGNORECASE)
    if m_calc_cmd:
        calc_res = safe_calculate_math(m_calc_cmd.group(1).strip())
        if calc_res is not None:
            bot.reply_to(message, f"🧮 <b>Результат:</b> <code>{calc_res}</code> 😸", parse_mode='HTML')
            return

    # ВИКТОРИНА
    if quiz and quiz.get('answer') and quiz.get('chat_id') == chat_id and text_lower == quiz['answer']:
        # quiz is a global per-chat prize. The old code modified only a deepcopy,
        # so several users could answer the same question and all receive the prize.
        with QUIZ_LOCK:
            live_quiz = current_quiz.get(chat_id)
            if not live_quiz or not live_quiz.get('answer') or live_quiz.get('chat_id') != chat_id or text_lower != live_quiz.get('answer'):
                return
            reward = max(0, int(live_quiz.get('reward', 0) or 0))
            current_quiz.pop(chat_id, None)
            if reward <= 0:
                return
            add_coins(user_id, user_name, reward, username=user_username)
            add_account_exp(user_id, user_name, 20, username=user_username)
            mark_dirty()
        u_link = make_link(chat_id, user_name, user_id, ping=True)
        bot.reply_to(message, f"🎉 <b>ПРАВИЛЬНЫЙ ОТВЕТ!</b> 😻\n\nПервым(ой) правильно ответил(а) {u_link} и получает <b>+{reward} Ня-коинов 🪙</b> (+20 EXP)!", parse_mode='HTML')
        return

    # КОМАНДЫ СОЗДАТЕЛЯ
    if is_super_admin:
        if text_lower in ['/admin', '/admin_help', 'админ', 'админка']:
            admin_help_text = (
                f"👑 <b>ПАНЕЛЬ УПРАВЛЕНИЯ СОЗДАТЕЛЯ (ID: {ADMIN_ID}):</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "• <code>/add_promo КОД СУММА</code> — создать промокод\n"
                "• <code>/stop_bot</code> — спящий режим\n"
                "• <code>/start_bot</code> — возобновить работу\n"
                "• <code>/take_coins @user 500</code> — списать коины\n"
                "• <code>/give_coins @user 1000</code> — выдать коины\n"
                "• <code>/inspect @user</code> — осмотр игрока\n"
                "• <code>/set_karma @user 100</code> — изменить карму\n"
                "• <code>/force_divorce @user</code> — принудительный развод\n"
                "• <code>/give_item @user item_name</code> — выдать предмет\n"
                "• <code>/give_gif @user gulya</code> — выдать GIF профиля\n"
                "• <code>/give @user gif gulya</code> — выдать GIF через /give\n"
                "• <code>/wipe @user</code> — обнулить профиль\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )
            bot.reply_to(message, admin_help_text, parse_mode='HTML')
            return

        if text_lower.startswith('/add_promo'):
            parts = text.split()
            if len(parts) >= 3:
                p_code = parts[1].strip().upper()
                try: p_reward = int(parts[2])
                except ValueError:
                    bot.reply_to(message, "❌ Неверная сумма награды!")
                    return
                promos = db.setdefault('promos', {})
                promos[p_code] = {'reward': p_reward, 'exp': 100, 'claimed': []}
                promos[p_code.lower()] = promos[p_code]
                mark_dirty()
                bot.reply_to(message, f"✅ Промокод <b>{p_code}</b> на <b>{p_reward} 🪙</b> создан! 😻", parse_mode='HTML')
                return
            else:
                bot.reply_to(message, "❌ Формат: <code>/add_promo КОД СУММА</code>", parse_mode='HTML')
                return

        if text_lower in ['/stop_bot', '/shutdown', 'выключить бота', 'остановить бота']:
            db['bot_active'] = False
            save_data(send_backup=True)
            log_event('ОСТАНОВКА', f'Бот переведён в спящий режим администратором ID:{user_id}')
            bot.reply_to(message, "🛑 <b>Бот переведён в спящий режим.</b>", parse_mode='HTML')
            return

        if text_lower.startswith('/inspect'):
            t_name, t_id, _ = parse_target_and_args(message, '/inspect')
            if not t_id:
                bot.reply_to(message, "❌ Укажите юзера.")
                return
            te = get_user_econ(t_id, t_name)
            bot.reply_to(message, f"👁 <b>GOD INSPECT:</b> {t_name} ({t_id})\nБаланс: {te['balance']}\nБанк: {te.get('bank_deposit', 0)}\nКарма: {te.get('karma', 0)}\nСтрик: {te.get('bonus_streak', 0)}\nEXP: {te.get('account_exp', 0)}\nПредметы: {te.get('inventory')}", parse_mode='HTML')
            return

        if text_lower.startswith('/set_karma'):
            t_name, t_id, args = parse_target_and_args(message, '/set_karma')
            if not t_id or not args:
                bot.reply_to(message, "❌ Формат: /set_karma @user 100")
                return
            try: k_val = int(args)
            except ValueError: return
            te = get_user_econ(t_id, t_name)
            te['karma'] = k_val
            mark_dirty()
            bot.reply_to(message, f"✅ Карма {t_name} установлена на {k_val}.")
            return

        if text_lower.startswith('/force_divorce'):
            t_name, t_id, _ = parse_target_and_args(message, '/force_divorce')
            if not t_id: return
            te = get_user_econ(t_id, t_name)
            if te.get('marriage'):
                p_id = te['marriage']['partner_id']
                if p_id != 0:
                    pe = get_user_econ(p_id)
                    pe['marriage'] = None
                te['marriage'] = None
                mark_dirty()
                bot.reply_to(message, f"✅ Игрок {t_name} принудительно разведен.")
            else:
                bot.reply_to(message, "❌ Игрок не в браке.")
            return

        if text_lower.startswith('/wipe'):
            t_name, t_id, _ = parse_target_and_args(message, '/wipe')
            if not t_id: return
            db['economy'][get_global_user_key(t_id)] = {'display_name': t_name, 'user_id': t_id, 'balance': 0, 'karma': 0}
            mark_dirty()
            bot.reply_to(message, f"💀 Аккаунт {t_name} полностью ВАЙПНУТ.")
            return
            
        if text_lower.startswith('/give_item'):
            t_name, t_id, item = parse_target_and_args(message, '/give_item')
            if not t_id or not item: return
            te = get_user_econ(t_id, t_name)
            te.setdefault('inventory', []).append(item)
            mark_dirty()
            bot.reply_to(message, f"✅ Предмет {item} выдан {t_name}.")
            return

        m_take = re.match(r'^(?:/take_coins|/take|забрать\s+коины|списать\s+коины)\s*(.*)', text, re.IGNORECASE)
        if m_take:
            rem = m_take.group(1).strip()
            t_uid, t_uname, t_amt = None, None, 0
            if message.reply_to_message:
                ru = message.reply_to_message.from_user
                t_uid = ru.id
                t_uname = (f"{ru.first_name or ''} {ru.last_name or ''}").strip() or ru.username
                m_a = re.search(r'\b\d+\b', rem)
                t_amt = int(m_a.group(0)) if m_a else 0
            else:
                m_split = re.search(r'^(.*?)\s+(\d+)$', rem)
                if m_split:
                    target_raw = m_split.group(1).strip()
                    t_amt = int(m_split.group(2))
                    t_uid, t_uname = resolve_user_from_string(chat_id, target_raw)
                    if not t_uname: t_uname = target_raw
            if not t_uname or t_amt <= 0:
                bot.reply_to(message, "❌ Формат: <code>/take_coins @username 500</code>", parse_mode='HTML')
                return
            t_econ = get_user_econ(t_uid, t_uname)
            _set_balance(t_econ, max(0, t_econ.get('balance', 0) - t_amt))
            mark_dirty()
            u_link = make_link(chat_id, t_uname, t_uid, ping=True)
            bot.reply_to(message, f"💸 <b>Списано -{t_amt} 🪙</b> у {u_link}!\nБаланс: <b>{t_econ['balance']} 🪙</b>", parse_mode='HTML')
            return

        m_give = re.match(r'^(?:/give_coins|/give|выдать\s+коины|начислить\s+коины)\s*(.*)', text, re.IGNORECASE)
        if m_give:
            rem = m_give.group(1).strip()
            t_uid, t_uname, t_amt = None, None, 0
            if message.reply_to_message:
                ru = message.reply_to_message.from_user
                t_uid = ru.id
                t_uname = (f"{ru.first_name or ''} {ru.last_name or ''}").strip() or ru.username
                m_a = re.search(r'\b\d+\b', rem)
                t_amt = int(m_a.group(0)) if m_a else 0
            else:
                m_split = re.search(r'^(.*?)\s+(\d+)$', rem)
                if m_split:
                    target_raw = m_split.group(1).strip()
                    t_amt = int(m_split.group(2))
                    t_uid, t_uname = resolve_user_from_string(chat_id, target_raw)
                    if not t_uname: t_uname = target_raw
            if not t_uname or t_amt <= 0:
                bot.reply_to(message, "❌ Формат: <code>/give_coins @username 1000</code>", parse_mode='HTML')
                return
            t_econ = get_user_econ(t_uid, t_uname)
            _set_balance(t_econ, t_econ.get('balance', 0) + t_amt)
            mark_dirty()
            u_link = make_link(chat_id, t_uname, t_uid, ping=True)
            bot.reply_to(message, f"🎁 <b>Начислено +{t_amt} 🪙</b> для {u_link}!\nБаланс: <b>{t_econ['balance']} 🪙</b>", parse_mode='HTML')
            return

    # ТОРГОВЛЯ НА БИРЖЕ ТЕКСТОМ
    m_crypto = re.match(r'^(купить|продать)\s+(?:крипту|акции|монеты)?\s*([a-zA-Z]{2,6})\s+([\d\.]+)$', text_lower)
    if m_crypto:
        action_type = 'buy' if m_crypto.group(1) == 'купить' else 'sell'
        ticker_val = m_crypto.group(2).upper()
        amount_val = m_crypto.group(3)
        trade_crypto(chat_id, user_id, user_name, action_type, ticker_val, amount_val, reply_msg=message, username=user_username)
        return

    # СЕМЕЙНЫЙ СЕЙФ
    if text_lower.startswith('семейный сейф'):
        econ = get_user_econ(user_id, user_name, username=user_username)
        if not econ.get('marriage'):
            bot.reply_to(message, "❌ Вы не состоите в браке! 😿")
            return
        m_amt = re.search(r'(\d+)', text_lower)
        if 'положить' in text_lower and m_amt:
            amt = int(m_amt.group(1))
            if amt <= 0:
                bot.reply_to(message, "❌ Сумма должна быть положительной. 😿")
                return
            with CALLBACK_STATE_LOCK:
                m = econ.get('marriage')
                if not m:
                    bot.reply_to(message, "❌ Брак уже расторгнут! 😿")
                    return
                update_family_house_income(m)
                p_id = m.get('partner_id'); p_tag = m.get('partner_name')
                p_econ = get_user_econ(p_id, p_tag) if p_id is not None else {}
                with TRANSFER_LOCK:
                    if int(econ.get('balance', 0) or 0) < amt:
                        bot.reply_to(message, f"❌ Недостаточно средств на руках! У вас: {econ.get('balance', 0)} 🪙 😿")
                        return
                    _adjust_balance(econ, -(amt))
                    m['vault'] = max(0, int(m.get('vault', 0) or 0)) + amt
                    if isinstance(p_econ.get('marriage'), dict): p_econ['marriage']['vault'] = m['vault']
                    mark_dirty()
            bot.reply_to(message, f"💍 Вы положили <b>{amt} 🪙</b> в семейный сейф!\nВ сейфе: <b>{m['vault']} 🪙</b> 😻", parse_mode='HTML')
            return
        elif 'снять' in text_lower and m_amt:
            amt = int(m_amt.group(1))
            if amt <= 0:
                bot.reply_to(message, "❌ Сумма должна быть положительной. 😿")
                return
            with CALLBACK_STATE_LOCK:
                m = econ.get('marriage')
                if not m:
                    bot.reply_to(message, "❌ Брак уже расторгнут! 😿")
                    return
                update_family_house_income(m)
                p_id = m.get('partner_id'); p_tag = m.get('partner_name')
                p_econ = get_user_econ(p_id, p_tag) if p_id is not None else {}
                cur_vault = max(0, int(m.get('vault', 0) or 0))
                if cur_vault < amt:
                    bot.reply_to(message, f"❌ В сейфе недостаточно коинов! Накоплено: {cur_vault} 🪙 😿")
                    return
                with TRANSFER_LOCK:
                    m['vault'] = cur_vault - amt
                    if isinstance(p_econ.get('marriage'), dict): p_econ['marriage']['vault'] = m['vault']
                    _set_balance(econ, max(0, int(econ.get('balance', 0) or 0)) + amt)
                    mark_dirty()
            bot.reply_to(message, f"💸 Вы взяли <b>{amt} 🪙</b> из семейного сейфа!\nОстаток: <b>{m['vault']} 🪙</b> 😸", parse_mode='HTML')
            return

    # КВЕСТ СООБЩЕНИЙ
    completed_tasks = track_daily_task(user_id, user_name, 'messages', 1, chat_id, username=user_username) if activity_reward_allowed else []
    if completed_tasks:
        for task_name, reward in completed_tasks:
            try: bot.send_message(chat_id, f'🎉 {make_link(chat_id, user_name, user_id, ping=True)} выполнил(а) задание: <b>{task_name}</b>! +{reward} 🪙 😻', parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

    # ОГРАБЛЕНИЕ
    if text_lower.startswith('ограбить'):
        target_user = None
        target_user_id = None
        if message.reply_to_message:
            u = message.reply_to_message.from_user
            target_user = (f"{u.first_name or ''} {u.last_name or ''}").strip() or u.username
            target_user_id = u.id
        else:
            raw_arg = text[8:].strip()
            if raw_arg: target_user_id, target_user = resolve_user_from_string(chat_id, raw_arg)
        if not target_user or target_user_id == user_id:
            bot.reply_to(message, "❌ Укажите жертву: <code>ограбить @username</code> или ответом на сообщение! 😾", parse_mode='HTML')
            return

        econ = get_user_econ(user_id, user_name, username=user_username)
        if econ['balance'] < 30:
            bot.reply_to(message, "❌ Чтобы пойти на дело, нужно иметь в кармане хотя бы <b>30 🪙</b> (на случай штрафа)! 😿", parse_mode='HTML')
            return

        now = time.time()
        cooldown = 3600
        left = cooldown_text(econ.get('last_rob_time', 0), cooldown, econ)
        if left:
            bot.reply_to(message, f"⏳ Полиция на хвосте! Ограбление доступно через: <b>{left}</b>. 🙀", parse_mode='HTML')
            return

        t_econ = get_user_econ(target_user_id, target_user)
        if t_econ.get('vip_forever') or (t_econ.get('vip_until', 0) > now):
            u_link = make_link(chat_id, user_name, user_id, ping=True)
            t_link = make_link(chat_id, target_user, target_user_id, ping=True)
            bot.send_message(chat_id, f"🛡 У {t_link} действует <b>VIP NYA PASS</b>! Иммунитет к ограблениям защитил карманы от кражи {u_link}. 😸", parse_mode='HTML')
            return
        t_pocket = t_econ.get('balance', 0)
        if t_pocket < 50:
            bot.reply_to(message, "❌ У жертвы меньше 50 коинов на руках! Деньги в банке защищены на 100%. 😿", parse_mode='HTML')
            return

        econ['last_rob_time'] = now
        check_achievements(user_id, user_name, 'robs', 1, chat_id, username=user_username)

        t_bp = t_econ.setdefault('backpack', {})
        if t_bp.get('alarm_system', 0) > 0:
            with serialized_multi_user_action(user_id, target_user_id):
                econ = get_user_econ(user_id, user_name, username=user_username)
                t_econ = get_user_econ(target_user_id, target_user)
                t_bp = t_econ.setdefault('backpack', {})
                t_bp['alarm_system'] = max(0, int(t_bp.get('alarm_system', 0)) - 1)
                fine = min(max(0, int(econ.get('balance', 0) or 0)), 150)
                _adjust_balance(econ, -fine)
                _adjust_balance(t_econ, fine)
                mark_dirty()
            change_karma(user_id, user_name, -5)
            with CALLBACK_STATE_LOCK:
                active_wanted[(chat_id, user_id)] = {'name': user_name, 'expire': now + 900, 'reason': 'ограбление'}
            u_link = make_link(chat_id, user_name, user_id)
            t_link = make_link(chat_id, target_user, target_user_id, ping=True)
            bot.send_message(chat_id, f"🚨🔊 <b>СИГНАЛИЗАЦИЯ СРАБОТАЛА!</b> 🙀\n\n{u_link} попытался проникнуть в карман {t_link}, но сработала <b>Охранная сигнализация</b>!\nВор оглушен электрошокером и выплатил компенсацию <b>-{fine} 🪙</b> в пользу жертвы! (Карма -5)", parse_mode='HTML')
            return

        rob_chance = 0.40
        if econ.get('pet') and econ['pet'].get('id') == 'raccoon': rob_chance += 0.20

        if random.random() <= rob_chance:
            with serialized_multi_user_action(user_id, target_user_id):
                econ = get_user_econ(user_id, user_name, username=user_username)
                t_econ = get_user_econ(target_user_id, target_user)
                t_pocket = max(0, int(t_econ.get('balance', 0) or 0))
                if t_pocket < 1:
                    bot.reply_to(message, "❌ У жертвы уже нет денег на руках! 😿")
                    return
                stolen = min(t_pocket, max(1, min(500, int(t_pocket * random.uniform(0.08, 0.18)))))
                _adjust_balance(t_econ, -stolen)
                _adjust_balance(econ, stolen)
                mark_dirty()
            change_karma(user_id, user_name, -5)
            u_link = make_link(chat_id, user_name, user_id, ping=True)
            t_link = make_link(chat_id, target_user, target_user_id, ping=True)
            bot.send_message(chat_id, f"🥷 <b>УДАЧНОЕ ОГРАБЛЕНИЕ!</b> 😼\n\n{u_link} ловко украл у {t_link} <b>{stolen} Ня-коинов 🪙</b>! (Карма -5)", parse_mode='HTML')
        else:
            with serialized_multi_user_action(user_id, target_user_id):
                econ = get_user_econ(user_id, user_name, username=user_username)
                t_econ = get_user_econ(target_user_id, target_user)
                fine = min(max(0, int(econ.get('balance', 0) or 0)), random.randint(30, 90))
                if econ.get('active_title') == 'shadow_ninja': fine = int(fine * 0.5)
                _adjust_balance(econ, -fine)
                _adjust_balance(t_econ, fine)
                mark_dirty()
            change_karma(user_id, user_name, -3)
            u_link = make_link(chat_id, user_name, user_id, ping=True)
            t_link = make_link(chat_id, target_user, target_user_id, ping=True)
            bot.send_message(chat_id, f"🚨 <b>ПРОВАЛ ОГРАБЛЕНИЯ!</b> 😿\n\n{u_link} попался с поличным и выплатил {t_link} компенсацию: <b>-{fine} 🪙</b>! (Карма -3)", parse_mode='HTML')
        return

    # БАНК ТЕКСТОМ (С СОХРАНЕНИЕМ НАКОПЛЕННЫХ ПРОЦЕНТОВ)
    if text_lower.startswith(('банк положить', 'депозит')):
        econ = get_user_econ(user_id, user_name, username=user_username)
        update_bank_interest(econ)
        m_amt = re.search(r'(\d+)', text)
        if m_amt:
            amt = int(m_amt.group(1))
            if amt <= 0 or econ['balance'] < amt:
                bot.reply_to(message, f"❌ Недостаточно средств на руках! У вас: {econ['balance']} 🪙 😿")
                return
            _adjust_balance(econ, -(amt))
            econ['bank_deposit'] = econ.get('bank_deposit', 0) + amt
            check_achievements(user_id, user_name, 'bank_deposit', amt, chat_id, username=user_username)
            mark_dirty()
            bot.reply_to(message, f"🏦 Вы внесли <b>{amt} 🪙</b> на депозит в Ня-Банк! 😻\nНа депозите: <b>{econ['bank_deposit']} 🪙</b>", parse_mode='HTML')
        return
    elif text_lower.startswith('банк снять всё'):
        econ = get_user_econ(user_id, user_name, username=user_username)
        update_bank_interest(econ)
        dep = econ.get('bank_deposit', 0)
        if dep <= 0:
            bot.reply_to(message, "❌ Ваш банковский депозит пуст! 😿")
            return
        _adjust_balance(econ, dep)
        econ['bank_deposit'] = 0
        econ['last_bank_calc'] = time.time()
        mark_dirty()
        bot.reply_to(message, f"💸 Вы забрали весь вклад из банка: <b>+{dep} 🪙</b>! 😸\nБаланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
        return
    elif text_lower.startswith('банк снять'):
        econ = get_user_econ(user_id, user_name, username=user_username)
        update_bank_interest(econ)
        m_amt = re.search(r'(\d+)', text)
        if m_amt:
            amt = int(m_amt.group(1))
            dep = econ.get('bank_deposit', 0)
            if amt <= 0 or dep < amt:
                bot.reply_to(message, f"❌ В банке недостаточно средств! На депозите: {dep} 🪙 😿")
                return
            econ['bank_deposit'] -= amt
            _adjust_balance(econ, amt)
            if econ['bank_deposit'] == 0:
                econ['last_bank_calc'] = time.time()
            mark_dirty()
            bot.reply_to(message, f"💸 Вы сняли <b>{amt} 🪙</b> с банковского счёта! 😺\nОстаток в банке: <b>{econ['bank_deposit']} 🪙</b>", parse_mode='HTML')
        return

    # РП-КОМАНДЫ МОЖНО ОТКЛЮЧИТЬ ДЛЯ КОНКРЕТНОГО ЧАТА
    chat_sett = get_chat_settings(chat_id)
    if chat_sett.get('rp_enabled', True):
        # ОДИНОЧНЫЕ РП
        for solo_cmd, (solo_text, solo_emoji) in RP_SOLO_ACTIONS.items():
            if text_lower == solo_cmd or text_lower.startswith(f"{solo_cmd} "):
                sender_link = make_link(chat_id, user_name, user_id, ping=True)
                check_achievements(user_id, user_name, 'rp_actions', 1, chat_id, username=user_username)
                add_account_exp(user_id, user_name, 3, username=user_username)
                bot.send_message(chat_id, f"{solo_emoji} {sender_link} {solo_text}", parse_mode='HTML')
                return

        # ПАРНЫЕ РП
        for rp_cmd, rp_data in RP_ACTIONS.items():
            if text_lower.startswith(rp_cmd):
                target_user = None
                target_user_id = None
                if message.reply_to_message:
                    u = message.reply_to_message.from_user
                    target_user = (f"{u.first_name or ''} {u.last_name or ''}").strip() or u.username
                    target_user_id = u.id
                else:
                    raw_arg = text[len(rp_cmd):].strip()
                    if raw_arg:
                        uid, uname = resolve_user_from_string(chat_id, raw_arg)
                        target_user = uname or raw_arg
                        target_user_id = uid

                if target_user:
                    if target_user_id == user_id:
                        bot.reply_to(message, "❌ Вы не можете использовать это действие на себе! 😾")
                        return
                    sender_link = make_link(chat_id, user_name, user_id, ping=True)
                    target_link = make_link(chat_id, target_user, target_user_id, ping=True)
                    check_achievements(user_id, user_name, 'rp_actions', 1, chat_id, username=user_username)
                    add_account_exp(user_id, user_name, 3, username=user_username)
                    k_val = rp_data.get('karma', 0)
                    if k_val != 0:
                        change_karma(user_id, user_name, k_val)
                        k_sign = "+" if k_val > 0 else ""
                        k_str = f" [Карма {k_sign}{k_val}]"
                    else:
                        k_str = ""
                    bot.send_message(chat_id, f"{rp_data['emoji']} {sender_link} <b>{rp_data['verb']}</b> {target_link}!{k_str}", parse_mode='HTML')
                    return
                else:
                    bot.reply_to(message, f"💡 Ответьте на сообщение или укажите ник:\n<code>{rp_cmd} @username</code> 😸", parse_mode='HTML')
                    return

    # КТО ТЫ
    who_match = re.match(r'^(?:кто\s+ты)(?:\s+(.+))?$', text_lower)
    if who_match:
        target_query = who_match.group(1)
        target_found_id = None
        target_found_name = None
        if message.reply_to_message:
            u = message.reply_to_message.from_user
            target_found_name = (f"{u.first_name or ''} {u.last_name or ''}").strip() or u.username
            target_found_id = u.id
        elif target_query:
            target_found_id, target_found_name = resolve_user_from_string(chat_id, target_query.strip())
        else:
            target_found_name = user_name
            target_found_id = user_id
        in_rest, rest_info, _ = check_user_rest(db.get('rests', {}).get(str_chat, {}), user_id=target_found_id, user_name=target_found_name)
        if in_rest and rest_info:
            display_name = rest_info.get('user_name', target_found_name or 'Пользователь')
            user_link = make_link(chat_id, display_name, target_found_id or rest_info.get('user_id'), ping=False)
            bot.reply_to(message, f"🌴 <b>Пользователь {user_link} находится в ресте!</b> 😺\n📝 <b>Причина:</b> {html.escape(str(rest_info.get('reason', 'Не указана')))}\n⏱ <b>Срок:</b> {html.escape(rest_info.get('duration', 'Не указан'))}", parse_mode='HTML')
        else:
            display_name = target_found_name or 'Пользователь'
            user_link = make_link(chat_id, display_name, target_found_id, ping=False)
            bot.reply_to(message, f"✅ Пользователь {user_link} сейчас не находится в ресте! 😸", parse_mode='HTML')
        return

    for pattern, responses in ALWAYS_ACTIVE_PATTERNS.items():
        if re.search(pattern, text_lower, re.IGNORECASE):
            bot.reply_to(message, random.choice(responses))
            break

    if text_lower in ['+смехуятинка', 'смехуятинка']:
        if message.reply_to_message:
            target_u = message.reply_to_message.from_user
            target_tag = (f"{target_u.first_name or ''} {target_u.last_name or ''}").strip() or target_u.username
            target_id = target_u.id
            econ = get_user_econ(target_id, target_tag, username=target_u.username)
            econ['smeh'] = econ.get('smeh', 0) + 1
            check_achievements(target_id, target_tag, 'smeh_check', 1, chat_id, username=target_u.username)
            mark_dirty()
            u_link = make_link(chat_id, target_tag, target_id, ping=True)
            bot.reply_to(message, f"😂 Пользователю {u_link} начислено +1 очко <b>Смехуятинки</b>!\nВсего: <b>{econ['smeh']}</b> 😹", parse_mode='HTML')
        else: bot.reply_to(message, "❌ Ответьте этой командой на сообщение человека! 😾")
        return

    # РУССКИЙ ЭКОНОМИЧЕСКИЙ РОУТЕР — команды можно писать без /
    # Примеры: «передать 10000» (ответом на сообщение), «банк положить 5000».
    if text_lower.startswith(('передать ', 'перевод ', 'отправить ', 'скинуть ', '/pay ')):
        target_id, target_u, amount = parse_transfer_command(message)
        if amount <= 0 or not target_u:
            bot.reply_to(message, "❌ Формат: <code>передать @username 10000</code> или ответом на сообщение: <code>передать 10000</code>. 😾", parse_mode='HTML')
            return
        if not target_id or int(target_id) <= 0:
            bot.reply_to(message, "❌ Получатель не найден. Укажите реального пользователя: <code>@username</code>, ID или ответьте на его сообщение.", parse_mode='HTML')
            return
        if target_id == user_id:
            bot.reply_to(message, "❌ Нельзя переводить коины самому себе! 🙀")
            return
        with serialized_multi_user_action(user_id, int(target_id)):
            sender_econ = get_user_econ(user_id, user_name, username=user_username)
            target_econ = get_user_econ(user_id=int(target_id), user_tag=target_u)
            if sender_econ['balance'] < amount:
                bot.reply_to(message, f"❌ Недостаточно Ня-коинов! У вас: <b>{sender_econ['balance']} 🪙</b> 😿", parse_mode='HTML')
                return
            tax = max(1, int(amount * 0.03))
            receive_amount = amount - tax
            if receive_amount <= 0:
                bot.reply_to(message, "❌ Слишком маленькая сумма для перевода.")
                return
            _adjust_balance(sender_econ, -amount)
            sender_econ['daily_transferred'] = sender_econ.get('daily_transferred', 0) + amount
            _adjust_balance(target_econ, receive_amount)
            mark_dirty()
        target_link = make_link(chat_id, target_u, target_id, ping=True)
        bot.reply_to(message, f"💸 <b>Перевод выполнен!</b>\n\n👤 Получатель: {target_link}\n💰 Отправлено: <b>{amount:,} 🪙</b>\n🧾 Комиссия 3%: <b>{tax:,} 🪙</b>\n📥 Получит: <b>{receive_amount:,} 🪙</b>\n💳 Остаток: <b>{sender_econ['balance']:,} 🪙</b> 😸", parse_mode='HTML')
        return

    # БАНК: пополнение/снятие прямо текстом, без кнопок.
    m_bank = re.match(r'^(?:банк|депозит|сч[её]т)\\s+(положить|внести|пополнить|снять|вывести)\\s+(\\d+)$', text_lower)
    if m_bank:
        action, amount_raw = m_bank.groups()
        amount = int(amount_raw)
        if amount <= 0:
            bot.reply_to(message, "❌ Сумма должна быть больше нуля.")
            return
        econ = get_user_econ(user_id, user_name, username=user_username)
        update_bank_interest(econ)
        if action in ('положить', 'внести', 'пополнить'):
            if econ.get('balance', 0) < amount:
                bot.reply_to(message, f"❌ В кошельке только <b>{econ.get('balance', 0)} 🪙</b>.", parse_mode='HTML')
                return
            _adjust_balance(econ, -(amount))
            econ['bank_deposit'] = econ.get('bank_deposit', 0) + amount
            action_text = f"📥 На счёт внесено <b>{amount:,} 🪙</b>"
        else:
            if econ.get('bank_deposit', 0) < amount:
                bot.reply_to(message, f"❌ На депозите только <b>{econ.get('bank_deposit', 0)} 🪙</b>.", parse_mode='HTML')
                return
            econ['bank_deposit'] -= amount
            _adjust_balance(econ, amount)
            action_text = f"📤 Со счёта снято <b>{amount:,} 🪙</b>"
        mark_dirty()
        bot.reply_to(message, f"🏦 <b>НЯ-БАНК</b>\n{action_text}\n💳 В банке: <b>{econ.get('bank_deposit', 0):,} 🪙</b>\n💵 В кошельке: <b>{econ.get('balance', 0):,} 🪙</b>", parse_mode='HTML')
        return

    # Удобные русские названия существующих разделов.
    simple_aliases = {
        'кошелек': cmd_balance, 'кошелёк': cmd_balance, 'счёт': cmd_balance,
        'магазин': cmd_shop, 'шоп': cmd_shop, 'инв': cmd_inventory, 'рюкзак': cmd_backpack,
        'задания': cmd_tasks, 'квесты': cmd_tasks, 'достижения': cmd_achievements, 'ачивки': cmd_achievements,
        'профиль': cmd_profile, 'банк': cmd_bank, 'депозит': cmd_bank,
        'кейс': cmd_case, 'сундук': cmd_case, 'лотерея': cmd_lottery,
        'кредит': cmd_loan, 'погасить кредит': cmd_repay, 'погасить': cmd_repay,
        'работа': cmd_work, 'бизнес': cmd_business, 'бизнесы': cmd_business,
        'прибыль': cmd_collect, 'собрать прибыль': cmd_collect,
        'сад': cmd_garden, 'вакансии': cmd_public_jobs, 'jobs': cmd_public_jobs, 'зарплата': cmd_public_salary, 'salary': cmd_public_salary, 'монополия': cmd_monopoly, 'monopoly': cmd_monopoly, 'жильё': cmd_personal_home, 'жилье': cmd_personal_home, 'одежда питомца': cmd_pet_clothes,
        'топ': cmd_top, 'топ дня': cmd_top_daily, 'топ недели': cmd_top_weekly,
        'рулетка': cmd_wheel, 'мины': cmd_mines, 'дурак': cmd_durak,
        'ресурсы': cmd_resources_command, 'коллекция': cmd_collection, 'гильдия': cmd_guild_command, 'клан': cmd_guild_command, 'рынок игроков': cmd_player_market_command, 'рейд': cmd_raid_command, 'сезон': cmd_season_command, 'карта': cmd_world_command,
    }
    if text_lower in simple_aliases:
        simple_aliases[text_lower](message)
        return

    # ТЕКСТОВЫЕ КОМАНДЫ
    if text_lower in ['хромосомы', 'хромосома', 'замер хромосом']: cmd_chromosomes(message); return
    elif text_lower in ['айкью', 'iq', 'iqи', 'айкю']: cmd_iq(message); return
    elif text_lower in ['жир', 'жирок', 'жирность', 'процент жира']: cmd_fat(message); return
    elif text_lower in ['пятка', 'пяточка', 'размер пятки', 'пятки']: cmd_foot(message); return
    elif text_lower in ['писюн', 'член', 'замер']: cmd_dick(message); return
    elif text_lower in ['дроч', 'подрочить', 'фап']: cmd_fap(message); return
    elif text_lower in ['рюкзак', 'баффы']: cmd_backpack(message); return
    elif text_lower in ['мусорка', 'помойка', 'мусор']: cmd_trash(message); return
    elif text_lower in ['герои дня', 'итоги дня', 'ударники дня']: cmd_daily_heroes(message); return
    elif text_lower in ['факт вд', 'вд факт', 'факт violence district', 'факт']: cmd_fact_vd(message); return
    elif text_lower in ['питомец', 'пет', 'мой питомец']: cmd_pet(message); return
    elif text_lower in ['майнер', 'майнинг', 'криптоферма', 'ферма']: cmd_miner(message); return
    elif text_lower in ['гараж', 'тачки', 'машины']: cmd_garage(message); return
    elif text_lower in ['кулинария', 'приготовить', 'готовка']: cmd_cook(message); return
    elif text_lower in ['гулять', 'погулять']: cmd_walk_pet(message); return
    elif text_lower in ['рулетка', 'колесо']: cmd_wheel(message); return
    elif text_lower in ['снасти', 'удочки', 'луки']: cmd_gear(message); return
    elif text_lower in ['ачивки', 'достижения']: cmd_achievements(message); return
    elif text_lower in ['бизнес', 'бизнесы']: cmd_business(message); return
    elif text_lower in ['собрать', 'собрать прибыль', 'прибыль']: cmd_collect(message); return
    elif text_lower in ['семья', 'брак', 'мой брак']: cmd_family(message); return
    elif text_lower in ['подарок']: cmd_gift(message); return
    elif text_lower in ['развод']: cmd_divorce(message); return
    elif text_lower in ['баланс', 'коины', 'ня-коины', 'деньги']: cmd_balance(message); return
    elif text_lower in ['инвентарь', 'профиль', 'мои значки']: cmd_profile(message); return
    elif text_lower in ['пасс', 'пас', 'пропуск', 'хеллоуин', 'bp', '/pass']: cmd_halloween_pass(message); return
    elif text_lower in ['звезды', 'донат', 'stars', 'vip', 'nya pass']: cmd_stars(message); return
    elif text_lower in ['магазин', 'шоп']: cmd_shop(message); return
    elif text_lower in ['биржа', 'крипта', 'рынок']: cmd_market(message); return
    elif text_lower in ['портфель', 'мои акции']: cmd_portfolio(message); return
    elif text_lower in ['работа', 'вакансии']: cmd_work(message); return
    elif text_lower in ['опыт', 'тренировка']: cmd_train(message); return
    elif text_lower in ['кейс', 'сундук']: cmd_case(message); return
    elif text_lower in ['лотерея']: cmd_lottery(message); return
    elif text_lower in ['задания', 'квесты']: cmd_tasks(message); return
    elif text_lower in ['помощь', 'меню', 'навигатор', 'инфо']: send_welcome(message); return
    elif text_lower in ['настройки']: cmd_settings(message); return
    elif text_lower in ['сад', 'оранжерея']: cmd_garden(message); return
    elif text_lower.startswith('история'): cmd_history(message); return
    elif text_lower in ['мемы']: cmd_memes(message); return
    elif text_lower.startswith(('промо', 'промокод')): cmd_promo(message); return
    elif text_lower.startswith(('дурак', '/durak')): cmd_durak(message); return
    elif text_lower in ['настройки профиля', 'настройка профиля']: cmd_profile_settings(message); return
    elif text_lower.startswith(('сейф', '/safe')): cmd_safe(message); return
    elif text_lower in ['дом', 'мой дом', 'семейный дом', '/house']: cmd_house(message); return
    elif text_lower in ['шериф', 'полиция', '/sheriff']: cmd_sheriff(message); return
    elif text_lower.startswith(('поймать', '/catch')): cmd_catch(message); return
    elif text_lower in ['кпз', 'тюрьма', '/jail']: cmd_jail(message); return
    elif text_lower in ['побег', '/escape']: cmd_escape(message); return
    elif text_lower.startswith(('залог', '/bail')): cmd_bail(message); return
    elif text_lower.startswith(('бой питомцев', 'битвы питомцев', 'бой', '/pet_fight')): cmd_pet_fight(message); return
    elif text_lower.startswith(('мем', '/meme')): cmd_meme(message); return
    elif text_lower.startswith(('фанфик', '/story', '/fanfic')): cmd_story(message); return
    elif text_lower in ['аптека', 'больница', '/pharmacy']: cmd_pharmacy(message); return
    elif text_lower.startswith(('подарить звезды', 'подарок звезды', '/gift_stars')): cmd_gift_stars(message); return

    # ТОПЫ ТЕКСТОМ
    elif text_lower in ['топ', 'топы', 'лидеры', 'топ богачей', 'топ баланс', 'топ денег']: render_top_menu(chat_id, user_id=user_id, category='rich'); return
    elif text_lower in ['топ писюнов', 'топ писюн', 'топ член']: render_top_menu(chat_id, user_id=user_id, category='dick'); return
    elif text_lower in ['топ айкью', 'топ iq', 'топ умных']: render_top_menu(chat_id, user_id=user_id, category='iq'); return
    elif text_lower in ['топ кармы', 'топ ангелов', 'топ добрых']: render_top_menu(chat_id, user_id=user_id, category='karma'); return
    elif text_lower in ['топ жир', 'топ жира', 'топ жирных']: render_top_menu(chat_id, user_id=user_id, category='fat'); return
    elif text_lower in ['топ пяток', 'топ пятка']: render_top_menu(chat_id, user_id=user_id, category='foot'); return
    elif text_lower in ['топ хромосом', 'топ хромосомы']: render_top_menu(chat_id, user_id=user_id, category='chr'); return
    elif text_lower in ['топ сообщений', 'топ актива', 'топ смс']: render_top_menu(chat_id, user_id=user_id, category='msg'); return

    # СПОРТ-ИГРЫ ТЕКСТОМ
    elif text_lower.startswith(('футбол', 'пенальти')): cmd_football(message); return
    elif text_lower.startswith(('баскетбол', 'баскет')): cmd_basketball(message); return
    elif text_lower.startswith(('дартс', 'дротик')): cmd_darts(message); return
    elif text_lower.startswith(('боулинг', 'страйк')): cmd_bowling(message); return
    elif text_lower.startswith(('сапер', 'мины')): cmd_mines(message); return
    elif text_lower in ['классический сапер', 'сапер классик', 'csaper', 'сапёр']: cmd_classic_mines(message); return
    elif text_lower.startswith(('краш', 'ракета')): cmd_crash(message); return
    elif text_lower.startswith(('блэкджек', '21', 'очко')): cmd_bj(message); return
    elif text_lower.startswith(('кирпич', 'стройка')): cmd_brick(message); return

    # ЕЖЕДНЕВНЫЙ БОНУС
    elif text_lower in ['бонус', 'коин', 'взять бонус']:
        econ = get_user_econ(user_id, user_name, username=user_username)
        cooldown = 3600
        left = cooldown_text(econ.get('last_hourly', 0), cooldown, econ)
        if not left:
            now_sec = time.time()
            last_streak = econ.get('last_streak_time', 0)
            diff_hours = (now_sec - last_streak) / 3600.0

            if diff_hours < 48 and last_streak > 0:
                if diff_hours >= 20:
                    econ['bonus_streak'] = econ.get('bonus_streak', 0) + 1
                    econ['last_streak_time'] = now_sec
            else:
                econ['bonus_streak'] = 1
                econ['last_streak_time'] = now_sec

            streak = econ.get('bonus_streak', 1)
            streak_mult = min(2.0, 1.0 + (streak * 0.15))

            lvl, _, _, _ = get_account_level(econ.get('account_exp', 0))
            base_reward = random.randint(20, 45) + (lvl * 3)

            active_t = econ.get('active_title')
            if active_t and active_t in TITLES and TITLES[active_t].get('buff') == 'bonus_coins':
                base_reward += TITLES[active_t]['val']
            if econ.get('pet') and econ['pet'].get('id') == 'panda':
                base_reward = int(base_reward * 1.35)
            donor_bonus = get_title_bonus_multiplier(econ)
            if donor_bonus:
                base_reward = int(base_reward * (1.0 + donor_bonus))

            final_reward = int(base_reward * streak_mult)
            is_vip = econ.get('vip_forever') or (econ.get('vip_until', 0) > now_ts)
            if is_vip:
                final_reward = int(final_reward * 2.25)

            _adjust_balance(econ, final_reward)
            econ['last_hourly'] = now_ts
            add_account_exp(user_id, user_name, 10, username=user_username)
            mark_dirty()
            check_achievements(user_id, user_name, 'bonuses', 1, chat_id, username=user_username)
            completed = track_daily_task(user_id, user_name, 'bonus', 1, chat_id, username=user_username)

            vip_bonus_text = "\n⭐️ <b>VIP NYA PASS: Бонус увеличен (x2.25)!</b>" if is_vip else ""
            streak_note = f"\n🔥 <b>Стрик: {streak} дн.</b> (Множитель x{streak_mult:.2f})!{vip_bonus_text}"
            bot.reply_to(message, f"🎲 Вы собрали часовой бонус: <b>+{final_reward} Ня-коинов 🪙</b>!{streak_note}\nБаланс: <b>{econ['balance']} 💸</b> 😸", parse_mode='HTML')
            for task_name, task_reward in completed: bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙 😻', parse_mode='HTML')
        else:
            bot.reply_to(message, f"⏳ Бонус доступен каждый час! Ждать: <b>{left}</b>. 😿", parse_mode='HTML')
        return

    # КОСТИ (БЕЗ АБУЗА БЕСПЛАТНОГО EXP)
    elif text_lower.startswith(('кости', '/dice', 'кубик')):
        match = re.search(r'(?:кости|/dice|кубик)\s*(\d+)?', text, re.IGNORECASE)
        bet = int(match.group(1)) if match and match.group(1) else 0

        econ = get_user_econ(user_id, user_name, username=user_username)
        if bet < 30 and bet != 0:
            bot.reply_to(message, '❌ Минимальная ставка — 30 Ня-коинов! 😾')
            return
        if bet > econ['balance']:
            bot.reply_to(message, '❌ Недостаточно Ня-коинов для ставки! 😿')
            return

        if bet > 0:
            _adjust_balance(econ, -(bet))
            process_casino_bet(bet, chat_id)

        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)

        total = d1 + d2
        result = f'🎲 Выпало: <b>{d1} + {d2} = {total}</b>. 😺'
        if bet > 0:
            if total == 12:
                win = process_casino_win(int(bet * 3.0))
                _adjust_balance(econ, win)
                result += f'\n🎉 Джекпот 12! Вы выиграли <b>+{win} 🪙</b> (3.0x)! 🙀'
            elif total >= 8:
                win = process_casino_win(int(bet * 1.95))
                _adjust_balance(econ, win)
                result += f'\n✅ Победа! Выплата: <b>+{win} 🪙</b> (1.95x) 😻'
            else:
                result += f'\n💸 Вы проиграли <b>{bet} 🪙</b>. 😿'
            add_account_exp(user_id, user_name, 5, username=user_username)
            mark_dirty()
            check_achievements(user_id, user_name, 'games', 1, chat_id, username=user_username)
            completed = track_daily_task(user_id, user_name, 'dice', 1, chat_id, username=user_username)
            for task_name, task_reward in completed: bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙 😻', parse_mode='HTML')
        bot.reply_to(message, result + f"\n💰 Баланс: <b>{econ['balance']} 🪙</b> 😸", parse_mode='HTML')
        return

    # СЛОТЫ
    elif text_lower.startswith(('слоты', '/slots', 'казино')):
        match = re.search(r'(?:слоты|/slots|казино)\s*(\d+)?', text, re.IGNORECASE)
        bet = int(match.group(1)) if match and match.group(1) else 0

        econ = get_user_econ(user_id, user_name, username=user_username)
        if bet < 30:
            bot.reply_to(message, '❌ Минимальная ставка — 30 Ня-коинов! 😾', parse_mode='HTML')
            return
        if bet > econ['balance']:
            bot.reply_to(message, f"❌ Недостаточно коинов! Ваш баланс: <b>{econ['balance']} 🪙</b> 😿", parse_mode='HTML')
            return

        _adjust_balance(econ, -(bet))
        process_casino_bet(bet, chat_id)

        symbols_pool = ['🍒', '🍋', '🍊', '🍀', '⭐', '💎']
        luck_bonus = econ['pet'].get('luck_bonus', 0) if econ.get('pet') else 0
        if econ.get('luck_clover_until', 0) > now_ts: luck_bonus += 15

        pool = db.get('casino_pool', 1000000)
        if pool < bet * 10:
            weights = [38, 32, 18, 8, 3, 1]
        else:
            weights = [30, 25, 20, 14, 8 + int(luck_bonus * 0.04), 3 + int(luck_bonus * 0.03)]
            
        roll = random.choices(symbols_pool, weights=weights, k=3)
        result = f"🎰 <b>[ {roll[0]} | {roll[1]} | {roll[2]} ]</b> 😺\n"

        if roll[0] == roll[1] == roll[2] == '💎':
            win = process_casino_win(int(bet * 5))
            _adjust_balance(econ, win)
            result += f'\n💎👑 <b>МЕГА ДЖЕКПОТ (5x)!</b> Выигрыш: <b>+{win} 🪙</b>! 🙀'
        elif roll[0] == roll[1] == roll[2] and roll[0] in ['⭐', '🍀']:
            multiplier = 3 if roll[0] == '⭐' else 2.5
            win = process_casino_win(int(bet * multiplier))
            _adjust_balance(econ, win)
            result += f'\n🌟 <b>ОГРОМНЫЙ ВЫИГРЫШ ({multiplier}x)!</b> Награда: <b>+{win} 🪙</b>! 😻'
        elif roll[0] == roll[1] == roll[2]:
            win = process_casino_win(int(bet * 1.8))
            _adjust_balance(econ, win)
            result += f'\n🎉 <b>Три в ряд (1.8x)!</b> Выигрыш: <b>+{win} 🪙</b>! 😸'
        elif roll.count('💎') == 2 or roll.count('⭐') == 2:
            win = process_casino_win(int(bet * 1.2))
            _adjust_balance(econ, win)
            result += f'\n✨ <b>Два редких символа!</b> Выигрыш: <b>+{win} 🪙</b> (1.2x)! 😽'
        elif len(set(roll)) == 2:
            win = process_casino_win(int(bet * 0.6))
            _adjust_balance(econ, win)
            result += f'\n🙂 <b>Два совпадения!</b> Частичный возврат: <b>{win} 🪙</b> (0.6x).'
        else:
            result += f'\n💸 Проигрыш <b>-{bet} 🪙</b>. 😿'

        add_account_exp(user_id, user_name, 5, username=user_username)
        mark_dirty()
        check_achievements(user_id, user_name, 'games', 1, chat_id, username=user_username)
        completed = track_daily_task(user_id, user_name, 'slots', 1, chat_id, username=user_username)
        bot.reply_to(message, result + f"\n💰 Баланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
        for task_name, task_reward in completed: bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙 😻', parse_mode='HTML')
        return

    # РЫБАЛКА И ОХОТА
    elif text_lower in ['рыбалка', '/fish', 'рыба']:
        econ = get_user_econ(user_id, user_name, username=user_username)
        cooldown = 7200
        left = cooldown_text(econ.get('last_fish_time', 0), cooldown, econ)
        if left:
            bot.reply_to(message, f'⏳ Рыбалка доступна раз в 2 часа. Осталось ждать: <b>{left}</b>. 😿', parse_mode='HTML')
            return

        luck_bonus = econ['pet'].get('luck_bonus', 0) if econ.get('pet') else 0
        rod = econ.get('equipped_rod')
        if rod and rod in RODS: luck_bonus += RODS[rod]['luck']
        if gold_rush_event.get('active'): luck_bonus += 50

        weights = [max(1, int(f[3] * (1 + luck_bonus / 100.0))) for f in FISH_TYPES]
        caught = random.choices(FISH_TYPES, weights=weights, k=1)[0]
        econ['last_fish_time'] = time.time()
        add_inventory_item(econ['fish_inventory'], caught[0])
        add_account_exp(user_id, user_name, 8, username=user_username)
        mark_dirty()
        check_achievements(user_id, user_name, 'fish', 1, chat_id, username=user_username)
        rush_info = "\n🌟 <i>Действует Золотая Лихорадка (+50% к шансу)!</i>" if gold_rush_event.get('active') else ""
        bot.reply_to(message, f'🎣 Вы поймали: <b>{caught[0]}</b> [{caught[1]}]! 😺\n💰 Базовая цена: <b>{caught[2]} 🪙</b>{rush_info}\n💡 Продать: <code>продать</code> | Приготовить: <code>/cook</code>', parse_mode='HTML')
        return

    elif text_lower in ['охота', '/hunt']:
        econ = get_user_econ(user_id, user_name, username=user_username)
        cooldown = 7200
        left = cooldown_text(econ.get('last_hunt_time', 0), cooldown, econ)
        if left:
            bot.reply_to(message, f'⏳ Охота доступна раз в 2 часа. Осталось ждать: <b>{left}</b>. 😿', parse_mode='HTML')
            return

        luck_bonus = econ['pet'].get('luck_bonus', 0) if econ.get('pet') else 0
        bow = econ.get('equipped_bow')
        if bow and bow in BOWS: luck_bonus += BOWS[bow]['luck']
        if gold_rush_event.get('active'): luck_bonus += 50

        weights = [max(1, int(h[3] * (1 + luck_bonus / 100.0))) for h in HUNT_TYPES]
        caught = random.choices(HUNT_TYPES, weights=weights, k=1)[0]
        econ['last_hunt_time'] = time.time()
        add_inventory_item(econ['hunt_inventory'], caught[0])
        add_account_exp(user_id, user_name, 8, username=user_username)
        mark_dirty()
        check_achievements(user_id, user_name, 'hunt', 1, chat_id, username=user_username)
        rush_info = "\n🌟 <i>Действует Золотая Лихорадка (+50% к шансу)!</i>" if gold_rush_event.get('active') else ""
        bot.reply_to(message, f'🏹 Вы добыли: <b>{caught[0]}</b> [{caught[1]}]! 😺\n💰 Базовая цена: <b>{caught[2]} 🪙</b>{rush_info}\n💡 Продать: <code>продать</code> | Приготовить: <code>/cook</code>', parse_mode='HTML')
        return

    # ПЕРЕВОД КОИНОВ
    elif text_lower.startswith(('перевод', 'передать', 'отправить', 'скинуть', '/pay')):
        target_id, target_u, amount = parse_transfer_command(message)

        if amount <= 0 or not target_u:
            bot.reply_to(message, "❌ Формат: <code>передать @username 10000</code> или ответом на сообщение: <code>передать 10000</code>. 😾", parse_mode='HTML')
            return

        if not target_id or int(target_id) <= 0:
            bot.reply_to(message, "❌ Получатель не найден. Укажите реального пользователя: <code>@username</code>, ID или ответьте на его сообщение.", parse_mode='HTML')
            return
        if target_id == user_id:
            bot.reply_to(message, "❌ Нельзя переводить коины самому себе! 🙀")
            return

        with TRANSFER_LOCK:
            sender_econ = get_user_econ(user_id, user_name, username=user_username)
            if sender_econ['balance'] < amount:
                bot.reply_to(message, f"❌ Недостаточно Ня-коинов! У вас: <b>{sender_econ['balance']} 🪙</b> 😿", parse_mode='HTML')
                return

            tax = max(1, int(amount * 0.03))
            receive_amount = amount - tax
            if receive_amount <= 0:
                bot.reply_to(message, "❌ Слишком маленькая сумма для перевода.")
                return

            _adjust_balance(sender_econ, -(amount))
            sender_econ['daily_transferred'] = sender_econ.get('daily_transferred', 0) + amount
            target_econ = get_user_econ(user_id=target_id, user_tag=target_u)
            _adjust_balance(target_econ, receive_amount)
            mark_dirty()
        change_karma(user_id, user_name, 1)
        check_achievements(user_id, user_name, 'transfers', 1, chat_id, username=user_username)
        track_daily_task(user_id, user_name, 'transfer', 1, chat_id, username=user_username)

        target_link = make_link(chat_id, target_u, target_id, ping=True)
        bot.reply_to(
            message,
            f"💸 Вы перевели <b>{amount} 🪙</b> пользователю {target_link}! 😻\n"
            f"<i>(Комиссия 3%: сожжено {tax} 🪙, зачислено {receive_amount} 🪙)</i>\n"
            f"Ваш остаток: <b>{sender_econ['balance']} 🪙</b> 😸",
            parse_mode='HTML'
        )
        return

    # МОДЕРАЦИЯ: русские текстовые команды без /.
    if text_lower.startswith(('бан ', 'бан\n')) or text_lower == 'бан': _execute_moderation(message,'ban'); return
    if text_lower.startswith(('мут ', 'мут\n')) or text_lower == 'мут': _execute_moderation(message,'mute'); return
    if text_lower.startswith(('кик ', 'кик\n')) or text_lower == 'кик': _execute_moderation(message,'kick'); return
    if text_lower.startswith(('варн ', 'варн\n')) or text_lower == 'варн': _execute_moderation(message,'warn'); return
    if text_lower.startswith(('разбан ', 'анбан ')) or text_lower == 'разбан': _clear_moderation(message,'unban'); return
    if text_lower.startswith(('анмут ', 'снятьмут ')) or text_lower in ('анмут','снятьмут'): _clear_moderation(message,'unmute'); return
    if text_lower in ('баны','банлист','список банов'): _mod_list(message,'ban'); return
    if text_lower in ('муты','мутлист','список мутов'): _mod_list(message,'mute'); return
    if text_lower in ('варны','варнлист','список варнов'): _mod_list(message,'warn'); return

    # РЕСТЫ
    if text_lower.startswith('+рест'):
        if not is_admin(chat_id, user_id): return
        target_name, target_id, duration_text, reason = parse_rest_command(message)
        if target_name and duration_text:
            reward_given, count = apply_rest(chat_id, target_name, duration_text, reason, target_id)
            if count is None:
                bot.reply_to(message, '❌ Указанная дата уже прошла. Рест с прошедшей датой не создаётся.', parse_mode='HTML')
                return
            user_link = make_link(chat_id, target_name, target_id, ping=True)
            bot.reply_to(message, f'✅ Рест для {user_link} добавлен на {duration_text} (Причина: {reason})! 😺', parse_mode='HTML')

    elif text_lower.startswith('-рест'):
        if not is_admin(chat_id, user_id): return
        target_name = None
        target_id = None
        if message.reply_to_message:
            u = message.reply_to_message.from_user
            target_name = (f"{u.first_name or ''} {u.last_name or ''}").strip() or u.username
            target_id = u.id
        else:
            raw_arg = text[5:].strip()
            if raw_arg: target_id, target_name = resolve_user_from_string(chat_id, raw_arg)

        if str_chat in db.get('rests', {}):
            in_rest, rest_info, found_key = check_user_rest(db['rests'][str_chat], user_id=target_id, user_name=target_name)
            if in_rest and found_key:
                display_name = rest_info.get('user_name', target_name or found_key)
                del db['rests'][str_chat][found_key]
                add_to_history(str_chat, display_name, 'Снят', 'Досрочно администратором', target_id, "Снят рест (вручную)")
                mark_dirty()
                u_link = make_link(chat_id, display_name, target_id or rest_info.get("user_id"), ping=True)
                log_event('РЕСТ СНЯТ', f'Чат: <code>{chat_id}</code>\nАдмин: ID:{user_id}\nПользователь: {u_link}')
                bot.reply_to(message, f'🗑 Рест с {u_link} успешно снят. 😺', parse_mode='HTML')
            else:
                bot.reply_to(message, f'❌ Рест для указанного пользователя не найден. 😿', parse_mode='HTML')

    elif text_lower in ['ресты', 'рест']:
        if str_chat not in db['rests'] or not db['rests'][str_chat]:
            bot.reply_to(message, '🌴 В данный момент никто не находится в ресте. 😸')
        else:
            resp = '📋 <b>СПИСОК АКТИВНЫХ РЕСТОВ:</b> 😺\n━━━━━━━━━━━━━━━━━━━━\n'
            for r_key, info in db['rests'][str_chat].items():
                u_name = info.get('user_name', r_key)
                u_id = info.get('user_id')
                resp += f"• {make_link(chat_id, u_name, u_id, ping=False)} — {info['duration']} (Причина: {html.escape(str(info.get('reason', 'Не указана')))})\n"
            resp += '━━━━━━━━━━━━━━━━━━━━'

            markup = None
            if is_admin(chat_id, user_id):
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🗑 Снять рест (Выбрать)", callback_data=f"rest_remove_menu:{user_id}"))

            bot.reply_to(message, resp, reply_markup=markup, parse_mode='HTML')

def register(ctx, only=None):
    """Register selected handlers from this feature module."""
    _inject(ctx)
    bot = ctx["bot"]
    wanted = set(only) if only is not None else set(HANDLER_NAMES)
    registered = []
    if "handle_bot_chat_membership" in wanted:
        _handler = handle_bot_chat_membership
        _handler = serialize_user_action(_handler)
        bot.my_chat_member_handler()(_handler)
        ctx["handle_bot_chat_membership"] = _handler
        globals()["handle_bot_chat_membership"] = _handler
        registered.append("handle_bot_chat_membership")
    if "welcome_new_members" in wanted:
        _handler = welcome_new_members
        _handler = serialize_user_action(_handler)
        bot.message_handler(content_types=['new_chat_members'])(_handler)
        ctx["welcome_new_members"] = _handler
        globals()["welcome_new_members"] = _handler
        registered.append("welcome_new_members")
    if "cmd_groups" in wanted:
        _handler = cmd_groups
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['groups', 'группы'])(_handler)
        ctx["cmd_groups"] = _handler
        globals()["cmd_groups"] = _handler
        registered.append("cmd_groups")
    if "cmd_find_group" in wanted:
        _handler = cmd_find_group
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['findgroup', 'найтигруппу'])(_handler)
        ctx["cmd_find_group"] = _handler
        globals()["cmd_find_group"] = _handler
        registered.append("cmd_find_group")
    if "cmd_user_lookup" in wanted:
        _handler = cmd_user_lookup
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['user', 'юзер', 'пользователь'])(_handler)
        ctx["cmd_user_lookup"] = _handler
        globals()["cmd_user_lookup"] = _handler
        registered.append("cmd_user_lookup")
    if "cmd_group_info" in wanted:
        _handler = cmd_group_info
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['groupinfo', 'инфогруппы'])(_handler)
        ctx["cmd_group_info"] = _handler
        globals()["cmd_group_info"] = _handler
        registered.append("cmd_group_info")
    if "cmd_ban" in wanted:
        _handler = cmd_ban
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['ban', 'бан'])(_handler)
        ctx["cmd_ban"] = _handler
        globals()["cmd_ban"] = _handler
        registered.append("cmd_ban")
    if "cmd_mute" in wanted:
        _handler = cmd_mute
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['mute', 'мут'])(_handler)
        ctx["cmd_mute"] = _handler
        globals()["cmd_mute"] = _handler
        registered.append("cmd_mute")
    if "cmd_kick" in wanted:
        _handler = cmd_kick
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['kick', 'кик'])(_handler)
        ctx["cmd_kick"] = _handler
        globals()["cmd_kick"] = _handler
        registered.append("cmd_kick")
    if "cmd_warn" in wanted:
        _handler = cmd_warn
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['warn', 'варн'])(_handler)
        ctx["cmd_warn"] = _handler
        globals()["cmd_warn"] = _handler
        registered.append("cmd_warn")
    if "cmd_unban" in wanted:
        _handler = cmd_unban
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['unban', 'разбан'])(_handler)
        ctx["cmd_unban"] = _handler
        globals()["cmd_unban"] = _handler
        registered.append("cmd_unban")
    if "cmd_unmute" in wanted:
        _handler = cmd_unmute
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['unmute', 'анмут', 'снятьмут'])(_handler)
        ctx["cmd_unmute"] = _handler
        globals()["cmd_unmute"] = _handler
        registered.append("cmd_unmute")
    if "cmd_bans" in wanted:
        _handler = cmd_bans
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['bans', 'баны'])(_handler)
        ctx["cmd_bans"] = _handler
        globals()["cmd_bans"] = _handler
        registered.append("cmd_bans")
    if "cmd_mutes" in wanted:
        _handler = cmd_mutes
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['mutes', 'муты'])(_handler)
        ctx["cmd_mutes"] = _handler
        globals()["cmd_mutes"] = _handler
        registered.append("cmd_mutes")
    if "cmd_warns" in wanted:
        _handler = cmd_warns
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['warns', 'варны'])(_handler)
        ctx["cmd_warns"] = _handler
        globals()["cmd_warns"] = _handler
        registered.append("cmd_warns")
    if "cmd_admins" in wanted:
        _handler = cmd_admins
        bot.message_handler(commands=['admins', 'админы'])(_handler)
        bot.message_handler(func=lambda m: bool(getattr(m, 'text', None)) and m.text.strip().lower() == '!админы')(_handler)
        ctx['cmd_admins'] = _handler; globals()['cmd_admins'] = _handler; registered.append('cmd_admins')
    if "cmd_admin_control" in wanted:
        _handler = cmd_admin_control
        _handler = serialize_user_action(_handler)
        bot.message_handler(func=lambda m: bool(getattr(m, 'text', None)) and m.text.strip().lower().startswith('!взм'))(_handler)
        ctx['cmd_admin_control'] = _handler; globals()['cmd_admin_control'] = _handler; registered.append('cmd_admin_control')
    if "handle_messages" in wanted:
        _handler = handle_messages
        _handler = serialize_user_action(_handler)
        bot.message_handler(func=lambda message: True)(_handler)
        ctx["handle_messages"] = _handler
        globals()["handle_messages"] = _handler
        registered.append("handle_messages")
    return registered
