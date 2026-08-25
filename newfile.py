import csv
from datetime import datetime, timedelta
import html
import json
import os
import random
import re
import threading
import time
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from flask import Flask

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


# ID приватного канала для авто-бекапов базы данных
DB_CHANNEL_ID = normalize_tg_id(os.environ.get('DB_CHANNEL_ID', '-1004334874700'))

# Новый канал для логов действий, рестов, покупок и переводов
LOG_CHANNEL_ID = normalize_tg_id(os.environ.get('LOG_CHANNEL_ID', '-1004369517562'))
DATA_FILE = 'rests_data.json'

# Юзернейм администратора/разработчика
ADMIN_USERNAME = 'ukrgorilka'

# Медиа-канал
MEDIA_TG_CHAT_ID = normalize_tg_id(os.environ.get('MEDIA_TG_CHAT_ID', '-1004311479842'))
WHY_TG_MSG_IDS = [5, 9]
SUMMER_SONG_MSG_ID = 14

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
# ЭКОНОМИКА: ТОВАРЫ, ЗНАЧКИ, КОЛЬЦА
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

# 👑 ТИТУЛЫ С ПАССИВНЫМИ ЭФФЕКТАМИ
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

# ---------------------------------------------------------
# БИЗНЕСЫ 2.0 (С УРОВНЯМИ И ПРОКАЧКОЙ)
# ---------------------------------------------------------
BUSINESSES = {
    'coffee': {'name': '☕️ Уютная Кофейня', 'short': 'Кофейня', 'price': 2400, 'base_income': 35, 'upgrade_cost': 1800},
    'bakery': {'name': '🥐 Пекарня Булочек', 'short': 'Пекарня', 'price': 6000, 'base_income': 90, 'upgrade_cost': 4500},
    'crypto_farm': {'name': '💻 Крипто-Ферма', 'short': 'Крипто-Ферма', 'price': 18000, 'base_income': 280, 'upgrade_cost': 13000},
    'club': {'name': '🏰 Ночной Клуб', 'short': 'Ночной Клуб', 'price': 54000, 'base_income': 850, 'upgrade_cost': 38000},
    'autoshow': {'name': '🏎 Автосалон Спорткаров', 'short': 'Автосалон', 'price': 120000, 'base_income': 1800, 'upgrade_cost': 85000},
    'space_station': {'name': '🛰 Космическая Станция', 'short': 'Космостанция', 'price': 450000, 'base_income': 6500, 'upgrade_cost': 300000},
}

CUSTOM_TITLE_CERT_PRICE = 15000

# ---------------------------------------------------------
# СНАРЯЖЕНИЕ: УДОЧКИ И ЛУКИ
# ---------------------------------------------------------
RODS = {
    'rod_bamboo': {'name': '🎋 Бамбуковая удочка', 'short': '🎋 Бамбук', 'price': 500, 'luck': 10},
    'rod_carbon': {'name': '🎣 Карбоновый спиннинг', 'short': '🎣 Карбон', 'price': 2500, 'luck': 30},
    'rod_titan': {'name': '🔱 Удочка Посейдона', 'short': '🔱 Посейдон', 'price': 10000, 'luck': 70}
}

BOWS = {
    'bow_hunting': {'name': '🏹 Охотничий лук', 'short': '🏹 Охотничий', 'price': 600, 'luck': 10},
    'bow_sniper': {'name': '🎯 Снайперский лук', 'short': '🎯 Снайперский', 'price': 3000, 'luck': 35},
    'bow_phoenix': {'name': '🔥 Лук Феникса', 'short': '🔥 Феникс', 'price': 12000, 'luck': 80}
}

# ---------------------------------------------------------
# ГАРАЖ И ТРАНСПОРТ
# ---------------------------------------------------------
VEHICLES = {
    'scooter': {'name': '🛴 Электросамокат', 'short': '🛴 Самокат', 'price': 1500, 'cd_cut': 0.05, 'desc': '-5% ко всем таймерам'},
    'bike': {'name': '🏍 Спортбайк Yamaha', 'short': '🏍 Спортбайк', 'price': 7500, 'cd_cut': 0.12, 'desc': '-12% ко всем таймерам'},
    'bmw': {'name': '🚗 BMW M5 CS', 'short': '🚗 BMW M5', 'price': 30000, 'cd_cut': 0.22, 'desc': '-22% ко всем таймерам'},
    'ferrari': {'name': '🏎 Ferrari SF90', 'short': '🏎 Ferrari', 'price': 95000, 'cd_cut': 0.35, 'desc': '-35% ко всем таймерам'},
    'rocket': {'name': '🚀 Ракета SpaceX Starship', 'short': '🚀 Starship', 'price': 350000, 'cd_cut': 0.50, 'desc': '-50% ко всем таймерам'}
}

# ---------------------------------------------------------
# КРИПТО-БИРЖА
# ---------------------------------------------------------
MARKET_DEFAULT = {
    'NYA': {
        'name': '🐾 Ня-Биткоин (NYA)',
        'price': 120.0,
        'old_price': 110.0,
        'volatility': 0.18,
        'min_price': 15.0,
        'max_price': 3500.0,
        'last_update': 0
    },
    'MEOW': {
        'name': '🐱 Мяу-Эфириум (MEOW)',
        'price': 45.0,
        'old_price': 42.0,
        'volatility': 0.22,
        'min_price': 5.0,
        'max_price': 1200.0,
        'last_update': 0
    },
    'ANM': {
        'name': '🌸 Аниме-Акции (ANM)',
        'price': 15.0,
        'old_price': 14.0,
        'volatility': 0.28,
        'min_price': 1.0,
        'max_price': 500.0,
        'last_update': 0
    },
    'PAT': {
        'name': '🦶 Пятка-Коин (PAT)',
        'price': 5.0,
        'old_price': 6.0,
        'volatility': 0.35,
        'min_price': 0.5,
        'max_price': 200.0,
        'last_update': 0
    }
}

# ---------------------------------------------------------
# ПРОФЕССИИ
# ---------------------------------------------------------
JOBS = {
    'fermer': {'name': '👨‍🌾 Фермер', 'req_exp': 0, 'chance': 95, 'min_pay': 25, 'max_pay': 55, 'exp_gain': 10},
    'janitor': {'name': '🧹 Дворник', 'req_exp': 0, 'chance': 90, 'min_pay': 35, 'max_pay': 65, 'exp_gain': 12},
    'courier': {'name': '🛵 Курьер', 'req_exp': 50, 'chance': 80, 'min_pay': 75, 'max_pay': 145, 'exp_gain': 15},
    'cook': {'name': '👨‍🍳 Повар', 'req_exp': 150, 'chance': 70, 'min_pay': 145, 'max_pay': 290, 'exp_gain': 20},
    'office': {'name': '👨‍💻 Офисный клерк', 'req_exp': 350, 'chance': 60, 'min_pay': 280, 'max_pay': 550, 'exp_gain': 25},
    'programmer': {'name': '💻 Программист', 'req_exp': 800, 'chance': 45, 'min_pay': 650, 'max_pay': 1300, 'exp_gain': 35},
    'boss': {'name': '💼 Бизнесмен', 'req_exp': 1800, 'chance': 30, 'min_pay': 1500, 'max_pay': 3800, 'exp_gain': 50}
}

# ---------------------------------------------------------
# БОГАТЫЙ БЕСТИАРИЙ РЫБАЛКИ И ОХОТЫ
# ---------------------------------------------------------
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
]

# ---------------------------------------------------------
# ПИТОМЦЫ 2.0
# ---------------------------------------------------------
PETS_DATA = {
    'cat': {'name': '🐱 Котик Усач', 'short': '🐱 Котик', 'price': 720, 'luck_bonus': 15, 'desc': '+15% к удаче в охоте/рыбалке'},
    'dog': {'name': '🐶 Пёсель Верный', 'short': '🐶 Пёсель', 'price': 1450, 'luck_bonus': 25, 'desc': '+25% к удаче в охоте/рыбалке'},
    'fox': {'name': '🦊 Хитрая Лисичка', 'short': '🦊 Лисичка', 'price': 3000, 'luck_bonus': 40, 'desc': '+40% к удаче в охоте/рыбалке'},
    'owl': {'name': '🦉 Мудрая Сова', 'short': '🦉 Сова', 'price': 4800, 'luck_bonus': 60, 'desc': '+60% к удаче в охоте/рыбалке'},
    'raccoon': {'name': '🦝 Енот-Вор', 'short': '🦝 Енот', 'price': 6500, 'luck_bonus': 45, 'desc': '+20% к успеху ограблений'},
    'panda': {'name': '🐼 Панда Ленивец', 'short': '🐼 Панда', 'price': 8000, 'luck_bonus': 50, 'desc': '+35% к бонусу /bonus'},
    'dragon': {'name': '🐉 Маленький Дракон', 'short': '🐉 Дракончик', 'price': 12000, 'luck_bonus': 85, 'desc': '+85% к удаче во всем'},
    'unicorn': {'name': '🦄 Радужный Единорог', 'short': '🦄 Единорог', 'price': 25000, 'luck_bonus': 110, 'desc': '+110% ко всем доходам'}
}

# ---------------------------------------------------------
# ДОСТИЖЕНИЯ
# ---------------------------------------------------------
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
    'обнять': {'verb': 'крепко и тепло обнял(а)', 'emoji': '🫂✨'},
    'поцеловать': {'verb': 'нежно поцеловал(а) в щечку', 'emoji': '💋🌸'},
    'погладить': {'verb': 'ласково погладил(а) по голове', 'emoji': '🐱💆‍♂️'},
    'укусить': {'verb': 'сделал(а) игривый кусь за ушко', 'emoji': '🦷😼'},
    'кусь': {'verb': 'сделал(а) хрустящий кусь', 'emoji': '🐾😈'},
    'дать пять': {'verb': 'дал(а) звонкую и мощную пятерку', 'emoji': '✋🔥'},
    'ударить тапком': {'verb': 'с размаху огрел(а) тапком', 'emoji': '🩴💥'},
    'тапком': {'verb': 'метко запустил(а) тапок в', 'emoji': '🩴🎯'},
    'похвалить': {'verb': 'искренне похвалил(а) и назвал(а) умничкой', 'emoji': '🌟🥰'},
    'шлепнуть': {'verb': 'с чувством шлепнул(а)', 'emoji': '🍑👋'},
    'покормить': {'verb': 'заботливо покормил(а) с ложечки вкусняшкой', 'emoji': '🍰🥄'},
    'ущипнуть': {'verb': 'аккуратно ущипнул(а) за бочок', 'emoji': '🤏😏'},
    'утешить': {'verb': 'утешил(а), сказав, что всё обязательно будет хорошо', 'emoji': '🥺🕊'},
    'чихнуть': {'verb': 'громко чихнул(а) прямо на', 'emoji': '🤧💨'}
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

# Память для активных сессий
pending_marriages = {}
active_bj_games = {}
active_rps_games = {}
active_drops = {}
active_mines = {}
current_quiz = {'question': None, 'answer': None, 'reward': 0, 'chat_id': None}

# ---------------------------------------------------------
# БАЗА ДАННЫХ И БЕКАПЫ
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
        'lottery': {'tickets': {}, 'pot': 0, 'last_draw': 0}
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
                data = json.load(f)
                for key in ['settings', 'rests', 'history', 'economy', 'promos', 'market', 'marriages', 'lottery']:
                    if key not in data:
                        if key == 'lottery':
                            data[key] = {'tickets': {}, 'pot': 0, 'last_draw': 0}
                        else:
                            data[key] = {}
                return data
        except Exception as e:
            print(f'Ошибка чтения файла: {e}')

    return data


def save_data(send_backup=True):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=4)

        if send_backup and DB_CHANNEL_ID:
            with open(DATA_FILE, 'rb') as f:
                msg = bot.send_document(DB_CHANNEL_ID, f, caption="💾 Auto-backup rests_data.json")
                try:
                    bot.pin_chat_message(DB_CHANNEL_ID, msg.message_id, disable_notification=True)
                except Exception:
                    pass
    except Exception as e:
        print(f"Ошибка при сохранении бекапа в Telegram: {e}")


db = load_data()


