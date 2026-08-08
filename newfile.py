import csv
from datetime import datetime, timedelta
import json
import os
import random
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
# НАСТРОЙКИ БОТА И БАЗЫ ДАННЫХ
# ---------------------------------------------------------
TOKEN = '8963495889:AAFFwRPYDVj1gqwz879G7HkZgpgXDoGt87g'
bot = telebot.TeleBot(TOKEN)

# ID вашего приватного канала для авто-бекапов
DB_CHANNEL_ID = int(os.environ.get('DB_CHANNEL_ID', -1004334874700))
DATA_FILE = 'rests_data.json'

# Юзернейм администратора/разработчика для секретного промокода
ADMIN_USERNAME = 'ukrgorilka'

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

# Доступные значки в магазине с разнообразными ценами
BADGES = {
    'badge_star': {'name': 'Звездочка', 'emoji': '🌟', 'price': 100},
    'badge_paw': {'name': 'Лапка Котика', 'emoji': '🐾', 'price': 200},
    'badge_heart': {'name': 'Сердечко', 'emoji': '💖', 'price': 200},
    'badge_lightning': {'name': 'Молния', 'emoji': '⚡️', 'price': 300},
    'badge_crown': {'name': 'Корона', 'emoji': '👑', 'price': 300},
    'badge_diamond': {'name': 'Бриллиант', 'emoji': '💎', 'price': 500},
    'badge_rocket': {'name': 'Ракета', 'emoji': '🚀', 'price': 700},
    'badge_unicorn': {'name': 'Единорог', 'emoji': '🦄', 'price': 1000},
}

# --- ВСЕГДА АКТИВНЫЕ ТРИГГЕРЫ (Работают даже с Ня-Пассом) ---
ALWAYS_ACTIVE_PATTERNS = {
    # --- УПОМИНАНИЕ МАМЫ (ПОЗИТИВНЫЙ ОТВЕТ) ---
    r'\b(твоя\s+мамка|твоя\s+мама|твою\s+маму|твоя\s+мать|мамулька|маман)\b': [
        'Твоя мама самая лучшая и прекрасная! 🌸💖',
        'Мама — это святое! Давай только с любовью и уважением ✨🥰',
        'Твоя мама чудесный человек! 💐',
        'Мамочке привет и самого доброго дня! 🥞☕️',
        'Передай маме, что она замечательная! 🥐🌷'
    ],

    # --- ОХАЁ / ПРИВЕТСТВИЯ ---
    r'\b(охае|охаё|охайо|охаешечки|охаёшечки|охайоо|охаее)\b': [
        'Охаё! Анимешники в чате! 🎌🌸',
        'Охаёшечки! Доброго утречка/днечка! ☀️🍵',
        'Охаё! А кофе/чай уже заварен? ☕️✨',
        'Охаё-о-о! Свеж и готов к работе? 🥪😊',
        'Охаё! Не забудь позавтракать! 🥞🥐'
    ],

    # --- АНИМЕ ФРАЗЫ И СЛОВА ---
    r'\b(даттебайо|даттебае|даттебаё)\b': [
        'Наруто, ты ли это?! 🍥🦊',
        'Даттебаё! Мой путь ниндзя — следить за рестами! 🥷✨',
        'Стану Хокаге этого чата, даттебаё! 🍃👑',
        'Расенган в твою ленту! 🌀💥',
        'Главное — никогда не сдаваться, даттебаё! 🔥💪'
    ],
    r'\b(кавай|кавайный|кавайность|кавайка)\b': [
        'Кавайность этого сообщения зашкаливает! 🥺✨',
        'Милота спасает этот чат! 🌸ฅ^•ﻌ•^ฅ',
        'Ну прямо милота 100/10! 🐱💖',
        'Осторожно, повышенный уровень кавая! ⚠️🎀',
        'Спасибо, ты тоже очень кавайный! 🥰🐾'
    ],
    r'\b(ня|няшка|някать|нян)\b': [
        'Ня! 🐱🐾',
        'Котодевочки одобряют этот чат! 🐾✨',
        'Ня-ня-ня, всем позитивного дня! 🥐☕️',
        'Кто-то сказал «ня»? Пора гладить котиков! 🐈',
        'Някать разрешено, но рест по расписанию! 🌴😉'
    ],
    r'\b(аригато|аригатоо|аригато gozaimasu)\b': [
        'Доитасимасите! (Всегда пожалуйста!) 🙇‍♂️✨',
        'Не за что, обращайся! 🤝🌸',
        'Всегда рад помочь! 🤖❤️',
        'Аригато и тебе за хорошее настроение! 🌟',
        'Пожалуйста! Нарушать правила все равно нельзя 🤓☝️'
    ],
    r'\b(ямете|ямете кудасай|яметее)\b': [
        'ЯМЕТЕ КУДАСАЙ!! 😱💥',
        'А вот тут остановись, а то бан прилетит! 🛑🙈',
        'Ой-ой-ой, что тут происходит?! 😳🍿',
        'Крик души услышан! 📢🤯',
        'Спокойствие! Всё под контролем! 🧘‍♂️'
    ],
    r'\b(десу|десс)\b': [
        'Да, именно так, десу! 🤓✨',
        'Дез-дез-дез! 🌸',
        'Утверждение принято, десу! 📜✍️',
        'И добавить нечего, десу! 😼',
        'Самый правильный ответ, десу! 💯'
    ]
}

