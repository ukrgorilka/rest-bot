import csv
from datetime import datetime, timedelta
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
# ВЕБ-СЕРВЕР ДЛЯ KEEP-ALIVE (RENDER / REPLIT)
# ---------------------------------------------------------
app = Flask('')


@app.route('/')
def home():
    return "Bot is alive and running!"


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

# ID приватного канала для авто-бекапов базы данных
DB_CHANNEL_ID = int(os.environ.get('DB_CHANNEL_ID', '-1004334874700'))

# Отдельный канал для логов рестов, переводов и покупок
LOG_CHANNEL_ID = int(os.environ.get('LOG_CHANNEL_ID', '-5587336891'))
DATA_FILE = 'rests_data.json'

# Юзернейм администратора/разработчика для секретного промокода
ADMIN_USERNAME = 'ukrgorilka'

# Источник гифок и аудио из Telegram (ID чата https://t.me/c/4311479842)
MEDIA_TG_CHAT_ID = int(os.environ.get('MEDIA_TG_CHAT_ID', '-1004311479842'))
WHY_TG_MSG_IDS = [5, 9]
SUMMER_SONG_MSG_ID = 14

# Резервные прямые ссылки на случай отсутствия доступа к чату
WHY_GIFS = [
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3Z2eXpzc2ExOHBmbmdvZ3F0MHlyYm1sbTVrcHFqYm42aXFlZ3VwOSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/s239QJIh56sRW/giphy.gif",
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHlsMGVnZ29rNm0xb3JvdWRyc3dybDVrNTVrdXVnMzh0eWJ5dzdpNyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/1X7AZhiL08Y72/giphy.gif"
]

MONTHS = {
    'января': 1,
    'январь': 1,
    'февраля': 2,
    'февраль': 2,
    'марта': 3,
    'март': 3,
    'апреля': 4,
    'апрель': 4,
    'мая': 5,
    'май': 5,
    'июня': 6,
    'июнь': 6,
    'июля': 7,
    'июль': 7,
    'августа': 8,
    'август': 8,
    'сентября': 9,
    'сентябрь': 9,
    'октября': 10,
    'октябрь': 10,
    'ноября': 11,
    'ноябрь': 11,
    'декабря': 12,
    'декабрь': 12,
}

# Регулярное выражение для поиска длительности/срока (с поддержкой предлога "до")
DURATION_PATTERN = (
    r'(?:\b(?:до\s+)?\d+\s*(?:дней|дня|день|д|часов|часа|час|ч|минут|мин|м)\b|'
    r'\b(?:до\s+)?\d{1,2}[\.\/]\d{1,2}(?:[\.\/]\d{2,4})?|'
    r'\b(?:до\s+)?\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря|'
    r'январь|февраль|март|апрель|май|июнь|июль|август|сентябрь|октябрь|ноябрь|декабрь)|'
    r'на\s+неопредел[её]нный\s+срок|неопредел[её]нный\s+срок|бессрочно|без\s+срока|навсегда)'
)

# ---------------------------------------------------------
# ЭКОНОМИКА: ТОВАРЫ И ЦЕНЫ
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
    'king': {'name': 'Кинг', 'text': '👑 Кинг', 'price': 3000},
    'sonya': {'name': 'Соня', 'text': '💤 Соня', 'price': 2200},
    'legend': {'name': 'Легенда', 'text': '🔥 Легенда', 'price': 3600},
    'dragon': {'name': 'Дракон', 'text': '🐉 Дракон', 'price': 4200},
    'bun': {'name': 'Булочка', 'text': '🥐 Булочка', 'price': 1800},
}

RINGS = {
    'copper': {'name': 'Медное колечко', 'emoji': '🥉', 'price': 600},
    'silver': {'name': 'Серебряное кольцо', 'emoji': '🥈', 'price': 1800},
    'gold': {'name': 'Золотое кольцо', 'emoji': '🥇', 'price': 4200},
    'diamond': {'name': 'Бриллиантовое кольцо', 'emoji': '💍', 'price': 9600},
    'cosmic': {'name': 'Космическое кольцо Любви', 'emoji': '🌌', 'price': 24000},
}

BUSINESSES = {
    'coffee': {'name': '☕️ Уютная Кофейня', 'price': 2400, 'income_per_hour': 35},
    'bakery': {'name': '🥐 Пекарня Булочек', 'price': 6000, 'income_per_hour': 90},
    'crypto_farm': {'name': '💻 Крипто-Ферма', 'price': 18000, 'income_per_hour': 280},
    'club': {'name': '🏰 Ночной Клуб', 'price': 54000, 'income_per_hour': 850},
}

CUSTOM_TITLE_CERT_PRICE = 15000

# ---------------------------------------------------------
# СИСТЕМА КРИПТО-БИРЖИ И АКЦИЙ
# ---------------------------------------------------------
MARKET_DEFAULT = {
    'NYA': {
        'name': '🐾 Ня-Биткоин (NYA)',
        'price': 120.0,
        'old_price': 110.0,
        'volatility': 0.18,
        'min_price': 15.0,
        'max_price': 2500.0,
        'last_update': 0
    },
    'MEOW': {
        'name': '🐱 Мяу-Эфириум (MEOW)',
        'price': 45.0,
        'old_price': 42.0,
        'volatility': 0.22,
        'min_price': 5.0,
        'max_price': 900.0,
        'last_update': 0
    },
    'ANM': {
        'name': '🌸 Аниме-Акции (ANM)',
        'price': 15.0,
        'old_price': 14.0,
        'volatility': 0.28,
        'min_price': 1.0,
        'max_price': 400.0,
        'last_update': 0
    },
    'PAT': {
        'name': '🦶 Пятка-Коин (PAT)',
        'price': 5.0,
        'old_price': 6.0,
        'volatility': 0.35,
        'min_price': 0.5,
        'max_price': 150.0,
        'last_update': 0
    }
}

# ---------------------------------------------------------
# СИСТЕМА ПРОФЕССИЙ И ВАКАНСИЙ
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
# БЛОК РЫБАЛКИ, ОХОТЫ И ПИТОМЦЕВ
# ---------------------------------------------------------
FISH_TYPES = [
    ('🐟 Карась', 'Обычный', 12, 45),
    ('🐠 Окунь', 'Обычный', 20, 30),
    ('🐡 Щука', 'Редкий', 50, 15),
    ('🦀 Краб', 'Редкий', 75, 8),
    ('🐙 Осьминог', 'Эпический', 160, 3),
    ('🧜‍♀️ Русалка', 'Легендарный', 380, 2),
    ('🐉 Небесный Драконорыб', 'Мифический', 850, 1),
]

HUNT_TYPES = [
    ('🐇 Заяц', 'Обычный', 15, 45),
    ('🦊 Лиса', 'Обычный', 28, 30),
    ('🐗 Кабан', 'Редкий', 65, 15),
    ('🦌 Олень', 'Редкий', 95, 8),
    ('🐅 Снежный Барс', 'Эпический', 210, 3),
    ('🦅 Феникс', 'Легендарный', 420, 2),
    ('🦄 Звездный Грифон', 'Мифический', 1000, 1),
]

PETS_DATA = {
    'cat': {'name': '🐱 Котик Усач', 'price': 720, 'luck_bonus': 15, 'desc': '+15% к удаче в охоте и рыбалке'},
    'dog': {'name': '🐶 Пёсель Верный', 'price': 1450, 'luck_bonus': 25, 'desc': '+25% к удаче в охоте и рыбалке'},
    'fox': {'name': '🦊 Хитрая Лисичка', 'price': 3000, 'luck_bonus': 40, 'desc': '+40% к удаче в охоте и рыбалке'},
    'owl': {'name': '🦉 Мудрая Сова', 'price': 4800, 'luck_bonus': 60, 'desc': '+60% к удаче в охоте и рыбалке'},
    'dragon': {'name': '🐉 Маленький Дракон', 'price': 9600, 'luck_bonus': 85, 'desc': '+85% к удаче в охоте и рыбалке'}
}

# ---------------------------------------------------------
# БЛОК ДОСТИЖЕНИЙ (АЧИВОК)
# ---------------------------------------------------------
ACHIEVEMENTS = {
    'first_msg': {'title': '🌱 Первый шаг', 'desc': 'Отправить первое сообщение в чате', 'stat': 'messages', 'target': 1, 'reward': 50},
    'msg_100': {'title': '💬 Душа чата', 'desc': 'Написать 100 сообщений', 'stat': 'messages', 'target': 100, 'reward': 250},
    'msg_1000': {'title': '🗣 Легенда общения', 'desc': 'Написать 1000 сообщений', 'stat': 'messages', 'target': 1000, 'reward': 1200},
    'first_rp': {'title': '🎭 Актерское мастерство', 'desc': 'Использовать первое РП-действие', 'stat': 'rp_actions', 'target': 1, 'reward': 50},
    'rp_50': {'title': '💖 Центр внимания', 'desc': 'Использовать 50 РП-действий', 'stat': 'rp_actions', 'target': 50, 'reward': 500},
    'first_trade': {'title': '📊 Начинающий инвестор', 'desc': 'Совершить первую сделку на бирже', 'stat': 'crypto_trades', 'target': 1, 'reward': 80},
    'crypto_master': {'title': '🐺 Волк с Ня-Стрит', 'desc': 'Совершить 20 сделок на бирже', 'stat': 'crypto_trades', 'target': 20, 'reward': 800},
    'first_marriage': {'title': '💍 Счастливы вместе', 'desc': 'Вступить в законный брак', 'stat': 'marriages', 'target': 1, 'reward': 250},
    'first_biz': {'title': '🏢 Первое предприятие', 'desc': 'Приобрести свой первый бизнес', 'stat': 'biz_bought', 'target': 1, 'reward': 300},
    'first_bonus': {'title': '🎁 Первые коины', 'desc': 'Собрать свой первый часовой бонус', 'stat': 'bonuses', 'target': 1, 'reward': 40},
    'bonus_50': {'title': '💎 Бонусный коллекционер', 'desc': 'Собрать 50 часовых бонусов', 'stat': 'bonuses', 'target': 50, 'reward': 800},
    'first_fish': {'title': '🎣 Начинающий рыбак', 'desc': 'Поймать свою первую рыбу', 'stat': 'fish', 'target': 1, 'reward': 80},
    'fish_25': {'title': '🦈 Морской Волк', 'desc': 'Поймать 25 рыб', 'stat': 'fish', 'target': 25, 'reward': 600},
    'first_hunt': {'title': '🏹 Начинающий охотник', 'desc': 'Сделать первый успешный выстрел', 'stat': 'hunt', 'target': 1, 'reward': 80},
    'hunt_25': {'title': '🐅 Царь тайги', 'desc': 'Сходить на охоту 25 раз', 'stat': 'hunt', 'target': 25, 'reward': 600},
    'first_transfer': {'title': '🤝 Щедрая душа', 'desc': 'Сделать первый перевод другу', 'stat': 'transfers', 'target': 1, 'reward': 100},
    'first_game': {'title': '🎲 Начинающий игрок', 'desc': 'Сыграть 1 раз в азартную игру', 'stat': 'games', 'target': 1, 'reward': 80},
    'gamer_50': {'title': '🎰 Мастер азарта', 'desc': 'Сыграть 50 раз в азартные игры', 'stat': 'games', 'target': 50, 'reward': 1000},
    'first_rest': {'title': '🌴 Заслуженный отдых', 'desc': 'Получить свой первый рест', 'stat': 'rests', 'target': 1, 'reward': 150},
    'rich_1000': {'title': '💰 Богач', 'desc': 'Накопить 1000 Ня-коинов на балансе', 'stat': 'balance_check', 'target': 1000, 'reward': 400}
}

DAILY_TASKS = {
    0: [('messages', 'Написать 30 сообщений', 30, 60), ('transfer', 'Перевести коины другу', 1, 30), ('bonus', 'Собрать 2 часовых бонуса', 2, 45)],
    1: [('messages', 'Написать 40 сообщений', 40, 70), ('dice', 'Сыграть в кости 3 раза', 3, 50), ('fish', 'Поймать 1 рыбу', 1, 40)],
    2: [('messages', 'Написать 30 сообщений', 30, 60), ('slots', 'Испытать слоты 2 раза', 2, 45), ('iq', 'Измерить IQ', 1, 30)],
    3: [('messages', 'Написать 50 сообщений', 50, 85), ('transfer', 'Перевести коины другу', 1, 30), ('hunt', 'Сходить на охоту', 1, 45)],
    4: [('messages', 'Написать 35 сообщений', 35, 65), ('dice', 'Сыграть в кости 5 раз', 5, 75), ('fat', 'Измерить жир', 1, 30)],
    5: [('messages', 'Написать 45 сообщений', 45, 75), ('bonus', 'Собрать 3 часовых бонуса', 3, 65), ('fish', 'Поймать 2 рыбы', 2, 60)],
    6: [('messages', 'Написать 60 сообщений', 60, 100), ('roulette', 'Сыграть в рулетку 2 раза', 2, 60), ('hunt', 'Сходить на охоту 2 раза', 2, 75)],
}

