import ast
import csv
import copy
from datetime import datetime, timedelta, timezone
import html
import json
import os
import random
import re
import threading
import time
import telebot
import psycopg2
from psycopg2.extras import Json
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, ReactionTypeEmoji, LabeledPrice
from flask import Flask

# ---------------------------------------------------------
# ЕДИНЫЙ ЧАСОВОЙ ПОЯС (МСК / UTC+3)
# ---------------------------------------------------------
MSK_TZ = timezone(timedelta(hours=3))

def now_msk():
    return datetime.now(MSK_TZ)

# ---------------------------------------------------------
# ВЕБ-СЕРВЕР ДЛЯ KEEP-ALIVE (RENDER / REPLIT / VPS)
# ---------------------------------------------------------
app = Flask('')

@app.route('/')
def home():
    return "Nya Bot is alive and running! 😺"

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
TOKEN = os.environ.get("BOT_TOKEN", "").strip()
if not TOKEN:
    print("[ВНИМАНИЕ] BOT_TOKEN не задан в переменных окружения (ENV)! Бот ожидает BOT_TOKEN в Render.")
bot = telebot.TeleBot(TOKEN)
db_lock = threading.Lock()
db_dirty = False
db_version = 0

ADMIN_ID = 6081930693
ADMIN_USERNAME = 'ukrgorilka'

BOT_USERNAME_CACHE = None

def get_cached_bot_username():
    global BOT_USERNAME_CACHE
    if BOT_USERNAME_CACHE is None:
        try:
            me = bot.get_me()
            BOT_USERNAME_CACHE = (me.username or "").lower()
        except Exception:
            BOT_USERNAME_CACHE = ""
    return BOT_USERNAME_CACHE

def normalize_tg_id(cid_val):
    if not cid_val:
        return 0
    cid_str = str(cid_val).strip()
    try:
        val = int(cid_str)
        if val < 0 and not str(val).startswith('-100') and len(str(abs(val))) >= 9:
            return int(f"-100{abs(val)}")
        return val
    except ValueError:
        return 0

# ID каналов и чатов
# PostgreSQL/Neon is now the primary persistent database.
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
# Telegram-channel database backups are disabled by default.
DB_CHANNEL_ID = normalize_tg_id(os.environ.get('DB_CHANNEL_ID', '0'))
LOG_CHANNEL_ID = normalize_tg_id(os.environ.get('LOG_CHANNEL_ID', '-1004369517562'))
VD_CHAT_ID = normalize_tg_id(os.environ.get('VD_CHAT_ID', '-1003703264754'))
DATA_FILE = 'rests_data.json'

def leave_banned_chats():
    """Leave chats explicitly listed as banned in persistent DB/config."""
    banned = db.get('banned_chats', [])
    if isinstance(banned, dict):
        banned = list(banned.keys())
    for raw_chat_id in banned or []:
        try:
            chat_id = int(raw_chat_id)
            bot.leave_chat(chat_id)
        except Exception as e:
            print(f"[BANNED CHAT] failed to leave {raw_chat_id}: {e}")

def is_chat_banned(chat_id):
    """Return True when the chat is explicitly banned."""
    try:
        chat_id = int(chat_id)
    except (TypeError, ValueError):
        return False
    banned = db.get('banned_chats', [])
    if isinstance(banned, dict):
        return str(chat_id) in banned or chat_id in banned
    try:
        return chat_id in {int(x) for x in (banned or [])}
    except (TypeError, ValueError):
        return False

MEDIA_TG_CHAT_ID = normalize_tg_id(os.environ.get('MEDIA_TG_CHAT_ID', '-1004311479842'))

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

DURATION_PATTERN = (
    r'(?:\b(?:до\s+)?\d+\s*(?:дней|дня|день|д|часов|часа|час|ч|минут|мин|м)\b|'
    r'\b(?:до\s+)?\d{1,2}[\.\/]\d{1,2}(?:[\.\/]\d{2,4})?|'
    r'\b(?:до\s+)?\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря|'
    r'январь|февраль|март|апрель|май|июнь|июль|август|сентябрь|октябрь|ноябрь|декабрь)|'
    r'на\s+неопредел[её]нный\s+срок|неопредел[её]нный\s+срок|бессрочно|без\s+срока|навсегда)'
)

# ---------------------------------------------------------
# СТРИМЕР И САД БОНСАЙ (РАСШИРЕННЫЙ)
# ---------------------------------------------------------
STREAM_EQUIP = {
    'mic': {'name': '🎙 Микрофон', 'levels': [0, 1000, 3000, 8000, 15000]},
    'webcam': {'name': '📷 Вебкамера', 'levels': [0, 1500, 4000, 10000, 20000]},
    'light': {'name': '💡 Неоновый свет', 'levels': [0, 800, 2000, 5000, 12000]}
}

STREAM_GENRES = ['Гейминг', 'ASMR', 'Мемы', 'Трэш-ток']

GARDEN_SEEDS = {
    'chamomile': {'name': '🌼 Полевая ромашка', 'price': 70, 'grow_time': 3600*2, 'water_req': 2, 'reward_min': 150, 'reward_max': 250, 'emoji': '🌼'},
    'sakura': {'name': '🌸 Сакура', 'price': 300, 'grow_time': 3600*12, 'water_req': 3, 'reward_min': 800, 'reward_max': 1200, 'emoji': '🌸'},
    'berries': {'name': '🫐 Волшебные ягоды', 'price': 500, 'grow_time': 3600*8, 'water_req': 3, 'reward_min': 1000, 'reward_max': 1800, 'emoji': '🫐'},
    'money_tree': {'name': '💸 Денежное дерево', 'price': 800, 'grow_time': 3600*24, 'water_req': 5, 'reward_min': 2000, 'reward_max': 3500, 'emoji': '🌳'},
    'bamboo': {'name': '🎋 Золотой бамбук', 'price': 1500, 'grow_time': 3600*48, 'water_req': 7, 'reward_min': 4000, 'reward_max': 7000, 'emoji': '🎋'},
    'lotus': {'name': '🪷 Небесный лотос', 'price': 5000, 'grow_time': 3600*72, 'water_req': 9, 'reward_min': 14000, 'reward_max': 24000, 'emoji': '🪷'},
    'yggdrasil': {'name': '🌌 Древо Иггдрасиль', 'price': 50000, 'grow_time': 3600*120, 'water_req': 14, 'reward_min': 150000, 'reward_max': 280000, 'emoji': '🌌'}
}

# ---------------------------------------------------------
# БАЗА ЗНАНИЙ VIOLENCE DISTRICT (18 ФАКТОВ)
# ---------------------------------------------------------
VD_FACTS = [
    ("🏥 Больница Милосердия", "Карта «Крыша больницы милосердия» полностью вдохновлена и перенесена из культовой игры Left 4 Dead (первая кампания «No Mercy»)."),
    ("👕 Ретро-гардероб", "До крупного обновления с Вейл все маньяки в игре имели классическую 2D-одежду (текстуры)."),
    ("🪓 Первый охотник", "Самым первым стартовым маньяком в игре является The Slasher — Джейсон Вурхиз из легендарной франшизы «Пятница 13-е»."),
    ("🩸 Тайна подвала", "В подвале на карте «Кровавая Баня» за генератором или шкафом есть надпись «I know they have seen the basement» («Я знаю, они видели подвал»)."),
    ("🔦 Пасхалка Сайлент Хилл", "На карте «Кровавая Баня» в закрытой конструкции туалетной зоны спрятано фото Джеймса из игры «Silent Hill 2»."),
    ("📰 Новости Блоксбурга", "На втором этаже «Кровавой Бани» есть забавная пасхалка на Bloxburg News Guy."),
    ("⚡️ Шиноби во дворе", "На «Кровавой Бане» во дворе возле выхода висит изображение Саске из аниме «Наруто»."),
    ("👥 Оригинальная четверка", "Стартовый релизный ростер насчитывал всего 4 маньяка: Джейсон (The Slasher), Майкл Майерс (The Stalker), Джекет (The Masked) и Джефф (The Killer)."),
    ("🐔 Сложности масок", "Сложнее всего разработчикам дался Джакет — его модель масок была тесно связана со способностями, и малейшее искажение формы рушило всю анимацию и вайб."),
    ("🏚 Уютный дом Кожаного Лица", "И старое, и новое лобби в плейсе были скопированы с дома из слэшера «Техасская резня бензопилой»."),
    ("🎧 Эволюция темы погони", "Джеффу трижды меняли музыку погони: самая первая была темой Легиона из «Dead by Daylight»."),
    ("🔪 Судьба Саймона", "Саймона из «Cry of Fear» сначала планировали выпустить как отдельного убийцу, но в итоге сделали скином на Джеффа."),
    ("🛸 Утраченная Носторомо", "Старая карта «Носторомо» была удалена из-за постоянных жалоб на лаги и просадки кадров на слабых устройствах."),
    ("👤 Мексиканский след", "Ранний концепт Вейл изображал персонажа мужского пола (предположительно мексиканского происхождения)."),
    ("🎬 Загадочное мори", "Когда-то создатель Yousef показывал в sneak-peeks анимацию добивания (мори), но в финальную версию она так и не вошла."),
    ("🎀 Уникальная Джейн", "Музыка погони у скина «Джейн Убийца» имеет собственный уникальный саундтрек, отличный от темы Джеффа."),
    ("⚔️ Эра Арториаса", "На релизе Арториас был абсолютной имбой из-за огромных хитбоксов и лёгкости управления, снискав нелюбовь комьюнити."),
    ("👁 Забытая 3-я стадия", "У Майкла была 3-я стадия скорости и выпада, фото которой до сих пор осталось в его игровом меню.")
]

# ---------------------------------------------------------
# ЭКОНОМИКА: ТОВАРЫ, ЗНАЧКИ, КОЛЬЦА, ТЕМЫ И РАСХОДНИКИ
# ---------------------------------------------------------
BADGES = {
    'badge_star': {'name': 'Звездочка', 'emoji': '🌟', 'price': 120},
    'badge_dango': {'name': 'Данго', 'emoji': '🍡', 'price': 180},
    'badge_paw': {'name': 'Лапка Котика', 'emoji': '🐾', 'price': 240},
    'badge_heart': {'name': 'Сердечко', 'emoji': '💖', 'price': 240},
    'badge_fire': {'name': 'Огонек', 'emoji': '🔥', 'price': 300},
    'badge_lightning': {'name': 'Молния', 'emoji': '⚡️', 'price': 360},
    'badge_crown': {'name': 'Корона', 'emoji': '👑', 'price': 360},
    'badge_clover': {'name': 'Клевер', 'emoji': '🍀', 'price': 420},
    'badge_sakura': {'name': 'Сакура', 'emoji': '🌸', 'price': 480},
    'badge_diamond': {'name': 'Бриллиант', 'emoji': '💎', 'price': 600},
    'badge_skull': {'name': 'Череп', 'emoji': '💀', 'price': 720},
    'badge_rocket': {'name': 'Ракета', 'emoji': '🚀', 'price': 840},
    'badge_fox': {'name': 'Лисичка', 'emoji': '🦊', 'price': 960},
    'badge_alien': {'name': 'Инопланетянин', 'emoji': '👽', 'price': 1100},
    'badge_unicorn': {'name': 'Единорог', 'emoji': '🦄', 'price': 1200},
    'badge_dragon': {'name': 'Дракон', 'emoji': '🐉', 'price': 1800},
    'badge_ghost': {'name': 'Призрак', 'emoji': '👻', 'price': 2400},
    'badge_foot': {'name': 'Пятка', 'emoji': '🦶', 'price': 3600},
}

TITLES = {
    'pumpkin_lord': {'name': 'Повелитель Тыкв', 'text': '🎃 Повелитель Тыкв', 'price': 0, 'buff': 'luck', 'val': 15, 'desc': '+15% к удаче во всех играх и событиях (Хеллоуин Pass)'},
    'king': {'name': 'Кинг', 'text': '👑 Кинг', 'price': 3000, 'buff': 'luck', 'val': 10, 'desc': '+10% к удаче в играх'},
    'sonya': {'name': 'Соня', 'text': '💤 Соня', 'price': 2200, 'buff': 'cd_reduction', 'val': 10, 'desc': '-10% ко всем кулдаунам'},
    'legend': {'name': 'Легенда', 'text': '🔥 Легенда', 'price': 3600, 'buff': 'exp_bonus', 'val': 25, 'desc': '+25% к опыту профиля'},
    'dragon': {'name': 'Дракон', 'text': '🐉 Дракон', 'price': 4200, 'buff': 'biz_bonus', 'val': 8, 'desc': '+8% к доходу бизнесов'},
    'bun': {'name': 'Булочка', 'text': '🥐 Булочка', 'price': 1800, 'buff': 'bonus_coins', 'val': 15, 'desc': '+15 коинов к /bonus'},
    'coffee_man': {'name': 'Кофеман', 'text': '☕️ Кофеман', 'price': 2500, 'buff': 'cd_reduction', 'val': 15, 'desc': '-15% ко всем кулдаунам'},
    'oligarch': {'name': 'Олигарх', 'text': '💸 Олигарх', 'price': 5000, 'buff': 'biz_bonus', 'val': 12, 'desc': '+12% к прибыли предприятий'},
    'shadow_ninja': {'name': 'Теневой Ниндзя', 'text': '🥷 Теневой Ниндзя', 'price': 3500, 'buff': 'rob_save', 'val': 50, 'desc': '-50% штраф при ограблении'},
    'sakura_lord': {'name': 'Сакура', 'text': '🌸 Сакура', 'price': 2800, 'buff': 'pet_exp', 'val': 30, 'desc': '+30% к опыту питомца'},
    'gigachad': {'name': 'Гигачад', 'text': '🗿 Гигачад', 'price': 6000, 'buff': 'all_power', 'val': 10, 'desc': '+10% ко всем доходам и удаче'},
    'clown': {'name': 'Главный Клоун', 'text': '🤡 Главный Клоун', 'price': 2000, 'buff': 'smeh_boost', 'val': 100, 'desc': '+1 очко Смехуятинки за смс'},
    'beer_baron': {'name': 'Пивной Барон', 'text': '🍺 Пивной Барон', 'price': 3200, 'buff': 'bonus_coins', 'val': 25, 'desc': '+25 коинов к /bonus'},
    'tapok_master': {'name': 'Повелитель Тапка', 'text': '🩴 Повелитель Тапка', 'price': 4000, 'buff': 'luck', 'val': 15, 'desc': '+15% к удаче охоты/рыбалки'},
}

RINGS = {
    'copper': {'name': 'Медное колечко', 'emoji': '🥉', 'price': 600},
    'silver': {'name': 'Серебряное кольцо', 'emoji': '🥈', 'price': 1800},
    'gold': {'name': 'Золотое кольцо', 'emoji': '🥇', 'price': 4200},
    'diamond': {'name': 'Бриллиантовое кольцо', 'emoji': '💍', 'price': 9600},
    'cosmic': {'name': 'Космическое кольцо Любви', 'emoji': '🌌', 'price': 24000},
}

THEMES = {
    'default': {'name': 'Классическая', 'price': 0, 'border': '──────────────────────', 'header': '👤 <b>КАРТОЧКА ИГРОКА</b>', 'icon': '🔹'},
    'sakura': {'name': '🌸 Сакура', 'price': 1200, 'border': '🌸══════ ✿ ══════🌸', 'header': '🌸 <b>КАРТОЧКА ИГРОКА: SAKURA EDITION</b> 🌸', 'icon': '🌸'},
    'neon': {'name': '🌌 Неон / Киберпанк', 'price': 2000, 'border': '⚡️══════ ◈ ══════⚡️', 'header': '🌌 <b>CYBERPUNK ID-CARD: NEON</b> ⚡️', 'icon': '🔮'},
    'gold': {'name': '👑 Королевское Золото', 'price': 3500, 'border': '⚜️══════ 👑 ══════⚜️', 'header': '👑 <b>КОРОЛЕВСКИЙ VIP ПРОФИЛЬ</b> ⚜️', 'icon': '✨'},
    'gothic': {'name': '💀 Тёмная Готика', 'price': 2500, 'border': '☠️══════ 🪦 ══════☠️', 'header': '💀 <b>ГОТИЧЕСКИЙ ГРИМУАР ДУШИ</b> 🕯', 'icon': '🩸'},
    'cyberpunk': {'name': '🤖 Киберпанк 2077', 'price': 3000, 'border': '⚠️══════ ⚡️ ══════⚠️', 'header': '🤖 <b>CYBERPUNK NEURAL PROFILE</b> 🦾', 'icon': '🔋'},
    'space': {'name': '🌌 Космос и Звезды', 'price': 3500, 'border': '🪐══════ 🌠 ══════🌌', 'header': '🌌 <b>ГАЛАКТИЧЕСКИЙ АТЛАС ЗВЕЗД</b> 🪐', 'icon': '✨'},
    'blood_moon': {'name': '🩸 Кровавая Луна', 'price': 4000, 'border': '🌕══════ 🩸 ══════🌑', 'header': '🩸 <b>АЛТАРЬ КРОВАВОЙ ЛУНЫ</b> 🗡', 'icon': '🍷'},
    'emerald': {'name': '🌿 Изумрудный Лес', 'price': 2200, 'border': '🍃══════ 🌲 ══════🍃', 'header': '🌿 <b>ХРАНИТЕЛЬ ДРЕВНЕГО ЛЕСА</b> 🍃', 'icon': '🌱'},
    'synthwave': {'name': '🌇 Синтвейв 80s', 'price': 2800, 'border': '🌴══════ 🌆 ══════🌴', 'header': '🌇 <b>RETROWAVE SUNSET DRIVE</b> 🏎', 'icon': '📼'},
    'frost': {'name': '❄️ Вечная Мерзлота', 'price': 2600, 'border': '❄️══════ 🧊 ══════❄️', 'header': '❄️ <b>ЛЕДЯНОЙ ЧЕРТОГ АРКТИКИ</b> 🧊', 'icon': '💎'},
    'halloween': {'name': '🎃 Тёмный Хеллоуин: Тыквенная Ночь 🦇', 'price': 0, 'border': '🎃══════ 🦇 🕸 🕯 ══════🎃', 'header': '🎃 <b>ТЁМНЫЙ ГРИМУАР ТЫКВЕННОЙ НОЧИ</b> 🦇', 'icon': '🦇'},
    'stars_gold': {'name': '🌟 Императорское Золото VIP', 'price': 0, 'border': '⭐️══════ ⚜️ ══════⭐️', 'header': '🌟 <b>ИМПЕРАТОРСКИЙ STARS ПРОФИЛЬ</b> 👑', 'icon': '⭐️'},
    'stars_anime': {'name': '🎀 Аниме Люкс VIP', 'price': 0, 'border': '✨══════ 🎀 ══════✨', 'header': '🎀 <b>ANIME LUXURY SUPREME ID</b> 💖', 'icon': '💫'},
    'stars_galaxy': {'name': '🌌 Бездна Сингулярности VIP', 'price': 0, 'border': '🪐══════ 🌀 ══════🌌', 'header': '🌌 <b>БЕЗДНА КОСМИЧЕСКОЙ СИНГУЛЯРНОСТИ</b> 🛸', 'icon': '🪐'}
}
# ---------------------------------------------------------
# ЭКОНОМИКА TELEGRAM STARS (ЗВЁЗДЫ) & VIP PASS
# ---------------------------------------------------------
STARS_COIN_PACKS = {
    'coins_1_star': {'name': '💰 35,000 Ня-коинов', 'coins': 35000, 'stars': 1, 'desc': 'Стартовый мешочек коинов (выгодный курс)'},
    'coins_3_stars': {'name': '💵 100,000 Ня-коинов', 'coins': 100000, 'stars': 3, 'desc': 'Народный пак: 100к коинов всего за 3 ⭐️!'},
    'coins_5_stars': {'name': '💳 200,000 Ня-коинов', 'coins': 200000, 'stars': 5, 'desc': 'Крупный капитал для предприятий и бизнеса'},
    'coins_10_stars': {'name': '🏦 500,000 Ня-коинов', 'coins': 500000, 'stars': 10, 'desc': 'Капитал магната для покорения биржи и топов'},
    'coins_20_stars': {'name': '💎 1,200,000 Ня-коинов', 'coins': 1200000, 'stars': 20, 'desc': 'Миллионный фонд для абсолютного богатства'}
}

STARS_VIP_PASS = {
    'pass_7_days': {'name': '⭐️ VIP Nya Pass (7 дней)', 'days': 7, 'stars': 1, 'desc': '-30% ко всем кулдаунам, 2x /bonus, 100% защита от ограблений'},
    'pass_30_days': {'name': '⭐️ VIP Nya Pass (30 дней)', 'days': 30, 'stars': 3, 'desc': 'Месяц полного VIP комфорта и удвоенных наград'},
    'pass_forever': {'name': '👑 VIP Nya Pass НАВСЕГДА', 'days': -1, 'stars': 25, 'desc': 'Пожизненный VIP статус и все привилегии навсегда!'}
}

VIP_BADGES = {
    'vip_badge_crown': {'name': 'Корона VIP', 'emoji': '👑', 'stars': 1, 'desc': 'Символ элиты чата'},
    'vip_badge_star': {'name': 'Звезда Покровителя', 'emoji': '⭐️', 'stars': 1, 'desc': 'Знак поддержки бота'},
    'vip_badge_gem': {'name': 'Сияющий Алмаз', 'emoji': '💎', 'stars': 1, 'desc': 'Драгоценный статус'},
    'vip_badge_angel': {'name': 'Крылья Ангела', 'emoji': '🪽', 'stars': 2, 'desc': 'Светлый хранитель'},
    'vip_badge_galaxy': {'name': 'Космос', 'emoji': '🌌', 'stars': 2, 'desc': 'Межгалактический покровитель'},
    'vip_badge_dragon': {'name': 'Дракон Империи', 'emoji': '🐲', 'stars': 2, 'desc': 'Мощь древнего дракона'}
}

STARS_COSMETICS = {
    'bp_premium': {'name': '🎃 Премиум Хеллоуинский Pass', 'stars': 2, 'type': 'bp_premium', 'desc': 'Открывает премиум-ветку наград, Тыквокота и Тёмную тему!'},
    'custom_title': {'name': '🌟 Сертификат Кастомного Титула', 'stars': 2, 'type': 'title_cert', 'desc': 'Возможность поставить любой свой титул в /custom_title'},
    'pet_griffin': {'name': '👑 Питомец: Королевский Грифон', 'stars': 3, 'type': 'pet', 'pet_id': 'vip_griffin', 'desc': 'Эксклюзивный питомец (+150% к удаче)'},
    'theme_gold': {'name': '🌟 Тема: Императорское Золото VIP', 'stars': 1, 'type': 'theme', 'theme_id': 'stars_gold', 'desc': 'Роскошная золотая рамка профиля'},
    'theme_anime': {'name': '🎀 Тема: Аниме Люкс VIP', 'stars': 1, 'type': 'theme', 'theme_id': 'stars_anime', 'desc': 'Премиальный аниме стиль профиля'},
    'theme_galaxy': {'name': '🌌 Тема: Бездна Сингулярности VIP', 'stars': 2, 'type': 'theme', 'theme_id': 'stars_galaxy', 'desc': 'Космическая стилистика сингулярности'},
    'badge_crown': {'name': '👑 Значок: Корона VIP', 'stars': 1, 'type': 'badge', 'emoji': '👑', 'desc': 'VIP значок рядом с ником'},
    'badge_star': {'name': '⭐️ Значок: Звезда Покровителя', 'stars': 1, 'type': 'badge', 'emoji': '⭐️', 'desc': 'Значок спонсора бота'},
    'badge_gem': {'name': '💎 Значок: Сияющий Алмаз', 'stars': 1, 'type': 'badge', 'emoji': '💎', 'desc': 'Драгоценный значок'},
    'badge_angel': {'name': '🪽 Значок: Крылья Ангела', 'stars': 2, 'type': 'badge', 'emoji': '🪽', 'desc': 'Ангельские крылья в чате'},
    'badge_galaxy': {'name': '🌌 Значок: Космос', 'stars': 2, 'type': 'badge', 'emoji': '🌌', 'desc': 'Галактический значок'},
    'badge_dragon': {'name': '🐲 Значок: Дракон Империи', 'stars': 2, 'type': 'badge', 'emoji': '🐲', 'desc': 'Значок дракона'}
}


# ---------------------------------------------------------
# ШРИФТЫ ДЛЯ ПРОФИЛЯ
# ---------------------------------------------------------
FONTS = {
    'default': {'name': 'Обычный (Telegram)', 'desc': 'Стандартный шрифт интерфейса'},
    'monospace': {'name': '💻 Моноширинный', 'desc': 'Стиль терминала и кода'},
    'bold_serif': {'name': '🎩 Сериф жирный', 'desc': 'Классический винтажный стиль'},
    'script': {'name': '✒️ Рукописный курсив', 'desc': 'Элегантный каллиграфический стиль'},
    'fraktur': {'name': '⚔️ Готический', 'desc': 'Древний готический шрифт'},
    'bubbles': {'name': '🫧 Пузырьки', 'desc': 'Игривый стиль в кружочках'}
}

FONT_MAPS = {
    'bold_serif': {'A':'𝐀','B':'𝐁','C':'𝐂','D':'𝐃','E':'𝐄','F':'𝐅','G':'𝐆','H':'𝐇','I':'𝐈','J':'𝐉','K':'𝐊','L':'𝐋','M':'𝐌','N':'𝐍','O':'𝐎','P':'𝐏','Q':'𝐐','R':'𝐑','S':'𝐒','T':'𝐓','U':'𝐔','V':'𝐕','W':'𝐖','X':'𝐗','Y':'𝐘','Z':'𝐙','a':'𝐚','b':'𝐛','c':'𝐜','d':'𝐝','e':'𝐞','f':'𝐟','g':'𝐠','h':'𝐡','i':'𝐢','j':'𝐣','k':'𝐤','l':'𝐥','m':'𝐦','n':'𝐧','o':'𝐨','p':'𝐩','q':'𝐪','r':'𝐫','s':'𝐬','t':'𝐭','u':'𝐮','v':'𝐯','w':'𝐰','x':'𝐱','y':'𝐲','z':'𝐳','0':'𝟎','1':'𝟏','2':'𝟐','3':'𝟑','4':'𝟒','5':'𝟓','6':'𝟔','7':'𝟕','8':'𝟖','9':'𝟗'},
    'script': {'A':'𝒜','B':'𝐵','C':'𝒞','D':'𝒟','E':'𝐸','F':'𝐹','G':'𝒢','H':'𝐻','I':'𝐼','J':'𝒥','K':'𝒦','L':'𝐿','M':'𝑀','N':'𝒩','O':'𝒪','P':'𝒫','Q':'𝒬','R':'𝑅','S':'𝒮','T':'𝒯','U':'𝒰','V':'𝒱','W':'𝒲','X':'𝒳','Y':'𝒴','Z':'𝒵','a':'𝒶','b':'𝒷','c':'𝒸','d':'𝒹','e':'𝑒','f':'𝒻','g':'𝑔','h':'𝒽','i':'𝒾','j':'𝒿','k':'𝓀','l':'𝓁','m':'𝓂','n':'𝓃','o':'𝑜','p':'𝓅','q':'𝓆','r':'𝓇','s':'𝓈','t':'𝓉','u':'𝓊','v':'𝓋','w':'𝓌','x':'𝓍','y':'𝓎','z':'𝓏'},
    'fraktur': {'A':'𝔄','B':'𝔅','C':'ℭ','D':'𝔇','E':'𝔈','F':'𝔉','G':'𝔊','H':'ℌ','I':'ℑ','J':'𝔍','K':'𝔎','L':'𝔏','M':'𝔐','N':'𝔑','O':'𝔒','P':'𝔓','Q':'𝔔','R':'ℜ','S':'𝔖','T':'𝔗','U':'𝔘','V':'𝔙','W':'𝔚','X':'𝔛','Y':'𝔜','Z':'ℨ','a':'𝔞','b':'𝔟','c':'𝔠','d':'𝔡','e':'𝔢','f':'𝔣','g':'𝔤','h':'𝔥','i':'𝔦','j':'𝔧','k':'𝔨','l':'𝔩','m':'𝔪','n':'𝔫','o':'𝔬','p':'𝔭','q':'𝔮','r':'𝔯','s':'𝔰','t':'𝔱','u':'𝔲','v':'𝔳','w':'𝔴','x':'𝔵','y':'𝔶','z':'𝔷'},
    'bubbles': {'A':'Ⓐ','B':'Ⓑ','C':'Ⓒ','D':'Ⓓ','E':'Ⓔ','F':'Ⓕ','G':'Ⓖ','H':'Ⓗ','I':'Ⓘ','J':'Ⓙ','K':'Ⓚ','L':'Ⓛ','M':'Ⓜ','N':'Ⓝ','O':'Ⓞ','P':'Ⓟ','Q':'Ⓠ','R':'Ⓡ','S':'Ⓢ','T':'Ⓣ','U':'Ⓤ','V':'Ⓥ','W':'Ⓦ','X':'Ⓧ','Y':'Ⓨ','Z':'Ⓩ','a':'ⓐ','b':'ⓑ','c':'ⓒ','d':'ⓓ','e':'ⓔ','f':'ⓕ','g':'ⓖ','h':'ⓗ','i':'ⓘ','j':'ⓙ','k':'ⓚ','l':'ⓛ','m':'ⓜ','n':'ⓝ','o':'ⓞ','p':'ⓟ','q':'ⓠ','r':'ⓡ','s':'ⓢ','t':'ⓣ','u':'ⓤ','v':'ⓥ','w':'ⓦ','x':'ⓧ','y':'ⓨ','z':'ⓩ','0':'⓪','1':'①','2':'②','3':'③','4':'④','5':'⑤','6':'⑥','7':'⑦','8':'⑧','9':'⑨'}
}

def apply_font(text_str, font_key='default'):
    if not text_str or font_key == 'default':
        return text_str
    if font_key == 'monospace':
        return f"<code>{text_str}</code>"
    f_map = FONT_MAPS.get(font_key)
    if not f_map:
        return text_str
    parts = re.split(r'(<[^>]+>)', str(text_str))
    res = []
    for p in parts:
        if p.startswith('<') and p.endswith('>'):
            res.append(p)
        else:
            res.append("".join(f_map.get(ch, ch) for ch in p))
    return "".join(res)

BUFF_ITEMS = {
    'energy_drink': {'name': '⚡️ Энергетик Red Cat', 'short': '⚡️ Энергетик', 'price': 400, 'desc': 'Мгновенный сброс всех кулдаунов работы, замеров, мусорки и охоты (кд 30 мин)'},
    'luck_clover': {'name': '🍀 Клевер Удачи (1 час)', 'short': '🍀 Клевер', 'price': 700, 'desc': '+15% к удаче во всех играх казино на 1 час'},
    'alarm_system': {'name': '🛡 Охранная сигнализация', 'short': '🛡 Сигнализация', 'price': 600, 'desc': 'Защита от 1 ограбления (вор оглушается и платит вам штраф)'},
    'invis_mask': {'name': '🥷 Маска-невидимка (24 часа)', 'short': '🥷 Невидимка', 'price': 500, 'desc': 'Скрывает мемные замеры в общих топах чата'},
    'garden_fertilizer': {'name': '🧪 Супер-удобрение для сада', 'short': '🧪 Удобрение', 'price': 5000, 'desc': 'Одно применение ускоряет текущий рост растения на 10%. Можно покупать сколько угодно.'}
}

# ---------------------------------------------------------
# РАСШИРЕННЫЕ БИЗНЕСЫ
# ---------------------------------------------------------
BUSINESSES = {
    'bottles': {'name': '🥫 Приём стеклотары', 'short': 'Стеклотара', 'price': 200, 'base_income': 3, 'upgrade_cost': 120},
    'lemonade': {'name': '🍋 Лоток с лимонадом', 'short': 'Лимонад', 'price': 450, 'base_income': 6, 'upgrade_cost': 280},
    'shawarma': {'name': '🌯 Ларек с Шаурмой', 'short': 'Шаурма', 'price': 800, 'base_income': 9, 'upgrade_cost': 500},
    'coffee': {'name': '☕️ Уютная Кофейня', 'short': 'Кофейня', 'price': 2400, 'base_income': 24, 'upgrade_cost': 1800},
    'bakery': {'name': '🥐 Пекарня Булочек', 'short': 'Пекарня', 'price': 6000, 'base_income': 54, 'upgrade_cost': 4500},
    'crypto_farm': {'name': '💻 Крипто-Ферма', 'short': 'Крипто-Ферма', 'price': 18000, 'base_income': 150, 'upgrade_cost': 13000},
    'club': {'name': '🏰 Ночной Клуб', 'short': 'Ночной Клуб', 'price': 54000, 'base_income': 420, 'upgrade_cost': 38000},
    'autoshow': {'name': '🏎 Автосалон Спорткаров', 'short': 'Автосалон', 'price': 120000, 'base_income': 900, 'upgrade_cost': 85000},
    'space_station': {'name': '🛰 Космическая Станция', 'short': 'Космостанция', 'price': 450000, 'base_income': 3150, 'upgrade_cost': 300000},
    'megacorp': {'name': '🏢 Мегакорпорация', 'short': 'Мегакорп', 'price': 1500000, 'base_income': 10500, 'upgrade_cost': 1000000},
    'oil_rig': {'name': '🛢 Нефтяная вышка в Сибири', 'short': 'Нефтевышка', 'price': 3500000, 'base_income': 24000, 'upgrade_cost': 2200000},
    'shipyard': {'name': '🚀 Космодромная верфь', 'short': 'Верфь', 'price': 10000000, 'base_income': 66000, 'upgrade_cost': 6500000},
    'mars_colony': {'name': '🪐 Колония на Марсе', 'short': 'Марс', 'price': 50000000, 'base_income': 300000, 'upgrade_cost': 30000000}
}

CUSTOM_TITLE_CERT_PRICE = 15000

RODS = {
    'rod_stick': {'name': '🪵 Палка с ниткой', 'short': '🪵 Ветка', 'price': 120, 'luck': 4},
    'rod_bamboo': {'name': '🎋 Бамбуковая удочка', 'short': '🎋 Бамбук', 'price': 500, 'luck': 10},
    'rod_carbon': {'name': '🎣 Карбоновый спиннинг', 'short': '🎣 Карбон', 'price': 2500, 'luck': 25},
    'rod_titan': {'name': '🔱 Удочка Посейдона', 'short': '🔱 Посейдон', 'price': 10000, 'luck': 55},
    'rod_laser': {'name': '🏮 Лазерная Удочка', 'short': '🏮 Лазер', 'price': 25000, 'luck': 90},
    'rod_quantum': {'name': '🌌 Квантовый Спиннинг Сингулярности', 'short': '🌌 Сингулярность', 'price': 100000, 'luck': 160}
}

BOWS = {
    'bow_slingshot': {'name': '🪵 Деревянная рогатка', 'short': '🪵 Рогатка', 'price': 120, 'luck': 4},
    'bow_hunting': {'name': '🏹 Охотничий лук', 'short': '🏹 Охотничий', 'price': 600, 'luck': 10},
    'bow_sniper': {'name': '🎯 Снайперский лук', 'short': '🎯 Снайперский', 'price': 3000, 'luck': 30},
    'bow_phoenix': {'name': '🔥 Лук Феникса', 'short': '🔥 Феникс', 'price': 12000, 'luck': 65},
    'bow_laser': {'name': '🔫 Лазерный Бластер', 'short': '🔫 Бластер', 'price': 30000, 'luck': 110},
    'bow_antimatter': {'name': '⚡️ Аннигилятор Антиматерии', 'short': '⚡️ Аннигилятор', 'price': 120000, 'luck': 180}
}

VEHICLES = {
    'slippers': {'name': '🩴 Дырявые сланцы', 'short': '🩴 Сланцы', 'price': 100, 'cd_cut': 0.01, 'desc': '-1% ко всем таймерам', 'tier': 0, 'msg_id': None},
    'rusty_bike': {'name': '🚲 Ржавый велосипед «Салют»', 'short': '🚲 Велосипед', 'price': 250, 'cd_cut': 0.02, 'desc': '-2% ко всем таймерам', 'tier': 1, 'msg_id': None},
    'skateboard': {'name': '🛹 Скейтборд Pro', 'short': '🛹 Скейт', 'price': 500, 'cd_cut': 0.03, 'desc': '-3% ко всем таймерам', 'tier': 2, 'msg_id': None},
    'scooter': {'name': '🛴 Электросамокат', 'short': '🛴 Самокат', 'price': 1500, 'cd_cut': 0.05, 'desc': '-5% ко всем таймерам', 'tier': 3, 'msg_id': 274},
    'vaz_2107': {'name': '🚗 ВАЗ-2107 «Семёрка» Боевая', 'short': '🚗 ВАЗ-2107', 'price': 3500, 'cd_cut': 0.08, 'desc': '-8% ко всем таймерам', 'tier': 4, 'msg_id': None},
    'bike': {'name': '🏍 Спортбайк Yamaha R1', 'short': '🏍 Спортбайк', 'price': 7500, 'cd_cut': 0.12, 'desc': '-12% ко всем таймерам', 'tier': 5, 'msg_id': 275},
    'supra': {'name': '🏎 Toyota Supra A80 Twin-Turbo', 'short': '🏎 Supra', 'price': 15000, 'cd_cut': 0.16, 'desc': '-16% ко всем таймерам', 'tier': 6, 'msg_id': None},
    'bmw': {'name': '🚗 BMW M5 CS', 'short': '🚗 BMW M5', 'price': 30000, 'cd_cut': 0.22, 'desc': '-22% ко всем таймерам', 'tier': 7, 'msg_id': 276},
    'ferrari': {'name': '🏎 Ferrari SF90 Stradale', 'short': '🏎 Ferrari', 'price': 95000, 'cd_cut': 0.30, 'desc': '-30% ко всем таймерам', 'tier': 8, 'msg_id': 277},
    'helicopter': {'name': '🚁 Вертолёт Robinson R44', 'short': '🚁 Вертолёт', 'price': 200000, 'cd_cut': 0.38, 'desc': '-38% ко всем таймерам', 'tier': 9, 'msg_id': None},
    'rocket': {'name': '🚀 Ракета SpaceX Starship', 'short': '🚀 Starship', 'price': 350000, 'cd_cut': 0.45, 'desc': '-45% ко всем таймерам', 'tier': 10, 'msg_id': 278},
    'yacht': {'name': '🛥 Суперяхта Олигарха Eclipse', 'short': '🛥 Суперяхта', 'price': 650000, 'cd_cut': 0.52, 'desc': '-52% ко всем таймерам', 'tier': 11, 'msg_id': None},
    'teleport': {'name': '🌀 Квантовый Телепорт', 'short': '🌀 Телепорт', 'price': 1000000, 'cd_cut': 0.60, 'desc': '-60% ко всем таймерам', 'tier': 12, 'msg_id': None},
    'private_jet': {'name': '🛩 Частный Бизнес-джет Gulfstream G650', 'short': '🛩 Бизнес-джет', 'price': 2500000, 'cd_cut': 0.68, 'desc': '-68% ко всем таймерам', 'tier': 13, 'msg_id': None},
    'star_cruiser': {'name': '🛸 Космический Крейсер Империи', 'short': '🛸 Космокрейсер', 'price': 10000000, 'cd_cut': 0.75, 'desc': '-75% ко всем таймерам', 'tier': 14, 'msg_id': None}
}

MARKET_DEFAULT = {
    'NYA': {'name': '🐾 Ня-Биткоин (NYA)', 'price': 120.0, 'old_price': 110.0, 'volatility': 0.18, 'min_price': 15.0, 'max_price': 3500.0, 'last_update': 0},
    'MEOW': {'name': '🐱 Мяу-Эфириум (MEOW)', 'price': 45.0, 'old_price': 42.0, 'volatility': 0.22, 'min_price': 5.0, 'max_price': 1200.0, 'last_update': 0},
    'ANM': {'name': '🌸 Аниме-Акции (ANM)', 'price': 15.0, 'old_price': 14.0, 'volatility': 0.28, 'min_price': 1.0, 'max_price': 500.0, 'last_update': 0},
    'PAT': {'name': '🦶 Пятка-Коин (PAT)', 'price': 5.0, 'old_price': 6.0, 'volatility': 0.35, 'min_price': 0.5, 'max_price': 200.0, 'last_update': 0}
}

JOBS = {
    'fermer': {'name': '👨‍🌾 Фермер', 'req_exp': 0, 'chance': 95, 'min_pay': 25, 'max_pay': 55, 'exp_gain': 10},
    'janitor': {'name': '🧹 Дворник', 'req_exp': 0, 'chance': 90, 'min_pay': 35, 'max_pay': 65, 'exp_gain': 12},
    'courier': {'name': '🛵 Курьер', 'req_exp': 50, 'chance': 80, 'min_pay': 75, 'max_pay': 145, 'exp_gain': 15},
    'cook': {'name': '👨‍🍳 Повар', 'req_exp': 150, 'chance': 70, 'min_pay': 145, 'max_pay': 290, 'exp_gain': 20},
    'office': {'name': '👨‍💻 Офисный клерк', 'req_exp': 350, 'chance': 60, 'min_pay': 280, 'max_pay': 550, 'exp_gain': 25},
    'programmer': {'name': '💻 Программист', 'req_exp': 800, 'chance': 45, 'min_pay': 650, 'max_pay': 1300, 'exp_gain': 35},
    'boss': {'name': '💼 Бизнесмен', 'req_exp': 1800, 'chance': 30, 'min_pay': 1500, 'max_pay': 3800, 'exp_gain': 50}
}

FISH_TYPES = [
    ('🐟 Речной Карась', 'Обычный', 12, 50),
    ('🐠 Речной Окунь', 'Обычный', 20, 40),
    ('🐡 Речная Плотва', 'Обычный', 25, 35),
    ('🦈 Зубастая Щука', 'Редкий', 60, 20),
    ('🦀 Речной Рак', 'Редкий', 80, 15),
    ('🦞 Золотистый Краб', 'Редкий', 110, 12),
    ('🐙 Глубоководный Осьминог', 'Эпический', 220, 7),
    ('🐡 Электрический Скат', 'Эпический', 290, 5),
    ('🐬 Радужный Дельфин', 'Эпический', 360, 4),
    ('🧜‍♀️ Лазурная Русалка', 'Легендарный', 650, 2),
    ('🐳 Древний Белый Кит', 'Легендарный', 900, 2),
    ('🐉 Небесный Драконорыб', 'Мифический', 1800, 1),
    ('🔱 Божественный Левиафан', 'Божественный', 4500, 1),
    ('🌌 Астральный Скат', 'Космический', 12000, 0.5),
]

HUNT_TYPES = [
    ('🐇 Полевой Заяц', 'Обычный', 15, 50),
    ('🐿 Шустрая Белка', 'Обычный', 22, 40),
    ('🦊 Рыжая Лисица', 'Обычный', 35, 35),
    ('🐗 Дикий Кабан', 'Редкий', 75, 20),
    ('🐺 Серый Волк', 'Редкий', 95, 15),
    ('🦌 Благородный Олень', 'Редкий', 130, 12),
    ('🐻 Бурый Медведь', 'Эпический', 260, 7),
    ('🐅 Снежный Барс', 'Эпический', 340, 5),
    ('🦣 Мамонт Саванны', 'Эпический', 480, 4),
    ('🦅 Огненный Феникс', 'Легендарный', 750, 2),
    ('🦄 Звездный Грифон', 'Легендарный', 1100, 2),
    ('🐉 Пещерный Дракон', 'Мифический', 2200, 1),
    ('🌌 Астральный Бегемот', 'Божественный', 5500, 1),
    ('🌋 Магмовый Голем', 'Космический', 15000, 0.5),
]

PETS_DATA = {
    'pumpkin_cat': {'name': '🎃 Тыквоголовый Кот', 'short': '🎃 Тыквокот', 'price': 0, 'luck_bonus': 120, 'desc': '+120% к удаче, хранитель хеллоуинской магии'},
    'cat': {'name': '🐱 Котик Усач', 'short': '🐱 Котик', 'price': 720, 'luck_bonus': 15, 'desc': '+15% к удаче в охоте/рыбалке'},
    'dog': {'name': '🐶 Пёсель Верный', 'short': '🐶 Пёсель', 'price': 1450, 'luck_bonus': 25, 'desc': '+25% к удаче в охоте/рыбалке'},
    'fox': {'name': '🦊 Хитрая Лисичка', 'short': '🦊 Лисичка', 'price': 3000, 'luck_bonus': 40, 'desc': '+40% к удаче в охоте/рыбалке'},
    'owl': {'name': '🦉 Мудрая Сова', 'short': '🦉 Сова', 'price': 4800, 'luck_bonus': 60, 'desc': '+60% к удаче в охоте/рыбалке'},
    'raccoon': {'name': '🦝 Енот-Вор', 'short': '🦝 Енот', 'price': 6500, 'luck_bonus': 45, 'desc': '+20% к успеху ограблений'},
    'panda': {'name': '🐼 Панда Ленивец', 'short': '🐼 Панда', 'price': 8000, 'luck_bonus': 50, 'desc': '+35% к бонусу /bonus'},
    'dragon': {'name': '🐉 Маленький Дракон', 'short': '🐉 Дракончик', 'price': 12000, 'luck_bonus': 85, 'desc': '+85% к удаче во всем'},
    'capybara': {'name': '🦦 Капибара Чила', 'short': '🦦 Капибара', 'price': 15000, 'luck_bonus': 90, 'desc': '+90% к удаче, максимальный чилл'},
    'unicorn': {'name': '🦄 Радужный Единорог', 'short': '🦄 Единорог', 'price': 25000, 'luck_bonus': 110, 'desc': '+110% ко всем доходам'},
    'vip_griffin': {'name': '👑 Королевский Грифон', 'short': '👑 Грифон', 'price': 0, 'luck_bonus': 150, 'desc': '+150% ко всей удаче, благословение небес (VIP Питомец за 3 ⭐️)'}
}

ACHIEVEMENTS = {
    'first_msg': {'title': '🌱 Первый шаг', 'desc': 'Отправить первое сообщение в чате', 'stat': 'messages', 'target': 1, 'reward': 50},
    'msg_100': {'title': '💬 Душа чата', 'desc': 'Написать 100 сообщений', 'stat': 'messages', 'target': 100, 'reward': 250},
    'msg_1000': {'title': '🗣 Легенда общения', 'desc': 'Написать 1000 сообщений', 'stat': 'messages', 'target': 1000, 'reward': 1200},
    'msg_5000': {'title': '👑 Король чата', 'desc': 'Написать 5000 сообщений', 'stat': 'messages', 'target': 5000, 'reward': 3500},
    'first_rp': {'title': '🎭 Актерское мастерство', 'desc': 'Использовать первое РП-действие', 'stat': 'rp_actions', 'target': 1, 'reward': 50},
    'rp_50': {'title': '💖 Центр внимания', 'desc': 'Использовать 50 РП-действий', 'stat': 'rp_actions', 'target': 50, 'reward': 500},
    'rp_200': {'title': '🌟 РП-Маэстро', 'desc': 'Использовать 200 РП-действий', 'stat': 'rp_actions', 'target': 200, 'reward': 1500},
    'first_trade': {'title': '📊 Начинающий инвестор', 'desc': 'Совершить первую сделку на бирже', 'stat': 'crypto_trades', 'target': 1, 'reward': 80},
    'crypto_master': {'title': '🐺 Волк с Ня-Стрит', 'desc': 'Совершить 20 сделок на бирже', 'stat': 'crypto_trades', 'target': 20, 'reward': 800},
    'first_marriage': {'title': '💍 Счастливы вместе', 'desc': 'Вступить в законный брак', 'stat': 'marriages', 'target': 1, 'reward': 250},
    'first_biz': {'title': '🏢 Первое предприятие', 'desc': 'Приобрести свой первый бизнес', 'stat': 'biz_bought', 'target': 1, 'reward': 300},
    'biz_all': {'title': '🏰 Бизнес-магнат', 'desc': 'Купить 4 разных бизнеса', 'stat': 'biz_bought', 'target': 4, 'reward': 2500},
    'first_bonus': {'title': '🎁 Первые коины', 'desc': 'Собрать свой первый часовой бонус', 'stat': 'bonuses', 'target': 1, 'reward': 40},
    'bonus_50': {'title': '💎 Бонусный коллекционер', 'desc': 'Собрать 50 часовых бонусов', 'stat': 'bonuses', 'target': 50, 'reward': 800},
    'bonus_150': {'title': '⏳ Хранитель времени', 'desc': 'Собрать 150 часовых бонусов', 'stat': 'bonuses', 'target': 150, 'reward': 2000},
    'first_fish': {'title': '🎣 Начинающий рыбак', 'desc': 'Поймать свою первую рыбу', 'stat': 'fish', 'target': 1, 'reward': 80},
    'fish_25': {'title': '🦈 Морской Волк', 'desc': 'Поймать 25 рыб', 'stat': 'fish', 'target': 25, 'reward': 600},
    'fish_100': {'title': '🌊 Посейдон', 'desc': 'Поймать 100 рыб', 'stat': 'fish', 'target': 100, 'reward': 2200},
    'first_hunt': {'title': '🏹 Начинающий охотник', 'desc': 'Сделать первый успешный выстрел', 'stat': 'hunt', 'target': 1, 'reward': 80},
    'hunt_25': {'title': '🐅 Царь тайги', 'desc': 'Сходить на охоту 25 раз', 'stat': 'hunt', 'target': 25, 'reward': 600},
    'hunt_100': {'title': '🦅 Соколиный глаз', 'desc': 'Сходить на охоту 100 раз', 'stat': 'hunt', 'target': 100, 'reward': 2200},
    'first_transfer': {'title': '🤝 Щедрая душа', 'desc': 'Сделать первый перевод другу', 'stat': 'transfers', 'target': 1, 'reward': 100},
    'transfer_10': {'title': '💳 Меценат', 'desc': 'Сделать 10 переводов друзьям', 'stat': 'transfers', 'target': 10, 'reward': 500},
    'first_game': {'title': '🎲 Начинающий игрок', 'desc': 'Сыграть 1 раз в азартную игру', 'stat': 'games', 'target': 1, 'reward': 80},
    'gamer_50': {'title': '🎰 Мастер азарта', 'desc': 'Сыграть 50 раз в азартные игры', 'stat': 'games', 'target': 50, 'reward': 1000},
    'gamer_200': {'title': '🃏 Легенда Лас-Вегаса', 'desc': 'Сыграть 200 раз в азартные игры', 'stat': 'games', 'target': 200, 'reward': 3000},
    'first_rest': {'title': '🌴 Заслуженный отдых', 'desc': 'Получить свой первый рест', 'stat': 'rests', 'target': 1, 'reward': 150},
    'rest_5': {'title': '🏖 Главный курортник', 'desc': 'Побывать в ресте 5 раз', 'stat': 'rests', 'target': 5, 'reward': 800},
    'rich_1000': {'title': '💰 Богач', 'desc': 'Накопить 1000 Ня-коинов на балансе', 'stat': 'balance_check', 'target': 1000, 'reward': 400},
    'rich_10000': {'title': '🏦 Миллионер', 'desc': 'Накопить 10 000 Ня-коинов на балансе', 'stat': 'balance_check', 'target': 10000, 'reward': 2500},
    'bank_5000': {'title': '📈 Финансовая подушка', 'desc': 'Положить 5000 коинов на депозит в банк', 'stat': 'bank_deposit', 'target': 5000, 'reward': 600},
    'first_case': {'title': '📦 Искатель сокровищ', 'desc': 'Открыть свой первый сундук', 'stat': 'cases_opened', 'target': 1, 'reward': 100},
    'case_10': {'title': '🗝 Мастер сундуков', 'desc': 'Открыть 10 ежедневных кейсов', 'stat': 'cases_opened', 'target': 10, 'reward': 700},
    'first_work': {'title': '💼 Трудяга', 'desc': 'Успешно отработать смену на работе', 'stat': 'work_shifts', 'target': 1, 'reward': 100},
    'work_30': {'title': '🛠 Ветеран труда', 'desc': 'Отработать 30 смен на работе', 'stat': 'work_shifts', 'target': 30, 'reward': 900},
    'first_chromosomes': {'title': '🧬 Генный инженер', 'desc': 'Измерить количество хромосом', 'stat': 'chromosomes_check', 'target': 1, 'reward': 80},
    'chromosomes_20': {'title': '🔬 Профессор генетики', 'desc': 'Измерить хромосомы 20 раз', 'stat': 'chromosomes_check', 'target': 20, 'reward': 500},
    'smeh_10': {'title': '😂 Душа компании', 'desc': 'Получить 10 очков Смехуятинки', 'stat': 'smeh_check', 'target': 10, 'reward': 400},
    'pet_care_20': {'title': '🐾 Заботливый хозяин', 'desc': 'Покормить или искупать питомца 20 раз', 'stat': 'pet_care', 'target': 20, 'reward': 500},
    'first_rob': {'title': '🥷 Карманник', 'desc': 'Совершить ограбление участника', 'stat': 'robs', 'target': 1, 'reward': 100},
    'mines_win': {'title': '💣 Опытный сапёр', 'desc': 'Успешно забрать выигрыш в Сапёре', 'stat': 'mines_wins', 'target': 5, 'reward': 500},
    'wheel_spin': {'title': '🎡 Любимчик Фортуны', 'desc': 'Крутануть Колесо Фортуны 10 раз', 'stat': 'wheel_spins', 'target': 10, 'reward': 600}
}

DAILY_TASKS = {
    0: [('messages', 'Написать 30 сообщений', 30, 60), ('transfer', 'Перевести коины другу', 1, 30), ('bonus', 'Собрать 2 часовых бонуса', 2, 45)],
    1: [('messages', 'Написать 40 сообщений', 40, 70), ('dice', 'Сыграть в кости 3 раза', 3, 50), ('fish', 'Поймать 1 рыбу', 1, 40)],
    2: [('messages', 'Написать 30 сообщений', 30, 60), ('slots', 'Испытать слоты 2 раза', 2, 45), ('iq', 'Измерить IQ', 1, 30)],
    3: [('messages', 'Написать 50 сообщений', 50, 85), ('transfer', 'Перевести коины другу', 1, 30), ('chromosomes', 'Измерить хромосомы', 1, 35)],
    4: [('messages', 'Написать 35 сообщений', 35, 65), ('dice', 'Сыграть в кости 5 раз', 5, 75), ('fat', 'Измерить жир', 1, 30)],
    5: [('messages', 'Написать 45 сообщений', 45, 75), ('bonus', 'Собрать 3 часовых бонуса', 3, 65), ('fish', 'Поймать 2 рыбы', 2, 60)],
    6: [('messages', 'Написать 60 сообщений', 60, 100), ('chromosomes', 'Измерить хромосомы', 1, 40), ('hunt', 'Сходить на охоту 2 раза', 2, 75)],
}

WEEKLY_TASKS = [
    ('messages', 'Написать 250 сообщений за неделю', 250, 220),
    ('fish', 'Поймать 10 рыб за неделю', 10, 180),
    ('hunt', 'Сходить на охоту 10 раз за неделю', 10, 180),
    ('bonus', 'Собрать 15 часовых бонусов', 15, 280),
    ('dice', 'Сыграть в кости 20 раз', 20, 240),
]

RP_ACTIONS = {
    'обнять': {'verb': 'крепко и тепло обнял(а)', 'emoji': '🫂✨', 'karma': 1},
    'поцеловать': {'verb': 'нежно поцеловал(а) в щечку', 'emoji': '💋🌸', 'karma': 2},
    'погладить': {'verb': 'ласково погладил(а) по голове', 'emoji': '🐱💆‍♂️', 'karma': 1},
    'укусить': {'verb': 'сделал(а) игривый кусь за ушко', 'emoji': '🦷😼', 'karma': -1},
    'кусь': {'verb': 'сделал(а) хрустящий кусь', 'emoji': '🐾😈', 'karma': -1},
    'дать пять': {'verb': 'дал(а) звонкую и мощную пятерку', 'emoji': '✋🔥', 'karma': 1},
    'ударить тапком': {'verb': 'с размаху огрел(а) тапком', 'emoji': '🩴💥', 'karma': -3},
    'тапком': {'verb': 'метко запустил(а) тапок в', 'emoji': '🩴🎯', 'karma': -2},
    'похвалить': {'verb': 'искренне похвалил(а) и назвал(а) умничкой', 'emoji': '🌟🥰', 'karma': 2},
    'шлепнуть': {'verb': 'с чувством шлепнул(а)', 'emoji': '🍑👋', 'karma': -1},
    'покормить': {'verb': 'заботливо покормил(а) с ложечки вкусняшкой', 'emoji': '🍰🥄', 'karma': 2},
    'ущипнуть': {'verb': 'аккуратно ущипнул(а) за бочок', 'emoji': '🤏😏', 'karma': -1},
    'утешить': {'verb': 'утешил(а), сказав, что всё обязательно будет хорошо', 'emoji': '🥺🕊', 'karma': 2},
    'чихнуть': {'verb': 'громко чихнул(а) прямо на', 'emoji': '🤧💨', 'karma': -1},
    'задушить в объятиях': {'verb': 'крепко задушил(а) в своих мягких объятиях', 'emoji': '🤗💖', 'karma': 1},
    'дать леща': {'verb': 'выдал(а) звонкого отрезвляющего леща', 'emoji': '🐟👋💥', 'karma': -3},
    'лещ': {'verb': 'отвесил(а) мощного леща', 'emoji': '🐟💥', 'karma': -2},
    'пощекотать': {'verb': 'весело и беспощадно пощекотал(а) за бока', 'emoji': '👐😂', 'karma': 1},
    'укрыть пледом': {'verb': 'заботливо укутал(а) в теплый мягкий плед', 'emoji': '🧶🛏', 'karma': 2},
    'укрыть': {'verb': 'укутал(а) в уютное одеялко', 'emoji': '🛏🧸', 'karma': 1},
    'напоить чаем': {'verb': 'угостил(а) кружечкой согревающего чая с печеньками', 'emoji': '🍵🍪', 'karma': 2},
    'угостить кофе': {'verb': 'приготовил(а) ароматный кофе для', 'emoji': '☕️✨', 'karma': 2},
    'взять за руку': {'verb': 'нежно взял(а) за руку и тепло сжал(а) пальцы', 'emoji': '🤝❤️', 'karma': 1},
    'держать за руку': {'verb': 'крепко держит за руку', 'emoji': '🤝🌸', 'karma': 1},
    'бросить снежок': {'verb': 'слепил(а) круглый снежок и метко запустил(а) в', 'emoji': '❄️🎯', 'karma': -1},
    'плюнуть': {'verb': 'смачно плюнул(а) прямо в лицо', 'emoji': '💦🎯', 'karma': -5},
    'пожать руку': {'verb': 'крепко и с уважением пожал(а) руку', 'emoji': '🤝👔', 'karma': 1},
    'убить': {'verb': 'эпично ликвидировал(а) взглядом и отправил(а) на перерождение', 'emoji': '⚔️💀', 'karma': -5}
}

RP_SOLO_ACTIONS = {
    'умереть': ('трагично упал(а) без сил и сделал(а) вид, что умер(ла)... ⚰️💀', '⚰️'),
    'сдохнуть': ('испустил(а) дух и лежит без движения 💀🪦', '💀'),
    'рип': ('отправился(лась) в мир иной. F в чат... 🕯🕊', '🕯'),
    'грустить': ('сидит в углу комнаты и тихонечко грустит под грустную музыку 🥺💧', '🥺'),
    'плакать': ('заливается горькими слезками 😭🌧', '😭'),
    'танцевать': ('вышел(ла) в центр чата и выдал(а) дикий флекс! 💃🕺✨', '💃'),
    'флексить': ('показывает невероятный стиль и флексит во всю! 🔥😎', '😎'),
    'спать': ('завернулся(лась) в теплое одеялко и сладко уснул(а) 💤🧸', '💤'),
    'лечь спать': ('пошел(ла) баиньки. Всем сладких снов! 🌙😴', '😴'),
    'кушать': ('с аппетитом уплетает вкуснейшую пиццу и сладости 🍕🍰', '🍕'),
    'жрать': ('с жадностью опустошает холодильник чата 🍔🍟😋', '🍔'),
    'пить чай': ('наслаждается чашечкой горячего ароматного чая 🍵🫖', '🍵'),
    'пить кофе': ('бодрится чашечкой крепкого кофе ☕️⚡️', '☕️'),
    'смущаться': ('мило покраснел(а) до кончиков ушей и спрятал(а) личико 👉👈😳', '😳'),
    'радоваться': ('прыгает до потолка от безумного счастья! 🎉🥳🎈', '🥳')
}

ALWAYS_ACTIVE_PATTERNS = {
    r'\bзачем\b': [
        'За мясом! 😼',
        'За мясом! 😹🥩'
    ],
    r'\b(твоя\s+мамка|твоя\s+мама|твою\s+маму|твоя\s+мать|мамулька|маман)\b': [
        'Твоя мама самая лучшая и прекрасная! 🌸💖',
        'Мама — это святое! Давай только с любовью и уважением ✨🥰',
        'Твоя мама чудесный человек! 💐',
        'Мамочке привет и самого доброго дня! 🥞☕️',
        'Передай маме, что она замечательная! 🥐🌷'
    ],
    r'\b(охае|охаё|охайо|охаешечки|охаёшечки|охайоо|охаее)\b': [
        'Охаё! Анимешники в чате! 🎌🌸',
        'Охаёшечки! Доброго утречка/днечка! ☀️🍵',
        'Охаё! А кофе/чай уже заварен? ☕️✨',
        'Доброго утречка, нанамания! 🎏'
    ],
    r'\b(семпай|сенпай|семпайчик|сенпайчик|senpai|sempai)\b': [
        'Семпай заметил тебя! 👉👈🌸',
        'Ох, семпай... Ты такой внимательный! 🥺✨',
        'Семпай, не забудь сделать перерыв и попить чаю! 🍵🥐',
        'Все смотрят только на семпая! 👀✨'
    ],
    r'\b(даттебайо|даттебае|даттебаё)\b': [
        'Наруто, ты ли это?! 🍥🦊',
        'Даттебаё! Мой путь ниндзя — следить за рестами! 🥷✨',
        'Стану Хокаге этого чата, даттебаё! 🍃👑',
        'Расенган в твою ленту! 🌀💥'
    ],
    r'\b(кавай|кавайный|кавайность|кавайка)\b': [
        'Кавайность этого сообщения зашкаливает! 🥺✨',
        'Милота спасает этот чат! 🌸ฅ^•ﻌ•^ฅ',
        'Ну прямо милота 100/10! 🐱💖'
    ],
    r'\b(ня|няшка|някать|нян)\b': [
        'Ня! 🐱🐾',
        'Котодевочки одобряют этот чат! 🐾✨',
        'Ня-ня-ня, всем позитивного дня! 🥐☕️'
    ],
    r'\b(аригато|аригатоо|аригато gozaimasu)\b': [
        'Доитасимасите! (Всегда пожалуйста!) 🙇‍♂️✨',
        'Не за что, обращайся! 🤝🌸',
        'Всегда рад помочь! 🤖❤️'
    ],
    r'\b(ямете|ямете кудасай|яметее)\b': [
        'ЯМЕТЕ КУДАСАЙ!! 😱💥',
        'А вот тут остановись, а то бан прилетит! 🛑🙈'
    ],
    r'\b(десу|десс)\b': [
        'Да, именно так, десу! 🤓✨',
        'Дез-дез-дез! 🌸',
        'Подтверждаю на все 100%, десу! 👌'
    ]
}


# ---------------------------------------------------------
# СЕМЕЙНЫЕ ДОМА И МЕБЕЛЬ (ПАССИВНЫЙ ДОХОД В СЕЙФ СЕМЬИ)
# ---------------------------------------------------------
FAMILY_HOUSES = {
    'moscow': {'name': '🏙 Квартира на Арбате (Москва)', 'price': 15000, 'income': 10, 'city': 'Москва 🇷🇺'},
    'kyiv': {'name': '🏛 Пентхаус на Крещатике (Киев)', 'price': 15000, 'income': 10, 'city': 'Киев 🇺🇦'},
    'bern': {'name': '🏔 Шале в Альпах (Берн, Швейцария)', 'price': 45000, 'income': 35, 'city': 'Берн 🇨🇭'},
    'tokyo': {'name': '🌸 Пагода в Сибуе (Токио)', 'price': 70000, 'income': 60, 'city': 'Токио 🇯🇵'},
    'london': {'name': '🏰 Особняк у Тауэра (Лондон)', 'price': 120000, 'income': 110, 'city': 'Лондон 🇬🇧'}
}

FAMILY_FURNITURE = {
    'fireplace': {'name': '🔥 Уютный камин', 'price': 2500, 'income': 3},
    'sofa': {'name': '🛋 Мягкий велюровый диван', 'price': 1800, 'income': 2},
    'jacuzzi': {'name': '🛁 Джакузи с подсветкой', 'price': 6500, 'income': 8},
    'cinema': {'name': '🎬 Домашний кинотеатр 4K', 'price': 12000, 'income': 15},
    'cat_castle': {'name': '🐱 Игровой замок котика', 'price': 3500, 'income': 5},
    'pool': {'name': '🏊‍♂️ Бассейн во дворе', 'price': 25000, 'income': 30}
}

# ---------------------------------------------------------
# МЕМНЫЕ БОЛЕЗНИ И АПТЕКА
# ---------------------------------------------------------
MEME_DISEASES = {
    'tygydyk': {'name': '🐾 Кошачий тыгыдык', 'suffix': '...тыгыдык-тыгыдык! 🐾', 'cure': 'chamomile_tea'},
    'anime_fever': {'name': '🌸 Острая аниме-зависимость', 'suffix': '...ня! десу~ 🌸', 'cure': 'anti_anime'},
    'lazy_butt': {'name': '💤 Синдром ленивой жопки', 'suffix': '...зевнул(а) и лёг(ла) спать 💤', 'cure': 'energy_shot'},
    'oink': {'name': '🐷 Хрюкающий токсикоз', 'suffix': '...хрю! 🐷', 'cure': 'oink_syrup'},
    'kus_fever': {'name': '😼 Хронический кусь', 'suffix': '...кусь за бочок! 😼', 'cure': 'kus_vaccine'}
}

PHARMACY_ITEMS = {
    'chamomile_tea': {'name': '🍵 Чай с ромашкой', 'price': 50, 'cure': 'tygydyk', 'desc': 'Лечит Кошачий тыгыдык'},
    'anti_anime': {'name': '💊 Таблетка Анти-Аниме', 'price': 60, 'cure': 'anime_fever', 'desc': 'Лечит Аниме-зависимость'},
    'energy_shot': {'name': '💉 Бодрящий укол кофеина', 'price': 70, 'cure': 'lazy_butt', 'desc': 'Лечит Синдром ленивой жопки'},
    'oink_syrup': {'name': '🍯 Сироп «Не хрюкай»', 'price': 50, 'cure': 'oink', 'desc': 'Лечит Хрюканье'},
    'kus_vaccine': {'name': '🩹 Вакцина от куся', 'price': 60, 'cure': 'kus_fever', 'desc': 'Лечит Хронический кусь'},
    'aibolit_panacea': {'name': '🧪 Панацея Айболита', 'price': 150, 'cure': 'all', 'desc': 'Исцеляет от всех болезней + иммунитет на 24 часа!'}
}

# ---------------------------------------------------------
# СЕЗОННЫЙ ХЕЛЛОУИНСКИЙ PASS (BATTLE PASS 30 УРОВНЕЙ)
# ---------------------------------------------------------
HALLOWEEN_BP_LEVELS = 30
HALLOWEEN_BP_EXP_PER_LVL = 100
HALLOWEEN_BP_MAX_LEVEL = 30
HALLOWEEN_BP_MAX_EXP = HALLOWEEN_BP_EXP_PER_LVL * HALLOWEEN_BP_MAX_LEVEL

# ---------------------------------------------------------
# ИГРОВЫЕ СТРУКТУРЫ
# ---------------------------------------------------------
pending_marriages = {}
active_bj_games = {}
active_rps_games = {}
active_drops = {}
active_mines = {}
active_crash = {}
active_brick = {}
active_c_mines = {}
active_durak = {}
active_wanted = {}  # {(chat_id, user_id): wanted_data}
active_pet_fights = {}
active_memes = {}
active_quizzes = {}

gold_rush_event = {'active': False, 'until': 0}
current_quiz = {}

user_flood_history = {}
user_flood_muted = {}
# Лимит команд: отдельная история, чтобы старый антиспам не очищал её.
command_rate_history = {}
last_chat_activity = {}
# ---------------------------------------------------------
# БАЗА ДАННЫХ И АТОМАРНЫЕ БЕКАПЫ
# ---------------------------------------------------------
def _default_data():
    return {
        'rests': {},
        'history': {},
        'settings': {},
        'economy': {},
        'promos': {
            'FIX': {'reward': 5000, 'exp': 100, 'claimed': []},
            'fix': {'reward': 5000, 'exp': 100, 'claimed': []}
        },
        'market': {},
        'marriages': {},
        'lottery': {'tickets': {}, 'pot': 0, 'last_draw': 0},
        'bot_active': True,
        'casino_pool': 1000000,
        'safe': {'code': f"{random.randint(0, 9999):04d}", 'pot': 30000, 'tried_codes': []},
        'daily_memes': [],
        'processed_stars_charges': [],
        'meme_winners': [],
        'chest_claims': {}
    }

def _normalize_loaded_data(data):
    """Keep the same defaults/compatibility rules as the old JSON loader."""
    if not isinstance(data, dict):
        data = {}
    base = _default_data()
    for key in base:
        if key in data:
            base[key] = data[key]
    if not isinstance(base.get('promos'), dict):
        base['promos'] = {}
    if 'FIX' not in base['promos']:
        base['promos']['FIX'] = {'reward': 5000, 'exp': 100, 'claimed': []}
    if 'fix' not in base['promos']:
        base['promos']['fix'] = base['promos']['FIX']
    if 'safe' not in base or not isinstance(base['safe'], dict):
        base['safe'] = {'code': f"{random.randint(0, 9999):04d}", 'pot': 30000, 'tried_codes': []}
    if 'daily_memes' not in base:
        base['daily_memes'] = []
    if 'processed_stars_charges' not in base:
        base['processed_stars_charges'] = []
    if 'meme_winners' not in base:
        base['meme_winners'] = []
    if 'chest_claims' not in base:
        base['chest_claims'] = {}
    return base

def _pg_connect():
    if not DATABASE_URL:
        return None
    return psycopg2.connect(DATABASE_URL, connect_timeout=10)

def _pg_init():
    conn = _pg_connect()
    if conn is None:
        return False
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS bot_state (
                        id SMALLINT PRIMARY KEY,
                        data JSONB NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
        return True
    finally:
        conn.close()

def _pg_load():
    conn = _pg_connect()
    if conn is None:
        return None
    try:
        _pg_init()
        with conn.cursor() as cur:
            cur.execute('SELECT data FROM bot_state WHERE id = 1')
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()

def _pg_save(snapshot):
    conn = _pg_connect()
    if conn is None:
        return False
    try:
        _pg_init()
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO bot_state (id, data, updated_at)
                    VALUES (1, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        data = EXCLUDED.data,
                        updated_at = NOW()
                """, (Json(snapshot),))
        return True
    finally:
        conn.close()

def _load_local_json():
    if not os.path.exists(DATA_FILE):
        return None
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f'[DB] Ошибка чтения локального JSON: {e}')
        return None

def load_data():
    """Load state from Neon first; migrate existing rests_data.json once if Neon is empty."""
    base = _default_data()

    if DATABASE_URL:
        try:
            pg_data = _pg_load()
            if pg_data is not None:
                print('[DB] Загружена база из Neon PostgreSQL.')
                return _normalize_loaded_data(pg_data)

            local_data = _load_local_json()
            if local_data is not None:
                migrated = _normalize_loaded_data(local_data)
                if _pg_save(migrated):
                    print('[DB] Выполнена первичная миграция rests_data.json -> Neon PostgreSQL.')
                return migrated

            print('[DB] Neon пустая, локальная JSON-база не найдена. Создаётся новая база.')
            base = _normalize_loaded_data(base)
            _pg_save(base)
            return base
        except Exception as e:
            print(f'[DB ERROR] Не удалось загрузить Neon: {e}')
            print('[DB] Переключение на локальный JSON как аварийный fallback.')

    local_data = _load_local_json()
    if local_data is not None:
        return _normalize_loaded_data(local_data)

    return _normalize_loaded_data(base)

def mark_dirty():
    global db_dirty, db_version
    db_dirty = True
    db_version += 1

def save_data(send_backup=False):
    global db_dirty
    # PostgreSQL/Neon is the primary store. A local JSON snapshot is kept as a
    # safety fallback, but Telegram channel backups are optional and disabled by default.
    with db_lock:
        snapshot = copy.deepcopy(db)
        snapshot_version = db_version
    try:
        saved_to_pg = False
        if DATABASE_URL:
            try:
                saved_to_pg = _pg_save(snapshot)
                if not saved_to_pg:
                    raise RuntimeError('PostgreSQL недоступен')
            except Exception as e:
                print(f'[DB ERROR] Ошибка сохранения в Neon: {e}')

        temp_file = f"{DATA_FILE}.tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=4)
        os.replace(temp_file, DATA_FILE)

        with db_lock:
            if db_version == snapshot_version and (saved_to_pg or not DATABASE_URL):
                db_dirty = False

        if send_backup and DB_CHANNEL_ID:
            with open(DATA_FILE, 'rb') as f:
                msg = bot.send_document(DB_CHANNEL_ID, f, caption='💾 Экстренный бекап базы данных')
                try:
                    bot.pin_chat_message(DB_CHANNEL_ID, msg.message_id, disable_notification=True)
                except Exception as e:
                    print(f'[BACKUP PIN ERROR] {e}')
    except Exception as e:
        print(f'Ошибка при сохранении базы данных: {e}')

def auto_save_worker():
    global db_dirty
    while True:
        time.sleep(10)
        try:
            finalize_meme_contests()
        except Exception:
            pass
        if db_dirty:
            save_data(send_backup=False)

def periodic_backup_worker():
    # Telegram channel backups are opt-in now. Neon is the primary persistent DB.
    while True:
        time.sleep(900)
        try:
            if DB_CHANNEL_ID and os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'rb') as f:
                    msg = bot.send_document(DB_CHANNEL_ID, f, caption=f"💾 Плановый авто-бекап базы данных [{now_msk().strftime('%d.%m.%Y %H:%M')}]" )
                    try:
                        bot.pin_chat_message(DB_CHANNEL_ID, msg.message_id, disable_notification=True)
                    except Exception as e:
                        print(f'[BACKUP PIN ERROR] {e}')
        except Exception as e:
            print(f'[BACKUP ERROR] Ошибка планового бекапа: {e}')

db = load_data()

def setup_bot_commands():
    commands = [
        BotCommand('menu', '📱 Главное интерактивное меню'),
        BotCommand('profile', '👤 Профиль, баланс и карточка игрока'),
        BotCommand('stars', '⭐️ Звёздный магазин и VIP Pass (Telegram Stars)'),
        BotCommand('profile_settings', '⚙️ Настройки тем, шрифтов и визуала профиля'),
        BotCommand('shop', '🏪 Магазин значков, тем, титулов и расходников'),
        BotCommand('trash', '🗑 Порыться в мусорке в поисках лута'),
        BotCommand('durak', '🃏 Карточная игра Дурак (36 карт)'),
        BotCommand('promo', '🎁 Активировать промокод на коины'),
        BotCommand('stream', '🎥 Запустить трансляцию стримера'),
        BotCommand('garden', '🪴 Ваша личная оранжерея Бонсай'),
        BotCommand('backpack', '🎒 Рюкзак баффов и расходников'),
        BotCommand('crash', '🚀 Игра Краш (Взлетающая ракета)'),
        BotCommand('brick', '🧱 Игра Кирпич (Стройка)'),
        BotCommand('wheel', '🎡 Бесплатное Колесо Фортуны'),
        BotCommand('mines', '💣 Игра Сапёр (Мины)'),
        BotCommand('football', '⚽️ Футбол пенальти'),
        BotCommand('daily_heroes', '🏆 Герои и ударники дня'),
        BotCommand('ball', '🔮 Магический шар предсказаний'),
        BotCommand('chance', '📊 Измеритель шанса и вероятности'),
        BotCommand('detector', '🕵️‍♂️ Детектор правды и лжи'),
        BotCommand('dick', '🍆 Измерить размер писюна'),
        BotCommand('fap', '💦 Сделать ежедневный фап'),
        BotCommand('garage', '🏎 Гараж и личный транспорт'),
        BotCommand('cook', '🍳 Приготовить пойманную еду'),
        BotCommand('walk', '🦮 Отправить питомца на прогулку'),
        BotCommand('bank', '🏦 Ня-Банк и депозиты (+1% / 6ч)'),
        BotCommand('loan', '💳 Взять кредит в банке'),
        BotCommand('case', '📦 Ежедневный бесплатный кейс'),
        BotCommand('chest', '🎁 Ежедневный сундук и серия наград'),
        BotCommand('inventory', '🎒 Коллекция питомцев и косметики'),
        BotCommand('memes', '📸 Мемы дня и рейтинг'),
        BotCommand('top_daily', '🏆 Топ активности за сегодня'),
        BotCommand('top_weekly', '🏆 Топ активности за неделю'),
        BotCommand('lottery', '🎟 Лотерея джекпота'),
        BotCommand('business', '🏢 Бизнесы 2.0 и прокачка'),
        BotCommand('miner', '💻 Криптоферма и майнинг NYA'),
        BotCommand('collect', '💰 Собрать прибыль предприятий'),
        BotCommand('family', '💍 Информация о браке и семье'),
        BotCommand('market', '📈 Крипто-биржа и котировки'),
        BotCommand('work', '💼 Биржа труда и вакансии'),
        BotCommand('pet', '🐾 Ваш питомец и уход'),
        BotCommand('fish', '🎣 Отправиться на рыбалку'),
        BotCommand('hunt', '🏹 Отправиться на охоту'),
        BotCommand('bj', '🃏 Сыграть в Блэкджек (21)'),
        BotCommand('dice', '🎲 Кости'),
        BotCommand('slots', '🎰 Слоты'),
        BotCommand('tasks', '📋 Задания и квесты'),
        BotCommand('top', '🏆 Таблицы лидеров чата'),
        BotCommand('safe', '🔒 Взлом 4-значного сейфа чата'),
        BotCommand('house', '🏡 Семейный дом и обустройство'),
        BotCommand('sheriff', '👮‍♂️ Полиция чата и служба шерифа'),
        BotCommand('jail', '🔒 КПЗ и статус тюрьмы'),
        BotCommand('escape', '🏃‍♂️ Попытка побега из тюрьмы'),
        BotCommand('pet_fight', '⚔️ Подпольные бои питомцев'),
        BotCommand('meme', '📸 Опубликовать мем дня'),
        BotCommand('story', '📜 Смешная история / фанфик про участников'),
        BotCommand('pass', '🎃 Хеллоуинский Боевой Пропуск'),
        BotCommand('pharmacy', '💊 Аптека и лечение мемных болезней'),
        BotCommand('gift_stars', '🎁 Подарить Stars товар другу'),
        BotCommand('settings', '⚙️ Настройки бота в чате')
    ]
    try:
        bot.set_my_commands(commands)
    except Exception as e:
        print(f"Ошибка установки меню команд: {e}")

def clean_tag(user_str):
    if not user_str:
        return 'Пользователь'
    return str(user_str).replace('@', '').strip()

def get_chat_settings(chat_id):
    str_chat = str(chat_id)
    if str_chat not in db['settings']:
        db['settings'][str_chat] = {
            'max_days': None,  # лимит реста отключён
            'rp_enabled': True,
            'flood_protection': False,
            'auto_reactions': True,
            'welcome_enabled': True,
            'timezone_offset': 3,
            'remind_minutes': 60
        }
    else:
        # Новые настройки добавляются без сброса старых параметров.
        sett = db['settings'][str_chat]
        sett.setdefault('rp_enabled', True)
        sett.setdefault('flood_protection', False)
        sett.setdefault('auto_reactions', True)
        sett.setdefault('welcome_enabled', True)
        # Раньше стоял жёсткий лимит 30/60 дней — теперь ограничения нет.
        sett['max_days'] = None
        mark_dirty()
    return db['settings'][str_chat]

def get_market_data():
    if 'market' not in db or not db['market']:
        db['market'] = json.loads(json.dumps(MARKET_DEFAULT))
        save_data()

    market = db['market']
    now = time.time()
    changed = False

    for ticker, info in market.items():
        if now - info.get('last_update', 0) >= 1800:
            old_p = info.get('price', 10.0)
            volatility = info.get('volatility', 0.2)
            pct = random.uniform(-volatility, volatility)
            new_p = round(max(info.get('min_price', 1.0), min(info.get('max_price', 3500.0), old_p * (1 + pct))), 2)
            info['old_price'] = old_p
            info['price'] = new_p
            info['last_update'] = now
            changed = True

    if changed:
        mark_dirty()

    return market

def get_global_user_key(user_id=None, user_tag=None):
    if user_id:
        return f"id_{user_id}"
    if user_tag:
        return f"tag_{clean_tag(user_tag).lower()}"
    return "unknown_user"

def get_account_level(exp):
    lvl = 1
    current_tier_base = 0
    next_tier_exp = 100

    while exp >= next_tier_exp:
        current_tier_base = next_tier_exp
        lvl += 1
        next_tier_exp = int(100 * (lvl ** 1.5))

    in_tier_exp = exp - current_tier_base
    needed_in_tier = max(1, next_tier_exp - current_tier_base)
    percent = min(1.0, in_tier_exp / needed_in_tier)

    filled = int(percent * 8)
    bar = "█" * filled + "░" * (8 - filled)
    return lvl, exp, next_tier_exp, bar

def get_user_cd_reduction(econ):
    if not econ or not isinstance(econ, dict):
        return 0.0
    reduction = 0.0
    veh = econ.get('vehicle')
    if veh and veh in VEHICLES:
        reduction += VEHICLES[veh].get('cd_cut', 0.0)

    active_t = econ.get('active_title')
    if active_t and active_t in TITLES:
        t_info = TITLES[active_t]
        if t_info.get('buff') == 'cd_reduction':
            reduction += (t_info.get('val', 0) / 100.0)

    if econ.get('vip_forever') or (econ.get('vip_until', 0) > time.time()):
        reduction += 0.30

    return min(0.75, max(0.0, reduction))

def cooldown_text(last_time, cooldown, user_econ=None):
    if not last_time:
        return None
    now_ts = time.time()
    reduction = get_user_cd_reduction(user_econ) if user_econ else 0.0
    effective_cooldown = max(1.0, cooldown * (1.0 - reduction))
    elapsed = now_ts - float(last_time)
    left = int(effective_cooldown - elapsed)
    if left <= 0:
        return None

    hours = left // 3600
    minutes = (left % 3600) // 60
    seconds = left % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours} ч")
    if minutes > 0:
        parts.append(f"{minutes} мин")
    if seconds > 0 or not parts:
        parts.append(f"{seconds} сек")
    return " ".join(parts)

def update_pet_stats(pet):
    if not pet:
        return
    now = time.time()
    last_update = pet.get('last_update', now)
    hours_passed = (now - last_update) / 3600.0

    if hours_passed > 0.1:
        pet['hunger'] = max(0, pet.get('hunger', 100) - int(hours_passed * 4))
        pet['cleanliness'] = max(0, pet.get('cleanliness', 100) - int(hours_passed * 3))
        pet['last_update'] = now
        mark_dirty()

def update_bank_interest(econ):
    bank_dep = econ.get('bank_deposit', 0)
    if bank_dep <= 0:
        econ['last_bank_calc'] = time.time()
        return 0

    now = time.time()
    last_calc = econ.get('last_bank_calc', now)
    hours_passed = (now - last_calc) / 3600.0

    periods = int(hours_passed // 6)
    if periods > 0:
        # Считаем сразу за весь прошедший период, чтобы не терять проценты
        # после 120 периодов офлайна.
        new_dep = int(bank_dep * (1.0025 ** periods))  # +0.25% за 6 часов
        earned = new_dep - bank_dep
        econ['bank_deposit'] = new_dep
        econ['last_bank_calc'] = last_calc + (periods * 6 * 3600)
        if earned > 0:
            mark_dirty()
        return earned
    return 0

def merge_user_econ_data(dest, src):
    if not src or not isinstance(src, dict):
        return dest

    for num_field in ['balance', 'bank_deposit', 'account_exp', 'work_exp', 'smeh', 'cooked_meals', 'bonus_streak', 'stars_donated', 'bp_exp']:
        dest[num_field] = dest.get(num_field, 0) + src.get(num_field, 0)

    for ts_field in [
        'last_fish_time', 'last_hunt_time', 'last_work_time', 'last_hourly', 
        'last_train_time', 'last_iq_time', 'last_fat_time', 'last_foot_time', 
        'last_chromosomes_time', 'last_dick_time', 'last_wheel_time', 
        'last_pet_walk', 'last_case_time', 'last_rob_time', 'last_stream_time',
        'luck_clover_until', 'invis_until', 'last_streak_time', 'last_energy_drink_time',
        'last_trash_time', 'vip_until', 'jail_until', 'disease_immunity_until', 'last_safe_try'
    ]:
        dest[ts_field] = max(dest.get(ts_field, 0), src.get(ts_field, 0))

    if src.get('vip_forever'):
        dest['vip_forever'] = True

    v_dest = dest.get('vehicle')
    v_src = src.get('vehicle')
    tier_dest = VEHICLES[v_dest]['tier'] if v_dest in VEHICLES else -1
    tier_src = VEHICLES[v_src]['tier'] if v_src in VEHICLES else -1
    if tier_src > tier_dest:
        dest['vehicle'] = v_src

    for eq in ['equipped_rod', 'equipped_bow', 'active_title', 'custom_title', 'badge', 'profile_theme', 'pfp_file_id', 'profile_font']:
        if not dest.get(eq) and src.get(eq):
            dest[eq] = src[eq]

    if src.get('has_custom_title_cert'):
        dest['has_custom_title_cert'] = True

    for list_field in ['inventory', 'titles', 'rings', 'purchased_themes', 'purchased_fonts', 'achievements', 'paid_stars_items']:
        combined = list(dict.fromkeys(dest.get(list_field, []) + src.get(list_field, [])))
        dest[list_field] = combined

    # Одноразовые Stars-энтитлменты тоже обязаны переживать объединение
    # старого tag_аккаунта с новым id_аккаунтом.
    for bool_field in ['bp_premium', 'has_custom_title_cert', 'vip_forever']:
        if src.get(bool_field):
            dest[bool_field] = True

    for dict_field in ['fish_inventory', 'hunt_inventory']:
        dest_dict = dest.setdefault(dict_field, {})
        for k, v in src.get(dict_field, {}).items():
            dest_dict[k] = dest_dict.get(k, 0) + v

    bp_dest = dest.setdefault('backpack', {})
    for item_k, cnt in src.get('backpack', {}).items():
        bp_dest[item_k] = bp_dest.get(item_k, 0) + cnt

    cp_dest = dest.setdefault('crypto_portfolio', {})
    for coin_k, cnt in src.get('crypto_portfolio', {}).items():
        cp_dest[coin_k] = cp_dest.get(coin_k, 0.0) + cnt

    biz_dest = dest.setdefault('businesses', {})
    biz_src = src.get('businesses', {})
    for b_k, b_v in biz_src.items():
        if b_k not in biz_dest:
            biz_dest[b_k] = b_v

    bl_dest = dest.setdefault('biz_levels', {})
    bl_src = src.get('biz_levels', {})
    for bl_k, bl_v in bl_src.items():
        bl_dest[bl_k] = max(bl_dest.get(bl_k, 1), bl_v)

    if not dest.get('pet') and src.get('pet'):
        dest['pet'] = src['pet']

    if not dest.get('marriage') and src.get('marriage'):
        dest['marriage'] = src['marriage']

    return dest

def get_user_econ(user_id=None, user_tag=None, username=None):
    if 'economy' not in db:
        db['economy'] = {}

    clean_u = clean_tag(username).lower() if username else None
    clean_d = clean_tag(user_tag) if user_tag else None

    if not user_id and clean_u:
        for k, v in list(db['economy'].items()):
            if v.get('username') and v['username'].lower() == clean_u and v.get('user_id'):
                user_id = v['user_id']
                break

    key = get_global_user_key(user_id, user_tag or username)

    if user_id:
        target_tags = []
        if clean_u:
            target_tags.append(clean_u)
        if clean_d:
            target_tags.append(clean_d.lower())

        for tag_candidate in set(target_tags):
            old_tag_key = f"tag_{tag_candidate}"
            if old_tag_key in db['economy'] and old_tag_key != key:
                old_data = db['economy'].pop(old_tag_key)
                if key in db['economy']:
                    merge_user_econ_data(db['economy'][key], old_data)
                else:
                    db['economy'][key] = old_data

    if key not in db['economy']:
        db['economy'][key] = {
            'display_name': clean_d or 'Пользователь',
            'username': clean_u,
            'user_id': user_id,
            'balance': 50,
            'karma': 0
        }
        mark_dirty()

    u_data = db['economy'][key]
    # Integrity check: старый бесплатный VIP-грифон без подтверждённой Stars-покупки больше не считается действительным.
    # Если покупка была совершена в старой версии, stars_donated >= 3 позволяет сохранить питомца; новые покупки
    # всегда получают явный paid_stars_items entitlement.
    pet_state = u_data.get('pet')
    if isinstance(pet_state, dict) and pet_state.get('id') == 'vip_griffin':
        paid_items = u_data.setdefault('paid_stars_items', [])
        if 'pet_griffin' not in paid_items:
            if u_data.get('stars_donated', 0) >= 3:
                paid_items.append('pet_griffin')
                mark_dirty()
            else:
                u_data['pet'] = None
                mark_dirty()
    if clean_d:
        u_data['display_name'] = clean_d
    if clean_u:
        u_data['username'] = clean_u
    if user_id:
        u_data['user_id'] = user_id

    for field, default in [
        ('username', clean_u), ('pfp_file_id', None), ('inventory', []), ('account_exp', 0),
        ('smeh', 0), ('iq', 100), ('fat', 20), ('foot_size', 25), ('dick_size', 15),
        ('last_dick_time', 0), ('fap_count', 0), ('fap_date', ''), ('last_fap_time', 0),
        ('chromosomes', 46), ('last_chromosomes_time', 0), ('last_wheel_time', 0),
        ('last_pet_walk', 0), ('last_pet_care', 0), ('rest_rewards_count', 0),
        ('titles', []), ('active_title', None), ('custom_title', None),
        ('has_custom_title_cert', False), ('rings', []), ('active_ring', None),
        ('marriage', None), ('businesses', {}), ('biz_levels', {}),
        ('last_biz_collect', time.time()), ('vehicle', None),
        ('equipped_rod', None), ('equipped_bow', None), ('daily_tasks_date', ''),
        ('daily_progress', {}), ('daily_claimed', []), ('weekly_tasks_yearweek', ''),
        ('weekly_progress', {}), ('weekly_claimed', []), ('fish_inventory', {}),
        ('hunt_inventory', {}), ('cooked_meals', 0), ('crypto_portfolio', {}),
        ('last_fish_time', 0), ('last_hunt_time', 0), ('achievements', []),
        ('stats', {}), ('work_exp', 0), ('last_work_time', 0), ('last_train_time', 0),
        ('pet', None), ('paid_stars_items', []), ('chest_streak', 0), ('bank_deposit', 0), ('last_bank_calc', time.time()),
        ('last_case_time', 0), ('last_rob_time', 0), ('last_trash_time', 0),
        ('profile_theme', 'default'), ('purchased_themes', ['default']),
        ('profile_font', 'default'), ('purchased_fonts', ['default']),
        ('backpack', {'energy_drink': 0, 'luck_clover': 0, 'alarm_system': 0, 'invis_mask': 0, 'garden_fertilizer': 0}),
        ('luck_clover_until', 0), ('invis_until', 0), ('daily_casino_win', 0),
        ('daily_casino_profit', 0), ('daily_transferred', 0), ('daily_stats_date', ''),
        ('karma', 0), ('chat_ids', []), ('garden', None), ('stream_studio', {'mic': 1, 'webcam': 1, 'light': 1}), 
        ('last_stream_time', 0), ('last_cmd_time', 0), ('last_cmd_text', ""),
        ('loan', {'amount': 0, 'due': 0, 'defaulted': False}),
        ('bonus_streak', 0), ('last_streak_time', 0),
        ('last_energy_drink_time', 0), ('vip_until', 0), ('vip_forever', False), ('stars_donated', 0), ('is_sheriff', False), ('jail_until', 0), ('disease', None), ('disease_immunity_until', 0), ('bp_exp', 0), ('bp_claimed_free', []), ('bp_claimed_prem', []), ('bp_premium', False), ('last_safe_try', 0)
    ]:
        if field not in u_data:
            u_data[field] = default

    if 'msg_stats' not in u_data:
        u_data['msg_stats'] = {
            'day_date': '', 'day_count': 0, 'week_key': '',
            'week_count': 0, 'month_key': '', 'month_count': 0, 'total_count': 0
        }

    today_str = now_msk().strftime('%Y-%m-%d')
    if u_data.get('daily_stats_date') != today_str:
        u_data['daily_stats_date'] = today_str
        u_data['daily_casino_win'] = 0
        u_data['daily_casino_profit'] = 0
        u_data['daily_transferred'] = 0
        mark_dirty()

    update_bank_interest(u_data)

    if u_data.get('pet'):
        update_pet_stats(u_data['pet'])

    return u_data

def change_karma(user_id, user_tag, amount, username=None):
    econ = get_user_econ(user_id, user_tag, username=username)
    econ['karma'] = max(-100, min(100, econ.get('karma', 0) + amount))
    mark_dirty()
    return econ['karma']

def add_account_exp(user_id, user_tag, exp_amount=1, username=None):
    econ = get_user_econ(user_id, user_tag, username)
    active_t = econ.get('active_title')
    bonus = 1.0
    if active_t and active_t in TITLES and TITLES[active_t].get('buff') == 'exp_bonus':
        bonus += (TITLES[active_t]['val'] / 100.0)

    econ['account_exp'] = econ.get('account_exp', 0) + int(exp_amount * bonus)
    mark_dirty()

def add_message_stat(user_id, user_tag, username=None):
    econ = get_user_econ(user_id, user_tag, username)
    m_stats = econ.setdefault('msg_stats', {})
    now = now_msk()

    today_str = now.strftime('%Y-%m-%d')
    week_str = f"{now.year}-W{now.isocalendar()[1]}"
    month_str = now.strftime('%Y-%m')

    if m_stats.get('day_date') != today_str:
        m_stats['day_date'] = today_str
        m_stats['day_count'] = 0

    if m_stats.get('week_key') != week_str:
        m_stats['week_key'] = week_str
        m_stats['week_count'] = 0

    if m_stats.get('month_key') != month_str:
        m_stats['month_key'] = month_str
        m_stats['month_count'] = 0

    m_stats['day_count'] = m_stats.get('day_count', 0) + 1
    m_stats['week_count'] = m_stats.get('week_count', 0) + 1
    m_stats['month_count'] = m_stats.get('month_count', 0) + 1
    m_stats['total_count'] = m_stats.get('total_count', 0) + 1

    add_account_exp(user_id, user_tag, 2, username)

def add_coins(user_id=None, user_tag=None, amount=0, username=None):
    user_data = get_user_econ(user_id, user_tag, username)
    user_data['balance'] += amount
    mark_dirty()
    check_achievements(user_id, user_tag, 'balance_check', 0, username=username)
    return user_data['balance']

def check_casino_limits(econ, bet, is_multiplayer=False):
    return True


def get_chat_safe(chat_id):
    """Return a safe state isolated per chat."""
    safe_root = db.setdefault('safe', {})
    # Backward compatibility: migrate legacy global safe into the current chat once.
    if 'code' in safe_root or 'pot' in safe_root or 'tried_codes' in safe_root:
        legacy = safe_root.copy()
        db['safe'] = {}
        if chat_id is not None:
            db['safe'][str(chat_id)] = legacy
        safe_root = db['safe']
    key = str(chat_id)
    safe = safe_root.setdefault(key, {
        'code': f"{random.randint(0, 9999):04d}",
        'pot': 30000,
        'tried_codes': []
    })
    safe.setdefault('code', f"{random.randint(0, 9999):04d}")
    safe.setdefault('pot', 30000)
    safe.setdefault('tried_codes', [])
    return safe

def add_to_safe_pot(amount, chat_id=None):
    # Если вызывающий код не передал чат, сохраняем старую совместимость через
    # глобальный ключ, но новые вызовы должны передавать chat_id.
    if chat_id is None:
        chat_id = 0
    safe = get_chat_safe(chat_id)
    add_amount = max(1, int(amount * 0.5))
    safe['pot'] = safe.get('pot', 30000) + add_amount
    mark_dirty()

def update_family_house_income(marriage_data):
    if not marriage_data or not isinstance(marriage_data, dict):
        return 0
    house_id = marriage_data.get('house')
    if not house_id or house_id not in FAMILY_HOUSES:
        marriage_data['last_house_calc'] = time.time()
        return 0
    now = time.time()
    last_calc = marriage_data.get('last_house_calc', now)
    hours_passed = (now - last_calc) / 3600.0
    if hours_passed < 0.1:
        return 0
    hourly_rate = FAMILY_HOUSES[house_id]['income']
    for furn in marriage_data.get('furniture', []):
        if furn in FAMILY_FURNITURE:
            hourly_rate += FAMILY_FURNITURE[furn]['income']
    earned = int(hourly_rate * hours_passed)
    if earned > 0:
        marriage_data['vault'] = marriage_data.get('vault', 0) + earned
        marriage_data['last_house_calc'] = now
        mark_dirty()
    return earned

def is_in_jail(user_id):
    econ = get_user_econ(user_id=user_id)
    jail_until = econ.get('jail_until', 0)
    if jail_until > time.time():
        left_min = max(1, int((jail_until - time.time()) // 60))
        return True, left_min
    return False, 0

def get_user_bp_level(bp_exp):
    # После 30 уровня прогресс больше не зацикливается.
    bp_exp = max(0, int(bp_exp or 0))
    if bp_exp >= HALLOWEEN_BP_MAX_EXP:
        return HALLOWEEN_BP_MAX_LEVEL, HALLOWEEN_BP_EXP_PER_LVL, HALLOWEEN_BP_EXP_PER_LVL, "🎃" * 8
    lvl = min(HALLOWEEN_BP_MAX_LEVEL, (bp_exp // HALLOWEEN_BP_EXP_PER_LVL) + 1)
    in_lvl_exp = bp_exp % HALLOWEEN_BP_EXP_PER_LVL
    pct = min(1.0, in_lvl_exp / float(HALLOWEEN_BP_EXP_PER_LVL))
    bar_len = int(pct * 8)
    bar = "🎃" * bar_len + "🕸" * (8 - bar_len)
    return lvl, in_lvl_exp, HALLOWEEN_BP_EXP_PER_LVL, bar

def add_bp_exp(user_id, user_tag, amount=5, username=None):
    econ = get_user_econ(user_id, user_tag, username=username)
    econ['bp_exp'] = econ.get('bp_exp', 0) + amount
    mark_dirty()

def try_infect_user(user_id, user_tag, disease_id=None, chance=0.03):
    econ = get_user_econ(user_id, user_tag)
    now = time.time()
    if econ.get('disease') or econ.get('disease_immunity_until', 0) > now:
        return None
    if random.random() <= chance:
        if not disease_id:
            disease_id = random.choice(list(MEME_DISEASES.keys()))
        econ['disease'] = disease_id
        mark_dirty()
        return MEME_DISEASES[disease_id]['name']
    return None

def process_casino_bet(bet, chat_id=None):
    db['casino_pool'] = max(10000, db.get('casino_pool', 1000000) + max(0, bet))
    add_to_safe_pot(bet, chat_id=chat_id)
    mark_dirty()

def process_casino_win(win):
    if win <= 0:
        return 0
    pool = max(10000, db.get('casino_pool', 1000000))
    actual_win = max(1, min(win, pool))
    db['casino_pool'] = max(10000, pool - actual_win)
    mark_dirty()
    return actual_win

def can_process_user_message(message):
    if message and getattr(message, 'chat', None):
        if is_chat_banned(message.chat.id):
            try:
                bot.leave_chat(message.chat.id)
            except Exception:
                pass
            return False

    if not message or not getattr(message, 'from_user', None):
        return False

    user_id = message.from_user.id
    user_username = (message.from_user.username or '').lower()
    is_super_admin = (user_id == ADMIN_ID)

    # Запоминаем чаты, где пользователь реально встречался. Это позволяет
    # строить чатовые топы без смешивания участников разных чатов.
    try:
        econ = get_user_econ(user_id=user_id, user_tag=message.from_user.username or message.from_user.first_name, username=message.from_user.username)
        chat_ids = econ.setdefault('chat_ids', [])
        cid = int(message.chat.id)
        if cid not in chat_ids:
            chat_ids.append(cid)
            mark_dirty()
    except Exception as e:
        print(f"[CHAT TRACK ERROR] {e}")

    bot_is_active = db.get('bot_active', True)
    if not bot_is_active and not is_super_admin:
        return False

    return True

def log_event(event_type, message_text):
    if not LOG_CHANNEL_ID:
        return
    try:
        clean_text = str(message_text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        clean_text = re.sub(r'&lt;b&gt;(.*?)&lt;/b&gt;', r'<b>\1</b>', clean_text, flags=re.DOTALL)
        clean_text = re.sub(r'&lt;code&gt;(.*?)&lt;/code&gt;', r'<code>\1</code>', clean_text, flags=re.DOTALL)
        clean_text = re.sub(r'&lt;a href="(.*?)"&gt;(.*?)&lt;/a&gt;', r'<a href="\1">\2</a>', clean_text, flags=re.DOTALL)

        full_msg = f"📌 <b>[{html.escape(event_type)}]</b>\n⏱ <i>{now_msk().strftime('%Y-%m-%d %H:%M:%S')}</i>\n\n{clean_text}"
        bot.send_message(LOG_CHANNEL_ID, full_msg, parse_mode='HTML')
    except Exception as e:
        print(f"[LOG ERROR] Не удалось отправить лог: {e}")

def check_achievements(user_id, user_tag, stat_name, amount=1, chat_id=None, username=None):
    econ = get_user_econ(user_id, user_tag, username)
    stats = econ.setdefault('stats', {})
    unlocked = econ.setdefault('achievements', [])

    if stat_name == 'balance_check':
        stats['balance_check'] = econ.get('balance', 0)
    elif stat_name == 'bank_deposit':
        stats['bank_deposit'] = econ.get('bank_deposit', 0)
    elif stat_name == 'smeh_check':
        stats['smeh_check'] = econ.get('smeh', 0)
    else:
        stats[stat_name] = stats.get(stat_name, 0) + amount

    unlocked_new = []

    for ach_id, ach_info in ACHIEVEMENTS.items():
        if ach_id not in unlocked:
            req_stat = ach_info['stat']
            target_val = ach_info['target']
            current_val = stats.get(req_stat, 0)

            if current_val >= target_val:
                unlocked.append(ach_id)
                reward = ach_info['reward']
                econ['balance'] += reward
                add_account_exp(user_id, user_tag, 50, username)
                unlocked_new.append((ach_info['title'], ach_info['desc'], reward))

    if unlocked_new:
        mark_dirty()
        if chat_id:
            u_link = make_link(chat_id, user_tag, user_id, ping=True)
            for title, desc, reward in unlocked_new:
                msg = (
                    f"🏆 <b>НОВОЕ ДОСТИЖЕНИЕ РАЗБЛОКИРОВАНО!</b>\n"
                    f"──────────────────────\n"
                    f"👤 Игрок: {u_link}\n"
                    f"🎖 <b>{title}</b>\n"
                    f"📜 <i>{desc}</i>\n"
                    f"💰 Награда: <b>+{reward} Ня-коинов 🪙</b> (+50 EXP)\n"
                    f"──────────────────────"
                )
                try:
                    bot.send_message(chat_id, msg, parse_mode='HTML')
                except Exception:
                    pass

def daily_task_date():
    return now_msk().strftime('%Y-%m-%d')

def weekly_task_key():
    now = now_msk()
    return f"{now.year}-W{now.isocalendar()[1]}"

def get_daily_tasks(user_id=None, user_tag=None, username=None):
    econ = get_user_econ(user_id, user_tag, username)
    today = daily_task_date()
    if econ.get('daily_tasks_date') != today:
        econ['daily_tasks_date'] = today
        econ['daily_progress'] = {}
        econ['daily_claimed'] = []
    return DAILY_TASKS[now_msk().weekday()], econ

def get_weekly_tasks(user_id=None, user_tag=None, username=None):
    econ = get_user_econ(user_id, user_tag, username)
    w_key = weekly_task_key()
    if econ.get('weekly_tasks_yearweek') != w_key:
        econ['weekly_tasks_yearweek'] = w_key
        econ['weekly_progress'] = {}
        econ['weekly_claimed'] = []
    return WEEKLY_TASKS, econ

def track_daily_task(user_id, user_tag, task_key, amount=1, chat_id=None, username=None):
    completed = []
    check_achievements(user_id, user_tag, task_key, amount, chat_id, username=username)

    tasks, econ = get_daily_tasks(user_id, user_tag, username)
    progress = econ.setdefault('daily_progress', {})
    progress[task_key] = progress.get(task_key, 0) + amount

    for key, description, target, reward in tasks:
        if key not in econ.get('daily_claimed', []) and progress.get(key, 0) >= target:
            econ.setdefault('daily_claimed', []).append(key)
            econ['balance'] += reward
            add_account_exp(user_id, user_tag, 25, username)
            completed.append((f"Ежедневное: {description}", reward))

    w_tasks, _ = get_weekly_tasks(user_id, user_tag, username)
    w_progress = econ.setdefault('weekly_progress', {})
    w_progress[task_key] = w_progress.get(task_key, 0) + amount

    for key, description, target, reward in w_tasks:
        if key not in econ.get('weekly_claimed', []) and w_progress.get(key, 0) >= target:
            econ.setdefault('weekly_claimed', []).append(key)
            econ['balance'] += reward
            add_account_exp(user_id, user_tag, 100, username)
            completed.append((f"Еженедельное: {description}", reward))

    if completed:
        mark_dirty()
    return completed

def format_daily_tasks(user_id, user_tag):
    tasks, econ = get_daily_tasks(user_id, user_tag)
    w_tasks, _ = get_weekly_tasks(user_id, user_tag)
    weekdays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']

    lines = [
        f"📋 <b>ЗАДАНИЯ И КВЕСТЫ — {weekdays[now_msk().weekday()].upper()}</b>",
        "──────────────────────",
        "☀️ <b>Ежедневные квесты:</b>"
    ]
    for key, description, target, reward in tasks:
        current = min(econ.get('daily_progress', {}).get(key, 0), target)
        done = key in econ.get('daily_claimed', [])
        status = '✅' if done else '🔄'
        lines.append(f"{status} {description}: <b>{current}/{target}</b> (<b>+{reward} 🪙</b>)")

    lines.append("\n📅 <b>Еженедельные квесты:</b>")
    for key, description, target, reward in w_tasks:
        current = min(econ.get('weekly_progress', {}).get(key, 0), target)
        done = key in econ.get('weekly_claimed', [])
        status = '✅' if done else '🔄'
        lines.append(f"{status} {description}: <b>{current}/{target}</b> (<b>+{reward} 🪙</b>)")
    lines.append("──────────────────────")

    return '\n'.join(lines)

def add_inventory_item(inventory, item_name):
    inventory[item_name] = inventory.get(item_name, 0) + 1

def make_link(chat_id, user_name, user_id=None, ping=True):
    name = clean_tag(user_name)
    badge_str = ""
    title_str = ""
    user_econ = get_user_econ(user_id, user_name)

    if user_econ.get('badge'):
        badge_str = f" [{user_econ['badge']}]"

    if user_econ.get('custom_title'):
        title_str = f" [{html.escape(str(user_econ['custom_title']))}]"
    else:
        active_title = user_econ.get('active_title')
        if active_title in TITLES:
            title_str = f" [{TITLES[active_title]['text']}]"

    if not ping:
        return f'<b>{html.escape(name)}</b>{badge_str}{title_str}'

    if user_id:
        return f'<a href="tg://user?id={user_id}">{html.escape(name)}</a>{badge_str}{title_str}'
    return f'<b>{html.escape(name)}</b>{badge_str}{title_str}'

def is_admin(chat_id, user_id):
    # В личном чате Telegram не предоставляет статуса администратора:
    # доступ должен быть только у владельца/ADMIN_ID.
    if user_id == ADMIN_ID:
        return True
    try:
        chat_id = int(chat_id)
    except (TypeError, ValueError):
        return False
    if chat_id > 0:
        return False
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except Exception:
        return False

def resolve_user_from_string(chat_id, query_str):
    if not query_str:
        return None, None

    query = query_str.strip()

    m_tg = re.search(r'tg://(?:openmessage\?user_id=|user\?id=)(\d+)', query)
    if m_tg:
        uid = int(m_tg.group(1))
        econ = get_user_econ(user_id=uid)
        return uid, econ.get('display_name', f"ID:{uid}")

    if query.isdigit() and len(query) >= 5:
        uid = int(query)
        econ = get_user_econ(user_id=uid)
        return uid, econ.get('display_name', f"ID:{uid}")

    m_tme = re.search(r'(?:https?://)?t\.me/([a-zA-Z0-9_]{3,32})', query)
    if m_tme:
        query = m_tme.group(1)

    clean_q = query.replace('@', '').strip().lower()
    str_chat = str(chat_id)

    if 'economy' in db:
        for k, v in list(db['economy'].items()):
            u_name = v.get('username')
            if u_name and u_name.lower() == clean_q and v.get('user_id'):
                return v['user_id'], v.get('display_name', query.replace('@', '').strip())

    if 'economy' in db:
        for k, v in list(db['economy'].items()):
            uid = v.get('user_id')
            if uid and str(uid) == clean_q:
                return uid, v.get('display_name', f"ID:{uid}")

    if 'economy' in db:
        for k, v in list(db['economy'].items()):
            disp = v.get('display_name', '').lower()
            if disp == clean_q or clean_tag(disp).lower() == clean_q:
                return v.get('user_id'), v.get('display_name')

    if str_chat in db.get('rests', {}):
        for r_key, r_info in list(db['rests'][str_chat].items()):
            rec_uid = r_info.get('user_id')
            rec_name = r_info.get('user_name', r_key)
            if str(rec_uid) == clean_q or rec_name.lower() == clean_q or r_key.lower() == clean_q:
                return rec_uid, rec_name

    if str_chat in db.get('history', {}):
        for hist_user, items in list(db['history'][str_chat].items()):
            if hist_user.lower() == clean_q:
                for item in reversed(items):
                    if item.get('user_id'):
                        return item.get('user_id'), hist_user
                return None, hist_user

    return None, query.replace('@', '').strip()

def check_user_rest(chat_rests, user_id=None, user_name=None):
    if not chat_rests:
        return False, None, None

    u_id_str = str(user_id) if user_id else None
    u_name_clean = user_name.strip().lower() if user_name else None

    for r_key, r_info in list(chat_rests.items()):
        rec_uid = str(r_info.get('user_id', '')) if r_info.get('user_id') else None
        rec_name = r_info.get('user_name', r_key).strip().lower()

        if u_id_str and (rec_uid == u_id_str or r_key == u_id_str):
            return True, r_info, r_key

        if u_name_clean:
            if rec_name == u_name_clean or r_key.lower() == u_name_clean:
                return True, r_info, r_key
            if clean_tag(rec_name).lower() == clean_tag(u_name_clean).lower():
                return True, r_info, r_key

    return False, None, None

def parse_rest_command(message):
    text = message.text.strip() if message.text else ''
    body = re.sub(r'^\+рест\s*', '', text, flags=re.IGNORECASE).strip()

    if message.reply_to_message:
        u = message.reply_to_message.from_user
        target_name = (f"{u.first_name or ''} {u.last_name or ''}").strip() or (u.username or "Пользователь")
        target_id = u.id

        if '|' in body:
            parts = [p.strip() for p in body.split('|') if p.strip()]
            duration = parts[0] if parts else '3 дня'
            reason = " | ".join(parts[1:]) if len(parts) > 1 else 'Не указана'
        else:
            d_match = re.search(DURATION_PATTERN, body, re.IGNORECASE)
            if d_match:
                duration = d_match.group(0)
                reason = body.replace(duration, '').strip() or 'Не указана'
            else:
                duration = '3 дня'
                reason = body or 'Не указана'
        return target_name, target_id, duration, reason

    m_tg = re.search(r'tg://(?:openmessage\?user_id=|user\?id=)(\d+)', body)
    if m_tg:
        target_id = int(m_tg.group(1))
        econ = get_user_econ(user_id=target_id)
        target_name = econ.get('display_name', f"ID:{target_id}")
        clean_body = body.replace(m_tg.group(0), '').strip()
        if '|' in clean_body:
            parts = [p.strip() for p in clean_body.split('|') if p.strip()]
            duration = parts[0] if parts else '3 дня'
            reason = " | ".join(parts[1:]) if len(parts) > 1 else 'Не указана'
        else:
            d_match = re.search(DURATION_PATTERN, clean_body, re.IGNORECASE)
            if d_match:
                duration = d_match.group(0)
                reason = clean_body.replace(duration, '').strip() or 'Не указана'
            else:
                duration = '3 дня'
                reason = clean_body or 'Не указана'
        return target_name, target_id, duration, reason

    m_tag = re.search(r'@([a-zA-Z0-9_]{3,32})', body)
    if m_tag:
        raw_tag = m_tag.group(1)
        uid, uname = resolve_user_from_string(message.chat.id, raw_tag)
        target_name = uname or raw_tag
        target_id = uid
        clean_body = body.replace(m_tag.group(0), '').strip()
        if '|' in clean_body:
            parts = [p.strip() for p in clean_body.split('|') if p.strip()]
            duration = parts[0] if parts else '3 дня'
            reason = " | ".join(parts[1:]) if len(parts) > 1 else 'Не указана'
        else:
            d_match = re.search(DURATION_PATTERN, clean_body, re.IGNORECASE)
            if d_match:
                duration = d_match.group(0)
                reason = clean_body.replace(duration, '').strip() or 'Не указана'
            else:
                duration = '3 дня'
                reason = clean_body or 'Не указана'
        return target_name, target_id, duration, reason

    if '|' in body:
        parts = [p.strip() for p in body.split('|') if p.strip()]
        if len(parts) >= 3:
            if re.search(DURATION_PATTERN, parts[0], re.IGNORECASE):
                target_raw = parts[-1]
                duration = parts[0]
                reason = " | ".join(parts[1:-1])
            else:
                target_raw = parts[0]
                duration = parts[1]
                reason = " | ".join(parts[2:])
            uid, uname = resolve_user_from_string(message.chat.id, target_raw)
            return uname or target_raw, uid, duration, reason
        elif len(parts) == 2:
            d0 = re.search(DURATION_PATTERN, parts[0], re.IGNORECASE)
            if d0:
                duration = d0.group(0)
                target_raw = parts[0].replace(duration, '').strip()
                reason = parts[1]
                if not target_raw:
                    target_raw = parts[1]
                    reason = 'Не указана'
                uid, uname = resolve_user_from_string(message.chat.id, target_raw)
                return uname or target_raw, uid, duration, reason
            else:
                target_raw = parts[0]
                d1 = re.search(DURATION_PATTERN, parts[1], re.IGNORECASE)
                if d1:
                    duration = d1.group(0)
                    reason = parts[1].replace(duration, '').strip() or 'Не указана'
                else:
                    duration = '3 дня'
                    reason = parts[1] or 'Не указана'
                uid, uname = resolve_user_from_string(message.chat.id, target_raw)
                return uname or target_raw, uid, duration, reason

    d_match = re.search(DURATION_PATTERN, body, re.IGNORECASE)
    if d_match:
        duration = d_match.group(0)
        target_raw = body.replace(duration, '').strip()
        uid, uname = resolve_user_from_string(message.chat.id, target_raw)
        return uname or target_raw, uid, duration, 'Не указана'

    uid, uname = resolve_user_from_string(message.chat.id, body)
    return uname or body, uid, '3 дня', 'Не указана'

def parse_target_and_args(message, cmd_prefix):
    text = message.text.strip() if message.text else ''
    target_user = None
    target_user_id = None
    raw_args = ''

    if message.reply_to_message:
        u = message.reply_to_message.from_user
        target_user = (f"{u.first_name or ''} {u.last_name or ''}").strip() or (u.username or "Пользователь")
        target_user_id = u.id
        m = re.search(f'{re.escape(cmd_prefix)}\\s*(.*)', text, re.IGNORECASE)
        if m:
            raw_args = m.group(1).strip()
        return target_user, target_user_id, raw_args

    m_body = re.search(f'{re.escape(cmd_prefix)}\\s+(.+)', text, re.IGNORECASE)
    if not m_body:
        return None, None, ''

    body = m_body.group(1).strip()

    m_tg = re.search(r'tg://(?:openmessage\?user_id=|user\?id=)(\d+)', body)
    if m_tg:
        target_user_id = int(m_tg.group(1))
        econ = get_user_econ(user_id=target_user_id)
        target_user = econ.get('display_name', f"ID:{target_user_id}")
        raw_args = body.replace(m_tg.group(0), '').strip()
        return target_user, target_user_id, raw_args

    m_tag = re.search(r'@([a-zA-Z0-9_]{3,32})', body)
    if m_tag:
        raw_name = m_tag.group(1)
        uid, uname = resolve_user_from_string(message.chat.id, raw_name)
        target_user = uname or raw_name
        target_user_id = uid
        raw_args = body.replace(m_tag.group(0), '').strip()
        return target_user, target_user_id, raw_args

    m_digits = re.search(r'\b\d+\b', body)
    if m_digits:
        raw_args = m_digits.group(0)
        potential_name = body.replace(raw_args, '').strip()
        if potential_name:
            uid, uname = resolve_user_from_string(message.chat.id, potential_name)
            return uname or potential_name, uid, raw_args

    uid, uname = resolve_user_from_string(message.chat.id, body)
    return uname or body, uid, ''

def parse_transfer_command(message):
    text = message.text.strip() if message.text else ''
    body = re.sub(r'^(?:/pay|перевод|передать|отправить|скинуть)\s*', '', text, flags=re.IGNORECASE).strip()

    if message.reply_to_message:
        u = message.reply_to_message.from_user
        target_id = u.id
        target_name = (f"{u.first_name or ''} {u.last_name or ''}").strip() or u.username or "Пользователь"
        clean_body = re.sub(r'@[a-zA-Z0-9_]{3,32}', '', body).strip()
        m_amt = re.search(r'\b(\d+)\b', clean_body)
        amount = int(m_amt.group(1)) if m_amt else 0
        return target_id, target_name, amount

    m_num_first = re.match(r'^(\d+)\s+(.+)$', body)
    if m_num_first:
        amount = int(m_num_first.group(1))
        raw_target = m_num_first.group(2).strip()
        uid, uname = resolve_user_from_string(message.chat.id, raw_target)
        return uid, uname or raw_target, amount

    m_target_first = re.match(r'^(.+)\s+(\d+)$', body)
    if m_target_first:
        raw_target = m_target_first.group(1).strip()
        amount = int(m_target_first.group(2))
        uid, uname = resolve_user_from_string(message.chat.id, raw_target)
        return uid, uname or raw_target, amount

    return None, None, 0

def parse_duration_to_seconds(duration_str, chat_id=None):
    duration_str = duration_str.lower().strip()
    duration_str = re.sub(r'^до\s+', '', duration_str)

    indefinite_markers = (
        'на неопределённый срок', 'на неопределенный срок',
        'неопределённый срок', 'неопределенный срок',
        'бессрочно', 'без срока', 'навсегда'
    )
    if any(marker in duration_str for marker in indefinite_markers):
        return None

    match_rel = re.search(r'(\d+)\s*(дней|дня|день|д|часов|часа|час|ч|минут|мин|м)\b', duration_str)
    if match_rel:
        val = int(match_rel.group(1))
        unit = match_rel.group(2)
        if unit in ['д', 'день', 'дня', 'дней']: sec = val * 86400
        elif unit in ['ч', 'час', 'часа', 'часов']: sec = val * 3600
        elif unit in ['м', 'мин', 'минут']: sec = val * 60
        else: sec = 0

        if chat_id:
            sett = get_chat_settings(chat_id)
            max_days = sett.get('max_days')
            if max_days is not None:
                max_sec = max_days * 86400
                if sec > max_sec:
                    return max_sec
        return sec

    match_date = re.search(r'(\d{1,2})[\.\/](\d{1,2})(?:[\.\/](\d{2,4}))?', duration_str)
    if match_date:
        day = int(match_date.group(1))
        month = int(match_date.group(2))
        year = int(match_date.group(3)) if match_date.group(3) else now_msk().year
        if year < 100: year += 2000
        try:
            target_dt = datetime(year, month, day, 23, 59, 59, tzinfo=MSK_TZ)
            now = now_msk()
            if target_dt < now and not match_date.group(3):
                target_dt = datetime(year + 1, month, day, 23, 59, 59, tzinfo=MSK_TZ)
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
            year = now_msk().year
            try:
                target_dt = datetime(year, month, day, 23, 59, 59, tzinfo=MSK_TZ)
                now = now_msk()
                if target_dt < now:
                    target_dt = datetime(year + 1, month, day, 23, 59, 59, tzinfo=MSK_TZ)
                diff = (target_dt - now).total_seconds()
                return max(diff, 0)
            except ValueError:
                pass
    return 259200  # Дефолт 3 дня при нераспознанном сроке

def add_to_history(chat_str, user, duration_text, reason, user_id=None, action_type="Выдан рест"):
    if chat_str not in db['history']:
        db['history'][chat_str] = {}
    clean_user = clean_tag(user)
    if clean_user not in db['history'][chat_str]:
        db['history'][chat_str][clean_user] = []
    entry = {
        'date': now_msk().strftime('%Y-%m-%d %H:%M'),
        'action': action_type,
        'duration': duration_text,
        'reason': reason,
        'user_id': user_id,
    }
    db['history'][chat_str][clean_user].append(entry)
    mark_dirty()

def rest_manager_worker():
    notified_reminders = set()
    while True:
        time.sleep(10)
        try:
            now_ts = time.time()
            if 'rests' not in db: continue
            for str_chat_id, rests_dict in list(db['rests'].items()):
                chat_id = int(str_chat_id)
                sett = get_chat_settings(chat_id)
                remind_sec = sett.get('remind_minutes', 60) * 60

                for r_key, info in list(rests_dict.items()):
                    end_time = info.get('end_time')
                    if not end_time: continue

                    remaining = end_time - now_ts
                    target_user_id = info.get('user_id')
                    u_name = info.get('user_name', r_key)
                    remind_id = f"{str_chat_id}_{r_key}_{int(end_time)}"

                    if remaining <= 0:
                        del rests_dict[r_key]
                        add_to_history(str_chat_id, u_name, 'Истек', 'Снятие по таймеру', target_user_id, "Снят рест (авто)")
                        mark_dirty()
                        u_link = make_link(chat_id, u_name, target_user_id, ping=True)
                        log_event('РЕСТ СНЯТ (АВТО)', f'Чат: <code>{chat_id}</code>\nПользователь: {u_link}\nСтатус: Время реста истекло.')
                        try:
                            bot.send_message(chat_id, f'⏰ <b>Время реста для {u_link} истекло!</b> Рест автоматически снят. 😺', parse_mode='HTML')
                        except Exception:
                            pass
                        continue

                    if 0 < remaining <= remind_sec and remind_id not in notified_reminders:
                        notified_reminders.add(remind_id)
                        mins = int(remind_sec / 60)
                        u_link = make_link(chat_id, u_name, target_user_id, ping=True)
                        try:
                            bot.send_message(chat_id, f'🔔 <b>Напоминание:</b> Рест у {u_link} закончится через {mins} мин! 😺', parse_mode='HTML')
                        except Exception:
                            pass
        except Exception as e:
            print(f"[REST WORKER ERROR] {e}")

def apply_rest(chat_id, user_name, duration_text, reason='Не указана', target_user_id=None):
    str_chat = str(chat_id)
    if str_chat not in db['rests']:
        db['rests'][str_chat] = {}
    clean_user = clean_tag(user_name)
    seconds = parse_duration_to_seconds(duration_text, chat_id)
    is_indefinite = any(marker in duration_text.lower() for marker in ('на неопределённый срок', 'бессрочно', 'навсегда'))
    end_time = (time.time() + seconds) if seconds else None
    display_duration = 'на неопределённый срок' if is_indefinite else duration_text
    rest_key = str(target_user_id) if target_user_id else clean_user

    db['rests'][str_chat][rest_key] = {
        'duration': display_duration,
        'reason': reason,
        'end_time': end_time,
        'user_id': target_user_id,
        'user_name': clean_user
    }
    add_to_history(str_chat, clean_user, duration_text, reason, target_user_id, "Выдан рест")

    econ = get_user_econ(target_user_id, clean_user)
    reward_given = False
    if econ['rest_rewards_count'] < 5:
        econ['balance'] += 150
        econ['rest_rewards_count'] += 1
        reward_given = True

    check_achievements(target_user_id, clean_user, 'rests', 1, chat_id)
    mark_dirty()
    log_event('РЕСТ ВЫДАН', f'Чат: <code>{chat_id}</code>\nПользователь: {make_link(chat_id, clean_user, target_user_id, ping=False)}\nСрок: <b>{duration_text}</b>\nПричина: {reason}')
    return reward_given, econ['rest_rewards_count']

# ---------------------------------------------------------
# БЕЗОПАСНЫЙ КАЛЬКУЛЯТОР ДЛЯ ЧАТА
# ---------------------------------------------------------
def safe_calculate_math(expr_str):
    if len(expr_str) > 60: return None
    clean_expr = expr_str.strip().replace('×', '*').replace('÷', '/').replace(':', '/')
    if not re.match(r'^[\d\s\+\-\*\/\%\(\)\.]+$', clean_expr): return None
    try:
        tree = ast.parse(clean_expr, mode='eval')
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Num, 
                                     ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.USub, ast.UAdd)):
                return None
        res = eval(compile(tree, filename='', mode='eval'), {"__builtins__": None}, {})
        if isinstance(res, (int, float)):
            if abs(res) > 1e14: return None
            if isinstance(res, float) and res.is_integer(): return int(res)
            return round(res, 4)
    except Exception:
        return None

# ---------------------------------------------------------
# ФОНОВЫЕ ПОТОКИ: ОЧИСТКА ПАМЯТИ, ЛИХОРАДКА (1.5 ЧАСА)
# ---------------------------------------------------------
def memory_and_debt_worker():
    while True:
        time.sleep(15)  # Проверка каждые 15 сек для точного таймера лобби
        now = time.time()
        try:
            # Авто-удаление лобби Дурака через 10 минут (600 секунд) если игра не собралась
            for d_k in list(active_durak.keys()):
                d_game = active_durak[d_k]
                if not d_game.get('started') and (now - d_game.get('start_time', now) > 600):
                    chat_id_lobby = d_game.get('chat_id')
                    msg_id_lobby = d_game.get('msg_id')
                    bet_lobby = d_game.get('bet', 0)
                    for pl in d_game.get('players', []):
                        if pl['id'] != 'bot' and bet_lobby > 0:
                            add_coins(pl['id'], pl.get('name'), bet_lobby)
                    if chat_id_lobby and msg_id_lobby:
                        try: bot.delete_message(chat_id_lobby, msg_id_lobby)
                        except Exception as e: print(f"[NONFATAL ERROR] {e}")
                    del active_durak[d_k]

            for dict_ref in [active_crash, active_mines, active_bj_games, active_rps_games, active_brick, active_c_mines, active_durak]:
                for k in list(dict_ref.keys()):
                    game_obj = dict_ref[k]
                    if now - game_obj.get('start_time', now) > 900:
                        bet_amt = game_obj.get('bet', 0)
                        if bet_amt > 0 and not game_obj.get('finished', False):
                            if dict_ref is active_rps_games:
                                if game_obj.get('p1_id'): add_coins(game_obj['p1_id'], game_obj.get('p1_tag'), bet_amt)
                                if game_obj.get('p2_id'): add_coins(game_obj['p2_id'], game_obj.get('p2_tag'), bet_amt)
                            elif dict_ref is active_durak:
                                for p in game_obj.get('players', []):
                                    if p.get('id') and p['id'] != 'bot':
                                        add_coins(p['id'], p.get('name'), bet_amt)
                            elif game_obj.get('user_id'):
                                add_coins(game_obj['user_id'], game_obj.get('user_name') or game_obj.get('user_tag'), bet_amt)
                        del dict_ref[k]

            for k in list(pending_marriages.keys()):
                if now - pending_marriages[k].get('start_time', now) > 900:
                    del pending_marriages[k]

            for k in list(active_drops.keys()):
                if now - int(k.split('_')[1]) > 1800:
                    del active_drops[k]

            # Очистка устаревших записей антифлуда (защита от утечки памяти)
            for uid in list(user_flood_muted.keys()):
                if now > user_flood_muted[uid]:
                    user_flood_muted.pop(uid, None)
            for uid in list(user_flood_history.keys()):
                user_flood_history[uid] = [t for t in user_flood_history[uid] if now - t <= 5.0]
                if not user_flood_history[uid]:
                    user_flood_history.pop(uid, None)
            for key in list(command_rate_history.keys()):
                command_rate_history[key] = [t for t in command_rate_history[key] if now - t < 3600]
                if not command_rate_history[key]:
                    command_rate_history.pop(key, None)

            # Коллекторы по кредитам (исправлено списание депозита)
            for key, econ in list(db.get('economy', {}).items()):
                loan = econ.get('loan')
                if loan and loan.get('amount', 0) > 0 and now > loan.get('due', 0) and not loan.get('defaulted'):
                    amount = loan['amount']
                    pocket = econ.get('balance', 0)
                    bank_dep = econ.get('bank_deposit', 0)
                    total_funds = pocket + bank_dep
                    if total_funds >= amount:
                        from_pocket = min(pocket, amount)
                        econ['balance'] -= from_pocket
                        econ['bank_deposit'] = max(0, bank_dep - (amount - from_pocket))
                        econ['loan'] = {'amount': 0, 'due': 0, 'defaulted': False}
                    else:
                        econ['loan']['amount'] = max(0, amount - total_funds)
                        econ['balance'] = 0
                        econ['bank_deposit'] = 0
                        econ['loan']['defaulted'] = True
                        econ['karma'] = max(-100, econ.get('karma', 0) - 20)
                    mark_dirty()
        except Exception as e:
            print(f"[MEMORY WORKER ERROR] {e}")

def vd_facts_worker():
    while True:
        time.sleep(random.randint(7200, 14400))
        try:
            if VD_CHAT_ID and not is_chat_banned(VD_CHAT_ID):
                title, desc = random.choice(VD_FACTS)
                msg_text = (
                    "🩸 <b>ИНТЕРЕСНЫЙ ФАКТ | VIOLENCE DISTRICT</b> 🔪\n"
                    "──────────────────────\n"
                    f"📌 <b>{title}</b>\n"
                    f"📖 <i>{desc}</i>\n"
                    "──────────────────────\n"
                    "💡 <i>Хотите еще? Введите в чате:</i> <code>факт вд</code> 😺"
                )
                bot.send_message(VD_CHAT_ID, msg_text, parse_mode='HTML')
        except Exception:
            pass

def gold_rush_worker():
    global gold_rush_event
    while True:
        time.sleep(random.randint(14400, 28800))
        try:
            gold_rush_event['active'] = True
            gold_rush_event['until'] = time.time() + 5400
            rush_msg = (
                "🌟🔥 <b>ВНИМАНИЕ! НАЧАЛАСЬ «ЗОЛОТАЯ ЛИХОРАДКА»!</b> 🔥🌟\n"
                "──────────────────────\n"
                "⏳ <b>Длительность:</b> 1.5 часа (90 минут)!\n"
                "🎣 <b>Рыбалка и Охота:</b> Шанс редкой и легендарной добычи увеличен в <b>2 РАЗА</b>! 😻\n"
                "💰 <b>Скупщик:</b> Повышенные цены на продажу улова (<code>/sell</code>)!\n"
                "──────────────────────\n"
                "<i>Хватайте снасти и отправляйтесь на /fish и /hunt прямо сейчас!</i> 😺"
            )
            active_chats = [cid for cid in db.get('settings', {}).keys() if int(cid) < 0]
            for str_chat_id in active_chats:
                try:
                    bot.send_message(int(str_chat_id), rush_msg, parse_mode='HTML')
                    time.sleep(0.05)
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
            
            time.sleep(5400)
            gold_rush_event['active'] = False
            end_msg = "⏱ <b>Золотая лихорадка завершилась!</b> Спасибо всем за активную добычу! 🏕 😸"
            for str_chat_id in active_chats:
                try:
                    bot.send_message(int(str_chat_id), end_msg, parse_mode='HTML')
                    time.sleep(0.05)
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
        except Exception:
            pass

def random_chat_drops_worker():
    while True:
        time.sleep(random.randint(5400, 9000))
        try:
            active_chats = [cid for cid in db.get('settings', {}).keys() if int(cid) < 0]
            if not active_chats: continue
            target_chat = int(random.choice(active_chats))
            reward = random.randint(60, 250)
            drop_id = f"drop_{int(time.time())}_{random.randint(100, 999)}"
            active_drops[drop_id] = {'chat_id': target_chat, 'reward': reward, 'claimed': False}
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🎁 Забрать подарок! 😻", callback_data=f"claim_{drop_id}"))
            msg_text = (
                "📦 <b>ВНЕЗАПНЫЙ ДРОП В ЧАТЕ!</b> 😺\n"
                "──────────────────────\n"
                f"На полу чата найдена коробка с <b>{reward} Ня-коинами 🪙</b>!\n"
                "Кто первый нажмёт кнопку ниже — заберёт всю награду себе! 😸"
            )
            bot.send_message(target_chat, msg_text, reply_markup=markup, parse_mode='HTML')
        except Exception:
            pass

def market_news_worker():
    news_templates = [
        ("🚀 <b>ЭКСТРЕННЫЕ НОВОСТИ БИРЖИ!</b>\nКрупный венчурный фонд инвестировал 10,000,000 в <b>{name}</b>! Курс взлетает! 😻", 'pump', 0.25, 0.45),
        ("🔥 <b>ПАМП НА НЯ-СТРИТ!</b>\nПопулярный блогер выпустил обзор на <b>{name}</b>! Монета летит на Луну! 😺", 'pump', 0.20, 0.35),
        ("📉 <b>ОБВАЛ РЫНКА!</b>\nХакеры совершили атаку на смарт-контракт <b>{name}</b>! Панические распродажи! 🙀", 'dump', 0.20, 0.35),
        ("⚠️ <b>РЕГУЛЯТОРЫ В ДЕЛЕ!</b>\nВведены новые ограничения на торговлю <b>{name}</b>! Временная просадка курса! 😿", 'dump', 0.15, 0.30)
    ]
    while True:
        time.sleep(random.randint(7200, 14400))
        try:
            market = get_market_data()
            ticker = random.choice(list(market.keys()))
            asset = market[ticker]
            template, mode, min_pct, max_pct = random.choice(news_templates)
            pct = random.uniform(min_pct, max_pct)
            old_p = asset['price']
            if mode == 'pump': new_p = round(min(asset.get('max_price', 3500.0), old_p * (1 + pct)), 2)
            else: new_p = round(max(asset.get('min_price', 1.0), old_p * (1 - pct)), 2)
            asset['old_price'] = old_p
            asset['price'] = new_p
            asset['last_update'] = time.time()
            mark_dirty()
            news_text = template.format(name=asset['name']) + f"\n\n📊 Новый курс <b>{ticker}</b>: <b>{new_p:.2f} 🪙</b> (Было: {old_p:.2f} 🪙) 😸"
            active_chats = [cid for cid in db.get('settings', {}).keys() if int(cid) < 0]
            for str_chat_id in active_chats:
                try:
                    bot.send_message(int(str_chat_id), news_text, parse_mode='HTML')
                    time.sleep(0.05)
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
        except Exception:
            pass

def chat_quiz_worker():
    quiz_questions = [
        ("🧮 <b>БЫСТРАЯ МАТЕМАТИКА</b>\nСколько будет: <code>45 + 18 * 3</code>?", "99", 150),
        ("🧮 <b>БЫСТРАЯ МАТЕМАТИКА</b>\nСколько будет: <code>150 - 45 * 2</code>?", "60", 120),
        ("🧮 <b>БЫСТРАЯ МАТЕМАТИКА</b>\nСколько будет: <code>12 * 12 + 6</code>?", "150", 140),
        ("🩸 <b>ВИКТОРИНА VIOLENCE DISTRICT</b>\nКакой самый первый маньяк появился в игре?", "джейсон", 200),
        ("🩸 <b>ВИКТОРИНА VIOLENCE DISTRICT</b>\nИз какой игры вдохновлена карта «Крыша больницы милосердия»?", "left 4 dead", 220),
        ("🩸 <b>ВИКТОРИНА VIOLENCE DISTRICT</b>\nСкином на какого маньяка стал Саймон из Cry of Fear?", "джефф", 200),
        ("🔤 <b>АНАГРАММА</b>\nСоберите слово из букв: <b>К О И Н Е М Е Т</b>", "экономика", 180),
        ("🔤 <b>АНАГРАММА</b>\nСоберите слово из букв: <b>Р Е С Т О П У К</b>", "проступок", 180),
        ("🎬 <b>УГАДАЙ ФИЛЬМ ПО ЭМОДЗИ</b>\n🚢 🧊 👩‍❤️‍👨 🎻", "титаник", 180),
        ("🎬 <b>УГАДАЙ ФИЛЬМ ПО ЭМОДЗИ</b>\n🧙‍♂️ 🧝‍♂️ 💍 🌋 👁", "властелин колец", 220),
    ]
    while True:
        time.sleep(random.randint(4800, 8400))
        try:
            active_chats = [cid for cid in db.get('settings', {}).keys() if int(cid) < 0]
            if not active_chats: continue
            target_chat = int(random.choice(active_chats))
            q_data = random.choice(quiz_questions)
            current_quiz[target_chat] = {'question': q_data[0], 'answer': q_data[1].lower().strip(), 'reward': q_data[2], 'chat_id': target_chat}
            msg_text = (
                "⚡️ <b>ЭКСПРЕСС-ВИКТОРИНА В ЧАТЕ!</b> 😺\n"
                "──────────────────────\n"
                f"{q_data[0]}\n\n"
                f"💰 Награда первому верному ответу: <b>+{q_data[2]} Ня-коинов 🪙</b> 😻\n"
                "──────────────────────\n"
                "<i>Просто напишите правильный ответ в чат!</i> 😸"
            )
            bot.send_message(target_chat, msg_text, parse_mode='HTML')
        except Exception:
            pass

def chat_silence_worker():
    silence_prompts = [
        "👀 В чате так тихо... Колитесь, кто чем сейчас занят? ☕️✨",
        "🐾 Котики напоминают: сделайте глоток водички, расправьте плечи и улыбнитесь! 🌸 😺",
        "💭 Мысль часа: если кошка легла на клавиатуру — это не лень, это технический перерыв! 🐱🛋 😸",
        "🎲 Чат спит, а ракета в <code>/crash</code> и рулетка в <code>/wheel</code> ждут победителей! 🔥 😻",
        "💬 Всем отличного настроения и продуктивного дня! Не забывайте заглядывать в <code>/tasks</code> 📋 😺"
    ]
    while True:
        time.sleep(3600)
        try:
            now = time.time()
            active_chats = [int(cid) for cid in db.get('settings', {}).keys() if int(cid) < 0]
            for cid in active_chats:
                last_act = last_chat_activity.get(cid, now)
                if now - last_act >= 18000:
                    last_chat_activity[cid] = now
                    bot.send_message(cid, random.choice(silence_prompts), parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")

def start_background_threads():
    leave_banned_chats()
    threading.Thread(target=vd_facts_worker, daemon=True).start()
    threading.Thread(target=gold_rush_worker, daemon=True).start()
    threading.Thread(target=random_chat_drops_worker, daemon=True).start()
    threading.Thread(target=market_news_worker, daemon=True).start()
    threading.Thread(target=chat_quiz_worker, daemon=True).start()
    threading.Thread(target=chat_silence_worker, daemon=True).start()
    threading.Thread(target=periodic_backup_worker, daemon=True).start()
    threading.Thread(target=auto_save_worker, daemon=True).start()
    threading.Thread(target=rest_manager_worker, daemon=True).start()
    threading.Thread(target=memory_and_debt_worker, daemon=True).start()

# ---------------------------------------------------------
# ПРИВЕТСТВИЕ И ПРОЩАНИЕ
# ---------------------------------------------------------
@bot.message_handler(content_types=['new_chat_members'])
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

# ---------------------------------------------------------
# ГЛАВНОЕ МЕНЮ И СПРАВОЧНИК
# ---------------------------------------------------------
@bot.message_handler(commands=['start', 'help', 'menu', 'info'])
def send_welcome(message):
    if not can_process_user_message(message):
        return
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📚 ЧИТАТЬ ПОЛНЫЙ ГАЙД В TELETYPE 🌐", url="https://teletype.in/@ukrgorilka/Nya")
    )
    
    welcome_text = (
        "🤖 <b>ГЛАВНЫЙ НАВИГАТОР НЯ-БОТА</b> 😺\n"
        "──────────────────────\n"
        "Добро пожаловать! Все команды, механики экономики, рестов, бизнесов и игр собраны в официальном руководстве: 😻\n\n"
        "📖 <b>Официальный Teletype гайд:</b>\n"
        "👉 https://teletype.in/@ukrgorilka/Nya\n\n"
        "🎁 <b>Активируйте промокод:</b> <code>/promo FIX</code> на <b>5,000 🪙</b>!\n"
        "\n💰 <b>БЫСТРЫЕ РУССКИЕ КОМАНДЫ</b>\n"
        "• <code>баланс</code> / <code>профиль</code> / <code>магазин</code>\n"
        "• <code>передать 10000</code> — ответом на сообщение\n"
        "• <code>передать @username 10000</code> — перевод игроку\n"
        "• <code>банк</code> / <code>банк положить 5000</code> / <code>банк снять 5000</code>\n"
        "• <code>кредит 5000</code> / <code>погасить</code> / <code>кейс</code> / <code>задания</code>\n"
        "• <code>работа</code> / <code>бизнес</code> / <code>прибыль</code> / <code>сад</code>\n"
        "• <code>топ</code> / <code>ачивки</code> / <code>инвентарь</code>\n"
        "\n💡 <i>Есть крутые идеи или нашли баг? Напишите создателю:</i> @ukrgorilka ✨\n"
        "──────────────────────\n"
        "👇 <i>Нажмите кнопку ниже, чтобы открыть статью:</i> 😸"
    )
    try:
        bot.reply_to(message, welcome_text, reply_markup=markup, parse_mode='HTML')
    except Exception:
        pass

# ---------------------------------------------------------
# ОБРАБОТЧИК ФАКТОВ VIOLENCE DISTRICT
# ---------------------------------------------------------
@bot.message_handler(commands=['fact_vd', 'vd_fact'])
def cmd_fact_vd(message):
    if not can_process_user_message(message):
        return
    title, desc = random.choice(VD_FACTS)
    msg_text = (
        "🩸 <b>ИНТЕРЕСНЫЙ ФАКТ | VIOLENCE DISTRICT</b> 🔪 😺\n"
        "──────────────────────\n"
        f"📌 <b>{title}</b>\n"
        f"📖 <i>{desc}</i>\n"
        "──────────────────────\n"
        "💡 <i>Хотите еще? Напишите:</i> <code>факт вд</code> 😸"
    )
    try:
        bot.reply_to(message, msg_text, parse_mode='HTML')
    except Exception:
        pass

# ---------------------------------------------------------
# МУСОРКА (/trash)
# ---------------------------------------------------------
TRASH_LOOT = [
    ('empty', 'Ничего, кроме пустой ржавой банки и старой газеты... 😿', 0),
    ('coins_small', 'горсточку мелочи! (+25 🪙) 🪙', 25),
    ('coins_med', 'кошелёк с забытыми коинами! (+80 🪙) 💰', 80),
    ('coins_big', 'чьи-то спрятанные сбережения! (+250 🪙) 💵', 250),
    ('fertilizer', 'пакет питательного Супер-Удобрения для сада! 🧪', 'fertilizer'),
    ('energy', 'почти полную баночку Энергетика Red Cat! ⚡️', 'energy_drink'),
    ('fish', 'завёрнутую в кулёк свежую рыбку! 🐟', 'fish'),
    ('boots', 'вполне крепкие старые кроссовки! (сданы за 40 🪙) 👟', 40),
    ('watch', 'старинные золотые часы! Проданы скупщику за 450 🪙 ⏱', 450)
]

@bot.message_handler(commands=['trash', 'мусорка', 'помойка'])
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
    msg_text = f"🗑 <b>РАСКОПКИ В МУСОРКЕ</b> 😺\n──────────────────────\n{u_link} порылся(лась) в мусорных баках чата и нашёл(ла):\n👉 <b>{l_desc}</b>"

    if l_type.startswith('coins') or l_type in ['boots', 'watch']:
        econ['balance'] += l_val
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
    msg_text += f"\n──────────────────────\n💰 Баланс: <b>{econ['balance']} 🪙</b> 😸"
    bot.reply_to(message, msg_text, parse_mode='HTML')

# ---------------------------------------------------------
# ПРОМОКОДЫ (/promo FIX)
# ---------------------------------------------------------
@bot.message_handler(commands=['promo', 'промо', 'промокод'])
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
    econ['balance'] += reward
    add_account_exp(user_id, user_name, exp_bonus, username=message.from_user.username)
    claimed_list.append(user_id)
    mark_dirty()

    log_event('ПРОМОКОД АКТИВИРОВАН', f'Игрок {make_link(message.chat.id, user_name, user_id, ping=False)} активировал промокод <b>{code_upper}</b> на +{reward} 🪙!')

    bot.reply_to(
        message,
        f"🎉 <b>ПРОМОКОД УСПЕШНО АКТИВИРОВАН!</b> 😻\n"
        f"──────────────────────\n"
        f"Код: <b>{html.escape(code_upper)}</b>\n"
        f"💰 Начислено: <b>+{reward} Ня-коинов 🪙</b>!\n"
        f"⭐ Получено: <b>+{exp_bonus} EXP опыта профиля</b>!\n"
        f"💵 Новый баланс: <b>{econ['balance']} 🪙</b> 😸\n"
        f"──────────────────────",
        parse_mode='HTML'
    )

# ---------------------------------------------------------
# ИГРА КИРПИЧ (/brick)
# ---------------------------------------------------------
@bot.message_handler(commands=['brick', 'кирпич'])
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

    econ['balance'] -= bet
    process_casino_bet(bet, chat_id)
    
    game_id = f"brick_{user_id}_{time.time_ns()}"
    active_brick[game_id] = {
        'user_id': user_id,
        'user_name': user_name,
        'username': message.from_user.username,
        'bet': bet,
        'step': 0,
        'mults': [1.0, 1.15, 1.35, 1.65, 2.1, 2.7, 3.5, 4.5],
        'risks': [0.0, 0.12, 0.22, 0.32, 0.42, 0.52, 0.65, 0.78],
        'start_time': time.time(),
        'finished': False
    }

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🏗 Сделать шаг на стройке", callback_data=f"brick_step_{game_id}:{user_id}"))

    bot.send_message(
        message.chat.id,
        f"🧱 <b>ИГРА КИРПИЧ (СТРОЙКА)</b> 😺\n"
        f"──────────────────────\n"
        f"👤 Строитель: {make_link(message.chat.id, user_name, user_id, ping=False)}\n"
        f"💰 Ставка: <b>{bet} 🪙</b>\n"
        f"📈 Текущий множитель: <b>1.00x</b>\n"
        f"──────────────────────\n"
        f"<i>Делайте шаги, чтобы увеличить множитель, но осторожно: кирпич может сорваться в любой момент!</i> 😸",
        reply_markup=markup,
        parse_mode='HTML'
                             )
    # ---------------------------------------------------------
# ИГРА КРАШ (/crash)
# ---------------------------------------------------------
def crash_game_thread(game_id, chat_id, message_id, user_id, user_name, bet, crash_point):
    steps = [1.03, 1.08, 1.15, 1.25, 1.38, 1.55, 1.75, 2.00, 2.35, 2.80, 3.40, 4.20, 5.20, 6.50, 8.00, 10.00]
    
    for mult in steps:
        time.sleep(1.2)
        game = active_crash.get(game_id)
        if not game or game.get('cashed_out') or game.get('exploded'):
            return

        if mult >= crash_point:
            game['exploded'] = True
            game['finished'] = True
            try:
                bot.edit_message_text(
                    f"💥 <b>КРАШ! РАКЕТА ВЗОРВАЛАСЬ НА {crash_point:.2f}x!</b> 🙀\n\n"
                    f"👤 Пилот: {make_link(chat_id, user_name, user_id, ping=False)}\n"
                    f"💸 Ставка <b>{bet} Ня-коинов 🪙</b> сгорела в атмосфере... 😿",
                    chat_id=chat_id,
                    message_id=message_id,
                    parse_mode='HTML'
                )
            except Exception:
                pass
            active_crash.pop(game_id, None)
            return

        game['current_mult'] = mult
        cashout_amt = int(bet * mult)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(f"💰 Забрать куш ({cashout_amt} 🪙 | {mult:.2f}x) 😻", callback_data=f"crash_cashout_{game_id}:{user_id}"))

        bar_len = min(8, int(mult * 1.5))
        sky_bar = "☁️" * (8 - bar_len) + "🚀" + "🔥" * bar_len

        try:
            bot.edit_message_text(
                f"🚀 <b>ИГРА КРАШ (CRASH ROCKET)</b> 😺\n"
                f"──────────────────────\n"
                f"👤 Пилот: {make_link(chat_id, user_name, user_id, ping=False)}\n"
                f"💰 Ставка: <b>{bet} 🪙</b>\n"
                f"📈 Текущий множитель: <b>{mult:.2f}x</b>\n"
                f"🛰 Полет: [{sky_bar}]\n"
                f"──────────────────────\n"
                f"<i>Успейте зафиксировать выигрыш до взрыва ракеты!</i> 😸",
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=markup,
                parse_mode='HTML'
            )
        except Exception:
            pass

@bot.message_handler(commands=['crash', 'краш', 'ракета'])
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

    econ['balance'] -= bet
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
            f"──────────────────────\n"
            f"💥 <b>РАКЕТА ВЗОРВАЛАСЬ НА СТАРТЕ (1.00x)!</b> 🙀\n\n"
            f"👤 Пилот: {make_link(message.chat.id, user_name, user_id, ping=False)}\n"
            f"💸 Ваша ставка <b>{bet} Ня-коинов 🪙</b> моментально сгорела в атмосфере... 😿",
            parse_mode='HTML'
        )
        del active_crash[game_id]
        return

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"💰 Забрать куш ({bet} 🪙 | 1.00x) 😻", callback_data=f"crash_cashout_{game_id}:{user_id}"))

    sent_msg = bot.send_message(
        message.chat.id,
        f"🚀 <b>ИГРА КРАШ (CRASH ROCKET)</b> 😺\n"
        f"──────────────────────\n"
        f"👤 Пилот: {make_link(message.chat.id, user_name, user_id, ping=False)}\n"
        f"💰 Ставка: <b>{bet} 🪙</b>\n"
        f"📈 Запуск двигателей... [🚀☁️☁️☁️☁️☁️☁️]\n"
        f"──────────────────────\n"
        f"<i>Приготовьтесь забрать куш!</i> 😸",
        reply_markup=markup,
        parse_mode='HTML'
    )

    t = threading.Thread(target=crash_game_thread, args=(game_id, message.chat.id, sent_msg.message_id, user_id, user_name, bet, crash_point))
    t.daemon = True
    t.start()

# ---------------------------------------------------------
# СИМУЛЯТОР СТРИМЕРА (/stream)
# ---------------------------------------------------------
def stream_thread(chat_id, user_id, user_name, genre, message_id):
    econ = get_user_econ(user_id, user_name)
    studio = econ.get('stream_studio', {'mic': 1, 'webcam': 1, 'light': 1})
    
    base_viewers = (studio.get('mic', 1) + studio.get('webcam', 1) + studio.get('light', 1)) * 40
    viewers = base_viewers + random.randint(10, 80)
    
    text = (
        f"🔴 <b>СТРИМ ЗАПУЩЕН!</b> 😺\n"
        f"──────────────────────\n"
        f"👤 Стример: {make_link(chat_id, user_name, user_id, ping=False)}\n"
        f"🎮 Жанр: <b>{genre}</b>\n\n"
        f"<i>Зрители подключаются... (👁 {viewers})</i> 😸"
    )
    try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode='HTML')
    except Exception as e: print(f"[NONFATAL ERROR] {e}")
    
    time.sleep(3)
    
    event_roll = random.random()
    if event_roll < 0.3:
        event = "🔥 Чат сходит с ума от ваших шуток! 😹"
        viewers = int(viewers * 1.4)
    elif event_roll < 0.6:
        event = "💰 Крупный донатер скинул солидную сумму! 😻"
    elif event_roll < 0.8:
        event = "🎉 RAID от популярного стримера! 🙀"
        viewers = int(viewers * 2.0)
    else:
        event = "📉 Интернет лагает, часть зрителей ушла... 😿"
        viewers = int(viewers * 0.75)
        
    text += f"\n\n⚡️ <b>Событие:</b> {event}\n<i>(👁 {viewers} зрителей)</i>"
    try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode='HTML')
    except Exception as e: print(f"[NONFATAL ERROR] {e}")
        
    time.sleep(3)
    
    donates = int(viewers * random.uniform(0.4, 1.2))
    if 'Трэш-ток' in genre.title(): karma_diff = -2
    else: karma_diff = 1
        
    change_karma(user_id, user_name, karma_diff)
    econ['balance'] += donates
    mark_dirty()
    
    k_sign = "+" if karma_diff > 0 else ""
    text += (
        f"\n\n🏁 <b>СТРИМ ЗАВЕРШЕН!</b> 😺\n"
        f"──────────────────────\n"
        f"💸 Заработано донатов: <b>+{donates} 🪙</b> 😻\n"
        f"⚖️ Влияние на Карму: <b>{k_sign}{karma_diff}</b> 😸"
    )
    try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode='HTML')
    except Exception as e: print(f"[NONFATAL ERROR] {e}")

@bot.message_handler(commands=['stream', 'стрим'])
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
        
    parts = message.text.split(maxsplit=1)
    genre = parts[1].strip() if len(parts) > 1 else random.choice(STREAM_GENRES)
    
    econ['last_stream_time'] = now
    mark_dirty()
    
    msg = bot.reply_to(message, "🔴 <i>Настройка ОБС и запуск потока...</i> 😺", parse_mode='HTML')
    t = threading.Thread(target=stream_thread, args=(message.chat.id, user_id, user_name, genre, msg.message_id))
    t.daemon = True
    t.start()

# ---------------------------------------------------------
# САД БОНСАЙ (/garden)
# ---------------------------------------------------------
def render_garden_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    garden = econ.get('garden')

    markup = InlineKeyboardMarkup(row_width=2)
    if not garden:
        text = (
            f"🪴 <b>ВАША ОРАНЖЕРЕЯ БОНСАЙ</b> 😺\n"
            f"──────────────────────\n"
            f"У вас пока нет посаженных растений! 😿\n\n"
            f"Купите семена ниже, чтобы начать выращивать свой сад для пассивного заработка. 😻\n"
            f"💧 <i>Полив платный (15 🪙 за ведро), а почва постепенно высыхает со временем!</i>"
        )
        for s_id, s_info in GARDEN_SEEDS.items():
            markup.add(InlineKeyboardButton(f"{s_info['emoji']} Купить {s_info['name']} ({s_info['price']} 🪙)", callback_data=f"buy_seed_{s_id}:{user_id}"))
    else:
        seed_id = garden['seed']
        seed_info = GARDEN_SEEDS.get(seed_id, GARDEN_SEEDS['sakura'])
        now = time.time()
        
        # Пересчет высыхания влаги
        last_dry_calc = garden.get('last_dry_calc', garden.get('planted_at', now))
        dry_interval = 3600 * 2  # каждые 2 часа почва теряет 1 очко полива
        lost_water = int((now - last_dry_calc) // dry_interval)
        if lost_water > 0:
            garden['water_count'] = max(0, garden.get('water_count', 0) - lost_water)
            garden['last_dry_calc'] = last_dry_calc + (lost_water * dry_interval)
            mark_dirty()

        elapsed = now - garden['planted_at']
        progress_pct = min(100, int((elapsed / seed_info['grow_time']) * 100))
        water_count = garden['water_count']
        req_water = seed_info['water_req']
        can_harvest = (progress_pct >= 100 and water_count >= req_water)
        
        stage = "🌱 Росток"
        if progress_pct >= 100 and water_count >= req_water: 
            stage = "🍎 Урожай готов к сбору!"
        elif progress_pct >= 100:
            stage = "🥀 Созрело, но почва пересохла! Нужен полив!"
        elif progress_pct >= 50: 
            stage = "🌿 Буйное цветение"
            
        bar_len = progress_pct // 10
        bar = "🟩" * bar_len + "⬜️" * (10 - bar_len)
        
        bp = econ.get('backpack', {})
        fert_count = bp.get('garden_fertilizer', 0)

        text = (
            f"🪴 <b>ВАШ САД: {seed_info['name']}</b> 😺\n"
            f"──────────────────────\n"
            f"📈 Прогресс роста: <b>{progress_pct}%</b>\n"
            f"[{bar}]\n"
            f"💧 Влажность почвы: <b>{water_count}/{req_water}</b> (15 🪙 / полив)\n"
            f"⏳ Почва постепенно высыхает каждые 2 часа!\n"
            f"🌻 Стадия: <b>{stage}</b>\n"
            f"──────────────────────"
        )
        
        markup.add(InlineKeyboardButton(f"💦 Полить растение (15 🪙)", callback_data=f"water_plant:{user_id}"))
        if fert_count > 0 and progress_pct < 100:
            markup.add(InlineKeyboardButton(f"🧪 Удобрить ({fert_count} шт. в рюкзаке)", callback_data=f"fertilize_plant:{user_id}"))
        if can_harvest:
            markup.add(InlineKeyboardButton("🧺 Собрать урожай", callback_data=f"harvest_plant:{user_id}"))
        markup.add(InlineKeyboardButton("❌ Выкорчевать", callback_data=f"uproot_plant:{user_id}"))
        
    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
    else:
        try: bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")

@bot.message_handler(commands=['garden', 'сад'])
def cmd_garden(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_garden_view(message.chat.id, user_id, user_name)

# ---------------------------------------------------------
# КРЕДИТЫ (НЯ-БАНК)
# ---------------------------------------------------------
@bot.message_handler(commands=['loan', 'кредит'])
def cmd_loan(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    
    loan = econ.setdefault('loan', {'amount': 0, 'due': 0, 'defaulted': False})
    
    if loan.get('amount', 0) > 0:
        due_date = datetime.fromtimestamp(loan['due'], tz=MSK_TZ).strftime('%d.%m.%Y %H:%M')
        bot.reply_to(message, f"❌ У вас уже есть активный кредит на <b>{loan['amount']} 🪙</b>! 😾\nОплатите его до {due_date} (команда: <code>/repay</code>).", parse_mode='HTML')
        return
        
    if loan.get('defaulted'):
        bot.reply_to(message, "❌ Ваша кредитная история испорчена (Вы в черном списке банка)! 🙀", parse_mode='HTML')
        return

    m = re.search(r'(?:/loan|кредит)\s*(\d+)?', message.text, re.IGNORECASE)
    amount = int(m.group(1)) if m and m.group(1) else 0
    
    lvl, _, _, _ = get_account_level(econ.get('account_exp', 0))
    max_loan = lvl * 1500
    
    if amount <= 0:
        bot.reply_to(message, f"🏦 <b>КРЕДИТНЫЙ ОТДЕЛ НЯ-БАНКА</b> 😺\n\nВам доступен кредит до <b>{max_loan} 🪙</b> (на 24 часа).\nСумма возврата будет на 15% больше!\n\nДля оформления введите: <code>/loan {max_loan}</code> 😸", parse_mode='HTML')
        return
        
    if amount > max_loan:
        bot.reply_to(message, f"❌ Банк не одобрил такую сумму! Максимум для вашего {lvl} уровня: <b>{max_loan} 🪙</b>. 😿", parse_mode='HTML')
        return
        
    repay_amount = int(amount * 1.15)
    econ['balance'] += amount
    econ['loan'] = {
        'amount': repay_amount,
        'due': time.time() + 86400,
        'defaulted': False
    }
    mark_dirty()
    
    bot.reply_to(message, f"✅ <b>КРЕДИТ ОДОБРЕН!</b> 😸\n\nВы получили <b>{amount} 🪙</b>.\nВам нужно вернуть <b>{repay_amount} 🪙</b> в течение 24 часов (команда <code>/repay</code>), иначе вмешаются коллекторы! 🙀", parse_mode='HTML')

@bot.message_handler(commands=['repay', 'погасить'])
def cmd_repay(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    
    loan = econ.get('loan', {})
    if loan.get('amount', 0) <= 0:
        bot.reply_to(message, "У вас нет активных кредитов! 😸")
        return
        
    amount_to_pay = loan['amount']
    if econ['balance'] < amount_to_pay:
        bot.reply_to(message, f"❌ Недостаточно средств для погашения! Нужно <b>{amount_to_pay} 🪙</b>, у вас: {econ['balance']}. 😿", parse_mode='HTML')
        return
        
    econ['balance'] -= amount_to_pay
    econ['loan'] = {'amount': 0, 'due': 0, 'defaulted': False}
    mark_dirty()
    bot.reply_to(message, f"✅ Кредит успешно погашен! Списано <b>{amount_to_pay} 🪙</b>. Ваша кредитная история чиста. 😻", parse_mode='HTML')

# ---------------------------------------------------------
# TELEGRAM-СПОРТ
# ---------------------------------------------------------
def process_sport_dice_game(message, game_type, bet):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_username = message.from_user.username
    econ = get_user_econ(user_id, user_name, username=user_username)

    if bet <= 0:
        bot.reply_to(message, "❌ Ставка должна быть больше 0! 😾")
        return

    if econ['balance'] < bet:
        bot.reply_to(message, f"❌ Недостаточно средств! У вас: <b>{econ['balance']} 🪙</b> 😿", parse_mode='HTML')
        return

    econ['balance'] -= bet
    process_casino_bet(bet, chat_id)

    emoji_map = {'football': '⚽', 'basketball': '🏀', 'darts': '🎯', 'bowling': '🎳'}
    dice_emoji = emoji_map.get(game_type, '🎲')
    dice_msg = bot.send_dice(chat_id, emoji=dice_emoji)
    val = dice_msg.dice.value

    def resolve_dice_async():
        time.sleep(3.5)
        try:
            has_clover = (econ.get('luck_clover_until', 0) > time.time())
            clover_str = " (🍀 Бонус клевера)" if has_clover else ""
            result_text = ""
            
            pool = db.get('casino_pool', 1000000)
            actual_val = val
            if pool < bet * 3:
                actual_val = 1

            if game_type == 'football':
                if actual_val in [3, 4, 5]:
                    mult = 1.35 if not has_clover else 1.45
                    win_amount = int(bet * mult)
                    win_amount = process_casino_win(win_amount)
                    econ['balance'] += win_amount
                    econ['daily_casino_win'] = econ.get('daily_casino_win', 0) + (win_amount - bet)
                    econ['daily_casino_profit'] = econ.get('daily_casino_profit', 0) + (win_amount - bet)
                    result_text = f"⚽️ <b>ГОООООЛ! МЯЧ В СЕТКЕ!</b> 😺\n🎉 Выигрыш: <b>+{win_amount} Ня-коинов 🪙</b> (x{mult}){clover_str}!"
                elif actual_val == 2:
                    result_text = f"🧤 <b>ВРАТАРЬ ОТБИЛ УДАР!</b> 🙀\n💸 Штанга и сейф! Ставка <b>{bet} 🪙</b> сгорела."
                else:
                    result_text = f"💨 <b>МИМО ВОРОТ!</b> 😿\n💸 Мяч улетел на трибуны. Проигрыш <b>{bet} 🪙</b>."

            elif game_type == 'basketball':
                if actual_val in [4, 5]:
                    mult = 1.65 if not has_clover else 1.75
                    win_amount = int(bet * mult)
                    win_amount = process_casino_win(win_amount)
                    econ['balance'] += win_amount
                    econ['daily_casino_win'] = econ.get('daily_casino_win', 0) + (win_amount - bet)
                    econ['daily_casino_profit'] = econ.get('daily_casino_profit', 0) + (win_amount - bet)
                    result_text = f"🏀 <b>ТОЧНЫЙ БРОСОК В КОРЗИНУ!</b> 😻\n🎉 Чистый трёхочковый! Выигрыш: <b>+{win_amount} 🪙</b> (x{mult}){clover_str}!"
                elif actual_val == 3:
                    result_text = f"🧱 <b>МЯЧ ЗАСТРЯЛ НА ДУЖКЕ!</b> 🙀\n💸 Досадный промах! Ставка <b>{bet} 🪙</b> сгорела."
                else:
                    result_text = f"💨 <b>МИМО ЩИТА!</b> 😿\n💸 Промах мимо корзины. Проигрыш <b>{bet} 🪙</b>."

            elif game_type == 'darts':
                if actual_val == 6:
                    mult = 2.5 if not has_clover else 2.8
                    win_amount = int(bet * mult)
                    win_amount = process_casino_win(win_amount)
                    econ['balance'] += win_amount
                    econ['daily_casino_win'] = econ.get('daily_casino_win', 0) + (win_amount - bet)
                    econ['daily_casino_profit'] = econ.get('daily_casino_profit', 0) + (win_amount - bet)
                    result_text = f"🎯👑 <b>ПРЯМО В ЯБЛОЧКО (BULLSEYE)!</b> 🙀\n🎉 Куш: <b>+{win_amount} 🪙</b> (x{mult}){clover_str}!"
                elif actual_val == 5:
                    mult = 1.25
                    win_amount = int(bet * mult)
                    win_amount = process_casino_win(win_amount)
                    econ['balance'] += win_amount
                    econ['daily_casino_win'] = econ.get('daily_casino_win', 0) + (win_amount - bet)
                    econ['daily_casino_profit'] = econ.get('daily_casino_profit', 0) + (win_amount - bet)
                    result_text = f"🎯 <b>ОТЛИЧНОЕ ПОПАДАНИЕ В ЦЕНТР!</b> 😺\n🎉 Выигрыш: <b>+{win_amount} 🪙</b> (x{mult})!"
                else:
                    result_text = f"💨 <b>ДРОТИК УЛЕТЕЛ МИМО!</b> (Значение: {actual_val}) 😿\n💸 Проигрыш <b>{bet} 🪙</b>."

            elif game_type == 'bowling':
                if actual_val == 6:
                    mult = 2.2 if not has_clover else 2.4
                    win_amount = int(bet * mult)
                    win_amount = process_casino_win(win_amount)
                    econ['balance'] += win_amount
                    econ['daily_casino_win'] = econ.get('daily_casino_win', 0) + (win_amount - bet)
                    econ['daily_casino_profit'] = econ.get('daily_casino_profit', 0) + (win_amount - bet)
                    result_text = f"🎳👑 <b>СТРАААЙК! ВСЕ КЕГЛИ РАЗБИТЫ!</b> 😹\n🎉 Точный бросок: <b>+{win_amount} 🪙</b> (x{mult}){clover_str}!"
                elif actual_val in [4, 5]:
                    win_amount = int(bet * 0.85)
                    win_amount = process_casino_win(win_amount)
                    econ['balance'] += win_amount
                    result_text = f"🎳 <b>ХОРОШИЙ СПЛИТ!</b> Часть кеглей устояла. 😸\n✅ Кэшбек: <b>+{win_amount} 🪙</b> (x0.85)."
                else:
                    result_text = f"💨 <b>ШАР СКАТИЛСЯ В ЖЁЛОБ!</b> (Значение: {actual_val}) 😿\n💸 Проигрыш <b>{bet} 🪙</b>."

            add_account_exp(user_id, user_name, 5, username=user_username)
            check_achievements(user_id, user_name, 'games', 1, chat_id, username=user_username)
            mark_dirty()

            u_link = make_link(chat_id, user_name, user_id, ping=True)
            bot.reply_to(message, f"👤 Игрок: {u_link}\n{result_text}\n💰 Баланс: <b>{econ['balance']} Ня-коинов 🪙</b> 😸", parse_mode='HTML')
        except Exception as e:
            print(f"[SPORT DICE ERROR] {e}")

    th = threading.Thread(target=resolve_dice_async)
    th.daemon = True
    th.start()

@bot.message_handler(commands=['football', 'футбол', 'пенальти'])
def cmd_football(message):
    if not can_process_user_message(message):
        return
    m = re.search(r'(?:/football|футбол|пенальти)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(m.group(1)) if m and m.group(1) else 50
    process_sport_dice_game(message, 'football', bet)

@bot.message_handler(commands=['basketball', 'баскетбол'])
def cmd_basketball(message):
    if not can_process_user_message(message):
        return
    m = re.search(r'(?:/basketball|баскетбол)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(m.group(1)) if m and m.group(1) else 50
    process_sport_dice_game(message, 'basketball', bet)

@bot.message_handler(commands=['darts', 'дартс'])
def cmd_darts(message):
    if not can_process_user_message(message):
        return
    m = re.search(r'(?:/darts|дартс)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(m.group(1)) if m and m.group(1) else 50
    process_sport_dice_game(message, 'darts', bet)

@bot.message_handler(commands=['bowling', 'боулинг'])
def cmd_bowling(message):
    if not can_process_user_message(message):
        return
    m = re.search(r'(?:/bowling|боулинг)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(m.group(1)) if m and m.group(1) else 50
    process_sport_dice_game(message, 'bowling', bet)

# ---------------------------------------------------------
# ШАР ПРЕДСКАЗАНИЙ, ДЕТЕКТОР И ИЗМЕРИТЕЛЬ ШАНСА
# ---------------------------------------------------------
BALL_RESPONSES = [
    "🎱 Бесспорно и абсолютно точно! ✨", "🎱 Звёзды шепчут: определенно ДА! 🌟",
    "🎱 Мой хрустальный шар говорит: даже не сомневайся! 🔮", "🎱 Вероятность крайне высока! 👌",
    "🎱 Знаки указывают на положительный исход! 🍃", "🎱 Туманно... Спроси чуть позже 🌫",
    "🎱 Лучше тебе пока не знать правды... 🤫", "🎱 Сейчас чакры закрыты, переспроси через 5 минут 🧘‍♂️",
    "🎱 Даже не думай об этом! 🙅‍♂️", "🎱 Мой ответ — категорическое НЕТ! 🛑",
    "🎱 Перспективы весьма сомнительные... 📉", "🎱 Шансы равны нулю, увы! 💀"
]

@bot.message_handler(commands=['ball', 'шар'])
def cmd_magic_ball(message):
    if not can_process_user_message(message):
        return
    q = re.sub(r'^(?:/ball|шар)\s*', '', message.text, flags=re.IGNORECASE).strip()
    if not q:
        bot.reply_to(message, "🔮 Задайте вопрос шару судьбы!\nПример: <code>шар пойду ли я сегодня спать вовремя?</code>", parse_mode='HTML')
        return
    ans = random.choice(BALL_RESPONSES)
    bot.reply_to(message, f"🔮 <b>Вопрос:</b> <i>«{html.escape(q)}»</i>\n\n{ans} 😺", parse_mode='HTML')

@bot.message_handler(commands=['chance', 'шанс'])
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
    bot.reply_to(message, f"📊 <b>АНАЛИЗ ВЕРОЯТНОСТИ СОБЫТИЯ:</b> 😸\n<i>«{html.escape(q)}»</i>\n──────────────────────\nШанс: <b>{pct}%</b> [{bar}]\n💡 Вердикт: <i>{verdict}</i>\n──────────────────────", parse_mode='HTML')

@bot.message_handler(commands=['detector', 'детектор', 'правда'])
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
    bot.reply_to(message, f"🕵️‍♂️ <b>СКАНИРОВАНИЕ НА ПОЛИГРАФЕ:</b> 😺\n<i>«{html.escape(q)}»</i>\n──────────────────────\nВердикт: {v_title}\n📝 <i>{v_desc}</i>\n──────────────────────", parse_mode='HTML')

# ---------------------------------------------------------
# УДАРНИКИ И ГЕРОИ ДНЯ
# ---------------------------------------------------------
@bot.message_handler(commands=['daily_heroes', 'герои_дня', 'ударники'])
def cmd_daily_heroes(message):
    if not can_process_user_message(message):
        return
    chat_id = message.chat.id
    econ_items = db.get('economy', {})

    top_msg_user, top_msg_cnt = None, 0
    top_casino_user, top_casino_win = None, 0
    top_transfer_user, top_transfer_amt = None, 0

    for k, info in econ_items.items():
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
        "──────────────────────\n"
        f"🗣 <b>Главный спикер дня:</b>\n👉 {speaker_str}\n\n"
        f"🎰 <b>Гроза казино и спорта:</b>\n👉 {casino_str}\n\n"
        f"💖 <b>Главный меценат чата:</b>\n👉 {transfer_str}\n"
        "──────────────────────\n"
        "👑 <i>Герои дня получают почёт, уважение и статус в чате на 24 часа!</i> 😻"
    )
    bot.reply_to(message, text, parse_mode='HTML')

# ---------------------------------------------------------
# РЮКЗАК И РАСХОДНИКИ
# ---------------------------------------------------------
def render_backpack_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    bp = econ.setdefault('backpack', {'energy_drink': 0, 'luck_clover': 0, 'alarm_system': 0, 'invis_mask': 0, 'garden_fertilizer': 0})

    markup = InlineKeyboardMarkup()
    if bp.get('energy_drink', 0) > 0: markup.add(InlineKeyboardButton(f"⚡️ Выпить Энергетик ({bp['energy_drink']} шт.)", callback_data=f"use_item_energy_drink:{user_id}"))
    if bp.get('luck_clover', 0) > 0: markup.add(InlineKeyboardButton(f"🍀 Активировать Клевер ({bp['luck_clover']} шт.)", callback_data=f"use_item_luck_clover:{user_id}"))
    if bp.get('invis_mask', 0) > 0: markup.add(InlineKeyboardButton(f"🥷 Надеть Невидимку ({bp['invis_mask']} шт.)", callback_data=f"use_item_invis_mask:{user_id}"))
    if bp.get('garden_fertilizer', 0) > 0: markup.add(InlineKeyboardButton(f"🧪 Удобрить Сад ({bp['garden_fertilizer']} шт.)", callback_data=f"fertilize_plant:{user_id}"))
    markup.add(InlineKeyboardButton("🏪 Купить расходники в Магазине", callback_data=f"shop_cat_buffs:{user_id}"))

    clover_status = "✅ Активен" if econ.get('luck_clover_until', 0) > time.time() else "❌ Не активен"
    invis_status = "✅ Включена" if econ.get('invis_until', 0) > time.time() else "❌ Выключена"

    text = (
        f"🎒 <b>РЮКЗАК БАФФОВ И РАСХОДНИКОВ</b> 😺\n"
        f"──────────────────────\n"
        f"👤 Владелец: {make_link(chat_id, user_name, user_id, ping=False)}\n\n"
        f"• ⚡️ Энергетик Red Cat: <b>{bp.get('energy_drink', 0)} шт.</b>\n"
        f"• 🍀 Клевер удачи: <b>{bp.get('luck_clover', 0)} шт.</b> (Статус: {clover_status})\n"
        f"• 🛡 Охранная сигнализация: <b>{bp.get('alarm_system', 0)} шт.</b> (Авто-защита)\n"
        f"• 🥷 Маска-невидимка: <b>{bp.get('invis_mask', 0)} шт.</b> (Статус: {invis_status})\n"
        f"• 🧪 Супер-Удобрение для сада: <b>{bp.get('garden_fertilizer', 0)} шт.</b>\n"
        f"──────────────────────\n"
        f"💡 <i>Нажмите кнопку под сообщением, чтобы использовать предмет!</i> 😸"
    )

    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            return
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['backpack', 'рюкзак', 'инвентарь_баффов'])
def cmd_backpack(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_backpack_view(message.chat.id, message.from_user.id, user_name)

# ---------------------------------------------------------
# КОЛЕСО ФОРТУНЫ (/wheel)
# ---------------------------------------------------------
@bot.message_handler(commands=['wheel', 'рулетка', 'колесо'])
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
        econ['balance'] += 100
        prize_text = "💰 Вы выиграли <b>+100 Ня-коинов 🪙</b>! 😸"
    elif win_key == 'coins_300':
        econ['balance'] += 300
        prize_text = "💵 Вы выиграли <b>+300 Ня-коинов 🪙</b>! 😻"
    elif win_key == 'jackpot':
        econ['balance'] += 1000
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

# ---------------------------------------------------------
# САПЁР / МИНЫ (/mines)
# ---------------------------------------------------------
def calculate_mines_multiplier(total_cells, mines_count, safe_opened, rtp=0.88):
    prob = 1.0
    for i in range(safe_opened):
        prob *= (total_cells - mines_count - i) / (total_cells - i)
    if prob <= 0:
        return 1.05
    mult = (1.0 / prob) * rtp
    return round(max(1.05, mult), 2)

def render_mines_board(game_id):
    game = active_mines.get(game_id)
    if not game: return None, None
    u_id = game['user_id']
    size = game.get('size', 4)
    total_cells = size * size

    markup = InlineKeyboardMarkup(row_width=size)
    buttons = []

    for i in range(total_cells):
        if i in game['revealed']:
            buttons.append(InlineKeyboardButton("💎", callback_data="noop"))
        elif game['finished'] and i in game['bombs']:
            buttons.append(InlineKeyboardButton("💣", callback_data="noop"))
        elif game['finished']:
            buttons.append(InlineKeyboardButton("▫️", callback_data="noop"))
        else:
            buttons.append(InlineKeyboardButton("❓", callback_data=f"mop_{game_id}_{i}:{u_id}"))

    for row_idx in range(0, total_cells, size):
        markup.add(*buttons[row_idx:row_idx+size])

    if not game['finished'] and len(game['revealed']) > 0:
        cashout_amount = int(game['bet'] * game['current_multiplier'])
        markup.add(InlineKeyboardButton(f"💰 Забрать куш ({cashout_amount} 🪙 | {game['current_multiplier']:.2f}x) 😻", callback_data=f"mco_{game_id}:{u_id}"))

    max_safe = total_cells - len(game['bombs'])
    text = (
        f"💣 <b>САПЁР (ПОЛЕ {size}х{size})</b> 😺\n"
        f"──────────────────────\n"
        f"👤 Игрок: {game['user_tag']}\n"
        f"💰 Ставка: <b>{game['bet']} 🪙</b> | Мин на поле: <b>{len(game['bombs'])} шт.</b>\n"
        f"💎 Найдено кристаллов: <b>{len(game['revealed'])}/{max_safe}</b>\n"
        f"📈 Множитель: <b>{game['current_multiplier']:.2f}x</b>\n"
        f"──────────────────────\n"
        f"<i>Открывайте безопасные клетки или заберите куш!</i> 😸"
    )
    return text, markup

@bot.message_handler(commands=['mines', 'мины', 'сапер'])
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

    econ['balance'] -= bet
    process_casino_bet(bet, chat_id)

    game_id = f"m_{user_id}_{time.time_ns()}"
    active_mines[game_id] = {
        'user_id': user_id,
        'user_tag': user_name,
        'username': message.from_user.username,
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
        InlineKeyboardButton("5x5 (25 кл.)", callback_data=f"msz_{game_id}_5:{user_id}")
    )
    markup.add(InlineKeyboardButton("❌ Отмена (вернуть ставку)", callback_data=f"mcancel_{game_id}:{user_id}"))

    bot.reply_to(
        message,
        f"💣 <b>НАСТРОЙКА ИГРЫ «САПЁР»</b> 😺\n"
        f"──────────────────────\n"
        f"💰 Ставка: <b>{bet} 🪙</b>\n\n"
        f"Шаг 1: <b>Выберите размер игрового поля:</b> 😸",
        reply_markup=markup,
        parse_mode='HTML'
    )

# ---------------------------------------------------------
# БЕСПЛАТНЫЙ КЛАССИЧЕСКИЙ САПЁР (ВКЛЮЧАЯ 96 КЛЕТОК И 1-КНОПКУ)
# ---------------------------------------------------------
NUM_EMOJIS = {
    0: '⬜', 1: '1⃣', 2: '2⃣', 3: '3⃣', 4: '4⃣', 5: '5⃣', 6: '6⃣', 7: '7⃣', 8: '8⃣'
}

CSAPER_DIFFICULTIES = {
    'easy': {'name': '🟢 Новичок (5х5)', 'cols': 5, 'rows': 5, 'mines': 4, 'reward': 100, 'exp': 30},
    'med': {'name': '🟡 Любитель (6х6)', 'cols': 6, 'rows': 6, 'mines': 7, 'reward': 250, 'exp': 60},
    'hard': {'name': '🔴 Эксперт (7х7)', 'cols': 7, 'rows': 7, 'mines': 11, 'reward': 600, 'exp': 120},
    'ultra_96': {'name': '🟣 Мега-Поле (8х12, 96 кл.)', 'cols': 8, 'rows': 12, 'mines': 18, 'reward': 1800, 'exp': 350}
}

def get_adjacent_indices(idx, cols, rows):
    r, c = divmod(idx, cols)
    neighbors = []
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                neighbors.append(nr * cols + nc)
    return neighbors

def reveal_cascade_cells(game, start_idx):
    cols = game.get('cols', game.get('size', 5))
    rows = game.get('rows', game.get('size', 5))
    to_visit = [start_idx]
    
    while to_visit:
        curr = to_visit.pop()
        if curr in game['revealed']:
            continue
        if curr in game['flags']:
            game['flags'].remove(curr)
            
        game['revealed'].add(curr)
        
        if game['numbers'].get(curr, 0) == 0:
            for neighbor in get_adjacent_indices(curr, cols, rows):
                if neighbor not in game['revealed'] and neighbor not in game['bombs']:
                    to_visit.append(neighbor)

def render_classic_mines_board(game_id):
    game = active_c_mines.get(game_id)
    if not game:
        return None, None
        
    cols = game.get('cols', game.get('size', 5))
    rows = game.get('rows', game.get('size', 5))
    total_cells = cols * rows
    u_id = game['user_id']
    mode = game.get('mode', 'dig')

    markup = InlineKeyboardMarkup(row_width=cols)
    buttons = []
    
    for i in range(total_cells):
        if i in game['revealed']:
            cnt = game['numbers'].get(i, 0)
            buttons.append(InlineKeyboardButton(NUM_EMOJIS.get(cnt, '⬜'), callback_data="noop"))
        elif game['finished']:
            if i in game['bombs']:
                buttons.append(InlineKeyboardButton("💣", callback_data="noop"))
            elif i in game['flags']:
                buttons.append(InlineKeyboardButton("🚩", callback_data="noop"))
            else:
                buttons.append(InlineKeyboardButton("▫️", callback_data="noop"))
        else:
            if i in game['flags']:
                buttons.append(InlineKeyboardButton("🚩", callback_data=f"cmo_{game_id}_{i}:{u_id}"))
            else:
                buttons.append(InlineKeyboardButton("⬛", callback_data=f"cmo_{game_id}_{i}:{u_id}"))
                
    for row_idx in range(0, total_cells, cols):
        markup.add(*buttons[row_idx:row_idx+cols])
        
    if not game['finished']:
        mode_btn = "⛏ Режим: КОПАТЬ" if mode == 'dig' else "🚩 Режим: ФЛАГ"
        markup.add(InlineKeyboardButton(mode_btn, callback_data=f"cmmode_{game_id}:{u_id}"))
        
    mines_left = max(0, game['mines_count'] - len(game['flags']))
    text = (
        f"🕹 <b>САПЁР: {game['diff_name'].upper()}</b> 😺\n"
        f"──────────────────────\n"
        f"👤 Сапёр: {game['user_name']}\n"
        f"💣 Мин на поле: <b>{game['mines_count']} шт.</b> | Осталось: <b>{mines_left}</b>\n"
        f"🎯 Режим: <b>{'⛏ Открывать клетки' if mode == 'dig' else '🚩 Ставить / Убирать флаги'}</b>\n"
        f"🏆 Награда за разминирование: <b>+{game['reward']} 🪙</b>\n"
        f"──────────────────────\n"
        f"<i>Используйте логику! Первый ход всегда безопасен.</i> 😸"
    )
    return text, markup

@bot.message_handler(commands=['minesweeper', 'csaper', 'сапер_классик', 'сапёр_классик'])
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
        "──────────────────────\n"
        "Игра полностью бесплатная и проверяет только вашу логику и ум!\n\n"
        "👇 <b>Выберите уровень сложности:</b>",
        reply_markup=markup,
        parse_mode='HTML'
    )

# ---------------------------------------------------------
# КАРТОЧНАЯ ИГРА ДУРАК (36 КАРТ, 6 РЕЖИМОВ, СИНХРОНИЗАЦИЯ В ЛС)
# ---------------------------------------------------------
DURAK_RANKS = ['6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
DURAK_SUITS = ['♠️', '♣️', '♦️', '♥️']
RANK_VALUES = {'6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}

def create_durak_deck():
    deck = [{'rank': r, 'suit': s} for s in DURAK_SUITS for r in DURAK_RANKS]
    random.shuffle(deck)
    return deck

def card_to_str(c):
    return f"{c['rank']}{c['suit']}"

def can_beat_card(attack_card, defend_card, trump_suit):
    if attack_card['suit'] == defend_card['suit']:
        return RANK_VALUES[defend_card['rank']] > RANK_VALUES[attack_card['rank']]
    if defend_card['suit'] == trump_suit:
        return True
    return False

def durak_deal_cards(game):
    for p in game['players']:
        while len(p['hand']) < 6 and len(game['deck']) > 0:
            p['hand'].append(game['deck'].pop())

def durak_bot_turn(game):
    bot_player = game['players'][1]
    human_player = game['players'][0]
    trump = game['trump']

    if game['defender_idx'] == 1:
        # Бот защищается
        attack_card = game['table'][-1]['attack']
        defend_candidates = [c for c in bot_player['hand'] if can_beat_card(attack_card, c, trump)]
        if defend_candidates:
            defend_candidates.sort(key=lambda c: (1 if c['suit'] == trump else 0, RANK_VALUES[c['rank']]))
            chosen = defend_candidates[0]
            bot_player['hand'].remove(chosen)
            game['table'][-1]['defend'] = chosen
            game['status_text'] = f"🤖 Бот отбил карту {card_to_str(attack_card)} картой {card_to_str(chosen)}!"
        else:
            taken = []
            for pair in game['table']:
                taken.append(pair['attack'])
                if pair.get('defend'):
                    taken.append(pair['defend'])
            bot_player['hand'].extend(taken)
            game['table'] = []
            durak_deal_cards(game)
            game['attacker_idx'] = 0
            game['defender_idx'] = 1
            game['status_text'] = f"🤖 Бот не смог отбиться и забрал все карты со стола!"
    else:
        # Бот атакует
        if not game['table']:
            bot_player['hand'].sort(key=lambda c: (1 if c['suit'] == trump else 0, RANK_VALUES[c['rank']]))
            chosen = bot_player['hand'].pop(0)
            game['table'].append({'attack': chosen, 'defend': None})
            game['status_text'] = f"🤖 Бот пошёл с карты {card_to_str(chosen)}!"
        else:
            table_ranks = set()
            for pair in game['table']:
                table_ranks.add(pair['attack']['rank'])
                if pair.get('defend'):
                    table_ranks.add(pair['defend']['rank'])
            toss_candidates = [c for c in bot_player['hand'] if c['rank'] in table_ranks and c['suit'] != trump]
            if toss_candidates and len(game['table']) < 6:
                chosen = toss_candidates[0]
                bot_player['hand'].remove(chosen)
                game['table'].append({'attack': chosen, 'defend': None})
                game['status_text'] = f"🤖 Бот подкинул карту {card_to_str(chosen)}!"
            else:
                game['table'] = []
                durak_deal_cards(game)
                game['attacker_idx'] = 0
                game['defender_idx'] = 1
                game['status_text'] = "✅ Бито! Ход переходит к вам!"

def sync_durak_pm(game_id):
    game = active_durak.get(game_id)
    if not game or not game.get('started') or game.get('finished'):
        return
    trump = game['trump']
    deck_count = len(game['deck'])
    players = game['players']
    table = game['table']

    for p_idx, p in enumerate(players):
        if p['id'] == 'bot':
            continue
        u_id = p['id']
        is_attacker = (p_idx == game['attacker_idx'])
        is_defender = (p_idx == game['defender_idx'])

        role_str = "⚔️ ВЫ АТАКУЕТЕ!" if is_attacker else "🛡 ВЫ ЗАЩИЩАЕТЕСЬ!" if is_defender else "⏳ Ожидайте своего хода"
        lines = [
            f"🃏 <b>ДУРАК (ВАШИ КАРТЫ В ЛС)</b> 😺",
            "──────────────────────",
            f"👑 Козырь партии: <b>{trump}</b> | В колоде: <b>{deck_count} карт</b>",
            f"🎯 <b>{role_str}</b>\n",
            "<b>Стол партии:</b>"
        ]
        if not table:
            lines.append("<i>[ Стол пуст ]</i>")
        else:
            for idx, pair in enumerate(table, 1):
                att = card_to_str(pair['attack'])
                dfn = card_to_str(pair['defend']) if pair.get('defend') else "❓ (ждёт защиты)"
                lines.append(f"{idx}. {att}  ⚔️  {dfn}")

        if game.get('status_text'):
            lines.append(f"\n📢 <i>{game['status_text']}</i>")
        lines.append("──────────────────────\n<b>Ваша рука (нажмите для хода):</b>")

        markup = InlineKeyboardMarkup(row_width=3)
        card_btns = []
        for c_idx, c in enumerate(p['hand']):
            card_btns.append(InlineKeyboardButton(card_to_str(c), callback_data=f"durak_card_{game_id}_{c_idx}:{u_id}"))
        for i in range(0, len(card_btns), 3):
            markup.add(*card_btns[i:i+3])

        action_row = []
        if is_defender and table and any(not pr.get('defend') for pr in table):
            action_row.append(InlineKeyboardButton("📥 Взять карты", callback_data=f"durak_take_{game_id}:{u_id}"))
        if is_attacker and table and all(pr.get('defend') for pr in table):
            action_row.append(InlineKeyboardButton("✅ Бито", callback_data=f"durak_bito_{game_id}:{u_id}"))
        if action_row:
            markup.add(*action_row)

        text_msg = "\n".join(lines)
        if p.get('pm_msg_id'):
            try:
                bot.edit_message_text(text_msg, chat_id=u_id, message_id=p['pm_msg_id'], reply_markup=markup, parse_mode='HTML')
            except Exception:
                try:
                    sent = bot.send_message(u_id, text_msg, reply_markup=markup, parse_mode='HTML')
                    p['pm_msg_id'] = sent.message_id
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
        else:
            try:
                sent = bot.send_message(u_id, text_msg, reply_markup=markup, parse_mode='HTML')
                p['pm_msg_id'] = sent.message_id
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

def render_durak_board(game_id, viewer_id=None):
    game = active_durak.get(game_id)
    if not game:
        return "❌ Игра завершена или не найдена!", None

    trump = game['trump']
    deck_count = len(game['deck'])
    players = game['players']
    table = game['table']

    lines = [
        f"🃏 <b>ДУРАК (36 КАРТ) | РЕЖИМ: {game['mode_name']}</b> 😺",
        "──────────────────────",
        f"👑 Козырь: <b>{trump}</b> | В колоде: <b>{deck_count} карт</b>",
        f"⚔️ Атакует: <b>{players[game['attacker_idx']]['name']}</b>",
        f"🛡 Защищается: <b>{players[game['defender_idx']]['name']}</b>\n",
        "<b>Игровой стол:</b>"
    ]

    if not table:
        lines.append("<i>[ Стол пуст ]</i>")
    else:
        for idx, pair in enumerate(table, 1):
            att = card_to_str(pair['attack'])
            dfn = card_to_str(pair['defend']) if pair.get('defend') else "❓ (ждёт защиты)"
            lines.append(f"{idx}. {att}  ⚔️  {dfn}")

    lines.append("\n<b>Игроки за столом:</b>")
    for idx, p in enumerate(players):
        role = ""
        if idx == game['attacker_idx']: role = " (⚔️ Атака)"
        elif idx == game['defender_idx']: role = " (🛡 Защита)"
        lines.append(f"• {p['name']}: {len(p['hand'])} карт{role}")

    if game.get('status_text'):
        lines.append(f"\n📢 <i>{game['status_text']}</i>")
    lines.append("──────────────────────")

    markup = InlineKeyboardMarkup(row_width=3)

    if not game['started']:
        req_cnt = game['target_players']
        cur_cnt = len(players)
        lines.append(f"\n⏳ <i>Ожидание игроков: {cur_cnt}/{req_cnt}...</i>")
        lines.append("⚠️ <b>Внимание:</b> Чтобы войти в игру, вы должны обязательно запустить бота в ЛС!")
        lines.append("⏰ <i>Если лобби не соберется за 10 минут, оно автоматически удалится!</i>")
        markup.add(InlineKeyboardButton(f"🤝 Присоединиться ({cur_cnt}/{req_cnt})", callback_data=f"durak_join_{game_id}"))
        markup.add(InlineKeyboardButton("❌ Отменить игру", callback_data=f"durak_cancel_{game_id}"))
        return "\n".join(lines), markup

    if game.get('target_players') == 2 and any(pl['id'] == 'bot' for pl in players):
        viewer_player = players[0]
        card_btns = []
        for c_idx, c in enumerate(viewer_player['hand']):
            card_btns.append(InlineKeyboardButton(card_to_str(c), callback_data=f"durak_card_{game_id}_{c_idx}:{viewer_player['id']}"))
        for i in range(0, len(card_btns), 3):
            markup.add(*card_btns[i:i+3])
        action_row = []
        if game['defender_idx'] == 0 and table and any(not pr.get('defend') for pr in table):
            action_row.append(InlineKeyboardButton("📥 Взять карты", callback_data=f"durak_take_{game_id}:{viewer_player['id']}"))
        if game['attacker_idx'] == 0 and table and all(pr.get('defend') for pr in table):
            action_row.append(InlineKeyboardButton("✅ Бито", callback_data=f"durak_bito_{game_id}:{viewer_player['id']}"))
        if action_row:
            markup.add(*action_row)
    else:
        lines.append("📱 <b>Карты розданы в ЛС!</b> Перейдите в диалог с ботом, чтобы делать ходы. 😺")

    return "\n".join(lines), markup

@bot.message_handler(commands=['durak', 'дурак'])
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
        f"──────────────────────\n"
        f"💰 Ставка: <b>{bet} Ня-коинов 🪙</b>\n\n"
        f"Выберите режим игры на кнопках ниже: 😸",
        reply_markup=markup,
        parse_mode='HTML'
            )
    # ---------------------------------------------------------
# МЕМНЫЕ СИМУЛЯТОРЫ: ПИСЮН И ФАП
# ---------------------------------------------------------
@bot.message_handler(commands=['dick', 'писюн', 'замер'])
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
        f"──────────────────────\n"
        f"Размер писюна: <b>{new_size} см ({sign}{change} см) 📏</b>\n"
        f"📝 <i>{comment}</i>\n"
        f"──────────────────────",
        parse_mode='HTML'
    )

@bot.message_handler(commands=['fap', 'дроч', 'подрочить'])
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
        f"──────────────────────\n"
        f"👤 Участник: {u_link}\n"
        f"📊 Подходов за сегодня: <b>{count} раз(а)</b>\n"
        f"🎖 Ранг: <b>{rank}</b>\n"
        f"──────────────────────",
        parse_mode='HTML'
    )

# ---------------------------------------------------------
# ГАРАЖ (РАСШИРЕННЫЙ КАТАЛОГ)
# ---------------------------------------------------------
def render_garage_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    cur_veh = econ.get('vehicle')
    cur_name = VEHICLES[cur_veh]['name'] if cur_veh in VEHICLES else "Пешеход 🚶‍♂️"

    lines = [
        f"🏎 <b>ЛИЧНЫЙ АВТОГАРАЖ</b> 😺",
        "──────────────────────",
        f"👤 Владелец: {make_link(chat_id, user_name, user_id, ping=False)}",
        f"🚘 Текущий транспорт: <b>{cur_name}</b>\n",
        "<i>Транспорт навсегда снижает кулдауны на работу, охоту, рыбалку и замеры!</i>\n",
        "<b>Каталог транспорта:</b> 😸"
    ]

    markup = InlineKeyboardMarkup(row_width=2)
    veh_btns = []
    for v_id, v_info in VEHICLES.items():
        is_owned = " (Куплено)" if cur_veh == v_id else ""
        lines.append(f"• <b>{v_info['name']}</b> — <code>{v_info['price']} 🪙</code> ({v_info['desc']}){is_owned}")
        veh_btns.append(InlineKeyboardButton(f"{v_info['short']} — {v_info['price']} 🪙", callback_data=f"buy_veh_{v_id}:{user_id}"))

    for i in range(0, len(veh_btns), 2):
        markup.add(*veh_btns[i:i+2])

    lines.append("──────────────────────")
    text = "\n".join(lines)

    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            return
        except Exception as e: print(f"[NONFATAL ERROR] {e}")

    if cur_veh and cur_veh in VEHICLES and VEHICLES[cur_veh].get('msg_id'):
        try:
            bot.copy_message(
                chat_id=chat_id,
                from_chat_id=MEDIA_TG_CHAT_ID,
                message_id=VEHICLES[cur_veh]['msg_id'],
                caption=text,
                reply_markup=markup,
                parse_mode='HTML'
            )
            return
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
    try:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception:
        pass

@bot.message_handler(commands=['garage', 'гараж'])
def cmd_garage(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_garage_view(message.chat.id, user_id, user_name)

# ---------------------------------------------------------
# КУЛИНАРИЯ (/cook)
# ---------------------------------------------------------
@bot.message_handler(commands=['cook', 'кулинария', 'приготовить'])
def cmd_cook(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    fish_count = sum(econ.get('fish_inventory', {}).values())
    hunt_count = sum(econ.get('hunt_inventory', {}).values())

    if fish_count == 0 and hunt_count == 0:
        bot.reply_to(message, "🎒 У вас нет пойманной рыбы или мяса дичи для приготовления! 😿\nСходите на <code>/fish</code> или <code>/hunt</code>.", parse_mode='HTML')
        return

    econ['fish_inventory'] = {}
    econ['hunt_inventory'] = {}
    total_items = fish_count + hunt_count
    econ['cooked_meals'] = econ.get('cooked_meals', 0) + total_items

    if econ.get('pet'):
        p = econ['pet']
        p['hunger'] = 100
        p['cleanliness'] = min(100, p.get('cleanliness', 100) + 20)

    mark_dirty()
    bot.reply_to(
        message,
        f"🍳 <b>КУЛИНАРНЫЙ ШЕДЕВР ГОТОВ!</b> 😺\n"
        f"──────────────────────\n"
        f"Вы приготовили <b>{total_items} порций</b> изысканных блюд! 🍲🍖\n"
        f"🐾 Питомец накормлен до отвала (Сытость: <b>100%</b>) без трат коинов! 😻\n"
        f"──────────────────────",
        parse_mode='HTML'
    )

# ---------------------------------------------------------
# ПИТОМЕЦ (/pet)
# ---------------------------------------------------------
def render_pet_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    pet = econ.get('pet')

    if not pet:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🐾 Открыть Зоомагазин 😻", callback_data=f"shop_cat_pets_0:{user_id}"))
        text = "🐾 <b>У вас пока нет питомца!</b> 😿\n\nКупите верного друга в зоомагазине, чтобы получать бонусы к удаче, охоте и часовому доходу! 😻"
        if message_id:
            try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            return
        try: bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return

    update_pet_stats(pet)
    mark_dirty()

    hunger_bar = "🍗" * (pet.get('hunger', 100) // 20)
    clean_bar = "🧼" * (pet.get('cleanliness', 100) // 20)

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🍖 Покормить (30 🪙)", callback_data=f"pet_feed:{user_id}"),
        InlineKeyboardButton("🧼 Искупать (20 🪙)", callback_data=f"pet_wash:{user_id}")
    )
    markup.add(
        InlineKeyboardButton("🦮 Отправить гулять", callback_data=f"pet_walk_btn:{user_id}"),
        InlineKeyboardButton("🐾 Зоомагазин", callback_data=f"shop_cat_pets_0:{user_id}")
    )

    text = (
        f"🐾 <b>КАРТОЧКА ПИТОМЦА: {pet['name']}</b> 😺\n"
        f"──────────────────────\n"
        f"👤 Хозяин: {make_link(chat_id, user_name, user_id, ping=False)}\n"
        f"⭐ Опыт питомца: <b>{pet.get('pet_exp', 0)} EXP</b>\n"
        f"🍗 Сытость: <b>{pet.get('hunger', 100)}%</b> [{hunger_bar or '❌ Голоден'}]\n"
        f"🧼 Чистота: <b>{pet.get('cleanliness', 100)}%</b> [{clean_bar or '❌ Грязнуля'}]\n"
        f"✨ Бонус: <b>+{pet.get('luck_bonus', 10)}% к удаче</b>\n"
        f"──────────────────────\n"
        f"💡 <i>Используйте кнопки для ухода за питомцем!</i> 😸"
    )

    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return
    try: bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception as e: print(f"[NONFATAL ERROR] {e}")

@bot.message_handler(commands=['pet', 'питомец', 'пет'])
def cmd_pet(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_pet_view(message.chat.id, user_id, user_name)

# ---------------------------------------------------------
# ПРОГУЛКА ПИТОМЦА (/walk)
# ---------------------------------------------------------
def process_pet_walk(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    pet = econ.get('pet')

    if not pet:
        text = "❌ У вас нет питомца! Купите его в <code>/shop</code>. 😿"
        try: bot.send_message(chat_id, text, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return

    now = time.time()
    last_walk = econ.get('last_pet_walk', 0)
    cooldown = 10800

    left = cooldown_text(last_walk, cooldown, econ)
    if left:
        msg = f"⏳ Питомец устал! 😿 На следующую прогулку можно через: <b>{left}</b>."
        try: bot.send_message(chat_id, msg, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return

    econ['last_pet_walk'] = now

    events = [
        ("coins", "откопал(а) под деревом клад с коинами", random.randint(80, 250)),
        ("fish", "ловко поймал(а) в ручье рыбу", random.choice(FISH_TYPES)[0]),
        ("gem", "нашел(ла) сияющий кристалл и продал(а) его", random.randint(150, 400)),
        ("fun", "погонял(а) бабочек и поднял(а) настроение чату", 50),
        ("shoe", "притащил(а) в зубах старый башмак (но мы его продали)", 20),
        ("hero", "помог(ла) бабушке перейти дорогу и получил(а) награду", 300)
    ]

    ev_type, ev_desc, ev_val = random.choice(events)
    res_str = ""

    if ev_type in ['coins', 'gem', 'fun', 'shoe', 'hero']:
        econ['balance'] += ev_val
        res_str = f"💰 Прибыль: <b>+{ev_val} Ня-коинов 🪙</b>! 😸"
    elif ev_type == 'fish':
        add_inventory_item(econ['fish_inventory'], ev_val)
        res_str = f"🐟 Находка: <b>{ev_val}</b>! 😺"

    pet['pet_exp'] = pet.get('pet_exp', 0) + 25
    mark_dirty()

    try:
        bot.send_message(
            chat_id,
            f"🦮 <b>ПРОГУЛКА С ПИТОМЦЕМ: {pet['name']}</b> 😺\n"
            f"──────────────────────\n"
            f"Во время прогулки питомец {ev_desc}!\n"
            f"{res_str}\n"
            f"⭐ Опыт питомца: <b>+25 EXP</b>\n"
            f"──────────────────────",
            parse_mode='HTML'
        )
    except Exception:
        pass

@bot.message_handler(commands=['walk', 'гулять'])
def cmd_walk_pet(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    process_pet_walk(message.chat.id, user_id, user_name)

# ---------------------------------------------------------
# МАГАЗИН СНАСТЕЙ (/gear)
# ---------------------------------------------------------
@bot.message_handler(commands=['gear', 'снасти'])
def cmd_gear(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    lines = [
        "🎣 <b>МАГАЗИН ПРОФЕССИОНАЛЬНЫХ СНАСТЕЙ</b> 😺",
        "──────────────────────",
        "<i>Удочки и луки многократно увеличивают шанс на легендарную и мифическую добычу!</i>\n",
        "<b>Доступные снасти:</b> 😸"
    ]
    for r_id, r in RODS.items(): lines.append(f"• <b>{r['name']}</b> — <code>{r['price']} 🪙</code> (+{r['luck']}% к удаче)")
    for b_id, b in BOWS.items(): lines.append(f"• <b>{b['name']}</b> — <code>{b['price']} 🪙</code> (+{b['luck']}% к удаче)")
    lines.append("──────────────────────")

    markup = InlineKeyboardMarkup(row_width=2)
    rod_btns = [InlineKeyboardButton(f"{r_info['short']} — {r_info['price']} 🪙", callback_data=f"buy_rod_{r_id}:{user_id}") for r_id, r_info in RODS.items()]
    bow_btns = [InlineKeyboardButton(f"{b_info['short']} — {b_info['price']} 🪙", callback_data=f"buy_bow_{b_id}:{user_id}") for b_id, b_info in BOWS.items()]
    
    for i in range(0, len(rod_btns), 2):
        markup.add(*rod_btns[i:i+2])
    for i in range(0, len(bow_btns), 2):
        markup.add(*bow_btns[i:i+2])

    bot.reply_to(message, "\n".join(lines), reply_markup=markup, parse_mode='HTML')

# ---------------------------------------------------------
# БИЗНЕСЫ 2.0 (СБАЛАНСИРОВАННЫЙ ДОХОД)
# ---------------------------------------------------------
def render_business_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    user_biz = econ.setdefault('businesses', {})
    biz_levels = econ.setdefault('biz_levels', {})

    lines = [
        "🏢 <b>КОММЕРЧЕСКАЯ НЕДВИЖИМОСТЬ И БИЗНЕСЫ 2.0</b> 😺",
        "──────────────────────",
        "Каждое предприятие приносит пассивный доход в час и прокачивается до <b>5 ур.</b>!\n",
        "<b>Каталог предприятий:</b> 😸"
    ]

    markup = InlineKeyboardMarkup(row_width=2)
    b_btns = []
    for b_id, b_info in BUSINESSES.items():
        if b_id in user_biz:
            lvl = biz_levels.get(b_id, 1)
            upg_cost = b_info['upgrade_cost'] * lvl
            inc = int(b_info['base_income'] * (1 + (lvl-1)*0.45))
            lines.append(f"• <b>{b_info['name']}</b>: Уровень <b>{lvl}/5</b> (Доход: ~{inc} 🪙/ч)")
            if lvl < 5:
                b_btns.append(InlineKeyboardButton(f"⭐ Ап {b_info['short']} (ур. {lvl+1}) — {upg_cost} 🪙", callback_data=f"upg_biz_{b_id}:{user_id}"))
            else:
                b_btns.append(InlineKeyboardButton(f"👑 {b_info['short']} (МАКС)", callback_data="noop"))
        else:
            lines.append(f"• <b>{b_info['name']}</b> — <code>{b_info['price']} 🪙</code> (Базовый: {b_info['base_income']} 🪙/ч)")
            b_btns.append(InlineKeyboardButton(f"Купить {b_info['short']} — {b_info['price']} 🪙", callback_data=f"buy_biz_{b_id}:{user_id}"))

    for i in range(0, len(b_btns), 2):
        markup.add(*b_btns[i:i+2])

    markup.add(InlineKeyboardButton("💰 Собрать всю прибыль", callback_data=f"collect_biz_profit:{user_id}"))
    lines.append("──────────────────────")
    lines.append("🌴 <i>В ресте действует курортный бонус: +20% к прибыли!</i>")

    text = "\n".join(lines)
    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return
    try: bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception as e: print(f"[NONFATAL ERROR] {e}")

@bot.message_handler(commands=['business', 'бизнес', 'бизнесы', 'biz'])
def cmd_business(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_business_view(message.chat.id, user_id, user_name)

@bot.message_handler(commands=['miner', 'майнер', 'майнинг', 'ферма'])
def cmd_miner(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    user_biz = econ.get('businesses', {})
    biz_levels = econ.get('biz_levels', {})
    has_farm = 'crypto_farm' in user_biz

    if not has_farm:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💻 Купить Крипто-Ферму (18,000 🪙)", callback_data=f"buy_biz_crypto_farm:{user_id}"))
        text = (
            "💻 <b>КРИПТО-МАЙНИНГ СТАНЦИЯ</b> 😺\n"
            "──────────────────────\n"
            "У вас пока не установлена <b>Крипто-Ферма</b>! 😿\n\n"
            "Купите её, чтобы автоматически майнить монеты <b>NYA</b> каждый час и продавать их на бирже на пике цен! 😻\n"
            "──────────────────────"
        )
        bot.reply_to(message, text, reply_markup=markup, parse_mode='HTML')
        return

    lvl = biz_levels.get('crypto_farm', 1)
    market = get_market_data()
    nya_price = market.get('NYA', {}).get('price', 120.0)

    markup = InlineKeyboardMarkup()
    if lvl < 5:
        upg_cost = BUSINESSES['crypto_farm']['upgrade_cost'] * lvl
        markup.add(InlineKeyboardButton(f"⭐ Улучшить видеокарты (ур. {lvl+1}) — {upg_cost} 🪙", callback_data=f"upg_biz_crypto_farm:{user_id}"))
    markup.add(InlineKeyboardButton("💰 Собрать прибыль с фермы", callback_data=f"collect_biz_profit:{user_id}"))

    text = (
        f"💻 <b>ВАША КРИПТО-ФЕРМА (УРОВЕНЬ {lvl}/5)</b> 😺\n"
        f"──────────────────────\n"
        f"👤 Владелец: {make_link(message.chat.id, user_name, user_id, ping=False)}\n"
        f"⚡️ Хешрейт: <b>{lvl * 145} MH/s</b>\n"
        f"💵 Доходность: <b>~{int(BUSINESSES['crypto_farm']['base_income'] * (1 + (lvl-1)*0.45))} 🪙 в час</b>\n"
        f"📈 Текущий курс NYA: <b>{nya_price:.2f} 🪙</b>\n"
        f"──────────────────────\n"
        f"💡 Доход накапливается в общем пуле бизнесов! Нажмите кнопку ниже для сбора. 😸"
    )
    bot.reply_to(message, text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['collect', 'прибыль'])
def cmd_collect(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    user_biz = econ.get('businesses', {})
    biz_levels = econ.get('biz_levels', {})

    if not user_biz:
        bot.reply_to(message, "❌ У вас нет купленных бизнесов! Откройте <code>бизнесы</code> для покупки. 😾", parse_mode='HTML')
        return

    now = time.time()
    last_collect = econ.get('last_biz_collect', now)
    hours_passed = (now - last_collect) / 3600.0

    if hours_passed < 0.05:
        bot.reply_to(message, "⏳ Прибыль еще не накопилась, загляните чуть позже! 😿")
        return

    base_profit = 0
    for b_id in user_biz.keys():
        if b_id in BUSINESSES:
            lvl = biz_levels.get(b_id, 1)
            inc = int(BUSINESSES[b_id]['base_income'] * (1 + (lvl - 1) * 0.45) * hours_passed)
            base_profit += inc

    if base_profit <= 0:
        bot.reply_to(message, "⏳ Накоплений пока нет, подождите немного! 😿")
        return

    event_text = ""
    if random.random() < 0.15:
        if random.random() < 0.70:
            boost = int(base_profit * 0.5)
            base_profit += boost
            event_text = f"\n🌟 <b>Вирусный тренд в сети!</b> Приток клиентов дал <b>+{boost} 🪙</b>! 😻"
        else:
            tax = int(base_profit * 0.15)
            base_profit -= tax
            event_text = f"\n⚠️ <b>Плановое техобслуживание:</b> расход <b>-{tax} 🪙</b>. 😿"

    active_t = econ.get('active_title')
    if active_t and active_t in TITLES and TITLES[active_t].get('buff') == 'biz_bonus':
        bonus_t = int(base_profit * (TITLES[active_t]['val'] / 100.0))
        base_profit += bonus_t
        event_text += f"\n👑 Бонус титула: <b>+{bonus_t} 🪙</b>"

    in_rest, _, _ = check_user_rest(db.get('rests', {}).get(str(message.chat.id), {}), user_id=user_id, user_name=user_name)
    if in_rest:
        rest_bonus = int(base_profit * 0.20)
        base_profit += rest_bonus
        event_text += f"\n🌴 Курортный бонус реста (+20%): <b>+{rest_bonus} 🪙</b>"

    econ['balance'] += base_profit
    econ['last_biz_collect'] = now
    mark_dirty()

    bot.reply_to(message, f"💰 Собрана прибыль предприятий: <b>+{base_profit} Ня-коинов 🪙</b>!{event_text}\nБаланс: <b>{econ['balance']} 🪙</b> 😸", parse_mode='HTML')

# ---------------------------------------------------------
# БАНК, КЕЙС, ЛОТЕРЕЯ
# ---------------------------------------------------------
def render_bank_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    interest_earned = update_bank_interest(econ)
    mark_dirty()

    deposit = econ.get('bank_deposit', 0)
    pocket = econ.get('balance', 0)

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📥 Внести 100 🪙", callback_data=f"bank_dep_100:{user_id}"),
        InlineKeyboardButton("📥 Внести всё", callback_data=f"bank_dep_all:{user_id}")
    )
    markup.add(
        InlineKeyboardButton("📤 Снять 100 🪙", callback_data=f"bank_wd_100:{user_id}"),
        InlineKeyboardButton("📤 Снять всё", callback_data=f"bank_wd_all:{user_id}")
    )
    markup.add(InlineKeyboardButton("🔄 Обновить баланс", callback_data=f"bank_refresh:{user_id}"))

    text = (
        f"🏦 <b>НЯ-БАНК | НАКОПИТЕЛЬНЫЙ СЧЁТ</b> 😺\n"
        f"──────────────────────\n"
        f"👤 Владелец: {make_link(chat_id, user_name, user_id, ping=False)}\n\n"
        f"💳 На депозите: <b>{deposit} Ня-коинов 🪙</b>\n"
        f"💵 В кармане: <b>{pocket} 🪙</b>\n\n"
        f"📈 <b>Ставка:</b> <b>+0.25% каждые 6 часов (1% в сутки)</b>\n"
        f"🛡 <b>Защита:</b> Депозит защищен от любых карманных краж на 100%!\n"
        f"──────────────────────\n"
        f"💡 <i>Используйте кнопки или команды:</i> 😸\n"
        f"• <code>банк положить 500</code>\n"
        f"• <code>банк снять 500</code>"
    )

    if interest_earned > 0: text += f"\n\n✨ <i>Начислены дивиденды: +{interest_earned} 🪙!</i> 😻"

    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return
    try: bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception as e: print(f"[NONFATAL ERROR] {e}")

@bot.message_handler(commands=['bank', 'банк', 'депозит'])
def cmd_bank(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_bank_view(message.chat.id, message.from_user.id, user_name)

@bot.message_handler(commands=['case', 'кейс', 'сундук', 'chest', 'чест'])
def cmd_case(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    now = time.time()
    last_case = econ.get('last_case_time', 0)
    chest_claims = db.setdefault('chest_claims', {})
    previous = chest_claims.get(str(user_id), {}).get('date')
    cooldown = 86400

    left = cooldown_text(last_case, cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Бесплатный кейс доступен раз в 24 часа!\nДо следующего открытия: <b>{left}</b>. 😿", parse_mode='HTML')
        return

    econ['last_case_time'] = now
    today = daily_task_date()
    yesterday = (now_msk() - timedelta(days=1)).strftime('%Y-%m-%d')
    econ['chest_streak'] = econ.get('chest_streak', 0) + 1 if previous == yesterday else 1
    chest_claims[str(user_id)] = {'date': today, 'streak': econ['chest_streak']}

    roll = random.random()
    if roll < 0.50:
        coins_reward = random.randint(80, 250)
        econ['balance'] += coins_reward
        prize_str = f"💰 <b>+{coins_reward} Ня-коинов 🪙</b>"
    elif roll < 0.75:
        exp_reward = random.randint(30, 80)
        econ['work_exp'] = econ.get('work_exp', 0) + exp_reward
        prize_str = f"🎓 <b>+{exp_reward} EXP опыта работы</b>"
    elif roll < 0.90:
        trophy = random.choice(FISH_TYPES)[0]
        add_inventory_item(econ['fish_inventory'], trophy)
        prize_str = f"🐟 Редкий улов: <b>{trophy}</b>"
    else:
        trophy = random.choice(HUNT_TYPES)[0]
        add_inventory_item(econ['hunt_inventory'], trophy)
        prize_str = f"🏹 Охотничий трофей: <b>{trophy}</b>!"

    add_account_exp(user_id, user_name, 20, username=message.from_user.username)
    if econ.get('chest_streak', 0) >= 3:
        streak_bonus = min(1000, econ['chest_streak'] * 100)
        econ['balance'] += streak_bonus
        prize_str += f"\n🔥 Серия сундуков {econ['chest_streak']} дн.: <b>+{streak_bonus} 🪙</b>"
    check_achievements(user_id, user_name, 'cases_opened', 1, message.chat.id, username=message.from_user.username)
    mark_dirty()

    bot.reply_to(
        message,
        f"📦 <b>ВЫ ОТКРЫЛИ ЕЖЕДНЕВНЫЙ СУНДУК!</b> 😺\n"
        f"──────────────────────\n"
        f"🎉 Ваша награда: {prize_str}\n"
        f"⭐ Опыт аккаунта: <b>+20 EXP</b>\n"
        f"──────────────────────\n"
        f"Возвращайтесь за новым сундуком завтра! 😸",
        parse_mode='HTML'
    )

def render_lottery_view(chat_id, user_id, user_name, message_id=None):
    lottery = db.setdefault('lottery', {'tickets': {}, 'pot': 0, 'last_draw': 0})
    tickets = lottery.get('tickets', {})
    pot = lottery.get('pot', 0)
    total_tickets = sum(tickets.values())

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎟 Купить 1 билет (100 🪙)", callback_data=f"buy_ticket_1:{user_id}"),
        InlineKeyboardButton("🎟 Купить 5 билетов (500 🪙)", callback_data=f"buy_ticket_5:{user_id}")
    )

    my_tickets = tickets.get(str(user_id), 0)

    text = (
        f"🎟 <b>СЕРВЕРНАЯ ДЖЕКПОТ-ЛОТЕРЕЯ</b> 😺\n"
        f"──────────────────────\n"
        f"💰 Текущий Джекпот: <b>{pot} Ня-коинов 🪙</b>\n"
        f"🎫 Продано билетов: <b>{total_tickets}/10</b>\n"
        f"👤 Ваших билетов: <b>{my_tickets} шт.</b>\n"
        f"──────────────────────\n"
        f"📌 При достижении <b>10 билетов</b> бот автоматически разыграет весь банк между участниками! 😸"
    )
    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return
    try: bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception as e: print(f"[NONFATAL ERROR] {e}")

@bot.message_handler(commands=['lottery', 'лотерея'])
def cmd_lottery(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_lottery_view(message.chat.id, message.from_user.id, user_name)

# ---------------------------------------------------------
# ИСТОРИЯ РЕСТОВ И НАСТРОЙКИ ЧАТА
# ---------------------------------------------------------
@bot.message_handler(commands=['history', 'история'])
def cmd_history(message):
    if not can_process_user_message(message):
        return
    chat_id = message.chat.id
    str_chat = str(chat_id)
    target_user, target_user_id, _ = parse_target_and_args(message, '/history')
    if not target_user: target_user, target_user_id, _ = parse_target_and_args(message, 'история')

    if not target_user:
        target_user = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
        target_user_id = message.from_user.id

    clean_u = clean_tag(target_user)
    hist_entries = db.get('history', {}).get(str_chat, {}).get(clean_u, [])

    if not hist_entries:
        bot.reply_to(message, f"📜 История рестов для <b>{html.escape(clean_u)}</b> в этом чате пуста! 😿", parse_mode='HTML')
        return

    lines = [f"📜 <b>ИСТОРИЯ РЕСТОВ: {make_link(chat_id, clean_u, target_user_id, ping=False)}</b> 😺", "──────────────────────"]
    for idx, item in enumerate(reversed(hist_entries[-8:]), 1):
        lines.append(
            f"<b>{idx}. {item.get('action', 'Рест')}</b> ({item.get('date', '—')})\n"
            f"⏱ Срок: <code>{item.get('duration', '—')}</code> | Причина: <i>{item.get('reason', 'Не указана')}</i>\n"
        )
    lines.append("──────────────────────")
    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')

def render_settings_view(chat_id, user_id=None, message_id=None):
    sett = get_chat_settings(chat_id)
    rp_status = "✅ Включено" if sett.get('rp_enabled', True) else "❌ Выключено"
    flood_status = "✅ Включён" if sett.get('flood_protection', False) else "❌ Выключен"
    react_status = "✅ Включены" if sett.get('auto_reactions', True) else "❌ Выключены"
    welcome_status = "✅ Включено" if sett.get('welcome_enabled', True) else "❌ Выключено"

    uid_tag = f":{user_id}" if user_id else ""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton(f"🎭 РП-команды: {rp_status}", callback_data=f"toggle_rp{uid_tag}"))
    markup.add(InlineKeyboardButton(f"🛡 Антифлуд: {flood_status}", callback_data=f"toggle_flood{uid_tag}"))
    markup.add(InlineKeyboardButton(f"✨ Авто-реакции: {react_status}", callback_data=f"toggle_reactions{uid_tag}"))
    markup.add(InlineKeyboardButton(f"👋 Приветствия: {welcome_status}", callback_data=f"toggle_welcome{uid_tag}"))
    markup.add(InlineKeyboardButton(f"🔔 Напоминание: {sett.get('remind_minutes', 60)} мин.", callback_data=f"set_remind_time{uid_tag}"))

    text = (
        f"⚙️ <b>НАСТРОЙКИ НЯ-БОТА ДЛЯ ЧАТА</b> 😺\n"
        f"──────────────────────\n"
        f"🌴 Максимальный срок реста: <b>без ограничений</b>\n"
        f"🎭 РП-команды: <b>{rp_status}</b>\n"
        f"🛡 Антифлуд: <b>{flood_status}</b> — 5 команд/час\n"
        f"✨ Авто-реакции: <b>{react_status}</b>\n"
        f"👋 Приветствия: <b>{welcome_status}</b>\n"
        f"🔔 Напоминание: за <b>{sett.get('remind_minutes', 60)} мин.</b>\n"
        f"──────────────────────\n"
        f"<i>Все переключатели доступны администраторам чата.</i> 😸"
    )

    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return
    try: bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception as e: print(f"[NONFATAL ERROR] {e}")

@bot.message_handler(commands=['settings', 'настройки'])
def cmd_settings(message):
    if not can_process_user_message(message):
        return
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Настройки доступны только администраторам чата! 😾")
        return
    render_settings_view(message.chat.id, message.from_user.id)

# ---------------------------------------------------------
# АВАТАРКА ПРОФИЛЯ
# ---------------------------------------------------------
@bot.message_handler(commands=['set_pfp', 'аватарка'])
def cmd_set_pfp(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    photo_file_id = None
    if message.photo: photo_file_id = message.photo[-1].file_id
    elif message.reply_to_message and message.reply_to_message.photo: photo_file_id = message.reply_to_message.photo[-1].file_id

    if not photo_file_id:
        bot.reply_to(
            message,
            "📸 <b>КАК УСТАНОВИТЬ АВАТАРКУ В ПРОФИЛЬ:</b> 😺\n"
            "──────────────────────\n"
            "1. Отправьте в чат картинку и в подписи (caption) напишите <code>/set_pfp</code>\n"
            "2. Либо ответьте командой <code>/set_pfp</code> на любое сообщение с фото!\n"
            "──────────────────────",
            parse_mode='HTML'
        )
        return

    econ['pfp_file_id'] = photo_file_id
    mark_dirty()
    bot.reply_to(message, "✅ <b>Ваша аватарка профиля успешно установлена!</b> 😻\nПосмотреть: <code>/profile</code>", parse_mode='HTML')

@bot.message_handler(commands=['del_pfp', 'удалить_аватарку'])
def cmd_del_pfp(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    econ['pfp_file_id'] = None
    mark_dirty()
    bot.reply_to(message, "🗑 <b>Аватарка профиля успешно удалена!</b> 😿", parse_mode='HTML')

# ---------------------------------------------------------
# ПРОФИЛЬ, НАСТРОЙКИ ТЕМ И ШРИФТОВ
# ---------------------------------------------------------
@bot.message_handler(commands=['custom_title', 'set_title'])
def cmd_custom_title(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    if not econ.get('has_custom_title_cert', False):
        bot.reply_to(message, "❌ У вас нет <b>Сертификата на кастомный титул</b>! 😿\nКупите его в <code>/shop</code> за 15,000 🪙.", parse_mode='HTML')
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "❌ Укажите желаемый титул! 😾\nПример: <code>/custom_title 👑 Главный Кот</code>", parse_mode='HTML')
        return

    raw_title = parts[1].strip()[:32]
    clean_title = re.sub(r'<[^>]*>', '', raw_title).strip()
    if not clean_title:
        bot.reply_to(message, "❌ Недопустимый титул (содержит только теги)!", parse_mode='HTML')
        return
    econ['custom_title'] = clean_title
    econ['active_title'] = None
    mark_dirty()
    bot.reply_to(message, f"🎉 Ваш кастомный титул успешно установлен: <b>[{html.escape(clean_title)}]</b>! 😻", parse_mode='HTML')

def render_profile_settings_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    cur_theme = econ.get('profile_theme', 'default')
    cur_font = econ.get('profile_font', 'default')
    theme_name = THEMES.get(cur_theme, {}).get('name', 'Классическая')
    font_name = FONTS.get(cur_font, {}).get('name', 'Обычный')

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🎨 Сменить Тему", callback_data=f"ps_themes:{user_id}"),
        InlineKeyboardButton("🔤 Сменить Шрифт", callback_data=f"ps_fonts:{user_id}")
    )
    markup.add(
        InlineKeyboardButton("🏷 Значки", callback_data=f"ps_badges:{user_id}"),
        InlineKeyboardButton("👑 Титулы", callback_data=f"ps_titles:{user_id}")
    )
    markup.add(
        InlineKeyboardButton("📸 Сменить Аватарку", callback_data=f"ps_pfp:{user_id}"),
        InlineKeyboardButton("🔙 В Профиль", callback_data=f"ps_back_profile:{user_id}")
    )

    text = (
        f"⚙️ <b>НАСТРОЙКИ ВНЕШНЕГО ВИДА ПРОФИЛЯ</b> 😺\n"
        f"──────────────────────\n"
        f"👤 Игрок: {make_link(chat_id, user_name, user_id, ping=False)}\n"
        f"🎨 Активная тема: <b>{theme_name}</b>\n"
        f"🔤 Активный шрифт: <b>{font_name}</b>\n"
        f"──────────────────────\n"
        f"<i>Используйте кнопки ниже для индивидуальной кастомизации вашей карточки игрока!</i> 😻"
    )

    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return
    try: bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception as e: print(f"[NONFATAL ERROR] {e}")

@bot.message_handler(commands=['profile_settings', 'set_profile', 'настройки_профиля'])
def cmd_profile_settings(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_profile_settings_view(message.chat.id, user_id, user_name)

def send_user_profile(chat_id, user_tag, user_id, message_to_reply=None, message_id_to_edit=None, username=None):
    econ = get_user_econ(user_id, user_tag, username=username)
    theme_key = econ.get('profile_theme', 'default')
    theme_info = THEMES.get(theme_key, THEMES['default'])
    font_key = econ.get('profile_font', 'default')

    border = theme_info['border']
    header = theme_info['header']
    t_icon = theme_info['icon']

    markup = InlineKeyboardMarkup()

    purchased_titles = econ.get('titles', [])
    active_title = econ.get('active_title')
    custom_title = econ.get('custom_title')

    if purchased_titles:
        for title_key in purchased_titles:
            if title_key in TITLES and title_key != active_title:
                markup.add(InlineKeyboardButton(f"Надеть {TITLES[title_key]['text']}", callback_data=f"set_title_{title_key}:{user_id}"))
        if active_title or custom_title:
            markup.add(InlineKeyboardButton('❌ Снять текущий титул', callback_data=f'remove_title:{user_id}'))

    purchased_themes = econ.get('purchased_themes', ['default'])
    if len(purchased_themes) > 1:
        theme_row = []
        for t_k in purchased_themes:
            if t_k != theme_key and t_k in THEMES:
                theme_row.append(InlineKeyboardButton(f"Стиль: {THEMES[t_k]['name']}", callback_data=f"set_theme_{t_k}:{user_id}"))
        if theme_row: markup.add(*theme_row)

    current_badge = econ.get('badge') or "Отсутствует"

    if custom_title: current_title = f"🌟 {html.escape(custom_title)} (Кастом)"
    elif active_title in TITLES:
        t_obj = TITLES[active_title]
        current_title = f"{t_obj['text']} ({t_obj['desc']})"
    else: current_title = 'Отсутствует'

    inv = econ.get('inventory', [])
    inv_str = " ".join(inv) if inv else "Пусто"

    fish_inv = ', '.join(f'{name} × {count}' for name, count in econ.get('fish_inventory', {}).items()) or 'Пусто'
    hunt_inv = ', '.join(f'{name} × {count}' for name, count in econ.get('hunt_inventory', {}).items()) or 'Пусто'

    portfolio = econ.get('crypto_portfolio', {})
    portfolio_str = ', '.join(f'<b>{tick}</b>: {amt:.2f}' for tick, amt in portfolio.items() if amt > 0.0001) or 'Пусто'

    user_biz = econ.get('businesses', {})
    biz_levels = econ.get('biz_levels', {})
    biz_str = ', '.join(f"{BUSINESSES[b_id]['name']} (ур. {biz_levels.get(b_id, 1)})" for b_id in user_biz.keys() if b_id in BUSINESSES) or 'Нет'

    veh_str = VEHICLES[econ['vehicle']]['name'] if econ.get('vehicle') in VEHICLES else 'Пешеход 🚶‍♂️'

    marriage_info = "Холост(а)"
    if econ.get('marriage'):
        m_data = econ['marriage']
        ring_emoji = RINGS.get(m_data.get('ring'), {}).get('emoji', '💍')
        days_together = max(1, int((time.time() - m_data.get('married_at', time.time())) / 86400))
        marriage_info = f"{ring_emoji} В браке с <b>{html.escape(m_data.get('partner_name', 'Партнер'))}</b> ({days_together} дн.)"

    pet_info = "Отсутствует"
    if econ.get('pet'):
        p = econ['pet']
        update_pet_stats(p)
        pet_info = f"{p['name']} (🍖 {p['hunger']}%, 🧼 {p['cleanliness']}%, ⭐ {p.get('pet_exp', 0)} EXP)"

    unlocked_ach = len(econ.get('achievements', []))
    total_ach = len(ACHIEVEMENTS)

    m_st = econ.get('msg_stats', {})
    msg_stats_str = (
        f"• День: <b>{m_st.get('day_count', 0)}</b> | Неделя: <b>{m_st.get('week_count', 0)}</b>\n"
        f"• Месяц: <b>{m_st.get('month_count', 0)}</b> | Всего: <b>{m_st.get('total_count', 0)}</b>"
    )

    lvl, cur_exp, next_exp, bar = get_account_level(econ.get('account_exp', 0))

    karma = econ.get('karma', 0)
    if karma >= 80: karma_title = "😇 Святой Ангел"
    elif karma >= 30: karma_title = "🕊 Добряк"
    elif karma > -30: karma_title = "⚖️ Нейтрал"
    elif karma > -80: karma_title = "😈 Злодей"
    else: karma_title = "👹 Абсолютный Демон"

    vip_line = ""
    if econ.get('vip_forever'):
        vip_line = f"{t_icon} ⭐️ <b>VIP NYA PASS:</b> 👑 НАВСЕГДА\n"
    elif econ.get('vip_until', 0) > time.time():
        vip_date = datetime.fromtimestamp(econ['vip_until'], tz=MSK_TZ).strftime('%d.%m.%Y %H:%M')
        vip_line = f"{t_icon} ⭐️ <b>VIP NYA PASS:</b> до {vip_date}\n"

    stars_donated = econ.get('stars_donated', 0)
    stars_line = f"{t_icon} 🌟 Поддержка бота: <b>{stars_donated} ⭐️</b>\n" if stars_donated > 0 else ""

    loan_str = ""
    loan = econ.get('loan')
    if loan and loan.get('amount', 0) > 0:
        loan_str = f"\n{t_icon} 💳 Кредит: <b>-{loan['amount']} 🪙</b>"

    streak_days = econ.get('bonus_streak', 0)
    streak_str = f"🔥 Стрик бонусов: <b>{streak_days} дн.</b> (Множитель: x{min(2.0, 1.0 + (streak_days * 0.15)):.1f})\n"

    raw_text = (
        f"{header}\n"
        f"{border}\n"
        f"{t_icon} 👤 Игрок: {make_link(chat_id, user_tag, user_id, ping=False)}\n"
        f"{t_icon} ⭐ Уровень: <b>{lvl} LVL</b> [{bar}] (<b>{cur_exp}/{next_exp} EXP</b>)\n"
        f"{t_icon} ⚖️ Карма: <b>{karma}</b> ({karma_title})\n"
        f"{vip_line}"
        f"{stars_line}"
        f"{t_icon} {streak_str}"
        f"{t_icon} 💵 В кармане: <b>{econ['balance']} Ня-коинов 💸</b>\n"
        f"{t_icon} 🏦 На депозите: <b>{econ.get('bank_deposit', 0)} 🪙</b>{loan_str}\n"
        f"{t_icon} 🚘 Гараж: <b>{veh_str}</b>\n"
        f"{t_icon} 💼 Опыт работы: <b>{econ.get('work_exp', 0)} EXP</b>\n"
        f"{t_icon} 💍 Семья: <b>{marriage_info}</b>\n"
        f"{t_icon} 🏢 Бизнесы: <b>{biz_str}</b>\n"
        f"{t_icon} 🐾 Питомец: <b>{pet_info}</b>\n"
        f"{t_icon} 🏆 Достижения: <b>{unlocked_ach}/{total_ach}</b> (/achievements)\n"
        f"{border}\n"
        f"📊 <b>Биометрия и замеры:</b>\n"
        f"• 🍆 Писюн: <b>{econ.get('dick_size', 15)} см</b> | 💦 Фап: <b>{econ.get('fap_count', 0)} раз(а)</b>\n"
        f"• 🧬 Хромосомы: <b>{econ.get('chromosomes', 46)}</b> | 🧠 IQ: <b>{econ.get('iq', 100)}</b>\n"
        f"• 🥩 Жир: <b>{econ.get('fat', 20)}%</b> | 🦶 Размер пятки: <b>{econ.get('foot_size', 25)} см</b>\n"
        f"{border}\n"
        f"📊 <b>Активность сообщений:</b>\n{msg_stats_str}\n"
        f"📈 <b>Крипто-портфель:</b> {portfolio_str}\n"
        f"🏷 Значок: <b>{current_badge}</b> | Титул: <b>{current_title}</b>\n"
        f"🎒 Значки: {inv_str}\n"
        f"🐟 Рыба: {fish_inv} | 🏹 Дичь: {hunt_inv}\n"
        f"{border}"
    )

    text = apply_font(raw_text, font_key)

    if inv:
        row = []
        for emoji in inv:
            if emoji != current_badge:
                row.append(InlineKeyboardButton(f"Надеть {emoji}", callback_data=f"set_badge_{emoji}:{user_id}"))
                if len(row) == 3:
                    markup.add(*row)
                    row = []
        if row: markup.add(*row)
        if current_badge != "Отсутствует":
            markup.add(InlineKeyboardButton("❌ Снять значок", callback_data=f"remove_badge:{user_id}"))
        markup.add(InlineKeyboardButton("⚙️ Настройки тем и шрифтов", callback_data=f"open_profile_settings:{user_id}"))

    if message_id_to_edit:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id_to_edit, reply_markup=markup, parse_mode='HTML')
            return
        except Exception:
            try:
                bot.edit_message_caption(chat_id=chat_id, message_id=message_id_to_edit, caption=text, reply_markup=markup, parse_mode='HTML')
                return
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

    pfp_id = econ.get('pfp_file_id')
    if pfp_id:
        try:
            if message_to_reply:
                bot.send_photo(chat_id, pfp_id, caption=text, reply_markup=markup, reply_to_message_id=message_to_reply.message_id, parse_mode='HTML')
            else:
                bot.send_photo(chat_id, pfp_id, caption=text, reply_markup=markup, parse_mode='HTML')
            return
        except Exception as e: print(f"[NONFATAL ERROR] {e}")

    if message_to_reply:
        try: bot.reply_to(message_to_reply, text, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
    else:
        try: bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")

# ---------------------------------------------------------
# ЗАЩИТА ПОКУПОК TELEGRAM STARS
# ---------------------------------------------------------
def stars_item_is_one_time(item):
    """Косметика, питомцы и pass навсегда покупаются только один раз."""
    if not item:
        return False
    item_type = item.get('type')
    return item_type in {'theme', 'badge', 'pet', 'title_cert', 'bp_premium'}

def stars_item_owned(econ, kind, item_key):
    if kind == 'vippass':
        return item_key == 'pass_forever' and bool(econ.get('vip_forever'))
    if kind == 'cosm':
        item = STARS_COSMETICS.get(item_key)
        if not item:
            return False
        t = item.get('type')
        if t == 'bp_premium':
            return bool(econ.get('bp_premium'))
        if t == 'title_cert':
            return bool(econ.get('has_custom_title_cert'))
        if t == 'theme':
            return item.get('theme_id') in econ.get('purchased_themes', ['default'])
        if t == 'badge':
            return item.get('emoji') in econ.get('inventory', [])
        if t == 'pet':
            return item_key in econ.get('paid_stars_items', [])
    return False

def stars_purchase_error(econ, kind, item_key):
    if not stars_item_owned(econ, kind, item_key):
        return None
    if kind == 'vippass':
        return '❌ Вечный VIP уже куплен. Его нельзя купить повторно. 😸'
    return '❌ Этот вечный Stars-предмет уже есть у вас. Повторная покупка запрещена. 😸'

# ---------------------------------------------------------
# ФУНКЦИИ МАГАЗИНА TELEGRAM STARS
# ---------------------------------------------------------
def render_stars_shop(chat_id, user_id, user_name, category='main', message_id=None):
    econ = get_user_econ(user_id, user_name)
    now_ts = time.time()
    
    vip_status = "❌ Не активен"
    if econ.get('vip_forever'):
        vip_status = "👑 Активен НАВСЕГДА"
    elif econ.get('vip_until', 0) > now_ts:
        vip_date = datetime.fromtimestamp(econ['vip_until'], tz=MSK_TZ).strftime('%d.%m.%Y %H:%M')
        vip_status = f"✅ До {vip_date}"
        
    donated = econ.get('stars_donated', 0)

    markup = InlineKeyboardMarkup(row_width=1)

    if category == 'main':
        lines = [
            "⭐️ <b>МАГАЗИН TELEGRAM STARS (ДОНАТ)</b> 😺",
            "──────────────────────",
            f"👤 Игрок: {make_link(chat_id, user_name, user_id, ping=False)}",
            f"⭐️ Ваш статус VIP: <b>{vip_status}</b>",
            f"🌟 Всего поддержано: <b>{donated} ⭐️</b>\n",
            "<i>Все товары продаются по низким ценам для поддержки развития бота! Оплата происходит официально внутри Telegram за Звёзды (Telegram Stars).</i> 😻\n",
            "<b>Выберите категорию:</b>"
        ]
        markup.add(
            InlineKeyboardButton("💰 Пакеты Ня-коинов (3 ⭐️ = 100к)", callback_data=f"stars_cat_coins:{user_id}"),
            InlineKeyboardButton("👑 VIP Nya Pass (Подписка)", callback_data=f"stars_cat_pass:{user_id}"),
            InlineKeyboardButton("✨ Эксклюзивный визуал и статус", callback_data=f"stars_cat_cosm:{user_id}"),
            InlineKeyboardButton("🔙 Обычный магазин коинов", callback_data=f"shop_main:{user_id}")
        )
    elif category == 'coins':
        lines = [
            "💰 <b>ПАКЕТЫ НЯ-КОИНОВ ЗА ЗВЁЗДЫ</b> 😺",
            "──────────────────────",
            "<i>Мгновенное пополнение игрового баланса по супер-курсу:</i>\n"
        ]
        for p_k, p_v in STARS_COIN_PACKS.items():
            lines.append(f"• <b>{p_v['name']}</b> — <b>{p_v['stars']} ⭐️</b>\n  <i>{p_v['desc']}</i>\n")
            markup.add(InlineKeyboardButton(f"Купить {p_v['name']} ({p_v['stars']} ⭐️)", callback_data=f"star_buy_coins_{p_k}:{user_id}"))
        lines.append("──────────────────────")
        markup.add(InlineKeyboardButton("🔙 Назад в меню Stars", callback_data=f"stars_cat_main:{user_id}"))

    elif category == 'pass':
        lines = [
            "👑 <b>VIP NYA PASS (ПРИВИЛЕГИИ)</b> 😺",
            "──────────────────────",
            "<b>Что даёт VIP Nya Pass:</b>\n"
            "• ⚡️ <b>-30% ко всем таймерам</b> (работа, рыбалка, охота, замеры)\n"
            "• 🎁 <b>УДВОЕНИЕ часового бонуса /bonus (2x)!</b>\n"
            "• 🛡 <b>100% иммунитет</b> к карманным кражам (вас нельзя ограбить!)\n"
            "• ⭐️ Эксклюзивная отметка VIP в карточке профиля (/profile)\n"
            "• 😻 Особое уважение и статус в чате!\n"
        ]
        for pass_k, pass_v in STARS_VIP_PASS.items():
            owned = stars_item_owned(econ, 'vippass', pass_k)
            status = ' ✅ УЖЕ КУПЛЕН' if owned else ''
            lines.append(f"• <b>{pass_v['name']}</b> — <b>{pass_v['stars']} ⭐️</b>{status}")
            if not owned:
                markup.add(InlineKeyboardButton(f"Купить {pass_v['name']} ({pass_v['stars']} ⭐️)", callback_data=f"star_buy_pass_{pass_k}:{user_id}"))
        lines.append("──────────────────────")
        markup.add(InlineKeyboardButton("🔙 Назад в меню Stars", callback_data=f"stars_cat_main:{user_id}"))

    elif category == 'cosm':
        lines = [
            "✨ <b>ЭКСКЛЮЗИВНЫЙ ВИЗУАЛ И СТАТУС</b> 😺",
            "──────────────────────",
            "<i>Уникальная косметика и привилегии, доступные только за Звёзды:</i>\n"
        ]
        for c_k, c_v in STARS_COSMETICS.items():
            owned = stars_item_owned(econ, 'cosm', c_k)
            status = ' ✅ УЖЕ КУПЛЕНО' if owned else ''
            lines.append(f"• <b>{c_v['name']}</b> — <b>{c_v['stars']} ⭐️</b>{status}\n  <i>{c_v['desc']}</i>")
            if not owned:
                markup.add(InlineKeyboardButton(f"Купить: {c_v['name']} ({c_v['stars']} ⭐️)", callback_data=f"star_buy_cosm_{c_k}:{user_id}"))
        lines.append("──────────────────────")
        markup.add(InlineKeyboardButton("🔙 Назад в меню Stars", callback_data=f"stars_cat_main:{user_id}"))

    text = "\n".join(lines)
    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            return
        except Exception:
            pass
    try:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception:
        pass

def send_shop_menu(chat_id, user_id, user_tag, message_id=None):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton('⭐️ ЗВЁЗДНЫЙ МАГАЗИН (Telegram Stars) ⭐️', callback_data=f'shop_cat_stars_main:{user_id}')
    )
    markup.add(
        InlineKeyboardButton('✨ Значки профиля', callback_data=f'shop_cat_badges_0:{user_id}'),
        InlineKeyboardButton('👑 Титулы с баффом', callback_data=f'shop_cat_titles_0:{user_id}')
    )
    markup.add(
        InlineKeyboardButton('🎨 Темы профиля', callback_data=f'shop_cat_themes:{user_id}'),
        InlineKeyboardButton('🧰 Расходники', callback_data=f'shop_cat_buffs:{user_id}')
    )
    markup.add(
        InlineKeyboardButton('💍 Кольца (Брак)', callback_data=f'shop_cat_rings:{user_id}'),
        InlineKeyboardButton('🐾 Зоомагазин', callback_data=f'shop_cat_pets_0:{user_id}')
    )
    markup.add(
        InlineKeyboardButton('🏎 Гараж', callback_data=f'shop_cat_garage:{user_id}'),
        InlineKeyboardButton('🪴 Семена Сада', callback_data=f'shop_cat_garden:{user_id}')
    )
    markup.add(InlineKeyboardButton('🎙 Студия Стримера', callback_data=f'shop_cat_stream:{user_id}'))

    text = (
        "🏪 <b>ГЛОБАЛЬНЫЙ МАГАЗИН НЯ-БОТА</b> 😺\n"
        "──────────────────────\n"
        "Выберите интересующий вас каталог товаров: 😸"
    )
    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return
    try: bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception as e: print(f"[NONFATAL ERROR] {e}")

# ---------------------------------------------------------
# БРАКИ, СЕМЬЯ И ПОДАРКИ
# ---------------------------------------------------------
@bot.message_handler(commands=['marry', 'брак'])
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

    prop_id = f"{user_id}_{target_user_id or 0}_{int(time.time())}"
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

@bot.message_handler(commands=['family', 'семья'])
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
        f"──────────────────────\n"
        f"💍 Кольцо: {ring_emoji} <b>{ring_name}</b>\n"
        f"👫 Супруг(а): {partner_link}\n"
        f"⏳ Дней в браке: <b>{days_together} дн.</b>\n"
        f"💰 Семейный сейф: <b>{vault} Ня-коинов 🪙</b>\n"
        f"──────────────────────\n"
        f"💡 <b>Команды семьи:</b> 😸\n"
        f"• <code>подарок</code> — романтический букет (100 🪙)\n"
        f"• <code>семейный сейф положить 100</code>\n"
        f"• <code>семейный сейф снять 100</code>\n"
        f"• <code>развод</code> — расторгнуть брак"
    )
    bot.reply_to(message, text, parse_mode='HTML')

@bot.message_handler(commands=['gift', 'подарок'])
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
    if econ['balance'] < cost:
        bot.reply_to(message, f"❌ На роскошный букет нужно <b>{cost} 🪙</b>! 😿")
        return

    econ['balance'] -= cost
    p_econ = get_user_econ(p_id, p_tag)
    p_econ['balance'] += 80
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

@bot.message_handler(commands=['divorce', 'развод'])
def cmd_divorce(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    if not econ.get('marriage'):
        bot.reply_to(message, "❌ Вы не состоите в браке! 😿")
        return

    m = econ['marriage']
    p_id = m.get('partner_id')
    p_tag = m.get('partner_name')
    p_econ = get_user_econ(p_id, p_tag)

    vault = m.get('vault', 0)
    split_coins = vault // 2
    econ['balance'] += split_coins
    if p_id != 0:
        p_econ['balance'] += (vault - split_coins)
        p_econ['marriage'] = None
    econ['marriage'] = None
    mark_dirty()

    bot.reply_to(message, f"💔 <b>Брак расторгнут.</b> 😿\nСемейный сейф ({vault} 🪙) разделен поровну между бывшими супругами (+{split_coins} 🪙 каждому).", parse_mode='HTML')

# ---------------------------------------------------------
# ИГРЫ: БЛЭКДЖЕК, ЦУЕФА
# ---------------------------------------------------------
def calculate_bj_score(cards):
    score = sum(cards)
    aces = cards.count(11)
    while score > 21 and aces > 0:
        score -= 10
        aces -= 1
    return score

def process_bj_game(message, bet):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    if bet < 30:
        bot.reply_to(message, "❌ Минимальная ставка — 30 Ня-коинов! 😾")
        return

    if econ['balance'] < bet:
        bot.reply_to(message, f"❌ Недостаточно Ня-коинов! У вас: {econ['balance']} 🪙 😿")
        return

    econ['balance'] -= bet
    process_casino_bet(bet, chat_id)

    game_id = f"bj_{user_id}_{time.time_ns()}"
    deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4
    random.shuffle(deck)

    p_cards = [deck.pop(), deck.pop()]
    d_cards = [deck.pop(), deck.pop()]

    active_bj_games[game_id] = {
        'user_id': user_id, 'user_tag': user_name, 'username': message.from_user.username,
        'bet': bet, 'deck': deck, 'p_cards': p_cards, 'd_cards': d_cards, 'finished': False, 'start_time': time.time()
    }

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🃏 Взять карту", callback_data=f"bj_hit_{game_id}:{user_id}"),
        InlineKeyboardButton("✋ Хватит", callback_data=f"bj_stand_{game_id}:{user_id}")
    )

    p_score = calculate_bj_score(p_cards)
    bot.send_message(
        chat_id,
        f"🃏 <b>БЛЭКДЖЕК (21 ОЧКО)</b> 😺\n──────────────────────\n"
        f"👤 Игрок: {make_link(chat_id, user_name, user_id, ping=True)}\n💰 Ставка: <b>{bet} 🪙</b>\n\n"
        f"🎴 Ваши карты: {p_cards} (Сумма: <b>{p_score}</b>)\n🤖 Дилер: [{d_cards[0]}, ❓]\n──────────────────────",
        reply_markup=markup, parse_mode='HTML'
    )

@bot.message_handler(commands=['bj', 'blackjack', 'блэкджек', '21'])
def cmd_bj(message):
    if not can_process_user_message(message):
        return
    match = re.search(r'(?:/bj|blackjack|блэкджек|21)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(match.group(1)) if match and match.group(1) else 50
    process_bj_game(message, bet)

@bot.message_handler(commands=['rps', 'цуефа'])
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

    target_econ = get_user_econ(target_user_id, target_user)
    if econ['balance'] < bet:
        bot.reply_to(message, f"❌ У вас недостаточно Ня-коинов! Ваш баланс: {econ['balance']} 🪙 😿")
        return
    if target_econ['balance'] < bet:
        bot.reply_to(message, f"❌ У соперника недостаточно коинов для ставки ({target_econ['balance']} / {bet} 🪙)! 😿")
        return

    econ['balance'] -= bet
    target_econ['balance'] -= bet
    mark_dirty()

    game_id = f"rps_{user_id}_{target_user_id}_{time.time_ns()}"
    active_rps_games[game_id] = {
        'p1_id': user_id, 'p1_tag': user_name,
        'p2_id': target_user_id, 'p2_tag': target_user,
        'bet': bet, 'p1_choice': None, 'p2_choice': None,
        'start_time': time.time(), 'finished': False
    }

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🪨 Камень", callback_data=f"rps_r_{game_id}"),
        InlineKeyboardButton("✂️ Ножницы", callback_data=f"rps_s_{game_id}"),
        InlineKeyboardButton("📄 Бумага", callback_data=f"rps_p_{game_id}")
    )

    bot.send_message(
        chat_id,
        f"✌️ <b>ДУЭЛЬ: КАМЕНЬ-НОЖНИЦЫ-БУМАГА!</b> 😺\n──────────────────────\n"
        f"⚔️ {make_link(chat_id, user_name, user_id, ping=True)} VS {make_link(chat_id, target_user, target_user_id, ping=True)}\n"
        f"💰 Ставка: <b>{bet} 🪙</b> с каждого (Общий банк: <b>{bet * 2} 🪙</b>)!\n"
        f"──────────────────────\n"
        f"<i>Оба дуэлянта, сделайте свой выбор на кнопках ниже:</i> 😸",
        reply_markup=markup, parse_mode='HTML'
    )

# ---------------------------------------------------------
# КРИПТО-БИРЖА И ТОРГОВЛЯ
# ---------------------------------------------------------
@bot.message_handler(commands=['market', 'биржа', 'crypto', 'крипта'])
def cmd_market(message):
    if not can_process_user_message(message):
        return
    market = get_market_data()
    lines = [
        "📈 <b>НЯ-БИРЖА КРИПТОВАЛЮТ И АКЦИЙ</b> 😺",
        "──────────────────────",
        "<i>Курсы обновляются автоматически каждые 30 минут:</i>\n"
    ]
    for ticker, info in market.items():
        price = info['price']
        old_price = info.get('old_price', price)
        diff = price - old_price
        pct = (diff / old_price * 100) if old_price > 0 else 0
        trend = "🟢 📈 +" if diff >= 0 else "🔴 📉 "
        lines.append(f"• <b>{info['name']}</b> [{ticker}]\n  Курс: <b>{price:.2f} 🪙</b> ({trend}{pct:.1f}%)\n")

    lines.append("──────────────────────\n💡 <b>Как торговать:</b> 😸")
    lines.append("• <code>купить крипту NYA 5</code>\n• <code>продать крипту NYA 5</code>\n• <code>портфель</code> — посмотреть свои активы")
    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')

@bot.message_handler(commands=['portfolio', 'портфель'])
def cmd_portfolio(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    market = get_market_data()

    portfolio = econ.get('crypto_portfolio', {})
    total_val = 0.0
    lines = [f"💼 <b>ИНВЕСТИЦИОННЫЙ ПОРТФЕЛЬ: {make_link(message.chat.id, user_name, user_id, ping=False)}</b> 😺", "──────────────────────"]

    has_assets = False
    for ticker, amount in portfolio.items():
        if amount > 0.0001:
            has_assets = True
            cur_price = market.get(ticker, {}).get('price', 1.0)
            val = amount * cur_price
            total_val += val
            lines.append(f"• <b>{ticker}</b>: {amount:.2f} шт. (Оценка: <b>{val:.2f} 🪙</b>)")

    if not has_assets: lines.append("🎒 Ваш крипто-портфель пока пуст! Купите активы в <code>биржа</code>. 😿")
    else: lines.extend(["──────────────────────", f"📊 <b>Общая стоимость: {total_val:.2f} Ня-коинов 🪙</b> 😻"])
    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')

def trade_crypto(chat_id, user_id, user_tag, action, ticker, amount_str, reply_msg=None, username=None):
    market = get_market_data()
    ticker = ticker.upper().strip()

    if ticker not in market:
        available = ', '.join(market.keys())
        msg = f"❌ Неверный тикер! Доступные активы: <b>{available}</b> 😾"
        if reply_msg: bot.reply_to(reply_msg, msg, parse_mode='HTML')
        else: bot.send_message(chat_id, msg, parse_mode='HTML')
        return

    import math
    try:
        amount = float(amount_str)
        if math.isnan(amount) or math.isinf(amount) or amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        msg = "❌ Укажите корректное положительное число монет! 😾"
        if reply_msg: bot.reply_to(reply_msg, msg, parse_mode='HTML')
        else: bot.send_message(chat_id, msg, parse_mode='HTML')
        return

    econ = get_user_econ(user_id, user_tag, username=username)
    portfolio = econ.setdefault('crypto_portfolio', {})
    asset = market[ticker]
    price = asset['price']
    total_cost = round(price * amount, 2)

    if action == 'buy':
        charge_cost = max(1, math.ceil(total_cost))
        if econ['balance'] < charge_cost:
            msg = f"❌ Недостаточно коинов! Нужно <b>{charge_cost} 🪙</b> (У вас: {econ['balance']} 🪙). 😿"
            if reply_msg: bot.reply_to(reply_msg, msg, parse_mode='HTML')
            else: bot.send_message(chat_id, msg, parse_mode='HTML')
            return

        econ['balance'] -= charge_cost
        portfolio[ticker] = portfolio.get(ticker, 0.0) + amount
        check_achievements(user_id, user_tag, 'crypto_trades', 1, chat_id, username=username)
        add_account_exp(user_id, user_tag, 10, username=username)
        mark_dirty()

        msg = f"✅ <b>УСПЕШНАЯ ПОКУПКА!</b> 😻\n──────────────────────\nКуплено: <b>{amount:.2f} {ticker}</b> ({asset['name']})\nСписано: <b>-{charge_cost} 🪙</b>\nОстаток баланса: <b>{econ['balance']} 🪙</b>"
        if reply_msg: bot.reply_to(reply_msg, msg, parse_mode='HTML')
        else: bot.send_message(chat_id, msg, parse_mode='HTML')

    elif action == 'sell':
        user_amount = portfolio.get(ticker, 0.0)
        if user_amount < amount:
            msg = f"❌ Недостаточно {ticker}! В наличии: <b>{user_amount:.2f} шт.</b> 😿"
            if reply_msg: bot.reply_to(reply_msg, msg, parse_mode='HTML')
            else: bot.send_message(chat_id, msg, parse_mode='HTML')
            return

        portfolio[ticker] -= amount
        if portfolio[ticker] <= 0.0001: del portfolio[ticker]

        earned = max(1, int(round(total_cost)))
        econ['balance'] += earned
        check_achievements(user_id, user_tag, 'crypto_trades', 1, chat_id, username=username)
        add_account_exp(user_id, user_tag, 10, username=username)
        mark_dirty()

        msg = f"💰 <b>УСПЕШНАЯ ПРОДАЖА!</b> 😸\n──────────────────────\nПродано: <b>{amount:.2f} {ticker}</b>\nВыручка: <b>+{earned} 🪙</b>\nНовый баланс: <b>{econ['balance']} 🪙</b>"
        if reply_msg: bot.reply_to(reply_msg, msg, parse_mode='HTML')
        else: bot.send_message(chat_id, msg, parse_mode='HTML')

# ---------------------------------------------------------
# СИСТЕМА РАБОТЫ И ТРЕНИРОВКИ
# ---------------------------------------------------------
def train_work_exp(user_id, user_tag, username=None):
    econ = get_user_econ(user_id, user_tag, username=username)
    now = time.time()
    cooldown = 900
    left = cooldown_text(econ.get('last_train_time', 0), cooldown, econ)
    if left: return False, f"⏳ Тренировка доступна раз в 15 минут! Ждать: <b>{left}</b>. 😿"

    gain = random.randint(15, 40)
    econ['work_exp'] = econ.get('work_exp', 0) + gain
    econ['last_train_time'] = now
    add_account_exp(user_id, user_tag, gain, username=username)
    mark_dirty()
    return True, f"🎓 Вы усердно позанимались! 😸\nПолучено: <b>+{gain} EXP</b> опыта работы (Всего: <b>{econ['work_exp']} EXP</b>)."

@bot.message_handler(commands=['work', 'работа'])
def cmd_work(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    lines = [
        "💼 <b>БИРЖА ТРУДА И ВАКАНСИЙ</b> 😺",
        "──────────────────────",
        f"👤 Ваш опыт работы: <b>{econ.get('work_exp', 0)} EXP</b>\n",
        "<b>Доступные вакансии:</b> 😸"
    ]
    for j_id, j in JOBS.items():
        lines.append(f"• <b>{j['name']}</b>: от <code>{j['req_exp']} EXP</code> (З/П: {j['min_pay']}-{j['max_pay']} 🪙)")
    lines.append("──────────────────────")

    markup = InlineKeyboardMarkup()
    for job_id, job in JOBS.items():
        btn_text = f"{job['name']} ({job['req_exp']} EXP)"
        markup.add(InlineKeyboardButton(btn_text, callback_data=f"do_job_{job_id}:{user_id}"))

    markup.add(InlineKeyboardButton("🎓 Пройти тренировку (+EXP)", callback_data=f"train_exp_btn:{user_id}"))
    bot.reply_to(message, "\n".join(lines), reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['train', 'опыт'])
def cmd_train(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    _, text_resp = train_work_exp(user_id, user_name, username=message.from_user.username)
    bot.reply_to(message, text_resp, parse_mode='HTML')

@bot.message_handler(commands=['sell', 'продать'])
def cmd_sell(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    total_earned = 0
    items_sold = 0
    price_multiplier = 2.0 if gold_rush_event.get('active') else 1.0

    for fish_name, count in list(econ.get('fish_inventory', {}).items()):
        price = 20
        for f_item in FISH_TYPES:
            if f_item[0] == fish_name: price = int(f_item[2] * price_multiplier); break
        total_earned += price * count
        items_sold += count
    econ['fish_inventory'] = {}

    for hunt_name, count in list(econ.get('hunt_inventory', {}).items()):
        price = 25
        for h_item in HUNT_TYPES:
            if h_item[0] == hunt_name: price = int(h_item[2] * price_multiplier); break
        total_earned += price * count
        items_sold += count
    econ['hunt_inventory'] = {}

    if items_sold == 0:
        bot.reply_to(message, "🎒 У вас нет рыбы или охотничьих трофеев для продажи! 😿")
        return

    econ['balance'] += total_earned
    mark_dirty()
    rush_note = " (🌟 Золотая лихорадка x2.0!)" if gold_rush_event.get('active') else ""
    bot.reply_to(message, f"💰 Вы успешно продали добычу на сумму <b>+{total_earned} Ня-коинов 🪙</b>{rush_note}! 😻\nБаланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')

@bot.message_handler(commands=['profile', 'профиль'])
def cmd_profile(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    send_user_profile(message.chat.id, user_name, message.from_user.id, message_to_reply=message, username=message.from_user.username)

@bot.message_handler(commands=['achievements', 'ачивки'])
def cmd_achievements(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    unlocked = econ.get('achievements', [])

    lines = [f"🏆 <b>ДОСТИЖЕНИЯ: {make_link(message.chat.id, user_name, user_id, ping=False)}</b> 😺", "──────────────────────"]
    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id in unlocked: lines.append(f"✅ <b>{ach['title']}</b> — {ach['desc']} (+{ach['reward']} 🪙)")
        else: lines.append(f"🔒 <b>{ach['title']}</b> — {ach['desc']} (<b>+{ach['reward']} 🪙</b>)")
    lines.append("──────────────────────")
    lines.append(f"Прогресс: <b>{len(unlocked)}/{len(ACHIEVEMENTS)}</b> открыто. 😸")
    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')

@bot.message_handler(commands=['balance', 'баланс'])
def cmd_balance(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(message.from_user.id, user_name, username=message.from_user.username)
    streak_info = f"\n🔥 <b>Ежедневный стрик:</b> {econ.get('bonus_streak', 0)} дн."
    bot.reply_to(message, f"💵 <b>Ваш кошелек:</b> <b>{econ['balance']} Ня-коинов 💸</b>\n🏦 <b>В банке:</b> <b>{econ.get('bank_deposit', 0)} 🪙</b>{streak_info} 😺", parse_mode='HTML')


@bot.message_handler(commands=['stars', 'donate', 'vip', 'донат', 'звезды', 'пасс'])
def cmd_stars(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_stars_shop(message.chat.id, user_id, user_name, category='main')


@bot.message_handler(commands=['inventory','инвентарь','инв'])
def cmd_inventory(message):
    if not can_process_user_message(message): return
    uid=message.from_user.id; name=(f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ=get_user_econ(uid,name,username=message.from_user.username); pet=econ.get('pet')
    titles=[TITLES[t]['text'] for t in econ.get('titles',[]) if t in TITLES]
    lines=['🎒 <b>ИНВЕНТАРЬ И КОЛЛЕКЦИЯ</b>','──────────────────────',f"🐾 Питомец: <b>{pet.get('name')}</b>" if pet else '🐾 Питомец: <i>нет</i>',f"🏅 Значки: {', '.join(map(str,econ.get('inventory',[]))) if econ.get('inventory') else 'нет'}",f"👑 Титулы: {', '.join(titles) if titles else 'нет'}",f"🎨 Темы: {', '.join(econ.get('purchased_themes',['default']))}",f"⭐️ Stars-предметы: {', '.join(econ.get('paid_stars_items',[])) if econ.get('paid_stars_items') else 'нет'}",'──────────────────────','💡 Экипировка доступна через /profile и /shop.']
    bot.reply_to(message,'\n'.join(lines),parse_mode='HTML')

@bot.message_handler(commands=['shop', 'магазин'])
def cmd_shop(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    send_shop_menu(message.chat.id, message.from_user.id, user_name)

@bot.message_handler(commands=['tasks', 'задания', 'квесты'])
def cmd_tasks(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    bot.reply_to(message, format_daily_tasks(message.from_user.id, user_name), parse_mode='HTML')

# ---------------------------------------------------------
# БИОМЕТРИЯ: IQ, ЖИР, ПЯТКА, ХРОМОСОМЫ
# ---------------------------------------------------------
@bot.message_handler(commands=['iq'])
def cmd_iq(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    now_ts = time.time()
    cooldown = 1800
    left = cooldown_text(econ.get('last_iq_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Тест на IQ доступен раз в 30 минут! 😿\nПодождите: <b>{left}</b>.", parse_mode='HTML')
        return

    change = random.randint(-5, 15)
    econ['iq'] = max(0, econ.get('iq', 100) + change)
    econ['last_iq_time'] = now_ts
    mark_dirty()
    completed = track_daily_task(user_id, user_name, 'iq', 1, chat_id, username=message.from_user.username)
    sign = "+" if change >= 0 else ""
    bot.reply_to(message, f"🧠 {make_link(chat_id, user_name, user_id, ping=True)}, ваш IQ: <b>{econ['iq']} ({sign}{change}) 📊</b> 😺", parse_mode='HTML')
    for task_name, task_reward in completed: bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙 😻', parse_mode='HTML')

@bot.message_handler(commands=['fat'])
def cmd_fat(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    now_ts = time.time()
    cooldown = 1800
    left = cooldown_text(econ.get('last_fat_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Замер жира доступен раз в 30 минут! 😿\nПодождите: <b>{left}</b>.", parse_mode='HTML')
        return

    change = random.randint(-4, 6)
    econ['fat'] = max(0, min(100, econ.get('fat', 20) + change))
    econ['last_fat_time'] = now_ts
    mark_dirty()
    completed = track_daily_task(user_id, user_name, 'fat', 1, chat_id, username=message.from_user.username)
    sign = "+" if change >= 0 else ""
    bot.reply_to(message, f"🥩 {make_link(chat_id, user_name, user_id, ping=True)}, процент жира: <b>{econ['fat']}% ({sign}{change}%) 🍔</b> 😺", parse_mode='HTML')
    for task_name, task_reward in completed: bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙 😻', parse_mode='HTML')

@bot.message_handler(commands=['foot'])
def cmd_foot(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    now_ts = time.time()
    cooldown = 1200
    left = cooldown_text(econ.get('last_foot_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Измерить пятку можно раз в 20 минут! 😿\nПодождите: <b>{left}</b>.", parse_mode='HTML')
        return

    change = random.randint(-3, 4)
    econ['foot_size'] = max(5, min(80, econ.get('foot_size', 25) + change))
    econ['last_foot_time'] = now_ts
    mark_dirty()
    sign = "+" if change >= 0 else ""
    bot.reply_to(message, f"🦶 {make_link(chat_id, user_name, user_id, ping=True)}, размер пятки: <b>{econ['foot_size']} см ({sign}{change} см) 🦶</b> 😺", parse_mode='HTML')

@bot.message_handler(commands=['chromosomes', 'хромосомы', 'хромосома'])
def cmd_chromosomes(message):
    if not can_process_user_message(message):
        return
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    now_ts = time.time()
    cooldown = 1200
    left = cooldown_text(econ.get('last_chromosomes_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"🧬 Генетический анализ доступен раз в 20 минут! 😿\nПодождите: <b>{left}</b>.", parse_mode='HTML')
        return

    change = random.choice([-2, -1, 0, 1, 1, 2, 3])
    cur_chr = econ.get('chromosomes', 46)
    new_chr = max(38, min(100, cur_chr + change))
    econ['chromosomes'] = new_chr
    econ['last_chromosomes_time'] = now_ts
    mark_dirty()

    completed = track_daily_task(user_id, user_name, 'chromosomes', 1, chat_id, username=message.from_user.username)
    check_achievements(user_id, user_name, 'chromosomes_check', 1, chat_id, username=message.from_user.username)
    sign = "+" if change >= 0 else ""

    if new_chr == 46: comment = "Идеальный человеческий баланс! ✨ 😻"
    elif new_chr == 47: comment = "Обнаружена экстра-хромосома сверхразума! ⚡️ 🙀"
    elif new_chr > 47: comment = "Межгалактический уровень ДНК! 👽🚀 😹"
    else: comment = "Кажется, пара хромосом взяли отгул... 🔍 😿"

    u_link = make_link(chat_id, user_name, user_id, ping=True)
    bot.reply_to(message, f"🧬 <b>ГЕНЕТИЧЕСКИЙ ТЕСТ:</b> {u_link}\n──────────────────────\nКоличество хромосом: <b>{new_chr} ({sign}{change}) 🧬</b>\n📝 <i>{comment}</i>\n────────────────────── 😺", parse_mode='HTML')
    for task_name, task_reward in completed: bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙 😻', parse_mode='HTML')

# ---------------------------------------------------------
# ИНТЕРАКТИВНЫЕ ТОПЫ С КНОПКАМИ
# ---------------------------------------------------------
def render_top_menu(chat_id, user_id=None, category='rich', message_id=None):
    econ_items = db.get('economy', {})
    now = time.time()
    uid_tag = f":{user_id}" if user_id else ""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 Богачи", callback_data=f"top_cat_rich{uid_tag}"),
        InlineKeyboardButton("🍆 Писюн", callback_data=f"top_cat_dick{uid_tag}")
    )
    markup.add(
        InlineKeyboardButton("🧠 IQ", callback_data=f"top_cat_iq{uid_tag}"),
        InlineKeyboardButton("⚖️ Карма", callback_data=f"top_cat_karma{uid_tag}")
    )
    markup.add(
        InlineKeyboardButton("🦶 Пятки", callback_data=f"top_cat_foot{uid_tag}"),
        InlineKeyboardButton("🧬 Хромосомы", callback_data=f"top_cat_chr{uid_tag}")
    )
    markup.add(InlineKeyboardButton("💬 Сообщения (Актив)", callback_data=f"top_cat_msg{uid_tag}"))

    # Только пользователи, которые были замечены в этом чате. Для старых
    # аккаунтов без chat_ids оставляем их вне чатового топа до следующего сообщения.
    visible_items = {
        k: v for k, v in econ_items.items()
        if chat_id in v.get('chat_ids', []) and (category in ['rich', 'msg', 'karma'] or v.get('invis_until', 0) <= now)
    }

    if category == 'rich':
        sorted_data = sorted(visible_items.items(), key=lambda x: (x[1].get('balance', 0) + x[1].get('bank_deposit', 0)), reverse=True)
        title = "🏆 <b>ТОП БОГАЧЕЙ ЧАТА (Карман + Банк)</b> 😻"
        val_formatter = lambda info: f"<b>{info.get('balance', 0) + info.get('bank_deposit', 0)} 🪙</b>"
    elif category == 'dick':
        sorted_data = sorted(visible_items.items(), key=lambda x: x[1].get('dick_size', 15), reverse=True)
        title = "🍆 <b>ТОП ПО РАЗМЕРУ ПИСЮНА</b> 🙀"
        val_formatter = lambda info: f"<b>{info.get('dick_size', 15)} см 📏</b>"
    elif category == 'iq':
        sorted_data = sorted(visible_items.items(), key=lambda x: x[1].get('iq', 100), reverse=True)
        title = "🧠 <b>ТОП ПО УРОВНЮ IQ</b> 😸"
        val_formatter = lambda info: f"<b>{info.get('iq', 100)} IQ</b>"
    elif category == 'karma':
        sorted_data = sorted(visible_items.items(), key=lambda x: x[1].get('karma', 0), reverse=True)
        title = "⚖️ <b>ТОП КАРМЫ (Самые Светлые)</b> 😇"
        val_formatter = lambda info: f"<b>{info.get('karma', 0)} 😇</b>"
    elif category == 'foot':
        sorted_data = sorted(visible_items.items(), key=lambda x: x[1].get('foot_size', 25), reverse=True)
        title = "🦶 <b>ТОП ПО РАЗМЕРУ ПЯТКИ</b> 😸"
        val_formatter = lambda info: f"<b>{info.get('foot_size', 25)} см 🦶</b>"
    elif category == 'chr':
        sorted_data = sorted(visible_items.items(), key=lambda x: x[1].get('chromosomes', 46), reverse=True)
        title = "🧬 <b>ТОП ПО КОЛИЧЕСТВУ ХРОМОСОМ</b> 😺"
        val_formatter = lambda info: f"<b>{info.get('chromosomes', 46)} 🧬</b>"
    elif category == 'msg':
        sorted_data = sorted(visible_items.items(), key=lambda x: x[1].get('msg_stats', {}).get('total_count', 0), reverse=True)
        title = "💬 <b>ТОП ПО СООБЩЕНИЯМ В ЧАТЕ</b> 😻"
        val_formatter = lambda info: f"<b>{info.get('msg_stats', {}).get('total_count', 0)} смс</b>"
    else:
        sorted_data = []
        title = "🏆 <b>ТОП УЧАСТНИКОВ</b>"
        val_formatter = lambda info: ""

    lines = [title, "──────────────────────"]
    for idx, (k, info) in enumerate(sorted_data[:10], 1):
        u_name = info.get('display_name', 'Пользователь')
        u_id = info.get('user_id')
        lines.append(f"{idx}. {make_link(chat_id, u_name, u_id, ping=False)} — {val_formatter(info)}")

    if not sorted_data: lines.append("<i>Данных для отображения пока нет... 😿</i>")
    lines.extend(["──────────────────────", "👇 <i>Нажмите категорию ниже для переключения:</i> 😺"])

    text = "\n".join(lines)
    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return
    try: bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception as e: print(f"[NONFATAL ERROR] {e}")


def render_activity_leaderboard(chat_id, period='day'):
    key='day_count' if period=='day' else 'week_count'; label='СЕГОДНЯ' if period=='day' else 'ЭТУ НЕДЕЛЮ'
    items=[]
    for info in db.get('economy',{}).values():
        count=info.get('msg_stats',{}).get(key,0)
        if count>0: items.append((count,info))
    items.sort(key=lambda x:x[0],reverse=True)
    lines=[f'🏆 <b>ТОП АКТИВНОСТИ {label}</b>','──────────────────────']
    for i,(count,info) in enumerate(items[:10],1): lines.append(f"{i}. {make_link(chat_id,info.get('display_name','Пользователь'),info.get('user_id'),ping=False)} — <b>{count} смс</b>")
    if not items: lines.append('<i>Активности пока нет.</i>')
    bot.send_message(chat_id,'\n'.join(lines),parse_mode='HTML')

@bot.message_handler(commands=['top_daily','топ_день'])
def cmd_top_daily(message):
    if can_process_user_message(message): render_activity_leaderboard(message.chat.id,'day')

@bot.message_handler(commands=['top_weekly','топ_неделя'])
def cmd_top_weekly(message):
    if can_process_user_message(message): render_activity_leaderboard(message.chat.id,'week')

@bot.message_handler(commands=['top', 'топ'])
def cmd_top(message):
    if not can_process_user_message(message):
        return
    render_top_menu(message.chat.id, user_id=message.from_user.id, category='rich')

# ---------------------------------------------------------
# ГЛАВНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ И КОМАНД
# ---------------------------------------------------------

# ---------------------------------------------------------
# ИГРА СЕЙФ (ВЗЛОМ 4-ЗНАЧНОГО ШИФРА)
# ---------------------------------------------------------
@bot.message_handler(commands=['safe', 'сейф'])
def cmd_safe(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    chat_id = message.chat.id

    in_j, left_j = is_in_jail(user_id)
    if in_j:
        bot.reply_to(message, f"🔒 Вы отбываете срок в КПЗ! До выхода: <b>{left_j} мин.</b> 😿", parse_mode='HTML')
        return

    safe = get_chat_safe(chat_id)
    pot = safe.get('pot', 30000)
    tried = safe.setdefault('tried_codes', [])

    parts = message.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(
            message,
            f"🔒 <b>СЕЙФ ЧАТА (4-ЗНАЧНЫЙ ШИФР)</b> 🏦 😺\n"
            f"──────────────────────\n"
            f"💰 Накопленный банк сейфа: <b>{pot:,} Ня-коинов 🪙</b>!\n"
            f"<i>(В сейф отчисляется 50% от всех проигрышей чата в казино и спорте!)</i> 😻\n\n"
            f"📝 Уже опробовано комбинаций: <b>{len(tried)}</b>\n"
            f"💡 Чтобы попробовать угадать шифр (раз в 20 мин):\n"
            f"👉 <code>/safe 4815</code>\n"
            f"──────────────────────",
            parse_mode='HTML'
        )
        return

    code_entered = parts[1].strip()
    if not (len(code_entered) == 4 and code_entered.isdigit()):
        bot.reply_to(message, "❌ Код сейфа должен состоять ровно из 4 цифр (от 0000 до 9999)!\nПример: <code>/safe 4815</code> 😾", parse_mode='HTML')
        return

    now = time.time()
    last_try = econ.get('last_safe_try', 0)
    cooldown = 1200
    left = cooldown_text(last_try, cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Руки дрожат от отмычек! Следующая попытка через: <b>{left}</b>. 😿", parse_mode='HTML')
        return

    if code_entered in tried:
        bot.reply_to(message, f"❌ <b>Этот код уже писали!</b> Комбинацию <code>{code_entered}</code> уже кто-то вводил, и она оказалась неверной. Попробуйте другой код! 😿\n💰 В сейфе: <b>{pot:,} 🪙</b>", parse_mode='HTML')
        return

    econ['last_safe_try'] = now
    u_link = make_link(chat_id, user_name, user_id, ping=True)

    if code_entered == safe.get('code'):
        won_pot = pot
        econ['balance'] += won_pot
        add_account_exp(user_id, user_name, 200, username=message.from_user.username)
        change_karma(user_id, user_name, 5)

        new_code = f"{random.randint(0, 9999):04d}"
        safe['code'] = new_code
        safe['pot'] = 15000
        safe['tried_codes'] = []
        mark_dirty()

        log_event('СЕЙФ ВЗЛОМАН', f'Игрок {u_link} подобрал шифр <b>{code_entered}</b> и сорвал джекпот <b>{won_pot:,} 🪙</b>!')

        win_msg = (
            f"🎉💥🔓 <b>СЕЙФ УСПЕШНО ВЗЛОМАН!</b> 😻\n"
            f"──────────────────────\n"
            f"👤 Мега-медвежатник: {u_link}\n"
            f"🔑 Верный шифр: <b>{code_entered}</b>\n"
            f"💰 Сорванный куш: <b>+{won_pot:,} Ня-коинов 🪙</b>! 🙀\n"
            f"⭐ Опыт: <b>+200 EXP</b> | Карма: <b>+5</b>\n"
            f"──────────────────────\n"
            f"<i>Замки заменены на новые, в сейф заложен стартовый фонд 15,000 🪙! Охота продолжается!</i> 😸"
        )
        bot.send_message(chat_id, win_msg, parse_mode='HTML')
    else:
        tried.append(code_entered)
        add_account_exp(user_id, user_name, 5, username=message.from_user.username)
        mark_dirty()
        bot.reply_to(
            message,
            f"❌ <b>Щёлк! Код {code_entered} не подошёл!</b> 😿\n"
            f"Этот код добавлен в список неудачных попыток.\n"
            f"💰 Текущий банк сейфа: <b>{pot:,} Ня-коинов 🪙</b> (ждёт своего победителя!)\n"
            f"⏳ Повторная попытка доступна через 20 минут.",
            parse_mode='HTML'
        )

# ---------------------------------------------------------
# СЕМЕЙНЫЙ ДОМ И ОБУСТРОЙСТВО (/house, /дом)
# ---------------------------------------------------------
def render_house_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    m = econ.get('marriage')
    if not m:
        text = "❌ <b>Семейный дом доступен только тем, кто состоит в браке!</b> 😿\nСделайте предложение через <code>брак @username</code>!"
        if message_id:
            try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            return
        bot.send_message(chat_id, text, parse_mode='HTML')
        return

    update_family_house_income(m)
    mark_dirty()

    cur_house = m.get('house')
    cur_furniture = m.get('furniture', [])

    markup = InlineKeyboardMarkup(row_width=1)

    if not cur_house:
        lines = [
            "🏡 <b>КАТАЛОГ СЕМЕЙНОЙ НЕДВИЖИМОСТИ</b> 😺",
            "──────────────────────",
            f"Супруги: <b>{m.get('partner_name')}</b> и {make_link(chat_id, user_name, user_id, ping=False)}",
            "<i>Купите ваш первый семейный дом в одном из городов мира! Дом приносит постоянный пассивный доход в семейный сейф.</i> 😻\n",
            "<b>Доступные дома:</b>"
        ]
        for h_k, h_v in FAMILY_HOUSES.items():
            lines.append(f"• <b>{h_v['name']}</b> — <code>{h_v['price']:,} 🪙</code> (Доход: +{h_v['income']} 🪙/ч в сейф)")
            markup.add(InlineKeyboardButton(f"Купить {h_v['name']} ({h_v['price']:,} 🪙)", callback_data=f"buy_house_{h_k}:{user_id}"))
    else:
        h_info = FAMILY_HOUSES.get(cur_house, FAMILY_HOUSES['moscow'])
        hourly_total = h_info['income']
        furn_names = []
        for f_k in cur_furniture:
            if f_k in FAMILY_FURNITURE:
                furn_names.append(FAMILY_FURNITURE[f_k]['name'])
                hourly_total += FAMILY_FURNITURE[f_k]['income']

        furn_str = ", ".join(furn_names) if furn_names else "Пусто (нужна мебель)"
        lines = [
            f"🏡 <b>СЕМЕЙНЫЙ ОЧАГ: {h_info['name']}</b> 😺",
            "──────────────────────",
            f"📍 Город: <b>{h_info['city']}</b>",
            f"👫 Владельцы: <b>{m.get('partner_name')}</b> & {make_link(chat_id, user_name, user_id, ping=False)}",
            f"🛋 Интерьер и мебель: <i>{furn_str}</i>",
            f"💰 Пассивный доход дома: <b>+{hourly_total} 🪙 в час</b> прямо в семейный сейф!",
            f"🏦 В семейном сейфе: <b>{m.get('vault', 0):,} 🪙</b>",
            "──────────────────────",
            "<b>Каталог мебели для обустройства:</b>"
        ]
        for f_k, f_v in FAMILY_FURNITURE.items():
            is_bought = " (Уже куплено)" if f_k in cur_furniture else ""
            lines.append(f"• <b>{f_v['name']}</b> — <code>{f_v['price']:,} 🪙</code> (+{f_v['income']} 🪙/ч){is_bought}")
            if f_k not in cur_furniture:
                markup.add(InlineKeyboardButton(f"Купить {f_v['name']} ({f_v['price']:,} 🪙)", callback_data=f"buy_furn_{f_k}:{user_id}"))

        markup.add(InlineKeyboardButton("🔄 Обновить статус дома", callback_data=f"house_refresh:{user_id}"))

    text = "\n".join(lines)
    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['house', 'дом'])
def cmd_house(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_house_view(message.chat.id, user_id, user_name)

# ---------------------------------------------------------
# КРИМИНАЛ И ПОЛИЦИЯ ЧАТА (ШЕРИФ, РОЗЫСК, КПЗ, ПОБЕГ, ЗАЛОГ)
# ---------------------------------------------------------
@bot.message_handler(commands=['sheriff', 'шериф'])
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
        f"──────────────────────\n"
        f"Офицер: {u_link}\n"
        f"Ваша задача — ловить грабителей по горячим следам!\n\n"
        f"Когда кто-то совершит ограбление, у вас будет 15 минут, чтобы поймать преступника командой:\n"
        f"👉 <code>поймать @вор</code> или <code>/catch @вор</code>\n\n"
        f"💰 Награда за поимку: <b>+250 🪙</b>, +30 EXP и +3 к Карме! 😻\n"
        f"──────────────────────",
        parse_mode='HTML'
    )

@bot.message_handler(commands=['catch', 'поймать'])
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
    wanted_info = active_wanted.get((chat_id, target_user_id))
    if not wanted_info or wanted_info.get('expire', 0) < now:
        bot.reply_to(message, f"❌ Пользователь <b>{html.escape(target_user)}</b> сейчас не находится в оперативном розыске! 😾", parse_mode='HTML')
        return

    t_econ = get_user_econ(target_user_id, target_user)
    u_link = make_link(chat_id, user_name, user_id, ping=True)
    t_link = make_link(chat_id, target_user, target_user_id, ping=True)

    # Шанс задержания 75%
    if random.random() < 0.75:
        fine = min(t_econ.get('balance', 0), 200)
        t_econ['balance'] = max(0, t_econ.get('balance', 0) - fine)
        t_econ['jail_until'] = now + 900  # 15 минут КПЗ

        reward = 250
        econ['balance'] += reward
        add_account_exp(user_id, user_name, 35, username=message.from_user.username)
        change_karma(user_id, user_name, 3)

        active_wanted.pop((chat_id, target_user_id), None)
        mark_dirty()

        log_event('ПОЛИЦИЯ: АРЕСТ', f'Шериф {u_link} задержал вора {t_link}! Вор отправлен в КПЗ на 15 мин.')

        bot.send_message(
            chat_id,
            f"🚨🚔 <b>ГРАБИТЕЛЬ ОБЕЗВРЕЖЕН И ЗАДЕРЖАН!</b> 👮‍♂️\n"
            f"──────────────────────\n"
            f"Шериф {u_link} мастерски скрутил вора {t_link}! 💥\n"
            f"⚖️ С вора списан штраф: <b>-{fine} 🪙</b>\n"
            f"🔒 Вор отправлен в КПЗ на <b>15 минут</b> (команды заработка заблокированы)!\n"
            f"💰 Награда шерифу за службу: <b>+{reward} 🪙</b> (+35 EXP, +3 Кармы)! 😻\n"
            f"──────────────────────",
            parse_mode='HTML'
        )
    else:
        bot.send_message(
            chat_id,
            f"💨 <b>ОПЕРАЦИЯ ПРОВАЛЕНА!</b> 🙀\n\n"
            f"Вор {t_link} бросил дымовую шашку под ноги шерифу {u_link} и ловко скрылся во дворах! Погоня продолжается!",
            parse_mode='HTML'
        )

@bot.message_handler(commands=['jail', 'кпз', 'тюрьма'])
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
        f"──────────────────────\n"
        f"👤 Статус: {status_str}\n\n"
        f"🚨 Преступников в розыске: <b>{wanted_count} чел.</b>\n"
        f"──────────────────────\n"
        f"💡 <b>Команды полиции и арестантов:</b> 😸\n"
        f"• <code>/sheriff</code> — поступить на службу шерифом\n"
        f"• <code>поймать @вор</code> — задержать преступника из розыска\n"
        f"• <code>/escape</code> — совершить попытку побега из КПЗ (шанс 35%)\n"
        f"• <code>/bail @вор</code> — выкупить друга под залог (300 🪙)"
    )
    bot.reply_to(message, text, parse_mode='HTML')

@bot.message_handler(commands=['escape', 'побег'])
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

@bot.message_handler(commands=['bail', 'залог'])
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
    if econ['balance'] < bail_cost:
        bot.reply_to(message, f"❌ На внесение залога нужно <b>{bail_cost} 🪙</b>! У вас: {econ['balance']} 🪙. 😿", parse_mode='HTML')
        return

    econ['balance'] -= bail_cost
    t_econ = get_user_econ(target_user_id, target_user)
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

# ---------------------------------------------------------
# ПОДПОЛЬНЫЕ БОИ ПИТОМЦЕВ (/pet_fight, /бой)
# ---------------------------------------------------------
@bot.message_handler(commands=['pet_fight', 'бой_питомцев', 'битвы_питомцев'])
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

    if econ['balance'] < bet:
        bot.reply_to(message, f"❌ У вас недостаточно коинов! Ваш баланс: {econ['balance']} 🪙. 😿", parse_mode='HTML')
        return
    if t_econ['balance'] < bet:
        bot.reply_to(message, f"❌ У соперника недостаточно коинов ({t_econ['balance']}/{bet} 🪙)! 😿", parse_mode='HTML')
        return

    econ['balance'] -= bet
    t_econ['balance'] -= bet
    mark_dirty()

    # Расчет боевой мощи
    p1_pow = pet1.get('power', 15) + (pet1.get('pet_exp', 0) // 20) + random.randint(1, 15)
    p2_pow = pet2.get('power', 15) + (pet2.get('pet_exp', 0) // 20) + random.randint(1, 15)

    u_link = make_link(chat_id, user_name, user_id, ping=True)
    t_link = make_link(chat_id, target_user, target_user_id, ping=True)

    rounds_log = [
        f"🥊 <b>ПОДПОЛЬНЫЙ БОЙ ПИТОМЦЕВ!</b> 🐾 😺",
        "──────────────────────",
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
    w_econ = get_user_econ(winner_id, winner_name)
    w_econ['balance'] += total_pot
    win_pet['pet_exp'] = win_pet.get('pet_exp', 0) + 40
    win_pet['fights_won'] = win_pet.get('fights_won', 0) + 1
    loser_pet['pet_exp'] = loser_pet.get('pet_exp', 0) + 15
    mark_dirty()

    w_link = make_link(chat_id, winner_name, winner_id, ping=True)
    rounds_log.append("──────────────────────")
    rounds_log.append(f"🏆 <b>ПОБЕДИТЕЛЬ:</b> {win_pet['name']} (Тренер: {w_link})!")
    rounds_log.append(f"💸 Выигрыш: <b>+{total_pot} 🪙</b> | Опыт победителя: <b>+40 EXP</b>! 😻")

    bot.send_message(chat_id, "\n".join(rounds_log), parse_mode='HTML')

# ---------------------------------------------------------
# БИРЖА КОНТЕНТА И МЕМОДЕЛЬНЯ (/meme)
# ---------------------------------------------------------
# ---------------------------------------------------------
# МЕМ-КОНКУРС 2.0
# ---------------------------------------------------------
def finalize_meme_contests(current_date=None):
    current_date = current_date or daily_task_date()
    memes = db.setdefault('daily_memes', [])
    winners = db.setdefault('meme_winners', [])
    changed = False
    # Выбираем одного победителя на чат и дату по score = likes - dislikes.
    for date in sorted({m.get('date') for m in memes if m.get('date') and m.get('date') < current_date}):
        chats = sorted({m.get('chat_id') for m in memes if m.get('date') == date})
        for chat_id in chats:
            group = [m for m in memes if m.get('date') == date and m.get('chat_id') == chat_id and not m.get('winner_paid')]
            if not group:
                continue
            winner = max(group, key=lambda m: len(m.get('likes', [])) - len(m.get('dislikes', [])))
            score = len(winner.get('likes', [])) - len(winner.get('dislikes', []))
            winner['winner_paid'] = True
            changed = True
            if score > 0 and winner.get('author_id'):
                econ = get_user_econ(user_id=winner['author_id'])
                econ['balance'] = econ.get('balance', 0) + 1500
                winners.append({'date': date, 'chat_id': chat_id, 'author_id': winner['author_id'], 'score': score, 'reward': 1500})
                try:
                    bot.send_message(chat_id, f"🏆 <b>МЕМ ДНЯ!</b> Автор {make_link(chat_id, winner.get('author_name', 'Пользователь'), winner['author_id'], ping=True)} получает <b>+1 500 🪙</b>! 😻", parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
    if len(memes) > 500:
        del memes[:-500]
    if len(winners) > 200:
        del winners[:-200]
    if changed: mark_dirty()

def record_meme_vote(meme_id, user_id, is_like):
    meme = active_memes.get(meme_id)
    if not meme: return False, 'Мем устарел!'
    if user_id == meme.get('author_id'): return False, 'Автор не может голосовать за свой мем!'
    if is_like:
        if user_id in meme['likes']: meme['likes'].remove(user_id)
        else:
            meme['likes'].add(user_id); meme['dislikes'].discard(user_id)
    else:
        if user_id in meme['dislikes']: meme['dislikes'].remove(user_id)
        else:
            meme['dislikes'].add(user_id); meme['likes'].discard(user_id)
    for entry in db.setdefault('daily_memes', []):
        if entry.get('meme_id') == meme_id:
            entry['likes'] = list(meme['likes']); entry['dislikes'] = list(meme['dislikes']); break
    mark_dirty()
    return True, 'Ваш голос учтён! 😸'

@bot.message_handler(commands=['memes', 'мемы'])
def cmd_memes(message):
    if not can_process_user_message(message): return
    finalize_meme_contests()
    chat_id=message.chat.id; today=daily_task_date()
    entries=[m for m in db.get('daily_memes',[]) if m.get('chat_id')==chat_id and m.get('date')==today]
    if not entries:
        bot.reply_to(message,'📸 <b>Мемов сегодня ещё нет.</b>\nОпубликуйте первый через <code>/meme</code>! 😸',parse_mode='HTML'); return
    entries.sort(key=lambda m: len(m.get('likes',[]))-len(m.get('dislikes',[])), reverse=True)
    lines=['📸 <b>МЕМЫ ДНЯ</b>','──────────────────────']
    for i,m in enumerate(entries[:10],1):
        score=len(m.get('likes',[]))-len(m.get('dislikes',[]))
        lines.append(f"{i}. {make_link(chat_id,m.get('author_name','Пользователь'),m.get('author_id'),ping=False)} — 🔥 {len(m.get('likes',[]))} / 💩 {len(m.get('dislikes',[]))} — <b>{score:+d}</b>")
    lines.append('──────────────────────'); lines.append('🏆 Победитель предыдущего дня получает 1 500 🪙 автоматически.')
    bot.reply_to(message,'\n'.join(lines),parse_mode='HTML')

@bot.message_handler(commands=['meme', 'мем'])
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
    active_memes[meme_id] = {**meme_entry, 'likes': set(), 'dislikes': set()}
    db.setdefault('daily_memes', []).append(meme_entry)
    mark_dirty()

    add_bp_exp(user_id, user_name, 10, username=message.from_user.username)
    bot.reply_to(message, caption_text, reply_markup=markup, parse_mode='HTML')

# ---------------------------------------------------------
# ГЕНЕРАТОР ИСТОРИЙ И ФАНФИКОВ (/story, /fanfic)
# ---------------------------------------------------------
STORY_TEMPLATES = [
    "📖 <b>ХРОНИКИ ЧАТА: ДЕЛО О ШАУРМЕ</b> 🌯\n──────────────────────\nОднажды <b>{u1}</b> и <b>{u2}</b> решили открыть подпольный ларёк с шаурмой прямо в подвале Кровавой Бани. {u1} отвечал за секретный соус из кошачьих слёзок, а {u2} лично заманивал голодных участников чата. Бизнес шёл в гору, пока за шаурмой не пришёл местный шериф с ручным драконом! Теперь они оба флексят в центре площади и делают вид, что просто гуляли... 😹",
    "📖 <b>ХРОНИКИ ЧАТА: ИСЕКАЙ В МИР ТАПОК</b> 🩴\n──────────────────────\nВчера <b>{u1}</b> случайно уронил(а) золотой тапок на ногу <b>{u2}</b>, и открылся пространственный портал! Они очнулись в фэнтези-мире, где королём был Гигачад, а вместо магии все спорили о размере писюна и количестве хромосом. {u1} стал(а) верховным магом кошачьего тыгыдыка, а {u2} победил(а) финального босса, метко метнув в него жареного карася! 😻",
    "📖 <b>ХРОНИКИ ЧАТА: ОГРАБЛЕНИЕ ВЕКА</b> 🏦\n──────────────────────\n<b>{u1}</b> надел(а) маску-невидимку и позвал(а) <b>{u2}</b> грабить Ня-Банк. План был надёжен как швейцарские часы: {u1} отвлекает охрану танцем аниме-девочки, а {u2} взламывает сейф с помощью скрепки и молитвы семпаю. Всё шло идеально, пока сигнализация не заиграла гимн котиков на полную громкость! Пришлось убегать на дырявых сланцах с мешком коинов в зубах! 🏃‍♂️💨",
    "📖 <b>ХРОНИКИ ЧАТА: ТАЙНА ПОДВАЛА</b> 🩸\n──────────────────────\nПоздней ночью <b>{u1}</b> и <b>{u2}</b> исследовали больницу милосердия в поисках редкого лута. Вдруг из темноты раздался зловещий шорох... {u1} схватил(а) бамбуковую удочку, а {u2} прикрылся(лась) питомцем-капибарой. Оказалось, это Джейсон Вурхиз просто варил ночной пельменный суп и забыл посолить! В итоге все трое мирно пили чай с ромашкой до самого утра. 🍵✨",
    "📖 <b>ХРОНИКИ ЧАТА: КИБЕРПАНК 2077</b> 🤖\n──────────────────────\nВ неоновом мегаполисе <b>{u1}</b> прокачал(а) нейро-имплант для скоростного фапа, а <b>{u2}</b> установил(а) кибер-руку с лазерным бластером. Корпорация котиков объявила на них охоту за взлом биржи Ня-Биткоина. Уходя от дронов на боевой девятке ВАЗ-2107, они ворвались в стратосферу и навсегда вошли в легенды Ня-Стрит! 🚀🔥"
]

@bot.message_handler(commands=['story', 'fanfic', 'история_дня'])
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

# ---------------------------------------------------------
# СЕЗОННЫЙ ХЕЛЛОУИНСКИЙ PASS (/pass, /bp, /хеллоуин)
# ---------------------------------------------------------
def render_halloween_bp_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    bp_exp = econ.get('bp_exp', 0)
    is_prem = econ.get('bp_premium', False)

    lvl, in_exp, req_exp, bar = get_user_bp_level(bp_exp)

    prem_status = "👑 Премиум Ветка АКТИВНА" if is_prem else "🔒 Бесплатная Ветка (Премиум за 2 ⭐️)"

    lines = [
        "🎃 <b>ХЕЛЛОУИНСКИЙ СЕЗОН: BATTLE PASS</b> 🦇 😺",
        "──────────────────────",
        f"👤 Участник: {make_link(chat_id, user_name, user_id, ping=False)}",
        f"🏆 Уровень пропуска: <b>{lvl}/30 LVL</b> [{bar}] ({in_exp}/{req_exp} EXP)",
        f"⭐️ Статус: <b>{prem_status}</b>\n",
        "<i>Опыт даётся за смс в чате, работу, рыбалку, охоту, мусорку и игры!</i>\n",
        "<b>Главные награды Хеллоуина:</b>",
        "• <b>Ур. 15 (Free):</b> 🎃 Эксклюзивный значок Тыквы",
        "• <b>Ур. 30 (Free):</b> 👑 Титул «🎃 Повелитель Тыкв» (+15% к удаче)",
        "• <b>Ур. 20 (Premium):</b> 🐱 Питомец: 🎃 Тыквоголовый Кот (+120% к удаче!)",
        "• <b>Ур. 30 (Premium):</b> 🎨 Тема профиля: «🎃 Тёмный Хеллоуин: Тыквенная Ночь»! 🦇",
        "──────────────────────"
    ]

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎁 Забрать доступные награды", callback_data=f"claim_bp_rewards:{user_id}"))

    if not is_prem:
        markup.add(InlineKeyboardButton("⭐️ Купить Премиум Pass (2 ⭐️ Stars)", callback_data=f"buy_bp_prem_stars:{user_id}"))

    text = "\n".join(lines)
    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['pass', 'bp', 'хеллоуин', 'battle_pass'])
def cmd_halloween_pass(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_halloween_bp_view(message.chat.id, user_id, user_name)

# ---------------------------------------------------------
# АПТЕКА И МЕМНЫЕ БОЛЕЗНИ (/pharmacy, /аптека)
# ---------------------------------------------------------
def render_pharmacy_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    cur_disease = econ.get('disease')
    d_name = MEME_DISEASES[cur_disease]['name'] if cur_disease in MEME_DISEASES else "Здоров(а) как бык! 🦾"

    now = time.time()
    imm_status = "✅ Действует" if econ.get('disease_immunity_until', 0) > now else "❌ Нет"

    lines = [
        "💊 <b>ГОРОДСКАЯ АПТЕКА «НЯ-ФАРМ»</b> 🏥 😺",
        "──────────────────────",
        f"👤 Пациент: {make_link(chat_id, user_name, user_id, ping=False)}",
        f"🩺 Диагноз: <b>{d_name}</b>",
        f"🛡 Иммунитет к вирусам: <b>{imm_status}</b>\n",
        "<i>Лечите мемные хвори чата или сделайте прививку Айболита!</i> 😸\n",
        "<b>Витрина медикаментов:</b>"
    ]

    markup = InlineKeyboardMarkup(row_width=1)
    for p_k, p_v in PHARMACY_ITEMS.items():
        lines.append(f"• <b>{p_v['name']}</b> — <code>{p_v['price']} 🪙</code> ({p_v['desc']})")
        markup.add(InlineKeyboardButton(f"Купить {p_v['name']} ({p_v['price']} 🪙)", callback_data=f"buy_med_{p_k}:{user_id}"))

    lines.append("──────────────────────")
    text = "\n".join(lines)

    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['pharmacy', 'аптека', 'больница'])
def cmd_pharmacy(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_pharmacy_view(message.chat.id, user_id, user_name)

# ---------------------------------------------------------
# ПОДАРОК УСЛУГИ TELEGRAM STARS ДРУГУ (/gift_stars)
# ---------------------------------------------------------
@bot.message_handler(commands=['gift_stars', 'подарить_звезды', 'подарок_звезды'])
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
        bot.reply_to(message, "🎁 <b>КАК ПОДАРИТЬ УСЛУГУ ЗА ЗВЁЗДЫ ДРУГУ:</b>\n──────────────────────\nУкажите друга: <code>/gift_stars @username</code> или ответом на его сообщение! 😺", parse_mode='HTML')
        return

    if target_user_id == user_id:
        bot.reply_to(message, "❌ Для покупки себе используйте <code>/stars</code>! 😸", parse_mode='HTML')
        return

    t_link = make_link(chat_id, target_user, target_user_id, ping=False)
    markup = InlineKeyboardMarkup(row_width=1)
    # Новый формат callback: gift2|тип|товар|получатель|плательщик.
    # Никакого split по '_' — названия товаров могут содержать подчёркивания.
    markup.add(
        InlineKeyboardButton("💰 Подарить 100к коинов (3 ⭐️)", callback_data=f"gift2|coins|coins_3_stars|{target_user_id}|{user_id}"),
        InlineKeyboardButton("💳 Подарить 500к коинов (10 ⭐️)", callback_data=f"gift2|coins|coins_10_stars|{target_user_id}|{user_id}"),
        InlineKeyboardButton("👑 Подарить VIP Pass на месяц (3 ⭐️)", callback_data=f"gift2|pass|pass_30_days|{target_user_id}|{user_id}"),
        InlineKeyboardButton("🎃 Подарить Хеллоуин Pass (2 ⭐️)", callback_data=f"gift2|cosm|bp_premium|{target_user_id}|{user_id}"),
        InlineKeyboardButton("🌟 Подарить Кастомный Титул (2 ⭐️)", callback_data=f"gift2|cosm|custom_title|{target_user_id}|{user_id}"),
        InlineKeyboardButton("🐱 Подарить Королевского Грифона (3 ⭐️)", callback_data=f"gift2|cosm|pet_griffin|{target_user_id}|{user_id}")
    )

    bot.reply_to(
        message,
        f"🎁 <b>ВЫБЕРИТЕ ПОДАРОК ЗА ЗВЁЗДЫ ДЛЯ {t_link}</b> ⭐️ 😻\n"
        f"──────────────────────\n"
        f"Оплата спишется с вашего баланса Telegram Stars, а товар мгновенно поступит на аккаунт друга! 😸",
        reply_markup=markup,
        parse_mode='HTML'
    )

# ---------------------------------------------------------
# СУПЕР-АДМИН: ВЫДАЧА ЛЮБЫХ ПРЕДМЕТОВ, ВКЛЮЧАЯ STARS-ДОНАТЫ
# Только ADMIN_ID / ADMIN_USERNAME. Целевая выдача не зависит от прав чата.
# Примеры:
# /give @user coins 100000
# /give @user vip 30
# /give @user vip_forever
# /give @user pet_griffin
# /give @user theme_gold
# /give @user badge_crown
# /give @user bp_premium
# /give @user all
# ---------------------------------------------------------
def _is_owner_admin(message):
    return bool(message and message.from_user and (
        message.from_user.id == ADMIN_ID
    ))

def _grant_all_donations(econ):
    econ['vip_forever'] = True
    econ['bp_premium'] = True
    econ['has_custom_title_cert'] = True
    econ.setdefault('paid_stars_items', [])
    for item_id, item in STARS_COSMETICS.items():
        item_type = item.get('type')
        if item_type == 'theme' and item.get('theme_id'):
            purchased = econ.setdefault('purchased_themes', ['default'])
            if item['theme_id'] not in purchased:
                purchased.append(item['theme_id'])
        elif item_type == 'badge' and item.get('emoji'):
            inv = econ.setdefault('inventory', [])
            if item['emoji'] not in inv:
                inv.append(item['emoji'])
        elif item_type == 'pet':
            if item_id not in econ['paid_stars_items']:
                econ['paid_stars_items'].append(item_id)
            pet_id = item.get('pet_id')
            if pet_id in PETS_DATA:
                pinfo = PETS_DATA[pet_id]
                econ['pet'] = {'id': pet_id, 'name': pinfo['name'], 'luck_bonus': pinfo['luck_bonus'], 'hunger': 100, 'cleanliness': 100, 'pet_exp': 0, 'last_update': time.time()}
        elif item_type == 'bp_premium':
            if 'bp_premium' not in econ['paid_stars_items']:
                econ['paid_stars_items'].append('bp_premium')
        elif item_type == 'title_cert':
            if 'custom_title' not in econ['paid_stars_items']:
                econ['paid_stars_items'].append('custom_title')
    if 'pet_griffin' in STARS_COSMETICS and 'pet_griffin' not in econ['paid_stars_items']:
        econ['paid_stars_items'].append('pet_griffin')

def _admin_grant(message):
    if not _is_owner_admin(message):
        return False
    raw = (message.text or '').strip()
    parts = raw.split()
    if len(parts) < 3:
        bot.reply_to(message, "❌ Формат: <code>/give @user coins 100000</code> или <code>/give @user all</code>.", parse_mode='HTML')
        return True
    target_raw = parts[1]
    target_id = None
    target_name = None
    if message.reply_to_message and (target_raw in ('reply', '.', '-', '@reply') or target_raw.lower() == 'this'):
        target = message.reply_to_message.from_user
        target_id = target.id
        target_name = target.username or target.first_name or f'ID:{target_id}'
    else:
        target_id, target_name = resolve_user_from_string(message.chat.id, target_raw)
    if not target_id:
        bot.reply_to(message, "❌ Не удалось найти пользователя. Используй @username, ID или ответ на его сообщение.")
        return True

    econ = get_user_econ(user_id=target_id, user_tag=target_name)
    item = parts[2].lower()
    amount = parts[3] if len(parts) > 3 else None
    changed = []

    if item in ('coins', 'coin', 'коины', 'коины'):
        try: value = int(amount or '0')
        except ValueError: value = 0
        if value <= 0:
            bot.reply_to(message, "❌ Укажи положительное количество коинов.")
            return True
        econ['balance'] += value; changed.append(f'+{value:,} 🪙')
    elif item in ('vip', 'vip_days'):
        try: days = int(amount or '30')
        except ValueError: days = 0
        if days <= 0:
            bot.reply_to(message, "❌ Количество дней должно быть больше 0.")
            return True
        econ['vip_until'] = max(time.time(), econ.get('vip_until', 0)) + days * 86400
        changed.append(f'VIP +{days} дн.')
    elif item in ('vip_forever', 'vip_forever_25', 'вечный_vip'):
        econ['vip_forever'] = True; changed.append('VIP навсегда')
    elif item in ('all', 'everything', 'донаты', 'donates'):
        _grant_all_donations(econ); changed.append('все Stars-донаты')
    elif item in STARS_COSMETICS:
        c = STARS_COSMETICS[item]
        t = c.get('type')
        if t == 'bp_premium': econ['bp_premium'] = True
        elif t == 'title_cert': econ['has_custom_title_cert'] = True
        elif t == 'theme':
            th = c.get('theme_id'); purchased = econ.setdefault('purchased_themes', ['default'])
            if th and th not in purchased: purchased.append(th)
            if th: econ['profile_theme'] = th
        elif t == 'badge':
            em = c.get('emoji'); inv = econ.setdefault('inventory', [])
            if em and em not in inv: inv.append(em)
            econ['badge'] = em
        elif t == 'pet':
            pid = c.get('pet_id'); econ.setdefault('paid_stars_items', [])
            if item not in econ['paid_stars_items']: econ['paid_stars_items'].append(item)
            if pid in PETS_DATA:
                pi=PETS_DATA[pid]; econ['pet']={'id':pid,'name':pi['name'],'luck_bonus':pi['luck_bonus'],'hunger':100,'cleanliness':100,'pet_exp':0,'last_update':time.time()}
        changed.append(c.get('name', item))
    elif item in ('pass_forever', 'vip_pass_forever'):
        econ['vip_forever'] = True; changed.append('VIP навсегда')
    elif item in ('bp_premium', 'premium_pass'):
        econ['bp_premium'] = True; econ.setdefault('paid_stars_items', [])
        if 'bp_premium' not in econ['paid_stars_items']: econ['paid_stars_items'].append('bp_premium')
        changed.append('Премиум Pass')
    elif item.startswith('theme_'):
        key=item.replace('theme_','',1)
        if key in THEMES:
            purchased=econ.setdefault('purchased_themes',['default'])
            if key not in purchased: purchased.append(key)
            econ['profile_theme']=key; changed.append(THEMES[key]['name'])
        else:
            bot.reply_to(message, "❌ Такой темы нет."); return True
    elif item.startswith('badge_'):
        key=item
        if key in STARS_COSMETICS and STARS_COSMETICS[key].get('type')=='badge':
            em=STARS_COSMETICS[key]['emoji']; inv=econ.setdefault('inventory',[])
            if em not in inv: inv.append(em)
            econ['badge']=em; changed.append(em)
        elif key in VIP_BADGES:
            em=VIP_BADGES[key]['emoji']; inv=econ.setdefault('inventory',[])
            if em not in inv: inv.append(em)
            econ['badge']=em; changed.append(em)
        else:
            bot.reply_to(message, "❌ Такой VIP-значок не найден."); return True
    elif item in ('pet_griffin', 'vip_griffin'):
        econ.setdefault('paid_stars_items', [])
        if 'pet_griffin' not in econ['paid_stars_items']: econ['paid_stars_items'].append('pet_griffin')
        if 'vip_griffin' in PETS_DATA:
            pi=PETS_DATA['vip_griffin']; econ['pet']={'id':'vip_griffin','name':pi['name'],'luck_bonus':pi['luck_bonus'],'hunger':100,'cleanliness':100,'pet_exp':0,'last_update':time.time()}
        changed.append('👑 Королевский Грифон')
    elif item == 'stars':
        try: value=int(amount or '0')
        except ValueError: value=0
        if value <= 0: bot.reply_to(message,"❌ Укажи положительное число Stars."); return True
        econ['stars_donated']=econ.get('stars_donated',0)+value; changed.append(f'+{value} ⭐️ в статистику донатов')
    else:
        bot.reply_to(message, "❌ Неизвестный предмет. Используй <code>all</code>, <code>coins</code>, <code>vip</code>, <code>vip_forever</code>, <code>pet_griffin</code> или ID товара из Stars-магазина.", parse_mode='HTML')
        return True

    mark_dirty()
    bot.reply_to(message, f"✅ <b>Выдача выполнена</b>\n👤 {html.escape(str(target_name or target_id))}\n🎁 {html.escape(', '.join(changed))}", parse_mode='HTML')
    return True

@bot.message_handler(commands=['give', 'выдать', 'grant'])
def admin_give_command(message):
    _admin_grant(message)

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if not message or not getattr(message, 'from_user', None):
        return

    chat_id = message.chat.id
    if is_chat_banned(chat_id):
        return

    text = message.text.strip() if message.text else ''
    str_chat = str(chat_id)
    user_id = message.from_user.id
    user_username = (message.from_user.username or '').lower()
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username or 'Пользователь'
    text_lower = text.lower()
    now_ts = time.time()
    quiz = current_quiz.get(chat_id)

    is_super_admin = (user_id == ADMIN_ID)

    bot_is_active = db.get('bot_active', True)
    if not bot_is_active:
        if is_super_admin and text_lower in ['/start_bot', '/resume', 'включить бота', 'запустить бота']:
            db['bot_active'] = True
            save_data()
            log_event('ВКЛЮЧЕНИЕ', f'Бот возобновил работу по команде ID:{user_id}')
            bot.reply_to(message, "🟢 <b>Бот успешно включен и возобновил работу!</b> 😻", parse_mode='HTML')
            return
        elif is_super_admin:
            pass
        else:
            return

    last_chat_activity[chat_id] = now_ts

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

    # АНТИФЛУД: настройка действует ТОЛЬКО в том чате, где её включил администратор.
    # ЛС боту и другие чаты никогда не попадают под лимит этого чата.
    # Лимит: 5 команд в час на пользователя именно в этом чате.
    is_private_chat = getattr(message.chat, 'type', '') == 'private'
    if (not is_private_chat and chat_settings.get('flood_protection', False)
            and text_lower.startswith('/')):
        flood_key = f"{chat_id}:{user_id}"
        cmd_hist = [t for t in command_rate_history.get(flood_key, []) if now_ts - t < 3600]
        if len(cmd_hist) >= 5:
            command_rate_history[flood_key] = cmd_hist
            remaining = max(1, int(3600 - (now_ts - cmd_hist[0])))
            mins = max(1, (remaining + 59) // 60)
            u_link = make_link(chat_id, user_name, user_id, ping=True)
            bot.send_message(chat_id, f"🛡 {u_link}, <b>антифлуд сработал.</b> Лимит — 5 команд в час. Попробуй снова примерно через {mins} мин. 😾", parse_mode='HTML')
            return
        cmd_hist.append(now_ts)
        command_rate_history[flood_key] = cmd_hist
        if len(cmd_hist) == 4:
            u_link = make_link(chat_id, user_name, user_id, ping=True)
            bot.send_message(chat_id, f"⚠️ {u_link}, предупреждение антифлуда: использовано <b>4/5 команд</b> за последний час.", parse_mode='HTML')
        elif len(cmd_hist) == 5:
            u_link = make_link(chat_id, user_name, user_id, ping=True)
            bot.send_message(chat_id, f"⚠️ {u_link}, <b>5/5 команд</b> использовано. Следующая команда будет заблокирована до окончания часового лимита.", parse_mode='HTML')

    # Старый короткий антиспам оставляем только для одинаковых экономических команд.

    add_message_stat(user_id, user_name, username=user_username)
    add_bp_exp(user_id, user_name, 2, username=user_username)
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

    # КАЛЬКУЛЯТОР
    m_calc_cmd = re.match(r'^(?:/calc|посчитай|вычисли|реши|сколько\s+будет)\s+([\d\s\+\-\*\/\%\(\)\.\:×÷]+)$', text, re.IGNORECASE)
    if m_calc_cmd:
        calc_res = safe_calculate_math(m_calc_cmd.group(1).strip())
        if calc_res is not None:
            bot.reply_to(message, f"🧮 <b>Результат:</b> <code>{calc_res}</code> 😸", parse_mode='HTML')
            return

    # ВИКТОРИНА
    if quiz and quiz.get('answer') and quiz.get('chat_id') == chat_id:
        if text_lower == quiz['answer']:
            reward = quiz['reward']
            quiz['answer'] = None
            add_coins(user_id, user_name, reward, username=user_username)
            add_account_exp(user_id, user_name, 20, username=user_username)
            u_link = make_link(chat_id, user_name, user_id, ping=True)
            bot.reply_to(message, f"🎉 <b>ПРАВИЛЬНЫЙ ОТВЕТ!</b> 😻\n\nПервым(ой) правильно ответил(а) {u_link} и получает <b>+{reward} Ня-коинов 🪙</b> (+20 EXP)!", parse_mode='HTML')
            return

    # КОМАНДЫ СОЗДАТЕЛЯ
    if is_super_admin:
        if text_lower in ['/admin', '/admin_help', 'админ', 'админка']:
            admin_help_text = (
                f"👑 <b>ПАНЕЛЬ УПРАВЛЕНИЯ СОЗДАТЕЛЯ (ID: {ADMIN_ID}):</b>\n"
                "──────────────────────\n"
                "• <code>/add_promo КОД СУММА</code> — создать промокод\n"
                "• <code>/stop_bot</code> — спящий режим\n"
                "• <code>/start_bot</code> — возобновить работу\n"
                "• <code>/take_coins @user 500</code> — списать коины\n"
                "• <code>/give_coins @user 1000</code> — выдать коины\n"
                "• <code>/inspect @user</code> — осмотр игрока\n"
                "• <code>/set_karma @user 100</code> — изменить карму\n"
                "• <code>/force_divorce @user</code> — принудительный развод\n"
                "• <code>/give_item @user item_name</code> — выдать предмет\n"
                "• <code>/wipe @user</code> — обнулить профиль\n"
                "──────────────────────"
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
            t_econ['balance'] = max(0, t_econ.get('balance', 0) - t_amt)
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
            t_econ['balance'] = t_econ.get('balance', 0) + t_amt
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
        m = econ['marriage']
        p_id = m.get('partner_id')
        p_tag = m.get('partner_name')
        p_econ = get_user_econ(p_id, p_tag)
        m_amt = re.search(r'(\d+)', text_lower)
        if 'положить' in text_lower and m_amt:
            amt = int(m_amt.group(1))
            if amt <= 0 or econ['balance'] < amt:
                bot.reply_to(message, f"❌ Недостаточно средств на руках! У вас: {econ['balance']} 🪙 😿")
                return
            econ['balance'] -= amt
            m['vault'] = m.get('vault', 0) + amt
            if p_econ.get('marriage'): p_econ['marriage']['vault'] = m['vault']
            mark_dirty()
            bot.reply_to(message, f"💍 Вы положили <b>{amt} 🪙</b> в семейный сейф!\nВ сейфе: <b>{m['vault']} 🪙</b> 😻", parse_mode='HTML')
            return
        elif 'снять' in text_lower and m_amt:
            amt = int(m_amt.group(1))
            cur_vault = m.get('vault', 0)
            if amt <= 0 or cur_vault < amt:
                bot.reply_to(message, f"❌ В сейфе недостаточно коинов! Накоплено: {cur_vault} 🪙 😿")
                return
            m['vault'] -= amt
            if p_econ.get('marriage'): p_econ['marriage']['vault'] = m['vault']
            econ['balance'] += amt
            mark_dirty()
            bot.reply_to(message, f"💸 Вы взяли <b>{amt} 🪙</b> из семейного сейфа!\nОстаток: <b>{m['vault']} 🪙</b> 😸", parse_mode='HTML')
            return

    # КВЕСТ СООБЩЕНИЙ
    completed_tasks = track_daily_task(user_id, user_name, 'messages', 1, chat_id, username=user_username)
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
            t_bp['alarm_system'] -= 1
            fine = min(econ['balance'], 150)
            econ['balance'] -= fine
            t_econ['balance'] += fine
            change_karma(user_id, user_name, -5)
            active_wanted[(chat_id, user_id)] = {'name': user_name, 'expire': now + 900, 'reason': 'ограбление'}
            mark_dirty()
            u_link = make_link(chat_id, user_name, user_id)
            t_link = make_link(chat_id, target_user, target_user_id, ping=True)
            bot.send_message(chat_id, f"🚨🔊 <b>СИГНАЛИЗАЦИЯ СРАБОТАЛА!</b> 🙀\n\n{u_link} попытался проникнуть в карман {t_link}, но сработала <b>Охранная сигнализация</b>!\nВор оглушен электрошокером и выплатил компенсацию <b>-{fine} 🪙</b> в пользу жертвы! (Карма -5)", parse_mode='HTML')
            return

        rob_chance = 0.40
        if econ.get('pet') and econ['pet'].get('id') == 'raccoon': rob_chance += 0.20

        if random.random() <= rob_chance:
            stolen = max(10, min(500, int(t_pocket * random.uniform(0.08, 0.18))))
            t_econ['balance'] -= stolen
            econ['balance'] += stolen
            change_karma(user_id, user_name, -5)
            mark_dirty()
            u_link = make_link(chat_id, user_name, user_id, ping=True)
            t_link = make_link(chat_id, target_user, target_user_id, ping=True)
            bot.send_message(chat_id, f"🥷 <b>УДАЧНОЕ ОГРАБЛЕНИЕ!</b> 😼\n\n{u_link} ловко украл у {t_link} <b>{stolen} Ня-коинов 🪙</b>! (Карма -5)", parse_mode='HTML')
        else:
            fine = min(econ['balance'], random.randint(30, 90))
            if econ.get('active_title') == 'shadow_ninja': fine = int(fine * 0.5)
            econ['balance'] -= fine
            t_econ['balance'] += fine
            change_karma(user_id, user_name, -3)
            mark_dirty()
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
            econ['balance'] -= amt
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
        econ['balance'] += dep
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
            econ['balance'] += amt
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
            bot.reply_to(message, f"🌴 <b>Пользователь {user_link} находится в ресте!</b> 😺\n📝 <b>Причина:</b> {html.escape(rest_info.get('reason', 'Не указана'))}\n⏱ <b>Срок:</b> {html.escape(rest_info.get('duration', 'Не указан'))}", parse_mode='HTML')
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
        if target_id == user_id:
            bot.reply_to(message, "❌ Нельзя переводить коины самому себе! 🙀")
            return
        sender_econ = get_user_econ(user_id, user_name, username=user_username)
        if sender_econ['balance'] < amount:
            bot.reply_to(message, f"❌ Недостаточно Ня-коинов! У вас: <b>{sender_econ['balance']} 🪙</b> 😿", parse_mode='HTML')
            return
        tax = max(1, int(amount * 0.03))
        receive_amount = amount - tax
        sender_econ['balance'] -= amount
        sender_econ['daily_transferred'] = sender_econ.get('daily_transferred', 0) + amount
        add_coins(user_id=target_id, user_tag=target_u, amount=receive_amount)
        mark_dirty()
        target_link = make_link(chat_id, target_u, target_id, ping=True)
        bot.reply_to(message, f"💸 <b>Перевод выполнен!</b>\n\n👤 Получатель: {target_link}\n💰 Отправлено: <b>{amount:,} 🪙</b>\n🧾 Комиссия 3%: <b>{tax:,} 🪙</b>\n📥 Получит: <b>{receive_amount:,} 🪙</b>\n💳 Остаток: <b>{sender_econ['balance']:,} 🪙</b> 😸".replace(',', ' '), parse_mode='HTML')
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
            econ['balance'] -= amount
            econ['bank_deposit'] = econ.get('bank_deposit', 0) + amount
            action_text = f"📥 На счёт внесено <b>{amount:,} 🪙</b>".replace(',', ' ')
        else:
            if econ.get('bank_deposit', 0) < amount:
                bot.reply_to(message, f"❌ На депозите только <b>{econ.get('bank_deposit', 0)} 🪙</b>.", parse_mode='HTML')
                return
            econ['bank_deposit'] -= amount
            econ['balance'] += amount
            action_text = f"📤 Со счёта снято <b>{amount:,} 🪙</b>".replace(',', ' ')
        mark_dirty()
        bot.reply_to(message, f"🏦 <b>НЯ-БАНК</b>\n{action_text}\n💳 В банке: <b>{econ.get('bank_deposit', 0):,} 🪙</b>\n💵 В кошельке: <b>{econ.get('balance', 0):,} 🪙</b>".replace(',', ' '), parse_mode='HTML')
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
        'сад': cmd_garden,
        'топ': cmd_top, 'топ дня': cmd_top_daily, 'топ недели': cmd_top_weekly,
        'рулетка': cmd_wheel, 'мины': cmd_mines, 'дурак': cmd_durak,
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

            final_reward = int(base_reward * streak_mult)
            is_vip = econ.get('vip_forever') or (econ.get('vip_until', 0) > now_ts)
            if is_vip:
                final_reward = int(final_reward * 2.0)

            econ['balance'] += final_reward
            econ['last_hourly'] = now_ts
            add_account_exp(user_id, user_name, 10, username=user_username)
            mark_dirty()
            check_achievements(user_id, user_name, 'bonuses', 1, chat_id, username=user_username)
            completed = track_daily_task(user_id, user_name, 'bonus', 1, chat_id, username=user_username)

            vip_bonus_text = "\n⭐️ <b>VIP NYA PASS: Бонус удвоен (x2.0)!</b>" if is_vip else ""
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
            econ['balance'] -= bet
            process_casino_bet(bet, chat_id)

        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)

        total = d1 + d2
        result = f'🎲 Выпало: <b>{d1} + {d2} = {total}</b>. 😺'
        if bet > 0:
            if total == 12:
                win = process_casino_win(int(bet * 3.0))
                econ['balance'] += win
                result += f'\n🎉 Джекпот 12! Вы выиграли <b>+{win} 🪙</b> (3.0x)! 🙀'
            elif total >= 8:
                win = process_casino_win(int(bet * 1.95))
                econ['balance'] += win
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

        econ['balance'] -= bet
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
            econ['balance'] += win
            result += f'\n💎👑 <b>МЕГА ДЖЕКПОТ (5x)!</b> Выигрыш: <b>+{win} 🪙</b>! 🙀'
        elif roll[0] == roll[1] == roll[2] and roll[0] in ['⭐', '🍀']:
            multiplier = 3 if roll[0] == '⭐' else 2.5
            win = process_casino_win(int(bet * multiplier))
            econ['balance'] += win
            result += f'\n🌟 <b>ОГРОМНЫЙ ВЫИГРЫШ ({multiplier}x)!</b> Награда: <b>+{win} 🪙</b>! 😻'
        elif roll[0] == roll[1] == roll[2]:
            win = process_casino_win(int(bet * 1.8))
            econ['balance'] += win
            result += f'\n🎉 <b>Три в ряд (1.8x)!</b> Выигрыш: <b>+{win} 🪙</b>! 😸'
        elif roll.count('💎') == 2 or roll.count('⭐') == 2:
            win = process_casino_win(int(bet * 1.2))
            econ['balance'] += win
            result += f'\n✨ <b>Два редких символа!</b> Выигрыш: <b>+{win} 🪙</b> (1.2x)! 😽'
        elif len(set(roll)) == 2:
            win = process_casino_win(int(bet * 0.6))
            econ['balance'] += win
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

        if target_id == user_id:
            bot.reply_to(message, "❌ Нельзя переводить коины самому себе! 🙀")
            return

        sender_econ = get_user_econ(user_id, user_name, username=user_username)
        if sender_econ['balance'] < amount:
            bot.reply_to(message, f"❌ Недостаточно Ня-коинов! У вас: <b>{sender_econ['balance']} 🪙</b> 😿", parse_mode='HTML')
            return

        tax = max(1, int(amount * 0.03))
        receive_amount = amount - tax

        sender_econ['balance'] -= amount
        sender_econ['daily_transferred'] = sender_econ.get('daily_transferred', 0) + amount

        add_coins(user_id=target_id, user_tag=target_u, amount=receive_amount)
        change_karma(user_id, user_name, 1)
        mark_dirty()
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

    # РЕСТЫ
    if text_lower.startswith('+рест'):
        if not is_admin(chat_id, user_id): return
        target_name, target_id, duration_text, reason = parse_rest_command(message)
        if target_name and duration_text:
            reward_given, count = apply_rest(chat_id, target_name, duration_text, reason, target_id)
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
            resp = '📋 <b>СПИСОК АКТИВНЫХ РЕСТОВ:</b> 😺\n──────────────────────\n'
            for r_key, info in db['rests'][str_chat].items():
                u_name = info.get('user_name', r_key)
                u_id = info.get('user_id')
                resp += f"• {make_link(chat_id, u_name, u_id, ping=False)} — {info['duration']} (Причина: {info.get('reason', 'Не указана')})\n"
            resp += '──────────────────────'

            markup = None
            if is_admin(chat_id, user_id):
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🗑 Снять рест (Выбрать)", callback_data=f"rest_remove_menu:{user_id}"))

            bot.reply_to(message, resp, reply_markup=markup, parse_mode='HTML')

# ---------------------------------------------------------
# ОБРАБОТКА CALLBACK КНОПОК
# ---------------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    try:
        if not call or not getattr(call, 'from_user', None) or not getattr(call, 'message', None):
            return
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        user_username = (call.from_user.username or '').lower()
        user_name = (f"{call.from_user.first_name or ''} {call.from_user.last_name or ''}").strip() or call.from_user.username or 'Пользователь'
        now_ts = time.time()

        if is_chat_banned(chat_id):
            bot.answer_callback_query(call.id, "❌ Работа бота в этом чате запрещена!", show_alert=True)
            return

        user_hist = [t for t in user_flood_history.get(user_id, []) if now_ts - t <= 2.0]
        user_hist.append(now_ts)
        user_flood_history[user_id] = user_hist
        if len(user_hist) >= 5:
            bot.answer_callback_query(call.id, "⚠️ Слишком быстро нажимаете кнопки!", show_alert=True)
            return

        if call.data == 'noop':
            bot.answer_callback_query(call.id)
            return

        raw_data = call.data
        owner_id = None
        action_data = raw_data

        if ':' in raw_data:
            parts = raw_data.rsplit(':', 1)
            if parts[1].isdigit():
                action_data = parts[0]
                owner_id = int(parts[1])

        if owner_id and owner_id != user_id:
            if action_data in ['set_max_days', 'set_remind_time', 'toggle_rp', 'toggle_flood', 'toggle_reactions', 'toggle_welcome']:
                if not is_admin(chat_id, user_id):
                    bot.answer_callback_query(call.id, "❌ Настройки доступны только администраторам!", show_alert=True)
                    return
            else:
                bot.answer_callback_query(call.id, "❌ Это меню открыто другим пользователем!", show_alert=True)
                return


        # МЕМЫ: ГОЛОСОВАНИЕ
        elif action_data.startswith('meme_l_') or action_data.startswith('meme_d_'):
            meme_id = action_data[7:]
            meme = active_memes.get(meme_id)
            if not meme:
                bot.answer_callback_query(call.id, "❌ Мем устарел!", show_alert=True)
                return
            is_like = action_data.startswith('meme_l_')
            ok_vote, vote_msg = record_meme_vote(meme_id, user_id, is_like)
            if not ok_vote:
                bot.answer_callback_query(call.id, vote_msg, show_alert=True)
                return
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton(f"🔥 {len(meme['likes'])}", callback_data=f"meme_l_{meme_id}"),
                InlineKeyboardButton(f"💩 {len(meme['dislikes'])}", callback_data=f"meme_d_{meme_id}")
            )
            try: bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup)
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            bot.answer_callback_query(call.id, "Ваш голос учтён! 😸")
            return

        # СЕМЕЙНЫЙ ДОМ: КНОПКИ
        elif action_data.startswith('buy_house_'):
            h_k = action_data.replace('buy_house_', '')
            if h_k in FAMILY_HOUSES:
                h_info = FAMILY_HOUSES[h_k]
                econ = get_user_econ(user_id, user_name, username=user_username)
                m = econ.get('marriage')
                if not m:
                    bot.answer_callback_query(call.id, "❌ Только для пар в браке!", show_alert=True)
                    return
                if econ['balance'] < h_info['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {h_info['price']:,} 🪙! 😿", show_alert=True)
                    return
                econ['balance'] -= h_info['price']
                m['house'] = h_k
                m['furniture'] = []
                m['last_house_calc'] = time.time()
                p_econ = get_user_econ(m.get('partner_id'))
                if p_econ.get('marriage'):
                    p_econ['marriage']['house'] = h_k
                    p_econ['marriage']['furniture'] = []
                    p_econ['marriage']['last_house_calc'] = time.time()
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Вы приобрели {h_info['name']}! 😻", show_alert=True)
                render_house_view(chat_id, user_id, user_name, message_id=call.message.message_id)
            return

        elif action_data.startswith('buy_furn_'):
            f_k = action_data.replace('buy_furn_', '')
            if f_k in FAMILY_FURNITURE:
                f_info = FAMILY_FURNITURE[f_k]
                econ = get_user_econ(user_id, user_name, username=user_username)
                m = econ.get('marriage')
                if not m: return
                furn_list = m.setdefault('furniture', [])
                if f_k in furn_list:
                    bot.answer_callback_query(call.id, "❌ Этот предмет мебели уже куплен!", show_alert=True)
                    return
                if econ['balance'] < f_info['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {f_info['price']:,} 🪙! 😿", show_alert=True)
                    return
                econ['balance'] -= f_info['price']
                furn_list.append(f_k)
                p_econ = get_user_econ(m.get('partner_id'))
                if p_econ.get('marriage'):
                    p_econ['marriage'].setdefault('furniture', []).append(f_k)
                mark_dirty()
                bot.answer_callback_query(call.id, f"🛋 Куплена мебель: {f_info['name']}! 😻", show_alert=True)
                render_house_view(chat_id, user_id, user_name, message_id=call.message.message_id)
            return

        elif action_data == 'house_refresh':
            render_house_view(chat_id, user_id, user_name, message_id=call.message.message_id)
            bot.answer_callback_query(call.id, "Статус дома обновлен! 😸")
            return

        # АПТЕКА: КНОПКИ
        elif action_data.startswith('buy_med_'):
            med_k = action_data.replace('buy_med_', '')
            if med_k in PHARMACY_ITEMS:
                med = PHARMACY_ITEMS[med_k]
                econ = get_user_econ(user_id, user_name, username=user_username)
                if econ['balance'] < med['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {med['price']} 🪙! 😿", show_alert=True)
                    return
                econ['balance'] -= med['price']
                cur_d = econ.get('disease')
                if med['cure'] == 'all':
                    econ['disease'] = None
                    econ['disease_immunity_until'] = time.time() + 86400
                    bot.answer_callback_query(call.id, "🧪 Панацея Айболита исцелила от всего и дала иммунитет на 24 часа! 😻", show_alert=True)
                elif cur_d == med['cure']:
                    econ['disease'] = None
                    bot.answer_callback_query(call.id, f"✅ Вы выпили лекарство и полностью исцелились от {MEME_DISEASES[cur_d]['name']}! 😸", show_alert=True)
                else:
                    bot.answer_callback_query(call.id, f"💊 Препарат куплен, но у вас другой диагноз! 😸")
                mark_dirty()
                render_pharmacy_view(chat_id, user_id, user_name, message_id=call.message.message_id)
            return

        # ХЕЛЛОУИН BATTLE PASS: КНОПКИ
        elif action_data == 'claim_bp_rewards':
            econ = get_user_econ(user_id, user_name, username=user_username)
            bp_exp = econ.get('bp_exp', 0)
            lvl, _, _, _ = get_user_bp_level(bp_exp)
            is_prem = econ.get('bp_premium', False)
            claimed_free = econ.setdefault('bp_claimed_free', [])
            claimed_prem = econ.setdefault('bp_claimed_prem', [])

            free_gains = 0
            for l in range(1, lvl + 1):
                if l not in claimed_free:
                    claimed_free.append(l)
                    free_gains += 100 * l
                    milestone_free = {5: '🎃 Маленький фонарь', 10: '🕸 Паутинка', 25: '🦇 Летучая мышь'}
                    if l in milestone_free:
                        econ.setdefault('inventory', [])
                        if milestone_free[l] not in econ['inventory']:
                            econ['inventory'].append(milestone_free[l])
                    if l == 15 and '🎃' not in econ.get('inventory', []):
                        econ.setdefault('inventory', []).append('🎃')
                    if l == 30 and 'pumpkin_lord' not in econ.get('titles', []):
                        econ.setdefault('titles', []).append('pumpkin_lord')
                        econ['active_title'] = 'pumpkin_lord'

            prem_gains = 0
            if is_prem:
                for l in range(1, lvl + 1):
                    if l not in claimed_prem:
                        claimed_prem.append(l)
                        prem_gains += 350 * l
                        if l == 10:
                            econ.setdefault('inventory', [])
                            if '🎃 Премиум-тыква' not in econ['inventory']:
                                econ['inventory'].append('🎃 Премиум-тыква')
                        if l == 20:
                            p_info = PETS_DATA['pumpkin_cat']
                            econ['pet'] = {'id': 'pumpkin_cat', 'name': p_info['name'], 'luck_bonus': p_info['luck_bonus'], 'hunger': 100, 'cleanliness': 100, 'pet_exp': 0, 'last_update': time.time()}
                        if l == 30:
                            p_th = econ.setdefault('purchased_themes', ['default'])
                            if 'halloween' not in p_th: p_th.append('halloween')
                            econ['profile_theme'] = 'halloween'

            tot_coins = free_gains + prem_gains
            econ['balance'] += tot_coins
            mark_dirty()
            if tot_coins > 0:
                bot.answer_callback_query(call.id, f"🎉 Награды получены: +{tot_coins:,} 🪙 и трофеи сезона! 😻", show_alert=True)
            else:
                bot.answer_callback_query(call.id, "Все доступные награды уже получены! Повышайте уровень BP. 😸", show_alert=True)
            render_halloween_bp_view(chat_id, user_id, user_name, message_id=call.message.message_id)
            return

        elif action_data == 'buy_bp_prem_stars':
            try:
                bot.send_invoice(
                    chat_id=chat_id,
                    title="🎃 Премиум Хеллоуинский Pass",
                    description="Доступ к премиум-ветке наград: Тыквокот, Тёмная тема, горы коинов!",
                    invoice_payload=f"bpprem_self:{user_id}:{int(time.time())}",
                    provider_token="",
                    currency="XTR",
                    prices=[LabeledPrice(label="Хеллоуин Pass", amount=2)]
                )
                bot.answer_callback_query(call.id, "⭐️ Счёт на 2 ⭐️ выставлен!")
            except Exception as e:
                bot.answer_callback_query(call.id, f"❌ Ошибка выставления счёта: {e}", show_alert=True)
            return

        # НАСТРОЙКИ ПРОФИЛЯ
        elif action_data == 'open_profile_settings':
            render_profile_settings_view(chat_id, user_id, user_name, call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        elif action_data == 'ps_back_profile':
            send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)
            bot.answer_callback_query(call.id)
            return

        elif action_data == 'ps_fonts':
            econ = get_user_econ(user_id, user_name, username=user_username)
            cur_f = econ.get('profile_font', 'default')
            markup = InlineKeyboardMarkup(row_width=1)
            for f_k, f_v in FONTS.items():
                active_mark = " (Выбран)" if f_k == cur_f else ""
                markup.add(InlineKeyboardButton(f"{f_v['name']}{active_mark}", callback_data=f"set_font_{f_k}:{user_id}"))
            markup.add(InlineKeyboardButton("🔙 Назад в настройки", callback_data=f"open_profile_settings:{user_id}"))
            try:
                bot.edit_message_text(
                    "🔤 <b>ВЫБОР ШРИФТА ДЛЯ ПРОФИЛЯ</b> 😺\n──────────────────────\nВыберите желаемый стиль текста для вашей карточки игрока: 😻",
                    chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML'
                )
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            bot.answer_callback_query(call.id)
            return

        elif action_data.startswith('set_font_'):
            f_k = action_data.replace('set_font_', '')
            if f_k in FONTS:
                econ = get_user_econ(user_id, user_name, username=user_username)
                econ['profile_font'] = f_k
                mark_dirty()
                bot.answer_callback_query(call.id, f"✅ Установлен шрифт: {FONTS[f_k]['name']}! 😻", show_alert=True)
                render_profile_settings_view(chat_id, user_id, user_name, call.message.message_id)
            return

        elif action_data == 'ps_themes':
            econ = get_user_econ(user_id, user_name, username=user_username)
            cur_t = econ.get('profile_theme', 'default')
            purchased = econ.get('purchased_themes', ['default'])
            markup = InlineKeyboardMarkup(row_width=1)
            for t_k in purchased:
                if t_k in THEMES:
                    active_mark = " (Выбрана)" if t_k == cur_t else ""
                    markup.add(InlineKeyboardButton(f"{THEMES[t_k]['name']}{active_mark}", callback_data=f"set_theme_{t_k}:{user_id}"))
            markup.add(InlineKeyboardButton("🏪 Купить новые темы в Магазине", callback_data=f"shop_cat_themes:{user_id}"))
            markup.add(InlineKeyboardButton("🔙 Назад в настройки", callback_data=f"open_profile_settings:{user_id}"))
            try:
                bot.edit_message_text(
                    "🎨 <b>ВЫБОР ТЕМЫ ОФОРМЛЕНИЯ ПРОФИЛЯ</b> 😺\n──────────────────────\nВыберите тему из купленных или приобретите новые в магазине: 😻",
                    chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML'
                )
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            bot.answer_callback_query(call.id)
            return

        elif action_data in ['ps_badges', 'ps_titles', 'ps_pfp']:
            bot.answer_callback_query(call.id, "💡 Управление значками, титулами и аватарками доступно также в основном магазине /shop и командами /set_pfp и /custom_title! 😸", show_alert=True)
            return

        # МАГАЗИН: ГЛАВНОЕ МЕНЮ
                # КАТЕГОРИИ МАГАЗИНА STARS
        elif action_data == 'shop_cat_stars_main' or action_data == 'stars_cat_main':
            render_stars_shop(chat_id, user_id, user_name, category='main', message_id=call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        elif action_data == 'stars_cat_coins':
            render_stars_shop(chat_id, user_id, user_name, category='coins', message_id=call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        elif action_data == 'stars_cat_pass':
            render_stars_shop(chat_id, user_id, user_name, category='pass', message_id=call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        elif action_data == 'stars_cat_cosm':
            render_stars_shop(chat_id, user_id, user_name, category='cosm', message_id=call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        # ИНИЦИАЦИЯ ПОДАРКА TELEGRAM STARS ДРУГУ
        # Новый callback: gift2|kind|item_key|target_id|buyer_id
        elif action_data.startswith('gift2|'):
            try:
                parts_cb = action_data.split('|')
                if len(parts_cb) != 5 or parts_cb[0] != 'gift2':
                    raise ValueError('invalid gift callback')
                gift_kind = parts_cb[1]
                item_key = parts_cb[2]
                target_id = int(parts_cb[3])
                buyer_id = int(parts_cb[4])
            except (TypeError, ValueError):
                bot.answer_callback_query(call.id, "❌ Некорректный подарок!", show_alert=True)
                return

            if buyer_id != user_id or (owner_id and owner_id != user_id):
                bot.answer_callback_query(call.id, "❌ Этот подарок может оформить только его отправитель!", show_alert=True)
                return
            if target_id == buyer_id:
                bot.answer_callback_query(call.id, "❌ Нельзя подарить товар самому себе. Используйте /stars!", show_alert=True)
                return

            catalogs = {'coins': STARS_COIN_PACKS, 'pass': STARS_VIP_PASS, 'cosm': STARS_COSMETICS}
            item = catalogs.get(gift_kind, {}).get(item_key)
            # Спец-подарки, которые могут существовать вне STARS_COSMETICS.
            if gift_kind == 'cosm' and item is None and item_key == 'bp_premium':
                item = {'name': '🎃 Премиум Хеллоуин Pass', 'stars': 2}
            if gift_kind == 'cosm' and item is None and item_key == 'custom_title':
                item = {'name': '🌟 Сертификат Кастомного Титула', 'stars': 2}
            if gift_kind == 'cosm' and item is None and item_key == 'pet_griffin':
                item = {'name': '🐱 Королевский Грифон', 'stars': 3}
            if not item:
                bot.answer_callback_query(call.id, "❌ Товар подарка не найден!", show_alert=True)
                return

            target_econ = get_user_econ(user_id=target_id)
            owned_error = None
            if gift_kind == 'pass':
                owned_error = stars_purchase_error(target_econ, 'vippass', item_key)
            elif gift_kind == 'cosm':
                if item_key == 'bp_premium' and target_econ.get('bp_premium'):
                    owned_error = 'У получателя уже есть Премиум Pass.'
                elif item_key == 'custom_title' and target_econ.get('has_custom_title_cert'):
                    owned_error = 'У получателя уже есть сертификат титула.'
                elif item_key == 'pet_griffin' and 'pet_griffin' in target_econ.get('paid_stars_items', []):
                    owned_error = 'У получателя уже есть Королевский Грифон.'
                elif item_key in STARS_COSMETICS:
                    owned_error = stars_purchase_error(target_econ, 'cosm', item_key)
            if owned_error:
                bot.answer_callback_query(call.id, "❌ " + owned_error.replace('❌ ', ''), show_alert=True)
                return

            try:
                payload = f"gift2|{gift_kind}|{item_key}|{target_id}|{buyer_id}"
                bot.send_invoice(
                    chat_id=chat_id,
                    title=f"🎁 Подарок: {item['name']}",
                    description=f"Подарок для пользователя ID:{target_id}",
                    invoice_payload=payload,
                    provider_token="",
                    currency="XTR",
                    prices=[LabeledPrice(label=item['name'], amount=item['stars'])]
                )
                bot.answer_callback_query(call.id, f"⭐️ Счёт на {item['stars']} ⭐️ выставлен!")
            except Exception as e:
                print(f"[STARS GIFT INVOICE ERROR] {e}")
                bot.answer_callback_query(call.id, "❌ Не удалось выставить счёт.", show_alert=True)
            return

        # ИНИЦИАЦИЯ ОПЛАТЫ STARS: ПАКЕТЫ КОИНОВ
        elif action_data.startswith('star_buy_coins_'):
            pack_key = action_data.replace('star_buy_coins_', '')
            if pack_key in STARS_COIN_PACKS:
                pack = STARS_COIN_PACKS[pack_key]
                try:
                    bot.send_invoice(
                        chat_id=chat_id,
                        title=pack['name'],
                        description=pack['desc'],
                        invoice_payload=f"coinpack_{pack_key}:{user_id}:{int(time.time())}",
                        provider_token="",
                        currency="XTR",
                        prices=[LabeledPrice(label=pack['name'], amount=pack['stars'])]
                    )
                    bot.answer_callback_query(call.id, f"⭐️ Счёт на {pack['stars']} ⭐️ выставлен!")
                except Exception as e:
                    bot.answer_callback_query(call.id, f"❌ Ошибка выставления счёта: {e}", show_alert=True)
            return

        # ИНИЦИАЦИЯ ОПЛАТЫ STARS: VIP PASS
        elif action_data.startswith('star_buy_pass_'):
            pass_key = action_data.replace('star_buy_pass_', '')
            if pass_key in STARS_VIP_PASS:
                item = STARS_VIP_PASS[pass_key]
                econ = get_user_econ(user_id, user_name, username=user_username)
                purchase_error = stars_purchase_error(econ, 'vippass', pass_key)
                if purchase_error:
                    bot.answer_callback_query(call.id, purchase_error, show_alert=True)
                    return
                try:
                    bot.send_invoice(
                        chat_id=chat_id,
                        title=item['name'],
                        description=item['desc'],
                        invoice_payload=f"vippass_{pass_key}:{user_id}:{int(time.time())}",
                        provider_token="",
                        currency="XTR",
                        prices=[LabeledPrice(label=item['name'], amount=item['stars'])]
                    )
                    bot.answer_callback_query(call.id, f"⭐️ Счёт на {item['stars']} ⭐️ выставлен!")
                except Exception as e:
                    bot.answer_callback_query(call.id, f"❌ Ошибка выставления счёта: {e}", show_alert=True)
            return

        # ИНИЦИАЦИЯ ОПЛАТЫ STARS: КОСМЕТИКА И СТАТУС
        elif action_data.startswith('star_buy_cosm_'):
            cosm_key = action_data.replace('star_buy_cosm_', '')
            if cosm_key in STARS_COSMETICS:
                item = STARS_COSMETICS[cosm_key]
                econ = get_user_econ(user_id, user_name, username=user_username)
                purchase_error = stars_purchase_error(econ, 'cosm', cosm_key)
                if purchase_error:
                    bot.answer_callback_query(call.id, purchase_error, show_alert=True)
                    return
                try:
                    bot.send_invoice(
                        chat_id=chat_id,
                        title=item['name'],
                        description=item['desc'],
                        invoice_payload=f"cosm_{cosm_key}:{user_id}:{int(time.time())}",
                        provider_token="",
                        currency="XTR",
                        prices=[LabeledPrice(label=item['name'], amount=item['stars'])]
                    )
                    bot.answer_callback_query(call.id, f"⭐️ Счёт на {item['stars']} ⭐️ выставлен!")
                except Exception as e:
                    bot.answer_callback_query(call.id, f"❌ Ошибка выставления счёта: {e}", show_alert=True)
            return

        if action_data == 'shop_main':
            send_shop_menu(chat_id, user_id, user_name, message_id=call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        # ПЕРЕХОД В РАЗДЕЛ «ГАРАЖ» ИЗ МАГАЗИНА
        elif action_data == 'shop_cat_garage':
            render_garage_view(chat_id, user_id, user_name, message_id=call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        # ИНТЕРАКТИВНОЕ ПЕРЕКЛЮЧЕНИЕ ТОПОВ
        elif action_data.startswith('top_cat_'):
            cat = action_data.replace('top_cat_', '')
            render_top_menu(chat_id, user_id=user_id, category=cat, message_id=call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        # ОТМЕНА ПАРТИИ В ДУРАКА (С ВОЗВРАТОМ СТАВОК)
        elif action_data.startswith('durak_cancel_'):
            game_id = action_data.replace('durak_cancel_', '')
            game = active_durak.get(game_id)
            if not game:
                bot.answer_callback_query(call.id, "❌ Игра уже завершена или не найдена!", show_alert=True)
                return
            creator_id = game['players'][0]['id'] if game.get('players') else None
            if user_id != creator_id and not is_admin(chat_id, user_id):
                bot.answer_callback_query(call.id, "❌ Отменить игру может только её создатель или администратор!", show_alert=True)
                return
            bet = game.get('bet', 0)
            for p in game.get('players', []):
                if p.get('id') and p['id'] != 'bot' and bet > 0:
                    add_coins(p['id'], p.get('name'), bet)
            active_durak.pop(game_id, None)
            mark_dirty()
            bot.answer_callback_query(call.id, "✅ Партия в «Дурака» отменена, ставки возвращены!")
            try:
                bot.edit_message_text("❌ <b>Партия в «Дурака» отменена создателем.</b> Все ставки возвращены игрокам. 😸", chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML')
            except Exception:
                pass
            return

        # ИСПРАВЛЕННЫЙ ПЕРЕХОД В РАЗДЕЛ «КОЛЬЦА» В МАГАЗИНЕ
        elif action_data == 'shop_cat_rings':
            lines = [
                "💍 <b>КАТАЛОГ СВАДЕБНЫХ КОЛЕЦ</b> 💒 😺",
                "──────────────────────",
                "<i>Кольца необходимы для заключения брака (/marry) и украшают ваш профиль!</i>\n"
            ]
            for r_k, r_v in RINGS.items():
                lines.append(f"• {r_v['emoji']} <b>{r_v['name']}</b> — <code>{r_v['price']} 🪙</code>")
            lines.append("──────────────────────")

            markup = InlineKeyboardMarkup(row_width=1)
            for r_k, r_v in RINGS.items():
                markup.add(InlineKeyboardButton(f"Купить {r_v['emoji']} {r_v['name']} ({r_v['price']} 🪙)", callback_data=f"buy_ring_{r_k}:{user_id}"))
            markup.add(InlineKeyboardButton("🔙 Назад в магазин", callback_data=f"shop_main:{user_id}"))

            try:
                bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            bot.answer_callback_query(call.id)
            return

        # САД: УДОБРЕНИЕ
        elif action_data == 'fertilize_plant':
            econ = get_user_econ(user_id, user_name)
            garden = econ.get('garden')
            if not garden:
                bot.answer_callback_query(call.id, "❌ В саду ничего не растёт!", show_alert=True)
                return
            bp = econ.setdefault('backpack', {})
            if bp.get('garden_fertilizer', 0) <= 0:
                bot.answer_callback_query(call.id, "❌ У вас нет удобрения! Купите в /shop 😿", show_alert=True)
                return
            fert_used = int(garden.get('fertilizer_used', 0))
            if fert_used >= 3:
                bot.answer_callback_query(call.id, "❌ Для этого растения уже использовано максимум 3 удобрения! 😿", show_alert=True)
                return
            bp['garden_fertilizer'] -= 1
            garden['fertilizer_used'] = fert_used + 1
            seed_info = GARDEN_SEEDS[garden['seed']]
            cut_time = seed_info['grow_time'] * 0.10
            garden['planted_at'] -= cut_time
            mark_dirty()
            bot.answer_callback_query(call.id, "🧪 Растение удобрено! Рост ускорен на 10%! 😻", show_alert=True)
            render_garden_view(chat_id, user_id, user_name, call.message.message_id)
            return

        # САД: ПЛАТНЫЙ ПОЛИВ (15 коинов)
        elif action_data == 'water_plant':
            econ = get_user_econ(user_id, user_name, username=user_username)
            garden = econ.get('garden')
            if not garden: return
            seed_info = GARDEN_SEEDS[garden['seed']]
            
            now = time.time()
            last_dry_calc = garden.get('last_dry_calc', garden.get('planted_at', now))
            dry_interval = 3600 * 2
            lost_water = int((now - last_dry_calc) // dry_interval)
            if lost_water > 0:
                garden['water_count'] = max(0, garden.get('water_count', 0) - lost_water)
                garden['last_dry_calc'] = last_dry_calc + (lost_water * dry_interval)

            if garden['water_count'] >= seed_info['water_req']:
                bot.answer_callback_query(call.id, "💦 Земля максимально увлажнена! Полив сейчас не требуется. 😸", show_alert=True)
                return

            water_cost = 15
            if econ['balance'] < water_cost:
                bot.answer_callback_query(call.id, f"❌ На ведро воды нужно {water_cost} 🪙! 😿", show_alert=True)
                return

            econ['balance'] -= water_cost
            garden['water_count'] += 1
            garden['last_dry_calc'] = time.time()
            mark_dirty()
            bot.answer_callback_query(call.id, "💦 Растение полито свежей водой (-15 🪙)! 😸")
            render_garden_view(chat_id, user_id, user_name, call.message.message_id)
            return

        # ДУРАК: ВЫБОР РЕЖИМА
        elif action_data.startswith('durak_mode_'):
            m_parts = action_data.split('_')
            mode_num = int(m_parts[2])
            bet = int(m_parts[3])

            econ = get_user_econ(user_id, user_name, username=user_username)
            if bet > 0 and econ['balance'] < bet:
                bot.answer_callback_query(call.id, f"❌ Недостаточно средств для ставки {bet} 🪙!", show_alert=True)
                return

            if bet > 0:
                econ['balance'] -= bet
                mark_dirty()

            game_id = f"durak_{user_id}_{time.time_ns()}"
            deck = create_durak_deck()
            trump_card = deck[0]
            trump_suit = trump_card['suit']

            if mode_num == 1:
                bet = 0  # Против бота игра без ставок (множитель 2х отключен)
                p_human = {'id': user_id, 'name': user_name, 'hand': []}
                p_bot = {'id': 'bot', 'name': '🤖 Ня-Бот', 'hand': []}
                players = [p_human, p_bot]
                game = {
                    'mode_name': 'Соло против Бота',
                    'target_players': 2,
                    'bet': bet,
                    'players': players,
                    'deck': deck,
                    'trump': trump_suit,
                    'table': [],
                    'attacker_idx': 0,
                    'defender_idx': 1,
                    'started': True,
                    'finished': False,
                    'status_text': 'Игра началась! Вы ходите первым.',
                    'start_time': time.time(),
                    'chat_id': chat_id,
                    'msg_id': call.message.message_id
                }
                durak_deal_cards(game)
                active_durak[game_id] = game
                text, markup = render_durak_board(game_id, viewer_id=user_id)
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
            else:
                players = [{'id': user_id, 'name': user_name, 'hand': []}]
                game = {
                    'mode_name': f'Мультиплеер ({mode_num} игроков)',
                    'target_players': mode_num,
                    'bet': bet,
                    'players': players,
                    'deck': deck,
                    'trump': trump_suit,
                    'table': [],
                    'attacker_idx': 0,
                    'defender_idx': 1,
                    'started': False,
                    'finished': False,
                    'status_text': f'Ожидание игроков... (1/{mode_num})',
                    'start_time': time.time(),
                    'chat_id': chat_id,
                    'msg_id': call.message.message_id
                }
                active_durak[game_id] = game
                text, markup = render_durak_board(game_id, viewer_id=user_id)
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")

        # ДУРАК: ПРИСОЕДИНЕНИЕ (С ПРОВЕРКОЙ ЛС)
        elif action_data.startswith('durak_join_'):
            game_id = action_data.replace('durak_join_', '')
            game = active_durak.get(game_id)
            if not game or game['started']:
                bot.answer_callback_query(call.id, "❌ Игра уже началась или завершена!", show_alert=True)
                return

            if any(p['id'] == user_id for p in game['players']):
                bot.answer_callback_query(call.id, "Вы уже присоединились к этому столу!", show_alert=True)
                return

            try:
                test_msg = bot.send_message(user_id, "🤝 <b>Вы успешно подключились к столу игры «Дурак»!</b>\nВаши карты будут отправлены сюда, как только наберется вся команда! 🃏 😻", parse_mode='HTML')
                user_pm_msg_id = test_msg.message_id
            except Exception:
                b_name = ""
                try: b_name = bot.get_me().username
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
                tag_str = f"@{b_name}" if b_name else "бота"
                bot.answer_callback_query(call.id, f"❌ Вы должны сначала открыть диалог с ботом ({tag_str}) в ЛС и нажать START (Запустить), чтобы бот мог выдать вам карты!", show_alert=True)
                return

            bet = game['bet']
            econ = get_user_econ(user_id, user_name, username=user_username)
            if bet > 0 and econ['balance'] < bet:
                bot.answer_callback_query(call.id, f"❌ Для входа нужно {bet} 🪙!", show_alert=True)
                return

            if bet > 0:
                econ['balance'] -= bet
                mark_dirty()

            game['players'].append({'id': user_id, 'name': user_name, 'hand': [], 'pm_msg_id': user_pm_msg_id})
            cur_cnt = len(game['players'])
            req_cnt = game['target_players']

            if cur_cnt >= req_cnt:
                game['started'] = True
                durak_deal_cards(game)
                game['status_text'] = f"Все игроки в сборе! Ходит {game['players'][0]['name']}! Карты розданы в ЛС."
                sync_durak_pm(game_id)

            text, markup = render_durak_board(game_id, viewer_id=user_id)
            try: bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            bot.answer_callback_query(call.id, "✅ Вы успешно сели за игровой стол! Карты придут в ЛС! 😸")

        # ДУРАК: ХОД КАРТОЙ
        elif action_data.startswith('durak_card_'):
            m_parts = action_data.split('_')
            game_id = f"{m_parts[2]}_{m_parts[3]}_{m_parts[4]}"
            card_idx = int(m_parts[5])
            game = active_durak.get(game_id)

            if not game or game.get('finished'):
                bot.answer_callback_query(call.id, "❌ Игра завершена!", show_alert=True)
                return

            players = game['players']
            p_idx = next((i for i, p in enumerate(players) if p['id'] == user_id), None)
            if p_idx is None:
                bot.answer_callback_query(call.id, "❌ Вы не участник этой партии!", show_alert=True)
                return

            p = players[p_idx]
            if card_idx >= len(p['hand']):
                bot.answer_callback_query(call.id, "Карта уже сыграна!")
                return
            card = p['hand'][card_idx]
            trump = game['trump']

            is_attacker = (p_idx == game['attacker_idx'])
            is_defender = (p_idx == game['defender_idx'])

            def_hand_len = len(game['players'][game['defender_idx']]['hand'])
            unbeaten_cards = sum(1 for pair in game['table'] if pair.get('defend') is None)

            if not is_attacker and not is_defender:
                table_ranks = {pair['attack']['rank'] for pair in game['table']} | {pair['defend']['rank'] for pair in game['table'] if pair.get('defend')}
                if card['rank'] not in table_ranks or len(game['table']) >= 6 or unbeaten_cards >= def_hand_len:
                    bot.answer_callback_query(call.id, "❌ Нельзя подкинуть (лимит карт у защитника или неподходящий ранг)!", show_alert=True)
                    return
                p['hand'].pop(card_idx)
                game['table'].append({'attack': card, 'defend': None})
                game['status_text'] = f"{p['name']} подкинул(а) {card_to_str(card)}!"
            elif is_attacker:
                if not game['table']:
                    p['hand'].pop(card_idx)
                    game['table'].append({'attack': card, 'defend': None})
                    game['status_text'] = f"{p['name']} пошёл(ла) с {card_to_str(card)}!"
                else:
                    table_ranks = {pair['attack']['rank'] for pair in game['table']} | {pair['defend']['rank'] for pair in game['table'] if pair.get('defend')}
                    if card['rank'] not in table_ranks or len(game['table']) >= 6 or unbeaten_cards >= def_hand_len:
                        bot.answer_callback_query(call.id, "❌ Нельзя подкинуть (лимит карт у защитника или неподходящий ранг)!", show_alert=True)
                        return
                    p['hand'].pop(card_idx)
                    game['table'].append({'attack': card, 'defend': None})
                    game['status_text'] = f"{p['name']} подкинул(а) {card_to_str(card)}!"
            elif is_defender:
                unbeaten_idx = next((i for i, pair in enumerate(game['table']) if pair.get('defend') is None), None)
                if unbeaten_idx is None:
                    bot.answer_callback_query(call.id, "Все карты на столе уже отбиты!")
                    return
                target_attack = game['table'][unbeaten_idx]['attack']
                if not can_beat_card(target_attack, card, trump):
                    bot.answer_callback_query(call.id, f"❌ Карта {card_to_str(card)} не бьёт {card_to_str(target_attack)}!", show_alert=True)
                    return
                p['hand'].pop(card_idx)
                game['table'][unbeaten_idx]['defend'] = card
                game['status_text'] = f"{p['name']} отбил(а) {card_to_str(target_attack)} картой {card_to_str(card)}!"

            if game['target_players'] == 2 and game['players'][1]['id'] == 'bot':
                durak_bot_turn(game)

            survivors = [pl for pl in players if len(pl['hand']) > 0 or len(game['deck']) > 0]
            if len(survivors) <= 1:
                game['finished'] = True
                loser = survivors[0] if survivors else None
                is_vs_bot = any(pl['id'] == 'bot' for pl in players)
                if is_vs_bot:
                    tot_pot = game['bet']  # Без умножителя 2х за победу над ботом
                else:
                    tot_pot = game['bet'] * len(players)
                win_text = f"🏁 <b>ИГРА ОКОНЧЕНА!</b>\n"
                if loser:
                    win_text += f"🃏 В дураках остался: <b>{loser['name']}</b>! 🙀\n"
                else:
                    win_text += "🤝 Боевая ничья! Все вышли из игры! 😸\n"

                winners = [pl for pl in players if pl != loser and pl['id'] != 'bot']
                if winners and tot_pot > 0:
                    split_win = tot_pot // len(winners)
                    for w in winners:
                        add_coins(w['id'], w['name'], split_win)
                    if is_vs_bot:
                        win_text += f"💰 Возврат ставки: <b>+{split_win} 🪙</b> (умножитель 2х против бота отключен)!"
                    else:
                        win_text += f"💰 Победители разделили банк: <b>+{split_win} 🪙</b> каждому!"

                game['status_text'] = win_text
                text, markup = render_durak_board(game_id, viewer_id=user_id)
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
                sync_durak_pm(game_id)
                active_durak.pop(game_id, None)
                return

            text, markup = render_durak_board(game_id, viewer_id=user_id)
            try: bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            sync_durak_pm(game_id)
            bot.answer_callback_query(call.id)

        # ДУРАК: ВЗЯТЬ КАРТЫ
        elif action_data.startswith('durak_take_'):
            game_id = action_data.replace('durak_take_', '')
            game = active_durak.get(game_id)
            if not game: return
            p_idx = next((i for i, pl in enumerate(game['players']) if pl['id'] == user_id), None)
            if p_idx != game['defender_idx']:
                bot.answer_callback_query(call.id, "Только защищающийся может взять карты!", show_alert=True)
                return

            taken = []
            for pair in game['table']:
                taken.append(pair['attack'])
                if pair.get('defend'): taken.append(pair['defend'])
            game['players'][p_idx]['hand'].extend(taken)
            game['table'] = []
            durak_deal_cards(game)

            game['attacker_idx'] = (game['defender_idx'] + 1) % len(game['players'])
            game['defender_idx'] = (game['attacker_idx'] + 1) % len(game['players'])
            game['status_text'] = f"{user_name} забрал(а) карты со стола!"

            if game['target_players'] == 2 and game['players'][1]['id'] == 'bot':
                durak_bot_turn(game)

            text, markup = render_durak_board(game_id, viewer_id=user_id)
            try: bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            sync_durak_pm(game_id)
            bot.answer_callback_query(call.id)

        # ДУРАК: БИТО
        elif action_data.startswith('durak_bito_'):
            game_id = action_data.replace('durak_bito_', '')
            game = active_durak.get(game_id)
            if not game: return

            game['table'] = []
            durak_deal_cards(game)
            game['attacker_idx'] = game['defender_idx']
            game['defender_idx'] = (game['defender_idx'] + 1) % len(game['players'])
            game['status_text'] = "✅ Бито! Карты ушли в отбой!"

            if game['target_players'] == 2 and game['players'][1]['id'] == 'bot':
                durak_bot_turn(game)

            text, markup = render_durak_board(game_id, viewer_id=user_id)
            try: bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            sync_durak_pm(game_id)
            bot.answer_callback_query(call.id)

        # ИГРА КИРПИЧ
        elif action_data.startswith('brick_step_'):
            game_id = action_data.replace('brick_step_', '')
            game = active_brick.get(game_id)
            if not game or game.get('finished'):
                bot.answer_callback_query(call.id, "❌ Игра уже окончена!", show_alert=True)
                return
            if user_id != game['user_id']:
                bot.answer_callback_query(call.id, "❌ Не ваша игра!", show_alert=True)
                return

            step = game['step']
            if step >= len(game['mults']) - 1:
                bot.answer_callback_query(call.id, "❌ Максимальный шаг достигнут! Забирайте куш.", show_alert=True)
                return

            risk = game['risks'][step + 1]
            mult = game['mults'][step + 1]

            if random.random() < risk:
                game['finished'] = True
                try:
                    bot.edit_message_text(
                        f"🧱 <b>КРАШ НА СТРОЙКЕ!</b> 🙀\n\n"
                        f"👤 Игрок: {make_link(chat_id, user_name, user_id, ping=False)}\n"
                        f"💥 Кирпич сорвался на шаге {step+1} (Множитель: {mult:.2f}x)!\n"
                        f"💸 Ставка <b>{game['bet']} 🪙</b> утеряна... 😿",
                        chat_id=chat_id,
                        message_id=call.message.message_id,
                        parse_mode='HTML'
                    )
                except Exception:
                    pass
                del active_brick[game_id]
                return

            game['step'] = step + 1
            cashout_amt = int(game['bet'] * mult)

            markup = InlineKeyboardMarkup()
            if game['step'] < len(game['mults']) - 1:
                markup.add(InlineKeyboardButton(f"🏗 Сделать шаг (Риск {int(game['risks'][game['step']+1]*100)}%)", callback_data=f"brick_step_{game_id}:{user_id}"))
            markup.add(InlineKeyboardButton(f"💰 Забрать куш ({cashout_amt} 🪙 | {mult:.2f}x) 😻", callback_data=f"brick_cashout_{game_id}:{user_id}"))

            bar = "🟩" * (game['step'] + 1) + "⬜️" * (len(game['mults']) - game['step'] - 1)
            try:
                bot.edit_message_text(
                    f"🧱 <b>ИГРА КИРПИЧ (СТРОЙКА)</b> 😺\n"
                    f"──────────────────────\n"
                    f"👤 Строитель: {make_link(chat_id, user_name, user_id, ping=False)}\n"
                    f"💰 Ставка: <b>{game['bet']} 🪙</b>\n"
                    f"📈 Текущий множитель: <b>{mult:.2f}x</b>\n"
                    f"🏗 Прогресс: [{bar}]\n"
                    f"──────────────────────",
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    reply_markup=markup,
                    parse_mode='HTML'
                )
            except Exception:
                pass

        elif action_data.startswith('brick_cashout_'):
            game_id = action_data.replace('brick_cashout_', '')
            game = active_brick.get(game_id)
            if not game or game.get('finished'):
                bot.answer_callback_query(call.id, "❌ Игра окончена!", show_alert=True)
                return
            if user_id != game['user_id']:
                bot.answer_callback_query(call.id, "❌ Не ваша игра!", show_alert=True)
                return

            game['finished'] = True
            mult = game['mults'][game['step']]
            win_amt = int(game['bet'] * mult)
            win_amt = process_casino_win(win_amt)

            econ = get_user_econ(user_id, user_name, username=user_username)
            econ['balance'] += win_amt
            econ['daily_casino_win'] = econ.get('daily_casino_win', 0) + (win_amt - game['bet'])
            econ['daily_casino_profit'] = econ.get('daily_casino_profit', 0) + (win_amt - game['bet'])
            check_achievements(user_id, user_name, 'games', 1, chat_id, username=user_username)
            mark_dirty()

            try:
                bot.edit_message_text(
                    f"💰 <b>ВЫ УСПЕШНО ЗАБРАЛИ КУШ!</b> 😻\n\n"
                    f"👤 Строитель: {make_link(chat_id, user_name, user_id, ping=False)}\n"
                    f"🎉 Выигрыш: <b>+{win_amt} Ня-коинов 🪙</b> (Множитель: <b>{mult:.2f}x</b>)!\n"
                    f"💵 Баланс: <b>{econ['balance']} 🪙</b> 😸",
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    parse_mode='HTML'
                )
            except Exception:
                pass
            del active_brick[game_id]

        # ИГРА КРАШ: CASHOUT
        elif action_data.startswith('crash_cashout_'):
            game_id = action_data.replace('crash_cashout_', '')
            game = active_crash.get(game_id)
            if not game or game.get('cashed_out') or game.get('exploded'):
                bot.answer_callback_query(call.id, "❌ Раунд уже завершен!", show_alert=True)
                return
            if user_id != game['user_id']:
                bot.answer_callback_query(call.id, "❌ Это не ваш раунд!", show_alert=True)
                return

            game['cashed_out'] = True
            game['finished'] = True
            mult = game['current_mult']
            win_amt = int(game['bet'] * mult)
            win_amt = process_casino_win(win_amt)

            add_coins(user_id, user_name, win_amt, username=user_username)
            add_account_exp(user_id, user_name, 20, username=user_username)
            econ = get_user_econ(user_id, user_name, username=user_username)
            econ['daily_casino_win'] = econ.get('daily_casino_win', 0) + (win_amt - game['bet'])
            econ['daily_casino_profit'] = econ.get('daily_casino_profit', 0) + (win_amt - game['bet'])
            check_achievements(user_id, user_name, 'games', 1, chat_id, username=user_username)
            mark_dirty()

            bot.answer_callback_query(call.id, f"🎉 Куш забран: +{win_amt} 🪙 ({mult:.2f}x)! 😻", show_alert=True)
            try:
                bot.edit_message_text(
                    f"💰 <b>УСПЕШНЫЙ CASHOUT В КРАШЕ!</b> 😺\n\n"
                    f"👤 Пилот: {make_link(chat_id, user_name, user_id, ping=False)}\n"
                    f"🎉 Зафиксирован выигрыш: <b>+{win_amt} Ня-коинов 🪙</b> (Множитель: <b>{mult:.2f}x</b>)! 😻\n"
                    f"💵 Баланс: <b>{econ['balance']} 🪙</b>",
                    chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML'
                )
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            active_crash.pop(game_id, None)

        # РАСХОДНИКИ
        elif action_data == 'use_item_energy_drink':
            econ = get_user_econ(user_id, user_name, username=user_username)
            bp = econ.setdefault('backpack', {})
            if bp.get('energy_drink', 0) <= 0:
                bot.answer_callback_query(call.id, "❌ У вас нет энергетика!", show_alert=True)
                return

            now = time.time()
            last_drink = econ.get('last_energy_drink_time', 0)
            cooldown_drink = 1800
            left = cooldown_text(last_drink, cooldown_drink)
            if left:
                bot.answer_callback_query(call.id, f"⏳ Энергетик можно пить не чаще 1 раза в 30 минут! Ждать: {left} 😿", show_alert=True)
                return

            bp['energy_drink'] -= 1
            econ['last_energy_drink_time'] = now
            econ['last_work_time'] = 0; econ['last_fish_time'] = 0; econ['last_hunt_time'] = 0
            econ['last_train_time'] = 0; econ['last_iq_time'] = 0; econ['last_fat_time'] = 0
            econ['last_foot_time'] = 0; econ['last_chromosomes_time'] = 0; econ['last_dick_time'] = 0
            econ['last_trash_time'] = 0
            mark_dirty()
            bot.answer_callback_query(call.id, "⚡️ Энергетик выпит! Все таймеры сброшены! 😻", show_alert=True)
            render_backpack_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'use_item_luck_clover':
            econ = get_user_econ(user_id, user_name, username=user_username)
            bp = econ.setdefault('backpack', {})
            if bp.get('luck_clover', 0) <= 0:
                bot.answer_callback_query(call.id, "❌ У вас нет клевера! 😿", show_alert=True)
                return
            bp['luck_clover'] -= 1
            econ['luck_clover_until'] = time.time() + 3600
            mark_dirty()
            bot.answer_callback_query(call.id, "🍀 Клевер активирован! +15% к удаче в играх на 1 час! 😺", show_alert=True)
            render_backpack_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'use_item_invis_mask':
            econ = get_user_econ(user_id, user_name, username=user_username)
            bp = econ.setdefault('backpack', {})
            if bp.get('invis_mask', 0) <= 0:
                bot.answer_callback_query(call.id, "❌ У вас нет маски-невидимки! 😿", show_alert=True)
                return
            bp['invis_mask'] -= 1
            econ['invis_until'] = time.time() + 86400
            mark_dirty()
            bot.answer_callback_query(call.id, "🥷 Маска надета! Ваши замеры скрыты из топов на 24 часа! 😼", show_alert=True)
            render_backpack_view(chat_id, user_id, user_name, call.message.message_id)

        # СТУДИЯ СТРИМЕРА
        elif action_data == 'shop_cat_stream':
            econ = get_user_econ(user_id, user_name)
            studio = econ.setdefault('stream_studio', {'mic': 1, 'webcam': 1, 'light': 1})
            lines = [
                "🎙 <b>СТУДИЯ СТРИМЕРА (АПГРЕЙДЫ)</b> 😺", "──────────────────────",
                "<i>Улучшайте оборудование, чтобы привлекать больше зрителей!</i>\n"
            ]
            markup = InlineKeyboardMarkup(row_width=1)
            for k, v in STREAM_EQUIP.items():
                lvl = studio.get(k, 1)
                if lvl < 4:
                    cost = v['levels'][lvl]
                    lines.append(f"• <b>{v['name']}</b> (Ур. {lvl}/4) -> {cost} 🪙")
                    markup.add(InlineKeyboardButton(f"⬆️ Улучшить {v['name']} -> {cost} 🪙", callback_data=f"buy_studio_{k}:{user_id}"))
                else:
                    lines.append(f"• <b>{v['name']}</b> (Ур. МАХ) -> Полностью прокачано!")

            lines.append("──────────────────────")
            markup.add(InlineKeyboardButton("🔙 Назад в магазин", callback_data=f"shop_main:{user_id}"))
            try: bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('buy_studio_'):
            equip_key = action_data.replace('buy_studio_', '')
            econ = get_user_econ(user_id, user_name, username=user_username)
            studio = econ.setdefault('stream_studio', {'mic': 1, 'webcam': 1, 'light': 1})
            lvl = studio.get(equip_key, 1)
            if lvl >= 4:
                bot.answer_callback_query(call.id, "❌ Максимальный уровень! 🙀", show_alert=True)
                return
            cost = STREAM_EQUIP[equip_key]['levels'][lvl]
            if econ['balance'] < cost:
                bot.answer_callback_query(call.id, f"❌ Нужно {cost} 🪙! 😿", show_alert=True)
                return
            econ['balance'] -= cost
            studio[equip_key] = lvl + 1
            mark_dirty()
            bot.answer_callback_query(call.id, f"🎉 Вы улучшили {STREAM_EQUIP[equip_key]['name']} до {lvl+1} уровня! 😻")
            send_shop_menu(chat_id, user_id, user_name, message_id=call.message.message_id)

        # СЕМЕНА САДА
        elif action_data == 'shop_cat_garden':
            lines = [
                "🪴 <b>СЕМЕНА ОРАНЖЕРЕИ БОНСАЙ</b> 😺", "──────────────────────",
                "<i>Посадите семечко, поливайте его и соберите ценный урожай!</i> 😸\n"
            ]
            for s_id, s_info in GARDEN_SEEDS.items():
                hrs = s_info['grow_time'] // 3600
                lines.append(f"• {s_info['emoji']} <b>{s_info['name']}</b> — <code>{s_info['price']} 🪙</code>\n  <i>(Рост: {hrs} ч., Поливов: {s_info['water_req']}, Прибыль: {s_info['reward_min']}-{s_info['reward_max']} 🪙)</i>\n")
            lines.append("──────────────────────")

            markup = InlineKeyboardMarkup(row_width=2)
            btns = [InlineKeyboardButton(f"{s['emoji']} {s['price']} 🪙", callback_data=f"buy_seed_{s_id}:{user_id}") for s_id, s in GARDEN_SEEDS.items()]
            for i in range(0, len(btns), 2):
                markup.add(*btns[i:i+2])
            markup.add(InlineKeyboardButton("🔙 Назад в магазин", callback_data=f"shop_main:{user_id}"))
            try: bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('buy_seed_'):
            s_id = action_data.replace('buy_seed_', '')
            if s_id in GARDEN_SEEDS:
                seed = GARDEN_SEEDS[s_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                if econ.get('garden'):
                    bot.answer_callback_query(call.id, "❌ У вас уже растет растение в саду! Сначала соберите его. 😾", show_alert=True)
                    return
                if econ['balance'] < seed['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {seed['price']} 🪙! 😿", show_alert=True)
                    return
                econ['balance'] -= seed['price']
                econ['garden'] = {'seed': s_id, 'planted_at': time.time(), 'water_count': 0, 'last_dry_calc': time.time()}
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Вы посадили {seed['name']}! Зайдите в /garden 😻", show_alert=True)
                render_garden_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'harvest_plant':
            econ = get_user_econ(user_id, user_name)
            garden = econ.get('garden')
            if not garden: return
            seed_info = GARDEN_SEEDS[garden['seed']]
            elapsed = time.time() - garden['planted_at']
            if elapsed < seed_info['grow_time']:
                bot.answer_callback_query(call.id, "❌ Урожай еще не созрел! 😿", show_alert=True)
                return
            if garden['water_count'] < seed_info['water_req']:
                bot.answer_callback_query(call.id, "❌ Растению не хватило полива! Земля высохла. 😾", show_alert=True)
                return
            reward = random.randint(seed_info['reward_min'], seed_info['reward_max'])
            econ['balance'] += reward
            econ['garden'] = None
            change_karma(user_id, user_name, 2)
            mark_dirty()
            bot.answer_callback_query(call.id, f"🎉 Урожай собран: +{reward} 🪙! 😻")
            try:
                bot.edit_message_text(
                    f"🪴 <b>СБОР УРОЖАЯ</b> 😺\n──────────────────────\n"
                    f"Вы собрали великолепный урожай {seed_info['name']} и продали его за <b>{reward} Ня-коинов 🪙</b>!\n"
                    f"Карма повышена: <b>+2 😇</b>",
                    chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML'
                )
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data == 'uproot_plant':
            econ = get_user_econ(user_id, user_name)
            econ['garden'] = None
            mark_dirty()
            bot.answer_callback_query(call.id, "❌ Растение выкорчевано. 😿")
            render_garden_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'shop_cat_buffs':
            lines = [
                "🧰 <b>МАГАЗИН РАСХОДНИКОВ И БАФФОВ</b> 😺", "──────────────────────",
                "<i>Используйте расходники из рюкзака (/backpack) для преимуществ!</i> 😸\n"
            ]
            for b_id, b_info in BUFF_ITEMS.items():
                lines.append(f"• <b>{b_info['name']}</b> — <code>{b_info['price']} 🪙</code>\n  <i>{b_info['desc']}</i>\n")
            lines.append("──────────────────────")
            markup = InlineKeyboardMarkup(row_width=2)
            btns = [InlineKeyboardButton(f"{b['short']} • {b['price']} 🪙", callback_data=f"buy_buff_{b_id}:{user_id}") for b_id, b in BUFF_ITEMS.items()]
            for i in range(0, len(btns), 2):
                markup.add(*btns[i:i+2])
            markup.add(InlineKeyboardButton("🔙 Назад в магазин", callback_data=f"shop_main:{user_id}"))
            try: bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('buy_buff_'):
            b_id = action_data.replace('buy_buff_', '')
            if b_id in BUFF_ITEMS:
                item = BUFF_ITEMS[b_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                if econ['balance'] < item['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {item['price']} 🪙! 😿", show_alert=True)
                    return
                econ['balance'] -= item['price']
                bp = econ.setdefault('backpack', {})
                bp[b_id] = bp.get(b_id, 0) + 1
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Куплен предмет: {item['short']}! Откройте /backpack 😻", show_alert=True)

        elif action_data == 'shop_cat_themes':
            lines = [
                "🎨 <b>КАТАЛОГ ТЕМ ОФОРМЛЕНИЯ ПРОФИЛЯ</b> 😺", "──────────────────────",
                "<i>Тема полностью меняет графический стиль и рамки команды /profile!</i> 😸\n"
            ]
            for t_k, t_v in THEMES.items():
                if t_k != 'default': lines.append(f"• <b>{t_v['name']}</b> — <code>{t_v['price']} 🪙</code>")
            lines.append("──────────────────────")
            markup = InlineKeyboardMarkup(row_width=2)
            btns = [InlineKeyboardButton(f"{t_v['name']} • {t_v['price']} 🪙", callback_data=f"buy_theme_{t_k}:{user_id}") for t_k, t_v in THEMES.items() if t_k != 'default']
            for i in range(0, len(btns), 2):
                markup.add(*btns[i:i+2])
            markup.add(InlineKeyboardButton("🔙 Назад в магазин", callback_data=f"shop_main:{user_id}"))
            try: bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('buy_theme_'):
            t_key = action_data.replace('buy_theme_', '')
            if t_key in THEMES:
                theme = THEMES[t_key]
                econ = get_user_econ(user_id, user_name, username=user_username)
                purchased = econ.setdefault('purchased_themes', ['default'])
                if t_key in purchased:
                    bot.answer_callback_query(call.id, "❌ Эта тема уже куплена! 😾", show_alert=True)
                    return
                if econ['balance'] < theme['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {theme['price']} 🪙! 😿", show_alert=True)
                    return
                econ['balance'] -= theme['price']
                purchased.append(t_key)
                econ['profile_theme'] = t_key
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Куплена тема {theme['name']}! 😻", show_alert=True)
                send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)

        elif action_data.startswith('set_theme_'):
            t_key = action_data.replace('set_theme_', '')
            econ = get_user_econ(user_id, user_name, username=user_username)
            if t_key in econ.get('purchased_themes', ['default']):
                econ['profile_theme'] = t_key
                mark_dirty()
                bot.answer_callback_query(call.id, f"✅ Установлен стиль: {THEMES[t_key]['name']}! 😸")
                send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)

        # САПЁР
        elif action_data.startswith('msz_'):
            m_parts = action_data.split('_')
            game_id = f"{m_parts[1]}_{m_parts[2]}_{m_parts[3]}"
            chosen_size = int(m_parts[4])
            game = active_mines.get(game_id)
            if not game:
                bot.answer_callback_query(call.id, "❌ Игра устарела!", show_alert=True)
                return

            game['size'] = chosen_size
            markup = InlineKeyboardMarkup(row_width=3)
            mines_options = [1, 2, 3, 5] if chosen_size == 3 else [2, 3, 5, 8] if chosen_size == 4 else [3, 5, 8, 12, 18]
            btns = [InlineKeyboardButton(f"💣 {cnt} мин", callback_data=f"mbm_{game_id}_{cnt}:{user_id}") for cnt in mines_options]
            markup.add(*btns)
            markup.add(InlineKeyboardButton("❌ Отмена (вернуть ставку)", callback_data=f"mcancel_{game_id}:{user_id}"))

            try:
                bot.edit_message_text(
                    f"💣 <b>НАСТРОЙКА ИГРЫ «САПЁР» ({chosen_size}х{chosen_size})</b> 😺\n"
                    f"──────────────────────\n"
                    f"💰 Ставка: <b>{game['bet']} 🪙</b>\n\n"
                    f"Шаг 2: <b>Сколько мин разместить на поле?</b>\n"
                    f"<i>(Больше мин = выше множитель выигрыша!)</i> 😻",
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    reply_markup=markup,
                    parse_mode='HTML'
                )
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('mbm_'):
            m_parts = action_data.split('_')
            game_id = f"{m_parts[1]}_{m_parts[2]}_{m_parts[3]}"
            mines_count = int(m_parts[4])
            game = active_mines.get(game_id)
            if not game:
                bot.answer_callback_query(call.id, "❌ Игра устарела!", show_alert=True)
                return

            total_cells = game['size'] * game['size']
            game['bombs'] = set(random.sample(range(total_cells), mines_count))
            text_board, markup = render_mines_board(game_id)
            try: bot.edit_message_text(text_board, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('mop_'):
            m_parts = action_data.split('_')
            game_id = f"{m_parts[1]}_{m_parts[2]}_{m_parts[3]}"
            cell_idx = int(m_parts[4])
            game = active_mines.get(game_id)

            if not game or game.get('finished'):
                bot.answer_callback_query(call.id, "❌ Игра уже завершена! 😿", show_alert=True)
                return
            if user_id != game['user_id']:
                bot.answer_callback_query(call.id, "❌ Это не ваше игровое поле! 😾", show_alert=True)
                return

            total_cells = game['size'] * game['size']
            mines_count = len(game['bombs'])

            if cell_idx in game['bombs']:
                game['finished'] = True
                text_board, markup = render_mines_board(game_id)
                loss_text = (
                    f"💥 <b>БАБАХ! ВЫ НАСТУПИЛИ НА МИНУ!</b> 🙀\n\n"
                    f"💸 Ставка <b>{game['bet']} Ня-коинов 🪙</b> сгорела...\n\n{text_board}"
                )
                try: bot.edit_message_text(loss_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
                del active_mines[game_id]
                return
            else:
                game['revealed'].add(cell_idx)
                safe_opened = len(game['revealed'])
                game['current_multiplier'] = calculate_mines_multiplier(total_cells, mines_count, safe_opened)

                max_safe = total_cells - mines_count
                if safe_opened >= max_safe:
                    game['finished'] = True
                    win_amt = int(game['bet'] * game['current_multiplier'])
                    win_amt = process_casino_win(win_amt)
                    add_coins(user_id, user_name, win_amt, username=user_username)
                    add_account_exp(user_id, user_name, 50, username=user_username)
                    check_achievements(user_id, user_name, 'mines_wins', 1, chat_id, username=user_username)
                    mark_dirty()

                    text_board, markup = render_mines_board(game_id)
                    win_text = (
                        f"🏆 <b>НЕВЕРОЯТНО! ВСЕ {max_safe} КРИСТАЛЛОВ НАЙДЕНЫ!</b> 😻\n\n"
                        f"💰 Чистый выигрыш: <b>+{win_amt} Ня-коинов 🪙</b> (Коэфф: <b>{game['current_multiplier']:.2f}x</b>)!\n\n{text_board}"
                    )
                    try: bot.edit_message_text(win_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                    except Exception as e: print(f"[NONFATAL ERROR] {e}")
                    del active_mines[game_id]
                    return

                text_board, markup = render_mines_board(game_id)
                try: bot.edit_message_text(text_board, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('mco_'):
            game_id = action_data.replace('mco_', '')
            game = active_mines.get(game_id)
            if not game or game.get('finished'):
                bot.answer_callback_query(call.id, "❌ Игра окончена! 😿", show_alert=True)
                return
            if user_id != game['user_id']:
                bot.answer_callback_query(call.id, "❌ Это не ваша игра! 😾", show_alert=True)
                return

            game['finished'] = True
            win_amt = int(game['bet'] * game['current_multiplier'])
            win_amt = process_casino_win(win_amt)
            add_coins(user_id, user_name, win_amt, username=user_username)
            add_account_exp(user_id, user_name, 15, username=user_username)
            check_achievements(user_id, user_name, 'mines_wins', 1, chat_id, username=user_username)
            mark_dirty()

            text_board, markup = render_mines_board(game_id)
            cash_text = (
                f"💰 <b>ВЫ УСПЕШНО ЗАБРАЛИ КУШ!</b> 😻\n\n"
                f"🎉 Начислено: <b>+{win_amt} Ня-коинов 🪙</b> (Коэффициент: <b>{game['current_multiplier']:.2f}x</b>)!\n\n{text_board}"
            )
            try: bot.edit_message_text(cash_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            del active_mines[game_id]

        elif action_data.startswith('mcancel_'):
            game_id = action_data.replace('mcancel_', '')
            game = active_mines.get(game_id)
            if game:
                econ = get_user_econ(user_id, user_name, username=user_username)
                econ['balance'] += game['bet']
                mark_dirty()
                del active_mines[game_id]
            try: bot.edit_message_text("❌ Игра отменена, ставка возвращена на баланс. 😸", chat_id=chat_id, message_id=call.message.message_id)
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        # КЛАССИЧЕСКИЙ САПЁР
        elif action_data.startswith('cstart_'):
            diff_key = action_data.replace('cstart_', '')
            if diff_key in CSAPER_DIFFICULTIES:
                d_info = CSAPER_DIFFICULTIES[diff_key]
                cols = d_info.get('cols', 5)
                rows = d_info.get('rows', 5)
                game_id = f"cm_{user_id}_{time.time_ns()}"
                active_c_mines[game_id] = {
                    'user_id': user_id,
                    'user_name': user_name,
                    'username': user_username,
                    'cols': cols,
                    'rows': rows,
                    'mines_count': d_info['mines'],
                    'reward': d_info['reward'],
                    'exp': d_info['exp'],
                    'diff_name': d_info['name'],
                    'bombs': set(),
                    'numbers': {},
                    'revealed': set(),
                    'flags': set(),
                    'mode': 'dig',
                    'first_click': True,
                    'finished': False,
                    'start_time': time.time()
                }
                text_board, markup = render_classic_mines_board(game_id)
                try: bot.edit_message_text(text_board, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('cmmode_'):
            game_id = action_data.replace('cmmode_', '')
            game = active_c_mines.get(game_id)
            if not game or game.get('finished'): return
            if user_id != game['user_id']: return

            game['mode'] = 'flag' if game.get('mode', 'dig') == 'dig' else 'dig'
            bot.answer_callback_query(call.id, "🚩 Режим флага" if game['mode'] == 'flag' else "⛏ Режим копания")
            text_board, markup = render_classic_mines_board(game_id)
            try: bot.edit_message_text(text_board, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('cmo_'):
            m_parts = action_data.split('_')
            game_id = f"{m_parts[1]}_{m_parts[2]}_{m_parts[3]}"
            cell_arg = m_parts[4]
            game = active_c_mines.get(game_id)

            if not game or game.get('finished'):
                bot.answer_callback_query(call.id, "❌ Игра завершена!", show_alert=True)
                return
            if user_id != game['user_id']:
                bot.answer_callback_query(call.id, "❌ Это не ваша игра!", show_alert=True)
                return

            cols = game.get('cols', 5)
            rows = game.get('rows', 5)
            total_cells = cols * rows

            cell_idx = int(cell_arg)

            if game.get('mode') == 'flag':
                if cell_idx in game['revealed']: return
                if cell_idx in game['flags']: game['flags'].remove(cell_idx)
                else: game['flags'].add(cell_idx)
                text_board, markup = render_classic_mines_board(game_id)
                try: bot.edit_message_text(text_board, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
                bot.answer_callback_query(call.id)
                return

            if cell_idx in game['flags']:
                bot.answer_callback_query(call.id, "🚩 Сначала снимите флаг!", show_alert=True)
                return

            if game.get('first_click', True):
                game['first_click'] = False
                forbidden = set(get_adjacent_indices(cell_idx, cols, rows) + [cell_idx])
                available = [i for i in range(total_cells) if i not in forbidden]
                if len(available) < game['mines_count']:
                    available = [i for i in range(total_cells) if i != cell_idx]
                    
                game['bombs'] = set(random.sample(available, game['mines_count']))
                numbers = {}
                for i in range(total_cells):
                    if i not in game['bombs']:
                        numbers[i] = sum(1 for neighbor in get_adjacent_indices(i, cols, rows) if neighbor in game['bombs'])
                game['numbers'] = numbers

            if cell_idx in game['bombs']:
                game['finished'] = True
                text_board, markup = render_classic_mines_board(game_id)
                loss_text = f"💥 <b>БАБАХ! МИНА СДЕТОНИРОВАЛА!</b> 🙀\n\n{text_board}"
                try: bot.edit_message_text(loss_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
                del active_c_mines[game_id]
                return

            reveal_cascade_cells(game, cell_idx)
            max_safe = total_cells - len(game['bombs'])
            if len(game['revealed']) >= max_safe:
                game['finished'] = True
                reward = game['reward']
                exp_gain = game['exp']
                add_coins(user_id, user_name, reward, username=user_username)
                add_account_exp(user_id, user_name, exp_gain, username=user_username)
                check_achievements(user_id, user_name, 'mines_wins', 1, chat_id, username=user_username)

                text_board, markup = render_classic_mines_board(game_id)
                win_text = f"🏆🧠 <b>ПОЛЕ ПОЛНОСТЬЮ РАЗМИНИРОВАНО!</b> 😻\n\n🎉 Награда: <b>+{reward} Ня-коинов 🪙</b> (+{exp_gain} EXP)!\n\n{text_board}"
                try: bot.edit_message_text(win_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
                del active_c_mines[game_id]
                return

            text_board, markup = render_classic_mines_board(game_id)
            try: bot.edit_message_text(text_board, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            bot.answer_callback_query(call.id)

        # ПИТОМЕЦ
        elif action_data == 'pet_feed':
            econ = get_user_econ(user_id, user_name, username=user_username)
            pet = econ.get('pet')
            if not pet: return
            if pet.get('hunger', 100) >= 100:
                bot.answer_callback_query(call.id, "🍖 Питомец сыт! 😸", show_alert=True)
                return
            if econ['balance'] < 30:
                bot.answer_callback_query(call.id, "❌ Нужно 30 🪙 для корма! 😿", show_alert=True)
                return
            econ['balance'] -= 30
            pet['hunger'] = min(100, pet.get('hunger', 0) + 35)
            pet['pet_exp'] = pet.get('pet_exp', 0) + 10
            check_achievements(user_id, user_name, 'pet_care', 1, chat_id, username=user_username)
            mark_dirty()
            bot.answer_callback_query(call.id, "🍖 Питомец вкусно покушал (+10 EXP)! 😻")
            render_pet_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'pet_wash':
            econ = get_user_econ(user_id, user_name, username=user_username)
            pet = econ.get('pet')
            if not pet: return
            if pet.get('cleanliness', 100) >= 100:
                bot.answer_callback_query(call.id, "🧼 Питомец уже чистый! 😸", show_alert=True)
                return
            if econ['balance'] < 20:
                bot.answer_callback_query(call.id, "❌ Нужно 20 🪙 на шампунь! 😿", show_alert=True)
                return
            econ['balance'] -= 20
            pet['cleanliness'] = min(100, pet.get('cleanliness', 0) + 40)
            pet['pet_exp'] = pet.get('pet_exp', 0) + 10
            check_achievements(user_id, user_name, 'pet_care', 1, chat_id, username=user_username)
            mark_dirty()
            bot.answer_callback_query(call.id, "🧼 Питомец искупан до блеска (+10 EXP)! 😻")
            render_pet_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'pet_walk_btn':
            bot.answer_callback_query(call.id)
            process_pet_walk(chat_id, user_id, user_name)

        # БИЗНЕС
        elif action_data.startswith('upg_biz_'):
            b_id = action_data.replace('upg_biz_', '')
            if b_id in BUSINESSES:
                b_info = BUSINESSES[b_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                biz_levels = econ.setdefault('biz_levels', {})
                cur_lvl = biz_levels.get(b_id, 1)
                if cur_lvl >= 5:
                    bot.answer_callback_query(call.id, "❌ Достигнут максимальный 5-й уровень! 😸", show_alert=True)
                    return
                cost = b_info['upgrade_cost'] * cur_lvl
                if econ['balance'] < cost:
                    bot.answer_callback_query(call.id, f"❌ Нужно {cost} 🪙! 😿", show_alert=True)
                    return
                econ['balance'] -= cost
                biz_levels[b_id] = cur_lvl + 1
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 {b_info['short']} улучшен(а) до {cur_lvl+1} уровня! 😻")
                render_business_view(chat_id, user_id, user_name, message_id=call.message.message_id)

        elif action_data.startswith('buy_biz_'):
            b_id = action_data.replace('buy_biz_', '')
            if b_id in BUSINESSES:
                b_info = BUSINESSES[b_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                user_biz = econ.setdefault('businesses', {})
                biz_levels = econ.setdefault('biz_levels', {})
                if b_id in user_biz:
                    bot.answer_callback_query(call.id, "❌ Этот бизнес уже куплен! 😾", show_alert=True)
                    return
                if econ['balance'] < b_info['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {b_info['price']} 🪙! 😿", show_alert=True)
                    return
                econ['balance'] -= b_info['price']
                user_biz[b_id] = time.time()
                biz_levels[b_id] = 1
                check_achievements(user_id, user_name, 'biz_bought', 1, chat_id, username=user_username)
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Вы приобрели {b_info['name']}! 😻")
                render_business_view(chat_id, user_id, user_name, message_id=call.message.message_id)

        elif action_data == 'collect_biz_profit':
            econ = get_user_econ(user_id, user_name, username=user_username)
            user_biz = econ.get('businesses', {})
            biz_levels = econ.get('biz_levels', {})
            now = time.time()
            hours_passed = (now - econ.get('last_biz_collect', now)) / 3600.0
            base_profit = sum(int(BUSINESSES[b]['base_income'] * (1 + (biz_levels.get(b, 1) - 1) * 0.45) * hours_passed) for b in user_biz.keys() if b in BUSINESSES)
            if base_profit <= 0:
                bot.answer_callback_query(call.id, "⏳ Прибыль еще не накопилась! 😿", show_alert=True)
                return

            in_rest, _, _ = check_user_rest(db.get('rests', {}).get(str(chat_id), {}), user_id=user_id, user_name=user_name)
            total_profit = base_profit
            if in_rest: total_profit += int(base_profit * 0.20)

            econ['balance'] += total_profit
            econ['last_biz_collect'] = now
            mark_dirty()
            bot.answer_callback_query(call.id, f"💰 Собрано: +{total_profit} 🪙! 😻")
            render_business_view(chat_id, user_id, user_name, message_id=call.message.message_id)

        elif action_data.startswith('buy_veh_'):
            v_id = action_data.replace('buy_veh_', '')
            if v_id in VEHICLES:
                v_info = VEHICLES[v_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                cur_veh = econ.get('vehicle')
                cur_tier = VEHICLES[cur_veh]['tier'] if cur_veh in VEHICLES else -1
                new_tier = v_info.get('tier', 0)

                if cur_veh == v_id:
                    bot.answer_callback_query(call.id, "❌ Этот транспорт уже в вашем гараже! 😸", show_alert=True)
                    return
                if cur_tier > new_tier:
                    bot.answer_callback_query(call.id, f"❌ У вас уже есть более мощный транспорт! 😾", show_alert=True)
                    return
                if econ['balance'] < v_info['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {v_info['price']} 🪙! 😿", show_alert=True)
                    return

                econ['balance'] -= v_info['price']
                econ['vehicle'] = v_id
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Вы приобрели {v_info['name']}! 😻")
                render_garage_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data.startswith('buy_rod_'):
            r_id = action_data.replace('buy_rod_', '')
            if r_id in RODS:
                r_info = RODS[r_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                if econ['balance'] < r_info['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {r_info['price']} 🪙! 😿", show_alert=True)
                    return
                econ['balance'] -= r_info['price']
                econ['equipped_rod'] = r_id
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Вы экипировали {r_info['name']}! 😻")

        elif action_data.startswith('buy_bow_'):
            b_id = action_data.replace('buy_bow_', '')
            if b_id in BOWS:
                b_info = BOWS[b_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                if econ['balance'] < b_info['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {b_info['price']} 🪙! 😿", show_alert=True)
                    return
                econ['balance'] -= b_info['price']
                econ['equipped_bow'] = b_id
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Вы экипировали {b_info['name']}! 😻")

        # БАНК КНОПКИ
        elif action_data == 'bank_refresh':
            render_bank_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'bank_dep_100':
            econ = get_user_econ(user_id, user_name, username=user_username)
            if econ['balance'] < 100:
                bot.answer_callback_query(call.id, "❌ Недостаточно средств на руках! 😿", show_alert=True)
                return
            econ['balance'] -= 100
            econ['bank_deposit'] = econ.get('bank_deposit', 0) + 100
            check_achievements(user_id, user_name, 'bank_deposit', 100, chat_id, username=user_username)
            mark_dirty()
            bot.answer_callback_query(call.id, "✅ Внесено 100 🪙 на депозит! 😸")
            render_bank_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'bank_dep_all':
            econ = get_user_econ(user_id, user_name, username=user_username)
            b = econ.get('balance', 0)
            if b <= 0:
                bot.answer_callback_query(call.id, "❌ У вас нет наличных коинов! 😿", show_alert=True)
                return
            econ['balance'] = 0
            econ['bank_deposit'] = econ.get('bank_deposit', 0) + b
            check_achievements(user_id, user_name, 'bank_deposit', b, chat_id, username=user_username)
            mark_dirty()
            bot.answer_callback_query(call.id, f"✅ Внесено {b} 🪙 на депозит! 😻")
            render_bank_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'bank_wd_100':
            econ = get_user_econ(user_id, user_name, username=user_username)
            if econ.get('bank_deposit', 0) < 100:
                bot.answer_callback_query(call.id, "❌ В банке меньше 100 🪙! 😿", show_alert=True)
                return
            econ['bank_deposit'] -= 100
            econ['balance'] += 100
            mark_dirty()
            bot.answer_callback_query(call.id, "✅ Снято 100 🪙 с депозита! 😸")
            render_bank_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'bank_wd_all':
            econ = get_user_econ(user_id, user_name, username=user_username)
            dep = econ.get('bank_deposit', 0)
            if dep <= 0:
                bot.answer_callback_query(call.id, "❌ В банке нет средств! 😿", show_alert=True)
                return
            econ['bank_deposit'] = 0
            econ['balance'] += dep
            mark_dirty()
            bot.answer_callback_query(call.id, f"✅ Снят весь вклад: {dep} 🪙! 😻")
            render_bank_view(chat_id, user_id, user_name, call.message.message_id)

        # ЛОТЕРЕЯ
        elif action_data in ['buy_ticket_1', 'buy_ticket_5']:
            count = 1 if action_data == 'buy_ticket_1' else 5
            cost = count * 100
            econ = get_user_econ(user_id, user_name, username=user_username)

            if econ['balance'] < cost:
                bot.answer_callback_query(call.id, f"❌ Нужно {cost} 🪙! 😿", show_alert=True)
                return

            econ['balance'] -= cost
            lottery = db.setdefault('lottery', {'tickets': {}, 'pot': 0, 'last_draw': 0})
            t_dict = lottery.setdefault('tickets', {})
            t_dict[str(user_id)] = t_dict.get(str(user_id), 0) + count
            lottery['pot'] = lottery.get('pot', 0) + cost

            bot.answer_callback_query(call.id, f"🎟 Куплено {count} бил.! 😸")
            total_tickets = sum(t_dict.values())

            if total_tickets >= 10:
                pool = []
                for uid, t_count in t_dict.items(): pool.extend([uid] * t_count)
                winner_id = int(random.choice(pool))
                win_pot = lottery['pot']
                w_econ = get_user_econ(user_id=winner_id)
                w_econ['balance'] += win_pot
                lottery['tickets'] = {}
                lottery['pot'] = 0
                lottery['last_draw'] = time.time()
                mark_dirty()

                w_link = make_link(chat_id, w_econ.get('display_name', 'Игрок'), winner_id, ping=True)
                log_event('ЛОТЕРЕЯ: ДЖЕКПОТ', f'Победитель {w_link} сорвал джекпот <b>{win_pot} 🪙</b>!')
                bot.send_message(chat_id, f"🎉 <b>РОЗЫГРЫШ ЛОТЕРЕИ СОСТОЯЛСЯ!</b> 😻\n\n🏆 Джекпот <b>+{win_pot} Ня-коинов 🪙</b> забирает {w_link}!\nСледующий тираж уже открыт! 😸", parse_mode='HTML')
            else:
                mark_dirty()
                render_lottery_view(chat_id, user_id, user_name, call.message.message_id)

        # ЧАТ-ДРОПЫ
        elif raw_data.startswith('claim_drop_') or action_data.startswith('claim_drop_'):
            drop_id = raw_data.replace('claim_', '').split(':')[0]
            drop = active_drops.get(drop_id)
            if not drop or drop.get('claimed'):
                bot.answer_callback_query(call.id, "❌ Этот подарок уже кто-то забрал! 😿", show_alert=True)
                return

            drop['claimed'] = True
            reward = drop['reward']
            add_coins(user_id, user_name, reward, username=user_username)
            add_account_exp(user_id, user_name, 15, username=user_username)

            bot.answer_callback_query(call.id, f"🎉 Вы забрали +{reward} 🪙! 😻")
            u_link = make_link(chat_id, user_name, user_id, ping=True)
            try:
                bot.edit_message_text(
                    f"🎁 <b>ПОДАРОК ЗАБРАН!</b> 😺\n\nБыстрее всех оказался(лась) {u_link} и забрал(а) <b>+{reward} Ня-коинов 🪙</b>! 😸",
                    chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML'
                )
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        # ТРЕНИРОВКА ОПЫТА
        elif action_data == 'train_exp_btn':
            success, text_resp = train_work_exp(user_id, user_name, username=user_username)
            bot.answer_callback_query(call.id, text_resp.replace('<b>', '').replace('</b>', ''), show_alert=True)

        # РАБОТА
        elif action_data.startswith('do_job_'):
            job_id = action_data.replace('do_job_', '')
            if job_id in JOBS:
                job = JOBS[job_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                if econ.get('work_exp', 0) < job['req_exp']:
                    bot.answer_callback_query(call.id, f"❌ Нужно минимум {job['req_exp']} EXP опыта! 😿", show_alert=True)
                    return
                now = time.time()
                cooldown = 1800
                left = cooldown_text(econ.get('last_work_time', 0), cooldown, econ)
                if left:
                    bot.answer_callback_query(call.id, f"⏳ Отдохните еще: {left} 😿", show_alert=True)
                    return
                econ['last_work_time'] = now
                if random.randint(1, 100) <= job['chance']:
                    pay = random.randint(job['min_pay'], job['max_pay'])
                    econ['balance'] += pay
                    econ['work_exp'] = econ.get('work_exp', 0) + job['exp_gain']
                    add_account_exp(user_id, user_name, job['exp_gain'], username=user_username)
                    check_achievements(user_id, user_name, 'work_shifts', 1, chat_id, username=user_username)
                    mark_dirty()
                    bot.answer_callback_query(call.id, f"✅ Зарплата: +{pay} 🪙 (+{job['exp_gain']} EXP)! 😻", show_alert=True)
                    bot.send_message(chat_id, f"💼 {make_link(chat_id, user_name, user_id, ping=True)} заработал(а) <b>+{pay} 🪙</b> на должности <b>{job['name']}</b>! 😸", parse_mode='HTML')
                else:
                    econ['work_exp'] = econ.get('work_exp', 0) + 2
                    add_account_exp(user_id, user_name, 2, username=user_username)
                    mark_dirty()
                    bot.answer_callback_query(call.id, "❌ Вы ошиблись на смене! Получено +2 EXP. 😿", show_alert=True)

        # БРАКИ
        elif raw_data.startswith('m_yes_') or raw_data.startswith('m_no_'):
            prop_id = raw_data[6:].split(':')[0]
            prop = pending_marriages.get(prop_id)
            if not prop:
                bot.answer_callback_query(call.id, "❌ Предложение устарело! 😿", show_alert=True)
                return
            if user_id != prop['to_id'] and prop['to_id'] is not None:
                bot.answer_callback_query(call.id, "❌ Это предложение адресовано не вам! 😾", show_alert=True)
                return

            from_econ = get_user_econ(prop['from_id'], prop['from_tag'])
            to_econ = get_user_econ(user_id, user_name, username=user_username)

            if raw_data.startswith('m_yes_'):
                m_time = time.time()
                from_econ['marriage'] = {'partner_id': user_id, 'partner_name': user_name, 'ring': prop['ring'], 'married_at': m_time, 'vault': 0}
                to_econ['marriage'] = {'partner_id': prop['from_id'], 'partner_name': prop['from_tag'], 'ring': prop['ring'], 'married_at': m_time, 'vault': 0}
                check_achievements(prop['from_id'], prop['from_tag'], 'marriages', 1, chat_id)
                check_achievements(user_id, user_name, 'marriages', 1, chat_id, username=user_username)
                mark_dirty()
                ring_emoji = RINGS.get(prop['ring'], {}).get('emoji', '💍')
                try:
                    bot.edit_message_text(
                        f"💒 <b>Горько! Свадьба состоялась!</b> 🎉 😻\n\n{ring_emoji} {make_link(chat_id, prop['from_tag'], prop['from_id'], ping=True)} и {make_link(chat_id, user_name, user_id, ping=True)} теперь законные супруги! ❤️",
                        chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML'
                    )
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
            else:
                try:
                    bot.edit_message_text(
                        f"💔 {make_link(chat_id, user_name, user_id, ping=False)} отклонил(а) предложение руки и сердца. 😿",
                        chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML'
                    )
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
            del pending_marriages[prop_id]

        # БЛЭКДЖЕК
        elif action_data.startswith('bj_hit_') or action_data.startswith('bj_stand_'):
            game_id = action_data.split('_', 2)[2]
            game = active_bj_games.get(game_id)
            if not game or game.get('finished'):
                bot.answer_callback_query(call.id, "❌ Игра окончена! 😿", show_alert=True)
                return
            if user_id != game['user_id']:
                bot.answer_callback_query(call.id, "❌ Это не ваша игра! 😾", show_alert=True)
                return

            if action_data.startswith('bj_hit_'):
                if len(game['deck']) == 0:
                    game['deck'] = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 2
                    random.shuffle(game['deck'])
                game['p_cards'].append(game['deck'].pop())
                p_score = calculate_bj_score(game['p_cards'])
                if p_score > 21:
                    game['finished'] = True
                    try:
                        bot.edit_message_text(f"💥 <b>Перебор ({p_score})!</b> Вы проиграли <b>{game['bet']} 🪙</b>. 😿\nВаши карты: {game['p_cards']}", chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML')
                    except Exception as e: print(f"[NONFATAL ERROR] {e}")
                    del active_bj_games[game_id]
                    return
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🃏 Взять карту", callback_data=f"bj_hit_{game_id}:{user_id}"), InlineKeyboardButton("✋ Хватит", callback_data=f"bj_stand_{game_id}:{user_id}"))
                try:
                    bot.edit_message_text(f"🃏 Ваши карты: {game['p_cards']} (Сумма: <b>{p_score}</b>)\nДилер: [{game['d_cards'][0]}, ❓] 😺", chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
            else:
                game['finished'] = True
                p_score = calculate_bj_score(game['p_cards'])
                while calculate_bj_score(game['d_cards']) < 17:
                    if len(game['deck']) == 0:
                        game['deck'] = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 2
                        random.shuffle(game['deck'])
                    game['d_cards'].append(game['deck'].pop())
                d_score = calculate_bj_score(game['d_cards'])

                if d_score > 21 or p_score > d_score:
                    win = process_casino_win(int(game['bet'] * 1.8))
                    add_coins(user_id, user_name, win, username=user_username)
                    add_account_exp(user_id, user_name, 10, username=user_username)
                    res = f"🎉 <b>Вы выиграли +{win} 🪙 (x1.8)!</b> 😻"
                elif p_score == d_score:
                    add_coins(user_id, user_name, game['bet'], username=user_username)
                    res = f"🤝 <b>Ничья!</b> Ставка {game['bet']} 🪙 возвращена. 😸"
                else:
                    res = f"💸 <b>Дилер выиграл!</b> Проигрыш {game['bet']} 🪙. 😿"

                try:
                    bot.edit_message_text(f"{res}\n\n👤 Ваши карты: {game['p_cards']} ({p_score})\n🤖 Карты дилера: {game['d_cards']} ({d_score})", chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
                del active_bj_games[game_id]

        # ЦУЕФА
        elif action_data.startswith('rps_'):
            m_rps = re.match(r"^rps_([rsp])_(rps_\d+_\d+_\d+)$", action_data)
            if not m_rps:
                bot.answer_callback_query(call.id, "❌ Ошибка данных дуэли!", show_alert=True)
                return
            choice = m_rps.group(1)
            game_id = m_rps.group(2)
            game = active_rps_games.get(game_id)
            if not game or game.get('finished'):
                bot.answer_callback_query(call.id, "❌ Игра уже завершена или устарела!", show_alert=True)
                return

            if user_id == game['p1_id']:
                if game['p1_choice']:
                    bot.answer_callback_query(call.id, "Вы уже сделали выбор! Ожидаем соперника. ⏳", show_alert=True)
                    return
                game['p1_choice'] = choice
            elif user_id == game['p2_id']:
                if game['p2_choice']:
                    bot.answer_callback_query(call.id, "Вы уже сделали выбор! Ожидаем соперника. ⏳", show_alert=True)
                    return
                game['p2_choice'] = choice
            else:
                bot.answer_callback_query(call.id, "❌ Вы не являетесь участником этой дуэли! 😾", show_alert=True)
                return

            bot.answer_callback_query(call.id, "✅ Ваш выбор принят! 😸")

            if game['p1_choice'] and game['p2_choice']:
                game['finished'] = True
                c_map = {'r': '🪨 Камень', 's': '✂️ Ножницы', 'p': '📄 Бумага'}
                c1, c2 = game['p1_choice'], game['p2_choice']
                bet = game['bet']
                total_pot = bet * 2
                
                if c1 == c2:
                    add_coins(game['p1_id'], game['p1_tag'], bet)
                    add_coins(game['p2_id'], game['p2_tag'], bet)
                    res = "🤝 <b>Ничья!</b> Ставки возвращены обоим игрокам. 😸"
                elif (c1 == 'r' and c2 == 's') or (c1 == 's' and c2 == 'p') or (c1 == 'p' and c2 == 'r'):
                    win_val = int(total_pot * 0.95)
                    add_coins(game['p1_id'], game['p1_tag'], win_val)
                    res = f"🏆 Победил(а) {make_link(chat_id, game['p1_tag'], game['p1_id'], ping=True)}! (+{win_val} 🪙) 😻"
                else:
                    win_val = int(total_pot * 0.95)
                    add_coins(game['p2_id'], game['p2_tag'], win_val)
                    res = f"🏆 Победил(а) {make_link(chat_id, game['p2_tag'], game['p2_id'], ping=True)}! (+{win_val} 🪙) 😻"

                try:
                    bot.edit_message_text(
                        f"✌️ <b>ИТОГИ ДУЭЛИ ЦУ-Е-ФА:</b> 😺\n──────────────────────\n"
                        f"• {game['p1_tag']}: {c_map[c1]}\n"
                        f"• {game['p2_tag']}: {c_map[c2]}\n\n{res}",
                        chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML'
                    )
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
                active_rps_games.pop(game_id, None)

        # СНЯТИЕ РЕСТА
        elif action_data == 'rest_remove_menu':
            if not is_admin(chat_id, user_id):
                bot.answer_callback_query(call.id, "❌ Только для администраторов чата!", show_alert=True)
                return

            chat_rests = db.get('rests', {}).get(str(chat_id), {})
            if not chat_rests:
                bot.answer_callback_query(call.id, "🌴 В ресте никого нет!", show_alert=True)
                return

            markup = InlineKeyboardMarkup(row_width=1)
            for r_key, info in chat_rests.items():
                u_name = info.get('user_name', r_key)
                markup.add(InlineKeyboardButton(f"❌ Снять: {u_name}", callback_data=f"del_rest_user_{r_key}:{user_id}"))
            markup.add(InlineKeyboardButton("🔙 Назад", callback_data=f"rest_cancel_menu:{user_id}"))

            try:
                bot.edit_message_text(
                    "🗑 <b>ВЫБЕРИТЕ ПОЛЬЗОВАТЕЛЯ ДЛЯ СНЯТИЯ С РЕСТА:</b> 😺\n──────────────────────\nНажмите на кнопку с именем нужного человека:",
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    reply_markup=markup,
                    parse_mode='HTML'
                )
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('del_rest_user_'):
            if not is_admin(chat_id, user_id):
                bot.answer_callback_query(call.id, "❌ Только для администраторов чата!", show_alert=True)
                return

            target_r_key = action_data.replace('del_rest_user_', '')
            str_chat = str(chat_id)
            chat_rests = db.get('rests', {}).get(str_chat, {})

            if target_r_key in chat_rests:
                info = chat_rests.pop(target_r_key)
                u_name = info.get('user_name', target_r_key)
                t_uid = info.get('user_id')
                
                add_to_history(str_chat, u_name, 'Снят', 'Досрочно по кнопке админом', t_uid, "Снят рест (кнопка)")
                mark_dirty()

                u_link = make_link(chat_id, u_name, t_uid, ping=True)
                log_event('РЕСТ СНЯТ (КНОПКА)', f'Чат: <code>{chat_id}</code>\nАдмин: ID:{user_id}\nПользователь: {u_link}')
                bot.answer_callback_query(call.id, f"✅ Рест с {u_name} снят!")
                try:
                    bot.edit_message_text(f"🗑 Рест с {u_link} успешно снят по кнопке! 😺", chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
            else:
                bot.answer_callback_query(call.id, "❌ Пользователь уже не в ресте!", show_alert=True)

        elif action_data == 'rest_cancel_menu':
            chat_rests = db.get('rests', {}).get(str(chat_id), {})
            if not chat_rests:
                try: bot.edit_message_text('🌴 В данный момент никто не находится в ресте. 😸', chat_id=chat_id, message_id=call.message.message_id)
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
                return

            resp = '📋 <b>СПИСОК АКТИВНЫХ РЕСТОВ:</b> 😺\n──────────────────────\n'
            for r_key, info in chat_rests.items():
                u_name = info.get('user_name', r_key)
                u_id = info.get('user_id')
                resp += f"• {make_link(chat_id, u_name, u_id, ping=False)} — {info['duration']} (Причина: {info.get('reason', 'Не указана')})\n"
            resp += '──────────────────────'

            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🗑 Снять рест (Выбрать)", callback_data=f"rest_remove_menu:{user_id}"))
            try: bot.edit_message_text(resp, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        # НАСТРОЙКИ
        elif action_data == 'set_max_days':
            if not is_admin(chat_id, user_id): return
            sett = get_chat_settings(chat_id)
            sett['max_days'] = None
            mark_dirty()
            bot.answer_callback_query(call.id, '✅ Лимит реста полностью отключён! 😸')
            render_settings_view(chat_id, user_id=user_id, message_id=call.message.message_id)

        elif action_data == 'toggle_rp':
            if not is_admin(chat_id, user_id): return
            sett = get_chat_settings(chat_id)
            sett['rp_enabled'] = not sett.get('rp_enabled', True)
            mark_dirty()
            bot.answer_callback_query(call.id, f"🎭 РП-команды {'включены' if sett['rp_enabled'] else 'выключены'}!")
            render_settings_view(chat_id, user_id=user_id, message_id=call.message.message_id)

        elif action_data == 'toggle_flood':
            if not is_admin(chat_id, user_id): return
            sett = get_chat_settings(chat_id)
            sett['flood_protection'] = not sett.get('flood_protection', False)
            mark_dirty()
            bot.answer_callback_query(call.id, f"🛡 Антифлуд {'включён' if sett['flood_protection'] else 'выключен'}!")
            render_settings_view(chat_id, user_id=user_id, message_id=call.message.message_id)

        elif action_data == 'toggle_reactions':
            if not is_admin(chat_id, user_id): return
            sett = get_chat_settings(chat_id)
            sett['auto_reactions'] = not sett.get('auto_reactions', True)
            mark_dirty()
            bot.answer_callback_query(call.id, f"✨ Авто-реакции {'включены' if sett['auto_reactions'] else 'выключены'}!")
            render_settings_view(chat_id, user_id=user_id, message_id=call.message.message_id)

        elif action_data == 'toggle_welcome':
            if not is_admin(chat_id, user_id): return
            sett = get_chat_settings(chat_id)
            sett['welcome_enabled'] = not sett.get('welcome_enabled', True)
            mark_dirty()
            bot.answer_callback_query(call.id, f"👋 Приветствия {'включены' if sett['welcome_enabled'] else 'выключены'}!")
            render_settings_view(chat_id, user_id=user_id, message_id=call.message.message_id)

        elif action_data == 'set_remind_time':
            if not is_admin(chat_id, user_id): return
            sett = get_chat_settings(chat_id)
            opts = [10, 60, 1440]
            next_opt = opts[(opts.index(sett.get('remind_minutes', 60)) + 1) % len(opts)]
            sett['remind_minutes'] = next_opt
            mark_dirty()
            bot.answer_callback_query(call.id, f'✅ Напоминание установлено за {next_opt} мин! 😸')
            render_settings_view(chat_id, user_id=user_id, message_id=call.message.message_id)

        # ПАГИНАЦИЯ МАГАЗИНА
        elif action_data.startswith('shop_cat_badges_'):
            page = int(action_data.replace('shop_cat_badges_', ''))
            items_per_page = 6
            items = list(BADGES.items())
            total_pages = (len(items) + items_per_page - 1) // items_per_page
            
            start_idx = page * items_per_page
            end_idx = start_idx + items_per_page
            current_items = items[start_idx:end_idx]

            lines = ["✨ <b>КАТАЛОГ ЗНАЧКОВ ДЛЯ ПРОФИЛЯ</b> 😺", "──────────────────────", "<i>Значок отображается рядом с вашим ником в чате!</i> 😸\n"]
            for b_k, b_v in current_items:
                lines.append(f"• {b_v['emoji']} <b>{b_v['name']}</b> — <code>{b_v['price']} 🪙</code>")
            lines.append(f"\nСтраница {page+1} из {total_pages}")
            lines.append("──────────────────────")

            markup = InlineKeyboardMarkup(row_width=3)
            btns = [InlineKeyboardButton(f"{b_v['emoji']} {b_v['price']} 🪙", callback_data=f"buy_badge_{b_k}:{user_id}") for b_k, b_v in current_items]
            markup.add(*btns)
            
            nav_row = []
            if page > 0: nav_row.append(InlineKeyboardButton('⬅️ Назад', callback_data=f'shop_cat_badges_{page-1}:{user_id}'))
            if page < total_pages - 1: nav_row.append(InlineKeyboardButton('Вперед ➡️', callback_data=f'shop_cat_badges_{page+1}:{user_id}'))
            if nav_row: markup.add(*nav_row)
            
            markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data=f'shop_main:{user_id}'))
            try: bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('shop_cat_titles_'):
            page = int(action_data.replace('shop_cat_titles_', ''))
            items_per_page = 5
            items = list(TITLES.items())
            total_pages = (len(items) + items_per_page - 1) // items_per_page
            
            start_idx = page * items_per_page
            end_idx = start_idx + items_per_page
            current_items = items[start_idx:end_idx]

            lines = ["👑 <b>КАТАЛОГ ТИТУЛОВ С ПАССИВНЫМИ БАФФАМИ</b> 😺", "──────────────────────", "<i>Каждый титул дает постоянный бонус к удаче или доходу!</i> 😸\n"]
            for t_k, t_v in current_items:
                lines.append(f"• <b>{t_v['text']}</b> — <code>{t_v['price']} 🪙</code> ({t_v['desc']})")
            lines.append(f"\nСтраница {page+1} из {total_pages}")
            lines.append("──────────────────────")

            markup = InlineKeyboardMarkup(row_width=1)
            for t_key, t_info in current_items:
                markup.add(InlineKeyboardButton(f"{t_info['text']} • {t_info['price']} 🪙", callback_data=f"buy_title_{t_key}:{user_id}"))
            
            if page == 0:
                markup.add(InlineKeyboardButton('🌟 Сертификат Своего Титула (15к 🪙)', callback_data=f'buy_cert_custom_title:{user_id}'))
                
            nav_row = []
            if page > 0: nav_row.append(InlineKeyboardButton('⬅️ Назад', callback_data=f'shop_cat_titles_{page-1}:{user_id}'))
            if page < total_pages - 1: nav_row.append(InlineKeyboardButton('Вперед ➡️', callback_data=f'shop_cat_titles_{page+1}:{user_id}'))
            if nav_row: markup.add(*nav_row)
            
            markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data=f'shop_main:{user_id}'))
            try: bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('shop_cat_pets_'):
            page = int(action_data.replace('shop_cat_pets_', ''))
            items_per_page = 4
            items = list(PETS_DATA.items())
            total_pages = (len(items) + items_per_page - 1) // items_per_page
            
            start_idx = page * items_per_page
            end_idx = start_idx + items_per_page
            current_items = items[start_idx:end_idx]

            lines = ["🐾 <b>ЗОМАГАЗИН: ПИТОМЦЫ 2.0</b> 😺", "──────────────────────", "<i>Питомцы помогают в охоте, рыбалке, и дают бонусы!</i> 😸\n"]
            for p_k, p_v in current_items:
                lines.append(f"• <b>{p_v['name']}</b> — <code>{p_v['price']} 🪙</code>\n  <i>{p_v['desc']}</i>")
            lines.append(f"\nСтраница {page+1} из {total_pages}")
            lines.append("──────────────────────")

            markup = InlineKeyboardMarkup(row_width=2)
            btns = [InlineKeyboardButton(f"{p['short']} — {p['price']} 🪙", callback_data=f"buy_pet_{p_id}:{user_id}") for p_id, p in current_items]
            for i in range(0, len(btns), 2):
                markup.add(*btns[i:i+2])
            
            nav_row = []
            if page > 0: nav_row.append(InlineKeyboardButton('⬅️ Назад', callback_data=f'shop_cat_pets_{page-1}:{user_id}'))
            if page < total_pages - 1: nav_row.append(InlineKeyboardButton('Вперед ➡️', callback_data=f'shop_cat_pets_{page+1}:{user_id}'))
            if nav_row: markup.add(*nav_row)

            markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data=f'shop_main:{user_id}'))
            try: bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data == 'buy_cert_custom_title':
            econ = get_user_econ(user_id, user_name, username=user_username)
            if econ.get('has_custom_title_cert', False):
                bot.answer_callback_query(call.id, '❌ Сертификат уже куплен! Введите /custom_title', show_alert=True)
                return
            if econ['balance'] < CUSTOM_TITLE_CERT_PRICE:
                bot.answer_callback_query(call.id, f'❌ Нужно {CUSTOM_TITLE_CERT_PRICE} 🪙! 😿', show_alert=True)
                return
            econ['balance'] -= CUSTOM_TITLE_CERT_PRICE
            econ['has_custom_title_cert'] = True
            mark_dirty()
            bot.answer_callback_query(call.id, '🎉 Сертификат приобретен! Установите титул: /custom_title Ваш Титул 😻', show_alert=True)

        elif action_data.startswith('buy_ring_'):
            r_id = action_data.replace('buy_ring_', '')
            if r_id in RINGS:
                r_info = RINGS[r_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                if econ['balance'] < r_info['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {r_info['price']} 🪙! 😿", show_alert=True)
                    return
                econ['balance'] -= r_info['price']
                econ.setdefault('rings', []).append(r_id)
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Вы приобрели {r_info['name']}! 😻", show_alert=True)

        elif action_data.startswith('buy_title_'):
            title_key = action_data.replace('buy_title_', '')
            if title_key in TITLES:
                item = TITLES[title_key]
                econ = get_user_econ(user_id, user_name, username=user_username)
                if title_key in econ.get('titles', []):
                    bot.answer_callback_query(call.id, '❌ Титул уже куплен! 😾', show_alert=True)
                    return
                if econ['balance'] < item['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {item['price']} 🪙! 😿", show_alert=True)
                    return
                econ['balance'] -= item['price']
                econ.setdefault('titles', []).append(title_key)
                econ['active_title'] = title_key
                econ['custom_title'] = None
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Куплен титул {item['text']}! 😻", show_alert=True)
                send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)

        elif action_data.startswith('buy_badge_'):
            badge_key = action_data.replace('buy_badge_', '')
            if badge_key in BADGES:
                item = BADGES[badge_key]
                econ = get_user_econ(user_id, user_name, username=user_username)
                if item['emoji'] in econ.get('inventory', []):
                    bot.answer_callback_query(call.id, f"Значок {item['emoji']} уже есть! 😾", show_alert=True)
                    return
                if econ['balance'] < item['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {item['price']} 🪙! 😿", show_alert=True)
                    return
                econ['balance'] -= item['price']
                econ.setdefault('inventory', []).append(item['emoji'])
                econ['badge'] = item['emoji']
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Куплен значок {item['emoji']}! 😻", show_alert=True)

        elif action_data.startswith('buy_pet_'):
            pet_id = action_data.replace('buy_pet_', '')
            if pet_id in PETS_DATA:
                p_data = PETS_DATA[pet_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                if pet_id == 'vip_griffin':
                    # Грифон — Stars-only. Нулевой price в каталоге никогда не означает бесплатную выдачу.
                    if 'pet_griffin' not in econ.setdefault('paid_stars_items', []):
                        bot.answer_callback_query(call.id, "❌ Королевский Грифон доступен только после успешной оплаты 3 ⭐️ в Stars-магазине.", show_alert=True)
                        return
                else:
                    if econ['balance'] < p_data['price']:
                        bot.answer_callback_query(call.id, f"❌ Нужно {p_data['price']} 🪙! 😿", show_alert=True)
                        return
                    econ['balance'] -= p_data['price']
                econ['pet'] = {'id': pet_id, 'name': p_data['name'], 'luck_bonus': p_data['luck_bonus'], 'hunger': 100, 'cleanliness': 100, 'pet_exp': 0, 'last_update': time.time()}
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Вы завели питомца {p_data['name']}! 😻", show_alert=True)
                render_pet_view(chat_id, user_id, user_name, call.message.message_id)

        # УПРАВЛЕНИЕ ПРОФИЛЕМ
        elif action_data.startswith('set_title_'):
            title_key = action_data.replace('set_title_', '')
            econ = get_user_econ(user_id, user_name, username=user_username)
            if title_key in econ.get('titles', []) and title_key in TITLES:
                econ['active_title'] = title_key
                econ['custom_title'] = None
                mark_dirty()
                bot.answer_callback_query(call.id, f"✅ Надет титул {TITLES[title_key]['text']}! 😸")
                send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)

        elif action_data == 'remove_title':
            econ = get_user_econ(user_id, user_name, username=user_username)
            econ['active_title'] = None
            econ['custom_title'] = None
            mark_dirty()
            bot.answer_callback_query(call.id, '❌ Титул снят! 😿', show_alert=True)
            send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)

        elif action_data.startswith('set_badge_'):
            selected_emoji = action_data.replace('set_badge_', '')
            econ = get_user_econ(user_id, user_name, username=user_username)
            if selected_emoji in econ.get('inventory', []):
                econ['badge'] = selected_emoji
                mark_dirty()
                bot.answer_callback_query(call.id, f"✅ Надет значок {selected_emoji}! 😸")
                send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)

        elif action_data == 'remove_badge':
            econ = get_user_econ(user_id, user_name, username=user_username)
            econ['badge'] = None
            mark_dirty()
            bot.answer_callback_query(call.id, "❌ Значок снят! 😿", show_alert=True)
            send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)

    except Exception as e:
        print(f"[CALLBACK ERROR] Исключение в callback: {e}")
        try: bot.answer_callback_query(call.id, "⚠️ Произошла ошибка!", show_alert=False)
        except Exception as e: print(f"[NONFATAL ERROR] {e}")


# ---------------------------------------------------------
# ОБРАБОТЧИКИ ОПЛАТЫ TELEGRAM STARS (PRE-CHECKOUT & SUCCESS)
# ---------------------------------------------------------
def validate_stars_payload(payload, amount, buyer_id):
    try:
        raw_payload = str(payload or '')
        if raw_payload.startswith('gift2|'):
            g = raw_payload.split('|')
            if len(g) != 5:
                return False, 'Некорректный подарочный payload.'
            _, gift_kind, item_key, target_raw, payload_buyer_raw = g
            catalogs = {'coins': STARS_COIN_PACKS, 'pass': STARS_VIP_PASS, 'cosm': STARS_COSMETICS}
            item = catalogs.get(gift_kind, {}).get(item_key)
            if gift_kind == 'cosm' and item is None:
                special = {'bp_premium': ('🎃 Премиум Хеллоуин Pass', 2), 'custom_title': ('🌟 Сертификат Кастомного Титула', 2), 'pet_griffin': ('🐱 Королевский Грифон', 3)}
                if item_key in special:
                    n, st = special[item_key]; item = {'name': n, 'stars': st}
            if not item:
                return False, 'Товар подарка не найден.'
            if int(amount) != int(item['stars']):
                return False, 'Неверная сумма товара.'
            try:
                target_id = int(target_raw); payload_buyer = int(payload_buyer_raw)
            except ValueError:
                return False, 'Некорректный пользователь в подарке.'
            if payload_buyer != int(buyer_id):
                return False, 'Плательщик не совпадает с владельцем счёта.'
            if target_id == payload_buyer:
                return False, 'Нельзя подарить товар самому себе.'
            target_econ = get_user_econ(user_id=target_id)
            if gift_kind == 'pass':
                err = stars_purchase_error(target_econ, 'vippass', item_key)
                if err: return False, 'Получатель уже владеет этим VIP.'
            elif gift_kind == 'cosm':
                if item_key == 'bp_premium' and target_econ.get('bp_premium'): return False, 'Получатель уже владеет Премиум Pass.'
                if item_key == 'custom_title' and target_econ.get('has_custom_title_cert'): return False, 'Получатель уже владеет сертификатом.'
                if item_key == 'pet_griffin' and 'pet_griffin' in target_econ.get('paid_stars_items', []): return False, 'Получатель уже владеет Грифоном.'
                if item_key in STARS_COSMETICS:
                    err = stars_purchase_error(target_econ, 'cosm', item_key)
                    if err: return False, 'Получатель уже владеет этим Stars-предметом.'
            return True, ''

        parts = raw_payload.split(':')
        key = parts[0]
        expected = None
        payload_buyer = None
        if key.startswith('coinpack_'):
            item = STARS_COIN_PACKS.get(key.replace('coinpack_', ''))
            expected = item.get('stars') if item else None
            payload_buyer = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        elif key.startswith('vippass_'):
            item = STARS_VIP_PASS.get(key.replace('vippass_', ''))
            expected = item.get('stars') if item else None
            payload_buyer = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        elif key.startswith('cosm_'):
            item = STARS_COSMETICS.get(key.replace('cosm_', ''))
            expected = item.get('stars') if item else None
            payload_buyer = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        elif key.startswith('bpprem_'):
            expected = 2
            payload_buyer = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            # Не разрешаем даже выставлять новый счёт за вечный Pass, если он уже есть.
            if payload_buyer is not None:
                buyer_econ = get_user_econ(user_id=payload_buyer)
                if buyer_econ.get('bp_premium'):
                    return False, 'Премиум Pass уже куплен.'
        elif key.startswith('gift2:'):
            g = key.split(':')
            if len(g) != 5:
                return False, 'Некорректный подарочный payload.'
            _, gift_kind, item_key, target_raw, buyer_raw = g
            catalogs = {'coins': STARS_COIN_PACKS, 'pass': STARS_VIP_PASS, 'cosm': STARS_COSMETICS}
            item = catalogs.get(gift_kind, {}).get(item_key)
            if gift_kind == 'cosm' and item is None:
                special = {'bp_premium': ('🎃 Премиум Хеллоуин Pass', 2), 'custom_title': ('🌟 Сертификат Кастомного Титула', 2), 'pet_griffin': ('🐱 Королевский Грифон', 3)}
                if item_key in special:
                    n, st = special[item_key]; item = {'name': n, 'stars': st}
            expected = item.get('stars') if item else None
            target_id = int(target_raw) if target_raw.isdigit() else None
            payload_buyer = int(buyer_raw) if buyer_raw.isdigit() else None
        else:
            return False, 'Неизвестный товар.'
        if expected is None or int(amount) != int(expected):
            return False, 'Неверная сумма товара.'
        if payload_buyer is not None and int(payload_buyer) != int(buyer_id):
            return False, 'Плательщик не совпадает с владельцем счёта.'

        # Защита от повторной покупки вечных предметов даже по старому счёту.
        buyer_econ = get_user_econ(user_id=buyer_id)
        if key.startswith('vippass_'):
            item_key = key.replace('vippass_', '', 1)
            err = stars_purchase_error(buyer_econ, 'vippass', item_key)
            if err:
                return False, err.replace('❌ ', '')
        elif key.startswith('cosm_'):
            item_key = key.replace('cosm_', '', 1)
            err = stars_purchase_error(buyer_econ, 'cosm', item_key)
            if err:
                return False, err.replace('❌ ', '')
        elif key.startswith('gift2:') and target_id:
            # Для подарков проверяем владение именно получателя.
            target_econ = get_user_econ(user_id=target_id)
            if actual.startswith('pass_'):
                item_key = actual.replace('pass_', '', 1)
                err = stars_purchase_error(target_econ, 'vippass', item_key)
                if err:
                    return False, 'Получатель уже владеет этим вечным VIP.'
            elif actual == 'bp_premium':
                if target_econ.get('bp_premium'):
                    return False, 'Получатель уже владеет Премиум Pass.'
            elif actual in STARS_COSMETICS:
                err = stars_purchase_error(target_econ, 'cosm', actual)
                if err:
                    return False, 'Получатель уже владеет этим вечным Stars-предметом.'
        return True, ''
    except Exception:
        return False, 'Некорректный платёжный payload.'

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_stars_pre_checkout(pre_checkout_query):
    try:
        ok, reason = validate_stars_payload(pre_checkout_query.invoice_payload, pre_checkout_query.total_amount, pre_checkout_query.from_user.id)
        bot.answer_pre_checkout_query(pre_checkout_query.id, ok=ok, error_message=None if ok else reason)
    except Exception as e:
        print(f"[PRE-CHECKOUT ERROR] {e}")
        try: bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message='Платёж не прошёл проверку.')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")

@bot.message_handler(content_types=['successful_payment'])
def process_stars_successful_payment(message):
    try:
        sp = message.successful_payment
        payload = sp.invoice_payload
        stars_amount = sp.total_amount

        ok, reason = validate_stars_payload(payload, stars_amount, message.from_user.id)
        if not ok:
            print(f"[STARS SECURITY] rejected payment: {reason}; payload={payload!r}")
            return

        # Telegram can retry delivery of an update. Process each successful
        # payment only once using its unique charge id.
        charge_id = getattr(sp, 'telegram_payment_charge_id', None)
        processed = db.setdefault('processed_stars_charges', [])
        if charge_id and charge_id in processed:
            print(f"[STARS] duplicate payment ignored: {charge_id}")
            return
        if charge_id:
            processed.append(charge_id)
            mark_dirty()
            # Keep the persistent list bounded.
            if len(processed) > 10000:
                del processed[:-10000]
        chat_id = message.chat.id
        
        parts = payload.split(':')
        prod_type_key = parts[0]
        if payload.startswith('gift2|'):
            gift_parts = payload.split('|')
            if len(gift_parts) != 5:
                print(f'[STARS SECURITY] malformed gift2 payload: {payload!r}')
                return
            buyer_id = int(gift_parts[4])
        elif prod_type_key.startswith('gift_'):
            buyer_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else message.from_user.id
        else:
            buyer_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else message.from_user.id
        
        u = message.from_user
        user_name = (f"{u.first_name or ''} {u.last_name or ''}").strip() or u.username or "Пользователь"
        econ = get_user_econ(buyer_id, user_name, username=u.username)
        
        user_link = make_link(chat_id, user_name, buyer_id, ping=True)

        # Повторно не выдаём вечные подарки/покупки, даже если платёж создан до
        # предыдущей покупки. Монеты и временный VIP остаются многократными.
        if prod_type_key.startswith('vippass_'):
            _pk = prod_type_key.replace('vippass_', '', 1)
            _err = stars_purchase_error(econ, 'vippass', _pk)
            if _err:
                print(f"[STARS SECURITY] permanent VIP replay blocked: {_pk} buyer={buyer_id}")
                return
        elif prod_type_key.startswith('cosm_'):
            _ck = prod_type_key.replace('cosm_', '', 1)
            _err = stars_purchase_error(econ, 'cosm', _ck)
            if _err:
                print(f"[STARS SECURITY] permanent cosmetic replay blocked: {_ck} buyer={buyer_id}")
                return
        elif prod_type_key.startswith('bpprem_') and econ.get('bp_premium'):
            print(f"[STARS SECURITY] premium pass replay blocked: buyer={buyer_id}")
            return

        # Только после успешной проверки товара учитываем Stars в статистике поддержки.
        econ['stars_donated'] = econ.get('stars_donated', 0) + stars_amount

        # 0. Проверка на подарок другому человеку
        is_gift = payload.startswith('gift2|') or prod_type_key.startswith('gift_')
        if is_gift:
            if payload.startswith('gift2|'):
                gift_parts = payload.split('|')
                _, gift_kind, actual_prod, target_raw, actual_buyer_raw = gift_parts
            else:
                gift_kind = None
                actual_prod = prod_type_key.replace('gift_', '', 1)
                target_raw = parts[1]
                actual_buyer_raw = parts[2] if len(parts) > 2 else str(buyer_id)
            target_id = int(target_raw)
            actual_buyer_id = int(actual_buyer_raw)

            target_econ = get_user_econ(user_id=target_id)
            target_name = target_econ.get('display_name', f"ID:{target_id}")
            t_link = make_link(chat_id, target_name, target_id, ping=True)

            # Начисление подарка
            if actual_prod in STARS_COIN_PACKS:
                pack = STARS_COIN_PACKS[actual_prod]
                target_econ['balance'] += pack['coins']
                prod_name = pack['name']
            elif actual_prod in STARS_VIP_PASS:
                v_item = STARS_VIP_PASS[actual_prod]
                days = v_item['days']
                if days == -1: target_econ['vip_forever'] = True
                else: target_econ['vip_until'] = max(time.time(), target_econ.get('vip_until', 0)) + (days * 86400)
                prod_name = v_item['name']
            elif actual_prod == 'bp_premium':
                if target_econ.get('bp_premium'):
                    print(f"[STARS SECURITY] duplicate gifted premium pass blocked: target={target_id}")
                    return
                target_econ['bp_premium'] = True
                target_econ.setdefault('paid_stars_items', [])
                if 'bp_premium' not in target_econ['paid_stars_items']:
                    target_econ['paid_stars_items'].append('bp_premium')
                prod_name = "🎃 Премиум Хеллоуин Pass"
            elif actual_prod == 'custom_title':
                target_econ['has_custom_title_cert'] = True
                prod_name = "🌟 Сертификат Кастомного Титула"
            elif actual_prod == 'pet_griffin':
                p_info = PETS_DATA['vip_griffin']
                target_econ.setdefault('paid_stars_items', [])
                if 'pet_griffin' not in target_econ['paid_stars_items']:
                    target_econ['paid_stars_items'].append('pet_griffin')
                target_econ['pet'] = {'id': 'vip_griffin', 'name': p_info['name'], 'luck_bonus': p_info['luck_bonus'], 'hunger': 100, 'cleanliness': 100, 'pet_exp': 0, 'last_update': time.time()}
                prod_name = p_info['name']
            elif actual_prod in STARS_COSMETICS:
                cosm = STARS_COSMETICS[actual_prod]
                c_type = cosm.get('type')
                if c_type == 'title_cert':
                    target_econ['has_custom_title_cert'] = True
                elif c_type == 'theme':
                    theme_id = cosm.get('theme_id')
                    purchased = target_econ.setdefault('purchased_themes', ['default'])
                    if theme_id and theme_id not in purchased:
                        purchased.append(theme_id)
                    if theme_id:
                        target_econ['profile_theme'] = theme_id
                elif c_type == 'badge':
                    badge_emoji = cosm.get('emoji')
                    if badge_emoji:
                        inv = target_econ.setdefault('inventory', [])
                        if badge_emoji not in inv:
                            inv.append(badge_emoji)
                        target_econ['badge'] = badge_emoji
                elif c_type == 'pet':
                    pet_id = cosm.get('pet_id')
                    if pet_id in PETS_DATA:
                        target_econ.setdefault('paid_stars_items', [])
                        if actual_prod not in target_econ['paid_stars_items']:
                            target_econ['paid_stars_items'].append(actual_prod)
                        p_info = PETS_DATA[pet_id]
                        target_econ['pet'] = {'id': pet_id, 'name': p_info['name'], 'luck_bonus': p_info['luck_bonus'], 'hunger': 100, 'cleanliness': 100, 'pet_exp': 0, 'last_update': time.time()}
                prod_name = cosm.get('name', actual_prod)
            else:
                # Never silently convert an unknown paid product into coins.
                print(f"[STARS] unknown gift product: {actual_prod}")
                prod_name = f"неизвестный товар {actual_prod}"

            mark_dirty()
            log_event('STARS ПОДАРОК', f'{user_link} подарил {t_link} товар: {prod_name} за {stars_amount} ⭐️!')
            bot.send_message(
                chat_id,
                f"🎁⭐️ <b>РОСКОШНЫЙ ПОДАРОК ЗА ЗВЁЗДЫ!</b> 😻\n"
                f"──────────────────────\n"
                f"👤 Щедрый даритель: {user_link}\n"
                f"🎉 Счастливый получатель: {t_link}\n"
                f"📦 Подарок: <b>{prod_name}</b> ({stars_amount} ⭐️)!\n"
                f"──────────────────────\n"
                f"<i>Огромное спасибо за поддержку сервера и доброту!</i> 😸",
                parse_mode='HTML'
            )
            return

        # Покупка bp_premium себе
        if prod_type_key.startswith('bpprem_') or prod_type_key == 'cosm_bp_premium':
            econ['bp_premium'] = True
            econ.setdefault('paid_stars_items', [])
            if 'bp_premium' not in econ['paid_stars_items']:
                econ['paid_stars_items'].append('bp_premium')
            mark_dirty()
            log_event('STARS BP PREM', f'{user_link} активировал Премиум Хеллоуин Pass!')
            bot.reply_to(message, f"🎃 <b>ПРЕМИУМ ХЕЛЛОУИН PASS АКТИВИРОВАН!</b> 😻\nТеперь вам доступны все премиум-награды, Тыквокот и Тёмная тема в <code>/pass</code>!", parse_mode='HTML')
            return

        # 1. Покупка пакета коинов
        if prod_type_key.startswith('coinpack_'):
            pack_id = prod_type_key.replace('coinpack_', '')
            if pack_id in STARS_COIN_PACKS:
                pack = STARS_COIN_PACKS[pack_id]
                coins_to_add = pack['coins']
                econ['balance'] += coins_to_add
                add_account_exp(buyer_id, user_name, int(stars_amount * 50), username=u.username)
                mark_dirty()
                
                log_event('STARS ПОКУПКА', f'Игрок {user_link} приобрёл {pack["name"]} за {stars_amount} ⭐️!')
                success_msg = (
                    f"🎉 <b>ОПЛАТА УСПЕШНО ПРОШЛА!</b> 😻\n"
                    f"──────────────────────\n"
                    f"👤 Покупатель: {user_link}\n"
                    f"⭐️ Списано: <b>{stars_amount} Звёзд</b>\n"
                    f"💰 Начислено: <b>+{coins_to_add:,} Ня-коинов 🪙</b>!\n"
                    f"💵 Новый баланс: <b>{econ['balance']:,} 🪙</b>\n"
                    f"──────────────────────\n"
                    f"<i>Огромное спасибо за поддержку сервера и бота!</i> 😸"
                )
                bot.reply_to(message, success_msg, parse_mode='HTML')
                return

        # 2. Покупка VIP Nya Pass
        elif prod_type_key.startswith('vippass_'):
            pass_id = prod_type_key.replace('vippass_', '')
            if pass_id in STARS_VIP_PASS:
                item = STARS_VIP_PASS[pass_id]
                days = item['days']
                now_ts = time.time()
                
                if days == -1:
                    econ['vip_forever'] = True
                    dur_str = "НАВСЕГДА 👑"
                else:
                    cur_vip = max(now_ts, econ.get('vip_until', 0))
                    econ['vip_until'] = cur_vip + (days * 86400)
                    exp_date = datetime.fromtimestamp(econ['vip_until'], tz=MSK_TZ).strftime('%d.%m.%Y %H:%M')
                    dur_str = f"на {days} дней (до {exp_date})"
                    
                add_account_exp(buyer_id, user_name, int(stars_amount * 100), username=u.username)
                mark_dirty()
                
                log_event('STARS VIP PASS', f'Игрок {user_link} активировал VIP Nya Pass ({dur_str}) за {stars_amount} ⭐️!')
                success_msg = (
                    f"👑 <b>VIP NYA PASS АКТИВИРОВАН!</b> 😻\n"
                    f"──────────────────────\n"
                    f"👤 Владелец: {user_link}\n"
                    f"⏳ Срок действия: <b>{dur_str}</b>\n"
                    f"⭐️ Ваши привилегии:\n"
                    f"• ⚡️ -30% ко всем кулдаунам бота\n"
                    f"• 🎁 Удвоение часового бонуса /bonus (x2.0)\n"
                    f"• 🛡 100% защита от карманных краж и ограблений\n"
                    f"• 🌟 VIP отметка в профиле\n"
                    f"──────────────────────\n"
                    f"<i>Приятной игры с максимальным комфортом!</i> 😸"
                )
                bot.reply_to(message, success_msg, parse_mode='HTML')
                return

        # 3. Покупка эксклюзивной косметики
        elif prod_type_key.startswith('cosm_'):
            cosm_id = prod_type_key.replace('cosm_', '')
            if cosm_id in STARS_COSMETICS:
                cosm = STARS_COSMETICS[cosm_id]
                c_type = cosm['type']
                
                if c_type == 'title_cert':
                    econ['has_custom_title_cert'] = True
                    mark_dirty()
                    log_event('STARS ТИТУЛ', f'Игрок {user_link} купил сертификат кастомного титула за {stars_amount} ⭐️!')
                    bot.reply_to(
                        message,
                        f"🌟 <b>СЕРТИФИКАТ ТИТУЛА ПОЛУЧЕН!</b> 😻\n"
                        f"──────────────────────\n"
                        f"{user_link}, теперь вы можете установить любой личный титул командой:\n"
                        f"<code>/custom_title Ваш Титул</code> 😸",
                        parse_mode='HTML'
                    )
                    return
                elif c_type == 'theme':
                    theme_id = cosm['theme_id']
                    purchased = econ.setdefault('purchased_themes', ['default'])
                    if theme_id not in purchased:
                        purchased.append(theme_id)
                    econ['profile_theme'] = theme_id
                    mark_dirty()
                    log_event('STARS ТЕМА', f'Игрок {user_link} разблокировал тему {cosm["name"]} за {stars_amount} ⭐️!')
                    bot.reply_to(
                        message,
                        f"🎨 <b>VIP ТЕМА УСПЕШНО АКТИВИРОВАНА!</b> 😻\n"
                        f"──────────────────────\n"
                        f"Вам установлена тема: <b>{cosm['name']}</b>!\n"
                        f"Проверьте свой новый визуал командой: <code>/profile</code> 😸",
                        parse_mode='HTML'
                    )
                    return
                elif c_type == 'badge':
                    badge_emoji = cosm['emoji']
                    inv = econ.setdefault('inventory', [])
                    if badge_emoji not in inv:
                        inv.append(badge_emoji)
                    econ['badge'] = badge_emoji
                    mark_dirty()
                    log_event('STARS ЗНАЧОК', f'Игрок {user_link} разблокировал значок {badge_emoji} за {stars_amount} ⭐️!')
                    bot.reply_to(
                        message,
                        f"✨ <b>VIP ЗНАЧОК НАДЕТ!</b> 😻\n"
                        f"──────────────────────\n"
                        f"Значок <b>{badge_emoji} ({cosm['name']})</b> теперь красуется в вашем профиле и в чате! 😸",
                        parse_mode='HTML'
                    )
                    return
                elif c_type == 'pet':
                    pet_id = cosm['pet_id']
                    econ.setdefault('paid_stars_items', [])
                    if cosm_id not in econ['paid_stars_items']:
                        econ['paid_stars_items'].append(cosm_id)
                    p_info = PETS_DATA[pet_id]
                    econ['pet'] = {
                        'id': pet_id,
                        'name': p_info['name'],
                        'luck_bonus': p_info['luck_bonus'],
                        'hunger': 100,
                        'cleanliness': 100,
                        'pet_exp': 0,
                        'last_update': time.time()
                    }
                    mark_dirty()
                    log_event('STARS ПИТОМЕЦ', f'Игрок {user_link} приручил {p_info["name"]} за {stars_amount} ⭐️!')
                    bot.reply_to(
                        message,
                        f"👑 <b>КОРОЛЕВСКИЙ ГРИФОН ТЕПЕРЬ ВАШ!</b> 😻\n"
                        f"──────────────────────\n"
                        f"Вы приручили мифического зверя <b>{p_info['name']}</b>!\n"
                        f"Бонус удачи: <b>+{p_info['luck_bonus']}%</b> ко всем играм, рыбалке и охоте! 😸",
                        parse_mode='HTML'
                    )
                    return

        # Дефолтная благодарность если что-то иное
        econ['balance'] += stars_amount * 35000
        mark_dirty()
        bot.reply_to(message, f"🎉 Спасибо за поддержку в размере <b>{stars_amount} ⭐️</b>! Начислено <b>+{stars_amount * 35000:,} Ня-коинов 🪙</b>! 😻", parse_mode='HTML')

    except Exception as e:
        print(f"[SUCCESSFUL PAYMENT ERROR] {e}")

# ---------------------------------------------------------
# СТАРТ И ИНИЦИАЛИЗАЦИЯ БОТА
# ---------------------------------------------------------
setup_bot_commands()
start_background_threads()
keep_alive()

print('Бот успешно запущен со всеми обновлениями и исправлениями! 😸')
bot.infinity_polling()
