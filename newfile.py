import ast
import csv
from datetime import datetime, timedelta, timezone
import html
import json
import os
import random
import re
import threading
import time
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, ReactionTypeEmoji
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
    return "Nya Bot is alive and running!"

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
TOKEN = "8963495889:AAFFwRPYDVj1gqwz879G7HkZgpgXDoGt87g"
bot = telebot.TeleBot(TOKEN)
db_lock = threading.Lock()
db_dirty = False

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
DB_CHANNEL_ID = normalize_tg_id(os.environ.get('DB_CHANNEL_ID', '-1004334874700'))
LOG_CHANNEL_ID = normalize_tg_id(os.environ.get('LOG_CHANNEL_ID', '-1004369517562'))
VD_CHAT_ID = normalize_tg_id(os.environ.get('VD_CHAT_ID', '-1003703264754'))
DATA_FILE = 'rests_data.json'

ADMIN_USERNAME = 'ukrgorilka'

# Медиа-канал и летнее аудиосообщение
MEDIA_TG_CHAT_ID = normalize_tg_id(os.environ.get('MEDIA_TG_CHAT_ID', '-1004311479842'))
WHY_TG_MSG_IDS = [5, 9]
SUMMER_SONG_MSG_ID = 307

WHY_GIFS = [
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3Z2eXpzc2ExOHBmbmdvZ3F0MHlyYm1sbTVrcHFqYm42aXFlZ3VwOSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/s239QJIh56sRW/giphy.gif",
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHlsMGVnZ29rNm0xb3JvdWRyc3dybDVrNTVrdXVnMzh0eWJ5dzdpNyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/1X7AZhiL08Y72/giphy.gif"
]

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
# СТРИМЕР И САД БОНСАЙ
# ---------------------------------------------------------
STREAM_EQUIP = {
    'mic': {'name': '🎙 Микрофон', 'levels': [0, 1000, 3000, 8000, 15000]},
    'webcam': {'name': '📷 Вебкамера', 'levels': [0, 1500, 4000, 10000, 20000]},
    'light': {'name': '💡 Неоновый свет', 'levels': [0, 800, 2000, 5000, 12000]}
}

STREAM_GENRES = ['Гейминг', 'ASMR', 'Мемы', 'Трэш-ток']

GARDEN_SEEDS = {
    'sakura': {'name': '🌸 Сакура', 'price': 300, 'grow_time': 3600*12, 'water_req': 2, 'reward_min': 800, 'reward_max': 1200, 'emoji': '🌸'},
    'money_tree': {'name': '💸 Денежное дерево', 'price': 800, 'grow_time': 3600*24, 'water_req': 4, 'reward_min': 2000, 'reward_max': 3500, 'emoji': '🌳'},
    'bamboo': {'name': '🎋 Золотой бамбук', 'price': 1500, 'grow_time': 3600*48, 'water_req': 6, 'reward_min': 4000, 'reward_max': 7000, 'emoji': '🎋'},
    'berries': {'name': '🫐 Волшебные ягоды', 'price': 500, 'grow_time': 3600*8, 'water_req': 1, 'reward_min': 1000, 'reward_max': 1800, 'emoji': '🫐'}
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
    'gothic': {'name': '💀 Тёмная Готика', 'price': 2500, 'border': '☠️══════ 🪦 ══════☠️', 'header': '💀 <b>ГОТИЧЕСКИЙ ГРИМУАР ДУШИ</b> 🕯', 'icon': '🩸'}
}

BUFF_ITEMS = {
    'energy_drink': {'name': '⚡️ Энергетик Red Cat', 'short': '⚡️ Энергетик', 'price': 400, 'desc': 'Мгновенный сброс всех кулдаунов работы, замеров и охоты'},
    'luck_clover': {'name': '🍀 Клевер Удачи (1 час)', 'short': '🍀 Клевер', 'price': 700, 'desc': '+15% к удаче во всех играх казино на 1 час'},
    'alarm_system': {'name': '🛡 Охранная сигнализация', 'short': '🛡 Сигнализация', 'price': 600, 'desc': 'Защита от 1 ограбления (вор оглушается и платит вам штраф)'},
    'invis_mask': {'name': '🥷 Маска-невидимка (24 часа)', 'short': '🥷 Невидимка', 'price': 500, 'desc': 'Скрывает мемные замеры в общих топах чата'}
}

BUSINESSES = {
    'shawarma': {'name': '🌯 Ларек с Шаурмой', 'short': 'Шаурма', 'price': 800, 'base_income': 10, 'upgrade_cost': 500},
    'coffee': {'name': '☕️ Уютная Кофейня', 'short': 'Кофейня', 'price': 2400, 'base_income': 35, 'upgrade_cost': 1800},
    'bakery': {'name': '🥐 Пекарня Булочек', 'short': 'Пекарня', 'price': 6000, 'base_income': 90, 'upgrade_cost': 4500},
    'crypto_farm': {'name': '💻 Крипто-Ферма', 'short': 'Крипто-Ферма', 'price': 18000, 'base_income': 280, 'upgrade_cost': 13000},
    'club': {'name': '🏰 Ночной Клуб', 'short': 'Ночной Клуб', 'price': 54000, 'base_income': 850, 'upgrade_cost': 38000},
    'autoshow': {'name': '🏎 Автосалон Спорткаров', 'short': 'Автосалон', 'price': 120000, 'base_income': 1800, 'upgrade_cost': 85000},
    'space_station': {'name': '🛰 Космическая Станция', 'short': 'Космостанция', 'price': 450000, 'base_income': 6500, 'upgrade_cost': 300000},
    'megacorp': {'name': '🏢 Мегакорпорация', 'short': 'Мегакорп', 'price': 1500000, 'base_income': 25000, 'upgrade_cost': 1000000},
}

CUSTOM_TITLE_CERT_PRICE = 15000

RODS = {
    'rod_bamboo': {'name': '🎋 Бамбуковая удочка', 'short': '🎋 Бамбук', 'price': 500, 'luck': 10},
    'rod_carbon': {'name': '🎣 Карбоновый спиннинг', 'short': '🎣 Карбон', 'price': 2500, 'luck': 30},
    'rod_titan': {'name': '🔱 Удочка Посейдона', 'short': '🔱 Посейдон', 'price': 10000, 'luck': 70},
    'rod_laser': {'name': '🏮 Лазерная Удочка', 'short': '🏮 Лазер', 'price': 25000, 'luck': 120}
}

BOWS = {
    'bow_hunting': {'name': '🏹 Охотничий лук', 'short': '🏹 Охотничий', 'price': 600, 'luck': 10},
    'bow_sniper': {'name': '🎯 Снайперский лук', 'short': '🎯 Снайперский', 'price': 3000, 'luck': 35},
    'bow_phoenix': {'name': '🔥 Лук Феникса', 'short': '🔥 Феникс', 'price': 12000, 'luck': 80},
    'bow_laser': {'name': '🔫 Лазерный Бластер', 'short': '🔫 Бластер', 'price': 30000, 'luck': 150}
}

VEHICLES = {
    'skateboard': {
        'name': '🛹 Скейтборд',
        'short': '🛹 Скейт',
        'price': 500,
        'cd_cut': 0.02,
        'desc': '-2% ко всем таймерам',
        'tier': 0,
        'msg_id': None
    },
    'scooter': {
        'name': '🛴 Электросамокат',
        'short': '🛴 Самокат',
        'price': 1500,
        'cd_cut': 0.05,
        'desc': '-5% ко всем таймерам',
        'tier': 1,
        'msg_id': 274
    },
    'bike': {
        'name': '🏍 Спортбайк Yamaha',
        'short': '🏍 Спортбайк',
        'price': 7500,
        'cd_cut': 0.12,
        'desc': '-12% ко всем таймерам',
        'tier': 2,
        'msg_id': 275
    },
    'bmw': {
        'name': '🚗 BMW M5 CS',
        'short': '🚗 BMW M5',
        'price': 30000,
        'cd_cut': 0.22,
        'desc': '-22% ко всем таймерам',
        'tier': 3,
        'msg_id': 276
    },
    'ferrari': {
        'name': '🏎 Ferrari SF90',
        'short': '🏎 Ferrari',
        'price': 95000,
        'cd_cut': 0.35,
        'desc': '-35% ко всем таймерам',
        'tier': 4,
        'msg_id': 277
    },
    'rocket': {
        'name': '🚀 Ракета SpaceX Starship',
        'short': '🚀 Starship',
        'price': 350000,
        'cd_cut': 0.50,
        'desc': '-50% ко всем таймерам',
        'tier': 5,
        'msg_id': 278
    },
    'teleport': {
        'name': '🌀 Квантовый Телепорт',
        'short': '🌀 Телепорт',
        'price': 1000000,
        'cd_cut': 0.75,
        'desc': '-75% ко всем таймерам',
        'tier': 6,
        'msg_id': None
    }
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
    'cat': {'name': '🐱 Котик Усач', 'short': '🐱 Котик', 'price': 720, 'luck_bonus': 15, 'desc': '+15% к удаче в охоте/рыбалке'},
    'dog': {'name': '🐶 Пёсель Верный', 'short': '🐶 Пёсель', 'price': 1450, 'luck_bonus': 25, 'desc': '+25% к удаче в охоте/рыбалке'},
    'fox': {'name': '🦊 Хитрая Лисичка', 'short': '🦊 Лисичка', 'price': 3000, 'luck_bonus': 40, 'desc': '+40% к удаче в охоте/рыбалке'},
    'owl': {'name': '🦉 Мудрая Сова', 'short': '🦉 Сова', 'price': 4800, 'luck_bonus': 60, 'desc': '+60% к удаче в охоте/рыбалке'},
    'raccoon': {'name': '🦝 Енот-Вор', 'short': '🦝 Енот', 'price': 6500, 'luck_bonus': 45, 'desc': '+20% к успеху ограблений'},
    'panda': {'name': '🐼 Панда Ленивец', 'short': '🐼 Панда', 'price': 8000, 'luck_bonus': 50, 'desc': '+35% к бонусу /bonus'},
    'dragon': {'name': '🐉 Маленький Дракон', 'short': '🐉 Дракончик', 'price': 12000, 'luck_bonus': 85, 'desc': '+85% к удаче во всем'},
    'capybara': {'name': '🦦 Капибара Чила', 'short': '🦦 Капибара', 'price': 15000, 'luck_bonus': 90, 'desc': '+90% к удаче, максимальный чилл'},
    'unicorn': {'name': '🦄 Радужный Единорог', 'short': '🦄 Единорог', 'price': 25000, 'luck_bonus': 110, 'desc': '+110% ко всем доходам'}
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

# Временные игровые структуры и анти-флуд
pending_marriages = {}
active_bj_games = {}
active_rps_games = {}
active_drops = {}
active_mines = {}
active_crash = {}
active_brick = {}

gold_rush_event = {'active': False, 'until': 0}
current_quiz = {'question': None, 'answer': None, 'reward': 0, 'chat_id': None}

user_flood_history = {}
user_flood_muted = {}
last_chat_activity = {}

# ---------------------------------------------------------
# БАЗА ДАННЫХ И АТОМАРНЫЕ БЕКАПЫ
# ---------------------------------------------------------
def load_data():
    data = {
        'rests': {},
        'history': {},
        'settings': {},
        'economy': {},
        'promos': {},
        'market': {},
        'marriages': {},
        'lottery': {'tickets': {}, 'pot': 0, 'last_draw': 0},
        'bot_active': True,
        'casino_pool': 1000000
    }
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
        print(f"Инфо: Загрузка из Telegram пропущена: {e}")

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                for key in data.keys():
                    if key in loaded:
                        data[key] = loaded[key]
                return data
        except Exception as e:
            print(f'Ошибка чтения файла: {e}')

    return data

def mark_dirty():
    global db_dirty
    db_dirty = True

def save_data(send_backup=False):
    global db_dirty
    with db_lock:
        try:
            temp_file = f"{DATA_FILE}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(db, f, ensure_ascii=False, indent=4)
            os.replace(temp_file, DATA_FILE)
            db_dirty = False

            if send_backup and DB_CHANNEL_ID:
                with open(DATA_FILE, 'rb') as f:
                    msg = bot.send_document(DB_CHANNEL_ID, f, caption="💾 Экстренный бекап базы данных")
                    try:
                        bot.pin_chat_message(DB_CHANNEL_ID, msg.message_id, disable_notification=True)
                    except Exception:
                        pass
        except Exception as e:
            print(f"Ошибка при сохранении базы данных: {e}")

def auto_save_worker():
    global db_dirty
    while True:
        time.sleep(10)
        if db_dirty:
            save_data(send_backup=False)

def periodic_backup_worker():
    while True:
        time.sleep(900)
        try:
            if DB_CHANNEL_ID and os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'rb') as f:
                    msg = bot.send_document(DB_CHANNEL_ID, f, caption=f"💾 Плановый авто-бекап базы данных [{now_msk().strftime('%d.%m.%Y %H:%M')}]")
                    try:
                        bot.pin_chat_message(DB_CHANNEL_ID, msg.message_id, disable_notification=True)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[BACKUP ERROR] Ошибка планового бекапа: {e}")

db = load_data()

def setup_bot_commands():
    commands = [
        BotCommand('menu', '📱 Главное интерактивное меню'),
        BotCommand('profile', '👤 Профиль, баланс и карточка игрока'),
        BotCommand('shop', '🏪 Магазин значков, тем, титулов и расходников'),
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
            'max_days': 30,
            'delete_rest_msg': False,
            'timezone_offset': 3,
            'remind_minutes': 60,
            'summer_music': True
        }
        save_data()
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
    reduction = 0.0
    veh = econ.get('vehicle')
    if veh and veh in VEHICLES:
        reduction += VEHICLES[veh]['cd_cut']

    active_t = econ.get('active_title')
    if active_t and active_t in TITLES:
        t_info = TITLES[active_t]
        if t_info.get('buff') == 'cd_reduction':
            reduction += (t_info['val'] / 100.0)

    return min(0.75, reduction)

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
        new_dep = bank_dep
        for _ in range(min(periods, 120)):
            new_dep = int(new_dep * 1.01)

        earned = new_dep - bank_dep
        econ['bank_deposit'] = new_dep
        econ['last_bank_calc'] = last_calc + (periods * 6 * 3600)
        return earned
    return 0

def get_user_econ(user_id=None, user_tag=None, username=None):
    if 'economy' not in db:
        db['economy'] = {}

    clean_u = clean_tag(username).lower() if username else None
    clean_d = clean_tag(user_tag) if user_tag else None

    if not user_id and clean_u:
        for k, v in db['economy'].items():
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
                    db['economy'][key]['balance'] = db['economy'][key].get('balance', 0) + old_data.get('balance', 0)
                    for item, cnt in old_data.get('fish_inventory', {}).items():
                        db['economy'][key].setdefault('fish_inventory', {})[item] = db['economy'][key].setdefault('fish_inventory', {}).get(item, 0) + cnt
                    for item, cnt in old_data.get('hunt_inventory', {}).items():
                        db['economy'][key].setdefault('hunt_inventory', {})[item] = db['economy'][key].setdefault('hunt_inventory', {}).get(item, 0) + cnt
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
        ('pet', None), ('bank_deposit', 0), ('last_bank_calc', time.time()),
        ('last_case_time', 0), ('last_rob_time', 0),
        ('profile_theme', 'default'), ('purchased_themes', ['default']),
        ('backpack', {'energy_drink': 0, 'luck_clover': 0, 'alarm_system': 0, 'invis_mask': 0}),
        ('luck_clover_until', 0), ('invis_until', 0), ('daily_casino_win', 0),
        ('daily_casino_profit', 0), ('daily_transferred', 0), ('daily_stats_date', ''),
        ('karma', 0), ('garden', None), ('stream_studio', {'mic': 1, 'webcam': 1, 'light': 1}), 
        ('last_stream_time', 0), ('last_cmd_time', 0), ('last_cmd_text', ""),
        ('loan', {'amount': 0, 'due': 0, 'defaulted': False})
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
    if is_multiplayer: return True
    if econ.get('daily_casino_profit', 0) >= 100000:
        return False
    return True

def process_casino_bet(bet):
    db['casino_pool'] = db.get('casino_pool', 1000000) + bet
    mark_dirty()

def process_casino_win(win):
    pool = db.get('casino_pool', 1000000)
    actual_win = min(win, pool + 5000) 
    db['casino_pool'] -= actual_win
    mark_dirty()
    return actual_win

def log_event(event_type, message_text):
    if not LOG_CHANNEL_ID:
        return
    try:
        clean_text = message_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        clean_text = re.sub(r'&lt;b&gt;(.*?)&lt;/b&gt;', r'<b>\1</b>', clean_text)
        clean_text = re.sub(r'&lt;code&gt;(.*?)&lt;/code&gt;', r'<code>\1</code>', clean_text)
        clean_text = re.sub(r'&lt;a href="(.*?)"&gt;(.*?)&lt;/a&gt;', r'<a href="\1">\2</a>', clean_text)

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
                except Exception as e:
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

def cooldown_text(last_time, cooldown, user_econ=None):
    if user_econ:
        cooldown = int(cooldown * (1.0 - get_user_cd_reduction(user_econ)))

    left = int(cooldown - (time.time() - last_time))
    if left <= 0:
        return None
    hours, rem = divmod(left, 3600)
    minutes, seconds = divmod(rem, 60)
    return f'{hours} ч {minutes} мин {seconds} сек'

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
        title_str = f" [{user_econ['custom_title']}]"
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
    if chat_id > 0:
        return True
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
        for k, v in db['economy'].items():
            u_name = v.get('username')
            if u_name and u_name.lower() == clean_q and v.get('user_id'):
                return v['user_id'], v.get('display_name', query.replace('@', '').strip())

    if 'economy' in db:
        for k, v in db['economy'].items():
            uid = v.get('user_id')
            if uid and str(uid) == clean_q:
                return uid, v.get('display_name', f"ID:{uid}")

    if 'economy' in db:
        for k, v in db['economy'].items():
            disp = v.get('display_name', '').lower()
            if disp == clean_q or clean_tag(disp).lower() == clean_q:
                return v.get('user_id'), v.get('display_name')

    if str_chat in db.get('rests', {}):
        for r_key, r_info in db['rests'][str_chat].items():
            rec_uid = r_info.get('user_id')
            rec_name = r_info.get('user_name', r_key)
            if str(rec_uid) == clean_q or rec_name.lower() == clean_q or r_key.lower() == clean_q:
                return rec_uid, rec_name

    if str_chat in db.get('history', {}):
        for hist_user, items in db['history'][str_chat].items():
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

    for r_key, r_info in chat_rests.items():
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
                duration = body or '3 дня'
                reason = 'Не указана'
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
                duration = clean_body or '3 дня'
                reason = 'Не указана'
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
                duration = clean_body or '3 дня'
                reason = 'Не указана'
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
                    duration = parts[1]
                    reason = 'Не указана'
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
    body = re.sub(r'^(?:/pay|перевод|передать)\s*', '', text, flags=re.IGNORECASE).strip()

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
            max_sec = sett['max_days'] * 86400
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
    return None

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
                            bot.send_message(chat_id, f'⏰ <b>Время реста для {u_link} истекло!</b> Рест автоматически снят.', parse_mode='HTML')
                        except Exception:
                            pass
                        continue

                    if 0 < remaining <= remind_sec and remind_id not in notified_reminders:
                        notified_reminders.add(remind_id)
                        mins = int(remind_sec / 60)
                        u_link = make_link(chat_id, u_name, target_user_id, ping=True)
                        try:
                            bot.send_message(chat_id, f'🔔 <b>Напоминание:</b> Рест у {u_link} закончится через {mins} мин!', parse_mode='HTML')
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
    if len(expr_str) > 100: return None
    clean_expr = expr_str.strip().replace('^', '**').replace('×', '*').replace('÷', '/').replace(':', '/')
    if not re.match(r'^[\d\s\+\-\*\/\%\(\)\.]+$', clean_expr): return None
    try:
        tree = ast.parse(clean_expr, mode='eval')
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Num, 
                                     ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.UAdd)):
                return None
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
                if isinstance(node.right, ast.Constant) and (not isinstance(node.right.value, (int, float)) or node.right.value > 50):
                    return None
                if isinstance(node.left, ast.Constant) and (not isinstance(node.left.value, (int, float)) or abs(node.left.value) > 10000):
                    return None
        res = eval(compile(tree, filename='', mode='eval'), {"__builtins__": None}, {})
        if isinstance(res, (int, float)):
            if abs(res) > 1e14: return None
            if isinstance(res, float) and res.is_integer(): return int(res)
            return round(res, 4)
    except Exception:
        return None

# ---------------------------------------------------------
# ФОНОВЫЕ ПОТОКИ: СБОРЩИКИ, ЛЕТО, АВТО-ФАКТЫ, КРЕДИТЫ
# ---------------------------------------------------------
def memory_and_debt_worker():
    while True:
        time.sleep(300)
        now = time.time()
        try:
            # 1. Мусорщик зависших игр (старше 15 минут)
            for dict_ref in [active_crash, active_mines, active_bj_games, active_rps_games, active_brick]:
                for k in list(dict_ref.keys()):
                    if now - dict_ref[k].get('start_time', now) > 900:
                        del dict_ref[k]
            for k in list(pending_marriages.keys()):
                if now - pending_marriages[k].get('start_time', now) > 900:
                    del pending_marriages[k]

            # 2. Коллекторы по просроченным кредитам
            for key, econ in list(db.get('economy', {}).items()):
                loan = econ.get('loan')
                if loan and loan.get('amount', 0) > 0 and now > loan.get('due', 0) and not loan.get('defaulted'):
                    amount = loan['amount']
                    if econ['balance'] >= amount:
                        econ['balance'] -= amount
                        econ['loan'] = {'amount': 0, 'due': 0, 'defaulted': False}
                    else:
                        econ['balance'] = 0
                        econ['bank_deposit'] = 0
                        econ['karma'] -= 20
                        econ['loan']['defaulted'] = True
                    mark_dirty()
        except Exception as e:
            print(f"[MEMORY WORKER ERROR] {e}")

def vd_facts_worker():
    while True:
        time.sleep(random.randint(7200, 14400))
        try:
            if VD_CHAT_ID:
                title, desc = random.choice(VD_FACTS)
                msg_text = (
                    "🩸 <b>ИНТЕРЕСНЫЙ ФАКТ | VIOLENCE DISTRICT</b> 🔪\n"
                    "──────────────────────\n"
                    f"📌 <b>{title}</b>\n"
                    f"📖 <i>{desc}</i>\n"
                    "──────────────────────\n"
                    "💡 <i>Хотите еще? Введите в чате:</i> <code>факт вд</code>"
                )
                bot.send_message(VD_CHAT_ID, msg_text, parse_mode='HTML')
        except Exception:
            pass

def gold_rush_worker():
    global gold_rush_event
    while True:
        time.sleep(random.randint(10800, 21600))
        try:
            gold_rush_event['active'] = True
            gold_rush_event['until'] = time.time() + 1800
            rush_msg = (
                "🌟🔥 <b>ВНИМАНИЕ! НАЧАЛАСЬ «ЗОЛОТАЯ ЛИХОРАДКА»!</b> 🔥🌟\n"
                "──────────────────────\n"
                "⏳ <b>Длительность:</b> 30 минут!\n"
                "🎣 <b>Рыбалка и Охота:</b> Шанс редкой и легендарной добычи увеличен в <b>2 РАЗА</b>!\n"
                "💰 <b>Скупщик:</b> Повышенные цены на продажу улова (<code>/sell</code>)!\n"
                "──────────────────────\n"
                "<i>Хватайте снасти и отправляйтесь на /fish и /hunt прямо сейчас!</i>"
            )
            active_chats = [cid for cid in db.get('settings', {}).keys() if int(cid) < 0]
            for str_chat_id in active_chats:
                try: bot.send_message(int(str_chat_id), rush_msg, parse_mode='HTML')
                except Exception: pass
            time.sleep(1800)
            gold_rush_event['active'] = False
            end_msg = "⏱ <b>Золотая лихорадка завершилась!</b> Спасибо всем за активную добычу! 🏕"
            for str_chat_id in active_chats:
                try: bot.send_message(int(str_chat_id), end_msg, parse_mode='HTML')
                except Exception: pass
        except Exception:
            pass

def summer_music_worker():
    while True:
        try:
            now_utc3 = now_msk()
            current_year = now_utc3.year
            end_of_summer = datetime(current_year, 8, 31, 23, 59, 59, tzinfo=MSK_TZ)
            if now_utc3 <= end_of_summer and now_utc3.month in [6, 7, 8]:
                delta = end_of_summer - now_utc3
                days = delta.days
                hours, rem = divmod(delta.seconds, 3600)
                mins, _ = divmod(rem, 60)
                countdown_caption = (
                    "☀️ <b>ЛЕТО ТАЕТ НА ГЛАЗАХ... ЛОВИ КАЖДЫЙ ТЁПЛЫЙ МОМЕНТ!</b> 🌊\n"
                    "──────────────────────\n"
                    f"⏳ До окончания лета осталось: <b>{days} дн. {hours} ч. {mins} мин.</b>\n\n"
                    "🎧 <i>Твой атмосферный летний трек этого часа:</i>"
                )
                active_chats = list(db.get('settings', {}).keys())
                for str_chat_id in active_chats:
                    sett = get_chat_settings(int(str_chat_id))
                    if sett.get('summer_music', True):
                        chat_id = int(str_chat_id)
                        try:
                            bot.copy_message(
                                chat_id=chat_id,
                                from_chat_id=MEDIA_TG_CHAT_ID,
                                message_id=SUMMER_SONG_MSG_ID,
                                caption=countdown_caption,
                                parse_mode='HTML'
                            )
                        except Exception: pass
            now_again = now_msk()
            seconds_until_next_hour = (60 - now_again.minute) * 60 - now_again.second
            time.sleep(max(60, seconds_until_next_hour))
        except Exception:
            time.sleep(60)

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
            markup.add(InlineKeyboardButton("🎁 Забрать подарок!", callback_data=f"claim_{drop_id}"))
            msg_text = (
                "📦 <b>ВНЕЗАПНЫЙ ДРОП В ЧАТЕ!</b>\n"
                "──────────────────────\n"
                f"На полу чата найдена коробка с <b>{reward} Ня-коинами 🪙</b>!\n"
                "Кто первый нажмёт кнопку ниже — заберёт всю награду себе!"
            )
            bot.send_message(target_chat, msg_text, reply_markup=markup, parse_mode='HTML')
        except Exception:
            pass