WEEKLY_TASKS = [
    ('messages', 'Написать 250 сообщений за неделю', 250, 220),
    ('fish', 'Поймать 10 рыб за неделю', 10, 180),
    ('hunt', 'Сходить на охоту 10 раз за неделю', 10, 180),
    ('bonus', 'Собрать 15 часовых бонусов', 15, 280),
    ('dice', 'Сыграть в кости 20 раз', 20, 240),
]

# --- РП-КОМАНДЫ (Roleplay действия) ---
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

# --- ВСЕГДА АКТИВНЫЕ ТРИГГЕРЫ ---
ALWAYS_ACTIVE_PATTERNS = {
    r'\b(твоя\s+мамка|твоя\s+мама|твою\s+маму|твоя\s+мать|мамулька|маман)\b': [
        'Твоя мама самая лучшая и прекрасная! 🌸💖',
        'Мама — это святое! Давай только с любовью и уважением ✨🥰',
        'Твоя мама чудесный человек! 💐',
        'Мамочке привет и самого доброго дня! 🥞☕️',
        'Передай маме, что она замечательная! 🥐🌷',
        'Мама — главный человек в жизни, береги её! ❤️',
        'Желаем твоей мамочке крепкого здоровья! 🌿',
        'О маме только с теплом и улыбкой! ☀️',
        'Мамуле отправляем самые теплые обнимашки! 🧸',
        'Пусть у мамы все будет просто отлично! 🌟'
    ],
    r'\b(охае|охаё|охайо|охаешечки|охаёшечки|охайоо|охаее)\b': [
        'Охаё! Анимешники в чате! 🎌🌸',
        'Охаёшечки! Доброго утречка/днечка! ☀️🍵',
        'Охаё! А кофе/чай уже заварен? ☕️✨',
        'Охаё-о-о! Свеж и готов к работе? 🥪😊',
        'Охаё! Не забудь позавтракать! 🥞🥐',
        'Охаё! Пусть день пройдет кавайно! 🌸',
        'Доброго утречка, нанамания! 🎏',
        'Охаё! Бодрости на весь день! ⚡️',
        'С добрым утром! Готов к новым свершениям? 🚀',
        'Охаё! Улыбнись новому дню! 😄'
    ],
    r'\b(семпай|сенпай|семпайчик|сенпайчик|senpai|sempai)\b': [
        'Семпай заметил тебя! 👉👈🌸',
        'Ох, семпай... Ты такой внимательный! 🥺✨',
        'Семпай, не забудь сделать перерыв и попить чаю! 🍵🥐',
        'Ничего себе! Настоящий семпай в чате! 👑🎌',
        'Семпай всегда прав, десу! 🥰🐾',
        'Семпай, научи меня так же! 🎓',
        'Семпай пришел — порядок навел! 🧹',
        'Все смотрят только на семпая! 👀✨',
        'Семпай сегодня неотразим! 💖',
        'Вау, сам семпай обратил на нас внимание! 🌟'
    ],
    r'\b(даттебайо|даттебае|даттебаё)\b': [
        'Наруто, ты ли это?! 🍥🦊',
        'Даттебаё! Мой путь ниндзя — следить за рестами! 🥷✨',
        'Стану Хокаге этого чата, даттебаё! 🍃👑',
        'Расенган в твою ленту! 🌀💥',
        'Главное — никогда не сдаваться, даттебаё! 🔥💪',
        'Теневое клонирование активировано! 👥',
        'Курама передает привет, даттебаё! 🦊',
        'Ниндзя никогда не отступает от своего слова! 📜',
        'Пора кушать рамен у Ираку! 🍜',
        'Даттебаё! Сила молодости зашкаливает! 💥'
    ],
    r'\b(кавай|кавайный|кавайность|кавайка)\b': [
        'Кавайность этого сообщения зашкаливает! 🥺✨',
        'Милота спасает этот чат! 🌸ฅ^•ﻌ•^ฅ',
        'Ну прямо милота 100/10! 🐱💖',
        'Осторожно, повышенный уровень кавая! ⚠️🎀',
        'Спасибо, ты тоже очень кавайный! 🥰🐾',
        'Уровень милоты пробил потолок! 📈',
        'Зашкаливающий кавай обнаружен! 🚨',
        'Этот чат стал еще милее! 🎀',
        'Милота 1000%! 🌸',
        'Кавайность зашкаливает, держите меня! 🥺'
    ],
    r'\b(ня|няшка|някать|нян)\b': [
        'Ня! 🐱🐾',
        'Котодевочки одобряют этот чат! 🐾✨',
        'Ня-ня-ня, всем позитивного дня! 🥐☕️',
        'Кто-то сказал «ня»? Пора гладить котиков! 🐈',
        'Някать разрешено, но рест по расписанию! 🌴😉',
        'Ня! Мурчательного настроения! 🐱',
        'Всем по пушистому котику! 🐾',
        'Ня-ня! Кошачий лапки с вами! 🐾',
        'Нянькаемся и радуемся жизни! 🌸',
        'Лапки вверх! Ня! 🙌🐱'
    ],
    r'\b(аригато|аригатоо|аригато gozaimasu)\b': [
        'Доитасимасите! (Всегда пожалуйста!) 🙇‍♂️✨',
        'Не за что, обращайся! 🤝🌸',
        'Всегда рад помочь! 🤖❤️',
        'Аригато и тебе за хорошее настроение! 🌟',
        'Пожалуйста! Нарушать правила все равно нельзя 🤓☝️',
        'Пожалуйста, дорогой участник! 💖',
        'Всегда к вашим услугам! 🎩',
        'Аригато! Ты супер! 🌟',
        'Обращайся в любое время! ⏰',
        'Всегда пожалуйста! ✨'
    ],
    r'\b(ямете|ямете кудасай|яметее)\b': [
        'ЯМЕТЕ КУДАСАЙ!! 😱💥',
        'А вот тут остановись, а то бан прилетит! 🛑🙈',
        'Ой-ой-ой, что тут происходит?! 😳🍿',
        'Крик души услышан! 📢🤯',
        'Спокойствие! Всё под контролем! 🧘‍♂️',
        'Ямете! Не надо так громко! 🙉',
        'Остановитесь, пожалейте ушки! 👂💦',
        'Тише-тише, ямете кудасай! 🤫',
        'Слишком много эмоций! 💥',
        'Ямете! Перерыв на чай! 🍵'
    ],
    r'\b(десу|десс)\b': [
        'Да, именно так, десу! 🤓✨',
        'Дез-дез-дез! 🌸',
        'Утверждение принято, десу! 📜✍️',
        'И добавить нечего, десу! 😼',
        'Самый правильный ответ, десу! 💯',
        'Истинно так, десу! 🌟',
        'Подтверждаю на все 100%, десу! 👌',
        'Так точно, десу! 🫡',
        'Без сомнений, десу! 🌸',
        'Абсолютно верно, десу! 😼'
    ]
}

pending_requests = {}
pending_marriages = {}
active_bj_games = {}
active_rps_games = {}
req_counter = 0

# ---------------------------------------------------------
# БЛОК РАБОТЫ С ДАННЫМИ (JSON + TELEGRAM BACKUP)
# ---------------------------------------------------------
def load_data():
    data = {
        'rests': {},
        'history': {},
        'settings': {},
        'economy': {},
        'promos': {},
        'market': {},
        'marriages': {}
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
                for key in ['settings', 'rests', 'history', 'economy', 'promos', 'market', 'marriages']:
                    if key not in data:
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
        BotCommand('profile', '👤 Ваш профиль, статистика и портфель'),
        BotCommand('business', '🏢 Бизнесы и пассивный доход'),
        BotCommand('family', '💍 Информация о браке и семье'),
        BotCommand('market', '📈 Крипто-биржа и котировки'),
        BotCommand('work', '💼 Работа и вакансии'),
        BotCommand('train', '🎓 Получить опыт работы'),
        BotCommand('pet', '🐾 Ваш питомец и уход'),
        BotCommand('feed', '🍖 Покормить питомца'),
        BotCommand('wash', '🧼 Помыть питомца'),
        BotCommand('sell', '💰 Продать улов и трофеи'),
        BotCommand('achievements', '🏆 Ваши достижения и награды'),
        BotCommand('balance', '💵 Проверить баланс коинов'),
        BotCommand('bonus', '🎁 Ежечасовой бонус коинов'),
        BotCommand('shop', '🏪 Магазин (значки, кольца, питомцы)'),
        BotCommand('tasks', '📋 Ежедневные и недельные задания'),
        BotCommand('bj', '🃏 Сыграть в Блэкджек (21)'),
        BotCommand('fish', '🎣 Пойти на рыбалку'),
        BotCommand('hunt', '🏹 Пойти на охоту'),
        BotCommand('dice', '🎲 Сыграть в кости'),
        BotCommand('slots', '🎰 Сыграть в слоты'),
        BotCommand('iq', '🧠 Измерить уровень IQ'),
        BotCommand('fat', '🥩 Измерить процент жира'),
        BotCommand('foot', '🦶 Измерить размер пятки'),
        BotCommand('top', '🏆 Топ богачей, IQ и других параметров'),
        BotCommand('settings', '⚙️ Настройки бота (для админов)'),
        BotCommand('help', 'ℹ️ Полная справка по всем командам')
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


# --- ОБНОВЛЕНИЕ РЫНКА (БИРЖИ) ---
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
            new_p = round(max(info.get('min_price', 1.0), min(info.get('max_price', 1000.0), old_p * (1 + pct))), 2)
            info['old_price'] = old_p
            info['price'] = new_p
            info['last_update'] = now
            changed = True

    if changed:
        save_data(send_backup=False)

    return market


# --- ОБЩАЯ ГЛОБАЛЬНАЯ ЭКОНОМИКА И УРОВНИ ---
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


def update_pet_stats(pet):
    if not pet:
        return
    now = time.time()
    last_update = pet.get('last_update', now)
    hours_passed = (now - last_update) / 3600.0

    if hours_passed > 0.1:
        pet['hunger'] = max(0, pet.get('hunger', 100) - int(hours_passed * 5))
        pet['cleanliness'] = max(0, pet.get('cleanliness', 100) - int(hours_passed * 4))
        pet['last_update'] = now


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
            'account_exp': 0,
            'smeh': 0,
            'iq': 100,
            'fat': 20,
            'foot_size': 25,
            'last_hourly': 0,
            'last_iq_time': 0,
            'last_fat_time': 0,
            'last_foot_time': 0,
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
            'last_biz_collect': time.time(),
            'daily_tasks_date': '',
            'daily_progress': {},
            'daily_claimed': [],
            'weekly_tasks_yearweek': '',
            'weekly_progress': {},
            'weekly_claimed': [],
            'fish_inventory': {},
            'hunt_inventory': {},
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
        ('fat', 20), ('foot_size', 25), ('rest_rewards_count', 0), ('titles', []),
        ('active_title', None), ('custom_title', None), ('has_custom_title_cert', False),
        ('rings', []), ('active_ring', None), ('marriage', None), ('businesses', {}),
        ('last_biz_collect', time.time()), ('daily_tasks_date', ''), ('daily_progress', {}),
        ('daily_claimed', []), ('weekly_tasks_yearweek', ''), ('weekly_progress', {}),
        ('weekly_claimed', []), ('fish_inventory', {}), ('hunt_inventory', {}),
        ('crypto_portfolio', {}), ('last_fish_time', 0), ('last_hunt_time', 0),
        ('achievements', []), ('stats', {}), ('work_exp', 0),
        ('last_work_time', 0), ('last_train_time', 0), ('pet', None)
    ]:
        if field not in u_data:
            u_data[field] = default

    if 'msg_stats' not in u_data:
        u_data['msg_stats'] = {
            'day_date': '', 'day_count': 0, 'week_key': '',
            'week_count': 0, 'month_key': '', 'month_count': 0, 'total_count': 0
        }

    if u_data.get('pet'):
        update_pet_stats(u_data['pet'])

    return u_data


def add_account_exp(user_id, user_tag, exp_amount=1):
    econ = get_user_econ(user_id, user_tag)
    econ['account_exp'] = econ.get('account_exp', 0) + exp_amount
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
        bot.send_message(LOG_CHANNEL_ID, f'📌 <b>{event_type}</b>\n{message_text}', parse_mode='HTML')
    except Exception as e:
        print(f'Ошибка записи в канал логов: {e}')