def setup_bot_commands():
    commands = [
        BotCommand('menu', '📱 Главное интерактивное меню'),
        BotCommand('profile', '👤 Профиль, баланс и транспорт'),
        BotCommand('shop', '🏪 Магазин значков, титулов и питомцев'),
        BotCommand('wheel', '🎡 Бесплатное Колесо Фортуны'),
        BotCommand('mines', '💣 Игра Сапёр (Мины)'),
        BotCommand('dick', '🍆 Измерить размер писюна'),
        BotCommand('fap', '💦 Сделать ежедневный фап'),
        BotCommand('garage', '🏎 Гараж и личный транспорт'),
        BotCommand('cook', '🍳 Приготовить пойманную еду'),
        BotCommand('walk', '🦮 Отправить питомца на прогулку'),
        BotCommand('bank', '🏦 Ня-Банк и депозиты (+1% / 6ч)'),
        BotCommand('case', '📦 Ежедневный бесплатный кейс'),
        BotCommand('lottery', '🎟 Лотерея джекпота'),
        BotCommand('business', '🏢 Бизнесы 2.0 и прокачка'),
        BotCommand('miner', '💻 Криптоферма и майнинг NYA'),
        BotCommand('collect', '💰 Собрать прибыль предприятий'),
        BotCommand('family', '💍 Информация о браке и семье'),
        BotCommand('market', '📈 Крипто-биржа и котировки'),
        BotCommand('work', '💼 Биржа труда и вакансии'),
        BotCommand('train', '🎓 Тренировка опыта работы'),
        BotCommand('pet', '🐾 Ваш питомец и уход'),
        BotCommand('gear', '🎣 Магазин удочек и луков'),
        BotCommand('fish', '🎣 Отправиться на рыбалку'),
        BotCommand('hunt', '🏹 Отправиться на охоту'),
        BotCommand('sell', '💰 Продать весь улов и дичь'),
        BotCommand('bj', '🃏 Сыграть в Блэкджек (21)'),
        BotCommand('dice', '🎲 Кости'),
        BotCommand('slots', '🎰 Слоты'),
        BotCommand('tasks', '📋 Задания и квесты'),
        BotCommand('top', '🏆 Таблицы лидеров чата'),
        BotCommand('history', '📜 История рестов участника'),
        BotCommand('settings', '⚙️ Настройки бота в чате'),
        BotCommand('help', 'ℹ️ Полный справочник по всем командам')
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
        save_data(send_backup=False)

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

    return min(0.60, reduction)


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


def get_user_econ(user_id=None, user_tag=None):
    if 'economy' not in db:
        db['economy'] = {}

    key = get_global_user_key(user_id, user_tag)

    if user_id and key not in db['economy'] and user_tag:
        old_tag_key = f"tag_{clean_tag(user_tag).lower()}"
        if old_tag_key in db['economy']:
            db['economy'][key] = db['economy'].pop(old_tag_key)
            db['economy'][key]['user_id'] = user_id
            db['economy'][key]['display_name'] = clean_tag(user_tag)

    if key not in db['economy']:
        db['economy'][key] = {
            'display_name': clean_tag(user_tag) if user_tag else 'Пользователь',
            'user_id': user_id,
            'balance': 50,
            'bank_deposit': 0,
            'last_bank_calc': time.time(),
            'last_case_time': 0,
            'last_rob_time': 0,
            'account_exp': 0,
            'smeh': 0,
            'iq': 100,
            'fat': 20,
            'foot_size': 25,
            'dick_size': 15,
            'last_dick_time': 0,
            'fap_count': 0,
            'fap_date': '',
            'last_fap_time': 0,
            'chromosomes': 46,
            'last_hourly': 0,
            'last_iq_time': 0,
            'last_fat_time': 0,
            'last_foot_time': 0,
            'last_chromosomes_time': 0,
            'last_wheel_time': 0,
            'last_pet_walk': 0,
            'last_pet_care': 0,
            'badge': None,
            'inventory': [],
            'titles': [],
            'active_title': None,
            'custom_title': None,
            'has_custom_title_cert': False,
            'rings': [],
            'active_ring': None,
            'marriage': None,
            'businesses': {},
            'biz_levels': {},
            'last_biz_collect': time.time(),
            'vehicle': None,
            'equipped_rod': None,
            'equipped_bow': None,
            'daily_tasks_date': '',
            'daily_progress': {},
            'daily_claimed': [],
            'weekly_tasks_yearweek': '',
            'weekly_progress': {},
            'weekly_claimed': [],
            'fish_inventory': {},
            'hunt_inventory': {},
            'cooked_meals': 0,
            'crypto_portfolio': {},
            'last_fish_time': 0,
            'last_hunt_time': 0,
            'rest_rewards_count': 0,
            'achievements': [],
            'stats': {},
            'msg_stats': {
                'day_date': '',
                'day_count': 0,
                'week_key': '',
                'week_count': 0,
                'month_key': '',
                'month_count': 0,
                'total_count': 0
            },
            'work_exp': 0,
            'last_work_time': 0,
            'last_train_time': 0,
            'pet': None
        }
        save_data()

    u_data = db['economy'][key]
    if user_tag:
        u_data['display_name'] = clean_tag(user_tag)
    if user_id:
        u_data['user_id'] = user_id

    for field, default in [
        ('inventory', []), ('account_exp', 0), ('smeh', 0), ('iq', 100),
        ('fat', 20), ('foot_size', 25), ('dick_size', 15), ('last_dick_time', 0),
        ('fap_count', 0), ('fap_date', ''), ('last_fap_time', 0),
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
        ('last_case_time', 0), ('last_rob_time', 0)
    ]:
        if field not in u_data:
            u_data[field] = default

    if 'msg_stats' not in u_data:
        u_data['msg_stats'] = {
            'day_date': '', 'day_count': 0, 'week_key': '',
            'week_count': 0, 'month_key': '', 'month_count': 0, 'total_count': 0
        }

    update_bank_interest(u_data)

    if u_data.get('pet'):
        update_pet_stats(u_data['pet'])

    return u_data


def add_account_exp(user_id, user_tag, exp_amount=1):
    econ = get_user_econ(user_id, user_tag)
    active_t = econ.get('active_title')
    bonus = 1.0
    if active_t and active_t in TITLES and TITLES[active_t].get('buff') == 'exp_bonus':
        bonus += (TITLES[active_t]['val'] / 100.0)

    econ['account_exp'] = econ.get('account_exp', 0) + int(exp_amount * bonus)
    save_data(send_backup=False)


def add_message_stat(user_id, user_tag):
    econ = get_user_econ(user_id, user_tag)
    m_stats = econ.setdefault('msg_stats', {})
    now = datetime.now()

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

    add_account_exp(user_id, user_tag, 2)


def add_coins(user_id=None, user_tag=None, amount=0):
    user_data = get_user_econ(user_id, user_tag)
    user_data['balance'] += amount
    save_data()
    check_achievements(user_id, user_tag, 'balance_check', 0)
    return user_data['balance']


def log_event(event_type, message_text):
    if not LOG_CHANNEL_ID:
        return
    try:
        clean_text = message_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        clean_text = re.sub(r'&lt;b&gt;(.*?)&lt;/b&gt;', r'<b>\1</b>', clean_text)
        clean_text = re.sub(r'&lt;code&gt;(.*?)&lt;/code&gt;', r'<code>\1</code>', clean_text)
        clean_text = re.sub(r'&lt;a href="(.*?)"&gt;(.*?)&lt;/a&gt;', r'<a href="\1">\2</a>', clean_text)

        full_msg = f"📌 <b>[{html.escape(event_type)}]</b>\n⏱ <i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n\n{clean_text}"
        bot.send_message(LOG_CHANNEL_ID, full_msg, parse_mode='HTML')
    except Exception as e:
        print(f"[LOG ERROR] Не удалось отправить лог: {e}")


def check_achievements(user_id, user_tag, stat_name, amount=1, chat_id=None):
    econ = get_user_econ(user_id, user_tag)
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
                add_account_exp(user_id, user_tag, 50)
                unlocked_new.append((ach_info['title'], ach_info['desc'], reward))

    if unlocked_new:
        save_data(send_backup=False)
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
                    print(f"Ошибка уведомления ачивки: {e}")


def daily_task_date():
    return datetime.now().strftime('%Y-%m-%d')


def weekly_task_key():
    now = datetime.now()
    return f"{now.year}-W{now.isocalendar()[1]}"


def get_daily_tasks(user_id=None, user_tag=None):
    econ = get_user_econ(user_id, user_tag)
    today = daily_task_date()
    if econ.get('daily_tasks_date') != today:
        econ['daily_tasks_date'] = today
        econ['daily_progress'] = {}
        econ['daily_claimed'] = []
    return DAILY_TASKS[datetime.now().weekday()], econ


def get_weekly_tasks(user_id=None, user_tag=None):
    econ = get_user_econ(user_id, user_tag)
    w_key = weekly_task_key()
    if econ.get('weekly_tasks_yearweek') != w_key:
        econ['weekly_tasks_yearweek'] = w_key
        econ['weekly_progress'] = {}
        econ['weekly_claimed'] = []
    return WEEKLY_TASKS, econ


def track_daily_task(user_id, user_tag, task_key, amount=1, chat_id=None):
    completed = []
    check_achievements(user_id, user_tag, task_key, amount, chat_id)

    tasks, econ = get_daily_tasks(user_id, user_tag)
    progress = econ.setdefault('daily_progress', {})
    progress[task_key] = progress.get(task_key, 0) + amount

    for key, description, target, reward in tasks:
        if key not in econ.get('daily_claimed', []) and progress.get(key, 0) >= target:
            econ.setdefault('daily_claimed', []).append(key)
            econ['balance'] += reward
            add_account_exp(user_id, user_tag, 25)
            completed.append((f"Ежедневное: {description}", reward))

    w_tasks, _ = get_weekly_tasks(user_id, user_tag)
    w_progress = econ.setdefault('weekly_progress', {})
    w_progress[task_key] = w_progress.get(task_key, 0) + amount

    for key, description, target, reward in w_tasks:
        if key not in econ.get('weekly_claimed', []) and w_progress.get(key, 0) >= target:
            econ.setdefault('weekly_claimed', []).append(key)
            econ['balance'] += reward
            add_account_exp(user_id, user_tag, 100)
            completed.append((f"Еженедельное: {description}", reward))

    save_data(send_backup=False)
    return completed


def format_daily_tasks(user_id, user_tag):
    tasks, econ = get_daily_tasks(user_id, user_tag)
    w_tasks, _ = get_weekly_tasks(user_id, user_tag)
    weekdays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']

    lines = [
        f"📋 <b>ЗАДАНИЯ И КВЕСТЫ — {weekdays[datetime.now().weekday()].upper()}</b>",
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

    if str_chat in db.get('rests', {}):
        for r_key, r_info in db['rests'][str_chat].items():
            rec_uid = r_info.get('user_id')
            rec_name = r_info.get('user_name', r_key)
            if str(rec_uid) == clean_q or rec_name.lower() == clean_q or r_key.lower() == clean_q:
                return rec_uid, rec_name
            if clean_tag(rec_name).lower() == clean_q:
                return rec_uid, rec_name

    if 'economy' in db:
        for k, v in db['economy'].items():
            disp = v.get('display_name', '').lower()
            uid = v.get('user_id')
            if str(uid) == clean_q or disp == clean_q or clean_tag(disp).lower() == clean_q:
                return uid, v.get('display_name')

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


def parse_duration_to_seconds(duration_str, chat_id=None):
    duration_str = duration_str.lower().strip()
    duration_str = re.sub(r'^до\s+', '', duration_str)

    indefinite_markers = (
        'на неопределённый срок',
        'на неопределенный срок',
        'неопределённый срок',
        'неопределенный срок',
        'бессрочно',
        'без срока',
        'навсегда'
    )
    if any(marker in duration_str for marker in indefinite_markers):
        return None

    match_rel = re.search(r'(\d+)\s*(дней|дня|день|д|часов|часа|час|ч|минут|мин|м)\b', duration_str)
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


def add_to_history(chat_str, user, duration_text, reason, user_id=None, action_type="Выдан рест"):
    if chat_str not in db['history']:
        db['history'][chat_str] = {}
    clean_user = clean_tag(user)
    if clean_user not in db['history'][chat_str]:
        db['history'][chat_str][clean_user] = []
    entry = {
        'date': time.strftime('%Y-%m-%d %H:%M'),
        'action': action_type,
        'duration': duration_text,
        'reason': reason,
        'user_id': user_id,
    }
    db['history'][chat_str][clean_user].append(entry)


def schedule_rest_timers(chat_id, user_key, end_timestamp, target_user_id=None):
    def timer_thread():
        str_chat = str(chat_id)
        reminded = False
        while True:
            now = time.time()
            remaining = end_timestamp - now
            sett = get_chat_settings(chat_id)
            remind_sec = sett.get('remind_minutes', 60) * 60

            if remaining <= 0:
                if str_chat in db.get('rests', {}):
                    found_key = None
                    for k, info in list(db['rests'][str_chat].items()):
                        if k == user_key or (target_user_id and info.get('user_id') == target_user_id):
                            found_key = k
                            break

                    if found_key and db['rests'][str_chat][found_key].get('end_time') == end_timestamp:
                        u_name = db['rests'][str_chat][found_key].get('user_name', user_key)
                        del db['rests'][str_chat][found_key]
                        add_to_history(str_chat, u_name, 'Истек', 'Снятие по таймеру', target_user_id, "Снят рест (авто)")
                        save_data()
                        u_link = make_link(chat_id, u_name, target_user_id, ping=True)
                        log_event('РЕСТ СНЯТ (АВТО)', f'Чат: <code>{chat_id}</code>\nПользователь: {u_link}\nСтатус: Время реста истекло.')
                        try:
                            bot.send_message(chat_id, f'⏰ <b>Время реста для {u_link} истекло!</b> Рест автоматически снят.', parse_mode='HTML')
                        except Exception:
                            pass
                break

            if 0 < remaining <= remind_sec and not reminded:
                reminded = True
                mins = int(remind_sec / 60)
                u_link = make_link(chat_id, user_key, target_user_id, ping=True)
                try:
                    bot.send_message(chat_id, f'🔔 <b>Напоминание:</b> Рест у {u_link} закончится через {mins} мин!', parse_mode='HTML')
                except Exception:
                    pass

            time.sleep(min(remaining, 30))

    t = threading.Thread(target=timer_thread)
    t.daemon = True
    t.start()


def restore_timers():
    for str_chat, users in list(db['rests'].items()):
        chat_id = int(str_chat)
        for user_key, info in list(users.items()):
            end_time = info.get('end_time')
            u_id = info.get('user_id')
            if end_time:
                schedule_rest_timers(chat_id, user_key, end_time, u_id)


def apply_rest(chat_id, user_name, duration_text, reason='Не указана', target_user_id=None):
    str_chat = str(chat_id)
    if str_chat not in db['rests']:
        db['rests'][str_chat] = {}

    clean_user = clean_tag(user_name)
    seconds = parse_duration_to_seconds(duration_text, chat_id)
    is_indefinite = any(marker in duration_text.lower() for marker in (
        'на неопределённый срок',
        'на неопределенный срок',
        'неопределённый срок',
        'неопределенный срок',
        'бессрочно',
        'без срока',
        'навсегда'
    ))
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
    save_data()
    log_event('РЕСТ ВЫДАН', f'Чат: <code>{chat_id}</code>\nПользователь: {make_link(chat_id, clean_user, target_user_id, ping=False)}\nСрок: <b>{duration_text}</b>\nПричина: {reason}')
    if end_time:
        schedule_rest_timers(chat_id, rest_key, end_time, target_user_id)

    return reward_given, econ['rest_rewards_count']


# ---------------------------------------------------------
# ФОНОВЫЕ ПОТОКИ: ЛЕТО, ДРОПЫ, ВИКТОРИНЫ, НОВОСТИ БИРЖИ
# ---------------------------------------------------------
def summer_music_worker():
    while True:
        try:
            now_utc3 = datetime.utcnow() + timedelta(hours=3)
            current_year = now_utc3.year
            end_of_summer = datetime(current_year, 8, 31, 23, 59, 59)

            if now_utc3 <= end_of_summer and now_utc3.month in [6, 7, 8]:
                delta = end_of_summer - now_utc3
                days = delta.days
                hours, rem = divmod(delta.seconds, 3600)
                mins, _ = divmod(rem, 60)

                countdown_caption = (
                    "⏳ <b>Лето неумолимо утекает сквозь пальцы...</b>\n\n"
                    f"☀️ До конца лета осталось всего: <b>{days} дн. {hours} ч. {mins} мин.</b>\n"
                    "🎧 <i>Напоминание этого часа:</i>"
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
                        except Exception:
                            pass

            now_again = datetime.utcnow() + timedelta(hours=3)
            seconds_until_next_hour = (60 - now_again.minute) * 60 - now_again.second
            time.sleep(max(60, seconds_until_next_hour))

        except Exception as e:
            time.sleep(60)


def random_chat_drops_worker():
    while True:
        time.sleep(random.randint(5400, 9000))
        try:
            active_chats = [cid for cid in db.get('settings', {}).keys() if int(cid) < 0]
            if not active_chats:
                continue

            target_chat = int(random.choice(active_chats))
            reward = random.randint(60, 250)
            drop_id = f"drop_{int(time.time())}_{random.randint(100, 999)}"

            active_drops[drop_id] = {
                'chat_id': target_chat,
                'reward': reward,
                'claimed': False
            }

            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🎁 Забрать подарок!", callback_data=f"claim_{drop_id}"))

            msg_text = (
                "📦 <b>ВНЕЗАПНЫЙ ДРОП В ЧАТЕ!</b>\n"
                "──────────────────────\n"
                f"На полу чата найдена коробка с <b>{reward} Ня-коинами 🪙</b>!\n"
                "Кто первый нажмёт кнопку ниже — заберёт всю награду себе!"
            )
            bot.send_message(target_chat, msg_text, reply_markup=markup, parse_mode='HTML')

        except Exception as e:
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

            if mode == 'pump':
                new_p = round(min(asset.get('max_price', 3500.0), old_p * (1 + pct)), 2)
            else:
                new_p = round(max(asset.get('min_price', 1.0), old_p * (1 - pct)), 2)

            asset['old_price'] = old_p
            asset['price'] = new_p
            asset['last_update'] = time.time()
            save_data(send_backup=False)

            news_text = template.format(name=asset['name']) + f"\n\n📊 Новый курс <b>{ticker}</b>: <b>{new_p:.2f} 🪙</b> (Было: {old_p:.2f} 🪙)"

            active_chats = [cid for cid in db.get('settings', {}).keys() if int(cid) < 0]
            for str_chat_id in active_chats:
                try:
                    bot.send_message(int(str_chat_id), news_text, parse_mode='HTML')
                except Exception:
                    pass

        except Exception as e:
            pass


def chat_quiz_worker():
    quiz_questions = [
        ("🧮 <b>БЫСТРАЯ МАТЕМАТИКА</b>\nСколько будет: <code>45 + 18 * 3</code>?", "99", 150),
        ("🧮 <b>БЫСТРАЯ МАТЕМАТИКА</b>\nСколько будет: <code>150 - 45 * 2</code>?", "60", 120),
        ("🧮 <b>БЫСТРАЯ МАТЕМАТИКА</b>\nСколько будет: <code>12 * 12 + 6</code>?", "150", 140),
        ("🔤 <b>АНАГРАММА</b>\nСоберите слово из букв: <b>К О И Н Е М Е Т</b>", "экономика", 180),
        ("🔤 <b>АНАГРАММА</b>\nСоберите слово из букв: <b>Р Е С Т О П У К</b>", "проступок", 180),
        ("🔤 <b>АНАГРАММА</b>\nСоберите слово из букв: <b>К О Т И К М Я У</b>", "мяукотик", 200),
        ("🎬 <b>УГАДАЙ ФИЛЬМ ПО ЭМОДЗИ</b>\n🚢 🧊 👩‍❤️‍👨 🎻", "титаник", 180),
        ("🎬 <b>УГАДАЙ ФИЛЬМ ПО ЭМОДЗИ</b>\n🧙‍♂️ 🧝‍♂️ 💍 🌋 👁", "властелин колец", 220),
        ("🎬 <b>УГАДАЙ МУЛЬТФИЛЬМ ПО ЭМОДЗИ</b>\n🦁 👑 🐗 🐒 🌅", "король лев", 180),
        ("🎬 <b>УГАДАЙ ФИЛЬМ ПО ЭМОДЗИ</b>\n⚡️ 🧙‍♂️ 👓 🏰 🚂", "гарри поттер", 180),
    ]

    while True:
        time.sleep(random.randint(4800, 8400))
        try:
            active_chats = [cid for cid in db.get('settings', {}).keys() if int(cid) < 0]
            if not active_chats:
                continue

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

        except Exception as e:
            pass


def start_background_threads():
    threading.Thread(target=summer_music_worker, daemon=True).start()
    threading.Thread(target=random_chat_drops_worker, daemon=True).start()
    threading.Thread(target=market_news_worker, daemon=True).start()
    threading.Thread(target=chat_quiz_worker, daemon=True).start()


# ---------------------------------------------------------
# ПРИВЕТСТВИЕ И ПРОЩАНИЕ
# ---------------------------------------------------------
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_members(message):
    for member in message.new_chat_members:
        user_name = (f"{member.first_name or ''} {member.last_name or ''}").strip() or member.username
        user_link = make_link(message.chat.id, user_name, member.id, ping=True)
        add_coins(member.id, user_name, 50)

        welcome_text = (
            f"🎉 <b>Добро пожаловать в наш чат, {user_link}!</b>\n\n"
            f"🌸 Мы рады видеть тебя в нашей дружной семье!\n"
            f"💵 Тебе начислен приветственный подарок: <b>50 Ня-коинов 🪙</b>\n\n"
            f"💡 Введи <code>меню</code> или <code>/help</code>, чтобы открыть путеводитель."
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
# НАВИГАЦИОННОЕ МЕНЮ
# ---------------------------------------------------------
def get_main_menu_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🌴 Ресты и Отпуск", callback_data="help_rests"),
        InlineKeyboardButton("🏢 Бизнес 2.0 и Гараж", callback_data="help_biz")
    )
    markup.add(
        InlineKeyboardButton("💣 Сапёр и Игры", callback_data="help_games"),
        InlineKeyboardButton("🏦 Ня-Банк (+1%/6ч)", callback_data="help_bank")
    )
    markup.add(
        InlineKeyboardButton("💍 Семья и Подарки", callback_data="help_family"),
        InlineKeyboardButton("📈 Крипто-Биржа", callback_data="help_crypto")
    )
    markup.add(
        InlineKeyboardButton("🐾 Питомцы и Охота", callback_data="help_pets"),
        InlineKeyboardButton("🍆 Мемы и Замеры", callback_data="help_sims")
    )
    markup.add(
        InlineKeyboardButton("🎡 Колесо Фортуны", callback_data="help_wheel"),
        InlineKeyboardButton("💰 Экономика и Квесты", callback_data="help_econ")
    )
    return markup


@bot.message_handler(commands=['start', 'help', 'menu'])
def send_welcome(message):
    welcome_text = (
        "🤖 <b>ГЛАВНЫЙ НАВИГАТОР НЯ-БОТА</b>\n"
        "──────────────────────\n"
        "Добро пожаловать в центр управления всеми модулями, играми, бизнесом и отпусками!\n\n"
        "👇 <i>Выберите интересующий вас раздел:</i>"
    )
    bot.reply_to(message, welcome_text, reply_markup=get_main_menu_markup(), parse_mode='HTML')


# ---------------------------------------------------------
# КОЛЕСО ФОРТУНЫ (/wheel, /рулетка)
# ---------------------------------------------------------
@bot.message_handler(commands=['wheel', 'рулетка', 'колесо'])
def cmd_wheel(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name)

    now = time.time()
    last_spin = econ.get('last_wheel_time', 0)
    cooldown = 43200

    left = cooldown_text(last_spin, cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ <b>Колесо Фортуны доступно раз в 12 часов!</b>\nСледующее бесплатное вращение через: <b>{left}</b>.", parse_mode='HTML')
        return

    econ['last_wheel_time'] = now

    sectors = [
        ('coins_100', '💰 100 Ня-коинов', 30),
        ('coins_300', '💵 300 Ня-коинов', 20),
        ('jackpot', '💎 ДЖЕКПОТ 1,500 🪙', 5),
        ('fish', '🐟 Случайный редкий улов', 15),
        ('beast', '🏹 Охотничий трофей', 15),
        ('exp', '⭐ +80 Опыта профиля', 10),
        ('mini_rest', '🌴 Мини-курорт (Рест на 3 минуты)', 5)
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
        add_account_exp(user_id, user_name, 80)
        prize_text = "⭐ Вы получили <b>+80 EXP опыта профиля</b>!"
    elif win_key == 'mini_rest':
        apply_rest(message.chat.id, user_name, "3 минуты", "Выигрыш в Колесе Фортуны", user_id)
        prize_text = "🌴 Вы выиграли <b>3-минутный шуточный рест на курорте</b>!"

    check_achievements(user_id, user_name, 'wheel_spins', 1, message.chat.id)
    save_data()

    anim_text = (
        "🎡 <b>КОЛЕСО ФОРТУНЫ КРУТИТСЯ...</b>\n\n"
        "▫️ [ 💰 100 🪙 ]\n"
        "▫️ [ 💵 300 🪙 ]\n"
        "▫️ [ 💎 ДЖЕКПОТ 1,500 🪙 ]\n"
        "▫️ [ 🐟 Рыба / 🏹 Дичь ]\n"
        "▫️ [ 🌴 Мини-Рест ]\n\n"
        f"🎉 <b>Стрелка остановилась на секторе:</b>\n👉 <b>{win_sector[1]}</b>!\n\n"
        f"{prize_text}"
    )
    bot.reply_to(message, anim_text, parse_mode='HTML')


# ---------------------------------------------------------
# САПЁР / МИНЫ (/mines)
# ---------------------------------------------------------
def render_mines_board(game_id):
    game = active_mines.get(game_id)
    if not game:
        return None, None

    markup = InlineKeyboardMarkup(row_width=4)
    buttons = []

    for i in range(16):
        if i in game['revealed']:
            buttons.append(InlineKeyboardButton("💎", callback_data="noop"))
        elif game['finished'] and i in game['bombs']:
            buttons.append(InlineKeyboardButton("💣", callback_data="noop"))
        elif game['finished']:
            buttons.append(InlineKeyboardButton("▫️", callback_data="noop"))
        else:
            buttons.append(InlineKeyboardButton("❓", callback_data=f"mines_open_{game_id}_{i}"))

    for row_idx in range(0, 16, 4):
        markup.add(*buttons[row_idx:row_idx+4])

    if not game['finished'] and len(game['revealed']) > 0:
        cashout_amount = int(game['bet'] * game['current_multiplier'])
        markup.add(InlineKeyboardButton(f"💰 Забрать куш ({cashout_amount} 🪙 | {game['current_multiplier']:.2f}x)", callback_data=f"mines_cashout_{game_id}"))

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
    econ = get_user_econ(user_id, user_name)

    match = re.search(r'(?:/mines|мины|сапер)\s*(\d+)?', message.text, re.IGNORECASE)
    bet = int(match.group(1)) if match and match.group(1) else 50

    if bet <= 0:
        bot.reply_to(message, "❌ Ставка должна быть больше 0!")
        return

    if econ['balance'] < bet:
        bot.reply_to(message, f"❌ Недостаточно средств! У вас: {econ['balance']} 🪙")
        return

    econ['balance'] -= bet
    save_data()

    game_id = f"m_{user_id}_{int(time.time())}"
    bombs = set(random.sample(range(16), 3))

    active_mines[game_id] = {
        'user_id': user_id,
        'user_tag': user_name,
        'bet': bet,
        'bombs': bombs,
        'revealed': set(),
        'current_multiplier': 1.0,
        'finished': False
    }

    text, markup = render_mines_board(game_id)
    bot.reply_to(message, text, reply_markup=markup, parse_mode='HTML')


# ---------------------------------------------------------
# МЕМНЫЕ СИМУЛЯТОРЫ: ПИСЮН И ФАП
# ---------------------------------------------------------
@bot.message_handler(commands=['dick', 'писюн', 'замер'])
def cmd_dick(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name)

    now = time.time()
    last_time = econ.get('last_dick_time', 0)
    cooldown = 1200

    left = cooldown_text(last_time, cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Замер писюна доступен раз в 20 минут!\nПодождите: <b>{left}</b>.", parse_mode='HTML')
        return

    change = random.choice([-2, -1, 1, 1, 2, 3, 4])
    cur_size = econ.get('dick_size', 15)
    new_size = max(1, min(45, cur_size + change))

    econ['dick_size'] = new_size
    econ['last_dick_time'] = now
    save_data()

    sign = "+" if change >= 0 else ""
    u_link = make_link(chat_id, user_name, user_id, ping=True)

    if new_size >= 30:
        comment = "🍆 Настоящий гигант чата! Все трепещут!"
    elif new_size >= 18:
        comment = "🔥 Солидный и внушительный размерчик!"
    elif new_size >= 10:
        comment = "👌 Классический средний размер."
    else:
        comment = "🤏 Кажется, на улице было слишком холодно..."

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
    econ = get_user_econ(user_id, user_name)

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
    save_data()

    if count == 1:
        rank = "🌱 Начинающий любитель"
    elif count <= 3:
        rank = "🥋 Уверенный практик"
    elif count <= 6:
        rank = "🔥 Магистр мозолей"
    elif count <= 10:
        rank = "⚡️ Скоростной виртуоз"
    else:
        rank = "💀 Кибер-рука (Остановись, отвалится!)"

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
# ГАРАЖ И ТРАНСПОРТ (/garage)
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
        markup.add(InlineKeyboardButton(f"{v_info['short']} — {v_info['price']} 🪙", callback_data=f"buy_veh_{v_id}"))

    lines.append("──────────────────────")
    text = "\n".join(lines)

    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')


@bot.message_handler(commands=['garage', 'гараж'])
def cmd_garage(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_garage_view(message.chat.id, user_id, user_name)


# ---------------------------------------------------------
# КУЛИНАРИЯ (/cook, приготовить)
# ---------------------------------------------------------
@bot.message_handler(commands=['cook', 'кулинария', 'приготовить'])
def cmd_cook(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name)

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

    save_data()
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
# ПИТОМЕЦ (/pet, питомец, уход)
# ---------------------------------------------------------
def render_pet_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    pet = econ.get('pet')

    if not pet:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🐾 Открыть Зоомагазин", callback_data="shop_cat_pets"))
        text = (
            f"🐾 <b>У вас пока нет питомца!</b>\n\n"
            f"Купите верного друга в зоомагазине, чтобы получать бонусы к удаче, охоте и часовому доходу!"
        )
        if message_id:
            try:
                bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
                return
            except Exception:
                pass
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
        return

    update_pet_stats(pet)
    save_data(send_backup=False)

    hunger_bar = "🍗" * (pet.get('hunger', 100) // 20)
    clean_bar = "🧼" * (pet.get('cleanliness', 100) // 20)

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🍖 Покормить (30 🪙)", callback_data="pet_feed"),
        InlineKeyboardButton("🧼 Искупать (20 🪙)", callback_data="pet_wash")
    )
    markup.add(
        InlineKeyboardButton("🦮 Отправить гулять", callback_data="pet_walk_btn"),
        InlineKeyboardButton("🐾 Зоомагазин", callback_data="shop_cat_pets")
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
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')


@bot.message_handler(commands=['pet', 'питомец', 'пет'])
def cmd_pet(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_pet_view(message.chat.id, user_id, user_name)


# ---------------------------------------------------------
# ПРОГУЛКА ПИТОМЦА (/walk, гулять)
# ---------------------------------------------------------
def process_pet_walk(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    pet = econ.get('pet')

    if not pet:
        text = "❌ У вас нет питомца! Купите его в <code>/shop</code>."
        if message_id:
            bot.send_message(chat_id, text, parse_mode='HTML')
        else:
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
        ("fun", "погонял(а) бабочек и поднял(а) настроение чату", 50)
    ]

    ev_type, ev_desc, ev_val = random.choice(events)
    res_str = ""

    if ev_type in ['coins', 'gem', 'fun']:
        econ['balance'] += ev_val
        res_str = f"💰 Прибыль: <b>+{ev_val} Ня-коинов 🪙</b>!"
    elif ev_type == 'fish':
        add_inventory_item(econ['fish_inventory'], ev_val)
        res_str = f"🐟 Находка: <b>{ev_val}</b>!"

    pet['pet_exp'] = pet.get('pet_exp', 0) + 25
    save_data()

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
# МАГАЗИН СНАСТЕЙ (/gear, удочки, луки)
# ---------------------------------------------------------
@bot.message_handler(commands=['gear', 'снасти'])
def cmd_gear(message):
    lines = [
        "🎣 <b>МАГАЗИН ПРОФЕССИОНАЛЬНЫХ СНАСТЕЙ</b>",
        "──────────────────────",
        "<i>Удочки и луки многократно увеличивают шанс на легендарную и мифическую добычу!</i>\n",
        "<b>Доступные снасти:</b>"
    ]
    for r_id, r in RODS.items():
        lines.append(f"• <b>{r['name']}</b> — <code>{r['price']} 🪙</code> (+{r['luck']}% к удаче)")
    for b_id, b in BOWS.items():
        lines.append(f"• <b>{b['name']}</b> — <code>{b['price']} 🪙</code> (+{b['luck']}% к удаче)")
    lines.append("──────────────────────")

    markup = InlineKeyboardMarkup(row_width=2)
    rod_btns = [InlineKeyboardButton(f"{r_info['short']} — {r_info['price']} 🪙", callback_data=f"buy_rod_{r_id}") for r_id, r_info in RODS.items()]
    bow_btns = [InlineKeyboardButton(f"{b_info['short']} — {b_info['price']} 🪙", callback_data=f"buy_bow_{b_id}") for b_id, b_info in BOWS.items()]
    markup.add(*rod_btns[:2])
    markup.add(rod_btns[2])
    markup.add(*bow_btns[:2])
    markup.add(bow_btns[2])

    bot.reply_to(message, "\n".join(lines), reply_markup=markup, parse_mode='HTML')


# ---------------------------------------------------------
# БИЗНЕСЫ 2.0 (ПРОКАЧКА И ДОХОД)
# ---------------------------------------------------------
@bot.message_handler(commands=['business', 'бизнес', 'бизнесы', 'biz'])
def cmd_business(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
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
                markup.add(InlineKeyboardButton(f"⭐ Ап {b_info['short']} (ур. {lvl+1}) — {upg_cost} 🪙", callback_data=f"upg_biz_{b_id}"))
            else:
                markup.add(InlineKeyboardButton(f"👑 {b_info['short']} (МАКС 5 LVL)", callback_data="noop"))
        else:
            lines.append(f"• <b>{b_info['name']}</b> — <code>{b_info['price']} 🪙</code> (Базовый: {b_info['base_income']} 🪙/ч)")
            markup.add(InlineKeyboardButton(f"Купить {b_info['short']} — {b_info['price']} 🪙", callback_data=f"buy_biz_{b_id}"))

    markup.add(InlineKeyboardButton("💰 Собрать всю прибыль", callback_data="collect_biz_profit"))
    lines.append("──────────────────────")
    lines.append("🌴 <i>В ресте действует курортный бонус: +20% к прибыли!</i>")

    bot.reply_to(message, "\n".join(lines), reply_markup=markup, parse_mode='HTML')


# ---------------------------------------------------------
# МАЙНЕР / КРИПТОФЕРМА (/miner, майнер, майнинг)
# ---------------------------------------------------------
@bot.message_handler(commands=['miner', 'майнер', 'майнинг', 'ферма'])
def cmd_miner(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name)

    user_biz = econ.get('businesses', {})
    biz_levels = econ.get('biz_levels', {})
    has_farm = 'crypto_farm' in user_biz

    if not has_farm:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💻 Купить Крипто-Ферму (18,000 🪙)", callback_data="buy_biz_crypto_farm"))
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
        markup.add(InlineKeyboardButton(f"⭐ Улучшить видеокарты (ур. {lvl+1}) — {upg_cost} 🪙", callback_data="upg_biz_crypto_farm"))
    markup.add(InlineKeyboardButton("💰 Собрать прибыль с фермы", callback_data="collect_biz_profit"))

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
    econ = get_user_econ(user_id, user_name)
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
    save_data()

    bot.reply_to(message, f"💰 Собрана прибыль предприятий: <b>+{base_profit} Ня-коинов 🪙</b>!{event_text}\nБаланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')


# ---------------------------------------------------------
# ОБРАБОТЧИКИ БАНКА, КЕЙСА, ЛОТЕРЕИ
# ---------------------------------------------------------
def render_bank_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    interest_earned = update_bank_interest(econ)
    save_data(send_backup=False)

    deposit = econ.get('bank_deposit', 0)
    pocket = econ.get('balance', 0)

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📥 Внести 100 🪙", callback_data="bank_dep_100"),
        InlineKeyboardButton("📥 Внести всё", callback_data="bank_dep_all")
    )
    markup.add(
        InlineKeyboardButton("📤 Снять 100 🪙", callback_data="bank_wd_100"),
        InlineKeyboardButton("📤 Снять всё", callback_data="bank_wd_all")
    )
    markup.add(InlineKeyboardButton("🔄 Обновить баланс", callback_data="bank_refresh"))

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

    if interest_earned > 0:
        text += f"\n\n✨ <i>Начислены дивиденды: +{interest_earned} 🪙!</i>"

    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')


@bot.message_handler(commands=['bank', 'банк', 'депозит'])
def cmd_bank(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_bank_view(message.chat.id, message.from_user.id, user_name)


@bot.message_handler(commands=['case', 'кейс', 'сундук'])
def cmd_case(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name)

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

    add_account_exp(user_id, user_name, 20)
    check_achievements(user_id, user_name, 'cases_opened', 1, message.chat.id)
    save_data()

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
        InlineKeyboardButton("🎟 Купить 1 билет (100 🪙)", callback_data="buy_ticket_1"),
        InlineKeyboardButton("🎟 Купить 5 билетов (500 🪙)", callback_data="buy_ticket_5")
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
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')


@bot.message_handler(commands=['lottery', 'лотерея'])
def cmd_lottery(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    render_lottery_view(message.chat.id, message.from_user.id, user_name)


# ---------------------------------------------------------
# ИСТОРИЯ РЕСТОВ (/history, история)
# ---------------------------------------------------------
@bot.message_handler(commands=['history', 'история'])
def cmd_history(message):
    chat_id = message.chat.id
    str_chat = str(chat_id)
    target_user, target_user_id, _ = parse_target_and_args(message, '/history')
    if not target_user:
        target_user, target_user_id, _ = parse_target_and_args(message, 'история')

    if not target_user:
        target_user = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
        target_user_id = message.from_user.id

    clean_u = clean_tag(target_user)
    hist_entries = db.get('history', {}).get(str_chat, {}).get(clean_u, [])

    if not hist_entries:
        bot.reply_to(message, f"📜 История рестов для <b>{html.escape(clean_u)}</b> в этом чате пуста!", parse_mode='HTML')
        return

    lines = [
        f"📜 <b>ИСТОРИЯ РЕСТОВ: {make_link(chat_id, clean_u, target_user_id, ping=False)}</b>",
        "──────────────────────"
    ]
    for idx, item in enumerate(reversed(hist_entries[-8:]), 1):
        lines.append(
            f"<b>{idx}. {item.get('action', 'Рест')}</b> ({item.get('date', '—')})\n"
            f"⏱ Срок: <code>{item.get('duration', '—')}</code> | Причина: <i>{item.get('reason', 'Не указана')}</i>\n"
        )
    lines.append("──────────────────────")
    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')


# ---------------------------------------------------------
# НАСТРОЙКИ ЧАТА (/settings, настройки)
# ---------------------------------------------------------
def render_settings_view(chat_id, message_id=None):
    sett = get_chat_settings(chat_id)
    del_msg_status = "✅ Включено" if sett.get('delete_rest_msg', False) else "❌ Выключено"
    summer_status = "✅ Включена" if sett.get('summer_music', True) else "❌ Выключена"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"⏳ Макс. дней реста: {sett['max_days']} дн.", callback_data="set_max_days"))
    markup.add(InlineKeyboardButton(f"🗑 Авто-удаление смс в ресте: {del_msg_status}", callback_data="toggle_del_msg"))
    markup.add(InlineKeyboardButton(f"☀️ Музыка лета каждый час: {summer_status}", callback_data="toggle_summer_music"))
    markup.add(InlineKeyboardButton(f"🔔 Напоминание за: {sett.get('remind_minutes', 60)} мин.", callback_data="set_remind_time"))

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
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')


@bot.message_handler(commands=['settings', 'настройки'])
def cmd_settings(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Настройки доступны только администраторам чата!")
        return
    render_settings_view(message.chat.id)


# ---------------------------------------------------------
# ПРОФИЛЬ, МАГАЗИН И ТИТУЛЫ
# ---------------------------------------------------------
@bot.message_handler(commands=['custom_title', 'set_title'])
def cmd_custom_title(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name)

    if not econ.get('has_custom_title_cert', False):
        bot.reply_to(
            message,
            "❌ У вас нет <b>Сертификата на кастомный титул</b>!\nКупите его в <code>/shop</code> за 15,000 🪙.",
            parse_mode='HTML'
        )
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "❌ Укажите желаемый титул!\nПример: <code>/custom_title 👑 Главный Кот</code>", parse_mode='HTML')
        return

    new_title = parts[1].strip()[:32]
    econ['custom_title'] = new_title
    econ['active_title'] = None
    save_data()

    bot.reply_to(
        message,
        f"🎉 Ваш кастомный титул успешно установлен: <b>[{html.escape(new_title)}]</b>!",
        parse_mode='HTML'
    )


def send_user_profile(chat_id, user_tag, user_id, message_to_reply=None, message_id_to_edit=None):
    econ = get_user_econ(user_id, user_tag)
    markup = InlineKeyboardMarkup()

    purchased_titles = econ.get('titles', [])
    active_title = econ.get('active_title')
    custom_title = econ.get('custom_title')

    if purchased_titles:
        for title_key in purchased_titles:
            if title_key in TITLES and title_key != active_title:
                markup.add(InlineKeyboardButton(f"Надеть {TITLES[title_key]['text']}", callback_data=f"set_title_{title_key}"))
        if active_title or custom_title:
            markup.add(InlineKeyboardButton('❌ Снять текущий титул', callback_data='remove_title'))

    current_badge = econ.get('badge') or "Отсутствует"

    if custom_title:
        current_title = f"🌟 {html.escape(custom_title)} (Кастом)"
    elif active_title in TITLES:
        t_obj = TITLES[active_title]
        current_title = f"{t_obj['text']} ({t_obj['desc']})"
    else:
        current_title = 'Отсутствует'

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

    text = (
        f"👤 <b>КАРТОЧКА ИГРОКА: {make_link(chat_id, user_tag, user_id, ping=False)}</b>\n"
        f"──────────────────────\n"
        f"⭐ Уровень: <b>{lvl} LVL</b> [{bar}] (<b>{cur_exp}/{next_exp} EXP</b>)\n"
        f"💵 Баланс на руках: <b>{econ['balance']} Ня-коинов 💸</b>\n"
        f"🏦 В банке: <b>{econ.get('bank_deposit', 0)} 🪙</b>\n"
        f"🚘 Транспорт: <b>{veh_str}</b>\n"
        f"💼 Опыт работы: <b>{econ.get('work_exp', 0)} EXP</b>\n"
        f"💍 Семья: <b>{marriage_info}</b>\n"
        f"🏢 Бизнесы: <b>{biz_str}</b>\n"
        f"🐾 Питомец: <b>{pet_info}</b>\n"
        f"🏆 Достижения: <b>{unlocked_ach}/{total_ach}</b> (/achievements)\n"
        f"──────────────────────\n"
        f"📊 <b>Биометрия и мемные замеры:</b>\n"
        f"• 🍆 Писюн: <b>{econ.get('dick_size', 15)} см</b> | 💦 Фап за день: <b>{econ.get('fap_count', 0)}</b>\n"
        f"• 🧬 Хромосомы: <b>{econ.get('chromosomes', 46)}</b> | 🧠 IQ: <b>{econ.get('iq', 100)}</b>\n"
        f"• 🥩 Жир: <b>{econ.get('fat', 20)}%</b> | 🦶 Размер пятки: <b>{econ.get('foot_size', 25)} см</b>\n"
        f"──────────────────────\n"
        f"📊 <b>Активность сообщений:</b>\n{msg_stats_str}\n"
        f"📈 <b>Крипто-портфель:</b> {portfolio_str}\n"
        f"🏷 Значок: <b>{current_badge}</b> | Титул: <b>{current_title}</b>\n"
        f"🎒 Значки в инвентаре: {inv_str}\n"
        f"🐟 Улов: {fish_inv} | 🏹 Добыча: {hunt_inv}\n"
        f"──────────────────────"
    )

    if inv:
        row = []
        for emoji in inv:
            if emoji != current_badge:
                row.append(InlineKeyboardButton(f"Надеть {emoji}", callback_data=f"set_badge_{emoji}"))
                if len(row) == 3:
                    markup.add(*row)
                    row = []
        if row:
            markup.add(*row)
        if current_badge != "Отсутствует":
            markup.add(InlineKeyboardButton("❌ Снять значок", callback_data="remove_badge"))

    if message_id_to_edit:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id_to_edit, reply_markup=markup, parse_mode='HTML')
            return
        except Exception:
            pass

    if message_to_reply:
        bot.reply_to(message_to_reply, text, reply_markup=markup, parse_mode='HTML')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')


def send_shop_menu(chat_id, user_id, user_tag, message_id=None):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton('✨ Значки для профиля', callback_data='shop_cat_badges'))
    markup.add(InlineKeyboardButton('👑 Титулы с баффами', callback_data='shop_cat_titles'))
    markup.add(InlineKeyboardButton('💍 Обручальные кольца', callback_data='shop_cat_rings'))
    markup.add(InlineKeyboardButton('🐾 Зоомагазин (Питомцы 2.0)', callback_data='shop_cat_pets'))
    markup.add(InlineKeyboardButton('🏎 Автосалон (Гараж)', callback_data='shop_cat_garage'))

    text = (
        "🏪 <b>ГЛОБАЛЬНЫЙ МАГАЗИН НЯ-БОТА</b>\n"
        "──────────────────────\n"
        "Выберите интересующий вас каталог товаров:"
    )
    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')


# ---------------------------------------------------------
# БРАКИ, СЕМЬЯ И ПОДАРКИ
# ---------------------------------------------------------
@bot.message_handler(commands=['marry', 'брак'])
def cmd_marry(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name)

    if econ.get('marriage'):
        bot.reply_to(message, "❌ Вы уже состоите в браке! Чтобы развестись, введите: <code>развод</code>", parse_mode='HTML')
        return

    target_user, target_user_id, _ = parse_target_and_args(message, '/marry')
    if not target_user:
        target_user, target_user_id, _ = parse_target_and_args(message, 'брак')

    if not target_user:
        bot.reply_to(message, "❌ Укажите пользователя!\nПример: <code>брак @username</code> или ответом на сообщение.", parse_mode='HTML')
        return

    if target_user_id == user_id:
        bot.reply_to(message, "❌ Нельзя заключить брак с самим собой!")
        return

    target_econ = get_user_econ(target_user_id, target_user)
    if target_econ.get('marriage'):
        bot.reply_to(message, f"❌ Пользователь <b>{html.escape(target_user)}</b> уже состоит в браке!", parse_mode='HTML')
        return

    rings = econ.get('rings', [])
    chosen_ring = rings[0] if rings else 'copper'

    prop_id = f"{user_id}_{target_user_id or 0}_{int(time.time())}"
    pending_marriages[prop_id] = {
        'from_id': user_id,
        'from_tag': user_name,
        'to_id': target_user_id,
        'to_tag': target_user,
        'ring': chosen_ring
    }

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("💍 Согласиться", callback_data=f"m_yes_{prop_id}"),
        InlineKeyboardButton("❌ Отказать", callback_data=f"m_no_{prop_id}")
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
        reply_markup=markup,
        parse_mode='HTML'
    )


@bot.message_handler(commands=['family', 'семья'])
def cmd_family(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name)

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
    econ = get_user_econ(user_id, user_name)

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
    save_data()

    sender_l = make_link(message.chat.id, user_name, user_id, ping=True)
    partner_l = make_link(message.chat.id, p_tag, p_id, ping=True)

    bot.send_message(
        message.chat.id,
        f"💐 <b>РОМАНТИЧЕСКИЙ ПОДАРОК!</b>\n\n"
        f"{sender_l} преподнес(ла) роскошный букет цветов и сладости для {partner_l}! 💖🍫\n"
        f"Любовь крепнет с каждым днем! (+80 🪙 на счет любимого человека)",
        parse_mode='HTML'
    )


@bot.message_handler(commands=['divorce', 'развод'])
def cmd_divorce(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name)

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
    save_data()

    bot.reply_to(
        message,
        f"💔 <b>Брак расторгнут.</b>\n"
        f"Семейный сейф ({vault} 🪙) разделен поровну между бывшими супругами (+{split_coins} 🪙 каждому).",
        parse_mode='HTML'
    )


# ---------------------------------------------------------
# ИГРЫ: БЛЭКДЖЕК, ЦУЕФА, СЛОТЫ, КОСТИ
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
    econ = get_user_econ(user_id, user_name)

    if bet <= 0:
        bot.reply_to(message, "❌ Ставка должна быть больше 0!")
        return

    if econ['balance'] < bet:
        bot.reply_to(message, f"❌ Недостаточно Ня-коинов! У вас: {econ['balance']} 🪙")
        return

    econ['balance'] -= bet
    save_data()

    game_id = f"bj_{user_id}_{int(time.time())}"
    deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4
    random.shuffle(deck)

    p_cards = [deck.pop(), deck.pop()]
    d_cards = [deck.pop(), deck.pop()]

    active_bj_games[game_id] = {
        'user_id': user_id,
        'user_tag': user_name,
        'bet': bet,
        'deck': deck,
        'p_cards': p_cards,
        'd_cards': d_cards,
        'finished': False
    }

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🃏 Взять карту", callback_data=f"bj_hit_{game_id}"),
        InlineKeyboardButton("✋ Хватит", callback_data=f"bj_stand_{game_id}")
    )

    p_score = calculate_bj_score(p_cards)
    bot.send_message(
        chat_id,
        f"🃏 <b>БЛЭКДЖЕК (21 ОЧКО)</b>\n"
        f"──────────────────────\n"
        f"👤 Игрок: {make_link(chat_id, user_name, user_id, ping=True)}\n"
        f"💰 Ставка: <b>{bet} 🪙</b>\n\n"
        f"🎴 Ваши карты: {p_cards} (Сумма: <b>{p_score}</b>)\n"
        f"🤖 Дилер: [{d_cards[0]}, ❓]\n"
        f"──────────────────────",
        reply_markup=markup,
        parse_mode='HTML'
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
    econ = get_user_econ(user_id, user_name)

    target_user, target_user_id, raw_args = parse_target_and_args(message, '/rps')
    if not target_user:
        target_user, target_user_id, raw_args = parse_target_and_args(message, 'цуефа')

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
        'p1_id': user_id,
        'p1_tag': user_name,
        'p2_id': target_user_id,
        'p2_tag': target_user,
        'bet': bet,
        'p1_choice': None,
        'p2_choice': None
    }

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🪨 Камень", callback_data=f"rps_r_{game_id}"),
        InlineKeyboardButton("✂️ Ножницы", callback_data=f"rps_s_{game_id}"),
        InlineKeyboardButton("📄 Бумага", callback_data=f"rps_p_{game_id}")
    )

    bot.send_message(
        chat_id,
        f"✌️ <b>ДУЭЛЬ: КАМЕНЬ-НОЖНИЦЫ-БУМАГА!</b>\n"
        f"──────────────────────\n"
        f"⚔️ {make_link(chat_id, user_name, user_id, ping=True)} VS {make_link(chat_id, target_user, target_user_id, ping=True)}\n"
        f"💰 Ставка: <b>{bet} 🪙</b> с каждого!\n"
        f"──────────────────────\n"
        f"<i>Оба участника, нажмите свой тайный выбор на кнопках ниже:</i>",
        reply_markup=markup,
        parse_mode='HTML'
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

    lines.append("──────────────────────")
    lines.append("💡 <b>Как торговать:</b>")
    lines.append("• <code>купить крипту NYA 5</code>")
    lines.append("• <code>продать крипту NYA 5</code>")
    lines.append("• <code>портфель</code> — посмотреть свои активы")

    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')


@bot.message_handler(commands=['portfolio', 'портфель'])
def cmd_portfolio(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name)
    market = get_market_data()

    portfolio = econ.get('crypto_portfolio', {})
    total_val = 0.0

    lines = [
        f"💼 <b>ИНВЕСТИЦИОННЫЙ ПОРТФЕЛЬ: {make_link(message.chat.id, user_name, user_id, ping=False)}</b>",
        "──────────────────────"
    ]

    has_assets = False
    for ticker, amount in portfolio.items():
        if amount > 0.0001:
            has_assets = True
            cur_price = market.get(ticker, {}).get('price', 1.0)
            val = amount * cur_price
            total_val += val
            lines.append(f"• <b>{ticker}</b>: {amount:.2f} шт. (Оценка: <b>{val:.2f} 🪙</b>)")

    if not has_assets:
        lines.append("🎒 Ваш крипто-портфель пока пуст! Купите активы в <code>биржа</code>.")
    else:
        lines.append("──────────────────────")
        lines.append(f"📊 <b>Общая стоимость: {total_val:.2f} Ня-коинов 🪙</b>")

    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')


def trade_crypto(chat_id, user_id, user_tag, action, ticker, amount_str, reply_msg=None):
    market = get_market_data()
    ticker = ticker.upper().strip()

    if ticker not in market:
        available = ', '.join(market.keys())
        msg = f"❌ Неверный тикер! Доступные активы: <b>{available}</b>"
        if reply_msg:
            bot.reply_to(reply_msg, msg, parse_mode='HTML')
        else:
            bot.send_message(chat_id, msg, parse_mode='HTML')
        return

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
    except ValueError:
        msg = "❌ Укажите корректное положительное число монет!"
        if reply_msg:
            bot.reply_to(reply_msg, msg, parse_mode='HTML')
        else:
            bot.send_message(chat_id, msg, parse_mode='HTML')
        return

    econ = get_user_econ(user_id, user_tag)
    portfolio = econ.setdefault('crypto_portfolio', {})
    asset = market[ticker]
    price = asset['price']
    total_cost = round(price * amount, 2)

    if action == 'buy':
        if econ['balance'] < total_cost:
            msg = f"❌ Недостаточно коинов! Нужно <b>{total_cost:.2f} 🪙</b> (У вас: {econ['balance']} 🪙)."
            if reply_msg:
                bot.reply_to(reply_msg, msg, parse_mode='HTML')
            else:
                bot.send_message(chat_id, msg, parse_mode='HTML')
            return

        econ['balance'] -= int(total_cost)
        portfolio[ticker] = portfolio.get(ticker, 0.0) + amount
        check_achievements(user_id, user_tag, 'crypto_trades', 1, chat_id)
        add_account_exp(user_id, user_tag, 10)
        save_data()

        msg = (
            f"✅ <b>УСПЕШНАЯ ПОКУПКА!</b>\n"
            f"──────────────────────\n"
            f"Куплено: <b>{amount:.2f} {ticker}</b> ({asset['name']})\n"
            f"Списано: <b>-{total_cost:.2f} 🪙</b>\n"
            f"Остаток баланса: <b>{econ['balance']} 🪙</b>"
        )
        if reply_msg:
            bot.reply_to(reply_msg, msg, parse_mode='HTML')
        else:
            bot.send_message(chat_id, msg, parse_mode='HTML')

    elif action == 'sell':
        user_amount = portfolio.get(ticker, 0.0)
        if user_amount < amount:
            msg = f"❌ Недостаточно {ticker}! В наличии: <b>{user_amount:.2f} шт.</b>"
            if reply_msg:
                bot.reply_to(reply_msg, msg, parse_mode='HTML')
            else:
                bot.send_message(chat_id, msg, parse_mode='HTML')
            return

        portfolio[ticker] -= amount
        if portfolio[ticker] <= 0.0001:
            del portfolio[ticker]

        earned = int(total_cost)
        econ['balance'] += earned
        check_achievements(user_id, user_tag, 'crypto_trades', 1, chat_id)
        add_account_exp(user_id, user_tag, 10)
        save_data()

        msg = (
            f"💰 <b>УСПЕШНАЯ ПРОДАЖА!</b>\n"
            f"──────────────────────\n"
            f"Продано: <b>{amount:.2f} {ticker}</b>\n"
            f"Выручка: <b>+{earned} 🪙</b>\n"
            f"Новый баланс: <b>{econ['balance']} 🪙</b>"
        )
        if reply_msg:
            bot.reply_to(reply_msg, msg, parse_mode='HTML')
        else:
            bot.send_message(chat_id, msg, parse_mode='HTML')


# ---------------------------------------------------------
# СИСТЕМА РАБОТЫ И ТРЕНИРОВКИ
# ---------------------------------------------------------
def train_work_exp(user_id, user_tag):
    econ = get_user_econ(user_id, user_tag)
    now = time.time()
    cooldown = 900

    left = cooldown_text(econ.get('last_train_time', 0), cooldown, econ)
    if left:
        return False, f"⏳ Тренировка доступна раз в 15 минут! Ждать: <b>{left}</b>."

    gain = random.randint(15, 40)
    econ['work_exp'] = econ.get('work_exp', 0) + gain
    econ['last_train_time'] = now
    add_account_exp(user_id, user_tag, gain)
    save_data()
    return True, f"🎓 Вы усердно позанимались!\nПолучено: <b>+{gain} EXP</b> опыта работы (Всего: <b>{econ['work_exp']} EXP</b>)."


@bot.message_handler(commands=['work', 'работа'])
def cmd_work(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name)

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
        markup.add(InlineKeyboardButton(btn_text, callback_data=f"do_job_{job_id}"))

    markup.add(InlineKeyboardButton("🎓 Пройти тренировку (+EXP)", callback_data="train_exp_btn"))
    bot.reply_to(message, "\n".join(lines), reply_markup=markup, parse_mode='HTML')


@bot.message_handler(commands=['train', 'опыт'])
def cmd_train(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    _, text_resp = train_work_exp(user_id, user_name)
    bot.reply_to(message, text_resp, parse_mode='HTML')


@bot.message_handler(commands=['sell', 'продать'])
def cmd_sell(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name)

    total_earned = 0
    items_sold = 0

    for fish_name, count in list(econ.get('fish_inventory', {}).items()):
        price = 20
        for f_item in FISH_TYPES:
            if f_item[0] == fish_name:
                price = f_item[2]
                break
        total_earned += price * count
        items_sold += count
    econ['fish_inventory'] = {}

    for hunt_name, count in list(econ.get('hunt_inventory', {}).items()):
        price = 25
        for h_item in HUNT_TYPES:
            if h_item[0] == hunt_name:
                price = h_item[2]
                break
        total_earned += price * count
        items_sold += count
    econ['hunt_inventory'] = {}

    if items_sold == 0:
        bot.reply_to(message, "🎒 У вас нет рыбы или охотничьих трофеев для продажи!")
        return

    econ['balance'] += total_earned
    save_data()
    bot.reply_to(message, f"💰 Вы успешно продали добычу на сумму <b>+{total_earned} Ня-коинов 🪙</b>!\nБаланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')


@bot.message_handler(commands=['profile', 'профиль'])
def cmd_profile(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    send_user_profile(message.chat.id, user_name, message.from_user.id, message_to_reply=message)


@bot.message_handler(commands=['achievements', 'ачивки'])
def cmd_achievements(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name)
    unlocked = econ.get('achievements', [])

    lines = [
        f"🏆 <b>ДОСТИЖЕНИЯ: {make_link(message.chat.id, user_name, user_id, ping=False)}</b>",
        "──────────────────────"
    ]
    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id in unlocked:
            lines.append(f"✅ <b>{ach['title']}</b> — {ach['desc']} (+{ach['reward']} 🪙)")
        else:
            lines.append(f"🔒 <b>{ach['title']}</b> — {ach['desc']} (<b>+{ach['reward']} 🪙</b>)")

    lines.append("──────────────────────")
    lines.append(f"Прогресс: <b>{len(unlocked)}/{len(ACHIEVEMENTS)}</b> открыто.")

    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')


@bot.message_handler(commands=['balance', 'баланс'])
def cmd_balance(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(message.from_user.id, user_name)
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
    econ = get_user_econ(user_id, user_name)
    now_ts = time.time()
    cooldown = 1800

    left = cooldown_text(econ.get('last_iq_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Тест на IQ доступен раз в 30 минут!\nПодождите: <b>{left}</b>.", parse_mode='HTML')
        return

    change = random.randint(-5, 15)
    econ['iq'] = max(0, econ.get('iq', 100) + change)
    econ['last_iq_time'] = now_ts
    save_data()
    completed = track_daily_task(user_id, user_name, 'iq', 1, chat_id)
    sign = "+" if change >= 0 else ""

    bot.reply_to(message, f"🧠 {make_link(chat_id, user_name, user_id, ping=True)}, ваш IQ: <b>{econ['iq']} ({sign}{change}) 📊</b>", parse_mode='HTML')
    for task_name, task_reward in completed:
        bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')


@bot.message_handler(commands=['fat'])
def cmd_fat(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name)
    now_ts = time.time()
    cooldown = 1800

    left = cooldown_text(econ.get('last_fat_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Замер жира доступен раз в 30 минут!\nПодождите: <b>{left}</b>.", parse_mode='HTML')
        return

    change = random.randint(-4, 6)
    econ['fat'] = max(0, min(100, econ.get('fat', 20) + change))
    econ['last_fat_time'] = now_ts
    save_data()
    completed = track_daily_task(user_id, user_name, 'fat', 1, chat_id)
    sign = "+" if change >= 0 else ""

    bot.reply_to(message, f"🥩 {make_link(chat_id, user_name, user_id, ping=True)}, процент жира: <b>{econ['fat']}% ({sign}{change}%) 🍔</b>", parse_mode='HTML')
    for task_name, task_reward in completed:
        bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')


@bot.message_handler(commands=['foot'])
def cmd_foot(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name)
    now_ts = time.time()
    cooldown = 1200

    left = cooldown_text(econ.get('last_foot_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"⏳ Измерить пятку можно раз в 20 минут!\nПодождите: <b>{left}</b>.", parse_mode='HTML')
        return

    change = random.randint(-3, 4)
    econ['foot_size'] = max(5, min(60, econ.get('foot_size', 25) + change))
    econ['last_foot_time'] = now_ts
    save_data()
    sign = "+" if change >= 0 else ""

    bot.reply_to(message, f"🦶 {make_link(chat_id, user_name, user_id, ping=True)}, размер пятки: <b>{econ['foot_size']} см ({sign}{change} см) 🦶</b>", parse_mode='HTML')


@bot.message_handler(commands=['chromosomes', 'хромосомы', 'хромосома'])
def cmd_chromosomes(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name)
    now_ts = time.time()
    cooldown = 1200

    left = cooldown_text(econ.get('last_chromosomes_time', 0), cooldown, econ)
    if left:
        bot.reply_to(message, f"🧬 Генетический анализ доступен раз в 20 минут!\nПодождите: <b>{left}</b>.", parse_mode='HTML')
        return

    change = random.choice([-2, -1, 0, 1, 1, 2, 3])
    cur_chr = econ.get('chromosomes', 46)
    new_chr = max(38, min(60, cur_chr + change))
    econ['chromosomes'] = new_chr
    econ['last_chromosomes_time'] = now_ts
    save_data()

    completed = track_daily_task(user_id, user_name, 'chromosomes', 1, chat_id)
    check_achievements(user_id, user_name, 'chromosomes_check', 1, chat_id)
    sign = "+" if change >= 0 else ""

    if new_chr == 46:
        comment = "Идеальный человеческий баланс! ✨"
    elif new_chr == 47:
        comment = "Обнаружена экстра-хромосома сверхразума! ⚡️"
    elif new_chr > 47:
        comment = "Межгалактический уровень ДНК! 👽🚀"
    else:
        comment = "Кажется, пара хромосом взяли отгул... 🔍"

    u_link = make_link(chat_id, user_name, user_id, ping=True)
    bot.reply_to(
        message,
        f"🧬 <b>ГЕНЕТИЧЕСКИЙ ТЕСТ:</b> {u_link}\n"
        f"──────────────────────\n"
        f"Количество хромосом: <b>{new_chr} ({sign}{change}) 🧬</b>\n"
        f"📝 <i>{comment}</i>\n"
        f"──────────────────────",
        parse_mode='HTML'
    )
    for task_name, task_reward in completed:
        bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')


# ---------------------------------------------------------
# ИНТЕРАКТИВНЫЕ ТОПЫ С КНОПКАМИ
# ---------------------------------------------------------
def render_top_menu(chat_id, category='rich', message_id=None):
    econ_items = db.get('economy', {})
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💰 Богачи", callback_data="top_cat_rich"),
        InlineKeyboardButton("🍆 Писюн", callback_data="top_cat_dick")
    )
    markup.add(
        InlineKeyboardButton("🧠 IQ", callback_data="top_cat_iq"),
        InlineKeyboardButton("🥩 Жир", callback_data="top_cat_fat")
    )
    markup.add(
        InlineKeyboardButton("🦶 Пятки", callback_data="top_cat_foot"),
        InlineKeyboardButton("🧬 Хромосомы", callback_data="top_cat_chr")
    )
    markup.add(InlineKeyboardButton("💬 Сообщения (Актив)", callback_data="top_cat_msg"))

    if category == 'rich':
        sorted_data = sorted(econ_items.items(), key=lambda x: (x[1].get('balance', 0) + x[1].get('bank_deposit', 0)), reverse=True)
        title = "🏆 <b>ТОП БОГАЧЕЙ ЧАТА (Карман + Банк)</b>"
        val_formatter = lambda info: f"<b>{info.get('balance', 0) + info.get('bank_deposit', 0)} 🪙</b>"
    elif category == 'dick':
        sorted_data = sorted(econ_items.items(), key=lambda x: x[1].get('dick_size', 15), reverse=True)
        title = "🍆 <b>ТОП ПО РАЗМЕРУ ПИСЮНА</b>"
        val_formatter = lambda info: f"<b>{info.get('dick_size', 15)} см 📏</b>"
    elif category == 'iq':
        sorted_data = sorted(econ_items.items(), key=lambda x: x[1].get('iq', 100), reverse=True)
        title = "🧠 <b>ТОП ПО УРОВНЮ IQ</b>"
        val_formatter = lambda info: f"<b>{info.get('iq', 100)} IQ</b>"
    elif category == 'fat':
        sorted_data = sorted(econ_items.items(), key=lambda x: x[1].get('fat', 20), reverse=True)
        title = "🥩 <b>ТОП ПО ПРОЦЕНТУ ЖИРА</b>"
        val_formatter = lambda info: f"<b>{info.get('fat', 20)}% 🍔</b>"
    elif category == 'foot':
        sorted_data = sorted(econ_items.items(), key=lambda x: x[1].get('foot_size', 25), reverse=True)
        title = "🦶 <b>ТОП ПО РАЗМЕРУ ПЯТКИ</b>"
        val_formatter = lambda info: f"<b>{info.get('foot_size', 25)} см 🦶</b>"
    elif category == 'chr':
        sorted_data = sorted(econ_items.items(), key=lambda x: x[1].get('chromosomes', 46), reverse=True)
        title = "🧬 <b>ТОП ПО КОЛИЧЕСТВУ ХРОМОСОМ</b>"
        val_formatter = lambda info: f"<b>{info.get('chromosomes', 46)} 🧬</b>"
    elif category == 'msg':
        sorted_data = sorted(econ_items.items(), key=lambda x: x[1].get('msg_stats', {}).get('total_count', 0), reverse=True)
        title = "💬 <b>ТОП ПО СООБЩЕНИЯМ В ЧАТЕ</b>"
        val_formatter = lambda info: f"<b>{info.get('msg_stats', {}).get('total_count', 0)} смс</b>"
    else:
        sorted_data = []
        title = "🏆 <b>ТОП УЧАСТНИКОВ</b>"
        val_formatter = lambda info: ""

    lines = [
        title,
        "──────────────────────"
    ]

    for idx, (k, info) in enumerate(sorted_data[:10], 1):
        u_name = info.get('display_name', 'Пользователь')
        u_id = info.get('user_id')
        lines.append(f"{idx}. {make_link(chat_id, u_name, u_id, ping=False)} — {val_formatter(info)}")

    if not sorted_data:
        lines.append("<i>Данных для отображения пока нет...</i>")

    lines.append("──────────────────────")
    lines.append("👇 <i>Нажмите категорию ниже для переключения:</i>")

    text = "\n".join(lines)

    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')


@bot.message_handler(commands=['top', 'топ'])
def cmd_top(message):
    render_top_menu(message.chat.id, category='rich')


# ---------------------------------------------------------
# ГЛАВНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ И ОБЫЧНЫХ РУССКИХ СЛОВ
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

    add_message_stat(user_id, user_name)

    # ⚡️ ПРОВЕРКА ОТВЕТА НА ВИКТОРИНУ
    if current_quiz.get('answer') and current_quiz.get('chat_id') == chat_id:
        if text_lower == current_quiz['answer']:
            reward = current_quiz['reward']
            current_quiz['answer'] = None
            add_coins(user_id, user_name, reward)
            add_account_exp(user_id, user_name, 20)
            u_link = make_link(chat_id, user_name, user_id, ping=True)
            bot.reply_to(
                message,
                f"🎉 <b>ПРАВИЛЬНЫЙ ОТВЕТ!</b>\n\n"
                f"Первым(ой) правильно ответил(а) {u_link} и получает <b>+{reward} Ня-коинов 🪙</b> (+20 EXP)!",
                parse_mode='HTML'
            )
            return

    # 👑 КОМАНДЫ СОЗДАТЕЛЯ
    is_super_admin = (user_username == ADMIN_USERNAME.lower())

    if is_super_admin:
        if text_lower in ['/admin', '/admin_help', 'админ', 'админка']:
            admin_help_text = (
                "👑 <b>ПАНЕЛЬ УПРАВЛЕНИЯ СОЗДАТЕЛЯ (@ukrgorilka):</b>\n"
                "──────────────────────\n"
                "• <code>/take_coins @username 500</code> — списать коины\n"
                "• <code>/give_coins @username 1000</code> — выдать коины\n"
                "• <code>/stop_bot</code> — экстренная остановка и бекап\n"
                "──────────────────────"
            )
            bot.reply_to(message, admin_help_text, parse_mode='HTML')
            return

        if text_lower in ['/stop_bot', '/shutdown', 'выключить бота', 'остановить бота']:
            bot.reply_to(message, "🛑 <b>Бот экстренно останавливается...</b>\nДанные сохранены!", parse_mode='HTML')
            save_data(send_backup=True)
            log_event('ВЫКЛЮЧЕНИЕ', f'Бот остановлен администратором @{user_username}')
            time.sleep(1)
            os._exit(0)

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
                    if not t_uname:
                        t_uname = target_raw

            if not t_uname or t_amt <= 0:
                bot.reply_to(message, "❌ Формат: <code>/take_coins @username 500</code>", parse_mode='HTML')
                return

            t_econ = get_user_econ(t_uid, t_uname)
            t_econ['balance'] = max(0, t_econ.get('balance', 0) - t_amt)
            save_data()
            u_link = make_link(chat_id, t_uname, t_uid, ping=True)
            log_event('СПИСАНИЕ КОИНОВ', f'Админ @{user_username} списал {t_amt} 🪙 у {u_link}. Баланс: {t_econ["balance"]}')
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
                    if not t_uname:
                        t_uname = target_raw

            if not t_uname or t_amt <= 0:
                bot.reply_to(message, "❌ Формат: <code>/give_coins @username 1000</code>", parse_mode='HTML')
                return

            t_econ = get_user_econ(t_uid, t_uname)
            t_econ['balance'] = t_econ.get('balance', 0) + t_amt
            save_data()
            u_link = make_link(chat_id, t_uname, t_uid, ping=True)
            log_event('ВЫДАЧА КОИНОВ', f'Админ @{user_username} начислил {t_amt} 🪙 пользователю {u_link}.')
            bot.reply_to(message, f"🎁 <b>Начислено +{t_amt} 🪙</b> для {u_link}!\nБаланс: <b>{t_econ['balance']} 🪙</b>", parse_mode='HTML')
            return

    # ТОРГОВЛЯ НА БИРЖЕ ТЕКСТОМ
    m_crypto = re.match(r'^(купить|продать)\s+(?:крипту|акции|монеты)?\s*([a-zA-Z]{2,6})\s+([\d\.]+)$', text_lower)
    if m_crypto:
        action_type = 'buy' if m_crypto.group(1) == 'купить' else 'sell'
        ticker_val = m_crypto.group(2).upper()
        amount_val = m_crypto.group(3)
        trade_crypto(chat_id, user_id, user_name, action_type, ticker_val, amount_val, reply_msg=message)
        return

    # СЕМЕЙНЫЙ СЕЙФ
    if text_lower.startswith('семейный сейф'):
        econ = get_user_econ(user_id, user_name)
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
            if p_econ.get('marriage'):
                p_econ['marriage']['vault'] = m['vault']
            save_data()
            bot.reply_to(message, f"💍 Вы положили <b>{amt} 🪙</b> в семейный сейф!\nВ сейфе: <b>{m['vault']} 🪙</b>", parse_mode='HTML')
            return
        elif 'снять' in text_lower and m_amt:
            amt = int(m_amt.group(1))
            cur_vault = m.get('vault', 0)
            if amt <= 0 or cur_vault < amt:
                bot.reply_to(message, f"❌ В сейфе недостаточно коинов! Накоплено: {cur_vault} 🪙")
                return
            m['vault'] -= amt
            if p_econ.get('marriage'):
                p_econ['marriage']['vault'] = m['vault']
            econ['balance'] += amt
            save_data()
            bot.reply_to(message, f"💸 Вы взяли <b>{amt} 🪙</b> из семейного сейфа!\nОстаток: <b>{m['vault']} 🪙</b>", parse_mode='HTML')
            return

    # ОТСЛЕЖИВАНИЕ СООБЩЕНИЙ
    completed_tasks = track_daily_task(user_id, user_name, 'messages', 1, chat_id)
    if completed_tasks:
        for task_name, reward in completed_tasks:
            try:
                bot.send_message(chat_id, f'🎉 {make_link(chat_id, user_name, user_id, ping=True)} выполнил(а) задание: <b>{task_name}</b>! +{reward} 🪙', parse_mode='HTML')
            except Exception:
                pass

    if re.search(r'\b(почему|почему\??)\b', text_lower, re.IGNORECASE):
        chosen_msg_id = random.choice(WHY_TG_MSG_IDS)
        copied = False
        try:
            bot.copy_message(chat_id, from_chat_id=MEDIA_TG_CHAT_ID, message_id=chosen_msg_id, reply_to_message_id=message.message_id)
            copied = True
        except Exception:
            pass

        if not copied:
            chosen_gif = random.choice(WHY_GIFS)
            try:
                bot.send_animation(chat_id, chosen_gif, reply_to_message_id=message.message_id)
            except Exception:
                bot.reply_to(message, chosen_gif)
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
            if raw_arg:
                target_user_id, target_user = resolve_user_from_string(chat_id, raw_arg)

        if not target_user or target_user_id == user_id:
            bot.reply_to(message, "❌ Укажите жертву: <code>ограбить @username</code> или ответом на сообщение!", parse_mode='HTML')
            return

        econ = get_user_econ(user_id, user_name)
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
        check_achievements(user_id, user_name, 'robs', 1, chat_id)

        rob_chance = 0.40
        if econ.get('pet') and econ['pet'].get('id') == 'raccoon':
            rob_chance += 0.20

        if random.random() <= rob_chance:
            stolen = max(10, min(600, int(t_pocket * random.uniform(0.10, 0.20))))
            t_econ['balance'] -= stolen
            econ['balance'] += stolen
            save_data()
            u_link = make_link(chat_id, user_name, user_id, ping=True)
            t_link = make_link(chat_id, target_user, target_user_id, ping=True)
            log_event('ОГРАБЛЕНИЕ: УСПЕХ', f'{u_link} ограбил {t_link} на <b>{stolen} 🪙</b>!')
            bot.send_message(
                chat_id,
                f"🥷 <b>УДАЧНОЕ ОГРАБЛЕНИЕ!</b>\n\n"
                f"{u_link} ловко украл у {t_link} <b>{stolen} Ня-коинов 🪙</b>!",
                parse_mode='HTML'
            )
        else:
            fine = min(econ['balance'], random.randint(30, 90))
            if econ.get('active_title') == 'shadow_ninja':
                fine = int(fine * 0.5)

            econ['balance'] -= fine
            t_econ['balance'] += fine
            save_data()
            u_link = make_link(chat_id, user_name, user_id, ping=True)
            t_link = make_link(chat_id, target_user, target_user_id, ping=True)
            log_event('ОГРАБЛЕНИЕ: ПРОВАЛ', f'{u_link} попался при попытке ограбить {t_link}. Штраф: {fine} 🪙.')
            bot.send_message(
                chat_id,
                f"🚨 <b>ПРОВАЛ ОГРАБЛЕНИЯ!</b>\n\n"
                f"{u_link} попался с поличным и выплатил {t_link} компенсацию: <b>-{fine} 🪙</b>!",
                parse_mode='HTML'
            )
        return

    # БАНК ТЕКСТОМ
    if text_lower.startswith(('банк положить', 'депозит')):
        econ = get_user_econ(user_id, user_name)
        m_amt = re.search(r'(\d+)', text)
        if m_amt:
            amt = int(m_amt.group(1))
            if amt <= 0 or econ['balance'] < amt:
                bot.reply_to(message, f"❌ Недостаточно средств на руках! У вас: {econ['balance']} 🪙")
                return
            econ['balance'] -= amt
            econ['bank_deposit'] = econ.get('bank_deposit', 0) + amt
            econ['last_bank_calc'] = time.time()
            check_achievements(user_id, user_name, 'bank_deposit', amt, chat_id)
            save_data()
            log_event('БАНК: ВКЛАД', f'{make_link(chat_id, user_name, user_id, ping=False)} внес {amt} 🪙 на депозит.')
            bot.reply_to(message, f"🏦 Вы внесли <b>{amt} 🪙</b> на депозит в Ня-Банк!\nНа депозите: <b>{econ['bank_deposit']} 🪙</b>", parse_mode='HTML')
        return

    elif text_lower.startswith('банк снять всё'):
        econ = get_user_econ(user_id, user_name)
        dep = econ.get('bank_deposit', 0)
        if dep <= 0:
            bot.reply_to(message, "❌ Ваш банковский депозит пуст!")
            return
        econ['balance'] += dep
        econ['bank_deposit'] = 0
        econ['last_bank_calc'] = time.time()
        save_data()
        log_event('БАНК: СНЯТИЕ ВСЕГО', f'{make_link(chat_id, user_name, user_id, ping=False)} забрал весь депозит {dep} 🪙.')
        bot.reply_to(message, f"💸 Вы забрали весь вклад из банка: <b>+{dep} 🪙</b>!\nБаланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
        return

    elif text_lower.startswith('банк снять'):
        econ = get_user_econ(user_id, user_name)
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
            save_data()
            log_event('БАНК: СНЯТИЕ', f'{make_link(chat_id, user_name, user_id, ping=False)} снял {amt} 🪙 с депозита.')
            bot.reply_to(message, f"💸 Вы сняли <b>{amt} 🪙</b> с банковского счёта!\nОстаток в банке: <b>{econ['bank_deposit']} 🪙</b>", parse_mode='HTML')
        return

    # РП-ДЕЙСТВИЯ
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
                sender_link = make_link(chat_id, user_name, user_id, ping=True)
                target_link = make_link(chat_id, target_user, target_user_id, ping=True)
                check_achievements(user_id, user_name, 'rp_actions', 1, chat_id)
                add_account_exp(user_id, user_name, 3)
                bot.send_message(chat_id, f"{rp_data['emoji']} {sender_link} <b>{rp_data['verb']}</b> {target_link}!", parse_mode='HTML')
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
            bot.reply_to(
                message,
                f"🌴 <b>Пользователь {user_link} находится в ресте!</b>\n"
                f"📝 <b>Причина:</b> {html.escape(rest_info.get('reason', 'Не указана'))}\n"
                f"⏱ <b>Срок:</b> {html.escape(rest_info.get('duration', 'Не указан'))}",
                parse_mode='HTML'
            )
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
            except Exception:
                pass

    if text_lower in ['+смехуятинка', 'смехуятинка']:
        if message.reply_to_message:
            target_u = message.reply_to_message.from_user
            target_tag = (f"{target_u.first_name or ''} {target_u.last_name or ''}").strip() or target_u.username
            target_id = target_u.id

            econ = get_user_econ(target_id, target_tag)
            econ['smeh'] = econ.get('smeh', 0) + 1
            check_achievements(target_id, target_tag, 'smeh_check', 1, chat_id)
            save_data()

            u_link = make_link(chat_id, target_tag, target_id, ping=True)
            bot.reply_to(message, f"😂 Пользователю {u_link} начислено +1 очко <b>Смехуятинки</b>!\nВсего: <b>{econ['smeh']}</b>", parse_mode='HTML')
        else:
            bot.reply_to(message, "❌ Ответьте этой командой на сообщение человека!")
        return

    # ТЕКСТОВЫЕ КОМАНДЫ (БЕЗ СЛЭША)
    if text_lower in ['хромосомы', 'хромосома', 'замер хромосом']:
        cmd_chromosomes(message)
        return
    elif text_lower in ['айкью', 'iq', 'iqи', 'айкю']:
        cmd_iq(message)
        return
    elif text_lower in ['жир', 'жирок', 'жирность', 'процент жира']:
        cmd_fat(message)
        return
    elif text_lower in ['пятка', 'пяточка', 'размер пятки', 'пятки']:
        cmd_foot(message)
        return
    elif text_lower in ['писюн', 'член', 'замер']:
        cmd_dick(message)
        return
    elif text_lower in ['дроч', 'подрочить', 'фап']:
        cmd_fap(message)
        return
    elif text_lower in ['питомец', 'пет', 'мой питомец']:
        cmd_pet(message)
        return
    elif text_lower in ['майнер', 'майнинг', 'криптоферма', 'ферма']:
        cmd_miner(message)
        return
    elif text_lower in ['гараж', 'тачки', 'машины']:
        cmd_garage(message)
        return
    elif text_lower in ['кулинария', 'приготовить', 'готовка']:
        cmd_cook(message)
        return
    elif text_lower in ['гулять', 'погулять']:
        cmd_walk_pet(message)
        return
    elif text_lower in ['рулетка', 'колесо']:
        cmd_wheel(message)
        return
    elif text_lower in ['снасти', 'удочки', 'луки']:
        cmd_gear(message)
        return
    elif text_lower in ['ачивки', 'достижения']:
        cmd_achievements(message)
        return
    elif text_lower in ['бизнес', 'бизнесы']:
        cmd_business(message)
        return
    elif text_lower in ['собрать', 'собрать прибыль', 'прибыль']:
        cmd_collect(message)
        return
    elif text_lower in ['семья', 'брак', 'мой брак']:
        cmd_family(message)
        return
    elif text_lower in ['подарок']:
        cmd_gift(message)
        return
    elif text_lower in ['развод']:
        cmd_divorce(message)
        return
    elif text_lower in ['баланс', 'коины', 'ня-коины', 'деньги']:
        cmd_balance(message)
        return
    elif text_lower in ['инвентарь', 'профиль', 'мои значки']:
        cmd_profile(message)
        return
    elif text_lower in ['магазин', 'шоп']:
        cmd_shop(message)
        return
    elif text_lower in ['биржа', 'крипта', 'рынок']:
        cmd_market(message)
        return
    elif text_lower in ['портфель', 'мои акции']:
        cmd_portfolio(message)
        return
    elif text_lower in ['работа', 'вакансии']:
        cmd_work(message)
        return
    elif text_lower in ['опыт', 'тренировка']:
        cmd_train(message)
        return
    elif text_lower in ['кейс', 'сундук']:
        cmd_case(message)
        return
    elif text_lower in ['лотерея']:
        cmd_lottery(message)
        return
    elif text_lower in ['задания', 'квесты']:
        cmd_tasks(message)
        return
    elif text_lower in ['помощь', 'меню', 'навигатор']:
        send_welcome(message)
        return
    elif text_lower in ['настройки']:
        cmd_settings(message)
        return
    elif text_lower.startswith('история'):
        cmd_history(message)
        return

    # ТОПЫ ТЕКСТОМ
    elif text_lower in ['топ', 'топы', 'лидеры']:
        render_top_menu(chat_id, category='rich')
        return
    elif text_lower in ['топ богачей', 'топ баланс', 'топ денег']:
        render_top_menu(chat_id, category='rich')
        return
    elif text_lower in ['топ писюнов', 'топ писюн', 'топ член']:
        render_top_menu(chat_id, category='dick')
        return
    elif text_lower in ['топ айкью', 'топ iq', 'топ умных']:
        render_top_menu(chat_id, category='iq')
        return
    elif text_lower in ['топ жир', 'топ жира', 'топ жирных']:
        render_top_menu(chat_id, category='fat')
        return
    elif text_lower in ['топ пяток', 'топ пятка']:
        render_top_menu(chat_id, category='foot')
        return
    elif text_lower in ['топ хромосом', 'топ хромосомы']:
        render_top_menu(chat_id, category='chr')
        return
    elif text_lower in ['топ сообщений', 'топ актива', 'топ смс']:
        render_top_menu(chat_id, category='msg')
        return

    # САПЁР И БЛЭКДЖЕК ТЕКСТОМ
    elif text_lower.startswith(('сапер', 'мины')):
        cmd_mines(message)
        return
    elif text_lower.startswith(('блэкджек', '21', 'очко')):
        cmd_bj(message)
        return

    # БОНУС
    elif text_lower in ['бонус', 'коин', 'взять бонус']:
        econ = get_user_econ(user_id, user_name)
        now_ts = time.time()
        cooldown = 3600

        left = cooldown_text(econ.get('last_hourly', 0), cooldown, econ)
        if not left:
            lvl, _, _, _ = get_account_level(econ.get('account_exp', 0))
            reward = random.randint(20, 50) + (lvl * 3)

            active_t = econ.get('active_title')
            if active_t and active_t in TITLES and TITLES[active_t].get('buff') == 'bonus_coins':
                reward += TITLES[active_t]['val']

            if econ.get('pet') and econ['pet'].get('id') == 'panda':
                reward = int(reward * 1.35)

            econ['balance'] += reward
            econ['last_hourly'] = now_ts
            add_account_exp(user_id, user_name, 10)
            save_data()
            check_achievements(user_id, user_name, 'bonuses', 1, chat_id)
            completed = track_daily_task(user_id, user_name, 'bonus', 1, chat_id)
            bot.reply_to(
                message,
                f"🎲 Вы собрали часовой бонус: <b>+{reward} Ня-коинов 🪙</b>!\n"
                f"Баланс: <b>{econ['balance']} 💸</b>",
                parse_mode='HTML'
            )
            for task_name, task_reward in completed:
                bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        else:
            bot.reply_to(message, f"⏳ Бонус доступен каждый час! Ждать: <b>{left}</b>.", parse_mode='HTML')
        return

    # КОСТИ
    elif text_lower.startswith(('кости', '/dice', 'кубик')):
        match = re.search(r'(?:кости|/dice|кубик)\s*(\d+)?', text, re.IGNORECASE)
        bet = int(match.group(1)) if match and match.group(1) else 0

        econ = get_user_econ(user_id, user_name)
        if bet < 0 or bet > econ['balance']:
            bot.reply_to(message, '❌ Недостаточно Ня-коинов для ставки!')
            return
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        total = d1 + d2
        result = f'🎲 Выпало: <b>{d1} + {d2} = {total}</b>.'
        if bet:
            if total == 12:
                win = bet * 4
                econ['balance'] += win
                result += f'\n🎉 Джекпот! Вы выиграли <b>+{win} 🪙</b>!'
            elif total >= 8:
                win = bet
                econ['balance'] += win
                result += f'\n✅ Вы выиграли <b>+{win} 🪙</b>!'
            else:
                econ['balance'] -= bet
                result += f'\n💸 Вы проиграли <b>{bet} 🪙</b>.'
        add_account_exp(user_id, user_name, 5)
        save_data()
        check_achievements(user_id, user_name, 'games', 1, chat_id)
        completed = track_daily_task(user_id, user_name, 'dice', 1, chat_id)
        bot.reply_to(message, result + f"\n💰 Баланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
        for task_name, task_reward in completed:
            bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        return

    # СЛОТЫ
    elif text_lower.startswith(('слоты', '/slots', 'казино')):
        match = re.search(r'(?:слоты|/slots|казино)\s*(\d+)?', text, re.IGNORECASE)
        bet = int(match.group(1)) if match and match.group(1) else 0

        econ = get_user_econ(user_id, user_name)
        if bet <= 0:
            bot.reply_to(message, '❌ Укажите ставку! Пример: <code>слоты 100</code>', parse_mode='HTML')
            return
        if bet > econ['balance']:
            bot.reply_to(message, f"❌ Недостаточно коинов! Ваш баланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
            return

        symbols_pool = ['🍒', '🍋', '🍊', '🍀', '⭐', '💎']
        luck_bonus = econ['pet'].get('luck_bonus', 0) if econ.get('pet') else 0

        weights = [26, 23, 20, 15, 10 + int(luck_bonus * 0.05), 6 + int(luck_bonus * 0.04)]
        roll = random.choices(symbols_pool, weights=weights, k=3)
        result = f"🎰 <b>[ {roll[0]} | {roll[1]} | {roll[2]} ]</b>\n"

        if roll[0] == roll[1] == roll[2] == '💎':
            win = int(bet * 10)
            econ['balance'] += (win - bet)
            result += f'\n💎👑 <b>МЕГА ДЖЕКПОТ (10x)!</b> Выигрыш: <b>+{win} 🪙</b>!'
        elif roll[0] == roll[1] == roll[2] and roll[0] in ['⭐', '🍀']:
            multiplier = 5 if roll[0] == '⭐' else 4
            win = int(bet * multiplier)
            econ['balance'] += (win - bet)
            result += f'\n🌟 <b>ОГРОМНЫЙ ВЫИГРЫШ ({multiplier}x)!</b> Награда: <b>+{win} 🪙</b>!'
        elif roll[0] == roll[1] == roll[2]:
            win = int(bet * 2.5)
            econ['balance'] += (win - bet)
            result += f'\n🎉 <b>Три в ряд (2.5x)!</b> Выигрыш: <b>+{win} 🪙</b>!'
        elif roll.count('💎') == 2 or roll.count('⭐') == 2:
            win = int(bet * 1.5)
            econ['balance'] += (win - bet)
            result += f'\n✨ <b>Два редких символа!</b> Выигрыш: <b>+{win} 🪙</b> (1.5x)!'
        elif len(set(roll)) == 2:
            win = int(bet * 0.8)
            econ['balance'] += (win - bet)
            result += f'\n🙂 <b>Два совпадения!</b> Возврат: <b>{win} 🪙</b> (0.8x).'
        else:
            econ['balance'] -= bet
            result += f'\n💸 Проигрыш <b>-{bet} 🪙</b>.'

        add_account_exp(user_id, user_name, 5)
        save_data()
        check_achievements(user_id, user_name, 'games', 1, chat_id)
        completed = track_daily_task(user_id, user_name, 'slots', 1, chat_id)
        bot.reply_to(message, result + f"\n💰 Баланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
        for task_name, task_reward in completed:
            bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        return

    # РЫБАЛКА И ОХОТА
    elif text_lower in ['рыбалка', '/fish', 'рыба']:
        econ = get_user_econ(user_id, user_name)
        cooldown = 7200
        left = cooldown_text(econ.get('last_fish_time', 0), cooldown, econ)
        if left:
            bot.reply_to(message, f'⏳ Рыбалка доступна раз в 2 часа. Осталось: <b>{left}</b>.', parse_mode='HTML')
            return

        luck_bonus = econ['pet'].get('luck_bonus', 0) if econ.get('pet') else 0
        rod = econ.get('equipped_rod')
        if rod and rod in RODS:
            luck_bonus += RODS[rod]['luck']

        weights = [max(1, int(f[3] * (1 + luck_bonus / 100.0))) for f in FISH_TYPES]
        caught = random.choices(FISH_TYPES, weights=weights, k=1)[0]
        econ['last_fish_time'] = time.time()
        add_inventory_item(econ['fish_inventory'], caught[0])
        add_account_exp(user_id, user_name, 8)
        save_data()
        check_achievements(user_id, user_name, 'fish', 1, chat_id)
        bot.reply_to(message, f'🎣 Вы поймали: <b>{caught[0]}</b> [{caught[1]}]!\n💰 Базовая цена: <b>{caught[2]} 🪙</b>\n💡 Продать: <code>продать</code> | Приготовить: <code>/cook</code>', parse_mode='HTML')
        return

    elif text_lower in ['охота', '/hunt']:
        econ = get_user_econ(user_id, user_name)
        cooldown = 7200
        left = cooldown_text(econ.get('last_hunt_time', 0), cooldown, econ)
        if left:
            bot.reply_to(message, f'⏳ Охота доступна раз в 2 часа. Осталось: <b>{left}</b>.', parse_mode='HTML')
            return

        luck_bonus = econ['pet'].get('luck_bonus', 0) if econ.get('pet') else 0
        bow = econ.get('equipped_bow')
        if bow and bow in BOWS:
            luck_bonus += BOWS[bow]['luck']

        weights = [max(1, int(h[3] * (1 + luck_bonus / 100.0))) for h in HUNT_TYPES]
        caught = random.choices(HUNT_TYPES, weights=weights, k=1)[0]
        econ['last_hunt_time'] = time.time()
        add_inventory_item(econ['hunt_inventory'], caught[0])
        add_account_exp(user_id, user_name, 8)
        save_data()
        check_achievements(user_id, user_name, 'hunt', 1, chat_id)
        bot.reply_to(message, f'🏹 Вы добыли: <b>{caught[0]}</b> [{caught[1]}]!\n💰 Базовая цена: <b>{caught[2]} 🪙</b>\n💡 Продать: <code>продать</code> | Приготовить: <code>/cook</code>', parse_mode='HTML')
        return

    # ПЕРЕВОД КОИНОВ
    elif text_lower.startswith(('перевод', 'передать', '/pay')):
        target_u = None
        target_id = None
        amount = 0
        if message.reply_to_message:
            m_amount = re.search(r'(\d+)', text)
            if m_amount:
                amount = int(m_amount.group(1))
                replied_user = message.reply_to_message.from_user
                target_u = (f"{replied_user.first_name or ''} {replied_user.last_name or ''}").strip() or replied_user.username
                target_id = replied_user.id
        else:
            match = re.search(r'(?:перевод|передать|/pay)\s+(.+?)\s+(\d+)$', text, re.IGNORECASE)
            if match:
                raw_target = match.group(1).strip()
                amount = int(match.group(2))
                uid, uname = resolve_user_from_string(chat_id, raw_target)
                target_u = uname or raw_target
                target_id = uid

        if amount <= 0 or not target_u or target_id == user_id:
            bot.reply_to(message, "❌ Формат: <code>передать @username 100</code> или ответом на сообщение.", parse_mode='HTML')
            return

        sender_econ = get_user_econ(user_id, user_name)
        if sender_econ['balance'] < amount:
            bot.reply_to(message, "❌ Недостаточно Ня-коинов!", parse_mode='HTML')
            return

        tax = max(1, int(amount * 0.03))
        receive_amount = amount - tax

        sender_econ['balance'] -= amount
        add_coins(target_id, target_u, receive_amount)
        save_data()
        check_achievements(user_id, user_name, 'transfers', 1, chat_id)
        bot.reply_to(
            message,
            f"💸 Вы перевели <b>{amount} 🪙</b> пользователю {make_link(chat_id, target_u, target_id, ping=True)}!\n"
            f"<i>(Комиссия 3%: сожжено {tax} 🪙, зачислено {receive_amount} 🪙)</i>",
            parse_mode='HTML'
        )
        return

    # РЕСТЫ
    if text_lower.startswith('+рест'):
        if not is_admin(chat_id, user_id):
            return
        target_name, target_id, duration_text, reason = parse_rest_command(message)
        if target_name and duration_text:
            reward_given, count = apply_rest(chat_id, target_name, duration_text, reason, target_id)
            user_link = make_link(chat_id, target_name, target_id, ping=True)
            bot.reply_to(message, f'✅ Рест для {user_link} добавлен на {duration_text} (Причина: {reason})!', parse_mode='HTML')

    elif text_lower.startswith('-рест'):
        if not is_admin(chat_id, user_id):
            return

        target_name = None
        target_id = None

        if message.reply_to_message:
            u = message.reply_to_message.from_user
            target_name = (f"{u.first_name or ''} {u.last_name or ''}").strip() or u.username
            target_id = u.id
        else:
            raw_arg = text[5:].strip()
            if raw_arg:
                target_id, target_name = resolve_user_from_string(chat_id, raw_arg)

        if str_chat in db.get('rests', {}):
            in_rest, rest_info, found_key = check_user_rest(db['rests'][str_chat], user_id=target_id, user_name=target_name)
            if in_rest and found_key:
                display_name = rest_info.get('user_name', target_name or found_key)
                del db['rests'][str_chat][found_key]
                add_to_history(str_chat, display_name, 'Снят', 'Досрочно администратором', target_id, "Снят рест (вручную)")
                save_data()
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

    if call.data == 'noop':
        bot.answer_callback_query(call.id)
        return

    if call.data == 'help_main':
        try:
            bot.edit_message_text(
                "🤖 <b>ГЛАВНЫЙ НАВИГАТОР НЯ-БОТА</b>\n──────────────────────\nВыберите интересующий вас раздел:",
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=get_main_menu_markup(),
                parse_mode='HTML'
            )
        except Exception:
            pass

    elif call.data == 'help_wheel':
        text = (
            "🎡 <b>КОЛЕСО ФОРТУНЫ (/wheel)</b>\n"
            "──────────────────────\n"
            "Бесплатное вращение раз в 12 часов!\n\n"
            "• Призы: монеты, мега-джекпоты (1500 🪙), редкая рыба, дичь, шуточный мини-рест.\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data="help_main"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'help_sims':
        text = (
            "🍆 <b>МЕМНЫЕ СИМУЛЯТОРЫ И ЗАМЕРЫ</b>\n"
            "──────────────────────\n"
            "• <code>/dick</code> или <code>писюн</code> — замер размера\n"
            "• <code>/fap</code> или <code>дроч</code> — счетчик фапа и ранги\n"
            "• <code>хромосомы</code> — анализ ДНК\n"
            "• <code>iq</code> — тест интеллекта\n"
            "• <code>жир</code> — процент жира\n"
            "• <code>пятка</code> — размер пятки\n"
            "• <code>топ</code> — интерактивная таблица лидеров!\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data="help_main"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'help_rests':
        text = (
            "🌴 <b>СИСТЕМА РЕСТОВ И ОТПУСКОВ</b>\n"
            "──────────────────────\n"
            "• <code>+рест Иван 3 дня | отпуск</code> — выдать рест\n"
            "• <code>-рест @username</code> — снять рест\n"
            "• <code>история @username</code> — журнал рестов\n"
            "• <code>ресты</code> — список отдыхающих\n"
            "• <code>кто ты @username</code> — статус реста\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data="help_main"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'help_biz':
        text = (
            "🏢 <b>БИЗНЕСЫ 2.0 И ГАРАЖ</b>\n"
            "──────────────────────\n"
            "• <code>/business</code> — покупка и прокачка (1-5 LVL)\n"
            "• <code>/miner</code> — майнинг-ферма\n"
            "• <code>/garage</code> — покупка личного транспорта\n"
            "• <code>собрать прибыль</code> — сбор дохода с предприятий\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data="help_main"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'help_games':
        text = (
            "💣 <b>САПЁР И АЗАРТНЫЕ ИГРЫ</b>\n"
            "──────────────────────\n"
            "• <code>/mines 100</code> — игра в Сапёр на поле 4х4\n"
            "• <code>/bj 100</code> — Блэкджек (21 очко)\n"
            "• <code>слоты 100</code> — игровой автомат\n"
            "• <code>кости 100</code> — игра в кости\n"
            "• <code>/rps @username 100</code> — Цу-е-фа дуэль\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data="help_main"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'help_bank':
        text = (
            "🏦 <b>НЯ-БАНК И ДЕПОЗИТЫ</b>\n"
            "──────────────────────\n"
            "• <code>/bank</code> — меню депозита\n"
            "• <code>банк положить 500</code> — внести клад\n"
            "• <code>банк снять 500</code> — снять деньги\n"
            "📈 +1% каждые 6 часов (сложный процент)!\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data="help_main"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'help_family':
        text = (
            "💍 <b>БРАКИ И ПОДАРКИ</b>\n"
            "──────────────────────\n"
            "• <code>брак @username</code> — сделать предложение\n"
            "• <code>/family</code> — профиль пары и сейф\n"
            "• <code>подарок</code> — романтический подарок (100 🪙)\n"
            "• <code>семейный сейф положить 100</code>\n"
            "• <code>семейный сейф снять 100</code>\n"
            "• <code>развод</code> — расторгнуть брак\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data="help_main"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'help_crypto':
        text = (
            "📈 <b>КРИПТО-БИРЖА</b>\n"
            "──────────────────────\n"
            "• <code>биржа</code> — котировки монет\n"
            "• <code>купить крипту NYA 5</code> — покупка\n"
            "• <code>продать крипту NYA 5</code> — продажа\n"
            "• <code>портфель</code> — список активов\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data="help_main"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'help_pets':
        text = (
            "🐾 <b>ПИТОМЦЫ, КУЛИНАРИЯ И ОХОТА</b>\n"
            "──────────────────────\n"
            "• <code>/pet</code> — карточка питомца и уход\n"
            "• <code>/walk</code> — отправить питомца на прогулку за кладом\n"
            "• <code>/cook</code> — приготовить добычу для питомца\n"
            "• <code>/gear</code> — купить удочки и луки\n"
            "• <code>рыбалка</code> / <code>охота</code> — добыча\n"
            "• <code>продать</code> — продать трофеи\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data="help_main"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'help_econ':
        text = (
            "💰 <b>ЭКОНОМИКА И КВЕСТЫ</b>\n"
            "──────────────────────\n"
            "• <code>бонус</code> — часовые коины\n"
            "• <code>баланс</code>, <code>профиль</code> — вся статистика\n"
            "• <code>передать @user 100</code> — перевод коинов\n"
            "• <code>ачивки</code> — 42 достижения с наградами\n"
            "• <code>магазин</code> — значки, титулы, питомцы\n"
            "• <code>топ</code> — таблицы лидеров чата\n"
            "──────────────────────"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад в меню", callback_data="help_main"))
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    # ПЕРЕКЛЮЧЕНИЕ ТОПОВ
    elif call.data.startswith('top_cat_'):
        cat = call.data.replace('top_cat_', '')
        render_top_menu(chat_id, category=cat, message_id=call.message.message_id)

    # САПЁР
    elif call.data.startswith('mines_open_'):
        m_match = re.match(r"^mines_open_(m_\d+_\d+)_(\d+)$", call.data)
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
            loss_text = (
                f"💥 <b>БАБАХ! ВЫ НАСТУПИЛИ НА МИНУ!</b>\n\n"
                f"💸 Вы потеряли ставку: <b>{game['bet']} Ня-коинов 🪙</b>!\n\n"
                f"{text_board}"
            )
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
                add_coins(user_id, user_name, win_amt)
                add_account_exp(user_id, user_name, 50)
                check_achievements(user_id, user_name, 'mines_wins', 1, chat_id)
                save_data()
                text_board, markup = render_mines_board(game_id)
                win_text = (
                    f"🏆 <b>НЕВЕРОЯТНО! ВСЕ 13 КРИСТАЛЛОВ НАЙДЕНЫ!</b>\n\n"
                    f"💰 Выигрыш: <b>+{win_amt} Ня-коинов 🪙</b> (Множитель: <b>{game['current_multiplier']:.2f}x</b>)!\n\n"
                    f"{text_board}"
                )
                bot.edit_message_text(win_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                del active_mines[game_id]
                return

            text_board, markup = render_mines_board(game_id)
            bot.edit_message_text(text_board, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data.startswith('mines_cashout_'):
        game_id = call.data.replace('mines_cashout_', '')
        game = active_mines.get(game_id)
        if not game or game.get('finished'):
            bot.answer_callback_query(call.id, "❌ Игра окончена!", show_alert=True)
            return

        if user_id != game['user_id']:
            bot.answer_callback_query(call.id, "❌ Это не ваша игра!", show_alert=True)
            return

        game['finished'] = True
        win_amt = int(game['bet'] * game['current_multiplier'])
        add_coins(user_id, user_name, win_amt)
        add_account_exp(user_id, user_name, 15)
        check_achievements(user_id, user_name, 'mines_wins', 1, chat_id)
        save_data()

        text_board, markup = render_mines_board(game_id)
        cash_text = (
            f"💰 <b>ВЫ УСПЕШНО ЗАБРАЛИ КУШ!</b>\n\n"
            f"🎉 Начислено: <b>+{win_amt} Ня-коинов 🪙</b> (Коэффициент: <b>{game['current_multiplier']:.2f}x</b>)!\n\n"
            f"{text_board}"
        )
        bot.edit_message_text(cash_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
        del active_mines[game_id]

    # УХОД ЗА ПИТОМЦЕМ (КНОПКИ)
    elif call.data == 'pet_feed':
        econ = get_user_econ(user_id, user_name)
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
        check_achievements(user_id, user_name, 'pet_care', 1, chat_id)
        save_data()
        bot.answer_callback_query(call.id, "🍖 Питомец вкусно покушал (+10 EXP)!")
        render_pet_view(chat_id, user_id, user_name, call.message.message_id)

    elif call.data == 'pet_wash':
        econ = get_user_econ(user_id, user_name)
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
        check_achievements(user_id, user_name, 'pet_care', 1, chat_id)
        save_data()
        bot.answer_callback_query(call.id, "🧼 Питомец искупан до блеска (+10 EXP)!")
        render_pet_view(chat_id, user_id, user_name, call.message.message_id)

    elif call.data == 'pet_walk_btn':
        bot.answer_callback_query(call.id)
        process_pet_walk(chat_id, user_id, user_name)

    # ПРОКАЧКА БИЗНЕСА
    elif call.data.startswith('upg_biz_'):
        b_id = call.data.replace('upg_biz_', '')
        if b_id in BUSINESSES:
            b_info = BUSINESSES[b_id]
            econ = get_user_econ(user_id, user_name)
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
            save_data()
            bot.answer_callback_query(call.id, f"🎉 Предприятие улучшено до {cur_lvl+1} уровня!", show_alert=True)
            bot.send_message(chat_id, f"🏢 {make_link(chat_id, user_name, user_id, ping=True)} улучшил(а) <b>{b_info['name']}</b> до <b>{cur_lvl+1} LVL</b>!", parse_mode='HTML')

    # ПОКУПКА ТРАНСПОРТА
    elif call.data.startswith('buy_veh_'):
        v_id = call.data.replace('buy_veh_', '')
        if v_id in VEHICLES:
            v_info = VEHICLES[v_id]
            econ = get_user_econ(user_id, user_name)

            if econ.get('vehicle') == v_id:
                bot.answer_callback_query(call.id, "❌ Этот транспорт уже в вашем гараже!", show_alert=True)
                return

            if econ['balance'] < v_info['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {v_info['price']} 🪙!", show_alert=True)
                return

            econ['balance'] -= v_info['price']
            econ['vehicle'] = v_id
            save_data()
            bot.answer_callback_query(call.id, f"🎉 Вы приобрели {v_info['name']}!", show_alert=True)
            bot.send_message(chat_id, f"🏎 {make_link(chat_id, user_name, user_id, ping=True)} приобрел(а) новый транспорт — <b>{v_info['name']}</b> ({v_info['desc']})!", parse_mode='HTML')
            render_garage_view(chat_id, user_id, user_name, call.message.message_id)

    # ПОКУПКА СНАСТЕЙ
    elif call.data.startswith('buy_rod_'):
        r_id = call.data.replace('buy_rod_', '')
        if r_id in RODS:
            r_info = RODS[r_id]
            econ = get_user_econ(user_id, user_name)
            if econ['balance'] < r_info['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {r_info['price']} 🪙!", show_alert=True)
                return
            econ['balance'] -= r_info['price']
            econ['equipped_rod'] = r_id
            save_data()
            bot.answer_callback_query(call.id, f"🎉 Вы экипировали {r_info['name']}!", show_alert=True)

    elif call.data.startswith('buy_bow_'):
        b_id = call.data.replace('buy_bow_', '')
        if b_id in BOWS:
            b_info = BOWS[b_id]
            econ = get_user_econ(user_id, user_name)
            if econ['balance'] < b_info['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {b_info['price']} 🪙!", show_alert=True)
                return
            econ['balance'] -= b_info['price']
            econ['equipped_bow'] = b_id
            save_data()
            bot.answer_callback_query(call.id, f"🎉 Вы экипировали {b_info['name']}!", show_alert=True)

    # БАНК КНОПКИ
    elif call.data == 'bank_refresh':
        render_bank_view(chat_id, user_id, user_name, call.message.message_id)

    elif call.data == 'bank_dep_100':
        econ = get_user_econ(user_id, user_name)
        if econ['balance'] < 100:
            bot.answer_callback_query(call.id, "❌ Недостаточно средств на руках!", show_alert=True)
            return
        econ['balance'] -= 100
        econ['bank_deposit'] = econ.get('bank_deposit', 0) + 100
        check_achievements(user_id, user_name, 'bank_deposit', 100, chat_id)
        save_data()
        bot.answer_callback_query(call.id, "✅ Внесено 100 🪙 на депозит!")
        render_bank_view(chat_id, user_id, user_name, call.message.message_id)

    elif call.data == 'bank_dep_all':
        econ = get_user_econ(user_id, user_name)
        b = econ.get('balance', 0)
        if b <= 0:
            bot.answer_callback_query(call.id, "❌ У вас нет наличных коинов!", show_alert=True)
            return
        econ['balance'] = 0
        econ['bank_deposit'] = econ.get('bank_deposit', 0) + b
        check_achievements(user_id, user_name, 'bank_deposit', b, chat_id)
        save_data()
        bot.answer_callback_query(call.id, f"✅ Внесено {b} 🪙 на депозит!")
        render_bank_view(chat_id, user_id, user_name, call.message.message_id)

    elif call.data == 'bank_wd_100':
        econ = get_user_econ(user_id, user_name)
        if econ.get('bank_deposit', 0) < 100:
            bot.answer_callback_query(call.id, "❌ В банке меньше 100 🪙!", show_alert=True)
            return
        econ['bank_deposit'] -= 100
        econ['balance'] += 100
        save_data()
        bot.answer_callback_query(call.id, "✅ Снято 100 🪙 с депозита!")
        render_bank_view(chat_id, user_id, user_name, call.message.message_id)

    elif call.data == 'bank_wd_all':
        econ = get_user_econ(user_id, user_name)
        dep = econ.get('bank_deposit', 0)
        if dep <= 0:
            bot.answer_callback_query(call.id, "❌ В банке нет средств!", show_alert=True)
            return
        econ['bank_deposit'] = 0
        econ['balance'] += dep
        save_data()
        bot.answer_callback_query(call.id, f"✅ Снят весь вклад: {dep} 🪙!")
        render_bank_view(chat_id, user_id, user_name, call.message.message_id)

    # ЛОТЕРЕЯ
    elif call.data in ['buy_ticket_1', 'buy_ticket_5']:
        count = 1 if call.data == 'buy_ticket_1' else 5
        cost = count * 100
        econ = get_user_econ(user_id, user_name)

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
            for uid, t_count in t_dict.items():
                pool.extend([uid] * t_count)

            winner_id = int(random.choice(pool))
            win_pot = lottery['pot']
            w_econ = get_user_econ(user_id=winner_id)
            w_econ['balance'] += win_pot

            lottery['tickets'] = {}
            lottery['pot'] = 0
            lottery['last_draw'] = time.time()
            save_data()

            w_link = make_link(chat_id, w_econ.get('display_name', 'Игрок'), winner_id, ping=True)
            log_event('ЛОТЕРЕЯ: ДЖЕКПОТ', f'Победитель {w_link} сорвал джекпот <b>{win_pot} 🪙</b>!')
            bot.send_message(chat_id, f"🎉 <b>РОЗЫГРЫШ ЛОТЕРЕИ СОСТОЯЛСЯ!</b>\n\n🏆 Джекпот <b>+{win_pot} Ня-коинов 🪙</b> забирает {w_link}!\nСледующий тираж уже открыт!", parse_mode='HTML')
        else:
            save_data()
            render_lottery_view(chat_id, user_id, user_name, call.message.message_id)

    # ЧАТ-ДРОПЫ
    elif call.data.startswith('claim_drop_'):
        drop_id = call.data.replace('claim_', '')
        drop = active_drops.get(drop_id)
        if not drop or drop.get('claimed'):
            bot.answer_callback_query(call.id, "❌ Этот подарок уже кто-то забрал!", show_alert=True)
            return

        drop['claimed'] = True
        reward = drop['reward']
        add_coins(user_id, user_name, reward)
        add_account_exp(user_id, user_name, 15)

        bot.answer_callback_query(call.id, f"🎉 Вы забрали +{reward} 🪙!")
        u_link = make_link(chat_id, user_name, user_id, ping=True)
        bot.edit_message_text(
            f"🎁 <b>ПОДАРОК ЗАБРАН!</b>\n\nБыстрее всех оказался(лась) {u_link} и забрал(а) <b>+{reward} Ня-коинов 🪙</b>!",
            chat_id=chat_id,
            message_id=call.message.message_id,
            parse_mode='HTML'
        )

    # ТРЕНИРОВКА ОПЫТА
    elif call.data == 'train_exp_btn':
        success, text_resp = train_work_exp(user_id, user_name)
        bot.answer_callback_query(call.id, text_resp.replace('<b>', '').replace('</b>', ''), show_alert=True)
        if success:
            econ = get_user_econ(user_id, user_name)
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
                markup.add(InlineKeyboardButton(btn_text, callback_data=f"do_job_{job_id}"))

            markup.add(InlineKeyboardButton("🎓 Пройти тренировку (+EXP)", callback_data="train_exp_btn"))
            try:
                bot.edit_message_text(
                    "\n".join(lines),
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    reply_markup=markup,
                    parse_mode='HTML'
                )
            except Exception:
                pass

    # РАБОТА
    elif call.data.startswith('do_job_'):
        job_id = call.data.replace('do_job_', '')
        if job_id in JOBS:
            job = JOBS[job_id]
            econ = get_user_econ(user_id, user_name)
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
                add_account_exp(user_id, user_name, job['exp_gain'])
                check_achievements(user_id, user_name, 'work_shifts', 1, chat_id)
                save_data()
                bot.answer_callback_query(call.id, f"✅ Зарплата: +{pay} 🪙 (+{job['exp_gain']} EXP)!", show_alert=True)
                bot.send_message(chat_id, f"💼 {make_link(chat_id, user_name, user_id, ping=True)} заработал(а) <b>+{pay} 🪙</b> на должности <b>{job['name']}</b>!", parse_mode='HTML')
            else:
                econ['work_exp'] = econ.get('work_exp', 0) + 2
                add_account_exp(user_id, user_name, 2)
                save_data()
                bot.answer_callback_query(call.id, "❌ Вы ошиблись на смене! Получено +2 EXP.", show_alert=True)

    # ПОКУПКА БИЗНЕСА И СБОР
    elif call.data.startswith('buy_biz_'):
        b_id = call.data.replace('buy_biz_', '')
        if b_id in BUSINESSES:
            b_info = BUSINESSES[b_id]
            econ = get_user_econ(user_id, user_name)
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
            check_achievements(user_id, user_name, 'biz_bought', 1, chat_id)
            save_data()
            bot.answer_callback_query(call.id, f"🎉 Вы приобрели {b_info['name']}!", show_alert=True)
            bot.send_message(chat_id, f"🏢 {make_link(chat_id, user_name, user_id, ping=True)} приобрел(а) бизнес — <b>{b_info['name']}</b>!", parse_mode='HTML')

    elif call.data == 'collect_biz_profit':
        econ = get_user_econ(user_id, user_name)
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
        if in_rest:
            total_profit += int(base_profit * 0.20)

        econ['balance'] += total_profit
        econ['last_biz_collect'] = now
        save_data()
        bot.answer_callback_query(call.id, f"💰 Собрано: +{total_profit} 🪙!", show_alert=True)

    # БРАКИ
    elif call.data.startswith('m_yes_') or call.data.startswith('m_no_'):
        prop_id = call.data[6:]
        prop = pending_marriages.get(prop_id)
        if not prop:
            bot.answer_callback_query(call.id, "❌ Предложение устарело!", show_alert=True)
            return
        if user_id != prop['to_id'] and prop['to_id'] is not None:
            bot.answer_callback_query(call.id, "❌ Это предложение адресовано не вам!", show_alert=True)
            return

        from_econ = get_user_econ(prop['from_id'], prop['from_tag'])
        to_econ = get_user_econ(user_id, user_name)

        if call.data.startswith('m_yes_'):
            m_time = time.time()
            from_econ['marriage'] = {
                'partner_id': user_id,
                'partner_name': user_name,
                'ring': prop['ring'],
                'married_at': m_time,
                'vault': 0
            }
            to_econ['marriage'] = {
                'partner_id': prop['from_id'],
                'partner_name': prop['from_tag'],
                'ring': prop['ring'],
                'married_at': m_time,
                'vault': 0
            }
            check_achievements(prop['from_id'], prop['from_tag'], 'marriages', 1, chat_id)
            check_achievements(user_id, user_name, 'marriages', 1, chat_id)
            save_data()
            ring_emoji = RINGS.get(prop['ring'], {}).get('emoji', '💍')
            bot.edit_message_text(
                f"💒 <b>Горько! Свадьба состоялась!</b> 🎉\n\n"
                f"{ring_emoji} {make_link(chat_id, prop['from_tag'], prop['from_id'], ping=True)} и "
                f"{make_link(chat_id, user_name, user_id, ping=True)} теперь законные супруги! ❤️",
                chat_id=chat_id,
                message_id=call.message.message_id,
                parse_mode='HTML'
            )
        else:
            bot.edit_message_text(
                f"💔 {make_link(chat_id, user_name, user_id, ping=False)} отклонил(а) предложение руки и сердца.",
                chat_id=chat_id,
                message_id=call.message.message_id,
                parse_mode='HTML'
            )
        del pending_marriages[prop_id]

    # БЛЭКДЖЕК
    elif call.data.startswith('bj_hit_') or call.data.startswith('bj_stand_'):
        game_id = call.data.split('_', 2)[2]
        game = active_bj_games.get(game_id)
        if not game or game.get('finished'):
            bot.answer_callback_query(call.id, "❌ Игра окончена!", show_alert=True)
            return
        if user_id != game['user_id']:
            bot.answer_callback_query(call.id, "❌ Это не ваша игра!", show_alert=True)
            return

        if call.data.startswith('bj_hit_'):
            game['p_cards'].append(game['deck'].pop())
            p_score = calculate_bj_score(game['p_cards'])
            if p_score > 21:
                game['finished'] = True
                bot.edit_message_text(
                    f"💥 <b>Перебор ({p_score})!</b> Вы проиграли <b>{game['bet']} 🪙</b>.\nВаши карты: {game['p_cards']}",
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    parse_mode='HTML'
                )
                del active_bj_games[game_id]
                return
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("🃏 Взять карту", callback_data=f"bj_hit_{game_id}"),
                InlineKeyboardButton("✋ Хватит", callback_data=f"bj_stand_{game_id}")
            )
            bot.edit_message_text(
                f"🃏 Ваши карты: {game['p_cards']} (Сумма: <b>{p_score}</b>)\nДилер: [{game['d_cards'][0]}, ❓]",
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=markup,
                parse_mode='HTML'
            )
        else:
            game['finished'] = True
            p_score = calculate_bj_score(game['p_cards'])
            while calculate_bj_score(game['d_cards']) < 17:
                game['d_cards'].append(game['deck'].pop())
            d_score = calculate_bj_score(game['d_cards'])

            if d_score > 21 or p_score > d_score:
                win = game['bet'] * 2
                add_coins(user_id, user_name, win)
                add_account_exp(user_id, user_name, 10)
                res = f"🎉 <b>Вы выиграли +{win} 🪙!</b>"
            elif p_score == d_score:
                add_coins(user_id, user_name, game['bet'])
                res = f"🤝 <b>Ничья!</b> Ставка {game['bet']} 🪙 возвращена."
            else:
                res = f"💸 <b>Дилер выиграл!</b> Проигрыш {game['bet']} 🪙."

            bot.edit_message_text(
                f"{res}\n\n👤 Ваши карты: {game['p_cards']} ({p_score})\n🤖 Карты дилера: {game['d_cards']} ({d_score})",
                chat_id=chat_id,
                message_id=call.message.message_id,
                parse_mode='HTML'
            )
            del active_bj_games[game_id]

    # РПС (ЦУЕФА)
    elif call.data.startswith('rps_'):
        m_rps = re.match(r"^rps_([rsp])_(rps_\d+_\d+_\d+)$", call.data)
        if not m_rps:
            bot.answer_callback_query(call.id, "❌ Ошибка данных дуэли!", show_alert=True)
            return

        choice = m_rps.group(1)
        game_id = m_rps.group(2)
        game = active_rps_games.get(game_id)
        if not game:
            bot.answer_callback_query(call.id, "❌ Игра устарела!", show_alert=True)
            return

        if user_id == game['p1_id']:
            game['p1_choice'] = choice
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

            if c1 == c2:
                res = "🤝 <b>Ничья!</b> Коины возвращены игрокам."
            elif (c1 == 'r' and c2 == 's') or (c1 == 's' and c2 == 'p') or (c1 == 'p' and c2 == 'r'):
                add_coins(game['p1_id'], game['p1_tag'], bet * 2)
                res = f"🏆 Победил(а) {make_link(chat_id, game['p1_tag'], game['p1_id'], ping=True)}! (+{bet*2} 🪙)"
            else:
                add_coins(game['p2_id'], game['p2_tag'], bet * 2)
                res = f"🏆 Победил(а) {make_link(chat_id, game['p2_tag'], game['p2_id'], ping=True)}! (+{bet*2} 🪙)"

            bot.edit_message_text(
                f"✌️ <b>ИТОГИ ДУЭЛИ ЦУ-Е-ФА:</b>\n"
                f"──────────────────────\n"
                f"• {game['p1_tag']}: {c_map[c1]}\n• {game['p2_tag']}: {c_map[c2]}\n\n{res}",
                chat_id=chat_id,
                message_id=call.message.message_id,
                parse_mode='HTML'
            )
            del active_rps_games[game_id]

    # НАСТРОЙКИ (КНОПКИ)
    elif call.data == 'set_max_days':
        if not is_admin(chat_id, user_id):
            bot.answer_callback_query(call.id, "❌ Только для админов!", show_alert=True)
            return
        sett = get_chat_settings(chat_id)
        opts = [14, 30, 60]
        next_opt = opts[(opts.index(sett['max_days']) + 1) % len(opts)]
        sett['max_days'] = next_opt
        save_data()
        bot.answer_callback_query(call.id, f'✅ Лимит изменен на {next_opt} дней!')
        render_settings_view(chat_id, call.message.message_id)

    elif call.data == 'toggle_del_msg':
        if not is_admin(chat_id, user_id):
            bot.answer_callback_query(call.id, "❌ Только для админов!", show_alert=True)
            return
        sett = get_chat_settings(chat_id)
        sett['delete_rest_msg'] = not sett['delete_rest_msg']
        save_data()
        bot.answer_callback_query(call.id, f"✅ Авто-удаление: {'Включено' if sett['delete_rest_msg'] else 'Выключено'}")
        render_settings_view(chat_id, call.message.message_id)

    elif call.data == 'toggle_summer_music':
        if not is_admin(chat_id, user_id):
            bot.answer_callback_query(call.id, "❌ Только для админов!", show_alert=True)
            return
        sett = get_chat_settings(chat_id)
        sett['summer_music'] = not sett.get('summer_music', True)
        save_data()
        bot.answer_callback_query(call.id, f"✅ Музыка лета: {'Включена' if sett['summer_music'] else 'Выключена'}")
        render_settings_view(chat_id, call.message.message_id)

    elif call.data == 'set_remind_time':
        if not is_admin(chat_id, user_id):
            bot.answer_callback_query(call.id, "❌ Только для админов!", show_alert=True)
            return
        sett = get_chat_settings(chat_id)
        opts = [10, 60, 1440]
        next_opt = opts[(opts.index(sett.get('remind_minutes', 60)) + 1) % len(opts)]
        sett['remind_minutes'] = next_opt
        save_data()
        bot.answer_callback_query(call.id, f'✅ Напоминание установлено за {next_opt} мин!')
        render_settings_view(chat_id, call.message.message_id)

    # МАГАЗИН КАТАЛОГИ
    elif call.data == 'shop_main':
        send_shop_menu(chat_id, user_id, user_name, call.message.message_id)

    elif call.data == 'shop_cat_garage':
        render_garage_view(chat_id, user_id, user_name, call.message.message_id)

    elif call.data == 'shop_cat_titles':
        lines = [
            "👑 <b>КАТАЛОГ ТИТУЛОВ С ПАССИВНЫМИ БАФФАМИ</b>",
            "──────────────────────",
            "<i>Каждый титул дает постоянный бонус к удаче, опыту или доходу!</i>\n"
        ]
        for t_k, t_v in TITLES.items():
            lines.append(f"• <b>{t_v['text']}</b> — <code>{t_v['price']} 🪙</code> ({t_v['desc']})")
        lines.append("\n🌟 <b>Сертификат на Кастомный титул</b> — <code>15,000 🪙</code>")
        lines.append("──────────────────────")

        markup = InlineKeyboardMarkup(row_width=2)
        btns = [InlineKeyboardButton(f"{t_info['text']} • {t_info['price']} 🪙", callback_data=f"buy_title_{t_key}") for t_key, t_info in TITLES.items()]
        markup.add(*btns)
        markup.add(InlineKeyboardButton('🌟 Сертификат Своего Титула (15к 🪙)', callback_data='buy_cert_custom_title'))
        markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data='shop_main'))
        bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'shop_cat_badges':
        lines = [
            "✨ <b>КАТАЛОГ ЗНАЧКОВ ДЛЯ ПРОФИЛЯ</b>",
            "──────────────────────",
            "<i>Значок отображается рядом с вашим ником в чате и профиле!</i>\n"
        ]
        for b_k, b_v in BADGES.items():
            lines.append(f"• {b_v['emoji']} <b>{b_v['name']}</b> — <code>{b_v['price']} 🪙</code>")
        lines.append("──────────────────────")

        markup = InlineKeyboardMarkup(row_width=3)
        btns = [InlineKeyboardButton(f"{b_info['emoji']} {b_info['price']} 🪙", callback_data=f"buy_badge_{b_key}") for b_key, b_info in BADGES.items()]
        markup.add(*btns)
        markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data='shop_main'))
        bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'shop_cat_rings':
        lines = [
            "💍 <b>КАТАЛОГ ОБРУЧАЛЬНЫХ КОЛЕЦ</b>",
            "──────────────────────",
            "<i>Купленное кольцо можно преподнести при предложении руки и сердца!</i>\n"
        ]
        for r_k, r_v in RINGS.items():
            lines.append(f"• {r_v['emoji']} <b>{r_v['name']}</b> — <code>{r_v['price']} 🪙</code>")
        lines.append("──────────────────────")

        markup = InlineKeyboardMarkup(row_width=2)
        btns = [InlineKeyboardButton(f"{r_info['emoji']} {r_info['name']} • {r_info['price']} 🪙", callback_data=f"buy_ring_{r_id}") for r_id, r_info in RINGS.items()]
        markup.add(*btns)
        markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data='shop_main'))
        bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'shop_cat_pets':
        lines = [
            "🐾 <b>ЗОМАГАЗИН: ПИТОМЦЫ 2.0</b>",
            "──────────────────────",
            "<i>Питомцы помогают в охоте, рыбалке, приносят сокровища на прогулках и дают бонусы!</i>\n"
        ]
        for p_k, p_v in PETS_DATA.items():
            lines.append(f"• <b>{p_v['name']}</b> — <code>{p_v['price']} 🪙</code> ({p_v['desc']})")
        lines.append("──────────────────────")

        markup = InlineKeyboardMarkup(row_width=2)
        btns = [InlineKeyboardButton(f"{p['short']} — {p['price']} 🪙", callback_data=f"buy_pet_{p_id}") for p_id, p in PETS_DATA.items()]
        markup.add(*btns)
        markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data='shop_main'))
        bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'buy_cert_custom_title':
        econ = get_user_econ(user_id, user_name)
        if econ.get('has_custom_title_cert', False):
            bot.answer_callback_query(call.id, '❌ Сертификат уже куплен! Введите /custom_title', show_alert=True)
            return
        if econ['balance'] < CUSTOM_TITLE_CERT_PRICE:
            bot.answer_callback_query(call.id, f'❌ Нужно {CUSTOM_TITLE_CERT_PRICE} 🪙!', show_alert=True)
            return
        econ['balance'] -= CUSTOM_TITLE_CERT_PRICE
        econ['has_custom_title_cert'] = True
        save_data()
        bot.answer_callback_query(call.id, '🎉 Сертификат приобретен! Установите титул: /custom_title Ваш Титул', show_alert=True)

    elif call.data.startswith('buy_ring_'):
        r_id = call.data.replace('buy_ring_', '')
        if r_id in RINGS:
            r_info = RINGS[r_id]
            econ = get_user_econ(user_id, user_name)
            if econ['balance'] < r_info['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {r_info['price']} 🪙!", show_alert=True)
                return
            econ['balance'] -= r_info['price']
            econ.setdefault('rings', []).append(r_id)
            save_data()
            bot.answer_callback_query(call.id, f"🎉 Вы приобрели {r_info['name']}!", show_alert=True)

    elif call.data.startswith('buy_title_'):
        title_key = call.data.replace('buy_title_', '')
        if title_key in TITLES:
            item = TITLES[title_key]
            econ = get_user_econ(user_id, user_name)
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
            save_data()
            bot.answer_callback_query(call.id, f"🎉 Куплен титул {item['text']}!", show_alert=True)
            send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id)

    elif call.data.startswith('buy_badge_'):
        badge_key = call.data.replace('buy_badge_', '')
        if badge_key in BADGES:
            item = BADGES[badge_key]
            econ = get_user_econ(user_id, user_name)
            if item['emoji'] in econ.get('inventory', []):
                bot.answer_callback_query(call.id, f"Значок {item['emoji']} уже есть!", show_alert=True)
                return
            if econ['balance'] < item['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {item['price']} 🪙!", show_alert=True)
                return
            econ['balance'] -= item['price']
            econ.setdefault('inventory', []).append(item['emoji'])
            econ['badge'] = item['emoji']
            save_data()
            bot.answer_callback_query(call.id, f"🎉 Куплен значок {item['emoji']}!", show_alert=True)

    elif call.data.startswith('buy_pet_'):
        pet_id = call.data.replace('buy_pet_', '')
        if pet_id in PETS_DATA:
            p_data = PETS_DATA[pet_id]
            econ = get_user_econ(user_id, user_name)
            if econ['balance'] < p_data['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {p_data['price']} 🪙!", show_alert=True)
                return
            econ['balance'] -= p_data['price']
            econ['pet'] = {
                'id': pet_id,
                'name': p_data['name'],
                'luck_bonus': p_data['luck_bonus'],
                'hunger': 100,
                'cleanliness': 100,
                'pet_exp': 0,
                'last_update': time.time()
            }
            save_data()
            bot.answer_callback_query(call.id, f"🎉 Вы завели питомца {p_data['name']}!", show_alert=True)
            render_pet_view(chat_id, user_id, user_name, call.message.message_id)

    # УПРАВЛЕНИЕ ПРОФИЛЕМ (ТИТУЛЫ И ЗНАЧКИ)
    elif call.data.startswith('set_title_'):
        title_key = call.data.replace('set_title_', '')
        econ = get_user_econ(user_id, user_name)
        if title_key in econ.get('titles', []) and title_key in TITLES:
            econ['active_title'] = title_key
            econ['custom_title'] = None
            save_data()
            bot.answer_callback_query(call.id, f"✅ Надет титул {TITLES[title_key]['text']}!", show_alert=True)
            send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id)

    elif call.data == 'remove_title':
        econ = get_user_econ(user_id, user_name)
        econ['active_title'] = None
        econ['custom_title'] = None
        save_data()
        bot.answer_callback_query(call.id, '❌ Титул снят!', show_alert=True)
        send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id)

    elif call.data.startswith('set_badge_'):
        selected_emoji = call.data.replace('set_badge_', '')
        econ = get_user_econ(user_id, user_name)
        if selected_emoji in econ.get('inventory', []):
            econ['badge'] = selected_emoji
            save_data()
            bot.answer_callback_query(call.id, f"✅ Надет значок {selected_emoji}!", show_alert=True)
            send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id)

    elif call.data == 'remove_badge':
        econ = get_user_econ(user_id, user_name)
        econ['badge'] = None
        save_data()
        bot.answer_callback_query(call.id, "❌ Значок снят!", show_alert=True)
        send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id)


# ---------------------------------------------------------
# СТАРТ И ИНИЦИАЛИЗАЦИЯ
# ---------------------------------------------------------
setup_bot_commands()
restore_timers()
start_background_threads()
keep_alive()

print('Бот успешно запущен и подключен ко всем каналам!')
bot.infinity_polling()
