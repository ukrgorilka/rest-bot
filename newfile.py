import csv
from datetime import datetime
import json
import os
import re
import threading
import time
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from flask import Flask

# ---------------------------------------------------------
# ВЕБ-СЕРВЕР ДЛЯ KEEP-ALIVE (RENDER)
# ---------------------------------------------------------
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

# ---------------------------------------------------------
# НАЛАШТУВАННЯ БОТА ТА БАЗИ ДАНИХ
# ---------------------------------------------------------
TOKEN = '8963495889:AAFFwRPYDVj1gqwz879G7HkZgpgXDoGt87g'
bot = telebot.TeleBot(TOKEN)

# ID вашого приватного каналу для авто-бекапів
DB_CHANNEL_ID = int(os.environ.get('DB_CHANNEL_ID', -1004334874700))
DATA_FILE = 'rests_data.json'

MONTHS = {
    'января': 1, 'январь': 1,
    'февраля': 2, 'февраль': 2,
    'марта': 3, 'март': 3,
    'апреля': 4, 'апрель': 4,
    'мая': 5, 'май': 5,
    'июня': 6, 'июнь': 6,
    'июля': 7, 'июль': 7,
    'августа': 8, 'август': 8,
    'сентября': 9, 'сентябрь': 9,
    'октября': 10, 'октябрь': 10,
    'ноября': 11, 'ноябрь': 11,
    'декабря': 12, 'декабрь': 12,
}

pending_requests = {}
req_counter = 0

# ---------------------------------------------------------
# БЛОК РОБОТИ З ДАНИМИ (JSON + TELEGRAM BACKUP)
# ---------------------------------------------------------
def load_data():
    """Завантажує найновіший бекап із Telegram-каналу, якщо локального файлу немає або він застарів"""
    data = {'rests': {}, 'history': {}, 'settings': {}}
    
    # Спроба отримати останній бекап-файл з Telegram-каналу при старті Render
    try:
        if DB_CHANNEL_ID:
            chat = bot.get_chat(DB_CHANNEL_ID)
            if chat and chat.pinned_message and chat.pinned_message.document:
                file_info = bot.get_file(chat.pinned_message.document.file_id)
                downloaded_file = bot.download_file(file_info.file_path)
                with open(DATA_FILE, 'wb') as new_file:
                    new_file.write(downloaded_file)
                print("Успішно завантажено бекап з закрепу в Telegram-каналі!")
    except Exception as e:
        print(f"Інфо: Завантаження з Telegram пропущено або виникла помилка: {e}")

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'settings' not in data:
                    data['settings'] = {}
                if 'rests' not in data:
                    data['rests'] = {}
                if 'history' not in data:
                    data['history'] = {}
                return data
        except Exception as e:
            print(f'Ошибка чтения файла: {e}')

    return data