# ---------------------------------------------------------
# ОБРАБОТКА И ПРОВЕРКА АЧИВОК
# ---------------------------------------------------------
def check_achievements(user_id, user_tag, stat_name, amount=1, chat_id=None):
    econ = get_user_econ(user_id, user_tag)
    stats = econ.setdefault('stats', {})
    unlocked = econ.setdefault('achievements', [])

    if stat_name == 'balance_check':
        stats['balance_check'] = econ.get('balance', 0)
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
                    f"🎉 <b>ПОЛУЧЕНО ДОСТИЖЕНИЕ!</b>\n"
                    f"👤 Игрок: {u_link}\n"
                    f"🏆 <b>{title}</b> — <i>{desc}</i>\n"
                    f"💰 Награда: <b>+{reward} Ня-коинов 🪙</b> (+50 EXP)"
                )
                try:
                    bot.send_message(chat_id, msg, parse_mode='HTML')
                except Exception as e:
                    print(f"Ошибка отправки уведомления об ачивке: {e}")


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
        f'📋 <b>Задания и Квесты — {weekdays[datetime.now().weekday()]}</b>',
        '',
        '🌟 <i>Все задания доступны каждому участнику!</i>\n',
        '☀️ <b>Ежедневные задания:</b>'
    ]
    for key, description, target, reward in tasks:
        current = min(econ.get('daily_progress', {}).get(key, 0), target)
        done = key in econ.get('daily_claimed', [])
        status = '✅' if done else '🔄'
        lines.append(f'{status} {description}: <b>{current}/{target}</b> (Награда: <b>+{reward} 🪙</b>)')

    lines.append('\n📅 <b>Еженедельные задания:</b>')
    for key, description, target, reward in w_tasks:
        current = min(econ.get('weekly_progress', {}).get(key, 0), target)
        done = key in econ.get('weekly_claimed', [])
        status = '✅' if done else '🔄'
        lines.append(f'{status} {description}: <b>{current}/{target}</b> (Награда: <b>+{reward} 🪙</b>)')

    return '\n'.join(lines)


def cooldown_text(last_time, cooldown):
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
        return f'<b>{name}</b>{badge_str}{title_str}'

    if user_id:
        return f'<a href="tg://user?id={user_id}">{name}</a>{badge_str}{title_str}'
    return f'<b>{name}</b>{badge_str}{title_str}'


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
        target_user = f"ID:{target_user_id}"
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
# ТАЙМЕРЫ И УВЕДОМЛЕНИЯ РЕСТОВ
# ---------------------------------------------------------
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
                        save_data()
                        u_link = make_link(chat_id, u_name, target_user_id, ping=True)
                        try:
                            bot.send_message(chat_id, f'⏰ Время реста для {u_link} истекло. Рест автоматически снят!', parse_mode='HTML')
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
    add_to_history(str_chat, clean_user, duration_text, reason, target_user_id)

    econ = get_user_econ(target_user_id, clean_user)
    reward_given = False
    if econ['rest_rewards_count'] < 5:
        econ['balance'] += 150
        econ['rest_rewards_count'] += 1
        reward_given = True

    check_achievements(target_user_id, clean_user, 'rests', 1, chat_id)
    save_data()
    log_event('РЕСТ', f'Чат: <code>{chat_id}</code>\nПользователь: {make_link(chat_id, clean_user, target_user_id, ping=False)}\nСрок: <b>{duration_text}</b>\nПричина: {reason}')
    if end_time:
        schedule_rest_timers(chat_id, rest_key, end_time, target_user_id)

    return reward_given, econ['rest_rewards_count']


# ---------------------------------------------------------
# ФОНОВЫЙ ЛЕТНИЙ МУЗЫКАЛЬНЫЙ ТАЙМЕР
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
            print(f"Ошибка в цикле летней музыки: {e}")
            time.sleep(60)


def start_summer_music_thread():
    t = threading.Thread(target=summer_music_worker)
    t.daemon = True
    t.start()


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
            f"🎉 <b>Добро пожаловать в чат, {user_link}!</b>\n\n"
            f"🌸 Мы очень рады тебя видеть!\n"
            f"💵 Тебе начислен приветственный бонус: <b>50 Ня-коинов</b>!\n\n"
            f"💡 Используй <code>/help</code> или <code>/start</code>, чтобы узнать все возможности бота."
        )
        bot.send_message(message.chat.id, welcome_text, parse_mode='HTML')


@bot.message_handler(content_types=['left_chat_member'])
def goodbye_left_member(message):
    member = message.left_chat_member
    user_name = (f"{member.first_name or ''} {member.last_name or ''}").strip() or member.username
    user_link = make_link(message.chat.id, user_name, member.id, ping=False)
    farewell_text = f"👋 <b>{user_link}</b> покинул(а) наш чат. Пожелаем удачи! 🌸"
    bot.send_message(message.chat.id, farewell_text, parse_mode='HTML')


# ---------------------------------------------------------
# ФУНКЦИИ УХОДА ЗА ПИТОМЦЕМ
# ---------------------------------------------------------
def feed_pet(user_id, user_tag):
    econ = get_user_econ(user_id, user_tag)
    pet = econ.get('pet')

    if not pet:
        return False, "❌ У вас нет питомца! Купите его в магазине: <code>магазин</code> или <code>/shop</code>."

    update_pet_stats(pet)

    if econ['balance'] < 20:
        return False, "❌ На еду питомцу нужно <b>20 Ня-коинов</b>!"

    if pet.get('hunger', 100) >= 100:
        return False, f"😋 <b>{pet['name']}</b> уже полностью сыт(а) (100%)!"

    econ['balance'] -= 20
    pet['hunger'] = min(100, pet.get('hunger', 100) + 40)
    save_data()
    return True, f"🍖 Вы вкусно покормили <b>{pet['name']}</b>!\nСытость: <b>{pet['hunger']}%</b> (-20 🪙)"


def wash_pet(user_id, user_tag):
    econ = get_user_econ(user_id, user_tag)
    pet = econ.get('pet')

    if not pet:
        return False, "❌ У вас нет питомца! Купите его в магазине: <code>магазин</code> или <code>/shop</code>."

    update_pet_stats(pet)

    if econ['balance'] < 15:
        return False, "❌ На шампунь нужно <b>15 Ня-коинов</b>!"

    if pet.get('cleanliness', 100) >= 100:
        return False, f"✨ <b>{pet['name']}</b> уже чист(а) как стеклышко (100%)!"

    econ['balance'] -= 15
    pet['cleanliness'] = min(100, pet.get('cleanliness', 100) + 50)
    save_data()
    return True, f"🧼 Вы искупали <b>{pet['name']}</b>!\nЧистота: <b>{pet['cleanliness']}%</b> (-15 🪙)"


# ---------------------------------------------------------
# ОБРАБОТЧИКИ КОМАНД
# ---------------------------------------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    help_text = (
        '🤖 <b>НЯ-БОТ — ПОЛНЫЙ СПИСОК ВОЗМОЖНОСТЕЙ</b>\n\n'
        '☀️🎵 <b>ЛЕТО И МУЗЫКА</b>\n'
        '• Каждый час ровно в :00 бот присылает трек и обратный отсчет до конца лета!\n\n'
        '💍 <b>БРАКИ И СЕМЬЯ</b>\n'
        '• <code>/marry @username</code> или <code>брак @username</code> — сделать предложение.\n'
        '• <code>/family</code> или <code>семья</code> — инфо о браке и сейфе.\n'
        '• <code>семейный сейф положить 100</code> / <code>семейный сейф снять 100</code>.\n'
        '• <code>/divorce</code> или <code>развод</code> — развестись и поделить сейф.\n\n'
        '🏢 <b>БИЗНЕСЫ И ПАССИВНЫЙ ДОХОД</b>\n'
        '• <code>/business</code> или <code>бизнесы</code> — покупка коммерции.\n'
        '• <code>/collect</code> или <code>собрать прибыль</code> — забрать накопленные коины.\n\n'
        '📈 <b>КРИПТО-БИРЖА И АКЦИИ</b>\n'
        '• <code>/market</code> или <code>биржа</code> — котировки и графики цен.\n'
        '• <code>купить крипту NYA 5</code> или <code>/buy_crypto NYA 5</code>.\n'
        '• <code>продать крипту NYA 5</code> или <code>/sell_crypto NYA 5</code>.\n'
        '• <code>/portfolio</code> или <code>портфель</code> — ваш инвестиционный портфель.\n\n'
        '🎭 <b>РП-ДЕЙСТВИЯ</b>\n'
        '• <code>обнять</code>, <code>поцеловать</code>, <code>погладить</code>, <code>укусить</code> (или <code>кусь</code>), '
        '<code>дать пять</code>, <code>ударить тапком</code>, <code>похвалить</code>, <code>шлепнуть</code>, '
        '<code>покормить</code>, <code>ущипнуть</code>, <code>утешить</code>, <code>чихнуть</code>.\n\n'
        '💼 <b>РАБОТА И ОПЫТ</b>\n'
        '• <code>/work</code> или <code>работа</code> — выбор профессии и смена.\n'
        '• <code>опыт</code> или <code>/train</code> — тренировка и получение опыта.\n\n'
        '🐾 <b>ПИТОМЦЫ И УХОД</b>\n'
        '• <code>/pet</code> или <code>питомец</code> — статус питомца и меню ухода.\n'
        '• <code>покормить</code>, <code>помыть</code> — уход за питомцем.\n'
        '• <code>/pet_shop</code> или <code>магазин</code> — покупка питомца.\n\n'
        '🎣 <b>РЫБАЛКА, ОХОТА И ПРОДАЖА</b>\n'
        '• <code>рыбалка</code> или <code>/fish</code> — поймать рыбу (КД 2 часа).\n'
        '• <code>охота</code> или <code>/hunt</code> — добыть трофей (КД 2 часа).\n'
        '• <code>продать</code> или <code>/sell</code> — продать улов за коины.\n\n'
        '🌴 <b>РЕСТЫ</b>\n'
        '• <code>+рест Иван Иванов до 12 августа | отпуск</code> — выдать рест.\n'
        '• <code>-рест @username</code> или <code>-рест Иван Иванов</code> — снять рест.\n'
        '• <code>ресты</code>, <code>мой рест</code>, <code>кто ты @username</code>.\n\n'
        '💰 <b>НЯ-КОИНЫ И ПРОФИЛЬ</b>\n'
        '• <code>бонус</code> или <code>/bonus</code> — раз в час коины (растут с уровнем LVL!).\n'
        '• <code>баланс</code> или <code>/balance</code> — ваш кошелек.\n'
        '• <code>профиль</code> или <code>/profile</code> — вся статистика, значки, уровень.\n'
        '• <code>/custom_title Текст</code> — установить кастомный титул.\n'
        '• <code>ачивки</code> или <code>/achievements</code> — ваши достижения.\n'
        '• <code>передать 100</code> (ответом) или <code>передать @username 100</code>.\n\n'
        '🎰 <b>АЗАРТНЫЕ ИГРЫ И ДУЭЛИ</b>\n'
        '• <code>блэкджек 100</code> (или <code>/bj 100</code>) — 21 очко с дилером.\n'
        '• <code>слоты 100</code> (или <code>/slots 100</code>) — игровой автомат.\n'
        '• <code>кости 100</code> (или <code>/dice 100</code>) — игра в кости.\n'
        '• <code>/rps 100 @username</code> — Камень-Ножницы-Бумага.\n\n'
        '🧠 <b>РАЗВЛЕЧЕНИЯ И СТАТИСТИКА</b>\n'
        '• <code>iq</code>, <code>жир</code>, <code>пятка</code> — замеры параметров.\n'
        '• <code>топ</code> — глобальные рейтинги игроков.\n\n'
        '🏪 <b>МАГАЗИН</b>\n'
        '• <code>магазин</code> или <code>/shop</code> — значки, кольца, титулы, питомцы.'
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
        f"• Часовой пояс: <b>UTC+{sett['timezone_offset']} (Киев / МСК)</b>\n"
        f"• Летний музыкальный таймер: <b>{'Включен' if sett.get('summer_music', True) else 'Выключен'}</b>\n"
        f"• Время напоминания: <b>за {sett['remind_minutes']} мин</b>"
    )
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton('⏳ Лимит дней (14/30/60)', callback_data='set_max_days'),
        InlineKeyboardButton('🗑 Авто-удаление сообщений', callback_data='toggle_del_msg')
    )
    markup.add(
        InlineKeyboardButton('🎵 Музыка лета (Вкл/Выкл)', callback_data='toggle_summer_music'),
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
        f"🎉 Ваш кастомный титул успешно установлен: <b>[{new_title}]</b>!\nОн будет отображаться возле вашего ника везде.",
        parse_mode='HTML'
    )