# --- МАТЫ И СЛОВО КОЧ (Отключаются у тех, у кого активен Ня-Пасс) ---
MUTABLE_BAD_WORDS_PATTERNS = {
    # --- СЛОВО КОЧ ---
    r'\b(коч|кочч)\b': [
        'Это плохо! 🛑',
        'Давай без таких слов! 🤫',
        'Осуждаю подобные речи 🤓☝️',
        'Давай лучше о чем-то хорошем! 🌸',
        'Не стоит такое писать 🛑'
    ],
    
    # --- РАСШИРЕННЫЙ СПИСОК МАТОВ И ОСКОРБЛЕНИЙ ---
    r'\b(долбоеб|долбаеб|долбаёб|далбоеб|далбаеб|далбаёб|долбоёб|долбоеб|долбоящер|долбень|еблан|ебланище|ебланчик)\b': [
        'Давай без личных оскорблений, дружище! 🤝⚠️',
        'А вот обижать людей нельзя! 🥺🚫',
        'Доброта спасет мир, а ты ругаешься 🌸🕊',
        'А сам-то идеальный? 😜',
        'Давай жить дружно! 🐱💬',
        'Словарный запас подкачал, давай культурнее! 📚'
    ],
    r'\b(даун|даунич|дауненок|даунёнок|аутист|аутизм|дебил|дебилоид|имбецил|кретин|олигофрен|дауны)\b': [
        'Не стоит диагнозами бросаться, будь добрее! 🧠❤️',
        'Уважение к собеседнику выходит из чата... 🚶‍♂️💔',
        'Давай без ярлыков и оскорблений! 🛑🤐',
        'Эрудиция на высоте, а вот вежливость подкачала 📉📚',
        'Кто обозвал, тот сам так называется! 😜✨'
    ],
    r'\b(залупа|залупыш|залупоглаз|залупин|залупистый|залупка)\b': [
        'Ого, какие изысканные выражения из подворотни! 🏰💩',
        'Фильтруй базар, а то фильтр забьется! 🧼💥',
        'Давай общаться как цивилизованные люди! 🎩✨',
        'Фу такими словами кидаться, иди рот ополосни! 🚰🧼',
        'Минус 50 очков за дерзость! 🧙‍♂️🧹'
    ],
    r'\b(сосать|соси|отсоси|соснуть|сосешь|сосёшь|сосиска|отсосино)\b': [
        'Сосать можно только чупа-чупс! 🍭😋',
        'Кажется, кому-то не хватает сладкого в жизни! 🍫🍬',
        'Рот свой держи на замке, а не предлагай глупости! 🤐🔑',
        'Детский сад, группа «Солнышко» объявляет тихий час! 👶💤',
        'Давай без этих взрослых фантазий! 🛑🙈'
    ],
    r'\b(трахнул|трахать|вытрахал|втрахал|трахни|трахну|вытрахать|затрахал)\b': [
        'Трахать тут можно только мозги админу, но не советую! 🧠⚡️',
        'Какой грозный казанова нашелся! 🕶😏',
        'Попридержи коней, герой-любовник! 🐎🛑',
        'Режиссер, выключите у него взрослый канал! 📺❌',
        'Давай без пошлостей в общем чате! 🔞🚫'
    ],
    r'\b(шлюха|шлюшка|шлюховатый|проститутка|шалава|шмара|лярва|стерва|шлюхи)\b': [
        'Словарь негодяя активирован? Фильтруй базар! 🧼💥',
        'Уважение к людям вышло из чата... 🚶‍♂️💔',
        'Не смей так называть людей, уважай окружающих! 🙅‍♂️🔥',
        'За такие слова можно и в бан улететь! ✈️🔨',
        'Слишком много грязи, иди помойся! 🚿🧼'
    ],
    r'\b(мудак|мудило|гандон|презерватив|уебок|уёбок|уебан|уебище|уёбище|выблядок|мразь|сука|сучара)\b': [
        'Уровень токсичности зашкаливает! ☣️😱',
        'Давай без тяжелой артиллерии и оскорблений! 💣🛑',
        'Столько желчи, чашечку чая для успокоения? 🍵🧘‍♂️',
        'Кто-то забыл принять таблетки от агрессии! 💊😉',
        'Культура речи на нуле, пересдача осенью! 📚❌'
    ],
    r'\b(пизденыш|пиздёныш|говноед|засранец|падла|гад|пидор|пидорас|пидарас|чмо|хуесос|хуесосина)\b': [
        'Ого, какие глубокие познания ругательств! 🧹😱',
        'Давай общаться как цивилизованные люди! 🎩✨',
        'Минус 50 очков за дерзость! 🧙‍♂️🧹',
        'За такие слова в приличном доме чаем не угощают! ☕️❌'
    ],
    r'\b(блять|бля|блеать|блят|бляя|блятьь|блядь|блядина)\b': [
        'Вообще-то матюкаться нельзя 🤓☝️',
        'Рот с мылом помыть? 🧼🤐',
        'За такое и в угол поставить могут! 📐👵',
        'Культурнее, пожалуйста, мы же в приличном обществе! 🎩✨',
        'Словарный запас покинул чат... 📉'
    ],
    r'\b(нах|нахуй|похуй|нахуя|нахуйй|похую|нахрен|нафиг)\b': [
        'Маршрут перестроен: туда мы точно не идем 🗺❌',
        'GPS-навигатор отклонил ваш запрос! 🛑🧭',
        'Вектор движения выбран крайне некультурно! 📐🧭',
        'Фильтруй базар, а то фильтр забьется! 🧼💥'
    ],
    r'\b(пиздец|пизда|пиздос|пиздей|пиздато|пиздеть|пиздець|хуй|хуя|хуи|хуйня|хуево|заебись)\b': [
        'Ого, какие мы громкие слова знаем! 📢🤯',
        'Словарь Даля нервно курит в сторонке... 📚🚬',
        'Давай переведём это на интеллигентный язык? 🎩📜',
        'Спокойствие, только спокойствие! 🎈'
    ],
    r'\b(ахуеть|охуеть|охуел|ахуел|ебать|ебаться|ебаный|ёбаный|ебнутый|ебанутый)\b': [
        'Энергию бы да в полезное русло! ⚡️🚜',
        'Не выражайся, а то клавиатура покраснеет! ⌨️😳',
        'Опять эмоциональный взрыв? 💥🤯',
        'Ты бы лучше так правила чата учил! 📖🤓'
    ]
}