def market_news_worker():
    news_templates = [
        ("🚀 <b>ЭКСТРЕННЫЕ НОВОСТИ БИРЖИ!</b>\nКрупный венчурный фонд инвестировал 10,000,000 в <b>{name}</b>! Курс взлетает!", 'pump', 0.25, 0.45),
        ("🔥 <b>ПАМП НА НЯ-СТРИТ!</b>\nПопулярный блогер выпустил обзор на <b>{name}</b>! Монета летит на Луну!", 'pump', 0.20, 0.35),
        ("📉 <b>ОБВАЛ РЫНКА!</b>\nХакеры совершили атаку на смарт-контракт <b>{name}</b>! Панические распродажи!", 'dump', 0.20, 0.35),
        ("⚠️ <b>РЕГУЛЯТОРЫ В ДЕЛЕ!</b>\nВведены новые ограничения на торговлю <b>{name}</b>! Временная просадка курса!", 'dump', 0.15, 0.30)
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
            news_text = template.format(name=asset['name']) + f"\n\n📊 Новый курс <b>{ticker}</b>: <b>{new_p:.2f} 🪙</b> (Было: {old_p:.2f} 🪙)"
            active_chats = [cid for cid in db.get('settings', {}).keys() if int(cid) < 0]
            for str_chat_id in active_chats:
                try: bot.send_message(int(str_chat_id), news_text, parse_mode='HTML')
                except Exception: pass
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
            current_quiz['question'] = q_data[0]
            current_quiz['answer'] = q_data[1].lower().strip()
            current_quiz['reward'] = q_data[2]
            current_quiz['chat_id'] = target_chat
            msg_text = (
                "⚡️ <b>ЭКСПРЕСС-ВИКТОРИНА В ЧАТЕ!</b>\n"
                "──────────────────────\n"
                f"{q_data[0]}\n\n"
                f"💰 Награда первому верному ответу: <b>+{q_data[2]} Ня-коинов 🪙</b>\n"
                "──────────────────────\n"
                "<i>Просто напишите правильный ответ в чат!</i>"
            )
            bot.send_message(target_chat, msg_text, parse_mode='HTML')
        except Exception:
            pass

def chat_silence_worker():
    silence_prompts = [
        "👀 В чате так тихо... Колитесь, кто чем сейчас занят? ☕️✨",
        "🐾 Котики напоминают: сделайте глоток водички, расправьте плечи и улыбнитесь! 🌸",
        "💭 Мысль часа: если кошка легла на клавиатуру — это не лень, это технический перерыв! 🐱🛋",
        "🎲 Чат спит, а ракета в <code>/crash</code> и рулетка в <code>/wheel</code> ждут победителей! 🔥",
        "💬 Всем отличного настроения и продуктивного дня! Не забывайте заглядывать в <code>/tasks</code> 📋"
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
        except Exception: pass

def start_background_threads():
    threading.Thread(target=vd_facts_worker, daemon=True).start()
    threading.Thread(target=gold_rush_worker, daemon=True).start()
    threading.Thread(target=summer_music_worker, daemon=True).start()
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
    for member in message.new_chat_members:
        user_name = (f"{member.first_name or ''} {member.last_name or ''}").strip() or member.username
        user_link = make_link(message.chat.id, user_name, member.id, ping=True)
        add_coins(member.id, user_name, 50, username=member.username)

        welcome_text = (
            f"🎉 <b>Добро пожаловать в наш чат, {user_link}!</b>\n\n"
            f"🌸 Мы рады видеть тебя в нашей дружной семье!\n"
            f"💵 Тебе начислен приветственный подарок: <b>50 Ня-коинов 🪙</b>\n\n"
            f"💡 Введи <code>меню</code> или <code>/help</code>, чтобы открыть интерактивный путеводитель."
        )
        bot.send_message(message.chat.id, welcome_text, parse_mode='HTML')

@bot.message_handler(content_types=['left_chat_member'])
def goodbye_left_member(message):
    member = message.left_chat_member
    user_name = (f"{member.first_name or ''} {member.last_name or ''}").strip() or member.username
    user_link = make_link(message.chat.id, user_name, member.id, ping=False)
    farewell_text = f"👋 <b>{user_link}</b> покинул(а) наш чат. Пожелаем удачи на пути! 🌸"
    bot.send_message(message.chat.id, farewell_text, parse_mode='HTML')

# ---------------------------------------------------------
# ГЛАВНОЕ МЕНЮ И СПРАВОЧНИК
# ---------------------------------------------------------
def get_main_menu_markup(owner_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🌴 Ресты и Отпуск", callback_data=f"help_rests:{owner_id}"),
        InlineKeyboardButton("🏢 Бизнес 2.0 и Гараж", callback_data=f"help_biz:{owner_id}")
    )
    markup.add(
        InlineKeyboardButton("⚽️ Спорт & Казино", callback_data=f"help_sports:{owner_id}"),
        InlineKeyboardButton("🏦 Ня-Банк (+1%/6ч)", callback_data=f"help_bank:{owner_id}")
    )
    markup.add(
        InlineKeyboardButton("🎨 Темы и Рюкзак", callback_data=f"help_themes_buffs:{owner_id}"),
        InlineKeyboardButton("📈 Крипто-Биржа", callback_data=f"help_crypto:{owner_id}")
    )
    markup.add(
        InlineKeyboardButton("🐾 Питомцы и Охота", callback_data=f"help_pets:{owner_id}"),
        InlineKeyboardButton("🍆 Мемы, Шар и IQ", callback_data=f"help_sims:{owner_id}")
    )
    markup.add(
        InlineKeyboardButton("🎥 Стример и Сад", callback_data=f"help_stream_garden:{owner_id}"),
        InlineKeyboardButton("⚖️ Карма и РП", callback_data=f"help_karma_rp:{owner_id}")
    )
    markup.add(
        InlineKeyboardButton("🩸 Факты Violence District", callback_data=f"help_vd:{owner_id}"),
        InlineKeyboardButton("🏆 Ударники Дня", callback_data=f"help_heroes:{owner_id}")
    )
    markup.add(
        InlineKeyboardButton("💰 Экономика и Квесты", callback_data=f"help_econ:{owner_id}"),
        InlineKeyboardButton("📖 ПОЛНЫЙ СПРАВОЧНИК (А-Я)", callback_data=f"help_full_catalog:{owner_id}")
    )
    return markup

@bot.message_handler(commands=['start', 'help', 'menu', 'info'])
def send_welcome(message):
    welcome_text = (
        "🤖 <b>ГЛАВНЫЙ ИНТЕРАКТИВНЫЙ НАВИГАТОР НЯ-БОТА</b>\n"
        "──────────────────────\n"
        "Добро пожаловать в центр управления экономикой, спорт-играми, бизнесами, фактами VD и рестами!\n\n"
        "👇 <i>Выберите интересующий вас раздел из меню ниже:</i>"
    )
    bot.reply_to(message, welcome_text, reply_markup=get_main_menu_markup(message.from_user.id), parse_mode='HTML')

# ---------------------------------------------------------
# ИГРА КИРПИЧ (/brick)
# ---------------------------------------------------------
@bot.message_handler(commands=['brick', 'кирпич'])
def cmd_brick(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    m = re.search(r'(?:/brick|кирпич)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(m.group(1)) if m and m.group(1) else 50

    if bet <= 0:
        bot.reply_to(message, "❌ Ставка должна быть больше 0!")
        return

    if not check_casino_limits(econ, bet):
        bot.reply_to(message, "❌ Достигнут суточный лимит профита в казино! Приходите завтра.")
        return

    if econ['balance'] < bet:
        bot.reply_to(message, f"❌ Недостаточно средств! У вас: {econ['balance']} 🪙")
        return

    econ['balance'] -= bet
    process_casino_bet(bet)
    
    game_id = f"brick_{user_id}_{int(time.time())}"
    active_brick[game_id] = {
        'user_id': user_id,
        'user_name': user_name,
        'username': message.from_user.username,
        'bet': bet,
        'step': 0,
        'mults': [1.0, 1.2, 1.5, 1.9, 2.5, 3.5, 5.0, 8.0, 12.0],
        'risks': [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
        'start_time': time.time()
    }

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🏗 Сделать шаг на стройке", callback_data=f"brick_step_{game_id}:{user_id}"))

    bot.send_message(
        message.chat.id,
        f"🧱 <b>ИГРА КИРПИЧ (СТРОЙКА)</b>\n"
        f"──────────────────────\n"
        f"👤 Строитель: {make_link(message.chat.id, user_name, user_id, ping=False)}\n"
        f"💰 Ставка: <b>{bet} 🪙</b>\n"
        f"📈 Текущий множитель: <b>1.0x</b>\n"
        f"──────────────────────\n"
        f"<i>Делайте шаги, чтобы увеличить множитель, но помните: с каждым шагом шанс, что кирпич упадет на голову, растет!</i>",
        reply_markup=markup,
        parse_mode='HTML'
    )

# ---------------------------------------------------------
# ИГРА КРАШ (/crash)
# ---------------------------------------------------------
def crash_game_thread(game_id, chat_id, message_id, user_id, user_name, bet, crash_point):
    steps = [1.05, 1.15, 1.25, 1.40, 1.60, 1.85, 2.15, 2.50, 3.00, 3.60, 4.30, 5.20, 6.50, 8.00, 10.00, 13.00, 17.00, 22.00, 30.00, 50.00]
    
    for mult in steps:
        time.sleep(1.2)
        game = active_crash.get(game_id)
        if not game or game.get('cashed_out') or game.get('exploded'):
            return

        if mult >= crash_point:
            game['exploded'] = True
            try:
                bot.edit_message_text(
                    f"💥 <b>КРАШ! РАКЕТА ВЗОРВАЛАСЬ НА {crash_point:.2f}x!</b>\n\n"
                    f"👤 Игрок: {make_link(chat_id, user_name, user_id, ping=False)}\n"
                    f"💸 Ставка <b>{bet} Ня-коинов 🪙</b> сгорела в атмосфере...",
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
        markup.add(InlineKeyboardButton(f"💰 Забрать куш ({cashout_amt} 🪙 | {mult:.2f}x)", callback_data=f"crash_cashout_{game_id}:{user_id}"))

        bar_len = min(8, int(mult * 1.5))
        sky_bar = "☁️" * (8 - bar_len) + "🚀" + "🔥" * bar_len

        try:
            bot.edit_message_text(
                f"🚀 <b>ИГРА КРАШ (CRASH ROCKET)</b>\n"
                f"──────────────────────\n"
                f"👤 Пилот: {make_link(chat_id, user_name, user_id, ping=False)}\n"
                f"💰 Ставка: <b>{bet} 🪙</b>\n"
                f"📈 Текущий множитель: <b>{mult:.2f}x</b>\n"
                f"🛰 Полет: [{sky_bar}]\n"
                f"──────────────────────\n"
                f"<i>Успейте нажать кнопку ниже до взрыва ракеты!</i>",
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=markup,
                parse_mode='HTML'
            )
        except Exception:
            pass

@bot.message_handler(commands=['crash', 'краш', 'ракета'])
def cmd_crash(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    m = re.search(r'(?:/crash|краш|ракета)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(m.group(1)) if m and m.group(1) else 50

    if bet <= 0:
        bot.reply_to(message, "❌ Ставка должна быть больше 0!")
        return

    if bet > 5000:
        bot.reply_to(message, "❌ Максимальная ставка в Краш: <b>5000 🪙</b>!", parse_mode='HTML')
        return

    if not check_casino_limits(econ, bet):
        bot.reply_to(message, "❌ Достигнут суточный лимит профита в казино! Приходите завтра.")
        return

    if econ['balance'] < bet:
        bot.reply_to(message, f"❌ Недостаточно средств! У вас: {econ['balance']} 🪙")
        return

    econ['balance'] -= bet
    process_casino_bet(bet)

    game_id = f"cr_{user_id}_{int(time.time())}"
    
    r = random.random()
    pool = db.get('casino_pool', 1000000)
    
    if pool < bet * 5:
        crash_point = round(random.uniform(1.00, 1.10), 2)
    else:
        if r < 0.15: crash_point = 1.00
        elif r < 0.40: crash_point = round(random.uniform(1.05, 1.80), 2)
        elif r < 0.70: crash_point = round(random.uniform(1.85, 3.50), 2)
        elif r < 0.90: crash_point = round(random.uniform(3.50, 7.50), 2)
        elif r < 0.97: crash_point = round(random.uniform(7.50, 18.00), 2)
        else: crash_point = round(random.uniform(18.00, 50.00), 2)

    active_crash[game_id] = {
        'user_id': user_id,
        'user_name': user_name,
        'username': message.from_user.username,
        'bet': bet,
        'crash_point': crash_point,
        'current_mult': 1.00,
        'cashed_out': False,
        'exploded': False,
        'start_time': time.time()
    }

    if crash_point <= 1.00:
        active_crash[game_id]['exploded'] = True
        bot.send_message(
            message.chat.id,
            f"🚀 <b>ИГРА КРАШ (CRASH ROCKET)</b>\n"
            f"──────────────────────\n"
            f"💥 <b>РАКЕТА ВЗОРВАЛАСЬ НА СТАРТЕ (1.00x)!</b>\n\n"
            f"👤 Пилот: {make_link(message.chat.id, user_name, user_id, ping=False)}\n"
            f"💸 Ваша ставка <b>{bet} Ня-коинов 🪙</b> моментально сгорела в атмосфере...",
            parse_mode='HTML'
        )
        del active_crash[game_id]
        return

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"💰 Забрать куш ({bet} 🪙 | 1.00x)", callback_data=f"crash_cashout_{game_id}:{user_id}"))

    sent_msg = bot.send_message(
        message.chat.id,
        f"🚀 <b>ИГРА КРАШ (CRASH ROCKET)</b>\n"
        f"──────────────────────\n"
        f"👤 Пилот: {make_link(message.chat.id, user_name, user_id, ping=False)}\n"
        f"💰 Ставка: <b>{bet} 🪙</b>\n"
        f"📈 Запуск двигателей... [🚀☁️☁️☁️☁️☁️☁️]\n"
        f"──────────────────────\n"
        f"<i>Приготовьтесь забрать куш!</i>",
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
    
    base_viewers = (studio.get('mic', 1) + studio.get('webcam', 1) + studio.get('light', 1)) * 50
    viewers = base_viewers + random.randint(10, 100)
    
    text = (
        f"🔴 <b>СТРИМ ЗАПУЩЕН!</b>\n"
        f"──────────────────────\n"
        f"👤 Стример: {make_link(chat_id, user_name, user_id, ping=False)}\n"
        f"🎮 Жанр: <b>{genre}</b>\n\n"
        f"<i>Зрители подключаются... (👁 {viewers})</i>"
    )
    try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode='HTML')
    except Exception: pass
    
    time.sleep(3)
    
    event_roll = random.random()
    if event_roll < 0.3:
        event = "🔥 Чат сходит с ума от ваших шуток!"
        viewers = int(viewers * 1.5)
    elif event_roll < 0.6:
        event = "💰 Крупный донатер скинул солидную сумму!"
    elif event_roll < 0.8:
        event = "🎉 RAID от популярного стримера!"
        viewers = int(viewers * 2.5)
    else:
        event = "📉 Интернет лагает, часть зрителей ушла..."
        viewers = int(viewers * 0.7)
        
    text += f"\n\n⚡️ <b>Событие:</b> {event}\n<i>(👁 {viewers} зрителей)</i>"
    try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode='HTML')
    except Exception: pass
        
    time.sleep(3)
    
    donates = int(viewers * random.uniform(0.5, 1.5))
    if 'Трэш-ток' in genre.title(): karma_diff = -2
    else: karma_diff = 1
        
    change_karma(user_id, user_name, karma_diff)
    econ['balance'] += donates
    mark_dirty()
    
    k_sign = "+" if karma_diff > 0 else ""
    text += (
        f"\n\n🏁 <b>СТРИМ ЗАВЕРШЕН!</b>\n"
        f"──────────────────────\n"
        f"💸 Заработано донатов: <b>+{donates} 🪙</b>\n"
        f"⚖️ Влияние на Карму: <b>{k_sign}{karma_diff}</b>"
    )
    try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode='HTML')
    except Exception: pass

@bot.message_handler(commands=['stream', 'стрим'])
def cmd_stream(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    
    now = time.time()
    cooldown = 3600 * 2
    left = cooldown_text(econ.get('last_stream_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Стримить можно раз в 2 часа! Ждите: <b>{left}</b>.", parse_mode='HTML')
        return
        
    parts = message.text.split(maxsplit=1)
    genre = parts[1].strip() if len(parts) > 1 else random.choice(STREAM_GENRES)
    
    econ['last_stream_time'] = now
    mark_dirty()
    
    msg = bot.reply_to(message, "🔴 <i>Настройка ОБС и запуск потока...</i>", parse_mode='HTML')
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
            f"🪴 <b>ВАША ОРАНЖЕРЕЯ БОНСАЙ</b>\n"
            f"──────────────────────\n"
            f"У вас пока нет посаженных растений!\n\n"
            f"Купите семена ниже, чтобы начать выращивать свой сад для пассивного заработка."
        )
        for s_id, s_info in GARDEN_SEEDS.items():
            markup.add(InlineKeyboardButton(f"{s_info['emoji']} Купить {s_info['name']} ({s_info['price']} 🪙)", callback_data=f"buy_seed_{s_id}:{user_id}"))
    else:
        seed_id = garden['seed']
        seed_info = GARDEN_SEEDS[seed_id]
        now = time.time()
        
        elapsed = now - garden['planted_at']
        progress_pct = min(100, int((elapsed / seed_info['grow_time']) * 100))
        water_count = garden['water_count']
        req_water = seed_info['water_req']
        can_harvest = (progress_pct >= 100 and water_count >= req_water)
        
        stage = "🌱 Росток"
        if progress_pct >= 100: stage = "🍎 Урожай"
        elif progress_pct >= 50: stage = "🌿 Цветение"
            
        bar_len = progress_pct // 10
        bar = "🟩" * bar_len + "⬜️" * (10 - bar_len)
        
        text = (
            f"🪴 <b>ВАШ САД: {seed_info['name']}</b>\n"
            f"──────────────────────\n"
            f"📈 Прогресс роста: <b>{progress_pct}%</b>\n"
            f"[{bar}]\n"
            f"💧 Полив: <b>{water_count}/{req_water}</b>\n"
            f"🌻 Стадия: <b>{stage}</b>\n"
            f"──────────────────────"
        )
        
        if not can_harvest:
            markup.add(InlineKeyboardButton("💦 Полить растение", callback_data=f"water_plant:{user_id}"))
        if can_harvest:
            markup.add(InlineKeyboardButton("🧺 Собрать урожай", callback_data=f"harvest_plant:{user_id}"))
        markup.add(InlineKeyboardButton("❌ Выкорчевать", callback_data=f"uproot_plant:{user_id}"))
        
    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception: pass
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['garden', 'сад'])
def cmd_garden(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_garden_view(message.chat.id, user_id, user_name)

# ---------------------------------------------------------
# КРЕДИТЫ (НЯ-БАНК)
# ---------------------------------------------------------
@bot.message_handler(commands=['loan', 'кредит'])
def cmd_loan(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    
    loan = econ.setdefault('loan', {'amount': 0, 'due': 0, 'defaulted': False})
    
    if loan.get('amount', 0) > 0:
        due_date = datetime.fromtimestamp(loan['due']).strftime('%d.%m.%Y %H:%M')
        bot.reply_to(message, f"❌ У вас уже есть активный кредит на <b>{loan['amount']} 🪙</b>!\nОплатите его до {due_date} (команда: <code>/repay</code>).", parse_mode='HTML')
        return
        
    if loan.get('defaulted'):
        bot.reply_to(message, "❌ Ваша кредитная история испорчена (Вы в черном списке банка)!", parse_mode='HTML')
        return

    m = re.search(r'(?:/loan|кредит)\s*(\d+)?', message.text, re.IGNORECASE)
    amount = int(m.group(1)) if m and m.group(1) else 0
    
    lvl, _, _, _ = get_account_level(econ.get('account_exp', 0))
    max_loan = lvl * 1500
    
    if amount <= 0:
        bot.reply_to(message, f"🏦 <b>КРЕДИТНЫЙ ОТДЕЛ НЯ-БАНКА</b>\n\nВам доступен кредит до <b>{max_loan} 🪙</b> (на 24 часа).\nСумма возврата будет на 15% больше!\n\nДля оформления введите: <code>/loan {max_loan}</code>", parse_mode='HTML')
        return
        
    if amount > max_loan:
        bot.reply_to(message, f"❌ Банк не одобрил такую сумму! Максимум для вашего {lvl} уровня: <b>{max_loan} 🪙</b>.", parse_mode='HTML')
        return
        
    repay_amount = int(amount * 1.15)
    econ['balance'] += amount
    econ['loan'] = {
        'amount': repay_amount,
        'due': time.time() + 86400,
        'defaulted': False
    }
    mark_dirty()
    
    bot.reply_to(message, f"✅ <b>КРЕДИТ ОДОБРЕН!</b>\n\nВы получили <b>{amount} 🪙</b>.\nВам нужно вернуть <b>{repay_amount} 🪙</b> в течение 24 часов (команда <code>/repay</code>), иначе вмешаются коллекторы!", parse_mode='HTML')

@bot.message_handler(commands=['repay', 'погасить'])
def cmd_repay(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    
    loan = econ.get('loan', {})
    if loan.get('amount', 0) <= 0:
        bot.reply_to(message, "У вас нет активных кредитов!")
        return
        
    amount_to_pay = loan['amount']
    if econ['balance'] < amount_to_pay:
        bot.reply_to(message, f"❌ Недостаточно средств для погашения! Нужно <b>{amount_to_pay} 🪙</b>, у вас: {econ['balance']}.", parse_mode='HTML')
        return
        
    econ['balance'] -= amount_to_pay
    econ['loan'] = {'amount': 0, 'due': 0, 'defaulted': False}
    mark_dirty()
    bot.reply_to(message, f"✅ Кредит успешно погашен! Списано <b>{amount_to_pay} 🪙</b>. Ваша кредитная история чиста.", parse_mode='HTML')

# ---------------------------------------------------------
# TELEGRAM-СПОРТ И АЗАРТ
# ---------------------------------------------------------
def process_sport_dice_game(message, game_type, bet):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    if bet <= 0:
        bot.reply_to(message, "❌ Ставка должна быть больше 0!")
        return
        
    if not check_casino_limits(econ, bet):
        bot.reply_to(message, "❌ Достигнут суточный лимит профита в казино! Приходите завтра.")
        return

    if econ['balance'] < bet:
        bot.reply_to(message, f"❌ Недостаточно средств! У вас: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
        return

    econ['balance'] -= bet
    process_casino_bet(bet)

    emoji_map = {'football': '⚽', 'basketball': '🏀', 'darts': '🎯', 'bowling': '🎳'}
    dice_emoji = emoji_map.get(game_type, '🎲')
    msg = bot.send_dice(chat_id, emoji=dice_emoji)
    val = msg.dice.value

    time.sleep(3.5)
    has_clover = (econ.get('luck_clover_until', 0) > time.time())
    clover_str = " (🍀 Бонус клевера +15%)" if has_clover else ""
    result_text = ""
    
    pool = db.get('casino_pool', 1000000)
    force_loss = False
    if pool < bet * 3: force_loss = True

    if force_loss: val = 1 # Ломаем RNG, если пул пуст

    if game_type == 'football':
        if val in [3, 4, 5]:
            mult = 1.6 if not has_clover else 1.8
            win_amount = int(bet * mult)
            win_amount = process_casino_win(win_amount)
            econ['balance'] += win_amount
            econ['daily_casino_win'] = econ.get('daily_casino_win', 0) + (win_amount - bet)
            econ['daily_casino_profit'] = econ.get('daily_casino_profit', 0) + (win_amount - bet)
            result_text = f"⚽️ <b>ГОООООЛ! МЯЧ В СЕТКЕ!</b>\n🎉 Выигрыш: <b>+{win_amount} Ня-коинов 🪙</b> (x{mult}){clover_str}!"
        elif val == 2:
            result_text = f"🧤 <b>ВРАТАРЬ ОТБИЛ УДАР!</b>\n💸 Штанга и сейф! Ставка <b>{bet} 🪙</b> сгорела."
        else:
            result_text = f"💨 <b>МИМО ВОРОТ!</b>\n💸 Мяч улетел на трибуны. Проигрыш <b>{bet} 🪙</b>."
    elif game_type == 'basketball':
        if val in [4, 5]:
            mult = 2.0 if not has_clover else 2.3
            win_amount = int(bet * mult)
            win_amount = process_casino_win(win_amount)
            econ['balance'] += win_amount
            econ['daily_casino_win'] = econ.get('daily_casino_win', 0) + (win_amount - bet)
            econ['daily_casino_profit'] = econ.get('daily_casino_profit', 0) + (win_amount - bet)
            result_text = f"🏀 <b>ТОЧНЫЙ БРОСОК В КОРЗИНУ!</b>\n🎉 Чистый трёхочковый! Выигрыш: <b>+{win_amount} 🪙</b> (x{mult}){clover_str}!"
        elif val == 3:
            result_text = f"🧱 <b>МЯЧ ЗАСТРЯЛ НА ДУЖКЕ!</b>\n💸 Досадный промах! Ставка <b>{bet} 🪙</b> сгорела."
        else:
            result_text = f"💨 <b>МИМО ЩИТА!</b>\n💸 Промах мимо корзины. Проигрыш <b>{bet} 🪙</b>."
    elif game_type == 'darts':
        if val == 6:
            mult = 3.5 if not has_clover else 4.0
            win_amount = int(bet * mult)
            win_amount = process_casino_win(win_amount)
            econ['balance'] += win_amount
            econ['daily_casino_win'] = econ.get('daily_casino_win', 0) + (win_amount - bet)
            econ['daily_casino_profit'] = econ.get('daily_casino_profit', 0) + (win_amount - bet)
            result_text = f"🎯👑 <b>ПРЯМО В ЯБЛОЧКО (BULLSEYE)!</b>\n🎉 МЕГА-КУШ: <b>+{win_amount} 🪙</b> (x{mult}){clover_str}!"
        elif val == 5:
            mult = 1.5
            win_amount = int(bet * mult)
            win_amount = process_casino_win(win_amount)
            econ['balance'] += win_amount
            econ['daily_casino_win'] = econ.get('daily_casino_win', 0) + (win_amount - bet)
            econ['daily_casino_profit'] = econ.get('daily_casino_profit', 0) + (win_amount - bet)
            result_text = f"🎯 <b>ОТЛИЧНОЕ ПОПАДАНИЕ В ЦЕНТР!</b>\n🎉 Выигрыш: <b>+{win_amount} 🪙</b> (x{mult})!"
        else:
            result_text = f"💨 <b>ДРОТИК УЛЕТЕЛ МИМО!</b> (Значение: {val})\n💸 Проигрыш <b>{bet} 🪙</b>."
    elif game_type == 'bowling':
        if val == 6:
            mult = 3.0 if not has_clover else 3.5
            win_amount = int(bet * mult)
            win_amount = process_casino_win(win_amount)
            econ['balance'] += win_amount
            econ['daily_casino_win'] = econ.get('daily_casino_win', 0) + (win_amount - bet)
            econ['daily_casino_profit'] = econ.get('daily_casino_profit', 0) + (win_amount - bet)
            result_text = f"🎳👑 <b>СТРАААЙК! ВСЕ КЕГЛИ РАЗБИТЫ!</b>\n🎉 Мега-бросок: <b>+{win_amount} 🪙</b> (x{mult}){clover_str}!"
        elif val in [4, 5]:
            win_amount = int(bet * 1.1)
            win_amount = process_casino_win(win_amount)
            econ['balance'] += win_amount
            result_text = f"🎳 <b>ХОРОШИЙ СПЛИТ!</b> Сбито большинство кеглей.\n✅ Возврат с бонусом: <b>+{win_amount} 🪙</b> (x1.1)."
        else:
            result_text = f"💨 <b>ШАР СКАТИЛСЯ В ЖЁЛОБ!</b> (Значение: {val})\n💸 Проигрыш <b>{bet} 🪙</b>."

    add_account_exp(user_id, user_name, 5, username=message.from_user.username)
    check_achievements(user_id, user_name, 'games', 1, chat_id, username=message.from_user.username)
    mark_dirty()

    u_link = make_link(chat_id, user_name, user_id, ping=True)
    bot.reply_to(message, f"👤 Игрок: {u_link}\n{result_text}\n💰 Баланс: <b>{econ['balance']} Ня-коинов 🪙</b>", parse_mode='HTML')

@bot.message_handler(commands=['football', 'футбол', 'пенальти'])
def cmd_football(message):
    m = re.search(r'(?:/football|футбол|пенальти)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(m.group(1)) if m and m.group(1) else 50
    process_sport_dice_game(message, 'football', bet)

@bot.message_handler(commands=['basketball', 'баскетбол'])
def cmd_basketball(message):
    m = re.search(r'(?:/basketball|баскетбол)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(m.group(1)) if m and m.group(1) else 50
    process_sport_dice_game(message, 'basketball', bet)

@bot.message_handler(commands=['darts', 'дартс'])
def cmd_darts(message):
    m = re.search(r'(?:/darts|дартс)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(m.group(1)) if m and m.group(1) else 50
    process_sport_dice_game(message, 'darts', bet)

@bot.message_handler(commands=['bowling', 'боулинг'])
def cmd_bowling(message):
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
    q = re.sub(r'^(?:/ball|шар)\s*', '', message.text, flags=re.IGNORECASE).strip()
    if not q:
        bot.reply_to(message, "🔮 Задайте вопрос шару судьбы!\nПример: <code>шар пойду ли я сегодня спать вовремя?</code>", parse_mode='HTML')
        return
    ans = random.choice(BALL_RESPONSES)
    bot.reply_to(message, f"🔮 <b>Вопрос:</b> <i>«{html.escape(q)}»</i>\n\n{ans}", parse_mode='HTML')

@bot.message_handler(commands=['chance', 'шанс'])
def cmd_chance(message):
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
    bot.reply_to(message, f"📊 <b>АНАЛИЗ ВЕРОЯТНОСТИ СОБЫТИЯ:</b>\n<i>«{html.escape(q)}»</i>\n──────────────────────\nШанс: <b>{pct}%</b> [{bar}]\n💡 Вердикт: <i>{verdict}</i>\n──────────────────────", parse_mode='HTML')

@bot.message_handler(commands=['detector', 'детектор', 'правда'])
def cmd_detector(message):
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
    bot.reply_to(message, f"🕵️‍♂️ <b>СКАНИРОВАНИЕ НА ПОЛИГРАФЕ:</b>\n<i>«{html.escape(q)}»</i>\n──────────────────────\nВердикт: {v_title}\n📝 <i>{v_desc}</i>\n──────────────────────", parse_mode='HTML')

# ---------------------------------------------------------
# УДАРНИКИ И ГЕРОИ ДНЯ
# ---------------------------------------------------------
@bot.message_handler(commands=['daily_heroes', 'герои_дня', 'ударники'])
def cmd_daily_heroes(message):
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
        "🏆 <b>ГЕРОИ И УДАРНИКИ СЕГОДНЯШНЕГО ДНЯ</b>\n"
        "──────────────────────\n"
        f"🗣 <b>Главный спикер дня:</b>\n👉 {speaker_str}\n\n"
        f"🎰 <b>Гроза казино и спорта:</b>\n👉 {casino_str}\n\n"
        f"💖 <b>Главный меценат чата:</b>\n👉 {transfer_str}\n"
        "──────────────────────\n"
        "👑 <i>Герои дня получают почёт, уважение и статус в чате на 24 часа!</i>"
    )
    bot.reply_to(message, text, parse_mode='HTML')

# ---------------------------------------------------------
# РЮКЗАК И РАСХОДНИКИ
# ---------------------------------------------------------
def render_backpack_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    bp = econ.setdefault('backpack', {'energy_drink': 0, 'luck_clover': 0, 'alarm_system': 0, 'invis_mask': 0})

    markup = InlineKeyboardMarkup()
    if bp.get('energy_drink', 0) > 0: markup.add(InlineKeyboardButton(f"⚡️ Выпить Энергетик ({bp['energy_drink']} шт.)", callback_data=f"use_item_energy_drink:{user_id}"))
    if bp.get('luck_clover', 0) > 0: markup.add(InlineKeyboardButton(f"🍀 Активировать Клевер ({bp['luck_clover']} шт.)", callback_data=f"use_item_luck_clover:{user_id}"))
    if bp.get('invis_mask', 0) > 0: markup.add(InlineKeyboardButton(f"🥷 Надеть Невидимку ({bp['invis_mask']} шт.)", callback_data=f"use_item_invis_mask:{user_id}"))
    markup.add(InlineKeyboardButton("🏪 Купить расходники в Магазине", callback_data=f"shop_cat_buffs:{user_id}"))

    clover_status = "✅ Активен" if econ.get('luck_clover_until', 0) > time.time() else "❌ Не активен"
    invis_status = "✅ Включена" if econ.get('invis_until', 0) > time.time() else "❌ Выключена"

    text = (
        f"🎒 <b>РЮКЗАК БАФФОВ И РАСХОДНИКОВ</b>\n"
        f"──────────────────────\n"
        f"👤 Владелец: {make_link(chat_id, user_name, user_id, ping=False)}\n\n"
        f"• ⚡️ Энергетик Red Cat: <b>{bp.get('energy_drink', 0)} шт.</b>\n"
        f"• 🍀 Клевер удачи: <b>{bp.get('luck_clover', 0)} шт.</b> (Статус: {clover_status})\n"
        f"• 🛡 Охранная сигнализация: <b>{bp.get('alarm_system', 0)} шт.</b> (Авто-защита)\n"
        f"• 🥷 Маска-невидимка: <b>{bp.get('invis_mask', 0)} шт.</b> (Статус: {invis_status})\n"
        f"──────────────────────\n"
        f"💡 <i>Нажмите кнопку под сообщением, чтобы использовать предмет!</i>"
    )

    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            return
        except Exception: pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['backpack', 'рюкзак', 'инвентарь_баффов'])
def cmd_backpack(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_backpack_view(message.chat.id, message.from_user.id, user_name)

# ---------------------------------------------------------
# КОЛЕСО ФОРТУНЫ (/wheel)
# ---------------------------------------------------------
@bot.message_handler(commands=['wheel', 'рулетка', 'колесо'])
def cmd_wheel(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    now = time.time()
    last_spin = econ.get('last_wheel_time', 0)
    cooldown = 43200

    left = cooldown_text(last_spin, cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ <b>Колесо Фортуны доступно раз в 12 часов!</b>\nСледующее бесплатное вращение через: <b>{left}</b>.", parse_mode='HTML')
        return

    econ['last_wheel_time'] = now
    sectors = [
        ('coins_100', '💰 100 Ня-коинов', 30), ('coins_300', '💵 300 Ня-коинов', 20),
        ('jackpot', '💎 ДЖЕКПОТ 1,500 🪙', 5), ('fish', '🐟 Случайный редкий улов', 15),
        ('beast', '🏹 Охотничий трофей', 15), ('exp', '⭐ +80 Опыта профиля', 10),
        ('karma', '😇 +5 Кармы (Светлый путь)', 5)
    ]
    weights = [s[2] for s in sectors]
    win_sector = random.choices(sectors, weights=weights, k=1)[0]
    win_key = win_sector[0]

    prize_text = ""
    if win_key == 'coins_100':
        econ['balance'] += 100
        prize_text = "💰 Вы выиграли <b>+100 Ня-коинов 🪙</b>!"
    elif win_key == 'coins_300':
        econ['balance'] += 300
        prize_text = "💵 Вы выиграли <b>+300 Ня-коинов 🪙</b>!"
    elif win_key == 'jackpot':
        econ['balance'] += 1500
        prize_text = "💎👑 <b>МЕГА ДЖЕКПОТ! +1,500 Ня-коинов 🪙</b>!"
        log_event('КОЛЕСО: ДЖЕКПОТ', f'{make_link(message.chat.id, user_name, user_id, ping=False)} сорвал джекпот Колеса Фортуны (1,500 🪙)!')
    elif win_key == 'fish':
        trophy = random.choice(FISH_TYPES)[0]
        add_inventory_item(econ['fish_inventory'], trophy)
        prize_text = f"🐟 Вы выловили: <b>{trophy}</b>!"
    elif win_key == 'beast':
        trophy = random.choice(HUNT_TYPES)[0]
        add_inventory_item(econ['hunt_inventory'], trophy)
        prize_text = f"🏹 Вы добыли: <b>{trophy}</b>!"
    elif win_key == 'exp':
        add_account_exp(user_id, user_name, 80, username=message.from_user.username)
        prize_text = "⭐ Вы получили <b>+80 EXP опыта профиля</b>!"
    elif win_key == 'karma':
        change_karma(user_id, user_name, 5)
        prize_text = "😇 Вы выиграли <b>+5 Кармы</b>!"

    check_achievements(user_id, user_name, 'wheel_spins', 1, message.chat.id, username=message.from_user.username)
    mark_dirty()

    anim_text = (
        "🎡 <b>КОЛЕСО ФОРТУНЫ КРУТИТСЯ...</b>\n\n"
        "▫️ [ 💰 100 🪙 ]\n▫️ [ 💵 300 🪙 ]\n▫️ [ 💎 ДЖЕКПОТ 1,500 🪙 ]\n▫️ [ 🐟 Рыба / 🏹 Дичь ]\n▫️ [ 😇 Карма +5 ]\n\n"
        f"🎉 <b>Стрелка остановилась на секторе:</b>\n👉 <b>{win_sector[1]}</b>!\n\n{prize_text}"
    )
    bot.reply_to(message, anim_text, parse_mode='HTML')

# ---------------------------------------------------------
# САПЁР / МИНЫ (/mines)
# ---------------------------------------------------------
def render_mines_board(game_id):
    game = active_mines.get(game_id)
    if not game: return None, None
    u_id = game['user_id']
    markup = InlineKeyboardMarkup(row_width=4)
    buttons = []

    for i in range(16):
        if i in game['revealed']: buttons.append(InlineKeyboardButton("💎", callback_data="noop"))
        elif game['finished'] and i in game['bombs']: buttons.append(InlineKeyboardButton("💣", callback_data="noop"))
        elif game['finished']: buttons.append(InlineKeyboardButton("▫️", callback_data="noop"))
        else: buttons.append(InlineKeyboardButton("❓", callback_data=f"mines_open_{game_id}_{i}:{u_id}"))

    for row_idx in range(0, 16, 4):
        markup.add(*buttons[row_idx:row_idx+4])

    if not game['finished'] and len(game['revealed']) > 0:
        cashout_amount = int(game['bet'] * game['current_multiplier'])
        markup.add(InlineKeyboardButton(f"💰 Забрать куш ({cashout_amount} 🪙 | {game['current_multiplier']:.2f}x)", callback_data=f"mines_cashout_{game_id}:{u_id}"))

    text = (
        f"💣 <b>САПЁР (ПОЛЕ 4х4)</b>\n"
        f"──────────────────────\n"
        f"👤 Игрок: {game['user_tag']}\n"
        f"💰 Ставка: <b>{game['bet']} 🪙</b> | Мин на поле: <b>{len(game['bombs'])} шт.</b>\n"
        f"💎 Найдено кристаллов: <b>{len(game['revealed'])}/13</b>\n"
        f"📈 Множитель: <b>{game['current_multiplier']:.2f}x</b>\n"
        f"──────────────────────\n"
        f"<i>Открывайте безопасные клетки или заберите куш!</i>"
    )
    return text, markup

@bot.message_handler(commands=['mines', 'мины', 'сапер'])
def cmd_mines(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    match = re.search(r'(?:/mines|мины|сапер)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(match.group(1)) if match and match.group(1) else 50

    if bet <= 0:
        bot.reply_to(message, "❌ Ставка должна быть больше 0!")
        return

    if not check_casino_limits(econ, bet):
        bot.reply_to(message, "❌ Достигнут суточный лимит профита в казино! Приходите завтра.")
        return

    if econ['balance'] < bet:
        bot.reply_to(message, f"❌ Недостаточно средств! У вас: {econ['balance']} 🪙")
        return

    econ['balance'] -= bet
    process_casino_bet(bet)

    game_id = f"m_{user_id}_{int(time.time())}"
    bombs = set(random.sample(range(16), 3))

    active_mines[game_id] = {
        'user_id': user_id,
        'user_tag': user_name,
        'username': message.from_user.username,
        'bet': bet,
        'bombs': bombs,
        'revealed': set(),
        'current_multiplier': 1.0,
        'finished': False,
        'start_time': time.time()
    }

    text, markup = render_mines_board(game_id)
    bot.reply_to(message, text, reply_markup=markup, parse_mode='HTML')

# ---------------------------------------------------------
# МЕМНЫЕ СИМУЛЯТОРЫ: РАСШИРЕННЫЙ ПИСЮН И ФАП
# ---------------------------------------------------------
@bot.message_handler(commands=['dick', 'писюн', 'замер'])
def cmd_dick(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    now = time.time()
    last_time = econ.get('last_dick_time', 0)
    cooldown = 1200

    left = cooldown_text(last_time, cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Замер писюна доступен раз в 20 минут!\nПодождите: <b>{left}</b>.", parse_mode='HTML')
        return

    change = random.choice([-3, -2, -1, 1, 2, 3, 4, 5, 6])
    cur_size = econ.get('dick_size', 15)
    new_size = max(1, min(250, cur_size + change))

    econ['dick_size'] = new_size
    econ['last_dick_time'] = now
    mark_dirty()

    sign = "+" if change >= 0 else ""
    u_link = make_link(chat_id, user_name, user_id, ping=True)

    if new_size >= 100: comment = "🌌 Космический монумент масштабов галактики! Вселенная склоняет колени!"
    elif new_size >= 70: comment = "🗿 Колосс Родосский нервно курит в сторонке! Невероятный титан!"
    elif new_size >= 45: comment = "👑 Абсолютный повелитель и гигант чата!"
    elif new_size >= 30: comment = "🍆 Внушительный и устрашающий размерчик!"
    elif new_size >= 18: comment = "🔥 Крепкий и солидный инструмент!"
    elif new_size >= 10: comment = "👌 Классический средний размер."
    else: comment = "🤏 Кажется, на улице было слишком морозно..."

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
        bot.reply_to(message, f"⏳ Рука должна отдохнуть! Подождите: <b>{left}</b>.", parse_mode='HTML')
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
        f"💦 <b>СЕАНС ФАПА УСПЕШНО ЗАВЕРШЕН!</b>\n"
        f"──────────────────────\n"
        f"👤 Участник: {u_link}\n"
        f"📊 Подходов за сегодня: <b>{count} раз(а)</b>\n"
        f"🎖 Ранг: <b>{rank}</b>\n"
        f"──────────────────────",
        parse_mode='HTML'
    )

# ---------------------------------------------------------
# ГАРАЖ
# ---------------------------------------------------------
def render_garage_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    cur_veh = econ.get('vehicle')
    cur_name = VEHICLES[cur_veh]['name'] if cur_veh in VEHICLES else "Пешеход 🚶‍♂️"

    lines = [
        f"🏎 <b>ЛИЧНЫЙ АВТОГАРАЖ</b>",
        "──────────────────────",
        f"👤 Владелец: {make_link(chat_id, user_name, user_id, ping=False)}",
        f"🚘 Текущий транспорт: <b>{cur_name}</b>\n",
        "<i>Транспорт навсегда снижает кулдауны на работу, охоту, рыбалку и замеры!</i>\n",
        "<b>Каталог транспорта:</b>"
    ]

    markup = InlineKeyboardMarkup()
    for v_id, v_info in VEHICLES.items():
        is_owned = " (Куплено)" if cur_veh == v_id else ""
        lines.append(f"• <b>{v_info['name']}</b> — <code>{v_info['price']} 🪙</code> ({v_info['desc']}){is_owned}")
        markup.add(InlineKeyboardButton(f"{v_info['short']} — {v_info['price']} 🪙", callback_data=f"buy_veh_{v_id}:{user_id}"))

    lines.append("──────────────────────")
    text = "\n".join(lines)

    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            return
        except Exception: pass

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
        except Exception: pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['garage', 'гараж'])
def cmd_garage(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_garage_view(message.chat.id, user_id, user_name)

# ---------------------------------------------------------
# КУЛИНАРИЯ (/cook)
# ---------------------------------------------------------
@bot.message_handler(commands=['cook', 'кулинария', 'приготовить'])
def cmd_cook(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    fish_count = sum(econ.get('fish_inventory', {}).values())
    hunt_count = sum(econ.get('hunt_inventory', {}).values())

    if fish_count == 0 and hunt_count == 0:
        bot.reply_to(message, "🎒 У вас нет пойманной рыбы или мяса дичи для приготовления!\nСходите на <code>/fish</code> или <code>/hunt</code>.", parse_mode='HTML')
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
        f"🍳 <b>КУЛИНАРНЫЙ ШЕДЕВР ГОТОВ!</b>\n"
        f"──────────────────────\n"
        f"Вы приготовили <b>{total_items} порций</b> изысканных блюд! 🍲🍖\n"
        f"🐾 Питомец накормлен до отвала (Сытость: <b>100%</b>) без трат коинов!\n"
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
        markup.add(InlineKeyboardButton("🐾 Открыть Зоомагазин", callback_data=f"shop_cat_pets_0:{user_id}"))
        text = "🐾 <b>У вас пока нет питомца!</b>\n\nКупите верного друга в зоомагазине, чтобы получать бонусы к удаче, охоте и часовому доходу!"
        if message_id:
            try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            except Exception: pass
            return
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
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
        f"🐾 <b>КАРТОЧКА ПИТОМЦА: {pet['name']}</b>\n"
        f"──────────────────────\n"
        f"👤 Хозяин: {make_link(chat_id, user_name, user_id, ping=False)}\n"
        f"⭐ Опыт питомца: <b>{pet.get('pet_exp', 0)} EXP</b>\n"
        f"🍗 Сытость: <b>{pet.get('hunger', 100)}%</b> [{hunger_bar or '❌ Голоден'}]\n"
        f"🧼 Чистота: <b>{pet.get('cleanliness', 100)}%</b> [{clean_bar or '❌ Грязнуля'}]\n"
        f"✨ Бонус: <b>+{pet.get('luck_bonus', 10)}% к удаче</b>\n"
        f"──────────────────────\n"
        f"💡 <i>Используйте кнопки для ухода за питомцем!</i>"
    )

    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception: pass
        return
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['pet', 'питомец', 'пет'])
def cmd_pet(message):
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
        text = "❌ У вас нет питомца! Купите его в <code>/shop</code>."
        bot.send_message(chat_id, text, parse_mode='HTML')
        return

    now = time.time()
    last_walk = econ.get('last_pet_walk', 0)
    cooldown = 10800

    left = cooldown_text(last_walk, cooldown, econ)
    if left:
        msg = f"⏳ Питомец устал! На следующую прогулку можно через: <b>{left}</b>."
        bot.send_message(chat_id, msg, parse_mode='HTML')
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
        res_str = f"💰 Прибыль: <b>+{ev_val} Ня-коинов 🪙</b>!"
    elif ev_type == 'fish':
        add_inventory_item(econ['fish_inventory'], ev_val)
        res_str = f"🐟 Находка: <b>{ev_val}</b>!"

    pet['pet_exp'] = pet.get('pet_exp', 0) + 25
    mark_dirty()

    bot.send_message(
        chat_id,
        f"🦮 <b>ПРОГУЛКА С ПИТОМЦЕМ: {pet['name']}</b>\n"
        f"──────────────────────\n"
        f"Во время прогулки питомец {ev_desc}!\n"
        f"{res_str}\n"
        f"⭐ Опыт питомца: <b>+25 EXP</b>\n"
        f"──────────────────────",
        parse_mode='HTML'
    )

@bot.message_handler(commands=['walk', 'гулять'])
def cmd_walk_pet(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    process_pet_walk(message.chat.id, user_id, user_name)

# ---------------------------------------------------------
# МАГАЗИН СНАСТЕЙ (/gear)
# ---------------------------------------------------------
@bot.message_handler(commands=['gear', 'снасти'])
def cmd_gear(message):
    user_id = message.from_user.id
    lines = [
        "🎣 <b>МАГАЗИН ПРОФЕССИОНАЛЬНЫХ СНАСТЕЙ</b>",
        "──────────────────────",
        "<i>Удочки и луки многократно увеличивают шанс на легендарную и мифическую добычу!</i>\n",
        "<b>Доступные снасти:</b>"
    ]
    for r_id, r in RODS.items(): lines.append(f"• <b>{r['name']}</b> — <code>{r['price']} 🪙</code> (+{r['luck']}% к удаче)")
    for b_id, b in BOWS.items(): lines.append(f"• <b>{b['name']}</b> — <code>{b['price']} 🪙</code> (+{b['luck']}% к удаче)")
    lines.append("──────────────────────")

    markup = InlineKeyboardMarkup(row_width=2)
    rod_btns = [InlineKeyboardButton(f"{r_info['short']} — {r_info['price']} 🪙", callback_data=f"buy_rod_{r_id}:{user_id}") for r_id, r_info in RODS.items()]
    bow_btns = [InlineKeyboardButton(f"{b_info['short']} — {b_info['price']} 🪙", callback_data=f"buy_bow_{b_id}:{user_id}") for b_id, b_info in BOWS.items()]
    
    markup.add(*rod_btns[:2])
    if len(rod_btns) > 2: markup.add(*rod_btns[2:])
    markup.add(*bow_btns[:2])
    if len(bow_btns) > 2: markup.add(*bow_btns[2:])

    bot.reply_to(message, "\n".join(lines), reply_markup=markup, parse_mode='HTML')

# ---------------------------------------------------------
# БИЗНЕСЫ 2.0
# ---------------------------------------------------------
def render_business_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    user_biz = econ.setdefault('businesses', {})
    biz_levels = econ.setdefault('biz_levels', {})

    lines = [
        "🏢 <b>КОММЕРЧЕСКАЯ НЕДВИЖИМОСТЬ И БИЗНЕСЫ 2.0</b>",
        "──────────────────────",
        "Каждое предприятие приносит пассивный доход в час и прокачивается до <b>5 ур.</b>!\n",
        "<b>Каталог предприятий:</b>"
    ]

    markup = InlineKeyboardMarkup(row_width=2)
    for b_id, b_info in BUSINESSES.items():
        if b_id in user_biz:
            lvl = biz_levels.get(b_id, 1)
            upg_cost = b_info['upgrade_cost'] * lvl
            lines.append(f"• <b>{b_info['name']}</b>: Уровень <b>{lvl}/5</b> (Доход: ~{int(b_info['base_income'] * (1 + (lvl-1)*0.45))} 🪙/ч)")
            if lvl < 5:
                markup.add(InlineKeyboardButton(f"⭐ Ап {b_info['short']} (ур. {lvl+1}) — {upg_cost} 🪙", callback_data=f"upg_biz_{b_id}:{user_id}"))
            else:
                markup.add(InlineKeyboardButton(f"👑 {b_info['short']} (МАКС)", callback_data="noop"))
        else:
            lines.append(f"• <b>{b_info['name']}</b> — <code>{b_info['price']} 🪙</code> (Базовый: {b_info['base_income']} 🪙/ч)")
            markup.add(InlineKeyboardButton(f"Купить {b_info['short']} — {b_info['price']} 🪙", callback_data=f"buy_biz_{b_id}:{user_id}"))

    markup.add(InlineKeyboardButton("💰 Собрать всю прибыль", callback_data=f"collect_biz_profit:{user_id}"))
    lines.append("──────────────────────")
    lines.append("🌴 <i>В ресте действует курортный бонус: +20% к прибыли!</i>")

    text = "\n".join(lines)
    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception: pass
        return
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['business', 'бизнес', 'бизнесы', 'biz'])
def cmd_business(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_business_view(message.chat.id, user_id, user_name)

@bot.message_handler(commands=['miner', 'майнер', 'майнинг', 'ферма'])
def cmd_miner(message):
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
            "💻 <b>КРИПТО-МАЙНИНГ СТАНЦИЯ</b>\n"
            "──────────────────────\n"
            "У вас пока не установлена <b>Крипто-Ферма</b>!\n\n"
            "Купите её, чтобы автоматически майнить монеты <b>NYA</b> каждый час и продавать их на бирже на пике цен!\n"
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
        f"💻 <b>ВАША КРИПТО-ФЕРМА (УРОВЕНЬ {lvl}/5)</b>\n"
        f"──────────────────────\n"
        f"👤 Владелец: {make_link(message.chat.id, user_name, user_id, ping=False)}\n"
        f"⚡️ Хешрейт: <b>{lvl * 145} MH/s</b>\n"
        f"💵 Доходность: <b>~{int(280 * (1 + (lvl-1)*0.45))} 🪙 в час</b>\n"
        f"📈 Текущий курс NYA: <b>{nya_price:.2f} 🪙</b>\n"
        f"──────────────────────\n"
        f"💡 Доход накапливается в общем пуле бизнесов! Нажмите кнопку ниже для сбора."
    )
    bot.reply_to(message, text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['collect', 'прибыль'])
def cmd_collect(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    user_biz = econ.get('businesses', {})
    biz_levels = econ.get('biz_levels', {})

    if not user_biz:
        bot.reply_to(message, "❌ У вас нет купленных бизнесов! Откройте <code>бизнесы</code> для покупки.", parse_mode='HTML')
        return

    now = time.time()
    last_collect = econ.get('last_biz_collect', now)
    hours_passed = (now - last_collect) / 3600.0

    if hours_passed < 0.05:
        bot.reply_to(message, "⏳ Прибыль еще не накопилась, загляните чуть позже!")
        return

    base_profit = 0
    for b_id in user_biz.keys():
        if b_id in BUSINESSES:
            lvl = biz_levels.get(b_id, 1)
            inc = int(BUSINESSES[b_id]['base_income'] * (1 + (lvl - 1) * 0.45) * hours_passed)
            base_profit += inc

    if base_profit <= 0:
        bot.reply_to(message, "⏳ Накоплений пока нет, подождите немного!")
        return

    event_text = ""
    if random.random() < 0.15:
        if random.random() < 0.70:
            boost = int(base_profit * 0.5)
            base_profit += boost
            event_text = f"\n🌟 <b>Вирусный тренд в сети!</b> Приток клиентов дал <b>+{boost} 🪙</b>!"
        else:
            tax = int(base_profit * 0.15)
            base_profit -= tax
            event_text = f"\n⚠️ <b>Плановое техобслуживание:</b> расход <b>-{tax} 🪙</b>."

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

    bot.reply_to(message, f"💰 Собрана прибыль предприятий: <b>+{base_profit} Ня-коинов 🪙</b>!{event_text}\nБаланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')

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
        f"🏦 <b>НЯ-БАНК | НАКОПИТЕЛЬНЫЙ СЧЁТ</b>\n"
        f"──────────────────────\n"
        f"👤 Владелец: {make_link(chat_id, user_name, user_id, ping=False)}\n\n"
        f"💳 На депозите: <b>{deposit} Ня-коинов 🪙</b>\n"
        f"💵 В кармане: <b>{pocket} 🪙</b>\n\n"
        f"📈 <b>Ставка:</b> <b>+1% каждые 6 часов</b> (сложный процент!)\n"
        f"🛡 <b>Защита:</b> Депозит защищен от любых карманных краж на 100%!\n"
        f"──────────────────────\n"
        f"💡 <i>Используйте кнопки или команды:</i>\n"
        f"• <code>банк положить 500</code>\n"
        f"• <code>банк снять 500</code>"
    )

    if interest_earned > 0: text += f"\n\n✨ <i>Начислены дивиденды: +{interest_earned} 🪙!</i>"

    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception: pass
        return
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['bank', 'банк', 'депозит'])
def cmd_bank(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_bank_view(message.chat.id, message.from_user.id, user_name)

@bot.message_handler(commands=['case', 'кейс', 'сундук'])
def cmd_case(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    now = time.time()
    last_case = econ.get('last_case_time', 0)
    cooldown = 86400

    left = cooldown_text(last_case, cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Бесплатный кейс доступен раз в 24 часа!\nДо следующего открытия: <b>{left}</b>.", parse_mode='HTML')
        return

    econ['last_case_time'] = now

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
    check_achievements(user_id, user_name, 'cases_opened', 1, message.chat.id, username=message.from_user.username)
    mark_dirty()

    bot.reply_to(
        message,
        f"📦 <b>ВЫ ОТКРЫЛИ ЕЖЕДНЕВНЫЙ СУНДУК!</b>\n"
        f"──────────────────────\n"
        f"🎉 Ваша награда: {prize_str}\n"
        f"⭐ Опыт аккаунта: <b>+20 EXP</b>\n"
        f"──────────────────────\n"
        f"Возвращайтесь за новым сундуком завтра!",
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
        f"🎟 <b>СЕРВЕРНАЯ ДЖЕКПОТ-ЛОТЕРЕЯ</b>\n"
        f"──────────────────────\n"
        f"💰 Текущий Джекпот: <b>{pot} Ня-коинов 🪙</b>\n"
        f"🎫 Продано билетов: <b>{total_tickets}/10</b>\n"
        f"👤 Ваших билетов: <b>{my_tickets} шт.</b>\n"
        f"──────────────────────\n"
        f"📌 При достижении <b>10 билетов</b> бот автоматически разыграет весь банк между участниками!"
    )
    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception: pass
        return
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['lottery', 'лотерея'])
def cmd_lottery(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_lottery_view(message.chat.id, message.from_user.id, user_name)

# ---------------------------------------------------------
# ИСТОРИЯ РЕСТОВ И НАСТРОЙКИ ЧАТА
# ---------------------------------------------------------
@bot.message_handler(commands=['history', 'история'])
def cmd_history(message):
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
        bot.reply_to(message, f"📜 История рестов для <b>{html.escape(clean_u)}</b> в этом чате пуста!", parse_mode='HTML')
        return

    lines = [f"📜 <b>ИСТОРИЯ РЕСТОВ: {make_link(chat_id, clean_u, target_user_id, ping=False)}</b>", "──────────────────────"]
    for idx, item in enumerate(reversed(hist_entries[-8:]), 1):
        lines.append(
            f"<b>{idx}. {item.get('action', 'Рест')}</b> ({item.get('date', '—')})\n"
            f"⏱ Срок: <code>{item.get('duration', '—')}</code> | Причина: <i>{item.get('reason', 'Не указана')}</i>\n"
        )
    lines.append("──────────────────────")
    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')

def render_settings_view(chat_id, user_id=None, message_id=None):
    sett = get_chat_settings(chat_id)
    del_msg_status = "✅ Включено" if sett.get('delete_rest_msg', False) else "❌ Выключено"
    summer_status = "✅ Включена" if sett.get('summer_music', True) else "❌ Выключена"

    uid_tag = f":{user_id}" if user_id else ""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"⏳ Макс. дней реста: {sett['max_days']} дн.", callback_data=f"set_max_days{uid_tag}"))
    markup.add(InlineKeyboardButton(f"🗑 Авто-удаление смс в ресте: {del_msg_status}", callback_data=f"toggle_del_msg{uid_tag}"))
    markup.add(InlineKeyboardButton(f"☀️ Музыка лета каждый час: {summer_status}", callback_data=f"toggle_summer_music{uid_tag}"))
    markup.add(InlineKeyboardButton(f"🔔 Напоминание за: {sett.get('remind_minutes', 60)} мин.", callback_data=f"set_remind_time{uid_tag}"))

    text = (
        f"⚙️ <b>НАСТРОЙКИ НЯ-БОТА ДЛЯ ЧАТА</b>\n"
        f"──────────────────────\n"
        f"• Максимальный срок реста: <b>{sett['max_days']} дней</b>\n"
        f"• Авто-удаление сообщений отдыхающих: <b>{del_msg_status}</b>\n"
        f"• Напоминание об окончании реста: за <b>{sett.get('remind_minutes', 60)} мин.</b>\n"
        f"• Летнее напоминание и трек каждый час: <b>{summer_status}</b>\n"
        f"──────────────────────\n"
        f"<i>Нажимайте кнопки ниже для переключения параметров:</i>"
    )

    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception: pass
        return
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['settings', 'настройки'])
def cmd_settings(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Настройки доступны только администраторам чата!")
        return
    render_settings_view(message.chat.id, message.from_user.id)

# ---------------------------------------------------------
# АВАТАРКА ПРОФИЛЯ
# ---------------------------------------------------------
@bot.message_handler(commands=['set_pfp', 'аватарка'])
def cmd_set_pfp(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    photo_file_id = None
    if message.photo: photo_file_id = message.photo[-1].file_id
    elif message.reply_to_message and message.reply_to_message.photo: photo_file_id = message.reply_to_message.photo[-1].file_id

    if not photo_file_id:
        bot.reply_to(
            message,
            "📸 <b>КАК УСТАНОВИТЬ АВАТАРКУ В ПРОФИЛЬ:</b>\n"
            "──────────────────────\n"
            "1. Отправьте в чат картинку и в подписи (caption) напишите <code>/set_pfp</code>\n"
            "2. Либо ответьте командой <code>/set_pfp</code> на любое сообщение с фото!\n"
            "──────────────────────",
            parse_mode='HTML'
        )
        return

    econ['pfp_file_id'] = photo_file_id
    mark_dirty()
    bot.reply_to(message, "✅ <b>Ваша аватарка профиля успешно установлена!</b>\nПосмотреть: <code>/profile</code>", parse_mode='HTML')

@bot.message_handler(commands=['del_pfp', 'удалить_аватарку'])
def cmd_del_pfp(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    econ['pfp_file_id'] = None
    mark_dirty()
    bot.reply_to(message, "🗑 <b>Аватарка профиля успешно удалена!</b>", parse_mode='HTML')

# ---------------------------------------------------------
# ПРОФИЛЬ И КАРМА
# ---------------------------------------------------------
@bot.message_handler(commands=['custom_title', 'set_title'])
def cmd_custom_title(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    if not econ.get('has_custom_title_cert', False):
        bot.reply_to(message, "❌ У вас нет <b>Сертификата на кастомный титул</b>!\nКупите его в <code>/shop</code> за 15,000 🪙.", parse_mode='HTML')
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "❌ Укажите желаемый титул!\nПример: <code>/custom_title 👑 Главный Кот</code>", parse_mode='HTML')
        return

    new_title = parts[1].strip()[:32]
    econ['custom_title'] = new_title
    econ['active_title'] = None
    mark_dirty()
    bot.reply_to(message, f"🎉 Ваш кастомный титул успешно установлен: <b>[{html.escape(new_title)}]</b>!", parse_mode='HTML')

def send_user_profile(chat_id, user_tag, user_id, message_to_reply=None, message_id_to_edit=None, username=None):
    econ = get_user_econ(user_id, user_tag, username=username)
    theme_key = econ.get('profile_theme', 'default')
    theme_info = THEMES.get(theme_key, THEMES['default'])

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
    
    loan_str = ""
    loan = econ.get('loan')
    if loan and loan.get('amount', 0) > 0:
        loan_str = f"\n{t_icon} 💳 Кредит: <b>-{loan['amount']} 🪙</b>"

    text = (
        f"{header}\n"
        f"{border}\n"
        f"{t_icon} 👤 Игрок: {make_link(chat_id, user_tag, user_id, ping=False)}\n"
        f"{t_icon} ⭐ Уровень: <b>{lvl} LVL</b> [{bar}] (<b>{cur_exp}/{next_exp} EXP</b>)\n"
        f"{t_icon} ⚖️ Карма: <b>{karma}</b> ({karma_title})\n"
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

    if message_id_to_edit:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id_to_edit, reply_markup=markup, parse_mode='HTML')
            return
        except Exception:
            try:
                bot.edit_message_caption(chat_id=chat_id, message_id=message_id_to_edit, caption=text, reply_markup=markup, parse_mode='HTML')
                return
            except Exception: pass

    pfp_id = econ.get('pfp_file_id')
    if pfp_id:
        try:
            if message_to_reply:
                bot.send_photo(chat_id, pfp_id, caption=text, reply_markup=markup, reply_to_message_id=message_to_reply.message_id, parse_mode='HTML')
            else:
                bot.send_photo(chat_id, pfp_id, caption=text, reply_markup=markup, parse_mode='HTML')
            return
        except Exception: pass

    if message_to_reply: bot.reply_to(message_to_reply, text, reply_markup=markup, parse_mode='HTML')
    else: bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

def send_shop_menu(chat_id, user_id, user_tag, message_id=None):
    markup = InlineKeyboardMarkup()
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
        "🏪 <b>ГЛОБАЛЬНЫЙ МАГАЗИН НЯ-БОТА</b>\n"
        "──────────────────────\n"
        "Выберите интересующий вас каталог товаров:"
    )
    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception: pass
        return
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

# ---------------------------------------------------------
# БРАКИ, СЕМЬЯ И ПОДАРКИ
# ---------------------------------------------------------
@bot.message_handler(commands=['marry', 'брак'])
def cmd_marry(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    if econ.get('marriage'):
        bot.reply_to(message, "❌ Вы уже состоите в браке! Чтобы развестись, введите: <code>развод</code>", parse_mode='HTML')
        return

    target_user, target_user_id, _ = parse_target_and_args(message, '/marry')
    if not target_user: target_user, target_user_id, _ = parse_target_and_args(message, 'брак')

    if not target_user:
        bot.reply_to(message, "❌ Укажите пользователя!\nПример: <code>брак @username</code> или ответом на сообщение.", parse_mode='HTML')
        return

    if target_user_id == user_id:
        bot.reply_to(message, "❌ Нельзя заключить брак с самим собой!")
        return
# Проверка, что предложение сделано боту
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
            f"😳👉👈 <b>Ох, семпай... Это так неожиданно и приятно!</b>\n\n"
            f"Я согласна стать твоей вайфу! {ring_emoji}\n\n"
            f"💒 <b>Горько!</b> {u_link} и <b>🤖 {bot_name}</b> теперь официально в браке! 💖🌸",
            parse_mode='HTML'
        )
        return
        
    target_econ = get_user_econ(target_user_id, target_user)
    if target_econ.get('marriage'):
        bot.reply_to(message, f"❌ Пользователь <b>{html.escape(target_user)}</b> уже состоит в браке!", parse_mode='HTML')
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
        f"💖 {to_link}, вам делает предложение руки и сердца {from_link}!\n"
        f"💍 Преподнесенное кольцо: {ring_emoji} <b>{ring_name}</b>\n\n"
        f"Вы согласны соединить свои сердца?",
        reply_markup=markup, parse_mode='HTML'
    )

@bot.message_handler(commands=['family', 'семья'])
def cmd_family(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    if not econ.get('marriage'):
        bot.reply_to(message, "💔 Вы пока не состоите в браке! Сделайте предложение через <code>брак @username</code>.", parse_mode='HTML')
        return

    m = econ['marriage']
    ring_emoji = RINGS.get(m.get('ring'), {}).get('emoji', '💍')
    ring_name = RINGS.get(m.get('ring'), {}).get('name', 'Кольцо')
    days_together = max(1, int((time.time() - m.get('married_at', time.time())) / 86400))
    partner_link = make_link(message.chat.id, m.get('partner_name'), m.get('partner_id'), ping=False)
    vault = m.get('vault', 0)

    text = (
        f"💒 <b>ИНФОРМАЦИЯ О СЕМЬЕ:</b>\n"
        f"──────────────────────\n"
        f"💍 Кольцо: {ring_emoji} <b>{ring_name}</b>\n"
        f"👫 Супруг(а): {partner_link}\n"
        f"⏳ Дней в браке: <b>{days_together} дн.</b>\n"
        f"💰 Семейный сейф: <b>{vault} Ня-коинов 🪙</b>\n"
        f"──────────────────────\n"
        f"💡 <b>Команды семьи:</b>\n"
        f"• <code>подарок</code> — романтический букет (100 🪙)\n"
        f"• <code>семейный сейф положить 100</code>\n"
        f"• <code>семейный сейф снять 100</code>\n"
        f"• <code>развод</code> — расторгнуть брак"
    )
    bot.reply_to(message, text, parse_mode='HTML')

@bot.message_handler(commands=['gift', 'подарок'])
def cmd_gift(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    if not econ.get('marriage'):
        bot.reply_to(message, "❌ Подарки супругу доступны только тем, кто состоит в браке!")
        return

    m = econ['marriage']
    p_id = m.get('partner_id')
    p_tag = m.get('partner_name')

    cost = 100
    if econ['balance'] < cost:
        bot.reply_to(message, f"❌ На роскошный букет нужно <b>{cost} 🪙</b>!")
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
        f"💐 <b>РОМАНТИЧЕСКИЙ ПОДАРОК!</b>\n\n"
        f"{sender_l} преподнес(ла) роскошный букет цветов и сладости для {partner_l}! 💖🍫\n"
        f"Любовь крепнет с каждым днем! (+80 🪙 на счет любимого человека, +3 Карма)",
        parse_mode='HTML'
    )

@bot.message_handler(commands=['divorce', 'развод'])
def cmd_divorce(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    if not econ.get('marriage'):
        bot.reply_to(message, "❌ Вы не состоите в браке!")
        return

    m = econ['marriage']
    p_id = m.get('partner_id')
    p_tag = m.get('partner_name')
    p_econ = get_user_econ(p_id, p_tag)

    vault = m.get('vault', 0)
    split_coins = vault // 2
    econ['balance'] += split_coins
    p_econ['balance'] += (vault - split_coins)
    econ['marriage'] = None
    p_econ['marriage'] = None
    mark_dirty()

    bot.reply_to(message, f"💔 <b>Брак расторгнут.</b>\nСемейный сейф ({vault} 🪙) разделен поровну между бывшими супругами (+{split_coins} 🪙 каждому).", parse_mode='HTML')

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

    if bet <= 0:
        bot.reply_to(message, "❌ Ставка должна быть больше 0!")
        return

    if not check_casino_limits(econ, bet):
        bot.reply_to(message, "❌ Достигнут суточный лимит профита в казино! Приходите завтра.")
        return

    if econ['balance'] < bet:
        bot.reply_to(message, f"❌ Недостаточно Ня-коинов! У вас: {econ['balance']} 🪙")
        return

    econ['balance'] -= bet
    process_casino_bet(bet)

    game_id = f"bj_{user_id}_{int(time.time())}"
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
        f"🃏 <b>БЛЭКДЖЕК (21 ОЧКО)</b>\n──────────────────────\n"
        f"👤 Игрок: {make_link(chat_id, user_name, user_id, ping=True)}\n💰 Ставка: <b>{bet} 🪙</b>\n\n"
        f"🎴 Ваши карты: {p_cards} (Сумма: <b>{p_score}</b>)\n🤖 Дилер: [{d_cards[0]}, ❓]\n──────────────────────",
        reply_markup=markup, parse_mode='HTML'
    )

@bot.message_handler(commands=['bj', 'blackjack', 'блэкджек', '21'])
def cmd_bj(message):
    match = re.search(r'(?:/bj|blackjack|блэкджек|21)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(match.group(1)) if match and match.group(1) else 50
    process_bj_game(message, bet)

@bot.message_handler(commands=['rps', 'цуефа'])
def cmd_rps(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    target_user, target_user_id, raw_args = parse_target_and_args(message, '/rps')
    if not target_user: target_user, target_user_id, raw_args = parse_target_and_args(message, 'цуефа')

    match = re.search(r'(\d+)', raw_args)
    bet = int(match.group(1)) if match else 50

    if not target_user:
        bot.reply_to(message, "❌ Формат: <code>/rps @username 100</code> или ответом на сообщение.", parse_mode='HTML')
        return

    if target_user_id == user_id:
        bot.reply_to(message, "❌ Нельзя играть с самим собой!")
        return

    target_econ = get_user_econ(target_user_id, target_user)
    if econ['balance'] < bet or target_econ['balance'] < bet:
        bot.reply_to(message, "❌ У одного из участников недостаточно коинов для ставки!")
        return

    game_id = f"rps_{user_id}_{target_user_id or 0}_{int(time.time())}"
    active_rps_games[game_id] = {
        'p1_id': user_id, 'p1_tag': user_name,
        'p2_id': target_user_id, 'p2_tag': target_user,
        'bet': bet, 'p1_choice': None, 'p2_choice': None, 'start_time': time.time()
    }

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🪨 Камень", callback_data=f"rps_r_{game_id}"),
        InlineKeyboardButton("✂️ Ножницы", callback_data=f"rps_s_{game_id}"),
        InlineKeyboardButton("📄 Бумага", callback_data=f"rps_p_{game_id}")
    )

    bot.send_message(
        chat_id,
        f"✌️ <b>ДУЭЛЬ: КАМЕНЬ-НОЖНИЦЫ-БУМАГА!</b>\n──────────────────────\n"
        f"⚔️ {make_link(chat_id, user_name, user_id, ping=True)} VS {make_link(chat_id, target_user, target_user_id, ping=True)}\n"
        f"💰 Ставка: <b>{bet} 🪙</b> с каждого!\n──────────────────────\n"
        f"<i>Оба участника, нажмите свой тайный выбор на кнопках ниже:</i>",
        reply_markup=markup, parse_mode='HTML'
    )

# ---------------------------------------------------------
# КРИПТО-БИРЖА И ТОРГОВЛЯ
# ---------------------------------------------------------
@bot.message_handler(commands=['market', 'биржа', 'crypto', 'крипта'])
def cmd_market(message):
    market = get_market_data()
    lines = [
        "📈 <b>НЯ-БИРЖА КРИПТОВАЛЮТ И АКЦИЙ</b>",
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

    lines.append("──────────────────────\n💡 <b>Как торговать:</b>")
    lines.append("• <code>купить крипту NYA 5</code>\n• <code>продать крипту NYA 5</code>\n• <code>портфель</code> — посмотреть свои активы")
    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')

@bot.message_handler(commands=['portfolio', 'портфель'])
def cmd_portfolio(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    market = get_market_data()

    portfolio = econ.get('crypto_portfolio', {})
    total_val = 0.0
    lines = [f"💼 <b>ИНВЕСТИЦИОННЫЙ ПОРТФЕЛЬ: {make_link(message.chat.id, user_name, user_id, ping=False)}</b>", "──────────────────────"]

    has_assets = False
    for ticker, amount in portfolio.items():
        if amount > 0.0001:
            has_assets = True
            cur_price = market.get(ticker, {}).get('price', 1.0)
            val = amount * cur_price
            total_val += val
            lines.append(f"• <b>{ticker}</b>: {amount:.2f} шт. (Оценка: <b>{val:.2f} 🪙</b>)")

    if not has_assets: lines.append("🎒 Ваш крипто-портфель пока пуст! Купите активы в <code>биржа</code>.")
    else: lines.extend(["──────────────────────", f"📊 <b>Общая стоимость: {total_val:.2f} Ня-коинов 🪙</b>"])
    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')

def trade_crypto(chat_id, user_id, user_tag, action, ticker, amount_str, reply_msg=None, username=None):
    market = get_market_data()
    ticker = ticker.upper().strip()

    if ticker not in market:
        available = ', '.join(market.keys())
        msg = f"❌ Неверный тикер! Доступные активы: <b>{available}</b>"
        if reply_msg: bot.reply_to(reply_msg, msg, parse_mode='HTML')
        else: bot.send_message(chat_id, msg, parse_mode='HTML')
        return

    try:
        amount = float(amount_str)
        if amount <= 0: raise ValueError
    except ValueError:
        msg = "❌ Укажите корректное положительное число монет!"
        if reply_msg: bot.reply_to(reply_msg, msg, parse_mode='HTML')
        else: bot.send_message(chat_id, msg, parse_mode='HTML')
        return

    econ = get_user_econ(user_id, user_tag, username=username)
    portfolio = econ.setdefault('crypto_portfolio', {})
    asset = market[ticker]
    price = asset['price']
    total_cost = round(price * amount, 2)

    if action == 'buy':
        if econ['balance'] < total_cost:
            msg = f"❌ Недостаточно коинов! Нужно <b>{total_cost:.2f} 🪙</b> (У вас: {econ['balance']} 🪙)."
            if reply_msg: bot.reply_to(reply_msg, msg, parse_mode='HTML')
            else: bot.send_message(chat_id, msg, parse_mode='HTML')
            return

        econ['balance'] -= int(total_cost)
        portfolio[ticker] = portfolio.get(ticker, 0.0) + amount
        check_achievements(user_id, user_tag, 'crypto_trades', 1, chat_id, username=username)
        add_account_exp(user_id, user_tag, 10, username=username)
        mark_dirty()

        msg = f"✅ <b>УСПЕШНАЯ ПОКУПКА!</b>\n──────────────────────\nКуплено: <b>{amount:.2f} {ticker}</b> ({asset['name']})\nСписано: <b>-{total_cost:.2f} 🪙</b>\nОстаток баланса: <b>{econ['balance']} 🪙</b>"
        if reply_msg: bot.reply_to(reply_msg, msg, parse_mode='HTML')
        else: bot.send_message(chat_id, msg, parse_mode='HTML')

    elif action == 'sell':
        user_amount = portfolio.get(ticker, 0.0)
        if user_amount < amount:
            msg = f"❌ Недостаточно {ticker}! В наличии: <b>{user_amount:.2f} шт.</b>"
            if reply_msg: bot.reply_to(reply_msg, msg, parse_mode='HTML')
            else: bot.send_message(chat_id, msg, parse_mode='HTML')
            return

        portfolio[ticker] -= amount
        if portfolio[ticker] <= 0.0001: del portfolio[ticker]

        earned = int(total_cost)
        econ['balance'] += earned
        check_achievements(user_id, user_tag, 'crypto_trades', 1, chat_id, username=username)
        add_account_exp(user_id, user_tag, 10, username=username)
        mark_dirty()

        msg = f"💰 <b>УСПЕШНАЯ ПРОДАЖА!</b>\n──────────────────────\nПродано: <b>{amount:.2f} {ticker}</b>\nВыручка: <b>+{earned} 🪙</b>\nНовый баланс: <b>{econ['balance']} 🪙</b>"
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
    if left: return False, f"⏳ Тренировка доступна раз в 15 минут! Ждать: <b>{left}</b>."

    gain = random.randint(15, 40)
    econ['work_exp'] = econ.get('work_exp', 0) + gain
    econ['last_train_time'] = now
    add_account_exp(user_id, user_tag, gain, username=username)
    mark_dirty()
    return True, f"🎓 Вы усердно позанимались!\nПолучено: <b>+{gain} EXP</b> опыта работы (Всего: <b>{econ['work_exp']} EXP</b>)."

@bot.message_handler(commands=['work', 'работа'])
def cmd_work(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    lines = [
        "💼 <b>БИРЖА ТРУДА И ВАКАНСИЙ</b>",
        "──────────────────────",
        f"👤 Ваш опыт работы: <b>{econ.get('work_exp', 0)} EXP</b>\n",
        "<b>Доступные вакансии:</b>"
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
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    _, text_resp = train_work_exp(user_id, user_name, username=message.from_user.username)
    bot.reply_to(message, text_resp, parse_mode='HTML')

@bot.message_handler(commands=['sell', 'продать'])
def cmd_sell(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    total_earned = 0
    items_sold = 0
    price_multiplier = 1.5 if gold_rush_event.get('active') else 1.0

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
        bot.reply_to(message, "🎒 У вас нет рыбы или охотничьих трофеев для продажи!")
        return

    econ['balance'] += total_earned
    mark_dirty()
    rush_note = " (🌟 Золотая лихорадка x1.5!)" if gold_rush_event.get('active') else ""
    bot.reply_to(message, f"💰 Вы успешно продали добычу на сумму <b>+{total_earned} Ня-коинов 🪙</b>{rush_note}!\nБаланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')

@bot.message_handler(commands=['profile', 'профиль'])
def cmd_profile(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    send_user_profile(message.chat.id, user_name, message.from_user.id, message_to_reply=message, username=message.from_user.username)

@bot.message_handler(commands=['achievements', 'ачивки'])
def cmd_achievements(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    unlocked = econ.get('achievements', [])

    lines = [f"🏆 <b>ДОСТИЖЕНИЯ: {make_link(message.chat.id, user_name, user_id, ping=False)}</b>", "──────────────────────"]
    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id in unlocked: lines.append(f"✅ <b>{ach['title']}</b> — {ach['desc']} (+{ach['reward']} 🪙)")
        else: lines.append(f"🔒 <b>{ach['title']}</b> — {ach['desc']} (<b>+{ach['reward']} 🪙</b>)")
    lines.append("──────────────────────")
    lines.append(f"Прогресс: <b>{len(unlocked)}/{len(ACHIEVEMENTS)}</b> открыто.")
    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')

@bot.message_handler(commands=['balance', 'баланс'])
def cmd_balance(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(message.from_user.id, user_name, username=message.from_user.username)
    bot.reply_to(message, f"💵 <b>Ваш кошелек:</b> <b>{econ['balance']} Ня-коинов 💸</b>\n🏦 <b>В банке:</b> <b>{econ.get('bank_deposit', 0)} 🪙</b>", parse_mode='HTML')

@bot.message_handler(commands=['shop', 'магазин'])
def cmd_shop(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    send_shop_menu(message.chat.id, message.from_user.id, user_name)

@bot.message_handler(commands=['tasks', 'задания', 'квесты'])
def cmd_tasks(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    bot.reply_to(message, format_daily_tasks(message.from_user.id, user_name), parse_mode='HTML')

# ---------------------------------------------------------
# БИОМЕТРИЯ: IQ, ЖИР, ПЯТКА, ХРОМОСОМЫ
# ---------------------------------------------------------
@bot.message_handler(commands=['iq'])
def cmd_iq(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    now_ts = time.time()
    cooldown = 1800
    left = cooldown_text(econ.get('last_iq_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Тест на IQ доступен раз в 30 минут!\nПодождите: <b>{left}</b>.", parse_mode='HTML')
        return

    change = random.randint(-5, 15)
    econ['iq'] = max(0, econ.get('iq', 100) + change)
    econ['last_iq_time'] = now_ts
    mark_dirty()
    completed = track_daily_task(user_id, user_name, 'iq', 1, chat_id, username=message.from_user.username)
    sign = "+" if change >= 0 else ""
    bot.reply_to(message, f"🧠 {make_link(chat_id, user_name, user_id, ping=True)}, ваш IQ: <b>{econ['iq']} ({sign}{change}) 📊</b>", parse_mode='HTML')
    for task_name, task_reward in completed: bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')

@bot.message_handler(commands=['fat'])
def cmd_fat(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    now_ts = time.time()
    cooldown = 1800
    left = cooldown_text(econ.get('last_fat_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Замер жира доступен раз в 30 минут!\nПодождите: <b>{left}</b>.", parse_mode='HTML')
        return

    change = random.randint(-4, 6)
    econ['fat'] = max(0, min(100, econ.get('fat', 20) + change))
    econ['last_fat_time'] = now_ts
    mark_dirty()
    completed = track_daily_task(user_id, user_name, 'fat', 1, chat_id, username=message.from_user.username)
    sign = "+" if change >= 0 else ""
    bot.reply_to(message, f"🥩 {make_link(chat_id, user_name, user_id, ping=True)}, процент жира: <b>{econ['fat']}% ({sign}{change}%) 🍔</b>", parse_mode='HTML')
    for task_name, task_reward in completed: bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')

@bot.message_handler(commands=['foot'])
def cmd_foot(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    now_ts = time.time()
    cooldown = 1200
    left = cooldown_text(econ.get('last_foot_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Измерить пятку можно раз в 20 минут!\nПодождите: <b>{left}</b>.", parse_mode='HTML')
        return

    change = random.randint(-3, 4)
    econ['foot_size'] = max(5, min(80, econ.get('foot_size', 25) + change))
    econ['last_foot_time'] = now_ts
    mark_dirty()
    sign = "+" if change >= 0 else ""
    bot.reply_to(message, f"🦶 {make_link(chat_id, user_name, user_id, ping=True)}, размер пятки: <b>{econ['foot_size']} см ({sign}{change} см) 🦶</b>", parse_mode='HTML')

@bot.message_handler(commands=['chromosomes', 'хромосомы', 'хромосома'])
def cmd_chromosomes(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)
    now_ts = time.time()
    cooldown = 1200
    left = cooldown_text(econ.get('last_chromosomes_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"🧬 Генетический анализ доступен раз в 20 минут!\nПодождите: <b>{left}</b>.", parse_mode='HTML')
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

    if new_chr == 46: comment = "Идеальный человеческий баланс! ✨"
    elif new_chr == 47: comment = "Обнаружена экстра-хромосома сверхразума! ⚡️"
    elif new_chr > 47: comment = "Межгалактический уровень ДНК! 👽🚀"
    else: comment = "Кажется, пара хромосом взяли отгул... 🔍"

    u_link = make_link(chat_id, user_name, user_id, ping=True)
    bot.reply_to(message, f"🧬 <b>ГЕНЕТИЧЕСКИЙ ТЕСТ:</b> {u_link}\n──────────────────────\nКоличество хромосом: <b>{new_chr} ({sign}{change}) 🧬</b>\n📝 <i>{comment}</i>\n──────────────────────", parse_mode='HTML')
    for task_name, task_reward in completed: bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')

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

    visible_items = {k: v for k, v in econ_items.items() if category in ['rich', 'msg', 'karma'] or v.get('invis_until', 0) <= now}

    if category == 'rich':
        sorted_data = sorted(visible_items.items(), key=lambda x: (x[1].get('balance', 0) + x[1].get('bank_deposit', 0)), reverse=True)
        title = "🏆 <b>ТОП БОГАЧЕЙ ЧАТА (Карман + Банк)</b>"
        val_formatter = lambda info: f"<b>{info.get('balance', 0) + info.get('bank_deposit', 0)} 🪙</b>"
    elif category == 'dick':
        sorted_data = sorted(visible_items.items(), key=lambda x: x[1].get('dick_size', 15), reverse=True)
        title = "🍆 <b>ТОП ПО РАЗМЕРУ ПИСЮНА</b>"
        val_formatter = lambda info: f"<b>{info.get('dick_size', 15)} см 📏</b>"
    elif category == 'iq':
        sorted_data = sorted(visible_items.items(), key=lambda x: x[1].get('iq', 100), reverse=True)
        title = "🧠 <b>ТОП ПО УРОВНЮ IQ</b>"
        val_formatter = lambda info: f"<b>{info.get('iq', 100)} IQ</b>"
    elif category == 'karma':
        sorted_data = sorted(visible_items.items(), key=lambda x: x[1].get('karma', 0), reverse=True)
        title = "⚖️ <b>ТОП КАРМЫ (Самые Светлые)</b>"
        val_formatter = lambda info: f"<b>{info.get('karma', 0)} 😇</b>"
    elif category == 'foot':
        sorted_data = sorted(visible_items.items(), key=lambda x: x[1].get('foot_size', 25), reverse=True)
        title = "🦶 <b>ТОП ПО РАЗМЕРУ ПЯТКИ</b>"
        val_formatter = lambda info: f"<b>{info.get('foot_size', 25)} см 🦶</b>"
    elif category == 'chr':
        sorted_data = sorted(visible_items.items(), key=lambda x: x[1].get('chromosomes', 46), reverse=True)
        title = "🧬 <b>ТОП ПО КОЛИЧЕСТВУ ХРОМОСОМ</b>"
        val_formatter = lambda info: f"<b>{info.get('chromosomes', 46)} 🧬</b>"
    elif category == 'msg':
        sorted_data = sorted(visible_items.items(), key=lambda x: x[1].get('msg_stats', {}).get('total_count', 0), reverse=True)
        title = "💬 <b>ТОП ПО СООБЩЕНИЯМ В ЧАТЕ</b>"
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

    if not sorted_data: lines.append("<i>Данных для отображения пока нет...</i>")
    lines.extend(["──────────────────────", "👇 <i>Нажмите категорию ниже для переключения:</i>"])

    text = "\n".join(lines)
    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception: pass
        return
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['top', 'топ'])
def cmd_top(message):
    render_top_menu(message.chat.id, user_id=message.from_user.id, category='rich')

# ---------------------------------------------------------
# ГЛАВНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ И КОМАНД
# ---------------------------------------------------------
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    text = message.text.strip() if message.text else ''
    chat_id = message.chat.id
    str_chat = str(chat_id)
    user_id = message.from_user.id
    user_username = (message.from_user.username or '').lower()
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username or 'Пользователь'
    text_lower = text.lower()
    now_ts = time.time()

    is_super_admin = (user_username == ADMIN_USERNAME.lower())

    # 🛑 ПРОВЕРКА РЕЖИМА ОБСЛУЖИВАНИЯ / СНА
    bot_is_active = db.get('bot_active', True)
    if not bot_is_active:
        if is_super_admin and text_lower in ['/start_bot', '/resume', 'включить бота', 'запустить бота']:
            db['bot_active'] = True
            save_data()
            log_event('ВКЛЮЧЕНИЕ', f'Бот возобновил работу по команде @{user_username}')
            bot.reply_to(message, "🟢 <b>Бот успешно включен и возобновил работу!</b>", parse_mode='HTML')
            return
        elif is_super_admin: pass
        else: return

    last_chat_activity[chat_id] = now_ts

    # 🛡 АНТИ-ФЛУД
    econ = get_user_econ(user_id, user_name, username=user_username)
    if text_lower.startswith('/') or any(kw in text_lower for kw in ['рест', 'профиль', 'баланс', 'топ', 'шанс']):
        if (now_ts - econ.get('last_cmd_time', 0)) < 3.0 and econ.get('last_cmd_text') == text_lower:
            return 
        econ['last_cmd_time'] = now_ts
        econ['last_cmd_text'] = text_lower

    if user_id in user_flood_muted:
        if now_ts < user_flood_muted[user_id]: return
        else: del user_flood_muted[user_id]

    user_hist = user_flood_history.setdefault(user_id, [])
    user_hist.append(now_ts)
    user_flood_history[user_id] = [t for t in user_hist if now_ts - t <= 3.0]
    if len(user_flood_history[user_id]) >= 5:
        user_flood_muted[user_id] = now_ts + 25
        u_link = make_link(chat_id, user_name, user_id, ping=True)
        bot.send_message(chat_id, f"🧊 {u_link}, <b>остудись!</b> Слишком частые команды (заморозка на 25 сек).", parse_mode='HTML')
        return

    add_message_stat(user_id, user_name, username=user_username)

    # ПОВТОРЯЛКА (БОТ СКАЖИ ...)
    m_say = re.match(r'^(?:бот,?\s+)?скажи\s+(.+)$', text, re.IGNORECASE)
    if m_say:
        phrase = m_say.group(1).strip()
        bot.send_message(chat_id, phrase)
        return
    # 🎭 СЛУЧАЙНЫЕ РЕАКЦИИ
    if random.random() < 0.04 and len(text) > 2:
        try:
            rx_list = ['🔥', '🗿', '❤️', '👍', '⚡️', '🤡', '🎉', '👀', '👏', '💔']
            chosen_rx = random.choice(rx_list)
            bot.set_message_reaction(chat_id, message.message_id, [ReactionTypeEmoji(chosen_rx)])
        except Exception: pass

    # 🧮 БЕЗОПАСНЫЙ КАЛЬКУЛЯТОР
    calc_match = None
    m_calc_cmd = re.match(r'^(?:/calc|посчитай|вычисли|реши|сколько\s+будет)\s+([\d\s\+\-\*\/\%\(\)\^\.\:×÷]+)$', text, re.IGNORECASE)
    if m_calc_cmd: calc_match = m_calc_cmd.group(1).strip()
    elif re.match(r'^\s*\(?\d+[\d\s\+\-\*\/\%\(\)\^\.\:×÷]*\d+\)?\s*$', text):
        if any(op in text for op in ['+', '*', '/', '%', '^', '×', '÷']) or ('-' in text and not re.search(r'[a-zA-Zа-яА-Я]', text)):
            calc_match = text.strip()

    if calc_match:
        calc_res = safe_calculate_math(calc_match)
        if calc_res is not None:
            bot.reply_to(message, f"🧮 <b>Результат:</b> <code>{calc_res}</code>", parse_mode='HTML')
            return

    # ⚡️ ВИКТОРИНА
    if current_quiz.get('answer') and current_quiz.get('chat_id') == chat_id:
        if text_lower == current_quiz['answer']:
            reward = current_quiz['reward']
            current_quiz['answer'] = None
            add_coins(user_id, user_name, reward, username=user_username)
            add_account_exp(user_id, user_name, 20, username=user_username)
            u_link = make_link(chat_id, user_name, user_id, ping=True)
            bot.reply_to(message, f"🎉 <b>ПРАВИЛЬНЫЙ ОТВЕТ!</b>\n\nПервым(ой) правильно ответил(а) {u_link} и получает <b>+{reward} Ня-коинов 🪙</b> (+20 EXP)!", parse_mode='HTML')
            return

    # 👑 КОМАНДЫ СОЗДАТЕЛЯ (GOD MODE)
    if is_super_admin:
        if text_lower in ['/admin', '/admin_help', 'админ', 'админка']:
            admin_help_text = (
                "👑 <b>ПАНЕЛЬ УПРАВЛЕНИЯ СОЗДАТЕЛЯ (@ukrgorilka):</b>\n"
                "──────────────────────\n"
                "• <code>/stop_bot</code> — спящий режим\n"
                "• <code>/start_bot</code> — возобновить работу\n"
                "• <code>/take_coins @user 500</code> — списать коины\n"
                "• <code>/give_coins @user 1000</code> — выдать коины\n"
                "• <code>/inspect @user</code> — осмотр игрока (God Mode)\n"
                "• <code>/set_karma @user 100</code> — изменить карму\n"
                "• <code>/force_divorce @user</code> — принудительный развод\n"
                "• <code>/give_item @user item_name</code> — выдать предмет\n"
                "• <code>/wipe @user</code> — обнулить профиль\n"
                "──────────────────────"
            )
            bot.reply_to(message, admin_help_text, parse_mode='HTML')
            return

        if text_lower in ['/stop_bot', '/shutdown', 'выключить бота', 'остановить бота']:
            db['bot_active'] = False
            save_data(send_backup=True)
            log_event('ОСТАНОВКА', f'Бот переведён в спящий режим администратором @{user_username}')
            bot.reply_to(message, "🛑 <b>Бот переведён в спящий режим (технические работы).</b>", parse_mode='HTML')
            return

        # GOD MODE: Inspect User
        if text_lower.startswith('/inspect'):
            t_name, t_id, _ = parse_target_and_args(message, '/inspect')
            if not t_id:
                bot.reply_to(message, "❌ Укажите юзера.")
                return
            te = get_user_econ(t_id, t_name)
            bot.reply_to(message, f"👁 <b>GOD INSPECT:</b> {t_name} ({t_id})\nБаланс: {te['balance']}\nБанк: {te.get('bank_deposit', 0)}\nКарма: {te.get('karma', 0)}\nEXP: {te.get('account_exp', 0)}\nПредметы: {te.get('inventory')}", parse_mode='HTML')
            return

        # GOD MODE: Set Karma
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

        # GOD MODE: Force Divorce
        if text_lower.startswith('/force_divorce'):
            t_name, t_id, _ = parse_target_and_args(message, '/force_divorce')
            if not t_id: return
            te = get_user_econ(t_id, t_name)
            if te.get('marriage'):
                p_id = te['marriage']['partner_id']
                pe = get_user_econ(p_id)
                te['marriage'] = None
                pe['marriage'] = None
                mark_dirty()
                bot.reply_to(message, f"✅ Игрок {t_name} принудительно разведен.")
            else:
                bot.reply_to(message, "❌ Игрок не в браке.")
            return

        # GOD MODE: Wipe User
        if text_lower.startswith('/wipe'):
            t_name, t_id, _ = parse_target_and_args(message, '/wipe')
            if not t_id: return
            db['economy'][get_global_user_key(t_id)] = {'display_name': t_name, 'user_id': t_id, 'balance': 0, 'karma': 0}
            mark_dirty()
            bot.reply_to(message, f"💀 Аккаунт {t_name} полностью ВАЙПНУТ (Обнулен).")
            return
            
        # GOD MODE: Give Item
        if text_lower.startswith('/give_item'):
            t_name, t_id, item = parse_target_and_args(message, '/give_item')
            if not t_id or not item: return
            te = get_user_econ(t_id, t_name)
            te.setdefault('inventory', []).append(item)
            mark_dirty()
            bot.reply_to(message, f"✅ Предмет {item} выдан {t_name}.")
            return

        # Take Coins
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

        # Give Coins
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
            bot.reply_to(message, "❌ Вы не состоите в браке!")
            return
        m = econ['marriage']
        p_id = m.get('partner_id')
        p_tag = m.get('partner_name')
        p_econ = get_user_econ(p_id, p_tag)
        m_amt = re.search(r'(\d+)', text_lower)
        if 'положить' in text_lower and m_amt:
            amt = int(m_amt.group(1))
            if amt <= 0 or econ['balance'] < amt:
                bot.reply_to(message, f"❌ Недостаточно средств на руках! У вас: {econ['balance']} 🪙")
                return
            econ['balance'] -= amt
            m['vault'] = m.get('vault', 0) + amt
            if p_econ.get('marriage'): p_econ['marriage']['vault'] = m['vault']
            mark_dirty()
            bot.reply_to(message, f"💍 Вы положили <b>{amt} 🪙</b> в семейный сейф!\nВ сейфе: <b>{m['vault']} 🪙</b>", parse_mode='HTML')
            return
        elif 'снять' in text_lower and m_amt:
            amt = int(m_amt.group(1))
            cur_vault = m.get('vault', 0)
            if amt <= 0 or cur_vault < amt:
                bot.reply_to(message, f"❌ В сейфе недостаточно коинов! Накоплено: {cur_vault} 🪙")
                return
            m['vault'] -= amt
            if p_econ.get('marriage'): p_econ['marriage']['vault'] = m['vault']
            econ['balance'] += amt
            mark_dirty()
            bot.reply_to(message, f"💸 Вы взяли <b>{amt} 🪙</b> из семейного сейфа!\nОстаток: <b>{m['vault']} 🪙</b>", parse_mode='HTML')
            return

    # КВЕСТ СООБЩЕНИЙ
    completed_tasks = track_daily_task(user_id, user_name, 'messages', 1, chat_id, username=user_username)
    if completed_tasks:
        for task_name, reward in completed_tasks:
            try: bot.send_message(chat_id, f'🎉 {make_link(chat_id, user_name, user_id, ping=True)} выполнил(а) задание: <b>{task_name}</b>! +{reward} 🪙', parse_mode='HTML')
            except Exception: pass

    if re.search(r'\b(почему|почему\??)\b', text_lower, re.IGNORECASE):
        chosen_msg_id = random.choice(WHY_TG_MSG_IDS)
        copied = False
        try:
            bot.copy_message(chat_id, from_chat_id=MEDIA_TG_CHAT_ID, message_id=chosen_msg_id, reply_to_message_id=message.message_id)
            copied = True
        except Exception: pass
        if not copied:
            chosen_gif = random.choice(WHY_GIFS)
            try: bot.send_animation(chat_id, chosen_gif, reply_to_message_id=message.message_id)
            except Exception: bot.reply_to(message, chosen_gif)
        return

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
            bot.reply_to(message, "❌ Укажите жертву: <code>ограбить @username</code> или ответом на сообщение!", parse_mode='HTML')
            return

        econ = get_user_econ(user_id, user_name, username=user_username)
        if econ['balance'] < 30:
            bot.reply_to(message, "❌ Чтобы пойти на дело, нужно иметь в кармане хотя бы <b>30 🪙</b> (на случай штрафа)!", parse_mode='HTML')
            return

        now = time.time()
        cooldown = 3600
        left = cooldown_text(econ.get('last_rob_time', 0), cooldown, econ)
        if left:
            bot.reply_to(message, f"⏳ Полиция на хвосте! Ограбление доступно через: <b>{left}</b>.", parse_mode='HTML')
            return

        t_econ = get_user_econ(target_user_id, target_user)
        t_pocket = t_econ.get('balance', 0)
        if t_pocket < 50:
            bot.reply_to(message, "❌ У жертвы меньше 50 коинов на руках! Деньги в банке защищены на 100%.", parse_mode='HTML')
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
            mark_dirty()
            u_link = make_link(chat_id, user_name, user_id, ping=True)
            t_link = make_link(chat_id, target_user, target_user_id, ping=True)
            bot.send_message(chat_id, f"🚨🔊 <b>СИГНАЛИЗАЦИЯ СРАБОТАЛА!</b>\n\n{u_link} попытался проникнуть в карман {t_link}, но сработала <b>Охранная сигнализация</b>!\nВор оглушен электрошокером и выплатил компенсацию <b>-{fine} 🪙</b> в пользу жертвы! (Карма -5)", parse_mode='HTML')
            return

        rob_chance = 0.40
        if econ.get('pet') and econ['pet'].get('id') == 'raccoon': rob_chance += 0.20

        if random.random() <= rob_chance:
            stolen = max(10, min(600, int(t_pocket * random.uniform(0.10, 0.20))))
            t_econ['balance'] -= stolen
            econ['balance'] += stolen
            change_karma(user_id, user_name, -5)
            mark_dirty()
            u_link = make_link(chat_id, user_name, user_id, ping=True)
            t_link = make_link(chat_id, target_user, target_user_id, ping=True)
            bot.send_message(chat_id, f"🥷 <b>УДАЧНОЕ ОГРАБЛЕНИЕ!</b>\n\n{u_link} ловко украл у {t_link} <b>{stolen} Ня-коинов 🪙</b>! (Карма -5)", parse_mode='HTML')
        else:
            fine = min(econ['balance'], random.randint(30, 90))
            if econ.get('active_title') == 'shadow_ninja': fine = int(fine * 0.5)
            econ['balance'] -= fine
            t_econ['balance'] += fine
            change_karma(user_id, user_name, -3)
            mark_dirty()
            u_link = make_link(chat_id, user_name, user_id, ping=True)
            t_link = make_link(chat_id, target_user, target_user_id, ping=True)
            bot.send_message(chat_id, f"🚨 <b>ПРОВАЛ ОГРАБЛЕНИЯ!</b>\n\n{u_link} попался с поличным и выплатил {t_link} компенсацию: <b>-{fine} 🪙</b>! (Карма -3)", parse_mode='HTML')
        return

    # БАНК ТЕКСТОМ
    if text_lower.startswith(('банк положить', 'депозит')):
        econ = get_user_econ(user_id, user_name, username=user_username)
        m_amt = re.search(r'(\d+)', text)
        if m_amt:
            amt = int(m_amt.group(1))
            if amt <= 0 or econ['balance'] < amt:
                bot.reply_to(message, f"❌ Недостаточно средств на руках! У вас: {econ['balance']} 🪙")
                return
            econ['balance'] -= amt
            econ['bank_deposit'] = econ.get('bank_deposit', 0) + amt
            econ['last_bank_calc'] = time.time()
            check_achievements(user_id, user_name, 'bank_deposit', amt, chat_id, username=user_username)
            mark_dirty()
            bot.reply_to(message, f"🏦 Вы внесли <b>{amt} 🪙</b> на депозит в Ня-Банк!\nНа депозите: <b>{econ['bank_deposit']} 🪙</b>", parse_mode='HTML')
        return
    elif text_lower.startswith('банк снять всё'):
        econ = get_user_econ(user_id, user_name, username=user_username)
        dep = econ.get('bank_deposit', 0)
        if dep <= 0:
            bot.reply_to(message, "❌ Ваш банковский депозит пуст!")
            return
        econ['balance'] += dep
        econ['bank_deposit'] = 0
        econ['last_bank_calc'] = time.time()
        mark_dirty()
        bot.reply_to(message, f"💸 Вы забрали весь вклад из банка: <b>+{dep} 🪙</b>!\nБаланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
        return
    elif text_lower.startswith('банк снять'):
        econ = get_user_econ(user_id, user_name, username=user_username)
        m_amt = re.search(r'(\d+)', text)
        if m_amt:
            amt = int(m_amt.group(1))
            dep = econ.get('bank_deposit', 0)
            if amt <= 0 or dep < amt:
                bot.reply_to(message, f"❌ В банке недостаточно средств! На депозите: {dep} 🪙")
                return
            econ['bank_deposit'] -= amt
            econ['balance'] += amt
            econ['last_bank_calc'] = time.time()
            mark_dirty()
            bot.reply_to(message, f"💸 Вы сняли <b>{amt} 🪙</b> с банковского счёта!\nОстаток в банке: <b>{econ['bank_deposit']} 🪙</b>", parse_mode='HTML')
        return

    # ОДИНОЧНЫЕ РП
    for solo_cmd, (solo_text, solo_emoji) in RP_SOLO_ACTIONS.items():
        if text_lower == solo_cmd or text_lower.startswith(f"{solo_cmd} "):
            sender_link = make_link(chat_id, user_name, user_id, ping=True)
            check_achievements(user_id, user_name, 'rp_actions', 1, chat_id, username=user_username)
            add_account_exp(user_id, user_name, 3, username=user_username)
            bot.send_message(chat_id, f"{solo_emoji} {sender_link} {solo_text}", parse_mode='HTML')
            return

    # ПАРНЫЕ РП И КАРМА
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
                    bot.reply_to(message, "❌ Вы не можете использовать это действие на себе!")
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
                else: k_str = ""
                bot.send_message(chat_id, f"{rp_data['emoji']} {sender_link} <b>{rp_data['verb']}</b> {target_link}!{k_str}", parse_mode='HTML')
                return
            else:
                bot.reply_to(message, f"💡 Ответьте на сообщение или укажите ник:\n<code>{rp_cmd} @username</code>", parse_mode='HTML')
                return

    # КТО ТЫ @username
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
            bot.reply_to(message, f"🌴 <b>Пользователь {user_link} находится в ресте!</b>\n📝 <b>Причина:</b> {html.escape(rest_info.get('reason', 'Не указана'))}\n⏱ <b>Срок:</b> {html.escape(rest_info.get('duration', 'Не указан'))}", parse_mode='HTML')
        else:
            display_name = target_found_name or 'Пользователь'
            user_link = make_link(chat_id, display_name, target_found_id, ping=False)
            bot.reply_to(message, f"✅ Пользователь {user_link} сейчас не находится в ресте!", parse_mode='HTML')
        return

    for pattern, responses in ALWAYS_ACTIVE_PATTERNS.items():
        if re.search(pattern, text_lower, re.IGNORECASE):
            bot.reply_to(message, random.choice(responses))
            break

    # АВТО-УДАЛЕНИЕ СООБЩЕНИЙ В РЕСТЕ
    sett = get_chat_settings(chat_id)
    if sett.get('delete_rest_msg', False) and str_chat in db.get('rests', {}):
        in_rest, _, _ = check_user_rest(db['rests'][str_chat], user_id=user_id, user_name=user_name)
        if in_rest:
            try:
                bot.delete_message(chat_id, message.message_id)
                user_link = make_link(chat_id, user_name, user_id, ping=True)
                warn = bot.send_message(chat_id, f'⚠️ {user_link}, вы находитесь в ресте! Ваше сообщение удалено.', parse_mode='HTML')
                threading.Timer(5, lambda: bot.delete_message(chat_id, warn.message_id)).start()
                return
            except Exception: pass

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
            bot.reply_to(message, f"😂 Пользователю {u_link} начислено +1 очко <b>Смехуятинки</b>!\nВсего: <b>{econ['smeh']}</b>", parse_mode='HTML')
        else: bot.reply_to(message, "❌ Ответьте этой командой на сообщение человека!")
        return

    # ТЕКСТОВЫЕ КОМАНДЫ (БЕЗ СЛЭША)
    if text_lower in ['хромосомы', 'хромосома', 'замер хромосом']: cmd_chromosomes(message); return
    elif text_lower in ['айкью', 'iq', 'iqи', 'айкю']: cmd_iq(message); return
    elif text_lower in ['жир', 'жирок', 'жирность', 'процент жира']: cmd_fat(message); return
    elif text_lower in ['пятка', 'пяточка', 'размер пятки', 'пятки']: cmd_foot(message); return
    elif text_lower in ['писюн', 'член', 'замер']: cmd_dick(message); return
    elif text_lower in ['дроч', 'подрочить', 'фап']: cmd_fap(message); return
    elif text_lower in ['рюкзак', 'баффы']: cmd_backpack(message); return
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
    elif text_lower.startswith(('краш', 'ракета')): cmd_crash(message); return
    elif text_lower.startswith(('блэкджек', '21', 'очко')): cmd_bj(message); return
    elif text_lower.startswith(('кирпич', 'стройка')): cmd_brick(message); return

    # БОНУС
    elif text_lower in ['бонус', 'коин', 'взять бонус']:
        econ = get_user_econ(user_id, user_name, username=user_username)
        cooldown = 3600
        left = cooldown_text(econ.get('last_hourly', 0), cooldown, econ)
        if not left:
            lvl, _, _, _ = get_account_level(econ.get('account_exp', 0))
            reward = random.randint(20, 50) + (lvl * 3)
            active_t = econ.get('active_title')
            if active_t and active_t in TITLES and TITLES[active_t].get('buff') == 'bonus_coins': reward += TITLES[active_t]['val']
            if econ.get('pet') and econ['pet'].get('id') == 'panda': reward = int(reward * 1.35)

            econ['balance'] += reward
            econ['last_hourly'] = now_ts
            add_account_exp(user_id, user_name, 10, username=user_username)
            mark_dirty()
            check_achievements(user_id, user_name, 'bonuses', 1, chat_id, username=user_username)
            completed = track_daily_task(user_id, user_name, 'bonus', 1, chat_id, username=user_username)
            bot.reply_to(message, f"🎲 Вы собрали часовой бонус: <b>+{reward} Ня-коинов 🪙</b>!\nБаланс: <b>{econ['balance']} 💸</b>", parse_mode='HTML')
            for task_name, task_reward in completed: bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        else:
            bot.reply_to(message, f"⏳ Бонус доступен каждый час! Ждать: <b>{left}</b>.", parse_mode='HTML')
        return

    # КОСТИ
    elif text_lower.startswith(('кости', '/dice', 'кубик')):
        match = re.search(r'(?:кости|/dice|кубик)\s*(\d+)?', text, re.IGNORECASE)
        bet = int(match.group(1)) if match and match.group(1) else 0

        econ = get_user_econ(user_id, user_name, username=user_username)
        if bet < 0 or bet > econ['balance']:
            bot.reply_to(message, '❌ Недостаточно Ня-коинов для ставки!')
            return
            
        if bet > 0 and not check_casino_limits(econ, bet):
            bot.reply_to(message, "❌ Достигнут суточный лимит профита в казино! Приходите завтра.")
            return

        if bet > 0: process_casino_bet(bet)

        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        
        # Системная Маржа: если пул мал, не даем дубли в костях на больших ставках
        pool = db.get('casino_pool', 1000000)
        if bet > 1000 and pool < bet * 4 and d1 + d2 >= 8:
            d1 = random.randint(1, 3)
            d2 = random.randint(1, 3)

        total = d1 + d2
        result = f'🎲 Выпало: <b>{d1} + {d2} = {total}</b>.'
        if bet:
            if total == 12:
                win = bet * 4
                win = process_casino_win(win)
                econ['balance'] += win
                econ['daily_casino_win'] = econ.get('daily_casino_win', 0) + (win - bet)
                econ['daily_casino_profit'] = econ.get('daily_casino_profit', 0) + (win - bet)
                result += f'\n🎉 Джекпот! Вы выиграли <b>+{win} 🪙</b>!'
            elif total >= 8:
                win = bet
                win = process_casino_win(win)
                econ['balance'] += win
                econ['daily_casino_win'] = econ.get('daily_casino_win', 0) + win
                econ['daily_casino_profit'] = econ.get('daily_casino_profit', 0) + win
                result += f'\n✅ Вы выиграли <b>+{win} 🪙</b>!'
            else:
                econ['balance'] -= bet
                result += f'\n💸 Вы проиграли <b>{bet} 🪙</b>.'
        add_account_exp(user_id, user_name, 5, username=user_username)
        mark_dirty()
        check_achievements(user_id, user_name, 'games', 1, chat_id, username=user_username)
        completed = track_daily_task(user_id, user_name, 'dice', 1, chat_id, username=user_username)
        bot.reply_to(message, result + f"\n💰 Баланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
        for task_name, task_reward in completed: bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        return

    # СЛОТЫ
    elif text_lower.startswith(('слоты', '/slots', 'казино')):
        match = re.search(r'(?:слоты|/slots|казино)\s*(\d+)?', text, re.IGNORECASE)
        bet = int(match.group(1)) if match and match.group(1) else 0

        econ = get_user_econ(user_id, user_name, username=user_username)
        if bet <= 0:
            bot.reply_to(message, '❌ Укажите ставку! Пример: <code>слоты 100</code>', parse_mode='HTML')
            return
        if bet > econ['balance']:
            bot.reply_to(message, f"❌ Недостаточно коинов! Ваш баланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
            return
            
        if not check_casino_limits(econ, bet):
            bot.reply_to(message, "❌ Достигнут суточный лимит профита в казино! Приходите завтра.")
            return

        econ['balance'] -= bet
        process_casino_bet(bet)

        symbols_pool = ['🍒', '🍋', '🍊', '🍀', '⭐', '💎']
        luck_bonus = econ['pet'].get('luck_bonus', 0) if econ.get('pet') else 0
        if econ.get('luck_clover_until', 0) > now_ts: luck_bonus += 15

        pool = db.get('casino_pool', 1000000)
        if pool < bet * 10:
            # Режем шансы, если дом бедный
            weights = [35, 30, 20, 10, 4, 1]
        else:
            weights = [26, 23, 20, 15, 10 + int(luck_bonus * 0.05), 6 + int(luck_bonus * 0.04)]
            
        roll = random.choices(symbols_pool, weights=weights, k=3)
        result = f"🎰 <b>[ {roll[0]} | {roll[1]} | {roll[2]} ]</b>\n"

        if roll[0] == roll[1] == roll[2] == '💎':
            win = process_casino_win(int(bet * 10))
            econ['balance'] += win
            econ['daily_casino_win'] += win - bet
            econ['daily_casino_profit'] += win - bet
            result += f'\n💎👑 <b>МЕГА ДЖЕКПОТ (10x)!</b> Выигрыш: <b>+{win} 🪙</b>!'
        elif roll[0] == roll[1] == roll[2] and roll[0] in ['⭐', '🍀']:
            multiplier = 5 if roll[0] == '⭐' else 4
            win = process_casino_win(int(bet * multiplier))
            econ['balance'] += win
            econ['daily_casino_win'] += win - bet
            econ['daily_casino_profit'] += win - bet
            result += f'\n🌟 <b>ОГРОМНЫЙ ВЫИГРЫШ ({multiplier}x)!</b> Награда: <b>+{win} 🪙</b>!'
        elif roll[0] == roll[1] == roll[2]:
            win = process_casino_win(int(bet * 2.5))
            econ['balance'] += win
            econ['daily_casino_win'] += win - bet
            econ['daily_casino_profit'] += win - bet
            result += f'\n🎉 <b>Три в ряд (2.5x)!</b> Выигрыш: <b>+{win} 🪙</b>!'
        elif roll.count('💎') == 2 or roll.count('⭐') == 2:
            win = process_casino_win(int(bet * 1.5))
            econ['balance'] += win
            econ['daily_casino_win'] += win - bet
            econ['daily_casino_profit'] += win - bet
            result += f'\n✨ <b>Два редких символа!</b> Выигрыш: <b>+{win} 🪙</b> (1.5x)!'
        elif len(set(roll)) == 2:
            win = process_casino_win(int(bet * 0.8))
            econ['balance'] += win
            result += f'\n🙂 <b>Два совпадения!</b> Возврат: <b>{win} 🪙</b> (0.8x).'
        else:
            result += f'\n💸 Проигрыш <b>-{bet} 🪙</b>.'

        add_account_exp(user_id, user_name, 5, username=user_username)
        mark_dirty()
        check_achievements(user_id, user_name, 'games', 1, chat_id, username=user_username)
        completed = track_daily_task(user_id, user_name, 'slots', 1, chat_id, username=user_username)
        bot.reply_to(message, result + f"\n💰 Баланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
        for task_name, task_reward in completed: bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        return

    # РЫБАЛКА И ОХОТА
    elif text_lower in ['рыбалка', '/fish', 'рыба']:
        econ = get_user_econ(user_id, user_name, username=user_username)
        cooldown = 7200
        left = cooldown_text(econ.get('last_fish_time', 0), cooldown, econ)
        if left:
            bot.reply_to(message, f'⏳ Рыбалка доступна раз в 2 часа. Осталось: <b>{left}</b>.', parse_mode='HTML')
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
        bot.reply_to(message, f'🎣 Вы поймали: <b>{caught[0]}</b> [{caught[1]}]!\n💰 Базовая цена: <b>{caught[2]} 🪙</b>{rush_info}\n💡 Продать: <code>продать</code> | Приготовить: <code>/cook</code>', parse_mode='HTML')
        return

    elif text_lower in ['охота', '/hunt']:
        econ = get_user_econ(user_id, user_name, username=user_username)
        cooldown = 7200
        left = cooldown_text(econ.get('last_hunt_time', 0), cooldown, econ)
        if left:
            bot.reply_to(message, f'⏳ Охота доступна раз в 2 часа. Осталось: <b>{left}</b>.', parse_mode='HTML')
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
        bot.reply_to(message, f'🏹 Вы добыли: <b>{caught[0]}</b> [{caught[1]}]!\n💰 Базовая цена: <b>{caught[2]} 🪙</b>{rush_info}\n💡 Продать: <code>продать</code> | Приготовить: <code>/cook</code>', parse_mode='HTML')
        return

    # ПЕРЕВОД КОИНОВ
    elif text_lower.startswith(('перевод', 'передать', '/pay')):
        target_id, target_u, amount = parse_transfer_command(message)

        if amount <= 0 or not target_u:
            bot.reply_to(message, "❌ Формат: <code>передать @username 100</code> или ответом на сообщение: <code>передать 100</code>.", parse_mode='HTML')
            return

        if target_id == user_id:
            bot.reply_to(message, "❌ Нельзя переводить коины самому себе!")
            return

        sender_econ = get_user_econ(user_id, user_name, username=user_username)
        if sender_econ['balance'] < amount:
            bot.reply_to(message, f"❌ Недостаточно Ня-коинов! У вас: <b>{sender_econ['balance']} 🪙</b>", parse_mode='HTML')
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
            f"💸 Вы перевели <b>{amount} 🪙</b> пользователю {target_link}!\n"
            f"<i>(Комиссия 3%: сожжено {tax} 🪙, зачислено {receive_amount} 🪙)</i>\n"
            f"Ваш остаток: <b>{sender_econ['balance']} 🪙</b>",
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
            bot.reply_to(message, f'✅ Рест для {user_link} добавлен на {duration_text} (Причина: {reason})!', parse_mode='HTML')

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
                log_event('РЕСТ СНЯТ', f'Чат: <code>{chat_id}</code>\nАдмин: @{user_username}\nПользователь: {u_link}')
                bot.reply_to(message, f'🗑 Рест с {u_link} успешно снят.', parse_mode='HTML')
            else:
                bot.reply_to(message, f'❌ Рест для указанного пользователя не найден.', parse_mode='HTML')

    elif text_lower in ['ресты', 'рест']:
        if str_chat not in db['rests'] or not db['rests'][str_chat]:
            bot.reply_to(message, '🌴 В данный момент никто не находится в ресте.')
        else:
            resp = '📋 <b>СПИСОК АКТИВНЫХ РЕСТОВ:</b>\n──────────────────────\n'
            for r_key, info in db['rests'][str_chat].items():
                u_name = info.get('user_name', r_key)
                u_id = info.get('user_id')
                resp += f"• {make_link(chat_id, u_name, u_id, ping=False)} — {info['duration']} (Причина: {info.get('reason', 'Не указана')})\n"
            resp += '──────────────────────'
            bot.reply_to(message, resp, parse_mode='HTML')

    elif text_lower == 'мой рест':
        in_rest, info, _ = check_user_rest(db.get('rests', {}).get(str_chat, {}), user_id=user_id, user_name=user_name)
        if in_rest and info:
            bot.reply_to(message, f"🌴 <b>Ваш рест:</b> {info['duration']}\n📝 <b>Причина:</b> {info.get('reason', 'Не указана')}", parse_mode='HTML')
        else:
            bot.reply_to(message, "✅ Вы сейчас не находитесь в ресте!", parse_mode='HTML')

# ---------------------------------------------------------
# ОБРАБОТКА CALLBACK КНОПОК
# ---------------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    user_name = (f"{call.from_user.first_name or ''} {call.from_user.last_name or ''}").strip() or call.from_user.username
    user_username = (call.from_user.username or '').lower()
    now_ts = time.time()

    # 🛑 ПРОВЕРКА РЕЖИМА СНА
    bot_is_active = db.get('bot_active', True)
    is_super_admin = (user_username == ADMIN_USERNAME.lower())
    if not bot_is_active and not is_super_admin:
        bot.answer_callback_query(call.id, "⏳ Бот временно на техобслуживании!", show_alert=True)
        return

    # Защита от автокликера
    user_hist = user_flood_history.setdefault(user_id, [])
    user_hist.append(now_ts)
    user_flood_history[user_id] = [t for t in user_hist if now_ts - t <= 2.0]
    if len(user_flood_history[user_id]) >= 4:
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
        if action_data in ['set_max_days', 'toggle_del_msg', 'toggle_summer_music', 'set_remind_time']:
            if not is_admin(chat_id, user_id):
                bot.answer_callback_query(call.id, "❌ Настройки доступны только администраторам!", show_alert=True)
                return
        else:
            bot.answer_callback_query(call.id, "❌ Это меню открыто другим пользователем!", show_alert=True)
            return

    # ИГРА КИРПИЧ
    if action_data.startswith('brick_step_'):
        game_id = action_data.replace('brick_step_', '')
        game = active_brick.get(game_id)
        if not game:
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
        
        pool = db.get('casino_pool', 1000000)
        if pool < game['bet'] * mult:
            risk += 0.4 # Искусственное повышение риска, если банк пуст

        if random.random() < risk:
            bot.edit_message_text(
                f"🧱 <b>КРАШ НА СТРОЙКЕ!</b>\n\n"
                f"👤 Игрок: {make_link(chat_id, user_name, user_id, ping=False)}\n"
                f"💥 Кирпич упал на голову на шаге {step+1} (Множитель: {mult}x)!\n"
                f"💸 Ставка <b>{game['bet']} 🪙</b> утеряна...",
                chat_id=chat_id,
                message_id=call.message.message_id,
                parse_mode='HTML'
            )
            del active_brick[game_id]
            return

        game['step'] = step + 1
        cashout_amt = int(game['bet'] * mult)

        markup = InlineKeyboardMarkup()
        if game['step'] < len(game['mults']) - 1:
            markup.add(InlineKeyboardButton(f"🏗 Сделать шаг (Риск {int(game['risks'][game['step']+1]*100)}%)", callback_data=f"brick_step_{game_id}:{user_id}"))
        markup.add(InlineKeyboardButton(f"💰 Забрать куш ({cashout_amt} 🪙 | {mult}x)", callback_data=f"brick_cashout_{game_id}:{user_id}"))

        bar = "🟩" * (game['step'] + 1) + "⬜️" * (len(game['mults']) - game['step'] - 1)
        bot.edit_message_text(
            f"🧱 <b>ИГРА КИРПИЧ (СТРОЙКА)</b>\n"
            f"──────────────────────\n"
            f"👤 Строитель: {make_link(chat_id, user_name, user_id, ping=False)}\n"
            f"💰 Ставка: <b>{game['bet']} 🪙</b>\n"
            f"📈 Текущий множитель: <b>{mult}x</b>\n"
            f"🏗 Прогресс: [{bar}]\n"
            f"──────────────────────",
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode='HTML'
        )

    elif action_data.startswith('brick_cashout_'):
        game_id = action_data.replace('brick_cashout_', '')
        game = active_brick.get(game_id)
        if not game:
            bot.answer_callback_query(call.id, "❌ Игра окончена!", show_alert=True)
            return
        if user_id != game['user_id']:
            bot.answer_callback_query(call.id, "❌ Не ваша игра!", show_alert=True)
            return

        mult = game['mults'][game['step']]
        win_amt = int(game['bet'] * mult)
        win_amt = process_casino_win(win_amt)

        econ = get_user_econ(user_id, user_name, username=user_username)
        econ['balance'] += win_amt
        econ['daily_casino_win'] = econ.get('daily_casino_win', 0) + (win_amt - game['bet'])
        econ['daily_casino_profit'] = econ.get('daily_casino_profit', 0) + (win_amt - game['bet'])
        check_achievements(user_id, user_name, 'games', 1, chat_id, username=user_username)
        mark_dirty()

        bot.edit_message_text(
            f"💰 <b>ВЫ УСПЕШНО ЗАБРАЛИ КУШ!</b>\n\n"
            f"👤 Строитель: {make_link(chat_id, user_name, user_id, ping=False)}\n"
            f"🎉 Выигрыш: <b>+{win_amt} Ня-коинов 🪙</b> (Множитель: <b>{mult}x</b>)!\n"
            f"💵 Баланс: <b>{econ['balance']} 🪙</b>",
            chat_id=chat_id,
            message_id=call.message.message_id,
            parse_mode='HTML'
        )
        del active_brick[game_id]

    # НАВИГАЦИЯ СПРАВОЧНИКА
    elif action_data == 'help_main':
        try: bot.edit_message_text("🤖 <b>ГЛАВНЫЙ ИНТЕРАКТИВНЫЙ НАВИГАТОР НЯ-БОТА</b>\n──────────────────────\nВыберите интересующий вас раздел:", chat_id=chat_id, message_id=call.message.message_id, reply_markup=get_main_menu_markup(user_id), parse_mode='HTML')
        except Exception: pass

    elif action_data == 'help_vd':
        text = (
            "🩸 <b>ФАКТЫ И ВИКТОРИНЫ ПО VIOLENCE DISTRICT</b> 🔪\n"
            "──────────────────────\n"
            "• <code>факт вд</code> или <code>/fact_vd</code> — случайный секрет разработки или лора игры\n"
            "• В чате игры регулярно проходят экспресс-викторины с призами коинов!\n"
            "• В базе знаний собрано 18 интереснейших фактов от первых маньяков до скрытых пасхалок!\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🩸 Получить факт прямо сейчас", callback_data=f"get_instant_vd_fact:{user_id}"))
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data=f"help_main:{user_id}"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data == 'get_instant_vd_fact':
        title, desc = random.choice(VD_FACTS)
        msg_text = f"🩸 <b>ИНТЕРЕСНЫЙ ФАКТ | VIOLENCE DISTRICT</b> 🔪\n──────────────────────\n📌 <b>{title}</b>\n📖 <i>{desc}</i>\n──────────────────────"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🎲 Еще факт", callback_data=f"get_instant_vd_fact:{user_id}"))
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data=f"help_main:{user_id}"))
        bot.edit_message_text(msg_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data == 'help_sports':
        text = (
            "⚽️ <b>СПОРТИВНЫЕ ИГРЫ И КАЗИНО TELEGRAM</b>\n──────────────────────\n"
            "• 🚀 <code>/crash 100</code> — игра Краш (ракета со взлётом)\n"
            "• 🧱 <code>/brick 100</code> — игра Кирпич (множитель и риск)\n"
            "• ⚽️ <code>футбол 100</code> — пенальти в ворота (гол x1.6 - x1.8)\n"
            "• 🏀 <code>баскетбол 100</code> — бросок в корзину (гол x2.0 - x2.3)\n"
            "• 🎯 <code>дартс 100</code> — бросок дротика (яблочко x3.5 - x4.0)\n"
            "• 🎳 <code>боулинг 100</code> — бросок шара (страйк x3.0 - x3.5)\n"
            "• 💣 <code>/mines 100</code> — игра в Сапёр на поле 4х4\n"
            "• 🃏 <code>/bj 100</code> — Блэкджек (21 очко)\n"
            "• 🎰 <code>слоты 100</code> | 🎲 <code>кости 100</code> | ✌️ <code>/rps @user 100</code>\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data=f"help_main:{user_id}"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data == 'help_themes_buffs':
        text = (
            "🎨 <b>ТЕМЫ ПРОФИЛЯ И РАСХОДНИКИ</b>\n──────────────────────\n"
            "• <code>/backpack</code> — рюкзак ваших баффов и активация\n"
            "• 🎨 <b>Темы оформления:</b> Сакура, Неон/Киберпанк, Золото, Готика (в /shop)\n"
            "• ⚡️ <b>Энергетик:</b> мгновенный сброс всех таймеров\n"
            "• 🍀 <b>Клевер:</b> +15% к удаче в играх на 1 час\n"
            "• 🛡 <b>Сигнализация:</b> оглушает вора и защищает ваши деньги\n"
            "• 🥷 <b>Невидимка:</b> скрывает ваши замеры в общих топах\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data=f"help_main:{user_id}"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data == 'help_stream_garden':
        text = (
            "🎥 <b>СТРИМЕР И ОРАНЖЕРЕЯ БОНСАЙ</b> 🪴\n──────────────────────\n"
            "• <code>/stream [Жанр]</code> — запустить трансляцию (Гейминг, ASMR и др.)\n"
            "• Покупай микрофоны и вебкамеры в магазине для роста аудитории.\n"
            "• <code>/garden</code> — твоя личная оранжерея. Сажай семена, поливай и собирай урожай!\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data=f"help_main:{user_id}"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data == 'help_karma_rp':
        text = (
            "⚖️ <b>СИСТЕМА КАРМЫ И РП</b> 😇😈\n──────────────────────\n"
            "• <code>обнять @user</code>, <code>похвалить</code>, <code>подарок</code> повышают Карму (+)\n"
            "• <code>ударить тапком</code>, <code>плюнуть</code>, <code>ограбить</code> понижают Карму (-)\n"
            "• Проверь свой статус в <code>/profile</code>: от Святого Ангела до Демона!\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data=f"help_main:{user_id}"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data == 'help_heroes':
        text = (
            "🏆 <b>УДАРНИКИ И ГЕРОИ ДНЯ</b>\n──────────────────────\n"
            "• Команда: <code>герои дня</code> или <code>/daily_heroes</code>\n\n"
            "👑 <b>Номинации каждые 24 часа:</b>\n"
            "1. 🗣 <b>Главный спикер</b> — топ по сообщениям в чате за день\n"
            "2. 🎰 <b>Гроза казино</b> — самый удачливый игрок по выигрышам\n"
            "3. 💖 <b>Главный меценат</b> — щедрый игрок по переводам коинов\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data=f"help_main:{user_id}"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data == 'help_sims':
        text = (
            "🍆 <b>МЕМНЫЕ СИМУЛЯТОРЫ, ШАР И ЗАМЕРЫ</b>\n──────────────────────\n"
            "• 🔮 <code>шар [вопрос]</code> — магический шар судьбы\n"
            "• 📊 <code>шанс [событие]</code> — расчет процента вероятности\n"
            "• 🕵️‍♂️ <code>детектор [фраза]</code> — проверка на детекторе лжи\n"
            "• 🍆 <code>/dick</code> или <code>писюн</code> — замер размера (до 250 см!)\n"
            "• 💦 <code>/fap</code> или <code>дроч</code> — счетчик фапа и ранги\n"
            "• 🧬 <code>хромосомы</code> | 🧠 <code>iq</code> | 🥩 <code>жир</code> | 🦶 <code>пятка</code>\n"
            "• 🏆 <code>топ</code> — интерактивные топы чата\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data=f"help_main:{user_id}"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data == 'help_rests':
        text = (
            "🌴 <b>СИСТЕМА РЕСТОВ И ОТПУСКОВ</b>\n──────────────────────\n"
            "• <code>+рест Иван 3 дня | отпуск</code> — выдать рест\n"
            "• <code>-рест @username</code> — снять рест\n"
            "• <code>история @username</code> — журнал рестов\n"
            "• <code>ресты</code> — список отдыхающих\n"
            "• <code>кто ты @username</code> — статус реста\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data=f"help_main:{user_id}"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data == 'help_biz':
        text = (
            "🏢 <b>БИЗНЕСЫ 2.0 И ГАРАЖ</b>\n──────────────────────\n"
            "• <code>/business</code> — покупка и прокачка (1-5 LVL)\n"
            "• <code>/miner</code> — майнинг-ферма\n"
            "• <code>/garage</code> — покупка личного транспорта\n"
            "• <code>собрать прибыль</code> — сбор дохода с предприятий\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data=f"help_main:{user_id}"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data == 'help_bank':
        text = (
            "🏦 <b>НЯ-БАНК И ДЕПОЗИТЫ</b>\n──────────────────────\n"
            "• <code>/bank</code> — меню депозита\n"
            "• <code>банк положить 500</code> — внести вклад\n"
            "• <code>банк снять 500</code> — снять деньги\n"
            "• <code>/loan</code> — кредиты под % от банка\n"
            "📈 +1% каждые 6 часов (сложный процент)!\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data=f"help_main:{user_id}"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data == 'help_crypto':
        text = (
            "📈 <b>КРИПТО-БИРЖА</b>\n──────────────────────\n"
            "• <code>биржа</code> — котировки монет\n"
            "• <code>купить крипту NYA 5</code> — покупка\n"
            "• <code>продать крипту NYA 5</code> — продажа\n"
            "• <code>портфель</code> — список активов\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data=f"help_main:{user_id}"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data == 'help_pets':
        text = (
            "🐾 <b>ПИТОМЦЫ, КУЛИНАРИЯ И ОХОТА</b>\n──────────────────────\n"
            "• <code>/pet</code> — карточка питомца и уход\n"
            "• <code>/walk</code> — отправить питомца на прогулку за кладом\n"
            "• <code>/cook</code> — приготовить добычу для питомца\n"
            "• <code>/gear</code> — купить удочки и луки\n"
            "• <code>рыбалка</code> / <code>охота</code> — добыча\n"
            "• <code>продать</code> — продать трофеи\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data=f"help_main:{user_id}"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data == 'help_econ':
        text = (
            "💰 <b>ЭКОНОМИКА И КВЕСТЫ</b>\n──────────────────────\n"
            "• <code>бонус</code> — часовые коины\n"
            "• <code>баланс</code>, <code>профиль</code> — вся статистика\n"
            "• <code>передать @user 100</code> — перевод коинов\n"
            "• <code>ачивки</code> — 42 достижения с наградами\n"
            "• <code>магазин</code> — значки, титулы, питомцы, темы\n"
            "• <code>топ</code> — таблицы лидеров чата\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data=f"help_main:{user_id}"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data == 'help_full_catalog':
        text = (
            "📖 <b>ПОЛНЫЙ АЛФАВИТНЫЙ СПРАВОЧНИК КОМАНД:</b>\n──────────────────────\n"
            "• <b>А</b>: <code>ачивки</code>, <code>аватарка</code>, <code>айкью</code>\n"
            "• <b>Б</b>: <code>баланс</code>, <code>банк</code>, <code>бизнес</code>, <code>биржа</code>, <code>брак</code>, <code>бонус</code>\n"
            "• <b>В</b>: <code>вакансии</code>, <code>/walk</code> (гулять)\n"
            "• <b>Г</b>: <code>гараж</code>, <code>герои дня</code>, <code>гулять</code>\n"
            "• <b>Д</b>: <code>дартс 100</code>, <code>депозит</code>, <code>детектор</code>, <code>дроч</code>, <code>/dick</code>\n"
            "• <b>Ж</b>: <code>жир</code>\n"
            "• <b>З</b>: <code>задания</code>, <code>замер</code>\n"
            "• <b>И</b>: <code>инвентарь</code>, <code>история</code>, <code>итоги дня</code>\n"
            "• <b>К</b>: <code>кейс</code>, <code>кости 100</code>, <code>кулинария</code>, <code>колесо</code>, <code>краш 100</code>, <code>кредит</code>\n"
            "• <b>Л</b>: <code>лотерея</code>, <code>лидеры</code>\n"
            "• <b>М</b>: <code>магазин</code>, <code>майнер</code>, <code>мины 100</code>, <code>мой рест</code>\n"
            "• <b>О</b>: <code>ограбить @юзер</code>, <code>опыт</code>, <code>охота</code>\n"
            "• <b>П</b>: <code>передать @юзер 100</code>, <code>подарок</code>, <code>питомец</code>, <code>профиль</code>, <code>портфель</code>\n"
            "• <b>Р</b>: <code>работа</code>, <code>развод</code>, <code>ресты</code>, <code>рулетка</code>, <code>рыбалка</code>, <code>рюкзак</code>\n"
            "• <b>С</b>: <code>сапер 100</code>, <code>слоты 100</code>, <code>семья</code>, <code>стрим</code>, <code>сад</code>\n"
            "• <b>Т</b>: <code>топ</code>, <code>тренировка</code>, <code>тачки</code>\n"
            "• <b>Ф</b>: <code>факт вд</code>, <code>футбол 100</code>, <code>ферма</code>, <code>фап</code>\n"
            "• <b>Х</b>: <code>хромосомы</code>\n"
            "• <b>Ц</b>: <code>цуефа @юзер 100</code>\n"
            "• <b>Ш</b>: <code>шар [вопрос]</code>, <code>шанс [событие]</code>\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data=f"help_main:{user_id}"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

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

        bot.answer_callback_query(call.id, f"🎉 Куш забран: +{win_amt} 🪙 ({mult:.2f}x)!", show_alert=True)
        try:
            bot.edit_message_text(
                f"💰 <b>УСПЕШНЫЙ CASHOUT В КРАШЕ!</b>\n\n"
                f"👤 Пилот: {make_link(chat_id, user_name, user_id, ping=False)}\n"
                f"🎉 Зафиксирован выигрыш: <b>+{win_amt} Ня-коинов 🪙</b> (Множитель: <b>{mult:.2f}x</b>)!\n"
                f"💵 Баланс: <b>{econ['balance']} 🪙</b>",
                chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML'
            )
        except Exception: pass
        active_crash.pop(game_id, None)

    # ИСПОЛЬЗОВАНИЕ РАСХОДНИКОВ
    elif action_data == 'use_item_energy_drink':
        econ = get_user_econ(user_id, user_name, username=user_username)
        bp = econ.setdefault('backpack', {})
        if bp.get('energy_drink', 0) <= 0:
            bot.answer_callback_query(call.id, "❌ У вас нет энергетика!", show_alert=True)
            return
        bp['energy_drink'] -= 1
        econ['last_work_time'] = 0; econ['last_fish_time'] = 0; econ['last_hunt_time'] = 0
        econ['last_train_time'] = 0; econ['last_iq_time'] = 0; econ['last_fat_time'] = 0
        econ['last_foot_time'] = 0; econ['last_chromosomes_time'] = 0; econ['last_dick_time'] = 0
        mark_dirty()
        bot.answer_callback_query(call.id, "⚡️ Энергетик выпит! Все таймеры мгновенно сброшены!", show_alert=True)
        render_backpack_view(chat_id, user_id, user_name, call.message.message_id)

    elif action_data == 'use_item_luck_clover':
        econ = get_user_econ(user_id, user_name, username=user_username)
        bp = econ.setdefault('backpack', {})
        if bp.get('luck_clover', 0) <= 0:
            bot.answer_callback_query(call.id, "❌ У вас нет клевера!", show_alert=True)
            return
        bp['luck_clover'] -= 1
        econ['luck_clover_until'] = time.time() + 3600
        mark_dirty()
        bot.answer_callback_query(call.id, "🍀 Клевер активирован! +15% к удаче в играх на 1 час!", show_alert=True)
        render_backpack_view(chat_id, user_id, user_name, call.message.message_id)

    elif action_data == 'use_item_invis_mask':
        econ = get_user_econ(user_id, user_name, username=user_username)
        bp = econ.setdefault('backpack', {})
        if bp.get('invis_mask', 0) <= 0:
            bot.answer_callback_query(call.id, "❌ У вас нет маски-невидимки!", show_alert=True)
            return
        bp['invis_mask'] -= 1
        econ['invis_until'] = time.time() + 86400
        mark_dirty()
        bot.answer_callback_query(call.id, "🥷 Маска надета! Ваши замеры скрыты из топов на 24 часа!", show_alert=True)
        render_backpack_view(chat_id, user_id, user_name, call.message.message_id)

    # МАГАЗИН: СТУДИЯ СТРИМЕРА
    elif action_data == 'shop_cat_stream':
        econ = get_user_econ(user_id, user_name)
        studio = econ.setdefault('stream_studio', {'mic': 1, 'webcam': 1, 'light': 1})
        lines = [
            "🎙 <b>СТУДИЯ СТРИМЕРА (АПГРЕЙДЫ)</b>", "──────────────────────",
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
        bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data.startswith('buy_studio_'):
        equip_key = action_data.replace('buy_studio_', '')
        econ = get_user_econ(user_id, user_name, username=user_username)
        studio = econ.setdefault('stream_studio', {'mic': 1, 'webcam': 1, 'light': 1})
        lvl = studio.get(equip_key, 1)
        if lvl >= 4:
            bot.answer_callback_query(call.id, "❌ Максимальный уровень!", show_alert=True)
            return
        cost = STREAM_EQUIP[equip_key]['levels'][lvl]
        if econ['balance'] < cost:
            bot.answer_callback_query(call.id, f"❌ Нужно {cost} 🪙!", show_alert=True)
            return
        econ['balance'] -= cost
        studio[equip_key] = lvl + 1
        mark_dirty()
        bot.answer_callback_query(call.id, f"🎉 Вы улучшили {STREAM_EQUIP[equip_key]['name']} до {lvl+1} уровня!")
        
        markup = InlineKeyboardMarkup(row_width=1)
        lines = ["🎙 <b>СТУДИЯ СТРИМЕРА (АПГРЕЙДЫ)</b>", "──────────────────────", "<i>Улучшайте оборудование, чтобы привлекать больше зрителей!</i>\n"]
        for k, v in STREAM_EQUIP.items():
            curlvl = studio.get(k, 1)
            if curlvl < 4:
                ccost = v['levels'][curlvl]
                lines.append(f"• <b>{v['name']}</b> (Ур. {curlvl}/4) -> {ccost} 🪙")
                markup.add(InlineKeyboardButton(f"⬆️ Улучшить {v['name']} -> {ccost} 🪙", callback_data=f"buy_studio_{k}:{user_id}"))
            else:
                lines.append(f"• <b>{v['name']}</b> (Ур. МАХ) -> Полностью прокачано!")
        lines.append("──────────────────────")
        markup.add(InlineKeyboardButton("🔙 Назад в магазин", callback_data=f"shop_main:{user_id}"))
        bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data == 'shop_cat_garden':
        lines = [
            "🪴 <b>СЕМЕНА ОРАНЖЕРЕИ БОНСАЙ</b>", "──────────────────────",
            "<i>Посадите семечко, поливайте его и соберите ценный урожай!</i>\n"
        ]
        for s_id, s_info in GARDEN_SEEDS.items():
            hrs = s_info['grow_time'] // 3600
            lines.append(f"• {s_info['emoji']} <b>{s_info['name']}</b> — <code>{s_info['price']} 🪙</code>\n  <i>(Рост: {hrs} ч., Поливов: {s_info['water_req']}, Прибыль: {s_info['reward_min']}-{s_info['reward_max']} 🪙)</i>\n")
        lines.append("──────────────────────")

        markup = InlineKeyboardMarkup(row_width=2)
        btns = [InlineKeyboardButton(f"{s['emoji']} {s['price']} 🪙", callback_data=f"buy_seed_{s_id}:{user_id}") for s_id, s in GARDEN_SEEDS.items()]
        markup.add(*btns)
        markup.add(InlineKeyboardButton("🔙 Назад в магазин", callback_data=f"shop_main:{user_id}"))
        bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data.startswith('buy_seed_'):
        s_id = action_data.replace('buy_seed_', '')
        if s_id in GARDEN_SEEDS:
            seed = GARDEN_SEEDS[s_id]
            econ = get_user_econ(user_id, user_name, username=user_username)
            if econ.get('garden'):
                bot.answer_callback_query(call.id, "❌ У вас уже растет растение в саду! Сначала соберите его.", show_alert=True)
                return
            if econ['balance'] < seed['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {seed['price']} 🪙!", show_alert=True)
                return
            econ['balance'] -= seed['price']
            econ['garden'] = {'seed': s_id, 'planted_at': time.time(), 'water_count': 0}
            mark_dirty()
            bot.answer_callback_query(call.id, f"🎉 Вы посадили {seed['name']}! Зайдите в /garden", show_alert=True)
            render_garden_view(chat_id, user_id, user_name, call.message.message_id)

    elif action_data == 'water_plant':
        econ = get_user_econ(user_id, user_name)
        garden = econ.get('garden')
        if not garden: return
        seed_info = GARDEN_SEEDS[garden['seed']]
        if garden['water_count'] >= seed_info['water_req']:
            bot.answer_callback_query(call.id, "💦 Растение уже достаточно полито!", show_alert=True)
            return
        garden['water_count'] += 1
        mark_dirty()
        bot.answer_callback_query(call.id, "💦 Вы успешно полили растение!")
        render_garden_view(chat_id, user_id, user_name, call.message.message_id)

    elif action_data == 'harvest_plant':
        econ = get_user_econ(user_id, user_name)
        garden = econ.get('garden')
        if not garden: return
        seed_info = GARDEN_SEEDS[garden['seed']]
        elapsed = time.time() - garden['planted_at']
        if elapsed < seed_info['grow_time']:
            bot.answer_callback_query(call.id, "❌ Урожай еще не созрел!", show_alert=True)
            return
        if garden['water_count'] < seed_info['water_req']:
            bot.answer_callback_query(call.id, "❌ Растению не хватило воды! Полейте его.", show_alert=True)
            return
        reward = random.randint(seed_info['reward_min'], seed_info['reward_max'])
        econ['balance'] += reward
        econ['garden'] = None
        change_karma(user_id, user_name, 2)
        mark_dirty()
        bot.answer_callback_query(call.id, f"🎉 Урожай собран: +{reward} 🪙!")
        bot.edit_message_text(
            f"🪴 <b>СБОР УРОЖАЯ</b>\n──────────────────────\n"
            f"Вы собрали великолепный урожай {seed_info['name']} и продали его за <b>{reward} Ня-коинов 🪙</b>!\n"
            f"Карма повышена: <b>+2 😇</b>",
            chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML'
        )

    elif action_data == 'uproot_plant':
        econ = get_user_econ(user_id, user_name)
        econ['garden'] = None
        mark_dirty()
        bot.answer_callback_query(call.id, "❌ Растение выкорчевано.")
        render_garden_view(chat_id, user_id, user_name, call.message.message_id)

    elif action_data == 'shop_cat_buffs':
        lines = [
            "🧰 <b>МАГАЗИН РАСХОДНИКОВ И БАФФОВ</b>", "──────────────────────",
            "<i>Используйте расходники из рюкзака (/backpack) для преимуществ!</i>\n"
        ]
        for b_id, b_info in BUFF_ITEMS.items():
            lines.append(f"• <b>{b_info['name']}</b> — <code>{b_info['price']} 🪙</code>\n  <i>{b_info['desc']}</i>\n")
        lines.append("──────────────────────")
        markup = InlineKeyboardMarkup(row_width=2)
        btns = [InlineKeyboardButton(f"{b['short']} • {b['price']} 🪙", callback_data=f"buy_buff_{b_id}:{user_id}") for b_id, b in BUFF_ITEMS.items()]
        markup.add(*btns)
        markup.add(InlineKeyboardButton("🔙 Назад в магазин", callback_data=f"shop_main:{user_id}"))
        bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data.startswith('buy_buff_'):
        b_id = action_data.replace('buy_buff_', '')
        if b_id in BUFF_ITEMS:
            item = BUFF_ITEMS[b_id]
            econ = get_user_econ(user_id, user_name, username=user_username)
            if econ['balance'] < item['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {item['price']} 🪙!", show_alert=True)
                return
            econ['balance'] -= item['price']
            bp = econ.setdefault('backpack', {})
            bp[b_id] = bp.get(b_id, 0) + 1
            mark_dirty()
            bot.answer_callback_query(call.id, f"🎉 Куплен предмет: {item['short']}! Откройте /backpack", show_alert=True)

    elif action_data == 'shop_cat_themes':
        lines = [
            "🎨 <b>КАТАЛОГ ТЕМ ОФОРМЛЕНИЯ ПРОФИЛЯ</b>", "──────────────────────",
            "<i>Тема полностью меняет графический стиль и рамки команды /profile!</i>\n"
        ]
        for t_k, t_v in THEMES.items():
            if t_k != 'default': lines.append(f"• <b>{t_v['name']}</b> — <code>{t_v['price']} 🪙</code>")
        lines.append("──────────────────────")
        markup = InlineKeyboardMarkup(row_width=2)
        btns = [InlineKeyboardButton(f"{t_v['name']} • {t_v['price']} 🪙", callback_data=f"buy_theme_{t_k}:{user_id}") for t_k, t_v in THEMES.items() if t_k != 'default']
        markup.add(*btns)
        markup.add(InlineKeyboardButton("🔙 Назад в магазин", callback_data=f"shop_main:{user_id}"))
        bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data.startswith('buy_theme_'):
        t_key = action_data.replace('buy_theme_', '')
        if t_key in THEMES:
            theme = THEMES[t_key]
            econ = get_user_econ(user_id, user_name, username=user_username)
            purchased = econ.setdefault('purchased_themes', ['default'])
            if t_key in purchased:
                bot.answer_callback_query(call.id, "❌ Эта тема уже куплена!", show_alert=True)
                return
            if econ['balance'] < theme['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {theme['price']} 🪙!", show_alert=True)
                return
            econ['balance'] -= theme['price']
            purchased.append(t_key)
            econ['profile_theme'] = t_key
            mark_dirty()
            bot.answer_callback_query(call.id, f"🎉 Куплена и активирована тема {theme['name']}!", show_alert=True)
            send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)

    elif action_data.startswith('set_theme_'):
        t_key = action_data.replace('set_theme_', '')
        econ = get_user_econ(user_id, user_name, username=user_username)
        if t_key in econ.get('purchased_themes', ['default']):
            econ['profile_theme'] = t_key
            mark_dirty()
            bot.answer_callback_query(call.id, f"✅ Установлен стиль: {THEMES[t_key]['name']}!")
            send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)

    # САПЁР
    elif action_data.startswith('mines_open_'):
        m_match = re.match(r"^mines_open_(m_\d+_\d+)_(\d+)$", action_data)
        if not m_match:
            bot.answer_callback_query(call.id, "❌ Ошибка данных игры!", show_alert=True)
            return
        game_id = m_match.group(1)
        cell_idx = int(m_match.group(2))
        game = active_mines.get(game_id)
        if not game or game.get('finished'):
            bot.answer_callback_query(call.id, "❌ Игра уже завершена!", show_alert=True)
            return
        if user_id != game['user_id']:
            bot.answer_callback_query(call.id, "❌ Это не ваше игровое поле!", show_alert=True)
            return

        if cell_idx in game['bombs']:
            game['finished'] = True
            text_board, markup = render_mines_board(game_id)
            loss_text = f"💥 <b>БАБАХ! ВЫ НАСТУПИЛИ НА МИНУ!</b>\n\n💸 Вы потеряли ставку: <b>{game['bet']} Ня-коинов 🪙</b>!\n\n{text_board}"
            bot.edit_message_text(loss_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            del active_mines[game_id]
            return
        else:
            game['revealed'].add(cell_idx)
            safe_opened = len(game['revealed'])
            mult_map = {1: 1.25, 2: 1.60, 3: 2.10, 4: 2.80, 5: 3.80, 6: 5.20, 7: 7.50, 8: 11.0, 9: 16.0, 10: 25.0, 11: 40.0, 12: 70.0, 13: 150.0}
            game['current_multiplier'] = mult_map.get(safe_opened, 1.25)

            if safe_opened >= 13:
                game['finished'] = True
                win_amt = int(game['bet'] * game['current_multiplier'])
                win_amt = process_casino_win(win_amt)
                add_coins(user_id, user_name, win_amt, username=user_username)
                add_account_exp(user_id, user_name, 50, username=user_username)
                check_achievements(user_id, user_name, 'mines_wins', 1, chat_id, username=user_username)
                mark_dirty()
                text_board, markup = render_mines_board(game_id)
                win_text = f"🏆 <b>НЕВЕРОЯТНО! ВСЕ 13 КРИСТАЛЛОВ НАЙДЕНЫ!</b>\n\n💰 Выигрыш: <b>+{win_amt} Ня-коинов 🪙</b> (Множитель: <b>{game['current_multiplier']:.2f}x</b>)!\n\n{text_board}"
                bot.edit_message_text(win_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                del active_mines[game_id]
                return

            text_board, markup = render_mines_board(game_id)
            bot.edit_message_text(text_board, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif action_data.startswith('mines_cashout_'):
        game_id = action_data.replace('mines_cashout_', '')
        game = active_mines.get(game_id)
        if not game or game.get('finished'):
            bot.answer_callback_query(call.id, "❌ Игра окончена!", show_alert=True)
            return
        if user_id != game['user_id']:
            bot.answer_callback_query(call.id, "❌ Это не ваша игра!", show_alert=True)
            return

        game['finished'] = True
        win_amt = int(game['bet'] * game['current_multiplier'])
        win_amt = process_casino_win(win_amt)
        add_coins(user_id, user_name, win_amt, username=user_username)
        add_account_exp(user_id, user_name, 15, username=user_username)
        check_achievements(user_id, user_name, 'mines_wins', 1, chat_id, username=user_username)
        mark_dirty()

        text_board, markup = render_mines_board(game_id)
        cash_text = f"💰 <b>ВЫ УСПЕШНО ЗАБРАЛИ КУШ!</b>\n\n🎉 Начислено: <b>+{win_amt} Ня-коинов 🪙</b> (Коэффициент: <b>{game['current_multiplier']:.2f}x</b>)!\n\n{text_board}"
        bot.edit_message_text(cash_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
        del active_mines[game_id]

    # УХОД ЗА ПИТОМЦЕМ
    elif action_data == 'pet_feed':
        econ = get_user_econ(user_id, user_name, username=user_username)
        pet = econ.get('pet')
        if not pet:
            bot.answer_callback_query(call.id, "❌ У вас нет питомца!", show_alert=True)
            return
        if pet.get('hunger', 100) >= 100:
            bot.answer_callback_query(call.id, "🍖 Питомец сыт!", show_alert=True)
            return
        if econ['balance'] < 30:
            bot.answer_callback_query(call.id, "❌ Нужно 30 🪙 для корма!", show_alert=True)
            return
        econ['balance'] -= 30
        pet['hunger'] = min(100, pet.get('hunger', 0) + 35)
        pet['pet_exp'] = pet.get('pet_exp', 0) + 10
        check_achievements(user_id, user_name, 'pet_care', 1, chat_id, username=user_username)
        mark_dirty()
        bot.answer_callback_query(call.id, "🍖 Питомец вкусно покушал (+10 EXP)!")
        render_pet_view(chat_id, user_id, user_name, call.message.message_id)

    elif action_data == 'pet_wash':
        econ = get_user_econ(user_id, user_name, username=user_username)
        pet = econ.get('pet')
        if not pet:
            bot.answer_callback_query(call.id, "❌ У вас нет питомца!", show_alert=True)
            return
        if pet.get('cleanliness', 100) >= 100:
            bot.answer_callback_query(call.id, "🧼 Питомец уже чистый!", show_alert=True)
            return
        if econ['balance'] < 20:
            bot.answer_callback_query(call.id, "❌ Нужно 20 🪙 на шампунь!", show_alert=True)
            return
        econ['balance'] -= 20
        pet['cleanliness'] = min(100, pet.get('cleanliness', 0) + 40)
        pet['pet_exp'] = pet.get('pet_exp', 0) + 10
        check_achievements(user_id, user_name, 'pet_care', 1, chat_id, username=user_username)
        mark_dirty()
        bot.answer_callback_query(call.id, "🧼 Питомец искупан до блеска (+10 EXP)!")
        render_pet_view(chat_id, user_id, user_name, call.message.message_id)

    elif action_data == 'pet_walk_btn':
        bot.answer_callback_query(call.id)
        process_pet_walk(chat_id, user_id, user_name)

    # ПРОКАЧКА БИЗНЕСА
    elif action_data.startswith('upg_biz_'):
        b_id = action_data.replace('upg_biz_', '')
        if b_id in BUSINESSES:
            b_info = BUSINESSES[b_id]
            econ = get_user_econ(user_id, user_name, username=user_username)
            biz_levels = econ.setdefault('biz_levels', {})
            cur_lvl = biz_levels.get(b_id, 1)
            if cur_lvl >= 5:
                bot.answer_callback_query(call.id, "❌ Достигнут максимальный 5-й уровень!", show_alert=True)
                return
            cost = b_info['upgrade_cost'] * cur_lvl
            if econ['balance'] < cost:
                bot.answer_callback_query(call.id, f"❌ Нужно {cost} 🪙!", show_alert=True)
                return
            econ['balance'] -= cost
            biz_levels[b_id] = cur_lvl + 1
            mark_dirty()
            bot.answer_callback_query(call.id, f"🎉 {b_info['short']} улучшен(а) до {cur_lvl+1} уровня!")
            render_business_view(chat_id, user_id, user_name, message_id=call.message.message_id)

    elif action_data.startswith('buy_biz_'):
        b_id = action_data.replace('buy_biz_', '')
        if b_id in BUSINESSES:
            b_info = BUSINESSES[b_id]
            econ = get_user_econ(user_id, user_name, username=user_username)
            user_biz = econ.setdefault('businesses', {})
            biz_levels = econ.setdefault('biz_levels', {})
            if b_id in user_biz:
                bot.answer_callback_query(call.id, "❌ Этот бизнес уже приобретен!", show_alert=True)
                return
            if econ['balance'] < b_info['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {b_info['price']} 🪙!", show_alert=True)
                return
            econ['balance'] -= b_info['price']
            user_biz[b_id] = time.time()
            biz_levels[b_id] = 1
            check_achievements(user_id, user_name, 'biz_bought', 1, chat_id, username=user_username)
            mark_dirty()
            bot.answer_callback_query(call.id, f"🎉 Вы приобрели {b_info['name']}!")
            render_business_view(chat_id, user_id, user_name, message_id=call.message.message_id)

    elif action_data == 'collect_biz_profit':
        econ = get_user_econ(user_id, user_name, username=user_username)
        user_biz = econ.get('businesses', {})
        biz_levels = econ.get('biz_levels', {})
        now = time.time()
        hours_passed = (now - econ.get('last_biz_collect', now)) / 3600.0
        base_profit = sum(int(BUSINESSES[b]['base_income'] * (1 + (biz_levels.get(b, 1) - 1) * 0.45) * hours_passed) for b in user_biz.keys() if b in BUSINESSES)
        if base_profit <= 0:
            bot.answer_callback_query(call.id, "⏳ Прибыль еще не накопилась!", show_alert=True)
            return

        in_rest, _, _ = check_user_rest(db.get('rests', {}).get(str(chat_id), {}), user_id=user_id, user_name=user_name)
        total_profit = base_profit
        if in_rest: total_profit += int(base_profit * 0.20)

        econ['balance'] += total_profit
        econ['last_biz_collect'] = now
        mark_dirty()
        bot.answer_callback_query(call.id, f"💰 Собрано: +{total_profit} 🪙!", show_alert=True)
        render_business_view(chat_id, user_id, user_name, message_id=call.message.message_id)

    elif action_data.startswith('buy_veh_'):
        v_id = action_data.replace('buy_veh_', '')
        if v_id in VEHICLES:
            v_info = VEHICLES[v_id]
            econ = get_user_econ(user_id, user_name, username=user_username)
            cur_veh = econ.get('vehicle')
            cur_tier = VEHICLES[cur_veh]['tier'] if cur_veh in VEHICLES else 0
            new_tier = v_info.get('tier', 1)

            if cur_veh == v_id:
                bot.answer_callback_query(call.id, "❌ Этот транспорт уже в вашем гараже!", show_alert=True)
                return
            if cur_tier > new_tier:
                bot.answer_callback_query(call.id, f"❌ У вас уже есть более мощный транспорт ({VEHICLES[cur_veh]['name']})! Даунгрейд заблокирован.", show_alert=True)
                return
            if econ['balance'] < v_info['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {v_info['price']} 🪙!", show_alert=True)
                return

            econ['balance'] -= v_info['price']
            econ['vehicle'] = v_id
            mark_dirty()
            bot.answer_callback_query(call.id, f"🎉 Вы приобрели {v_info['name']}!", show_alert=True)
            render_garage_view(chat_id, user_id, user_name, call.message.message_id)

    elif action_data.startswith('buy_rod_'):
        r_id = action_data.replace('buy_rod_', '')
        if r_id in RODS:
            r_info = RODS[r_id]
            econ = get_user_econ(user_id, user_name, username=user_username)
            if econ['balance'] < r_info['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {r_info['price']} 🪙!", show_alert=True)
                return
            econ['balance'] -= r_info['price']
            econ['equipped_rod'] = r_id
            mark_dirty()
            bot.answer_callback_query(call.id, f"🎉 Вы экипировали {r_info['name']}!", show_alert=True)

    elif action_data.startswith('buy_bow_'):
        b_id = action_data.replace('buy_bow_', '')
        if b_id in BOWS:
            b_info = BOWS[b_id]
            econ = get_user_econ(user_id, user_name, username=user_username)
            if econ['balance'] < b_info['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {b_info['price']} 🪙!", show_alert=True)
                return
            econ['balance'] -= b_info['price']
            econ['equipped_bow'] = b_id
            mark_dirty()
            bot.answer_callback_query(call.id, f"🎉 Вы экипировали {b_info['name']}!", show_alert=True)

    # БАНК КНОПКИ
    elif action_data == 'bank_refresh':
        render_bank_view(chat_id, user_id, user_name, call.message.message_id)

    elif action_data == 'bank_dep_100':
        econ = get_user_econ(user_id, user_name, username=user_username)
        if econ['balance'] < 100:
            bot.answer_callback_query(call.id, "❌ Недостаточно средств на руках!", show_alert=True)
            return
        econ['balance'] -= 100
        econ['bank_deposit'] = econ.get('bank_deposit', 0) + 100
        check_achievements(user_id, user_name, 'bank_deposit', 100, chat_id, username=user_username)
        mark_dirty()
        bot.answer_callback_query(call.id, "✅ Внесено 100 🪙 на депозит!")
        render_bank_view(chat_id, user_id, user_name, call.message.message_id)

    elif action_data == 'bank_dep_all':
        econ = get_user_econ(user_id, user_name, username=user_username)
        b = econ.get('balance', 0)
        if b <= 0:
            bot.answer_callback_query(call.id, "❌ У вас нет наличных коинов!", show_alert=True)
            return
        econ['balance'] = 0
        econ['bank_deposit'] = econ.get('bank_deposit', 0) + b
        check_achievements(user_id, user_name, 'bank_deposit', b, chat_id, username=user_username)
        mark_dirty()
        bot.answer_callback_query(call.id, f"✅ Внесено {b} 🪙 на депозит!")
        render_bank_view(chat_id, user_id, user_name, call.message.message_id)

    elif action_data == 'bank_wd_100':
        econ = get_user_econ(user_id, user_name, username=user_username)
        if econ.get('bank_deposit', 0) < 100:
            bot.answer_callback_query(call.id, "❌ В банке меньше 100 🪙!", show_alert=True)
            return
        econ['bank_deposit'] -= 100
        econ['balance'] += 100
        mark_dirty()
        bot.answer_callback_query(call.id, "✅ Снято 100 🪙 с депозита!")
        render_bank_view(chat_id, user_id, user_name, call.message.message_id)

    elif action_data == 'bank_wd_all':
        econ = get_user_econ(user_id, user_name, username=user_username)
        dep = econ.get('bank_deposit', 0)
        if dep <= 0:
            bot.answer_callback_query(call.id, "❌ В банке нет средств!", show_alert=True)
            return
        econ['bank_deposit'] = 0
        econ['balance'] += dep
        mark_dirty()
        bot.answer_callback_query(call.id, f"✅ Снят весь вклад: {dep} 🪙!")
        render_bank_view(chat_id, user_id, user_name, call.message.message_id)

    # ЛОТЕРЕЯ
    elif action_data in ['buy_ticket_1', 'buy_ticket_5']:
        count = 1 if action_data == 'buy_ticket_1' else 5
        cost = count * 100
        econ = get_user_econ(user_id, user_name, username=user_username)

        if econ['balance'] < cost:
            bot.answer_callback_query(call.id, f"❌ Нужно {cost} 🪙!", show_alert=True)
            return

        econ['balance'] -= cost
        lottery = db.setdefault('lottery', {'tickets': {}, 'pot': 0, 'last_draw': 0})
        t_dict = lottery.setdefault('tickets', {})
        t_dict[str(user_id)] = t_dict.get(str(user_id), 0) + count
        lottery['pot'] = lottery.get('pot', 0) + cost

        bot.answer_callback_query(call.id, f"🎟 Куплено {count} бил.!")
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
            bot.send_message(chat_id, f"🎉 <b>РОЗЫГРЫШ ЛОТЕРЕИ СОСТОЯЛСЯ!</b>\n\n🏆 Джекпот <b>+{win_pot} Ня-коинов 🪙</b> забирает {w_link}!\nСледующий тираж уже открыт!", parse_mode='HTML')
        else:
            mark_dirty()
            render_lottery_view(chat_id, user_id, user_name, call.message.message_id)

    # ЧАТ-ДРОПЫ
    elif raw_data.startswith('claim_drop_') or action_data.startswith('claim_drop_'):
        drop_id = raw_data.replace('claim_', '').split(':')[0]
        drop = active_drops.get(drop_id)
        if not drop or drop.get('claimed'):
            bot.answer_callback_query(call.id, "❌ Этот подарок уже кто-то забрал!", show_alert=True)
            return

        drop['claimed'] = True
        reward = drop['reward']
        add_coins(user_id, user_name, reward, username=user_username)
        add_account_exp(user_id, user_name, 15, username=user_username)

        bot.answer_callback_query(call.id, f"🎉 Вы забрали +{reward} 🪙!")
        u_link = make_link(chat_id, user_name, user_id, ping=True)
        bot.edit_message_text(
            f"🎁 <b>ПОДАРОК ЗАБРАН!</b>\n\nБыстрее всех оказался(лась) {u_link} и забрал(а) <b>+{reward} Ня-коинов 🪙</b>!",
            chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML'
        )

    # ТРЕНИРОВКА ОПЫТА
    elif action_data == 'train_exp_btn':
        success, text_resp = train_work_exp(user_id, user_name, username=user_username)
        bot.answer_callback_query(call.id, text_resp.replace('<b>', '').replace('</b>', ''), show_alert=True)
        if success:
            econ = get_user_econ(user_id, user_name, username=user_username)
            lines = [
                "💼 <b>БИРЖА ТРУДА И ВАКАНСИЙ</b>", "──────────────────────",
                f"👤 Ваш опыт работы: <b>{econ.get('work_exp', 0)} EXP</b>\n", "<b>Доступные вакансии:</b>"
            ]
            for j_id, j in JOBS.items(): lines.append(f"• <b>{j['name']}</b>: от <code>{j['req_exp']} EXP</code> (З/П: {j['min_pay']}-{j['max_pay']} 🪙)")
            lines.append("──────────────────────")
            markup = InlineKeyboardMarkup()
            for job_id, job in JOBS.items():
                btn_text = f"{job['name']} ({job['req_exp']} EXP)"
                markup.add(InlineKeyboardButton(btn_text, callback_data=f"do_job_{job_id}:{user_id}"))
            markup.add(InlineKeyboardButton("🎓 Пройти тренировку (+EXP)", callback_data=f"train_exp_btn:{user_id}"))
            try: bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception: pass

    # РАБОТА
    elif action_data.startswith('do_job_'):
        job_id = action_data.replace('do_job_', '')
        if job_id in JOBS:
            job = JOBS[job_id]
            econ = get_user_econ(user_id, user_name, username=user_username)
            if econ.get('work_exp', 0) < job['req_exp']:
                bot.answer_callback_query(call.id, f"❌ Нужно минимум {job['req_exp']} EXP опыта!", show_alert=True)
                return
            now = time.time()
            cooldown = 1800
            left = cooldown_text(econ.get('last_work_time', 0), cooldown, econ)
            if left:
                bot.answer_callback_query(call.id, f"⏳ Отдохните еще: {left}", show_alert=True)
                return
            econ['last_work_time'] = now
            if random.randint(1, 100) <= job['chance']:
                pay = random.randint(job['min_pay'], job['max_pay'])
                econ['balance'] += pay
                econ['work_exp'] = econ.get('work_exp', 0) + job['exp_gain']
                add_account_exp(user_id, user_name, job['exp_gain'], username=user_username)
                check_achievements(user_id, user_name, 'work_shifts', 1, chat_id, username=user_username)
                mark_dirty()
                bot.answer_callback_query(call.id, f"✅ Зарплата: +{pay} 🪙 (+{job['exp_gain']} EXP)!", show_alert=True)
                bot.send_message(chat_id, f"💼 {make_link(chat_id, user_name, user_id, ping=True)} заработал(а) <b>+{pay} 🪙</b> на должности <b>{job['name']}</b>!", parse_mode='HTML')
            else:
                econ['work_exp'] = econ.get('work_exp', 0) + 2
                add_account_exp(user_id, user_name, 2, username=user_username)
                mark_dirty()
                bot.answer_callback_query(call.id, "❌ Вы ошиблись на смене! Получено +2 EXP.", show_alert=True)

    # БРАКИ
    elif raw_data.startswith('m_yes_') or raw_data.startswith('m_no_'):
        prop_id = raw_data[6:].split(':')[0]
        prop = pending_marriages.get(prop_id)
        if not prop:
            bot.answer_callback_query(call.id, "❌ Предложение устарело!", show_alert=True)
            return
        if user_id != prop['to_id'] and prop['to_id'] is not None:
            bot.answer_callback_query(call.id, "❌ Это предложение адресовано не вам!", show_alert=True)
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
            bot.edit_message_text(
                f"💒 <b>Горько! Свадьба состоялась!</b> 🎉\n\n{ring_emoji} {make_link(chat_id, prop['from_tag'], prop['from_id'], ping=True)} и {make_link(chat_id, user_name, user_id, ping=True)} теперь законные супруги! ❤️",
                chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML'
            )
        else:
            bot.edit_message_text(
                f"💔 {make_link(chat_id, user_name, user_id, ping=False)} отклонил(а) предложение руки и сердца.",
                chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML'
            )
        del pending_marriages[prop_id]

    # БЛЭКДЖЕК
    elif action_data.startswith('bj_hit_') or action_data.startswith('bj_stand_'):
        game_id = action_data.split('_', 2)[2]
        game = active_bj_games.get(game_id)
        if not game or game.get('finished'):
            bot.answer_callback_query(call.id, "❌ Игра окончена!", show_alert=True)
            return
        if user_id != game['user_id']:
            bot.answer_callback_query(call.id, "❌ Это не ваша игра!", show_alert=True)
            return

        if action_data.startswith('bj_hit_'):
            game['p_cards'].append(game['deck'].pop())
            p_score = calculate_bj_score(game['p_cards'])
            if p_score > 21:
                game['finished'] = True
                bot.edit_message_text(f"💥 <b>Перебор ({p_score})!</b> Вы проиграли <b>{game['bet']} 🪙</b>.\nВаши карты: {game['p_cards']}", chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML')
                del active_bj_games[game_id]
                return
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🃏 Взять карту", callback_data=f"bj_hit_{game_id}:{user_id}"), InlineKeyboardButton("✋ Хватит", callback_data=f"bj_stand_{game_id}:{user_id}"))
            bot.edit_message_text(f"🃏 Ваши карты: {game['p_cards']} (Сумма: <b>{p_score}</b>)\nДилер: [{game['d_cards'][0]}, ❓]", chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
        else:
            game['finished'] = True
            p_score = calculate_bj_score(game['p_cards'])
            while calculate_bj_score(game['d_cards']) < 17: game['d_cards'].append(game['deck'].pop())
            d_score = calculate_bj_score(game['d_cards'])

            if d_score > 21 or p_score > d_score:
                win = process_casino_win(game['bet'] * 2)
                add_coins(user_id, user_name, win, username=user_username)
                add_account_exp(user_id, user_name, 10, username=user_username)
                res = f"🎉 <b>Вы выиграли +{win} 🪙!</b>"
            elif p_score == d_score:
                add_coins(user_id, user_name, game['bet'], username=user_username)
                res = f"🤝 <b>Ничья!</b> Ставка {game['bet']} 🪙 возвращена."
            else:
                res = f"💸 <b>Дилер выиграл!</b> Проигрыш {game['bet']} 🪙."

            bot.edit_message_text(f"{res}\n\n👤 Ваши карты: {game['p_cards']} ({p_score})\n🤖 Карты дилера: {game['d_cards']} ({d_score})", chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML')
            del active_bj_games[game_id]

    # РПС (ЦУЕФА)
    elif action_data.startswith('rps_'):
        m_rps = re.match(r"^rps_([rsp])_(rps_\d+_\d+_\d+)$", action_data)
        if not m_rps:
            bot.answer_callback_query(call.id, "❌ Ошибка данных дуэли!", show_alert=True)
            return
        choice = m_rps.group(1)
        game_id = m_rps.group(2)
        game = active_rps_games.get(game_id)
        if not game:
            bot.answer_callback_query(call.id, "❌ Игра устарела!", show_alert=True)
            return

        if user_id == game['p1_id']: game['p1_choice'] = choice
        elif user_id == game['p2_id'] or game['p2_id'] is None:
            game['p2_id'] = user_id
            game['p2_tag'] = user_name
            game['p2_choice'] = choice
        else:
            bot.answer_callback_query(call.id, "❌ Вы не участвуете в этой дуэли!", show_alert=True)
            return

        bot.answer_callback_query(call.id, "✅ Ваш выбор принят!")

        if game['p1_choice'] and game['p2_choice']:
            c_map = {'r': '🪨 Камень', 's': '✂️ Ножницы', 'p': '📄 Бумага'}
            c1, c2 = game['p1_choice'], game['p2_choice']
            bet = game['bet']
            if c1 == c2: res = "🤝 <b>Ничья!</b> Коины возвращены игрокам."
            elif (c1 == 'r' and c2 == 's') or (c1 == 's' and c2 == 'p') or (c1 == 'p' and c2 == 'r'):
                add_coins(game['p1_id'], game['p1_tag'], bet * 2)
                res = f"🏆 Победил(а) {make_link(chat_id, game['p1_tag'], game['p1_id'], ping=True)}! (+{bet*2} 🪙)"
            else:
                add_coins(game['p2_id'], game['p2_tag'], bet * 2)
                res = f"🏆 Победил(а) {make_link(chat_id, game['p2_tag'], game['p2_id'], ping=True)}! (+{bet*2} 🪙)"

            bot.edit_message_text(f"✌️ <b>ИТОГИ ДУЭЛИ ЦУ-Е-ФА:</b>\n──────────────────────\n• {game['p1_tag']}: {c_map[c1]}\n• {game['p2_tag']}: {c_map[c2]}\n\n{res}", chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML')
            del active_rps_games[game_id]

    # НАСТРОЙКИ (КНОПКИ)
    elif action_data == 'set_max_days':
        if not is_admin(chat_id, user_id):
            bot.answer_callback_query(call.id, "❌ Только для админов!", show_alert=True)
            return
        sett = get_chat_settings(chat_id)
        opts = [14, 30, 60]
        next_opt = opts[(opts.index(sett['max_days']) + 1) % len(opts)]
        sett['max_days'] = next_opt
        mark_dirty()
        bot.answer_callback_query(call.id, f'✅ Лимит изменен на {next_opt} дней!')
        render_settings_view(chat_id, user_id=user_id, message_id=call.message.message_id)

    elif action_data == 'toggle_del_msg':
        if not is_admin(chat_id, user_id):
            bot.answer_callback_query(call.id, "❌ Только для админов!", show_alert=True)
            return
        sett = get_chat_settings(chat_id)
        sett['delete_rest_msg'] = not sett['delete_rest_msg']
        mark_dirty()
        bot.answer_callback_query(call.id, f"✅ Авто-удаление: {'Включено' if sett['delete_rest_msg'] else 'Выключено'}")
        render_settings_view(chat_id, user_id=user_id, message_id=call.message.message_id)

    elif action_data == 'toggle_summer_music':
        if not is_admin(chat_id, user_id):
            bot.answer_callback_query(call.id, "❌ Только для админов!", show_alert=True)
            return
        sett = get_chat_settings(chat_id)
        sett['summer_music'] = not sett.get('summer_music', True)
        mark_dirty()
        bot.answer_callback_query(call.id, f"✅ Музыка лета: {'Включена' if sett['summer_music'] else 'Выключена'}")
        render_settings_view(chat_id, user_id=user_id, message_id=call.message.message_id)

    elif action_data == 'set_remind_time':
        if not is_admin(chat_id, user_id):
            bot.answer_callback_query(call.id, "❌ Только для админов!", show_alert=True)
            return
        sett = get_chat_settings(chat_id)
        opts = [10, 60, 1440]
        next_opt = opts[(opts.index(sett.get('remind_minutes', 60)) + 1) % len(opts)]
        sett['remind_minutes'] = next_opt
        mark_dirty()
        bot.answer_callback_query(call.id, f'✅ Напоминание установлено за {next_opt} мин!')
        render_settings_view(chat_id, user_id=user_id, message_id=call.message.message_id)

    # МАГАЗИН ПАГИНАЦИЯ (ЗНАЧКИ)
    elif action_data.startswith('shop_cat_badges_'):
        page = int(action_data.replace('shop_cat_badges_', ''))
        items_per_page = 6
        items = list(BADGES.items())
        total_pages = (len(items) + items_per_page - 1) // items_per_page
        
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        current_items = items[start_idx:end_idx]

        lines = ["✨ <b>КАТАЛОГ ЗНАЧКОВ ДЛЯ ПРОФИЛЯ</b>", "──────────────────────", "<i>Значок отображается рядом с вашим ником в чате!</i>\n"]
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
        bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    # МАГАЗИН ПАГИНАЦИЯ (ТИТУЛЫ)
    elif action_data.startswith('shop_cat_titles_'):
        page = int(action_data.replace('shop_cat_titles_', ''))
        items_per_page = 5
        items = list(TITLES.items())
        total_pages = (len(items) + items_per_page - 1) // items_per_page
        
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        current_items = items[start_idx:end_idx]

        lines = ["👑 <b>КАТАЛОГ ТИТУЛОВ С ПАССИВНЫМИ БАФФАМИ</b>", "──────────────────────", "<i>Каждый титул дает постоянный бонус к удаче или доходу!</i>\n"]
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
        bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    # МАГАЗИН ПАГИНАЦИЯ (ПИТОМЦЫ)
    elif action_data.startswith('shop_cat_pets_'):
        page = int(action_data.replace('shop_cat_pets_', ''))
        items_per_page = 4
        items = list(PETS_DATA.items())
        total_pages = (len(items) + items_per_page - 1) // items_per_page
        
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        current_items = items[start_idx:end_idx]

        lines = ["🐾 <b>ЗОМАГАЗИН: ПИТОМЦЫ 2.0</b>", "──────────────────────", "<i>Питомцы помогают в охоте, рыбалке, и дают бонусы!</i>\n"]
        for p_k, p_v in current_items:
            lines.append(f"• <b>{p_v['name']}</b> — <code>{p_v['price']} 🪙</code>\n  <i>{p_v['desc']}</i>")
        lines.append(f"\nСтраница {page+1} из {total_pages}")
        lines.append("──────────────────────")

        markup = InlineKeyboardMarkup(row_width=2)
        btns = [InlineKeyboardButton(f"{p['short']} — {p['price']} 🪙", callback_data=f"buy_pet_{p_id}:{user_id}") for p_id, p in current_items]
        markup.add(*btns)
        
        nav_row = []
        if page > 0: nav_row.append(InlineKeyboardButton('⬅️ Назад', callback_data=f'shop_cat_pets_{page-1}:{user_id}'))
        if page < total_pages - 1: nav_row.append(InlineKeyboardButton('Вперед ➡️', callback_data=f'shop_cat_pets_{page+1}:{user_id}'))
        if nav_row: markup.add(*nav_row)

        markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data=f'shop_main:{user_id}'))
        bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    # ПОКУПКИ В МАГАЗИНЕ
    elif action_data == 'buy_cert_custom_title':
        econ = get_user_econ(user_id, user_name, username=user_username)
        if econ.get('has_custom_title_cert', False):
            bot.answer_callback_query(call.id, '❌ Сертификат уже куплен! Введите /custom_title', show_alert=True)
            return
        if econ['balance'] < CUSTOM_TITLE_CERT_PRICE:
            bot.answer_callback_query(call.id, f'❌ Нужно {CUSTOM_TITLE_CERT_PRICE} 🪙!', show_alert=True)
            return
        econ['balance'] -= CUSTOM_TITLE_CERT_PRICE
        econ['has_custom_title_cert'] = True
        mark_dirty()
        bot.answer_callback_query(call.id, '🎉 Сертификат приобретен! Установите титул: /custom_title Ваш Титул', show_alert=True)

    elif action_data.startswith('buy_ring_'):
        r_id = action_data.replace('buy_ring_', '')
        if r_id in RINGS:
            r_info = RINGS[r_id]
            econ = get_user_econ(user_id, user_name, username=user_username)
            if econ['balance'] < r_info['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {r_info['price']} 🪙!", show_alert=True)
                return
            econ['balance'] -= r_info['price']
            econ.setdefault('rings', []).append(r_id)
            mark_dirty()
            bot.answer_callback_query(call.id, f"🎉 Вы приобрели {r_info['name']}!", show_alert=True)

    elif action_data.startswith('buy_title_'):
        title_key = action_data.replace('buy_title_', '')
        if title_key in TITLES:
            item = TITLES[title_key]
            econ = get_user_econ(user_id, user_name, username=user_username)
            if title_key in econ.get('titles', []):
                bot.answer_callback_query(call.id, '❌ Титул уже куплен!', show_alert=True)
                return
            if econ['balance'] < item['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {item['price']} 🪙!", show_alert=True)
                return
            econ['balance'] -= item['price']
            econ.setdefault('titles', []).append(title_key)
            econ['active_title'] = title_key
            econ['custom_title'] = None
            mark_dirty()
            bot.answer_callback_query(call.id, f"🎉 Куплен титул {item['text']}!", show_alert=True)
            send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)

    elif action_data.startswith('buy_badge_'):
        badge_key = action_data.replace('buy_badge_', '')
        if badge_key in BADGES:
            item = BADGES[badge_key]
            econ = get_user_econ(user_id, user_name, username=user_username)
            if item['emoji'] in econ.get('inventory', []):
                bot.answer_callback_query(call.id, f"Значок {item['emoji']} уже есть!", show_alert=True)
                return
            if econ['balance'] < item['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {item['price']} 🪙!", show_alert=True)
                return
            econ['balance'] -= item['price']
            econ.setdefault('inventory', []).append(item['emoji'])
            econ['badge'] = item['emoji']
            mark_dirty()
            bot.answer_callback_query(call.id, f"🎉 Куплен значок {item['emoji']}!", show_alert=True)

    elif action_data.startswith('buy_pet_'):
        pet_id = action_data.replace('buy_pet_', '')
        if pet_id in PETS_DATA:
            p_data = PETS_DATA[pet_id]
            econ = get_user_econ(user_id, user_name, username=user_username)
            if econ['balance'] < p_data['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {p_data['price']} 🪙!", show_alert=True)
                return
            econ['balance'] -= p_data['price']
            econ['pet'] = {'id': pet_id, 'name': p_data['name'], 'luck_bonus': p_data['luck_bonus'], 'hunger': 100, 'cleanliness': 100, 'pet_exp': 0, 'last_update': time.time()}
            mark_dirty()
            bot.answer_callback_query(call.id, f"🎉 Вы завели питомца {p_data['name']}!", show_alert=True)
            render_pet_view(chat_id, user_id, user_name, call.message.message_id)

    # УПРАВЛЕНИЕ ПРОФИЛЕМ (ТИТУЛЫ И ЗНАЧКИ)
    elif action_data.startswith('set_title_'):
        title_key = action_data.replace('set_title_', '')
        econ = get_user_econ(user_id, user_name, username=user_username)
        if title_key in econ.get('titles', []) and title_key in TITLES:
            econ['active_title'] = title_key
            econ['custom_title'] = None
            mark_dirty()
            bot.answer_callback_query(call.id, f"✅ Надет титул {TITLES[title_key]['text']}!", show_alert=True)
            send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)

    elif action_data == 'remove_title':
        econ = get_user_econ(user_id, user_name, username=user_username)
        econ['active_title'] = None
        econ['custom_title'] = None
        mark_dirty()
        bot.answer_callback_query(call.id, '❌ Титул снят!', show_alert=True)
        send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)

    elif action_data.startswith('set_badge_'):
        selected_emoji = action_data.replace('set_badge_', '')
        econ = get_user_econ(user_id, user_name, username=user_username)
        if selected_emoji in econ.get('inventory', []):
            econ['badge'] = selected_emoji
            mark_dirty()
            bot.answer_callback_query(call.id, f"✅ Надет значок {selected_emoji}!", show_alert=True)
            send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)

    elif action_data == 'remove_badge':
        econ = get_user_econ(user_id, user_name, username=user_username)
        econ['badge'] = None
        mark_dirty()
        bot.answer_callback_query(call.id, "❌ Значок снят!", show_alert=True)
        send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)

# ---------------------------------------------------------
# СТАРТ И ИНИЦИАЛИЗАЦИЯ
# ---------------------------------------------------------
setup_bot_commands()
start_background_threads()
keep_alive()

print('Бот успешно запущен со всеми обновлениями (Карма, Стример, Сад, Краш, Защита, Режим Бога, Банк, Кирпич)!')
bot.infinity_polling()