def send_user_profile(chat_id, user_tag, user_id, message_to_reply=None, message_id_to_edit=None):
    econ = get_user_econ(user_id, user_tag)
    markup = InlineKeyboardMarkup()

    purchased_titles = econ.get('titles', [])
    active_title = econ.get('active_title')
    custom_title = econ.get('custom_title')

    if purchased_titles:
        title_row = []
        for title_key in purchased_titles:
            if title_key in TITLES and title_key != active_title:
                title_row.append(InlineKeyboardButton(f"Надеть {TITLES[title_key]['text']}", callback_data=f"set_title_{title_key}"))
                if len(title_row) == 2:
                    markup.add(*title_row)
                    title_row = []
        if title_row:
            markup.add(*title_row)
        if active_title or custom_title:
            markup.add(InlineKeyboardButton('❌ Снять титул', callback_data='remove_title'))

    current_badge = econ.get('badge') or "Отсутствует"

    if custom_title:
        current_title = f"🌟 {custom_title} (Кастомный)"
    else:
        current_title = TITLES.get(active_title, {}).get('text', 'Отсутствует')

    inv = econ.get('inventory', [])
    inv_str = " ".join(inv) if inv else "Пусто (купите в магазине)"

    fish_inv = ', '.join(f'{name} × {count}' for name, count in econ.get('fish_inventory', {}).items()) or 'Пусто'
    hunt_inv = ', '.join(f'{name} × {count}' for name, count in econ.get('hunt_inventory', {}).items()) or 'Пусто'

    portfolio = econ.get('crypto_portfolio', {})
    portfolio_str = ', '.join(f'<b>{tick}</b>: {amt:.2f}' for tick, amt in portfolio.items() if amt > 0.0001) or 'Пусто'

    user_biz = econ.get('businesses', {})
    biz_str = ', '.join(BUSINESSES[b_id]['name'] for b_id in user_biz.keys() if b_id in BUSINESSES) or 'Нет'

    marriage_info = "Холост(а)"
    if econ.get('marriage'):
        m_data = econ['marriage']
        ring_emoji = RINGS.get(m_data.get('ring'), {}).get('emoji', '💍')
        days_together = max(1, int((time.time() - m_data.get('married_at', time.time())) / 86400))
        marriage_info = f"{ring_emoji} В браке с <b>{m_data.get('partner_name', 'Партнер')}</b> ({days_together} дн.)"

    pet_info = "Отсутствует (Купите в <code>/shop</code>)"
    if econ.get('pet'):
        p = econ['pet']
        update_pet_stats(p)
        pet_info = f"{p['name']} (🍖 Сытость: {p['hunger']}%, 🧼 Чистота: {p['cleanliness']}%)"

    unlocked_ach = len(econ.get('achievements', []))
    total_ach = len(ACHIEVEMENTS)

    rest_rewards = econ.get('rest_rewards_count', 0)
    if rest_rewards < 5:
        rest_rewards_str = f"{rest_rewards}/5 (150 🪙)"
    else:
        rest_rewards_str = "5/5 (Лимит бонусов исчерпан ⛔️)"

    m_st = econ.get('msg_stats', {})
    msg_stats_str = (
        f"• За день: <b>{m_st.get('day_count', 0)}</b> | "
        f"За неделю: <b>{m_st.get('week_count', 0)}</b>\n"
        f"• За месяц: <b>{m_st.get('month_count', 0)}</b> | "
        f"За все время: <b>{m_st.get('total_count', 0)}</b>"
    )

    lvl, cur_exp, next_exp, bar = get_account_level(econ.get('account_exp', 0))

    text = (
        f"🌐 <b>Единый Профиль: {make_link(chat_id, user_tag, user_id, ping=False)}</b>\n"
        f"<i>(Синхронизировано по User ID во всех чатах и ЛС)</i>\n\n"
        f"⭐ Уровень: <b>{lvl} LVL</b> [{bar}] (<b>{cur_exp}/{next_exp} EXP</b>)\n"
        f"💵 Баланс: <b>{econ['balance']} Ня-коинов 💸</b>\n"
        f"💼 Опыт работы: <b>{econ.get('work_exp', 0)} EXP</b>\n"
        f"💍 Семья: <b>{marriage_info}</b>\n"
        f"🏢 Бизнесы: <b>{biz_str}</b>\n"
        f"🐾 Питомец: <b>{pet_info}</b>\n"
        f"🏆 Достижения: <b>{unlocked_ach}/{total_ach} (/achievements)</b>\n"
        f"📊 <b>Статистика сообщений:</b>\n{msg_stats_str}\n\n"
        f"📈 <b>Крипто-портфель:</b> {portfolio_str}\n"
        f"😂 Смехуятинка: <b>{econ.get('smeh', 0)} балл(ов)</b>\n"
        f"🧠 Айкью (IQ): <b>{econ.get('iq', 100)}</b>\n"
        f"🍔 Процент жира: <b>{econ.get('fat', 20)}%</b>\n"
        f"🦶 Размер пятки: <b>{econ.get('foot_size', 25)} см</b>\n"
        f"🎁 Награды за ресты: <b>{rest_rewards_str}</b>\n"
        f"🏷 Активный значок: <b>{current_badge}</b>\n"
        f"👑 Активный титул: <b>{current_title}</b>\n"
        f"🎒 Значки: {inv_str}\n"
        f"🐟 Рыболовный инвентарь: {fish_inv}\n"
        f"🏹 Охотничий инвентарь: {hunt_inv}"
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
    markup.add(InlineKeyboardButton('✨ Значки и смайлы', callback_data='shop_cat_badges'))
    markup.add(InlineKeyboardButton('👑 Титулы и Сертификаты', callback_data='shop_cat_titles'))
    markup.add(InlineKeyboardButton('💍 Обручальные кольца', callback_data='shop_cat_rings'))
    markup.add(InlineKeyboardButton('🐾 Магазин Питомцев', callback_data='shop_cat_pets'))

    text = "🏪 <b>Глобальный Магазин Ня-коинов:</b>\n\nВыберите категорию товаров:"
    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')


# ---------------------------------------------------------
# ОБРАБОТЧИКИ СЕМЬИ И БРАКОВ
# ---------------------------------------------------------
@bot.message_handler(commands=['marry', 'брак'])
def cmd_marry(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name)

    if econ.get('marriage'):
        bot.reply_to(message, "❌ Вы уже находитесь в браке! Чтобы развестись, введите: <code>/divorce</code> или <code>развод</code>", parse_mode='HTML')
        return

    target_user, target_user_id, _ = parse_target_and_args(message, '/marry')
    if not target_user:
        target_user, target_user_id, _ = parse_target_and_args(message, 'брак')

    if not target_user:
        bot.reply_to(message, "❌ Укажите пользователя для предложения!\nПример: <code>брак @username</code> или ответом на сообщение.", parse_mode='HTML')
        return

    if target_user_id == user_id:
        bot.reply_to(message, "❌ Нельзя заключить брак с самим собой!")
        return

    target_econ = get_user_econ(target_user_id, target_user)
    if target_econ.get('marriage'):
        bot.reply_to(message, f"❌ Пользователь <b>{target_user}</b> уже состоит в браке!", parse_mode='HTML')
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
        f"💖 {to_link}, пользователь {from_link} делает вам предложение руки и сердца!\n"
        f"💍 Преподнесенное кольцо: {ring_emoji} <b>{ring_name}</b>\n\n"
        f"Вы согласны вступить в законный брак?",
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
        f"💒 <b>Информация о семье:</b>\n\n"
        f"💍 Кольцо: {ring_emoji} <b>{ring_name}</b>\n"
        f"👫 Супруг(а): {partner_link}\n"
        f"⏳ Дней в браке: <b>{days_together} дн.</b>\n"
        f"💰 Семейный сейф: <b>{vault} Ня-коинов 🪙</b>\n\n"
        f"💡 <b>Команды сейфа:</b>\n"
        f"• <code>семейный сейф положить 100</code>\n"
        f"• <code>семейный сейф снять 100</code>\n"
        f"• <code>развод</code> — расторгнуть брак"
    )
    bot.reply_to(message, text, parse_mode='HTML')


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
# ОБРАБОТЧИКИ БИЗНЕСОВ И ПАССИВНОГО ДОХОДА
# ---------------------------------------------------------
@bot.message_handler(commands=['business', 'бизнес', 'бизнесы', 'biz'])
def cmd_business(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name)
    user_biz = econ.setdefault('businesses', {})

    markup = InlineKeyboardMarkup()
    for b_id, b_info in BUSINESSES.items():
        status = "✅ Куплен" if b_id in user_biz else f"Купить ({b_info['price']} 🪙)"
        markup.add(InlineKeyboardButton(f"{b_info['name']} — {status}", callback_data=f"buy_biz_{b_id}"))

    markup.add(InlineKeyboardButton("💰 Собрать прибыль", callback_data="collect_biz_profit"))

    text = (
        "🏢 <b>Коммерческая недвижимость и Бизнесы:</b>\n\n"
        "Купленные предприятия приносят пассивный доход каждый час!\n"
        "Для сбора прибыли используйте кнопку ниже или команду <code>собрать прибыль</code>."
    )
    bot.reply_to(message, text, reply_markup=markup, parse_mode='HTML')