pending_requests = {}
req_counter = 0

# ---------------------------------------------------------
# БЛОК РАБОТЫ С ДАННЫМИ (JSON + TELEGRAM BACKUP)
# ---------------------------------------------------------
def load_data():
    """Загружает свежий бекап из Telegram-канала, если локальный файл отсутствует или устарел"""
    data = {'rests': {}, 'history': {}, 'settings': {}, 'economy': {}}
    
    try:
        if DB_CHANNEL_ID:
            chat = bot.get_chat(DB_CHANNEL_ID)
            if chat and chat.pinned_message and chat.pinned_message.document:
                file_info = bot.get_file(chat.pinned_message.document.file_id)
                downloaded_file = bot.download_file(file_info.file_path)
                with open(DATA_FILE, 'wb') as new_file:
                    new_file.write(downloaded_file)
                print("Успешно загружен бекап из закрепа в Telegram-канале!")
    except Exception as e:
        print(f"Инфо: Загрузка из Telegram пропущена или возникла ошибка: {e}")

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
                if 'economy' not in data:
                    data['economy'] = {}
                return data
        except Exception as e:
            print(f'Ошибка чтения файла: {e}')

    return data

def save_data():
    """Сохраняет JSON локально и отправляет + закрепляет обновленный файл в канале-базе"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=4)
        
        if DB_CHANNEL_ID:
            with open(DATA_FILE, 'rb') as f:
                msg = bot.send_document(DB_CHANNEL_ID, f, caption="💾 Auto-backup rests_data.json")
                try:
                    bot.pin_chat_message(DB_CHANNEL_ID, msg.message_id, disable_notification=True)
                except Exception:
                    pass
    except Exception as e:
        print(f"Ошибка при сохранении бекапа в Telegram: {e}")

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

# --- ФУНКЦИИ ВАЛЮТЫ И ЭКОНОМИКИ (НЯ-КОИНЫ 🪙) ---
def get_user_econ(chat_id, user_tag):
    str_chat = str(chat_id)
    clean_u = clean_tag(user_tag)
    if 'economy' not in db:
        db['economy'] = {}
    if str_chat not in db['economy']:
        db['economy'][str_chat] = {}
    if clean_u not in db['economy'][str_chat]:
        db['economy'][str_chat][clean_u] = {
            'balance': 50,           # Стартовый баланс
            'last_hourly': 0,        # Timestamp последнего часового сбора
            'nya_pass_until': 0,     # Timestamp окончания действия Ня-Пасса
            'badge': None            # Купленный смайлик/значок
        }
        save_data()
    return db['economy'][str_chat][clean_u]

def add_coins(chat_id, user_tag, amount):
    str_chat = str(chat_id)
    clean_u = clean_tag(user_tag)
    user_data = get_user_econ(chat_id, clean_u)
    user_data['balance'] += amount
    save_data()
    return user_data['balance']

def is_nya_pass_active(chat_id, user_tag):
    """Проверяет, активен ли у пользователя Ня-Пасс от мата"""
    user_data = get_user_econ(chat_id, user_tag)
    until = user_data.get('nya_pass_until', 0)
    return time.time() < until

# ---------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ПАРСИНГА И ВСЕХ ПОЛЬЗОВАТЕЛЕЙ
# ---------------------------------------------------------
def clean_tag(user_str):
    if not user_str:
        return 'Пользователь'
    return user_str.replace('@', '').strip()

def make_link(chat_id, user_name, user_id=None):
    """Генерирует ссылку на юзера с учетом купленных кастомных смайлов"""
    name = clean_tag(user_name)
    badge_str = ""
    if chat_id:
        user_econ = get_user_econ(chat_id, name)
        if user_econ.get('badge'):
            badge_str = f" [{user_econ['badge']}]"

    if user_id:
        return f'<a href="tg://user?id={user_id}">{name}</a>{badge_str}'
    return f'<b>{name}</b>{badge_str}'

def is_admin(chat_id, user_id):
    if chat_id > 0:
        return True
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except Exception:
        return False

def parse_target_and_args(message, cmd_prefix):
    text = message.text.strip() if message.text else ''
    target_user = None
    target_user_id = None
    raw_args = ''

    # Вариант 1: Ответ на сообщение (Reply)
    if message.reply_to_message:
        u = message.reply_to_message.from_user
        target_user = clean_tag(u.username or u.first_name)
        target_user_id = u.id
        m = re.search(f'{re.escape(cmd_prefix)}\\s*(.*)', text, re.IGNORECASE)
        if m:
            raw_args = m.group(1).strip()
        return target_user, target_user_id, raw_args

    m_body = re.search(f'{re.escape(cmd_prefix)}\\s+(.+)', text, re.IGNORECASE)
    if not m_body:
        return None, None, ''

    body = m_body.group(1).strip()

    # Вариант 2: Юзернейм через @
    m_tag = re.search(r'@(\w+)', body)
    if m_tag:
        target_user = clean_tag(m_tag.group(1))
        raw_args = body.replace(m_tag.group(0), '').strip()
        return target_user, None, raw_args

    # Вариант 3: Имя через |
    if '|' in body:
        parts = body.split('|')
        possible_name = parts[-1].strip()
        if len(possible_name.split()) == 1:
            target_user = clean_tag(possible_name)
            raw_args = '|'.join(parts[:-1]).strip()
            return target_user, None, raw_args

    words = body.split()
    if len(words) > 1:
        target_user = clean_tag(words[-1])
        raw_args = ' '.join(words[:-1]).strip()
        return target_user, None, raw_args

    return None, None, ''

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
# ТАЙМЕРЫ И УВЕДОМЛЕНИЯ
# ---------------------------------------------------------
def schedule_rest_timers(chat_id, user, end_timestamp, target_user_id=None):
    def timer_thread():
        str_chat = str(chat_id)
        reminded = False
        clean_user = clean_tag(user)
        user_link = make_link(chat_id, clean_user, target_user_id)
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
    
    # Награждаем 150 Ня-коинами за взятие реста
    add_coins(chat_id, clean_user, 150)
    
    save_data()
    if end_time:
        schedule_rest_timers(chat_id, clean_user, end_time, target_user_id)

# ---------------------------------------------------------
# ПРИВЕТСТВИЕ И ПРОЩАНИЕ (ВХОД / ВЫХОД ИЗ ЧАТА)
# ---------------------------------------------------------
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_members(message):
    for member in message.new_chat_members:
        user_link = make_link(message.chat.id, member.username or member.first_name, member.id)
        
        # Начисляем приветственный бонус
        add_coins(message.chat.id, member.username or member.first_name, 50)
        
        welcome_text = (
            f"🎉 <b>Добро пожаловать в чат, {user_link}!</b>\n\n"
            f"🌸 Мы очень рады тебя видеть!\n"
            f"🪙 Тебе начислен приветственный бонус: <b>50 Ня-коинов</b>!\n\n"
            f"💡 Используй <code>/help</code> или <code>/start</code>, чтобы узнать все возможности бота."
        )
        bot.send_message(message.chat.id, welcome_text, parse_mode='HTML')

@bot.message_handler(content_types=['left_chat_member'])
def goodbye_left_member(message):
    member = message.left_chat_member
    user_link = make_link(message.chat.id, member.username or member.first_name, member.id)
    
    farewell_text = f"👋 <b>{user_link}</b> покинул(а) наш чат. Пожелаем удачи! 🌸"
    bot.send_message(message.chat.id, farewell_text, parse_mode='HTML')

# ---------------------------------------------------------
# ОБРАБОТЧИКИ КОМАНД И ПОЛНОЕ ОПИСАНИЕ БОТА
# ---------------------------------------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    help_text = (
        '🤖 <b>ПОЛНОЕ РУКОВОДСТВО И ВОЗМОЖНОСТИ БОТА</b>\n\n'
        '🌴 <b>1. СИСТЕМА УЧЕТА РЕСТОВ (ОТПУСКОВ):</b>\n'
        '• <code>+рест [срок] | [причина] [юзер]</code> — выдать рест пользователю (например: <code>+рест на 3 д | отпуск vorthon</code> или ответом на сообщение).\n'
        '• <code>-рест [юзер]</code> — снять рест с участника.\n'
        '• <code>+продлить [срок] [юзер]</code> — продлить действующий рест.\n'
        '• <code>причина [юзер] [новая причина]</code> — изменить причину реста.\n'
        '• <code>запрос рест [срок] | [причина]</code> — отправить запрос на рест администраторам чата.\n'
        '• <code>ресты</code> — список всех людей, находящихся в ресте сейчас.\n'
        '• <code>мой рест</code> — проверить оставшееся время своего реста.\n'
        '• <code>топ</code> / <code>статистика</code> — статистика чата по количеству рестов.\n'
        '• <code>отчет</code> / <code>логи</code> — подробный аналитический отчет и история.\n\n'
        
        '🪙 <b>2. ВНУТРЕННЯЯ ВАЛЮТА (НЯ-КОИНЫ):</b>\n'
        '• <code>бонус</code> / <code>/bonus</code> / <code>коин</code> — получать от 1 до 100 Ня-коинов КАЖДЫЙ ЧАС.\n'
        '• <code>баланс</code> / <code>/balance</code> — узнать свой баланс и статус.\n'
        '• <code>перевод @username [сумма]</code> — перевести коины другу.\n'
        '• <code>промокод [код]</code> — ввести секретный промокод.\n'
        '• <code>богачи</code> / <code>топ коинов</code> — рейтинг самых богатых участников.\n'
        '• <i>Награда за рест:</i> За каждый оформленный рест бот автоматический начисляeт <b>+150 Ня-коинов</b>!\n\n'

        '🏪 <b>3. ЛАВКА, СМАЙЛИКИ И НЯ-ПАСС:</b>\n'
        '• <code>магазин</code> / <code>лавка</code> — открыть магазин.\n'
        '• 🎟 <b>Ня-Пасс от мата (500 🪙)</b> — покупается на 7 дней. Бот перестает реагировать на ваши матерные слова и слово "коч".\n'
        '• 👑 <b>Пассы на Смайлики и Значки (100-1000 🪙)</b> — украшают ваше имя значками в списке рестов и топах!\n\n'

        '💬 <b>4. ИНТЕРАКТИВ И АВТО-ОТВЕТЧИК:</b>\n'
        '• <b>Приветствия и прощания:</b> Бот автоматически встречает новых участников бонусом и провожает ушедших.\n'
        '• <b>Реакции на слова:</b>\n'
        '  — При упоминании мамы ("твоя мама", "твоя мамка") бот отвечает добрыми комплиментами!\n'
        '  — Реакция на аниме фразы ("охаё", "ня", "кавай", "даттебаё", "аригато", "ямете", "десу").\n'
        '  — Фильтр мата и оскорблений (залупа, даун, блять и др.).\n\n'

        '⚙️ <b>5. НАСТРОЙКИ ЧАТА (для Админов):</b>\n'
        '• <code>/settings</code> — меню ограничений, лимитов дней и авто-удаления сообщений от участников в ресте.\n'
        '• <code>/export</code> — выгрузка всей истории рестов в файле CSV.'
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
    user_username = (message.from_user.username or '').lower()
    user_tag = clean_tag(message.from_user.username or message.from_user.first_name)
    text_lower = text.lower()

    # 1. ПРОВЕРКА ВСЕГДА АКТИВНЫХ СЛОВ (Мама, Охаё, Аниме, Кавай)
    triggered = False
    for pattern, responses in ALWAYS_ACTIVE_PATTERNS.items():
        if re.search(pattern, text_lower, re.IGNORECASE):
            bot.reply_to(message, random.choice(responses))
            triggered = True
            break

    # 2. ПРОВЕРКА НА МАТ И СЛОВО КОЧ (Срабатывает ТОЛЬКО если НЕТ Ня-Пасса)
    if not triggered and not is_nya_pass_active(chat_id, user_tag):
        for pattern, responses in MUTABLE_BAD_WORDS_PATTERNS.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                bot.reply_to(message, random.choice(responses))
                break

    # --- ПРОВЕРКА РЕСТА И АВТО-УДАЛЕНИЯ ---
    sett = get_chat_settings(chat_id)
    if sett.get('delete_rest_msg', False) and str_chat in db['rests']:
        if user_tag in db['rests'][str_chat]:
            try:
                bot.delete_message(chat_id, message.message_id)
                user_link = make_link(chat_id, user_tag, user_id)
                warn = bot.send_message(chat_id, f'⚠️ {user_link}, вы находитесь в ресте! Ваше сообщение удалено.', parse_mode='HTML')
                threading.Timer(5, lambda: bot.delete_message(chat_id, warn.message_id)).start()
                return
            except Exception:
                pass

    # --- БЛОК НЯ-КОИНОВ И ЛАВКИ ---
    if text_lower in ['баланс', '/balance', 'коины', 'ня-коины']:
        econ = get_user_econ(chat_id, user_tag)
        
        pass_str = ""
        if is_nya_pass_active(chat_id, user_tag):
            rem_sec = int(econ['nya_pass_until'] - time.time())
            days = rem_sec // 86400
            hours = (rem_sec % 86400) // 3600
            pass_str = f"\n🎟 <b>Ня-Пасс (Игнор мата):</b> Активен еще {days}д {hours}ч"
        
        badge_str = f"\n🏷 Значок профиля: {econ['badge']}" if econ.get('badge') else "\n🏷 Значок профиля: Отсутствует"

        bot.reply_to(
            message,
            f"🪙 <b>Кошелек пользователя {make_link(chat_id, user_tag, user_id)}:</b>\n"
            f"• Баланс: <b>{econ['balance']} Ня-коинов 🪙</b>{pass_str}{badge_str}",
            parse_mode='HTML'
        )
        return

    elif text_lower in ['бонус', '/bonus', 'коин', 'собрать']:
        econ = get_user_econ(chat_id, user_tag)
        now_ts = time.time()
        # 1 час = 3600 секунд
        if now_ts - econ.get('last_hourly', 0) >= 3600:
            reward = random.randint(1, 100)
            econ['balance'] += reward
            econ['last_hourly'] = now_ts
            save_data()
            bot.reply_to(message, f"🎲 Вы собрали: <b>+{reward} Ня-коинов 🪙</b>!\nТекущий баланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
        else:
            left_sec = 3600 - (now_ts - econ.get('last_hourly', 0))
            minutes = int(left_sec // 60)
            seconds = int(left_sec % 60)
            bot.reply_to(message, f"⏳ Можно собирать коины каждый час! Следующий сбор через: <b>{minutes} мин {seconds} сек</b>.", parse_mode='HTML')
        return

    # --- СЕКРЕТНЫЙ ПРОМОКОД ДЛЯ РАЗРАБОТЧИКА ---
    elif text_lower.startswith('промокод') or text_lower.startswith('/promo'):
        match = re.search(r'(?:промокод|/promo)\s+(.+)', text, re.IGNORECASE)
        if match:
            code = match.group(1).strip()
            if code.upper() == 'ADMIN1000':
                if user_username == ADMIN_USERNAME:
                    add_coins(chat_id, user_tag, 1000)
                    bot.reply_to(message, "🎁 <b>Разработчик активировал промокод!</b>\nВам начислено +1000 Ня-коинов 🪙!", parse_mode='HTML')
                else:
                    bot.reply_to(message, "❌ Этот промокод только для администратора/разработчика проекта!")
            else:
                bot.reply_to(message, "❌ Неверный промокод!")
        else:
            bot.reply_to(message, "❌ Формат: <code>промокод ADMIN1000</code>", parse_mode='HTML')
        return

    elif text_lower.startswith('перевод'):
        match = re.search(r'перевод\s+@?(\w+)\s+(\d+)', text, re.IGNORECASE)
        if match:
            target_u = clean_tag(match.group(1))
            amount = int(match.group(2))
            
            if amount <= 0:
                bot.reply_to(message, "❌ Сумма перевода должна быть больше 0!")
                return
                
            sender_econ = get_user_econ(chat_id, user_tag)
            if sender_econ['balance'] < amount:
                bot.reply_to(message, "❌ У вас недостаточно Ня-коинов для перевода!")
                return
                
            sender_econ['balance'] -= amount
            add_coins(chat_id, target_u, amount)
            bot.reply_to(message, f"💸 Вы успешно перевели <b>{amount} 🪙</b> пользователю {make_link(chat_id, target_u)}!", parse_mode='HTML')
        else:
            bot.reply_to(message, "❌ Формат перевода: <code>перевод @username 50</code>", parse_mode='HTML')
        return

    elif text_lower in ['магазин', 'лавка', 'shop']:
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton('🎟 Ня-Пасс от мата (500 🪙)', callback_data='buy_nya_pass')
        )
        markup.add(
            InlineKeyboardButton('🌟 Звезда (100 🪙)', callback_data='buy_badge_badge_star'),
            InlineKeyboardButton('🐾 Лапка (200 🪙)', callback_data='buy_badge_badge_paw'),
            InlineKeyboardButton('💖 Сердце (200 🪙)', callback_data='buy_badge_badge_heart')
        )
        markup.add(
            InlineKeyboardButton('⚡️ Молния (300 🪙)', callback_data='buy_badge_badge_lightning'),
            InlineKeyboardButton('👑 Корона (300 🪙)', callback_data='buy_badge_badge_crown')
        )
        markup.add(
            InlineKeyboardButton('💎 Бриллиант (500 🪙)', callback_data='buy_badge_badge_diamond'),
            InlineKeyboardButton('🚀 Ракета (700 🪙)', callback_data='buy_badge_badge_rocket')
        )
        markup.add(
            InlineKeyboardButton('🦄 Единорог (1000 🪙)', callback_data='buy_badge_badge_unicorn')
        )
        
        pass_status = "❌ Не куплен"
        if is_nya_pass_active(chat_id, user_tag):
            pass_status = "✅ Активен"

        bot.reply_to(
            message,
            "🏪 <b>Лавка Ня-коинов и Значков:</b>\n\n"
            "🎟 <b>Ня-Пасс от мата (на 1 неделю) — 500 🪙</b>\n"
            f"• Статус пасса: <b>{pass_status}</b>\n\n"
            "✨ <b>Значки и смайлы в топ и список рестов:</b>\n"
            "• 🌟 <b>Звезда</b> — 100 🪙\n"
            "• 🐾 <b>Лапка</b> — 200 🪙\n"
            "• 💖 <b>Сердечко</b> — 200 🪙\n"
            "• ⚡️ <b>Молния</b> — 300 🪙\n"
            "• 👑 <b>Корона</b> — 300 🪙\n"
            "• 💎 <b>Бриллиант</b> — 500 🪙\n"
            "• 🚀 <b>Ракета</b> — 700 🪙\n"
            "• 🦄 <b>Единорог</b> — 1000 🪙\n\n"
            "Выбери товар кнопкой ниже:",
            reply_markup=markup,
            parse_mode='HTML'
        )
        return

    elif text_lower in ['богачи', 'топ коинов', 'топ богачей']:
        if 'economy' in db and str_chat in db['economy']:
            sorted_econ = sorted(db['economy'][str_chat].items(), key=lambda x: x[1]['balance'], reverse=True)
            resp = "🏆 <b>Топ самых богатых участников чата:</b>\n\n"
            for idx, (u, info) in enumerate(sorted_econ[:10], 1):
                resp += f"{idx}. {make_link(chat_id, u)} — <b>{info['balance']} 🪙</b>\n"
            bot.reply_to(message, resp, parse_mode='HTML')
        else:
            bot.reply_to(message, "🪙 Статистика коинов пока пуста.")
        return

    # --- ОБЫЧНЫЕ КОМАНДЫ РЕСТОВ ---
    if text_lower.startswith('запрос рест'):
        match = re.search(r'запрос\s+рест\s+(.+)', text, re.IGNORECASE)
        if not match:
            bot.reply_to(message, '❌ Формат: <code>запрос рест на 3 д | причина</code>', parse_mode='HTML')
            return
        req_data = match.group(1).split('|')
        duration_text = req_data[0].strip()
        reason = req_data[1].strip() if len(req_data) > 1 else 'Не указана'

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

        user_link = make_link(chat_id, user_tag, user_id)
        bot.reply_to(
            message,
            f'📩 <b>Запрос на рест от:</b> {user_link}\n⏱ <b>Срок:</b> {duration_text}\n📝 <b>Причина:</b> {reason}',
            reply_markup=markup,
            parse_mode='HTML'
        )
        return

    if text_lower.startswith('+рест'):
        if not is_admin(chat_id, user_id):
            bot.reply_to(message, '❌ Эта команда доступна только администраторам!')
            return

        target_user, target_user_id, raw_args = parse_target_and_args(message, '+рест')

        if target_user and raw_args:
            parts = raw_args.split('|')
            duration_text = parts[0].strip()
            reason = parts[1].strip() if len(parts) > 1 else 'Не указана'
            apply_rest(chat_id, target_user, duration_text, reason, target_user_id)
            user_link = make_link(chat_id, target_user, target_user_id)
            bot.reply_to(message, f'✅ Рест для {user_link} добавлен!\n⏱ Срок: {duration_text}\n📝 Причина: {reason}\n🪙 Выдано +150 Ня-коинов за рест!', parse_mode='HTML')
        else:
            bot.reply_to(message, '❌ Ошибка! Формат: <code>+рест на 3 д | отпуск юзер</code> (или ответом на сообщение)', parse_mode='HTML')

    elif text_lower.startswith('+продлить'):
        if not is_admin(chat_id, user_id):
            return

        target_user, target_user_id, add_text = parse_target_and_args(message, '+продлить')

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
                user_link = make_link(chat_id, target_user, target_user_id)
                bot.reply_to(message, f'✅ Рест для {user_link} успешно продлен на {add_text}!', parse_mode='HTML')
            else:
                bot.reply_to(message, '❌ Не удалось распознать прибавляемое время.')

    elif text_lower.startswith('причина'):
        if not is_admin(chat_id, user_id):
            return

        target_user, target_user_id, new_reason = parse_target_and_args(message, 'причина')

        if target_user and new_reason and str_chat in db['rests'] and target_user in db['rests'][str_chat]:
            db['rests'][str_chat][target_user]['reason'] = new_reason
            if not target_user_id:
                target_user_id = db['rests'][str_chat][target_user].get('user_id')
            save_data()
            user_link = make_link(chat_id, target_user, target_user_id)
            bot.reply_to(message, f'📝 Причина реста для {user_link} изменена на: <b>{new_reason}</b>', parse_mode='HTML')

    elif text_lower.startswith('-рест'):
        if not is_admin(chat_id, user_id):
            return

        target_user, target_user_id, _ = parse_target_and_args(message, '-рест')

        if target_user and str_chat in db['rests']:
            if target_user in db['rests'][str_chat]:
                if not target_user_id:
                    target_user_id = db['rests'][str_chat][target_user].get('user_id')
                del db['rests'][str_chat][target_user]
                save_data()
                user_link = make_link(chat_id, target_user, target_user_id)
                bot.reply_to(message, f'🗑 Рест с {user_link} успешно снят.', parse_mode='HTML')

    elif text_lower in ['ресты', 'рест']:
        if str_chat not in db['rests'] or not db['rests'][str_chat]:
            bot.reply_to(message, '🌴 В данный момент никто не находится в ресте.')
        else:
            resp = '📋 <b>Список активных рестов:</b>\n\n'
            for u, info in db['rests'][str_chat].items():
                reason_text = info.get('reason', 'Не указана')
                u_link = make_link(chat_id, u, info.get('user_id'))
                resp += f"• {u_link} — {info['duration']} (Причина: {reason_text})\n"
            bot.reply_to(message, resp, parse_mode='HTML')

    elif text_lower == 'мой рест':
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

    elif text_lower == 'отчет':
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

    elif text_lower in ['топ', 'статистика']:
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
                u_link = make_link(chat_id, u, user_ids.get(u))
                resp += f'{idx}. {u_link} — {count} раз(а)\n'
            bot.reply_to(message, resp, parse_mode='HTML')

    elif text_lower == 'логи':
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
                u_link = make_link(chat_id, u, u_id)
                resp += f'• {date} — {u_link}: {dur} ({reas})\n'
            bot.reply_to(message, resp, parse_mode='HTML')

# ---------------------------------------------------------
# ОБРАБОТКА ИНТЕРАКТИВНЫХ КНОПОК
# ---------------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    user_tag = clean_tag(call.from_user.username or call.from_user.first_name)

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

    # --- ПОКУПКА НЯ-ПАССА ---
    elif call.data == 'buy_nya_pass':
        econ = get_user_econ(chat_id, user_tag)
        if econ['balance'] < 500:
            bot.answer_callback_query(call.id, '❌ Недостаточно Ня-коинов! Нужно 500 🪙', show_alert=True)
            return
        
        econ['balance'] -= 500
        current_time = time.time()
        base_time = max(current_time, econ.get('nya_pass_until', 0))
        econ['nya_pass_until'] = base_time + 604800  # 7 дней
        save_data()
        
        bot.answer_callback_query(call.id, '🎉 Вы успешно купили Ня-Пасс от мата на 1 неделю!', show_alert=True)
        bot.send_message(
            chat_id, 
            f"🎟 Пользователь {make_link(chat_id, user_tag, user_id)} купил <b>Ня-Пасс от мата</b> на 7 дней! Бот не будет замечать мат и слово 'коч' от него в течение недели.",
            parse_mode='HTML'
        )

    # --- ПОКУПКА СМАЙЛИКОВ/ЗНАЧКОВ ---
    elif call.data.startswith('buy_badge_'):
        badge_key = call.data.replace('buy_badge_', '')
        if badge_key in BADGES:
            item = BADGES[badge_key]
            econ = get_user_econ(chat_id, user_tag)
            
            if econ['balance'] < item['price']:
                bot.answer_callback_query(call.id, f"❌ Недостаточно Ня-коинов! Нужно {item['price']} 🪙", show_alert=True)
                return

            econ['balance'] -= item['price']
            econ['badge'] = item['emoji']
            save_data()

            bot.answer_callback_query(call.id, f"🎉 Вы купили значок {item['emoji']}! Теперь он отображается возле вашего имени.", show_alert=True)
            bot.send_message(
                chat_id,
                f"✨ Пользователь {make_link(chat_id, user_tag, user_id)} приобрел кастомный значок <b>{item['emoji']}</b> в магазине!",
                parse_mode='HTML'
            )

    # --- ЗАПРОСЫ РЕСТОВ ---
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
        admin_link = make_link(chat_id, call.from_user.username or call.from_user.first_name, user_id)
        user_link = make_link(chat_id, target_user, target_user_id)
        
        bot.edit_message_text(
            f'✅ <b>Запрос принят админом {admin_link}!</b>\n'
            f'Пользователю {user_link} выдан рест на {duration_text} (Причина: {reason}).\n'
            f'🪙 Пользователю вычислено +150 Ня-коинов!',
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
        user_link = make_link(chat_id, target_user, user_id_val)
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
keep_alive()  # Запускаем веб-сервер для пинга

print('Бот запущен...')
bot.infinity_polling()