def save_data():
    """Зберігає JSON локально та надсилає + закріплює оновлений файл у каналі-базі"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=4)
        
        # Відправка та закреплення в Telegram-каналі
        if DB_CHANNEL_ID:
            with open(DATA_FILE, 'rb') as f:
                msg = bot.send_document(DB_CHANNEL_ID, f, caption="💾 Auto-backup rests_data.json")
                try:
                    bot.pin_chat_message(DB_CHANNEL_ID, msg.message_id, disable_notification=True)
                except Exception:
                    pass
    except Exception as e:
        print(f"Помилка при збереженні бекапу в Telegram: {e}")

db = load_data()

def get_chat_settings(chat_id):
    str_chat = str(chat_id)
    if str_chat not in db['settings']:
        db['settings'][str_chat] = {
            'max_days': 30,
            'delete_rest_msg': False,
            'timezone_offset': 3,
            'remind_minutes': 60,
        }
        save_data()
    return db['settings'][str_chat]

# ---------------------------------------------------------
# ДОПОМІЖНІ ФУНКЦІЇ
# ---------------------------------------------------------
def clean_tag(user_str):
    if not user_str:
        return 'Пользователь'
    return user_str.replace('@', '')

def make_link(user_name, user_id=None):
    name = clean_tag(user_name)
    if user_id:
        return f'<a href="tg://user?id={user_id}">{name}</a>'
    return f'<b>{name}</b>'

def is_admin(chat_id, user_id):
    if chat_id > 0:
        return True
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except Exception:
        return False

def parse_duration_to_seconds(duration_str, chat_id=None):
    duration_str = duration_str.lower().strip()
    match_rel = re.search(r'(\d+)\s*(д|день|дня|дней|ч|час|часа|часов|м|мин|минут)', duration_str)
    if match_rel:
        val = int(match_rel.group(1))
        unit = match_rel.group(2)
        if unit in ['д', 'день', 'дня', 'дней']:
            sec = val * 86400
        elif unit in ['ч', 'час', 'часа', 'часов']:
            sec = val * 3600
        elif unit in ['м', 'мин', 'минут']:
            sec = val * 60
        else:
            sec = 0

        if chat_id:
            sett = get_chat_settings(chat_id)
            max_sec = sett['max_days'] * 86400
            if sec > max_sec:
                return max_sec
        return sec

    match_date = re.search(r'(\d{1,2})[\.\/](\d{1,2})(?:[\.\/](\d{2,4}))?', duration_str)
    if match_date:
        day = int(match_date.group(1))
        month = int(match_date.group(2))
        year = int(match_date.group(3)) if match_date.group(3) else datetime.now().year
        if year < 100:
            year += 2000
        try:
            target_dt = datetime(year, month, day, 23, 59, 59)
            now = datetime.now()
            if target_dt < now and not match_date.group(3):
                target_dt = datetime(year + 1, month, day, 23, 59, 59)
            diff = (target_dt - now).total_seconds()
            return max(diff, 0)
        except ValueError:
            pass

    match_words = re.search(r'(\d{1,2})\s+([а-яг-я]+)', duration_str)
    if match_words:
        day = int(match_words.group(1))
        month_str = match_words.group(2)
        if month_str in MONTHS:
            month = MONTHS[month_str]
            year = datetime.now().year
            try:
                target_dt = datetime(year, month, day, 23, 59, 59)
                now = datetime.now()
                if target_dt < now:
                    target_dt = datetime(year + 1, month, day, 23, 59, 59)
                diff = (target_dt - now).total_seconds()
                return max(diff, 0)
            except ValueError:
                pass

    return None

def add_to_history(chat_str, user, duration_text, reason, user_id=None):
    if chat_str not in db['history']:
        db['history'][chat_str] = {}
    clean_user = clean_tag(user)
    if clean_user not in db['history'][chat_str]:
        db['history'][chat_str][clean_user] = []
    entry = {
        'date': time.strftime('%Y-%m-%d %H:%M'),
        'duration': duration_text,
        'reason': reason,
        'user_id': user_id,
    }
    db['history'][chat_str][clean_user].append(entry)

# ---------------------------------------------------------
# ТАЙМЕРИ ТА СПОВІЩЕННЯ
# ---------------------------------------------------------
def schedule_rest_timers(chat_id, user, end_timestamp, target_user_id=None):
    def timer_thread():
        str_chat = str(chat_id)
        reminded = False
        clean_user = clean_tag(user)
        user_link = make_link(clean_user, target_user_id)
        while True:
            now = time.time()
            remaining = end_timestamp - now
            sett = get_chat_settings(chat_id)
            remind_sec = sett.get('remind_minutes', 60) * 60

            if remaining <= 0:
                if str_chat in db['rests'] and clean_user in db['rests'][str_chat] and db['rests'][str_chat][clean_user]['end_time'] == end_timestamp:
                    del db['rests'][str_chat][clean_user]
                    save_data()
                    try:
                        bot.send_message(chat_id, f'⏰ Время реста для {user_link} истекло. Рест автоматически снят!', parse_mode='HTML')
                    except Exception:
                        pass
                    if target_user_id:
                        try:
                            bot.send_message(target_user_id, '🌴 Ваш рест закончился! Пора возвращаться к работе.')
                        except Exception:
                            pass
                break

            if 0 < remaining <= remind_sec and not reminded:
                reminded = True
                mins = int(remind_sec / 60)
                try:
                    bot.send_message(chat_id, f'🔔 <b>Напоминание:</b> Рест у {user_link} закончится через {mins} мин!', parse_mode='HTML')
                except Exception:
                    pass

            time.sleep(min(remaining, 30))

    t = threading.Thread(target=timer_thread)
    t.daemon = True
    t.start()

def restore_timers():
    for str_chat, users in list(db['rests'].items()):
        chat_id = int(str_chat)
        for user, info in list(users.items()):
            end_time = info.get('end_time')
            u_id = info.get('user_id')
            if end_time:
                schedule_rest_timers(chat_id, user, end_time, u_id)

def apply_rest(chat_id, user, duration_text, reason='Не указана', target_user_id=None):
    str_chat = str(chat_id)
    if str_chat not in db['rests']:
        db['rests'][str_chat] = {}
    clean_user = clean_tag(user)
    seconds = parse_duration_to_seconds(duration_text, chat_id)
    end_time = (time.time() + seconds) if seconds else None
    db['rests'][str_chat][clean_user] = {
        'duration': duration_text,
        'reason': reason,
        'end_time': end_time,
        'user_id': target_user_id,
    }
    add_to_history(str_chat, clean_user, duration_text, reason, target_user_id)
    save_data()
    if end_time:
        schedule_rest_timers(chat_id, clean_user, end_time, target_user_id)

# ---------------------------------------------------------
# ОБРОБНИКИ КОМАНД
# ---------------------------------------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    help_text = (
        '🌴 <b>Бот для учета рестов готов к работе!</b>\n\n'
        '👑 <b>Админ-команды:</b>\n'
        '• <code>+рест на 3 д | отпуск</code> — выдать рест\n'
        '• <code>-рест</code> — снять рест\n'
        '• <code>+продлить на 2 д</code> — продлить рест\n'
        '• <code>причина новая причина</code> — изменить причину\n'
        '• <code>/settings</code> — настройки чата\n'
        '• <code>/export</code> — выгрузить CSV-файл истории\n'
        '• <code>отчет</code> — аналитический отчет\n'
        '• <code>логи</code> — история чата\n\n'
        '👤 <b>Для всех:</b>\n'
        '• <code>запрос рест на 2 д</code> — отправить запрос админам\n'
        '• <code>ресты</code> — список активных рестов\n'
        '• <code>мой рест</code> — время до конца реста\n'
        '• <code>топ</code> — статистика чата'
    )
    bot.reply_to(message, help_text, parse_mode='HTML')

@bot.message_handler(commands=['settings'])
def chat_settings_cmd(message):
    chat_id = message.chat.id
    if not is_admin(chat_id, message.from_user.id):
        bot.reply_to(message, '❌ Эта команда доступна только администраторам!')
        return
    sett = get_chat_settings(chat_id)
    text = (
        '⚙️ <b>Настройки бота для этого чата:</b>\n\n'
        f"• Макс. срок реста: <b>{sett['max_days']} дней</b>\n"
        f"• Авто-удаление сообщений тех, кто в ресте: <b>{'Включено' if sett['delete_rest_msg'] else 'Выключено'}</b>\n"
        f"• Часовой пояс: <b>UTC+{sett['timezone_offset']}</b>\n"
        f"• Время напоминания: <b>за {sett['remind_minutes']} мин</b>"
    )
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton('⏳ Лимит дней (14/30/60)', callback_data='set_max_days'),
        InlineKeyboardButton('🗑 Авто-удаление сообщений', callback_data='toggle_del_msg')
    )
    markup.add(
        InlineKeyboardButton('🔔 Напоминание (10мин/1ч/24ч)', callback_data='set_remind_time')
    )
    bot.reply_to(message, text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['export'])
def export_csv(message):
    chat_id = message.chat.id
    str_chat = str(chat_id)
    if not is_admin(chat_id, message.from_user.id):
        return
    if str_chat not in db['history'] or not db['history'][str_chat]:
        bot.reply_to(message, '📊 История рестов пуста, нет данных для экспорта.')
        return

    file_path = f'rests_export_{chat_id}.csv'
    with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['Дата', 'Пользователь', 'Длительность', 'Причина', 'User ID'])
        for u, items in db['history'][str_chat].items():
            for it in items:
                writer.writerow([
                    it.get('date', ''),
                    u,
                    it.get('duration', ''),
                    it.get('reason', ''),
                    it.get('user_id', '')
                ])
    with open(file_path, 'rb') as f:
        bot.send_document(chat_id, f, caption='📊 <b>Полный экспорт истории рестов в CSV</b>', parse_mode='HTML')
    if os.path.exists(file_path):
        os.remove(file_path)

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    global req_counter
    text = message.text.strip() if message.text else ''
    chat_id = message.chat.id
    str_chat = str(chat_id)
    user_id = message.from_user.id

    sett = get_chat_settings(chat_id)
    if sett.get('delete_rest_msg', False) and str_chat in db['rests']:
        u_tag = clean_tag(message.from_user.username or message.from_user.first_name)
        if u_tag in db['rests'][str_chat]:
            try:
                bot.delete_message(chat_id, message.message_id)
                user_link = make_link(u_tag, user_id)
                warn = bot.send_message(chat_id, f'⚠️ {user_link}, вы находитесь в ресте! Ваше сообщение удалено.', parse_mode='HTML')
                threading.Timer(5, lambda: bot.delete_message(chat_id, warn.message_id)).start()
                return
            except Exception:
                pass

    if text.lower().startswith('запрос рест'):
        match = re.search(r'запрос\s+рест\s+(.+)', text, re.IGNORECASE)
        if not match:
            bot.reply_to(message, '❌ Формат: <code>запрос рест на 3 д | причина</code>', parse_mode='HTML')
            return
        req_data = match.group(1).split('|')
        duration_text = req_data[0].strip()
        reason = req_data[1].strip() if len(req_data) > 1 else 'Не указана'
        user_tag = clean_tag(message.from_user.username or message.from_user.first_name)

        req_counter += 1
        req_id = str(req_counter)
        pending_requests[req_id] = {
            'user_tag': user_tag,
            'duration': duration_text,
            'reason': reason,
            'user_id': user_id
        }

        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton('✅ Принять', callback_data=f'app_{req_id}'),
            InlineKeyboardButton('❌ Отклонить', callback_data=f'den_{req_id}')
        )
        markup.add(
            InlineKeyboardButton('🏥 Больничный', callback_data=f'qs_{req_id}_Больничный'),
            InlineKeyboardButton('📚 Учеба', callback_data=f'qs_{req_id}_Учеба'),
            InlineKeyboardButton('🌴 Отпуск', callback_data=f'qs_{req_id}_Отпуск')
        )

        user_link = make_link(user_tag, user_id)
        bot.reply_to(
            message,
            f'📩 <b>Запрос на рест от:</b> {user_link}\n⏱ <b>Срок:</b> {duration_text}\n📝 <b>Причина:</b> {reason}',
            reply_markup=markup,
            parse_mode='HTML'
        )
        return

    if text.lower().startswith('+рест'):
        if not is_admin(chat_id, user_id):
            bot.reply_to(message, '❌ Эта команда доступна только администраторам!')
            return
        target_user = None
        target_user_id = None
        raw_args = ''

        if message.reply_to_message:
            u = message.reply_to_message.from_user
            target_user = clean_tag(u.username or u.first_name)
            target_user_id = u.id
            m = re.search(r'\+рест\s*(.*)', text, re.IGNORECASE)
            if m:
                raw_args = m.group(1).strip()
        else:
            m = re.search(r'\+рест\s+@?(\w+)\s*(.*)', text, re.IGNORECASE)
            if m:
                target_user = clean_tag(m.group(1))
                raw_args = m.group(2).strip()

        if target_user and raw_args:
            parts = raw_args.split('|')
            duration_text = parts[0].strip()
            reason = parts[1].strip() if len(parts) > 1 else 'Не указана'
            apply_rest(chat_id, target_user, duration_text, reason, target_user_id)
            user_link = make_link(target_user, target_user_id)
            bot.reply_to(message, f'✅ Рест для {user_link} добавлен!\n⏱ Срок: {duration_text}\n📝 Причина: {reason}', parse_mode='HTML')
        else:
            bot.reply_to(message, '❌ Ошибка! Формат: <code>+рест на 3 д | отпуск</code>', parse_mode='HTML')

    elif text.lower().startswith('+продлить'):
        if not is_admin(chat_id, user_id):
            return
        target_user = None
        target_user_id = None
        add_text = ''
        if message.reply_to_message:
            u = message.reply_to_message.from_user
            target_user = clean_tag(u.username or u.first_name)
            target_user_id = u.id
            m = re.search(r'\+продлить\s+(.+)', text, re.IGNORECASE)
            if m:
                add_text = m.group(1).strip()
        else:
            m = re.search(r'\+продлить\s+@?(\w+)\s+(.+)', text, re.IGNORECASE)
            if m:
                target_user = clean_tag(m.group(1))
                add_text = m.group(2).strip()

        if target_user and add_text and str_chat in db['rests'] and target_user in db['rests'][str_chat]:
            add_sec = parse_duration_to_seconds(add_text, chat_id)
            if add_sec:
                info = db['rests'][str_chat][target_user]
                info['end_time'] = (info['end_time'] + add_sec) if info.get('end_time') else (time.time() + add_sec)
                info['duration'] += f' (+{add_text})'
                if not target_user_id:
                    target_user_id = info.get('user_id')
                save_data()
                schedule_rest_timers(chat_id, target_user, info['end_time'], target_user_id)
                user_link = make_link(target_user, target_user_id)
                bot.reply_to(message, f'✅ Рест для {user_link} успешно продлен на {add_text}!', parse_mode='HTML')
            else:
                bot.reply_to(message, '❌ Не удалось распознать прибавляемое время.')

    elif text.lower().startswith('причина'):
        if not is_admin(chat_id, user_id):
            return
        target_user = None
        target_user_id = None
        new_reason = ''
        if message.reply_to_message:
            u = message.reply_to_message.from_user
            target_user = clean_tag(u.username or u.first_name)
            target_user_id = u.id
            m = re.search(r'причина\s+(.+)', text, re.IGNORECASE)
            if m:
                new_reason = m.group(1).strip()
        else:
            m = re.search(r'причина\s+@?(\w+)\s+(.+)', text, re.IGNORECASE)
            if m:
                target_user = clean_tag(m.group(1))
                new_reason = m.group(2).strip()

        if target_user and new_reason and str_chat in db['rests'] and target_user in db['rests'][str_chat]:
            db['rests'][str_chat][target_user]['reason'] = new_reason
            if not target_user_id:
                target_user_id = db['rests'][str_chat][target_user].get('user_id')
            save_data()
            user_link = make_link(target_user, target_user_id)
            bot.reply_to(message, f'📝 Причина реста для {user_link} изменена на: <b>{new_reason}</b>', parse_mode='HTML')

    elif text.lower().startswith('-рест'):
        if not is_admin(chat_id, user_id):
            return
        target_user = None
        target_user_id = None
        if message.reply_to_message:
            u = message.reply_to_message.from_user
            target_user = clean_tag(u.username or u.first_name)
            target_user_id = u.id
        else:
            m = re.search(r'-рест\s+@?(\w+)', text, re.IGNORECASE)
            if m:
                target_user = clean_tag(m.group(1))

        if target_user and str_chat in db['rests']:
            if target_user in db['rests'][str_chat]:
                if not target_user_id:
                    target_user_id = db['rests'][str_chat][target_user].get('user_id')
                del db['rests'][str_chat][target_user]
                save_data()
                user_link = make_link(target_user, target_user_id)
                bot.reply_to(message, f'🗑 Рест с {user_link} успешно снят.', parse_mode='HTML')

    elif text.lower() in ['ресты', 'рест']:
        if str_chat not in db['rests'] or not db['rests'][str_chat]:
            bot.reply_to(message, '🌴 В данный момент никто не находится в ресте.')
        else:
            resp = '📋 <b>Список активных рестов:</b>\n\n'
            for u, info in db['rests'][str_chat].items():
                reason_text = info.get('reason', 'Не указана')
                u_link = make_link(u, info.get('user_id'))
                resp += f"• {u_link} — {info['duration']} (Причина: {reason_text})\n"
            bot.reply_to(message, resp, parse_mode='HTML')

    elif text.lower() == 'мой рест':
        user_tag = clean_tag(message.from_user.username or message.from_user.first_name)
        if str_chat in db['rests'] and user_tag in db['rests'][str_chat]:
            info = db['rests'][str_chat][user_tag]
            rem_str = ''
            if info.get('end_time'):
                rem = int(info['end_time'] - time.time())
                if rem > 0:
                    hours, remainder = divmod(rem, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    rem_str = f'\n⏳ Осталось: {hours} ч {minutes} мин'
            bot.reply_to(message, f"🌴 <b>Ваш рест:</b> {info['duration']}\n📝 <b>Причина:</b> {info['reason']}{rem_str}", parse_mode='HTML')

    elif text.lower() == 'отчет':
        if not is_admin(chat_id, user_id):
            return
        if str_chat in db['history'] and db['history'][str_chat]:
            total_count = 0
            reasons_summary = {}
            for u, items in db['history'][str_chat].items():
                total_count += len(items)
                for it in items:
                    reas = it.get('reason', 'Другое')
                    reasons_summary[reas] = reasons_summary.get(reas, 0) + 1

            resp = (
                '📈 <b>Аналитический отчет по рестам:</b>\n\n'
                f'• Всего рестов зафиксировано: <b>{total_count}</b>\n'
                f'• Уникальных участников: <b>{len(db["history"][str_chat])}</b>\n\n'
                '📊 <b>Популярные причины:</b>\n'
            )
            for r_name, r_cnt in sorted(reasons_summary.items(), key=lambda x: x[1], reverse=True)[:5]:
                resp += f'• {r_name}: {r_cnt} раз(а)\n'
            bot.reply_to(message, resp, parse_mode='HTML')
        else:
            bot.reply_to(message, '📊 Нет данных для формирования отчета.')

    elif text.lower() in ['топ', 'статистика']:
        if str_chat in db['history'] and db['history'][str_chat]:
            stats = {}
            user_ids = {}
            for u, items in db['history'][str_chat].items():
                stats[u] = len(items)
                for it in items:
                    if it.get('user_id'):
                        user_ids[u] = it.get('user_id')

            sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
            resp = '🏆 <b>Топ по количеству рестов:</b>\n\n'
            for idx, (u, count) in enumerate(sorted_stats[:10], 1):
                u_link = make_link(u, user_ids.get(u))
                resp += f'{idx}. {u_link} — {count} раз(а)\n'
            bot.reply_to(message, resp, parse_mode='HTML')

    elif text.lower() == 'логи':
        if not is_admin(chat_id, user_id):
            return
        if str_chat in db['history'] and db['history'][str_chat]:
            resp = '📜 <b>Последние ресты в чате:</b>\n\n'
            all_logs = []
            for u, items in db['history'][str_chat].items():
                for it in items:
                    all_logs.append((it['date'], u, it['duration'], it['reason'], it.get('user_id')))
            all_logs.sort(key=lambda x: x[0], reverse=True)
            for date, u, dur, reas, u_id in all_logs[:10]:
                u_link = make_link(u, u_id)
                resp += f'• {date} — {u_link}: {dur} ({reas})\n'
            bot.reply_to(message, resp, parse_mode='HTML')

# ---------------------------------------------------------
# ОБРОБКА ІНТЕРАКТИВНИХ КНОПОК
# ---------------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    if call.data == 'set_max_days':
        if not is_admin(chat_id, user_id):
            return
        sett = get_chat_settings(chat_id)
        opts = [14, 30, 60]
        next_opt = opts[(opts.index(sett['max_days']) + 1) % len(opts)]
        sett['max_days'] = next_opt
        save_data()
        bot.answer_callback_query(call.id, f'✅ Максимальный срок изменен на {next_opt} дней!')
        chat_settings_cmd(call.message)

    elif call.data == 'toggle_del_msg':
        if not is_admin(chat_id, user_id):
            return
        sett = get_chat_settings(chat_id)
        sett['delete_rest_msg'] = not sett['delete_rest_msg']
        save_data()
        bot.answer_callback_query(call.id, f"✅ Авто-удаление: {'Включено' if sett['delete_rest_msg'] else 'Выключено'}")
        chat_settings_cmd(call.message)

    elif call.data == 'set_remind_time':
        if not is_admin(chat_id, user_id):
            return
        sett = get_chat_settings(chat_id)
        opts = [10, 60, 1440]
        next_opt = opts[(opts.index(sett.get('remind_minutes', 60)) + 1) % len(opts)]
        sett['remind_minutes'] = next_opt
        save_data()
        bot.answer_callback_query(call.id, f'✅ Напоминание установлено за {next_opt} мин!')
        chat_settings_cmd(call.message)

    elif call.data.startswith(('app_', 'qs_')):
        if not is_admin(chat_id, user_id):
            bot.answer_callback_query(call.id, '❌ Принимать решения могут только админы!', show_alert=True)
            return

        parts = call.data.split('_')
        req_id = parts[1]
        req_info = pending_requests.get(req_id)

        if not req_info:
            bot.answer_callback_query(call.id, '❌ Запрос устарел или не найден!', show_alert=True)
            return

        target_user = req_info['user_tag']
        duration_text = req_info['duration']
        reason = parts[2] if len(parts) > 2 else req_info['reason']
        target_user_id = req_info['user_id']

        apply_rest(chat_id, target_user, duration_text, reason, target_user_id)
        admin_link = make_link(call.from_user.username or call.from_user.first_name, user_id)
        user_link = make_link(target_user, target_user_id)
        
        bot.edit_message_text(
            f'✅ <b>Запрос принят админом {admin_link}!</b>\n'
            f'Пользователю {user_link} выдан рест на {duration_text} (Причина: {reason}).',
            chat_id=chat_id,
            message_id=call.message.message_id,
            parse_mode='HTML'
        )

    elif call.data.startswith('den_'):
        if not is_admin(chat_id, user_id):
            return
        req_id = call.data.split('_')[1]
        req_info = pending_requests.get(req_id)
        target_user = req_info['user_tag'] if req_info else 'Пользователь'
        user_id_val = req_info['user_id'] if req_info else None
        user_link = make_link(target_user, user_id_val)
        bot.edit_message_text(
            f'❌ <b>Запрос от {user_link} отклонен.</b>',
            chat_id=chat_id,
            message_id=call.message.message_id,
            parse_mode='HTML'
        )

# ---------------------------------------------------------
# ЗАПУСК
# ---------------------------------------------------------
restore_timers()
keep_alive()  # Запускаємо веб-сервер для пингу

print('Бот запущен...')
bot.infinity_polling()