@bot.message_handler(commands=['collect', 'прибыль'])
def cmd_collect(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name)
    user_biz = econ.get('businesses', {})

    if not user_biz:
        bot.reply_to(message, "❌ У вас нет купленных бизнесов! Откройте <code>бизнесы</code> для покупки.", parse_mode='HTML')
        return

    now = time.time()
    last_collect = econ.get('last_biz_collect', now)
    hours_passed = (now - last_collect) / 3600.0

    if hours_passed < 0.1:
        bot.reply_to(message, "⏳ Прибыль еще не накопилась, загляните чуть позже!")
        return

    total_profit = sum(int(BUSINESSES[b_id]['income_per_hour'] * hours_passed) for b_id in user_biz.keys() if b_id in BUSINESSES)

    if total_profit <= 0:
        bot.reply_to(message, "⏳ Накоплений пока нет, подождите еще немного!")
        return

    econ['balance'] += total_profit
    econ['last_biz_collect'] = now
    save_data()

    bot.reply_to(message, f"💰 Вы успешно собрали прибыль со своих предприятий: <b>+{total_profit} Ня-коинов 🪙</b>!\nБаланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')


# ---------------------------------------------------------
# ОБРАБОТЧИКИ ОПЫТА И ТРЕНИРОВКИ
# ---------------------------------------------------------
def train_work_exp(user_id, user_tag):
    econ = get_user_econ(user_id, user_tag)
    now = time.time()
    cooldown = 900

    if now - econ.get('last_train_time', 0) < cooldown:
        left = int(cooldown - (now - econ.get('last_train_time', 0)))
        mins, secs = divmod(left, 60)
        return False, f"⏳ Тренироваться можно раз в 15 минут! Отдохните еще: <b>{mins} мин {secs} сек</b>."

    gain = random.randint(12, 35)
    econ['work_exp'] = econ.get('work_exp', 0) + gain
    econ['last_train_time'] = now
    add_account_exp(user_id, user_tag, gain)
    save_data()
    return True, f"🎓 Вы усердно попрактиковались и изучили полезные материалы!\nПолучено: <b>+{gain} EXP</b> опыта работы (Всего: <b>{econ['work_exp']} EXP</b>)."


@bot.message_handler(commands=['train', 'опыт'])
def cmd_train(message):
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    _, text_resp = train_work_exp(user_id, user_name)
    bot.reply_to(message, text_resp, parse_mode='HTML')


# ---------------------------------------------------------
# ОБРАБОТЧИКИ ИГР (БЛЭКДЖЕК, РПС, КУБИКИ, СЛОТЫ)
# ---------------------------------------------------------
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

    p_score = sum(p_cards)
    bot.send_message(
        chat_id,
        f"🃏 <b>Блэкджек (21 очко) — Игра:</b> {make_link(chat_id, user_name, user_id, ping=True)}\n"
        f"💰 Ставка: <b>{bet} 🪙</b>\n\n"
        f"👤 Ваши карты: {p_cards} (Сумма: <b>{p_score}</b>)\n"
        f"🤖 Карта дилера: [{d_cards[0]}, ❓]",
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
        bot.reply_to(message, "❌ У одного из участников недостаточно коинов для такой ставки!")
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
        f"✌️ <b>Камень-Ножницы-Бумага!</b>\n"
        f"Дуэль: {make_link(chat_id, user_name, user_id, ping=True)} ⚔️ {make_link(chat_id, target_user, target_user_id, ping=True)}\n"
        f"💰 Ставка: <b>{bet} 🪙</b> с каждого!\n\n"
        f"<i>Оба игрока, нажмите кнопку со своим тайным выбором ниже:</i>",
        reply_markup=markup,
        parse_mode='HTML'
    )


# ---------------------------------------------------------
# ОБРАБОТЧИКИ КРИПТО-БИРЖИ
# ---------------------------------------------------------
@bot.message_handler(commands=['market', 'биржа', 'crypto', 'крипта'])
def cmd_market(message):
    market = get_market_data()
    lines = [
        "📈 <b>Ня-Биржа Криптовалют и Акций</b>\n",
        "<i>Курсы обновляются в реальном времени каждые 30 минут:</i>\n"
    ]

    for ticker, info in market.items():
        price = info['price']
        old_price = info.get('old_price', price)
        diff = price - old_price
        pct = (diff / old_price * 100) if old_price > 0 else 0
        trend = "🟢 📈 +" if diff >= 0 else "🔴 📉 "
        lines.append(f"• <b>{info['name']}</b> [{ticker}]\n  Текущая цена: <b>{price:.2f} 🪙</b> ({trend}{pct:.1f}%)\n")

    lines.append("💡 <b>Как торговать:</b>")
    lines.append("• Купить: <code>купить крипту NYA 5</code> или <code>/buy_crypto NYA 5</code>")
    lines.append("• Продать: <code>продать крипту NYA 5</code> или <code>/sell_crypto NYA 5</code>")
    lines.append("• Посмотреть свой портфель: <code>портфель</code>")

    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')


@bot.message_handler(commands=['portfolio', 'портфель'])
def cmd_portfolio(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name)
    market = get_market_data()

    portfolio = econ.get('crypto_portfolio', {})
    total_val = 0.0

    lines = [f"💼 <b>Инвестиционный Портфель: {make_link(message.chat.id, user_name, user_id, ping=False)}</b>\n"]

    has_assets = False
    for ticker, amount in portfolio.items():
        if amount > 0.0001:
            has_assets = True
            cur_price = market.get(ticker, {}).get('price', 1.0)
            val = amount * cur_price
            total_val += val
            lines.append(f"• <b>{ticker}</b>: {amount:.2f} шт. (Оценка: <b>{val:.2f} 🪙</b> по курсу {cur_price:.2f})")

    if not has_assets:
        lines.append("🎒 Ваш крипто-портфель пока пуст! Купите активы через <code>биржа</code>.")
    else:
        lines.append(f"\n📊 <b>Общая стоимость активов: {total_val:.2f} Ня-коинов 🪙</b>")

    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')


def trade_crypto(chat_id, user_id, user_tag, action, ticker, amount_str, reply_msg=None):
    market = get_market_data()
    ticker = ticker.upper().strip()

    if ticker not in market:
        available = ', '.join(market.keys())
        msg = f"❌ Неверный тикер актива! Доступные активы: <b>{available}</b>"
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
        msg = "❌ Укажите корректное количество монет (положительное число)!"
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
            msg = f"❌ Недостаточно средств! Для покупки {amount} {ticker} нужно <b>{total_cost:.2f} 🪙</b> (Ваш баланс: {econ['balance']} 🪙)."
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
            f"✅ <b>Успешная покупка!</b>\n"
            f"Куплено: <b>{amount:.2f} {ticker}</b> ({asset['name']})\n"
            f"Сумма сделки: <b>-{total_cost:.2f} 🪙</b>\n"
            f"Остаток баланса: <b>{econ['balance']} 🪙</b>"
        )
        if reply_msg:
            bot.reply_to(reply_msg, msg, parse_mode='HTML')
        else:
            bot.send_message(chat_id, msg, parse_mode='HTML')

    elif action == 'sell':
        user_amount = portfolio.get(ticker, 0.0)
        if user_amount < amount:
            msg = f"❌ У вас недостаточно {ticker} для продажи! В наличии: <b>{user_amount:.2f} шт.</b>"
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
            f"💰 <b>Успешная продажа!</b>\n"
            f"Продано: <b>{amount:.2f} {ticker}</b> ({asset['name']})\n"
            f"Выручка: <b>+{earned} 🪙</b>\n"
            f"Ваш баланс: <b>{econ['balance']} 🪙</b>"
        )
        if reply_msg:
            bot.reply_to(reply_msg, msg, parse_mode='HTML')
        else:
            bot.send_message(chat_id, msg, parse_mode='HTML')


@bot.message_handler(commands=['buy_crypto', 'buy_stock'])
def cmd_buy_crypto(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    parts = message.text.split()
    if len(parts) >= 3:
        trade_crypto(message.chat.id, message.from_user.id, user_name, 'buy', parts[1], parts[2], message)
    else:
        bot.reply_to(message, "❌ Формат: <code>/buy_crypto NYA 5</code>", parse_mode='HTML')


@bot.message_handler(commands=['sell_crypto', 'sell_stock'])
def cmd_sell_crypto(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    parts = message.text.split()
    if len(parts) >= 3:
        trade_crypto(message.chat.id, message.from_user.id, user_name, 'sell', parts[1], parts[2], message)
    else:
        bot.reply_to(message, "❌ Формат: <code>/sell_crypto NYA 5</code>", parse_mode='HTML')


# ---------------------------------------------------------
# ОБРАБОТЧИКИ СИСТЕМЫ РАБОТЫ И ПИТОМЦЕВ
# ---------------------------------------------------------
@bot.message_handler(commands=['work', 'работа'])
def cmd_work(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name)

    markup = InlineKeyboardMarkup()
    for job_id, job in JOBS.items():
        btn_text = f"{job['name']} (Нужно: {job['req_exp']} EXP)"
        markup.add(InlineKeyboardButton(btn_text, callback_data=f"do_job_{job_id}"))

    markup.add(InlineKeyboardButton("🎓 Получить опыт (Тренировка)", callback_data="train_exp_btn"))

    text = (
        f"💼 <b>Биржа Труда и Вакансий</b>\n\n"
        f"👤 Ваш текущий опыт работы: <b>{econ.get('work_exp', 0)} EXP</b>\n\n"
        f"📌 Чем выше должность, тем больше зарплата, но <b>ниже шанс успешного выполнения</b>.\n"
        f"Выберите профессию для работы или тренируйтесь:"
    )
    bot.reply_to(message, text, reply_markup=markup, parse_mode='HTML')


@bot.message_handler(commands=['pet', 'питомец'])
def cmd_pet(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_name)
    pet = econ.get('pet')

    if not pet:
        bot.reply_to(
            message,
            "❌ У вас еще нет питомца!\nКупите себе питомца в магазине: <code>магазин</code> или <code>/shop</code>.",
            parse_mode='HTML'
        )
        return

    update_pet_stats(pet)
    save_data()

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🍖 Покормить (20 🪙)", callback_data="pet_feed"),
        InlineKeyboardButton("🧼 Помыть (15 🪙)", callback_data="pet_wash")
    )

    status_luck = "✅ Бонус к удаче активен!" if pet['hunger'] >= 30 and pet['cleanliness'] >= 30 else "⚠️ Питомец голоден или грязный!"

    text = (
        f"🐾 <b>Ваш Питомец: {pet['name']}</b>\n\n"
        f"🍖 Сытость: <b>{pet['hunger']}/100%</b>\n"
        f"🧼 Чистота: <b>{pet['cleanliness']}/100%</b>\n"
        f"🌟 Бонус к удаче: <b>+{pet['luck_bonus']}%</b>\n"
        f"📌 Статус: <b>{status_luck}</b>"
    )
    bot.reply_to(message, text, reply_markup=markup, parse_mode='HTML')


@bot.message_handler(commands=['feed', 'покормить'])
def cmd_feed(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    _, resp = feed_pet(user_id, user_name)
    bot.reply_to(message, resp, parse_mode='HTML')


@bot.message_handler(commands=['wash', 'помыть'])
def cmd_wash(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    _, resp = wash_pet(user_id, user_name)
    bot.reply_to(message, resp, parse_mode='HTML')


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
    bot.reply_to(message, f"💰 Вы продали добычу на сумму <b>+{total_earned} Ня-коинов 🪙</b>!\nБаланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')


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

    lines = [f"🏆 <b>Достижения пользователя {make_link(message.chat.id, user_name, user_id, ping=False)}:</b>\n"]
    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id in unlocked:
            lines.append(f"✅ <b>{ach['title']}</b> — {ach['desc']} (Получено +{ach['reward']} 🪙)")
        else:
            lines.append(f"🔒 <b>{ach['title']}</b> — {ach['desc']} (Награда: <b>+{ach['reward']} 🪙</b>)")

    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')


@bot.message_handler(commands=['balance', 'баланс'])
def cmd_balance(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(message.from_user.id, user_name)
    bot.reply_to(message, f"💵 <b>Ваш кошелек:</b> <b>{econ['balance']} Ня-коинов 💸</b>", parse_mode='HTML')


@bot.message_handler(commands=['shop', 'магазин', 'pet_shop'])
def cmd_shop(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    send_shop_menu(message.chat.id, message.from_user.id, user_name)


@bot.message_handler(commands=['tasks', 'задания', 'квесты'])
def cmd_tasks(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    bot.reply_to(message, format_daily_tasks(message.from_user.id, user_name), parse_mode='HTML')


@bot.message_handler(commands=['iq'])
def cmd_iq(message):
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_name)
    now_ts = time.time()
    cooldown = 1800

    if now_ts - econ.get('last_iq_time', 0) < cooldown:
        left_sec = int(cooldown - (now_ts - econ.get('last_iq_time', 0)))
        mins, secs = divmod(left_sec, 60)
        bot.reply_to(message, f"⏳ Тест на IQ можно проходить раз в 30 минут!\nПодождите: <b>{mins} мин {secs} сек</b>.", parse_mode='HTML')
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

    if now_ts - econ.get('last_fat_time', 0) < cooldown:
        left_sec = int(cooldown - (now_ts - econ.get('last_fat_time', 0)))
        mins, secs = divmod(left_sec, 60)
        bot.reply_to(message, f"⏳ Замер жира можно проводить раз в 30 минут!\nПодождите: <b>{mins} мин {secs} сек</b>.", parse_mode='HTML')
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

    if now_ts - econ.get('last_foot_time', 0) < cooldown:
        left_sec = int(cooldown - (now_ts - econ.get('last_foot_time', 0)))
        mins, secs = divmod(left_sec, 60)
        bot.reply_to(message, f"⏳ Измерить пятку можно раз в 20 минут!\nПодождите: <b>{mins} мин {secs} сек</b>.", parse_mode='HTML')
        return

    change = random.randint(-3, 4)
    econ['foot_size'] = max(5, min(60, econ.get('foot_size', 25) + change))
    econ['last_foot_time'] = now_ts
    save_data()
    sign = "+" if change >= 0 else ""

    bot.reply_to(message, f"🦶 {make_link(chat_id, user_name, user_id, ping=True)}, размер пятки: <b>{econ['foot_size']} см ({sign}{change} см) 🦶</b>", parse_mode='HTML')


@bot.message_handler(commands=['top', 'топ'])
def cmd_top(message):
    bot.reply_to(
        message,
        "🏆 <b>Глобальные рейтинги участников:</b>\n\n"
        "• Напишите <code>топ богачей</code> — посмотреть богачей\n"
        "• Напишите <code>топ iq</code> — самые умные\n"
        "• Напишите <code>топ жира</code> — процент жира\n"
        "• Напишите <code>топ пяток</code> — размер пяток",
        parse_mode='HTML'
    )


# --- ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ ---
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    global req_counter
    text = message.text.strip() if message.text else ''
    chat_id = message.chat.id
    str_chat = str(chat_id)
    user_id = message.from_user.id
    user_username = (message.from_user.username or '').lower()
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username or 'Пользователь'
    text_lower = text.lower()

    # Учет статистики сообщений и опыта аккаунта
    add_message_stat(user_id, user_name)

    # ---------------------------------------------------------
    # 👑 КОМАНДЫ СОЗДАТЕЛЯ / АДМИНИСТРАТОРА (ukrgorilka)
    # ---------------------------------------------------------
    is_super_admin = (user_username == ADMIN_USERNAME.lower())

    if is_super_admin:
        if text_lower in ['/admin', '/admin_help', 'админ', 'админка']:
            admin_help_text = (
                "👑 <b>ПАНЕЛЬ УПРАВЛЕНИЯ СОЗДАТЕЛЯ (@ukrgorilka):</b>\n\n"
                "💰 <b>Управление балансом и ресурсами:</b>\n"
                "• <code>/take_coins @username 500000</code> или <code>забрать коины @username 500000</code>\n"
                "  <i>(или ответом на сообщение: <code>/take_coins 500000</code>)</i> — списать коины.\n"
                "• <code>/give_coins @username 10000</code> или <code>выдать коины @username 10000</code>\n"
                "  <i>(или ответом на сообщение: <code>/give_coins 10000</code>)</i> — выдать коины.\n"
                "• <code>/set_balance @username 1000</code> или <code>установить баланс @username 1000</code> — установить точный баланс.\n"
                "• <code>/reset_balance @username</code> или <code>обнулить баланс @username</code> — обнулить баланс до 0.\n"
                "• <code>/clear_inventory @username</code> или <code>очистить инвентарь @username</code> — очистить улов и криптопортфель.\n\n"
                "🛑 <b>Управление ботом:</b>\n"
                "• <code>/stop_bot</code> или <code>выключить бота</code> — экстренное сохранение базы и выключение бота.\n"
                "• <code>/promo COMPENSATION</code> — промокод компенсации игрокам (+500 🪙)."
            )
            bot.reply_to(message, admin_help_text, parse_mode='HTML')
            return

        if text_lower in ['/stop_bot', '/shutdown', 'выключить бота', 'остановить бота']:
            bot.reply_to(message, "🛑 <b>Бот экстренно останавливается создателем @ukrgorilka...</b>\nДанные успешно сохранены в файл и Telegram backup!", parse_mode='HTML')
            save_data(send_backup=True)
            log_event('ВЫКЛЮЧЕНИЕ БОТА', f'Бот остановлен администратором @{user_username} в чате {chat_id}')
            time.sleep(1)
            os._exit(0)

        m_take = re.match(r'^(?:/take_coins|/take|забрать\s+коины|забрать\s+монеты|списать\s+коины|списать\s+монеты)\s*(.*)', text, re.IGNORECASE)
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
                bot.reply_to(message, "❌ Формат: <code>/take_coins @username 500000</code> или ответом: <code>/take_coins 500000</code>", parse_mode='HTML')
                return

            t_econ = get_user_econ(t_uid, t_uname)
            old_b = t_econ.get('balance', 0)
            t_econ['balance'] = max(0, old_b - t_amt)
            save_data()
            u_link = make_link(chat_id, t_uname, t_uid, ping=True)
            log_event('АДМИН: СПИСАНИЕ КОИНОВ', f'Админ @{user_username} списал {t_amt} 🪙 у {u_link}. Старый баланс: {old_b}, новый: {t_econ["balance"]}')
            bot.reply_to(
                message,
                f"💸 <b>Коины успешно списаны!</b>\n"
                f"👤 Пользователь: {u_link}\n"
                f"📉 Списано: <b>-{t_amt} 🪙</b>\n"
                f"💵 Новый баланс: <b>{t_econ['balance']} 🪙</b> (был: {old_b} 🪙)",
                parse_mode='HTML'
            )
            return

        m_give = re.match(r'^(?:/give_coins|/give|выдать\s+коины|выдать\s+монеты|начислить\s+коины|начислить\s+монеты)\s*(.*)', text, re.IGNORECASE)
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
                bot.reply_to(message, "❌ Формат: <code>/give_coins @username 1000</code> или ответом: <code>/give_coins 1000</code>", parse_mode='HTML')
                return

            t_econ = get_user_econ(t_uid, t_uname)
            old_b = t_econ.get('balance', 0)
            t_econ['balance'] = old_b + t_amt
            save_data()
            u_link = make_link(chat_id, t_uname, t_uid, ping=True)
            log_event('АДМИН: ВЫДАЧА КОИНОВ', f'Админ @{user_username} выдал {t_amt} 🪙 пользователю {u_link}. Баланс: {t_econ["balance"]}')
            bot.reply_to(
                message,
                f"🎁 <b>Коины успешно начислены!</b>\n"
                f"👤 Пользователь: {u_link}\n"
                f"📈 Начислено: <b>+{t_amt} 🪙</b>\n"
                f"💵 Новый баланс: <b>{t_econ['balance']} 🪙</b>",
                parse_mode='HTML'
            )
            return

        m_set = re.match(r'^(?:/set_balance|установить\s+баланс)\s*(.*)', text, re.IGNORECASE)
        if m_set:
            rem = m_set.group(1).strip()
            t_uid, t_uname, t_amt = None, None, None

            if message.reply_to_message:
                ru = message.reply_to_message.from_user
                t_uid = ru.id
                t_uname = (f"{ru.first_name or ''} {ru.last_name or ''}").strip() or ru.username
                m_a = re.search(r'\b\d+\b', rem)
                t_amt = int(m_a.group(0)) if m_a else None
            else:
                m_split = re.search(r'^(.*?)\s+(\d+)$', rem)
                if m_split:
                    target_raw = m_split.group(1).strip()
                    t_amt = int(m_split.group(2))
                    t_uid, t_uname = resolve_user_from_string(chat_id, target_raw)
                    if not t_uname:
                        t_uname = target_raw

            if not t_uname or t_amt is None:
                bot.reply_to(message, "❌ Формат: <code>/set_balance @username 1000</code> или ответом: <code>/set_balance 1000</code>", parse_mode='HTML')
                return

            t_econ = get_user_econ(t_uid, t_uname)
            old_b = t_econ.get('balance', 0)
            t_econ['balance'] = max(0, t_amt)
            save_data()
            u_link = make_link(chat_id, t_uname, t_uid, ping=True)
            bot.reply_to(
                message,
                f"⚙️ <b>Баланс пользователя установлен!</b>\n"
                f"👤 Пользователь: {u_link}\n"
                f"💵 Баланс: <b>{t_econ['balance']} 🪙</b> (был: {old_b} 🪙)",
                parse_mode='HTML'
            )
            return

        m_reset = re.match(r'^(?:/reset_balance|обнулить\s+баланс)\s*(.*)', text, re.IGNORECASE)
        if m_reset:
            rem = m_reset.group(1).strip()
            t_uid, t_uname = None, None

            if message.reply_to_message:
                ru = message.reply_to_message.from_user
                t_uid = ru.id
                t_uname = (f"{ru.first_name or ''} {ru.last_name or ''}").strip() or ru.username
            elif rem:
                t_uid, t_uname = resolve_user_from_string(chat_id, rem)
                if not t_uname:
                    t_uname = rem

            if not t_uname:
                bot.reply_to(message, "❌ Формат: <code>/reset_balance @username</code> или ответом на сообщение.", parse_mode='HTML')
                return

            t_econ = get_user_econ(t_uid, t_uname)
            old_b = t_econ.get('balance', 0)
            t_econ['balance'] = 0
            save_data()
            u_link = make_link(chat_id, t_uname, t_uid, ping=True)
            bot.reply_to(
                message,
                f"🔄 <b>Баланс полностью обнулен!</b>\n"
                f"👤 Пользователь: {u_link}\n"
                f"💵 Баланс: <b>0 🪙</b> (сгорело: {old_b} 🪙)",
                parse_mode='HTML'
            )
            return

        m_clear_inv = re.match(r'^(?:/clear_inventory|очистить\s+инвентарь)\s*(.*)', text, re.IGNORECASE)
        if m_clear_inv:
            rem = m_clear_inv.group(1).strip()
            t_uid, t_uname = None, None

            if message.reply_to_message:
                ru = message.reply_to_message.from_user
                t_uid = ru.id
                t_uname = (f"{ru.first_name or ''} {ru.last_name or ''}").strip() or ru.username
            elif rem:
                t_uid, t_uname = resolve_user_from_string(chat_id, rem)
                if not t_uname:
                    t_uname = rem

            if not t_uname:
                bot.reply_to(message, "❌ Формат: <code>/clear_inventory @username</code> или ответом на сообщение.", parse_mode='HTML')
                return

            t_econ = get_user_econ(t_uid, t_uname)
            t_econ['fish_inventory'] = {}
            t_econ['hunt_inventory'] = {}
            t_econ['crypto_portfolio'] = {}
            save_data()
            u_link = make_link(chat_id, t_uname, t_uid, ping=True)
            bot.reply_to(
                message,
                f"🧹 <b>Инвентарь и криптопортфель очищены!</b>\n"
                f"👤 Пользователь: {u_link}\n"
                f"Рыба, охота и криптовалюты удалены.",
                parse_mode='HTML'
            )
            return

    completed_tasks = track_daily_task(user_id, user_name, 'messages', 1, chat_id)
    if completed_tasks:
        for task_name, reward in completed_tasks:
            try:
                bot.send_message(chat_id, f'🎉 {make_link(chat_id, user_name, user_id, ping=True)} выполнил(а) задание: <b>{task_name}</b>! +{reward} 🪙', parse_mode='HTML')
            except Exception:
                pass

    # ОТВЕТ ГИФКОЙ НА "ПОЧЕМУ"
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

    # ОБРАБОТКА СЕМЕЙНОГО СЕЙФА
    if text_lower.startswith('семейный сейф положить'):
        econ = get_user_econ(user_id, user_name)
        if not econ.get('marriage'):
            bot.reply_to(message, "❌ Вы не состоите в браке!")
            return
        m_amt = re.search(r'(\d+)', text)
        if m_amt:
            amt = int(m_amt.group(1))
            if amt <= 0 or econ['balance'] < amt:
                bot.reply_to(message, "❌ Недостаточно коинов на балансе!")
                return
            econ['balance'] -= amt
            econ['marriage']['vault'] = econ['marriage'].get('vault', 0) + amt

            p_econ = get_user_econ(econ['marriage']['partner_id'])
            if p_econ.get('marriage'):
                p_econ['marriage']['vault'] = econ['marriage']['vault']
            save_data()
            bot.reply_to(message, f"💰 Вы положили <b>{amt} 🪙</b> в семейный сейф! Всего в сейфе: <b>{econ['marriage']['vault']} 🪙</b>", parse_mode='HTML')
        return

    elif text_lower.startswith('семейный сейф снять'):
        econ = get_user_econ(user_id, user_name)
        if not econ.get('marriage'):
            bot.reply_to(message, "❌ Вы не состоите в браке!")
            return
        m_amt = re.search(r'(\d+)', text)
        if m_amt:
            amt = int(m_amt.group(1))
            vault = econ['marriage'].get('vault', 0)
            if amt <= 0 or vault < amt:
                bot.reply_to(message, "❌ В семейном сейфе недостаточно коинов!")
                return
            econ['marriage']['vault'] -= amt
            econ['balance'] += amt
            p_econ = get_user_econ(econ['marriage']['partner_id'])
            if p_econ.get('marriage'):
                p_econ['marriage']['vault'] = econ['marriage']['vault']
            save_data()
            bot.reply_to(message, f"💸 Вы сняли <b>{amt} 🪙</b> из семейного сейфа! Остаток: <b>{econ['marriage']['vault']} 🪙</b>", parse_mode='HTML')
        return

    # ТРЕНИРОВКА ОПЫТА
    if text_lower in ['опыт', 'прокачать опыт', 'тренировка']:
        cmd_train(message)
        return

    # ПОКОРМИТЬ / ПОМЫТЬ ПИТОМЦА ТЕКСТОМ
    if text_lower in ['покормить', 'покормить питомца', 'еда']:
        cmd_feed(message)
        return
    elif text_lower in ['помыть', 'помыть питомца', 'искупать']:
        cmd_wash(message)
        return

    # МАГАЗИН ТЕКСТОМ
    if text_lower in ['магазин', 'шоп', 'пет шоп', 'петшоп', 'магазин питомцев']:
        cmd_shop(message)
        return

    # ПОМОЩЬ / СТАРТ ТЕКСТОМ
    if text_lower in ['помощь', 'хелп', 'команды', 'меню']:
        send_welcome(message)
        return

    # БЛЭКДЖЕК ТЕКСТОМ
    m_bj_text = re.match(r'^(?:блэкджек|блекджек|бдж|21)(?:\s+(\d+))?$', text_lower)
    if m_bj_text:
        bet_val = int(m_bj_text.group(1)) if m_bj_text.group(1) else 50
        process_bj_game(message, bet_val)
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
                bot.reply_to(message, f"💡 Ответьте на сообщение пользователя или укажите ник/ссылку:\n<code>{rp_cmd} @username</code>", parse_mode='HTML')
                return

    # КРИПТО-ТОРГОВЛЯ ТЕКСТОМ
    if text_lower.startswith(('купить крипту', 'купить акцию')):
        parts = text.split()
        if len(parts) >= 4:
            trade_crypto(chat_id, user_id, user_name, 'buy', parts[2], parts[3], message)
            return

    elif text_lower.startswith(('продать крипту', 'продать акцию')):
        parts = text.split()
        if len(parts) >= 4:
            trade_crypto(chat_id, user_id, user_name, 'sell', parts[2], parts[3], message)
            return

    # РАСПОЗНАВАНИЕ «Кто ты @username» (СТРОГО «кто ты»)
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
                f"📝 <b>Причина:</b> {rest_info.get('reason', 'Не указана')}\n"
                f"⏱ <b>Срок:</b> {rest_info.get('duration', 'Не указан')}",
                parse_mode='HTML'
            )
        else:
            display_name = target_found_name or 'Пользователь'
            user_link = make_link(chat_id, display_name, target_found_id, ping=False)
            bot.reply_to(message, f"✅ Пользователь {user_link} сейчас не находится в ресте!", parse_mode='HTML')
        return

    # ВСЕГДА АКТИВНЫЕ ТРИГГЕРЫ
    for pattern, responses in ALWAYS_ACTIVE_PATTERNS.items():
        if re.search(pattern, text_lower, re.IGNORECASE):
            bot.reply_to(message, random.choice(responses))
            break

    # Авто-удаление сообщений находящихся в ресте
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

    # Команда +смехуятинка
    if text_lower in ['+смехуятинка', 'смехуятинка']:
        if message.reply_to_message:
            target_u = message.reply_to_message.from_user
            target_tag = (f"{target_u.first_name or ''} {target_u.last_name or ''}").strip() or target_u.username
            target_id = target_u.id

            econ = get_user_econ(target_id, target_tag)
            econ['smeh'] = econ.get('smeh', 0) + 1
            save_data()

            u_link = make_link(chat_id, target_tag, target_id, ping=True)
            bot.reply_to(message, f"😂 Пользователю {u_link} начислено +1 очко <b>Смехуятинки</b>!\nВсего: <b>{econ['smeh']}</b>", parse_mode='HTML')
        else:
            bot.reply_to(message, "❌ Ответьте этой командой на сообщение человека!")
        return

    # Замеры параметров
    elif text_lower in ['айкью', 'iq', 'iqи', 'айкю']:
        cmd_iq(message)
        return
    elif text_lower in ['жир', 'жирок', 'жирность', 'процент жира']:
        cmd_fat(message)
        return
    elif text_lower in ['пятка', 'пяточка', 'размер пятки', 'пятки']:
        cmd_foot(message)
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
    elif text_lower in ['богачи', 'топ коинов', 'топ богачей']:
        if 'economy' in db and db['economy']:
            sorted_econ = sorted(db['economy'].items(), key=lambda x: x[1].get('balance', 0), reverse=True)
            resp = "🏆 <b>Глобальный топ самых богатых участников:</b>\n\n"
            for idx, (k, info) in enumerate(sorted_econ[:10], 1):
                u_name = info.get('display_name', 'Пользователь')
                u_id = info.get('user_id')
                resp += f"{idx}. {make_link(chat_id, u_name, u_id, ping=False)} — <b>{info.get('balance', 0)} 🪙</b>\n"
            bot.reply_to(message, resp, parse_mode='HTML')
        return

    # Текстовые эквиваленты
    if text_lower in ['баланс', 'коины', 'ня-коины', 'деньги']:
        cmd_balance(message)
        return
    elif text_lower in ['инвентарь', 'профиль', 'мои значки']:
        cmd_profile(message)
        return
    elif text_lower in ['бонус', 'коин', 'взять бонус']:
        econ = get_user_econ(user_id, user_name)
        now_ts = time.time()
        if now_ts - econ.get('last_hourly', 0) >= 3600:
            lvl, _, _, _ = get_account_level(econ.get('account_exp', 0))
            reward = random.randint(15, 45) + (lvl * 3)
            econ['balance'] += reward
            econ['last_hourly'] = now_ts
            add_account_exp(user_id, user_name, 10)
            save_data()
            check_achievements(user_id, user_name, 'bonuses', 1, chat_id)
            completed = track_daily_task(user_id, user_name, 'bonus', 1, chat_id)
            bot.reply_to(
                message,
                f"🎲 Вы собрали часовой бонус: <b>+{reward} Ня-коинов 🪙</b> (+{lvl*3} за {lvl} LVL)!\n"
                f"Баланс: <b>{econ['balance']} 💸</b>",
                parse_mode='HTML'
            )
            for task_name, task_reward in completed:
                bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        else:
            left_sec = 3600 - (now_ts - econ.get('last_hourly', 0))
            mins, secs = divmod(int(left_sec), 60)
            bot.reply_to(message, f"⏳ Можно собирать коины каждый час! До следующего сбора: <b>{mins} мин {secs} сек</b>.", parse_mode='HTML')
        return
    elif text_lower in ['задания', 'daily', 'квесты']:
        cmd_tasks(message)
        return

    # ИГРА В КОСТИ
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

    # БАФНУТЫЕ СЛОТЫ (SLOTS)
    elif text_lower.startswith(('слоты', '/slots', 'казино')):
        match = re.search(r'(?:слоты|/slots|казино)\s*(\d+)?', text, re.IGNORECASE)
        bet = int(match.group(1)) if match and match.group(1) else 0

        econ = get_user_econ(user_id, user_name)
        if bet <= 0:
            bot.reply_to(message, '❌ Укажите ставку! Пример: <code>слоты 100</code> или <code>/slots 100</code>', parse_mode='HTML')
            return
        if bet > econ['balance']:
            bot.reply_to(message, f"❌ Недостаточно Ня-коинов! У вас на балансе: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
            return

        symbols_pool = ['🍒', '🍋', '🍊', '🍀', '⭐', '💎']
        luck_bonus = econ['pet'].get('luck_bonus', 0) if econ.get('pet') else 0

        weights = [
            26,  # 🍒
            23,  # 🍋
            20,  # 🍊
            15,  # 🍀
            10 + int(luck_bonus * 0.05),  # ⭐
            6 + int(luck_bonus * 0.04)   # 💎
        ]

        roll = random.choices(symbols_pool, weights=weights, k=3)
        result = f"🎰 <b>[ {roll[0]} | {roll[1]} | {roll[2]} ]</b>\n"

        if roll[0] == roll[1] == roll[2] == '💎':
            win = int(bet * 10)
            econ['balance'] += (win - bet)
            result += f'\n💎👑 <b>МЕГА ДЖЕКПОТ (10x)!</b> Вы сорвали куш: <b>+{win} 🪙</b>!'

        elif roll[0] == roll[1] == roll[2] and roll[0] in ['⭐', '🍀']:
            multiplier = 5 if roll[0] == '⭐' else 4
            win = int(bet * multiplier)
            econ['balance'] += (win - bet)
            result += f'\n🌟 <b>ОГРОМНЫЙ ВЫИГРЫШ ({multiplier}x)!</b> Награда: <b>+{win} 🪙</b>!'

        elif roll[0] == roll[1] == roll[2]:
            win = int(bet * 2.5)
            econ['balance'] += (win - bet)
            result += f'\n🎉 <b>Три в ряд (2.5x)!</b> Вы выиграли: <b>+{win} 🪙</b>!'

        elif roll.count('💎') == 2 or roll.count('⭐') == 2:
            win = int(bet * 1.5)
            econ['balance'] += (win - bet)
            result += f'\n✨ <b>Два редких символа!</b> Выигрыш: <b>+{win} 🪙</b> (1.5x)!'

        elif len(set(roll)) == 2:
            win = int(bet * 0.8)
            econ['balance'] += (win - bet)
            result += f'\n🙂 <b>Два совпадения!</b> Утешительный возврат: <b>{win} 🪙</b> (0.8x).'

        else:
            econ['balance'] -= bet
            result += f'\n💸 Ничего не совпало! Проигрыш <b>-{bet} 🪙</b>.'

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
        left = cooldown_text(econ.get('last_fish_time', 0), 7200)
        if left:
            bot.reply_to(message, f'⏳ Рыбалка доступна раз в 2 часа. Осталось: <b>{left}</b>.', parse_mode='HTML')
            return

        luck_bonus = econ['pet'].get('luck_bonus', 0) if econ.get('pet') else 0
        weights = [max(1, int(f[3] * (1 + luck_bonus / 100.0))) for f in FISH_TYPES]
        caught = random.choices(FISH_TYPES, weights=weights, k=1)[0]
        econ['last_fish_time'] = time.time()
        add_inventory_item(econ['fish_inventory'], caught[0])
        add_account_exp(user_id, user_name, 5)
        save_data()
        check_achievements(user_id, user_name, 'fish', 1, chat_id)
        bot.reply_to(message, f'🎣 Вы поймали: <b>{caught[0]}</b> [{caught[1]}]!\n💰 Базовая цена: <b>{caught[2]} 🪙</b>\n💡 Продать: <code>продать</code>', parse_mode='HTML')
        return

    elif text_lower in ['охота', '/hunt']:
        econ = get_user_econ(user_id, user_name)
        left = cooldown_text(econ.get('last_hunt_time', 0), 7200)
        if left:
            bot.reply_to(message, f'⏳ Охота доступна раз в 2 часа. Осталось: <b>{left}</b>.', parse_mode='HTML')
            return

        luck_bonus = econ['pet'].get('luck_bonus', 0) if econ.get('pet') else 0
        weights = [max(1, int(h[3] * (1 + luck_bonus / 100.0))) for h in HUNT_TYPES]
        caught = random.choices(HUNT_TYPES, weights=weights, k=1)[0]
        econ['last_hunt_time'] = time.time()
        add_inventory_item(econ['hunt_inventory'], caught[0])
        add_account_exp(user_id, user_name, 5)
        save_data()
        check_achievements(user_id, user_name, 'hunt', 1, chat_id)
        bot.reply_to(message, f'🏹 Вы добыли: <b>{caught[0]}</b> [{caught[1]}]!\n💰 Базовая цена: <b>{caught[2]} 🪙</b>\n💡 Продать: <code>продать</code>', parse_mode='HTML')
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
            f"<i>(Комиссия сети 3%: сгорело {tax} 🪙, зачислено {receive_amount} 🪙)</i>",
            parse_mode='HTML'
        )
        return

    # ПРОМОКОДЫ
    elif text_lower.startswith(('промокод', '/promo')):
        match = re.search(r'(?:промокод|/promo)\s+(.+)', text, re.IGNORECASE)
        if match:
            code_input = match.group(1).strip().upper()
            user_key = get_global_user_key(user_id, user_name)

            if code_input == 'ADMIN1000' and user_username == ADMIN_USERNAME:
                add_coins(user_id, user_name, 10000)
                bot.reply_to(message, "🎁 <b>+10000 Ня-коинов</b> начислено создателю!", parse_mode='HTML')
            elif code_input in ['COMPENSATION', 'КОМПЕНСАЦИЯ', 'FIX500', 'SORRY']:
                db.setdefault('promos', {}).setdefault('COMPENSATION', [])
                if user_key in db['promos']['COMPENSATION']:
                    bot.reply_to(message, "❌ Вы уже получили компенсацию по этому промокоду!", parse_mode='HTML')
                else:
                    db['promos']['COMPENSATION'].append(user_key)
                    add_coins(user_id, user_name, 500)
                    bot.reply_to(
                        message,
                        "🎉 <b>Промокод компенсации успешно активирован!</b>\n"
                        "💰 Вам начислено <b>+500 Ня-коинов 🪙</b>.\n"
                        "<i>Приятной игры и спасибо, что вы с нами! 🌸</i>",
                        parse_mode='HTML'
                    )
            elif code_input in ['OHAYO500', 'OHAYO']:
                db.setdefault('promos', {}).setdefault('OHAYO500', [])
                if user_key in db['promos']['OHAYO500']:
                    bot.reply_to(message, "❌ Вы уже активировали этот промокод!")
                else:
                    db['promos']['OHAYO500'].append(user_key)
                    add_coins(user_id, user_name, 500)
                    bot.reply_to(message, "🎉 Промокод активирован! +500 Ня-коинов 🪙!", parse_mode='HTML')
            else:
                bot.reply_to(message, "❌ Неверный промокод!")
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
                save_data()
                bot.reply_to(message, f'🗑 Рест с {make_link(chat_id, display_name, target_id or rest_info.get("user_id"), ping=True)} снят.', parse_mode='HTML')
            else:
                bot.reply_to(message, f'❌ Рест для указанного пользователя не найден.', parse_mode='HTML')

    elif text_lower in ['ресты', 'рест']:
        if str_chat not in db['rests'] or not db['rests'][str_chat]:
            bot.reply_to(message, '🌴 В данный момент никто не находится в ресте.')
        else:
            resp = '📋 <b>Список активных рестов:</b>\n\n'
            for r_key, info in db['rests'][str_chat].items():
                u_name = info.get('user_name', r_key)
                u_id = info.get('user_id')
                resp += f"• {make_link(chat_id, u_name, u_id, ping=False)} — {info['duration']} (Причина: {info.get('reason', 'Не указана')})\n"
            bot.reply_to(message, resp, parse_mode='HTML')

    elif text_lower == 'мой рест':
        in_rest, info, _ = check_user_rest(db.get('rests', {}).get(str_chat, {}), user_id=user_id, user_name=user_name)
        if in_rest and info:
            bot.reply_to(message, f"🌴 <b>Ваш рест:</b> {info['duration']}\n📝 <b>Причина:</b> {info.get('reason', 'Не указана')}", parse_mode='HTML')
        else:
            bot.reply_to(message, "✅ Вы сейчас не находитесь в ресте!", parse_mode='HTML')


# ---------------------------------------------------------
# ОБРАБОТКА ИНТЕРАКТИВНЫХ КНОПОК CALLBACK
# ---------------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    user_name = (f"{call.from_user.first_name or ''} {call.from_user.last_name or ''}").strip() or call.from_user.username

    if call.data == 'train_exp_btn':
        success, text_resp = train_work_exp(user_id, user_name)
        bot.answer_callback_query(call.id, text_resp.replace('<b>', '').replace('</b>', ''), show_alert=True)
        if success:
            econ = get_user_econ(user_id, user_name)
            markup = InlineKeyboardMarkup()
            for job_id, job in JOBS.items():
                btn_text = f"{job['name']} (Нужно: {job['req_exp']} EXP)"
                markup.add(InlineKeyboardButton(btn_text, callback_data=f"do_job_{job_id}"))
            markup.add(InlineKeyboardButton("🎓 Получить опыт (Тренировка)", callback_data="train_exp_btn"))
            try:
                bot.edit_message_text(
                    f"💼 <b>Биржа Труда и Вакансий</b>\n\n👤 Ваш текущий опыт: <b>{econ['work_exp']} EXP</b>\n\nВыберите профессию для работы:",
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    reply_markup=markup,
                    parse_mode='HTML'
                )
            except Exception:
                pass

    elif call.data.startswith('do_job_'):
        job_id = call.data.replace('do_job_', '')
        if job_id in JOBS:
            job = JOBS[job_id]
            econ = get_user_econ(user_id, user_name)
            if econ.get('work_exp', 0) < job['req_exp']:
                bot.answer_callback_query(call.id, f"❌ Нужно минимум {job['req_exp']} EXP опыта!", show_alert=True)
                return
            now = time.time()
            if now - econ.get('last_work_time', 0) < 1800:
                left = int(1800 - (now - econ.get('last_work_time', 0)))
                bot.answer_callback_query(call.id, f"⏳ Отдохните еще {left // 60} мин {left % 60} сек.", show_alert=True)
                return
            econ['last_work_time'] = now
            if random.randint(1, 100) <= job['chance']:
                pay = random.randint(job['min_pay'], job['max_pay'])
                econ['balance'] += pay
                econ['work_exp'] = econ.get('work_exp', 0) + job['exp_gain']
                add_account_exp(user_id, user_name, job['exp_gain'])
                save_data()
                bot.answer_callback_query(call.id, f"✅ Зарплата: +{pay} 🪙 (+{job['exp_gain']} EXP)!", show_alert=True)
                bot.send_message(chat_id, f"💼 {make_link(chat_id, user_name, user_id, ping=True)} заработал(а) <b>+{pay} 🪙</b> на должности <b>{job['name']}</b>!", parse_mode='HTML')
            else:
                econ['work_exp'] = econ.get('work_exp', 0) + 2
                add_account_exp(user_id, user_name, 2)
                save_data()
                bot.answer_callback_query(call.id, "❌ Вы ошиблись на смене! Получено +2 EXP.", show_alert=True)

    elif call.data.startswith('buy_biz_'):
        b_id = call.data.replace('buy_biz_', '')
        if b_id in BUSINESSES:
            b_info = BUSINESSES[b_id]
            econ = get_user_econ(user_id, user_name)
            user_biz = econ.setdefault('businesses', {})
            if b_id in user_biz:
                bot.answer_callback_query(call.id, "❌ Этот бизнес уже приобретен!", show_alert=True)
                return
            if econ['balance'] < b_info['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {b_info['price']} 🪙!", show_alert=True)
                return
            econ['balance'] -= b_info['price']
            user_biz[b_id] = time.time()
            check_achievements(user_id, user_name, 'biz_bought', 1, chat_id)
            save_data()
            bot.answer_callback_query(call.id, f"🎉 Вы приобрели {b_info['name']}!", show_alert=True)
            bot.send_message(chat_id, f"🏢 {make_link(chat_id, user_name, user_id, ping=True)} приобрел(а) бизнес — <b>{b_info['name']}</b>!", parse_mode='HTML')

    elif call.data == 'collect_biz_profit':
        econ = get_user_econ(user_id, user_name)
        user_biz = econ.get('businesses', {})
        now = time.time()
        hours_passed = (now - econ.get('last_biz_collect', now)) / 3600.0
        total_profit = sum(int(BUSINESSES[b]['income_per_hour'] * hours_passed) for b in user_biz.keys() if b in BUSINESSES)
        if total_profit <= 0:
            bot.answer_callback_query(call.id, "⏳ Прибыль еще не накопилась!", show_alert=True)
            return
        econ['balance'] += total_profit
        econ['last_biz_collect'] = now
        save_data()
        bot.answer_callback_query(call.id, f"💰 Собрано: +{total_profit} 🪙!", show_alert=True)

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
                f"{make_link(chat_id, user_name, user_id, ping=True)} теперь официально муж и жена! ❤️",
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
            p_score = sum(game['p_cards'])
            if p_score > 21:
                game['finished'] = True
                bot.edit_message_text(
                    f"💥 <b>Перебор ({p_score})!</b> Вы проиграли ставку <b>{game['bet']} 🪙</b>.\nВаши карты: {game['p_cards']}",
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
            p_score = sum(game['p_cards'])
            while sum(game['d_cards']) < 17:
                game['d_cards'].append(game['deck'].pop())
            d_score = sum(game['d_cards'])

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

    elif call.data.startswith('rps_'):
        parts = call.data.split('_')
        choice = parts[1]
        game_id = f"rps_{parts[2]}_{parts[3]}_{parts[4]}"
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
                f"✌️ <b>Итоги дуэли Цу-е-фа:</b>\n\n"
                f"• {game['p1_tag']}: {c_map[c1]}\n• {game['p2_tag']}: {c_map[c2]}\n\n{res}",
                chat_id=chat_id,
                message_id=call.message.message_id,
                parse_mode='HTML'
            )
            del active_rps_games[game_id]

    elif call.data == 'pet_feed':
        success, text_resp = feed_pet(user_id, user_name)
        bot.answer_callback_query(call.id, text_resp.replace('<b>', '').replace('</b>', ''), show_alert=True)
        if success:
            econ = get_user_econ(user_id, user_name)
            pet = econ.get('pet')
            status_luck = "✅ Бонус к удаче активен!" if pet['hunger'] >= 30 and pet['cleanliness'] >= 30 else "⚠️ Питомец голоден или грязный!"
            updated_text = (
                f"🐾 <b>Ваш Питомец: {pet['name']}</b>\n\n"
                f"🍖 Сытость: <b>{pet['hunger']}/100%</b>\n"
                f"🧼 Чистота: <b>{pet['cleanliness']}/100%</b>\n"
                f"🌟 Бонус к удаче: <b>+{pet['luck_bonus']}%</b>\n"
                f"📌 Статус: <b>{status_luck}</b>"
            )
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("🍖 Покормить (20 🪙)", callback_data="pet_feed"),
                InlineKeyboardButton("🧼 Помыть (15 🪙)", callback_data="pet_wash")
            )
            try:
                bot.edit_message_text(updated_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception:
                pass

    elif call.data == 'pet_wash':
        success, text_resp = wash_pet(user_id, user_name)
        bot.answer_callback_query(call.id, text_resp.replace('<b>', '').replace('</b>', ''), show_alert=True)
        if success:
            econ = get_user_econ(user_id, user_name)
            pet = econ.get('pet')
            status_luck = "✅ Бонус к удаче активен!" if pet['hunger'] >= 30 and pet['cleanliness'] >= 30 else "⚠️ Питомец голоден или грязный!"
            updated_text = (
                f"🐾 <b>Ваш Питомец: {pet['name']}</b>\n\n"
                f"🍖 Сытость: <b>{pet['hunger']}/100%</b>\n"
                f"🧼 Чистота: <b>{pet['cleanliness']}/100%</b>\n"
                f"🌟 Бонус к удаче: <b>+{pet['luck_bonus']}%</b>\n"
                f"📌 Статус: <b>{status_luck}</b>"
            )
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("🍖 Покормить (20 🪙)", callback_data="pet_feed"),
                InlineKeyboardButton("🧼 Помыть (15 🪙)", callback_data="pet_wash")
            )
            try:
                bot.edit_message_text(updated_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception:
                pass

    elif call.data == 'set_max_days':
        if not is_admin(chat_id, user_id):
            return
        sett = get_chat_settings(chat_id)
        opts = [14, 30, 60]
        next_opt = opts[(opts.index(sett['max_days']) + 1) % len(opts)]
        sett['max_days'] = next_opt
        save_data()
        bot.answer_callback_query(call.id, f'✅ Лимит изменен на {next_opt} дней!')
        chat_settings_cmd(call.message)

    elif call.data == 'toggle_del_msg':
        if not is_admin(chat_id, user_id):
            return
        sett = get_chat_settings(chat_id)
        sett['delete_rest_msg'] = not sett['delete_rest_msg']
        save_data()
        bot.answer_callback_query(call.id, f"✅ Авто-удаление: {'Включено' if sett['delete_rest_msg'] else 'Выключено'}")
        chat_settings_cmd(call.message)

    elif call.data == 'toggle_summer_music':
        if not is_admin(chat_id, user_id):
            return
        sett = get_chat_settings(chat_id)
        sett['summer_music'] = not sett.get('summer_music', True)
        save_data()
        bot.answer_callback_query(call.id, f"✅ Музыка лета: {'Включена' if sett['summer_music'] else 'Выключена'}")
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

    elif call.data == 'shop_main':
        send_shop_menu(chat_id, user_id, user_name, call.message.message_id)

    elif call.data == 'shop_cat_titles':
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton('👑 Кинг (3000 🪙)', callback_data='buy_title_king'),
            InlineKeyboardButton('💤 Соня (2200 🪙)', callback_data='buy_title_sonya')
        )
        markup.add(
            InlineKeyboardButton('🔥 Легенда (3600 🪙)', callback_data='buy_title_legend'),
            InlineKeyboardButton('🐉 Дракон (4200 🪙)', callback_data='buy_title_dragon')
        )
        markup.add(
            InlineKeyboardButton('🥐 Булочка (1800 🪙)', callback_data='buy_title_bun'),
            InlineKeyboardButton('🌟 Кастомный Титул (15000 🪙)', callback_data='buy_cert_custom_title')
        )
        markup.add(InlineKeyboardButton('🔙 Назад', callback_data='shop_main'))
        bot.edit_message_text("👑 <b>Категория: Титулы и Сертификаты</b>", chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'shop_cat_badges':
        markup = InlineKeyboardMarkup()
        for b_key, b_info in list(BADGES.items())[:8]:
            markup.add(InlineKeyboardButton(f"{b_info['emoji']} {b_info['name']} ({b_info['price']} 🪙)", callback_data=f"buy_badge_{b_key}"))
        markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data='shop_main'))
        bot.edit_message_text("✨ <b>Категория: Значки для профиля</b>", chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'shop_cat_rings':
        markup = InlineKeyboardMarkup()
        for r_id, r_info in RINGS.items():
            markup.add(InlineKeyboardButton(f"{r_info['emoji']} {r_info['name']} ({r_info['price']} 🪙)", callback_data=f"buy_ring_{r_id}"))
        markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data='shop_main'))
        bot.edit_message_text("💍 <b>Категория: Обручальные Кольца</b>\n\nКупленное кольцо можно преподнести при предложении брака!", chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'shop_cat_pets':
        markup = InlineKeyboardMarkup()
        for p_id, p in PETS_DATA.items():
            markup.add(InlineKeyboardButton(f"{p['name']} ({p['price']} 🪙)", callback_data=f"buy_pet_{p_id}"))
        markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data='shop_main'))
        bot.edit_message_text("🐾 <b>Магазин Питомцев</b>", chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'buy_cert_custom_title':
        econ = get_user_econ(user_id, user_name)
        if econ.get('has_custom_title_cert', False):
            bot.answer_callback_query(call.id, '❌ Сертификат уже приобретен! Используйте /custom_title', show_alert=True)
            return
        if econ['balance'] < CUSTOM_TITLE_CERT_PRICE:
            bot.answer_callback_query(call.id, f'❌ Нужно {CUSTOM_TITLE_CERT_PRICE} 🪙!', show_alert=True)
            return
        econ['balance'] -= CUSTOM_TITLE_CERT_PRICE
        econ['has_custom_title_cert'] = True
        save_data()
        bot.answer_callback_query(call.id, '🎉 Сертификат куплен! Установите титул: /custom_title Ваш Титул', show_alert=True)

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
                'last_update': time.time()
            }
            save_data()
            bot.answer_callback_query(call.id, f"🎉 Вы завели питомца {p_data['name']}!", show_alert=True)

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
# ЗАПУСК БОТА
# ---------------------------------------------------------
setup_bot_commands()
restore_timers()
start_summer_music_thread()
keep_alive()

print('Бот успешно запущен...')
bot.infinity_polling()
