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
TOKEN = "8963495889:AAFFwRPYDVj1gqwz879G7HkZgpgXDoGt87g"
bot = telebot.TeleBot(TOKEN)

# ID вашего приватного канала для авто-бекапов
DB_CHANNEL_ID = int(os.environ.get('DB_CHANNEL_ID', '-1004334874700'))
# Отдельный канал для логов рестов, переводов и покупок.
LOG_CHANNEL_ID = int(os.environ.get('LOG_CHANNEL_ID', '-5587336891'))
DATA_FILE = 'rests_data.json'

# Юзернейм администратора/разработчика для секретного промокода
ADMIN_USERNAME = 'ukrgorilka'

# Прямые рабочие гифки на вопрос "почему" (отправляются анимацией)
WHY_GIFS = [
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3Z2eXpzc2ExOHBmbmdvZ3F0MHlyYm1sbTVrcHFqYm42aXFlZ3VwOSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/s239QJIh56sRW/giphy.gif",
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHlsMGVnZ29rNm0xb3JvdWRyc3dybDVrNTVrdXVnMzh0eWJ5dzdpNyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/1X7AZhiL08Y72/giphy.gif",
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbm9xYXgwcThicGlpazVkbzBmdW5kZnUwdmx1bmkyamc1MmpxNXRreSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/91fAVRO8nnF3a/giphy.gif"
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

# Доступные значки в магазине
BADGES = {
    'badge_star': {'name': 'Звездочка', 'emoji': '🌟', 'price': 100},
    'badge_dango': {'name': 'Данго', 'emoji': '🍡', 'price': 150},
    'badge_paw': {'name': 'Лапка Котика', 'emoji': '🐾', 'price': 200},
    'badge_heart': {'name': 'Сердечко', 'emoji': '💖', 'price': 200},
    'badge_fire': {'name': 'Огонек', 'emoji': '🔥', 'price': 250},
    'badge_lightning': {'name': 'Молния', 'emoji': '⚡️', 'price': 300},
    'badge_crown': {'name': 'Корона', 'emoji': '👑', 'price': 300},
    'badge_clover': {'name': 'Клевер', 'emoji': '🍀', 'price': 350},
    'badge_sakura': {'name': 'Сакура', 'emoji': '🌸', 'price': 400},
    'badge_diamond': {'name': 'Бриллиант', 'emoji': '💎', 'price': 500},
    'badge_skull': {'name': 'Череп', 'emoji': '💀', 'price': 600},
    'badge_rocket': {'name': 'Ракета', 'emoji': '🚀', 'price': 700},
    'badge_fox': {'name': 'Лисичка', 'emoji': '🦊', 'price': 800},
    'badge_alien': {'name': 'Инопланетянин', 'emoji': '👽', 'price': 900},
    'badge_unicorn': {'name': 'Единорог', 'emoji': '🦄', 'price': 1000},
    'badge_dragon': {'name': 'Дракон', 'emoji': '🐉', 'price': 1500},
    'badge_ghost': {'name': 'Призрак', 'emoji': '👻', 'price': 2000},
    'badge_foot': {'name': 'Пятка', 'emoji': '🦶', 'price': 3000},
}

# Кастомные титулы для профиля
TITLES = {
    'king': {'name': 'Кинг', 'text': '👑 Кинг', 'price': 2500},
    'sonya': {'name': 'Соня', 'text': '💤 Соня', 'price': 1800},
    'legend': {'name': 'Легенда', 'text': '🔥 Легенда', 'price': 3000},
    'dragon': {'name': 'Дракон', 'text': '🐉 Дракон', 'price': 3500},
    'bun': {'name': 'Булочка', 'text': '🥐 Булочка', 'price': 1500},
}

# ---------------------------------------------------------
# СИСТЕМА ПРОФЕССИЙ И ВАКАНСИЙ
# ---------------------------------------------------------
JOBS = {
    'fermer': {
        'name': '👨‍🌾 Фермер',
        'req_exp': 0,
        'chance': 95,
        'min_pay': 30,
        'max_pay': 70,
        'exp_gain': 10
    },
    'janitor': {
        'name': '🧹 Дворник',
        'req_exp': 0,
        'chance': 90,
        'min_pay': 40,
        'max_pay': 80,
        'exp_gain': 12
    },
    'courier': {
        'name': '🛵 Курьер',
        'req_exp': 50,
        'chance': 80,
        'min_pay': 90,
        'max_pay': 180,
        'exp_gain': 15
    },
    'cook': {
        'name': '👨‍🍳 Повар',
        'req_exp': 150,
        'chance': 70,
        'min_pay': 180,
        'max_pay': 350,
        'exp_gain': 20
    },
    'office': {
        'name': '👨‍💻 Офисный клерк',
        'req_exp': 350,
        'chance': 60,
        'min_pay': 350,
        'max_pay': 700,
        'exp_gain': 25
    },
    'programmer': {
        'name': '💻 Программист',
        'req_exp': 800,
        'chance': 45,
        'min_pay': 800,
        'max_pay': 1600,
        'exp_gain': 35
    },
    'boss': {
        'name': '💼 Бизнесмен',
        'req_exp': 1800,
        'chance': 30,
        'min_pay': 2000,
        'max_pay': 5000,
        'exp_gain': 50
    }
}

# ---------------------------------------------------------
# БЛОК РЫБАЛКИ, ОХОТЫ И ПИТОМЦЕВ
# ---------------------------------------------------------
FISH_TYPES = [
    ('🐟 Карась', 'Обычный', 15, 40),
    ('🐠 Окунь', 'Обычный', 25, 30),
    ('🐡 Щука', 'Редкий', 60, 15),
    ('🦀 Краб', 'Редкий', 90, 10),
    ('🐙 Осьминог', 'Эпический', 200, 4),
    ('🧜‍♀️ Русалка', 'Легендарный', 450, 2),
    ('🐉 Небесный Драконорыб', 'Мифический', 1000, 1),
]

HUNT_TYPES = [
    ('🐇 Заяц', 'Обычный', 20, 40),
    ('🦊 Лиса', 'Обычный', 35, 30),
    ('🐗 Кабан', 'Редкий', 75, 15),
    ('🦌 Олень', 'Редкий', 110, 10),
    ('🐅 Снежный Барс', 'Эпический', 250, 4),
    ('🦅 Феникс', 'Легендарный', 500, 2),
    ('🦄 Звездный Грифон', 'Мифический', 1200, 1),
]

PETS_DATA = {
    'cat': {
        'name': '🐱 Котик Усач',
        'price': 600,
        'luck_bonus': 15,
        'desc': '+15% к удаче в охоте и рыбалке'
    },
    'dog': {
        'name': '🐶 Пёсель Верный',
        'price': 1200,
        'luck_bonus': 25,
        'desc': '+25% к удаче в охоте и рыбалке'
    },
    'fox': {
        'name': '🦊 Хитрая Лисичка',
        'price': 2500,
        'luck_bonus': 40,
        'desc': '+40% к удаче в охоте и рыбалке'
    },
    'owl': {
        'name': '🦉 Мудрая Сова',
        'price': 4000,
        'luck_bonus': 60,
        'desc': '+60% к удаче в охоте и рыбалке'
    },
    'dragon': {
        'name': '🐉 Маленький Дракон',
        'price': 8000,
        'luck_bonus': 85,
        'desc': '+85% к удаче в охоте и рыбалке'
    }
}

# ---------------------------------------------------------
# БЛОК АЧИВОК (ДОСТИЖЕНИЙ)
# ---------------------------------------------------------
ACHIEVEMENTS = {
    'first_msg': {
        'title': '🌱 Первый шаг',
        'desc': 'Отправить первое сообщение в чате',
        'stat': 'messages',
        'target': 1,
        'reward': 50
    },
    'msg_100': {
        'title': '💬 Душа чата',
        'desc': 'Написать 100 сообщений',
        'stat': 'messages',
        'target': 100,
        'reward': 300
    },
    'msg_1000': {
        'title': '🗣 Легенда общения',
        'desc': 'Написать 1000 сообщений',
        'stat': 'messages',
        'target': 1000,
        'reward': 1500
    },
    'first_bonus': {
        'title': '🎁 Первые коины',
        'desc': 'Собрать свой первый часовой бонус',
        'stat': 'bonuses',
        'target': 1,
        'reward': 50
    },
    'bonus_50': {
        'title': '💎 Бонусный коллекционер',
        'desc': 'Собрать 50 часовых бонусов',
        'stat': 'bonuses',
        'target': 50,
        'reward': 1000
    },
    'first_fish': {
        'title': '🎣 Начинающий рыбак',
        'desc': 'Поймать свою первую рыбу',
        'stat': 'fish',
        'target': 1,
        'reward': 100
    },
    'fish_25': {
        'title': '🦈 Морской Волк',
        'desc': 'Поймать 25 рыб',
        'stat': 'fish',
        'target': 25,
        'reward': 800
    },
    'first_hunt': {
        'title': '🏹 Начинающий охотник',
        'desc': 'Сделать первый успешный выстрел на охоте',
        'stat': 'hunt',
        'target': 1,
        'reward': 100
    },
    'hunt_25': {
        'title': '🐅 Царь тайги',
        'desc': 'Сходить на охоту 25 раз',
        'stat': 'hunt',
        'target': 25,
        'reward': 800
    },
    'first_transfer': {
        'title': '🤝 Щедрая душа',
        'desc': 'Сделать первый перевод коинов другому пользователю',
        'stat': 'transfers',
        'target': 1,
        'reward': 150
    },
    'first_game': {
        'title': '🎲 Начинающий игрок',
        'desc': 'Сыграть 1 раз в любую азартную игру (кости/слоты/рулетка)',
        'stat': 'games',
        'target': 1,
        'reward': 100
    },
    'gamer_50': {
        'title': '🎰 Мастер азарта',
        'desc': 'Сыграть 50 раз в азартные игры',
        'stat': 'games',
        'target': 50,
        'reward': 1200
    },
    'first_rest': {
        'title': '🌴 Заслуженный отдых',
        'desc': 'Получить свой первый рест',
        'stat': 'rests',
        'target': 1,
        'reward': 200
    },
    'rich_1000': {
        'title': '💰 Богач',
        'desc': 'Накопить 1000 Ня-коинов на балансе',
        'stat': 'balance_check',
        'target': 1000,
        'reward': 500
    }
}

# Динамические ежедневные задания
DAILY_TASKS = {
    0: [
        ('messages', 'Написать 30 сообщений', 30, 80),
        ('transfer', 'Перевести коины другу', 1, 40),
        ('bonus', 'Собрать 2 часовых бонуса', 2, 60),
    ],
    1: [
        ('messages', 'Написать 40 сообщений', 40, 90),
        ('dice', 'Сыграть в кости 3 раза', 3, 70),
        ('fish', 'Поймать 1 рыбу', 1, 50),
    ],
    2: [
        ('messages', 'Написать 30 сообщений', 30, 80),
        ('slots', 'Испытать слоты 2 раза', 2, 60),
        ('iq', 'Измерить IQ', 1, 40),
    ],
    3: [
        ('messages', 'Написать 50 сообщений', 50, 110),
        ('transfer', 'Перевести коины другу', 1, 40),
        ('hunt', 'Сходить на охоту', 1, 60),
    ],
    4: [
        ('messages', 'Написать 35 сообщений', 35, 85),
        ('dice', 'Сыграть в кости 5 раз', 5, 100),
        ('fat', 'Измерить жир', 1, 40),
    ],
    5: [
        ('messages', 'Написать 45 сообщений', 45, 100),
        ('bonus', 'Собрать 3 часовых бонуса', 3, 90),
        ('fish', 'Поймать 2 рыбы', 2, 80),
    ],
    6: [
        ('messages', 'Написать 60 сообщений', 60, 130),
        ('roulette', 'Сыграть в рулетку 2 раза', 2, 80),
        ('hunt', 'Сходить на охоту 2 раза', 2, 100),
    ],
}

# Еженедельные задания
WEEKLY_TASKS = [
    ('messages', 'Написать 250 сообщений за неделю', 250, 300),
    ('fish', 'Поймать 10 рыб за неделю', 10, 250),
    ('hunt', 'Сходить на охоту 10 раз за неделю', 10, 250),
    ('bonus', 'Собрать 15 часовых бонусов', 15, 400),
    ('dice', 'Сыграть в кости 20 раз', 20, 350),
]

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

# --- МАТЫ И СЛОВО КОЧ ---
MUTABLE_BAD_WORDS_PATTERNS = {
    r'(коч|кочч|коча|кочу|кочем|кочи|koch|kochch)': [
        'Это плохо! 🛑',
        'Давай без таких слов! 🤫',
        'Осуждаю подобные речи 🤓☝️',
        'Давай лучше о чем-то хорошем! 🌸',
        'Не стоит такое писать 🛑',
        'Слово под запретом, смени тему! 🚫',
        'Фильтруй лексикон, дружище! 🧼',
        'Давай общаться культурно! 🎩',
        'Зачем употреблять такие слова? 🤔',
        'Минус вайб от этого слова 📉'
    ],
    r'(долбоеб|долбаеб|долбаёб|далбоеб|далбаеб|далбаёб|долбоёб|долбоящер|долбень|еблан|ебланище|ебланчик|ебнат|ебло|ебач|ебобо|ебанат|ебанько|долбо|долба|еблыга|dolboeb|dalboeb|eblan|ebnat|ebobo|ebanat)': [
        'Давай без личных оскорблений, дружище! 🤝⚠️',
        'А вот обижать людей нельзя! 🥺🚫',
        'Доброта спасет мир, а ты ругаешься 🌸🕊',
        'А сам-то идеальный? 😜',
        'Давай жить дружно! 🐱💬',
        'Словарный запас подкачал, давай культурнее! 📚',
        'Держи себя в руках, не переходи на личности! 🛑',
        'Стоп агрессия! Включаем вежливость 💡',
        'Лучше скажи человеку что-то приятное! 💐',
        'Оскорбления никого не красят 🙅‍♂️'
    ],
    r'(пездюк|пиздюк|пиздюки|пездюки|пиздюшонок|пездюшонок|пиздюга|пездюга)': [
        'Не обозывай мелких, сам таким был! 👶🍼',
        'Культура речи на нуле, выражайся вежливее! 🧼',
        'Ого, какие слова полетели! Попридержи коней 🐎',
        'Зачем же так грубо о людях? 🥺',
        'Фильтруй выражения, дружище! 🛑',
        'Не надо обидных кличек! 🤝',
        'Давай без этикеток и прозвищ! 🏷❌',
        'Словарный запас требует чистки! 🧹',
        'Будь добрее, и к тебе потянутся! 🌸',
        'Успокойся и скажи нормально! ☕️'
    ],
    r'(пидр|пидор|пидорас|пидарас|пидрила|пидорина|пидорасще|пидорок|pidr|pidor|pidaras|pidrila)': [
        'Давай без грубых оскорблений в чате! 🛑',
        'Язык твой — враг твой! Фильтруй базар 🧼',
        'За такие слова можно и в бан улететь! ✈️🔨',
        'Уважение к собеседнику вышло из чата... 🚶‍♂️',
        'Слишком много яда, остынь! 🧊',
        'Держи свои ругательства при себе! 🤫',
        'В приличном обществе так не выражаются! 🎩',
        'Меньше грубости, больше позитива! 🐝',
        'Агрессия ни к чему хорошему не приведет 🛑',
        'Переключаем волну на вежливое общение! 📻'
    ],
    r'(даун|даунич|дауненок|даунёнок|аутист|аутизм|дебил|дебилоид|имбецил|кретин|олигофрен|дауны|daun|debil|kretin|autist)': [
        'Не стоит диагнозами бросаться, будь добрее! 🧠❤️',
        'Уважение к собеседнику выходит из чата... 🚶‍♂️💔',
        'Давай без ярлыков и оскорблений! 🛑🤐',
        'Эрудиция на высоте, а вот вежливость подкачала 📉📚',
        'Кто обозвал, тот сам так называется! 😜✨',
        'Уважай других, и уважать будут тебя! 🤝',
        'Врачи в чате не согласны с твоим диагнозом! 🩺',
        'Давай общаться без обидных слов! 🕊',
        'Твои слова могут задеть человека, подумай! 💭',
        'Переключаем волну на позитив! 📻✨'
    ],
    r'(вахуе|вахуи|в\s*ахуе|в\s*ахуи|вахуии|вахуее)': [
        'Вот это поворот! Удивление зашкаливает 😲⚡️',
        'Челюсть на полу? Поднимай аккуратно! 🦷😱',
        'Шок — это по-нашему, но выражайся потише! 🤫',
        'Эмоции кипят, остуди чайник! ☕️💥',
        'Сам в шоке от твоих слов! 🤯',
        'Удивление принято, но давай без мата! 🛑',
        'Ничего себе новости! 🗞⚡️',
        'Да уж, ситуадочка действительно культурный шок! 🎭',
        'Взрыв мозга зафиксирован! 💣',
        'Спокойствие, только спокойствие! 🎈'
    ],
    r'(залупа|залупыш|залупоглаз|залупин|залупистый|залупка|залупь|zalupa|zalupish|zalupoglaz)': [
        'Ого, какие изысканные выражения из подворотни! 🏰💩',
        'Фильтруй базар, а то фильтр забьется! 🧼💥',
        'Давай общаться как цивилизованные люди! 🎩✨',
        'Фу такими словами кидаться, иди рот ополосни! 🚰🧼',
        'Минус 50 очков за дерзость! 🧙‍♂️🧹',
        'Словарь подворотни активирован? Отключай! 🔌',
        'Культурный уровень падаеееет! 📉',
        'Кажется, кто-то забыл правила приличного тона 📖',
        'Давай без физиологических подробностей! 🙈',
        'Изысканность речи оставляет желать лучшего 🥐'
    ],
    r'(сосать|соси|отсоси|соснуть|сосешь|сосёшь|сосиска|отсосино|всосать|присосался|sosas|sosi|otsosi|sosesh)': [
        'Сосать можно только чупа-чупс! 🍭😋',
        'Кажется, кому-то не хватает сладкого в жизни! 🍫🍬',
        'Рот свой держи на замке, а не предлагай глупости! 🤐🔑',
        'Детский сад, группа «Солнышко» объявляет тихий час! 👶💤',
        'Давай без этих взрослых фантазий! 🛑🙈',
        'Чупа-чупс клубничный или яблочный предпочитаешь? 🍏',
        'Предложение отклонено комиссией по этике! ❌',
        'Держи свои странные просьбы при себе 🤫',
        'А может лучше чаю попить? 🍵',
        'Возрастной рейтинг чата: 0+, соблюдай! 🔞❌'
    ],
    r'(трахнул|трахать|вытрахал|втрахал|трахни|трахну|вытрахать|затрахал|трах|трахаться|trax|traxat|vytraxat)': [
        'Трахать тут можно только мозги админу, но не советую! 🧠⚡️',
        'Какой грозный казанова нашелся! 🕶😏',
        'Попридержи коней, герой-любовник! 🐎🛑',
        'Режиссер, выключите у него взрослый канал! 📺❌',
        'Давай без пошлостей в общем чате! 🔞🚫',
        'Ох уж эти гиганты мысли и казановы 🤦‍♂️',
        'Позаботься лучше о делах, а не о фантазиях! 💼',
        'Охладите свой пыл, сэр! 🧊',
        'Романтик из подворотни на связи 🌹',
        'Перенаправляем энергию в полезные дела! 🚜'
    ],
    r'(шлюха|шлюшка|шлюховатый|проститутка|шалава|шмара|лярва|стерва|шлюхи|шалавa|shliux|shlyux|prostitutka|shalava|shmara)': [
        'Словарь негодяя активирован? Фильтруй базар! 🧼💥',
        'Уважение к людям вышло из чата... 🚶‍♂️💔',
        'Не смей так называть людей, уважай окружающих! 🙅‍♂️🔥',
        'За такие слова можно и в бан улететь! ✈️🔨',
        'Слишком много грязи, иди помойся! 🚿🧼',
        'Уважение к женскому полу — слышал о таком? 🌹',
        'Очень некрасивое слово, забудь его! 🛑',
        'Язык твой — враг твой! 👅⚔️',
        'Давай общаться без вульгарности! 🎩',
        'Фильтр грубости сработал на 100%! 🛡'
    ],
    r'(мудак|мудило|гандон|презерватив|уебок|уёбок|уебан|уебище|уёбище|выблядок|мразь|сука|сучара|сучка|mudak|gandon|uebok|uebishe|mraz|suka|suchara)': [
        'Уровень токсичности зашкаливает! ☣️😱',
        'Давай без тяжелой артиллерии и оскорблений! 💣🛑',
        'Столько желчи, чашечку чая для успокоения? 🍵🧘‍♂️',
        'Кто-то забыл принять таблетки от агрессии! 💊😉',
        'Культура речи на нуле, пересдача осенью! 📚❌',
        'Токсичность детектед! Снижаем градус! 🌡',
        'Злость уничтожает изнутри, будь добрее! 🕊',
        'Вдох-выдох... Успокаиваемся! 🧘‍♂️',
        'Меньше яда, больше позитива! 🍯',
        'Давай обойдемся без этих эпитетов! 🛑'
    ],
    r'(пизденыш|пиздёныш|говноед|засранец|падла|гад|чмо|хуесос|хуесосина|пизда|пиздец|пиздос|пиздей|пиздато|пиздеть|pizda|pizdec|chmo|xuyesos)': [
        'Ого, какие глубокие познания ругательств! 🧹😱',
        'Давай общаться как цивилизованные люди! 🎩✨',
        'Минус 50 очков за дерзость! 🧙‍♂️🧹',
        'За такие слова в приличном доме чаем не угощают! ☕️❌',
        'Фильтруй выражения, пока молчанку не дали! 🤐',
        'Фонтан эмоций зашкаливает! 🌊',
        'Словарный запас явно требует обряда очищения! 🧼',
        'Культура речи покинула этот диалог 📉',
        'Давай выражать эмоции более культурно! 🎨',
        'Стоп-слово активировано! 🛑'
    ],
    r'(\bбл\b|\bбль\b|блять|бля|блеать|блят|бляя|блятьь|блядь|блядина|blyat|blya|bleat|bliat)': [
        'Вообще-то матюкаться нельзя 🤓☝️',
        'Рот с мылом помыть? 🧼🤐',
        'За такое и в угол поставить могут! 📐👵',
        'Культурнее, пожалуйста, мы же в приличном обществе! 🎩✨',
        'Словарный запас покинул чат... 📉',
        'Блякать будете за пределами чата! 🚪',
        'Вставляй лучше красивые слова, а не бля! 🌸',
        'Упс, кто-то случайно сматерился! 🙊',
        'Мат вреден для вашего кармического баланса! ⚖️',
        'Сдерживай свои эмоции, дружище! 🥊'
    ],
    r'(нах|нахуй|похуй|нахуя|нахуйй|похую|нахрен|нафиг|nahuy|pohuy|nahui|pohui|nahren|nafig)': [
        'Маршрут перестроен: туда мы точно не идем 🗺❌',
        'GPS-навигатор отклонил ваш запрос! 🛑🧭',
        'Вектор движения выбран крайне некультурно! 📐🧭',
        'Фильтруй базар, а то фильтр забьется! 🧼💥',
        'Туда идти опасненько, оставайся с нами! 🏰',
        'Компас показывает направление к культуре! 🧭✨',
        'Не посылай людей, а то сам туда попадешь! 🔄',
        'Маршрут вреден для здоровья! ⚠️',
        'Давай без указывания странных направлений! 🛑',
        'Навигатор заблокирован за грубость! 🔒'
    ],
    r'(хуй|хуя|хуи|хуйня|хуево|заебись|хуета|хуевина|xuy|hui|xui|xue|xuya|xuynea)': [
        'Ого, какие мы громкие слова знаем! 📢🤯',
        'Словарь Даля нервно курит в сторонке... 📚🚬',
        'Давай переведём это на интеллигентный язык? 🎩📜',
        'Спокойствие, только спокойствие! 🎈',
        'Ой-ой-ой, какие слова полетели! 🦅',
        'Заменяем плохие слова на ромашки! 🌼',
        'Культурный переводчик отказывается это переводить! 🤖❌',
        'Давай помягче выражения подбирать! 🧸',
        'Языковой фильтр напрягся! ⚡️',
        'Тссс, не выражайся так громко! 🤫'
    ],
    r'(ахуеть|охуеть|охуел|ахуел|охуели|ахуели|охуевший|ахуевший|ебать|ебаться|ебаный|ёбаный|ебнутый|ебанутый|axuet|oxuet|ebat|ebany|ebnuty)': [
        'Энергию бы да в полезное русло! ⚡️🚜',
        'Не выражайся, а то клавиатура покраснеет! ⌨️😳',
        'Опять эмоциональный взрыв? 💥🤯',
        'Ты бы лучше так правила чата учил! 📖🤓',
        'Эмоции кипят, снизь температуру! 🌡',
        'Вау, вот это экспрессия! Но давай потише! 🤫',
        'Держи свои эмоции в узде! 🐎',
        'Переходи на интеллигентные восхищения! 🎭',
        'Взрыв эмоций зафиксирован! 💣',
        'Давай выражать удивление без мата! 😲✨'
    ]
}

pending_requests = {}
req_counter = 0

# ---------------------------------------------------------
# БЛОК РАБОТЫ С ДАННЫМИ (JSON + TELEGRAM BACKUP)
# ---------------------------------------------------------
def load_data():
    """Загружает свежий бекап из Telegram-канала, если локальный файл отсутствует или устарел"""
    data = {'rests': {}, 'history': {}, 'settings': {}, 'economy': {}, 'promos': {}}
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
                if 'settings' not in data: data['settings'] = {}
                if 'rests' not in data: data['rests'] = {}
                if 'history' not in data: data['history'] = {}
                if 'economy' not in data: data['economy'] = {}
                if 'promos' not in data: data['promos'] = {}
                return data
        except Exception as e:
            print(f'Ошибка чтения файла: {e}')

    return data

def save_data(send_backup=True):
    """Сохраняет JSON локально и при необходимости отправляет бекап в Telegram."""
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
    """Регистрирует список команд бота в Telegram для кнопки '/'"""
    commands = [
        BotCommand('profile', '👤 Ваш профиль и инвентарь'),
        BotCommand('work', '💼 Работа и вакансии'),
        BotCommand('pet', '🐾 Ваш питомец и уход'),
        BotCommand('sell', '💰 Продать улов и трофеи'),
        BotCommand('achievements', '🏆 Ваши достижения и награды'),
        BotCommand('balance', '💵 Проверить баланс коинов'),
        BotCommand('bonus', '🎁 Ежечасовой бонус коинов'),
        BotCommand('shop', '🏪 Магазин (пассы, значки, питомцы)'),
        BotCommand('tasks', '📋 Ежедневные и недельные задания'),
        BotCommand('fish', '🎣 Пойти на рыбалку'),
        BotCommand('hunt', '🏹 Пойти на охоту'),
        BotCommand('dice', '🎲 Сыграть в кости'),
        BotCommand('slots', '🎰 Сыграть в слоты'),
        BotCommand('roulette', '🎡 Сыграть в рулетку'),
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
    return user_str.replace('@', '').strip()

def clean_junk_rests():
    """Удаляет сбойные/тестовые ресты из базы данных."""
    changed = False
    for str_chat in list(db.get('rests', {}).keys()):
        for user_key in list(db['rests'][str_chat].keys()):
            if user_key == '8' or user_key.isdigit() or clean_tag(user_key).lower() == 'тест':
                del db['rests'][str_chat][user_key]
                changed = True
    if changed:
        save_data()

clean_junk_rests()

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

# --- ОБЩАЯ ГЛОБАЛЬНАЯ ЭКОНОМИКА (Единая для ЛС и всех групп) ---
def get_global_user_key(user_id=None, user_tag=None):
    if user_id:
        return f"id_{user_id}"
    if user_tag:
        return f"tag_{clean_tag(user_tag).lower()}"
    return "unknown_user"

def update_pet_stats(pet):
    """Обновляет параметры сытости и чистоты питомца со временем."""
    if not pet:
        return
    now = time.time()
    last_update = pet.get('last_update', now)
    hours_passed = (now - last_update) / 3600.0

    if hours_passed > 0.1:
        # Питомец теряет 5% сытости и 4% чистоты в час
        pet['hunger'] = max(0, pet.get('hunger', 100) - int(hours_passed * 5))
        pet['cleanliness'] = max(0, pet.get('cleanliness', 100) - int(hours_passed * 4))
        pet['last_update'] = now

def get_user_econ(user_id=None, user_tag=None):
    if 'economy' not in db:
        db['economy'] = {}
    
    key = get_global_user_key(user_id, user_tag)
    
    if key not in db['economy']:
        db['economy'][key] = {
            'display_name': clean_tag(user_tag) if user_tag else 'Пользователь',
            'user_id': user_id,
            'balance': 50,           # Стартовый баланс
            'smeh': 0,               # Очки смехуятинки
            'iq': 100,               # Уровень IQ
            'fat': 20,               # Процент жира
            'foot_size': 25,         # Размер пятки в см
            'last_hourly': 0,        # Timestamp последнего часового сбора
            'last_iq_time': 0,       # Timestamp последнего измерения IQ (КД 30 мин)
            'last_fat_time': 0,      # Timestamp последнего измерения жира (КД 30 мин)
            'last_foot_time': 0,     # Timestamp последнего измерения пятки (КД 20 мин)
            'nya_pass_until': 0,     # Timestamp окончания действия Ня-Пасса
            'nya_pass_enabled': True,# Включен ли Ня-Пасс владельцем
            'badge': None,           # Активный значок
            'inventory': [],         # Список купленных значков
            'titles': [],             # Купленные кастомные титулы
            'active_title': None,     # Выбранный титул
            'daily_tasks_date': '',    # Дата текущих ежедневных заданий
            'daily_progress': {},      # Прогресс ежедневных заданий
            'daily_claimed': [],       # Уже оплаченные задания за день
            'weekly_tasks_yearweek': '', # Год и неделя для еженедельных заданий
            'weekly_progress': {},     # Прогресс недельных заданий
            'weekly_claimed': [],      # Оплаченные недельные задания
            'fish_inventory': {},      # Инвентарь рыбы
            'hunt_inventory': {},      # Инвентарь охотничьих трофеев
            'last_fish_time': 0,       # КД рыбалки 2 часа
            'last_hunt_time': 0,       # КД охоты 2 часа
            'rest_rewards_count': 0,   # Счетчик выданных 150 коинов (макс 5 навсегда)
            'achievements': [],        # Список разблокированных ачивок (ID)
            'stats': {},               # Глобальная статистика аккаунта
            'work_exp': 0,             # Опыт работы
            'last_work_time': 0,       # КД работы
            'pet': None                # Данные питомца
        }
        save_data()

    u_data = db['economy'][key]
    if user_tag:
        u_data['display_name'] = clean_tag(user_tag)
    if user_id:
        u_data['user_id'] = user_id

    # Гарантируем наличие всех ключей для старых аккаунтов
    if 'inventory' not in u_data: u_data['inventory'] = []
    if 'nya_pass_enabled' not in u_data: u_data['nya_pass_enabled'] = True
    if 'smeh' not in u_data: u_data['smeh'] = 0
    if 'iq' not in u_data: u_data['iq'] = 100
    if 'fat' not in u_data: u_data['fat'] = 20
    if 'foot_size' not in u_data: u_data['foot_size'] = 25
    if 'rest_rewards_count' not in u_data: u_data['rest_rewards_count'] = 0
    if 'titles' not in u_data: u_data['titles'] = []
    if 'active_title' not in u_data: u_data['active_title'] = None
    if 'daily_tasks_date' not in u_data: u_data['daily_tasks_date'] = ''
    if 'daily_progress' not in u_data: u_data['daily_progress'] = {}
    if 'daily_claimed' not in u_data: u_data['daily_claimed'] = []
    if 'weekly_tasks_yearweek' not in u_data: u_data['weekly_tasks_yearweek'] = ''
    if 'weekly_progress' not in u_data: u_data['weekly_progress'] = {}
    if 'weekly_claimed' not in u_data: u_data['weekly_claimed'] = []
    if 'fish_inventory' not in u_data: u_data['fish_inventory'] = {}
    if 'hunt_inventory' not in u_data: u_data['hunt_inventory'] = {}
    if 'last_fish_time' not in u_data: u_data['last_fish_time'] = 0
    if 'last_hunt_time' not in u_data: u_data['last_hunt_time'] = 0
    if 'achievements' not in u_data: u_data['achievements'] = []
    if 'stats' not in u_data: u_data['stats'] = {}
    if 'work_exp' not in u_data: u_data['work_exp'] = 0
    if 'last_work_time' not in u_data: u_data['last_work_time'] = 0
    if 'pet' not in u_data: u_data['pet'] = None

    if u_data.get('pet'):
        update_pet_stats(u_data['pet'])

    return u_data

def add_coins(user_id=None, user_tag=None, amount=0):
    user_data = get_user_econ(user_id, user_tag)
    user_data['balance'] += amount
    save_data()
    check_achievements(user_id, user_tag, 'balance_check', 0)
    return user_data['balance']

def is_nya_pass_active(user_id=None, user_tag=None):
    user_data = get_user_econ(user_id, user_tag)
    until = user_data.get('nya_pass_until', 0)
    enabled = user_data.get('nya_pass_enabled', True)
    return enabled and (time.time() < until)

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
                    f"💰 Награда: <b>+{reward} Ня-коинов 🪙</b>"
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
    
    # Трекаем общую статистику аккаунта для ачивок
    check_achievements(user_id, user_tag, task_key, amount, chat_id)

    # 1. Ежедневные задания
    tasks, econ = get_daily_tasks(user_id, user_tag)
    progress = econ.setdefault('daily_progress', {})
    progress[task_key] = progress.get(task_key, 0) + amount

    for key, description, target, reward in tasks:
        if key not in econ.get('daily_claimed', []) and progress.get(key, 0) >= target:
            econ.setdefault('daily_claimed', []).append(key)
            econ['balance'] += reward
            completed.append((f"Ежедневное: {description}", reward))

    # 2. Еженедельные задания
    w_tasks, _ = get_weekly_tasks(user_id, user_tag)
    w_progress = econ.setdefault('weekly_progress', {})
    w_progress[task_key] = w_progress.get(task_key, 0) + amount

    for key, description, target, reward in w_tasks:
        if key not in econ.get('weekly_claimed', []) and w_progress.get(key, 0) >= target:
            econ.setdefault('weekly_claimed', []).append(key)
            econ['balance'] += reward
            completed.append((f"Еженедельное: {description}", reward))

    save_data(send_backup=False)
    return completed

def format_daily_tasks(user_id, user_tag):
    tasks, econ = get_daily_tasks(user_id, user_tag)
    w_tasks, _ = get_weekly_tasks(user_id, user_tag)
    weekdays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    
    lines = [f'📋 <b>Задания и Квесты — {weekdays[datetime.now().weekday()]}</b>', '']
    lines.append('🌟 <i>Все задания доступны каждому участнику!</i>\n')
    
    lines.append('☀️ <b>Ежедневные задания:</b>')
    for key, description, target, reward in tasks:
        current = min(econ.get('daily_progress', {}).get(key, 0), target)
        done = key in econ.get('daily_claimed', [])
        status = '✅' if done else '🔄'
        lines.append(f'{status} {description}: <b>{current}/{target}</b> (Награда: <b>+{reward} 🪙</b>)')
        
    lines.append('\n📅 <b>Еженедельные задания (Обновляются каждый понедельник):</b>')
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

# ---------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ПАРСИНГА И ССЫЛОК
# ---------------------------------------------------------
def normalize_text_for_bad_words(text):
    text = text.lower()
    replacements = {
        'a': 'а', 'b': 'б', 'c': 'с', 'e': 'е', 'k': 'к', 
        'm': 'м', 'o': 'о', 'p': 'р', 't': 'т', 'x': 'х', 
        'y': 'у', 'u': 'у', 'i': 'и', 'g': 'г', 'h': 'х'
    }
    for en, ru in replacements.items():
        text = text.replace(en, ru)
    clean_text = re.sub(r'[\.\*_\-\+\/\&%\$\#@!\s\d]+', '', text)
    return clean_text

_USERNAME_CACHE = {}

def has_public_username(user_id):
    if not user_id:
        return False
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return False
    if user_id in _USERNAME_CACHE:
        return _USERNAME_CACHE[user_id]
    try:
        chat = bot.get_chat(user_id)
        result = bool(getattr(chat, 'username', None))
    except Exception:
        result = False
    _USERNAME_CACHE[user_id] = result
    return result

def make_link(chat_id, user_name, user_id=None, ping=True):
    name = clean_tag(user_name)
    badge_str = ""
    title_str = ""
    user_econ = get_user_econ(user_id, user_name)
    if user_econ.get('badge'):
        badge_str = f" [{user_econ['badge']}]"
    active_title = user_econ.get('active_title')
    if active_title in TITLES:
        title_str = f" [{TITLES[active_title]['text']}]"

    if not ping:
        return f'<b>{name}</b>{badge_str}{title_str}'

    if user_id and has_public_username(user_id):
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

def find_known_user_id(chat_id, user_name):
    clean_name = clean_tag(user_name).lower()
    str_chat = str(chat_id)

    for tag, info in db.get('rests', {}).get(str_chat, {}).items():
        if clean_tag(tag).lower() == clean_name and info.get('user_id'):
            return info.get('user_id')

    for info in db.get('economy', {}).values():
        if clean_tag(info.get('display_name', '')).lower() == clean_name and info.get('user_id'):
            return info.get('user_id')

    for tag, items in db.get('history', {}).get(str_chat, {}).items():
        if clean_tag(tag).lower() == clean_name:
            for item in reversed(items):
                if item.get('user_id'):
                    return item.get('user_id')
    return None

def parse_target_and_args(message, cmd_prefix):
    text = message.text.strip() if message.text else ''
    target_user = None
    target_user_id = None
    raw_args = ''

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

    m_tag = re.search(r'@(\w+)', body)
    if m_tag:
        target_user = clean_tag(m_tag.group(1))
        raw_args = body.replace(m_tag.group(0), '').strip()
        target_user_id = find_known_user_id(message.chat.id, target_user)
        return target_user, target_user_id, raw_args

    if '|' in body:
        parts = body.split('|')
        potential_name = parts[-1].strip()
        if not re.search(r'\d', potential_name) and len(potential_name.split()) == 1:
            target_user = clean_tag(potential_name)
            raw_args = '|'.join(parts[:-1]).strip()
            target_user_id = find_known_user_id(message.chat.id, target_user)
            return target_user, target_user_id, raw_args

    words = body.split()
    if len(words) > 1:
        if text.lower():
            if re.match(r'^\+рест\s+', text, re.IGNORECASE):
                m_rest_name = re.match(r'^\+рест\s+([^|\s]+)\s+(.+)$', text, re.IGNORECASE)
                if m_rest_name:
                    candidate = clean_tag(m_rest_name.group(1))
                    rest_args = m_rest_name.group(2).strip()
                    if candidate and not candidate.startswith(('до', 'на')):
                        target_user = candidate
                        target_user_id = find_known_user_id(message.chat.id, target_user)
                        return target_user, target_user_id, rest_args

        if not re.search(r'\d', words[-1]):
            target_user = clean_tag(words[-1])
            raw_args = ' '.join(words[:-1]).strip()
            target_user_id = find_known_user_id(message.chat.id, target_user)
            return target_user, target_user_id, raw_args

    return None, None, body

def parse_duration_to_seconds(duration_str, chat_id=None):
    duration_str = duration_str.lower().strip()

    indefinite_markers = (
        'на неопределённый срок', 'на неопределенный срок',
        'неопределённый срок', 'неопределенный срок',
        'бессрочно', 'без срока', 'навсегда'
    )
    if any(marker in duration_str for marker in indefinite_markers):
        return None

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
        user_link = make_link(chat_id, clean_user, target_user_id, ping=True)
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
    
    if clean_user == '8' or clean_user.isdigit():
        return False, 0
        
    seconds = parse_duration_to_seconds(duration_text, chat_id)
    is_indefinite = any(marker in duration_text.lower() for marker in (
        'на неопределённый срок', 'на неопределенный срок',
        'неопределённый срок', 'неопределенный срок',
        'бессрочно', 'без срока', 'навсегда'
    ))
    end_time = (time.time() + seconds) if seconds else None
    display_duration = 'на неопределённый срок' if is_indefinite else duration_text
    db['rests'][str_chat][clean_user] = {
        'duration': display_duration,
        'reason': reason,
        'end_time': end_time,
        'user_id': target_user_id,
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
        schedule_rest_timers(chat_id, clean_user, end_time, target_user_id)
        
    return reward_given, econ['rest_rewards_count']

# ---------------------------------------------------------
# ПРИВЕТСТВИЕ И ПРОЩАНИЕ
# ---------------------------------------------------------
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_members(message):
    for member in message.new_chat_members:
        user_link = make_link(message.chat.id, member.username or member.first_name, member.id, ping=True)
        add_coins(member.id, member.username or member.first_name, 50)
        
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
    user_link = make_link(message.chat.id, member.username or member.first_name, member.id, ping=False)
    farewell_text = f"👋 <b>{user_link}</b> покинул(а) наш чат. Пожелаем удачи! 🌸"
    bot.send_message(message.chat.id, farewell_text, parse_mode='HTML')

# ---------------------------------------------------------
# ОБРАБОТЧИКИ КОМАНД И ПОЛНОЕ ОПИСАНИЕ БОТА
# ---------------------------------------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    help_text = (
        '🤖 <b>НЯ-БОТ — ПОЛНЫЙ СПИСОК ВОЗМОЖНОСТЕЙ</b>\n\n'
        '💼 <b>РАБОТА И КАРЬЕРА</b>\n'
        '• <code>/work</code> / <code>работа</code> — выбор вакансии и работа. Получайте опыт и зарплату!\n\n'
        '🐾 <b>ПИТОМЦЫ И УХОД</b>\n'
        '• <code>/pet</code> / <code>питомец</code> — статус и уход за питомцем.\n'
        '• <code>/pet_shop</code> — магазин питомцев.\n'
        '• <code>/feed</code>, <code>/wash</code> — покормить и помыть питомца.\n\n'
        '🎣 <b>РЫБАЛКА, ОХОТА И ПРОДАЖА</b>\n'
        '• <code>/fish</code> / <code>рыбалка</code> — поймать рыбу (КД 2 часа).\n'
        '• <code>/hunt</code> / <code>охота</code> — добыть трофей (КД 2 часа).\n'
        '• <code>/sell</code> / <code>продать</code> — продать всю добычу за коины.\n\n'
        '🌴 <b>РЕСТЫ</b>\n'
        '• <code>+рест 3 дня | отпуск @username</code> — выдать рест.\n'
        '• <code>+рест @username на неопределённый срок</code> — бессрочный рест.\n'
        '• <code>-рест @username</code> — снять рест.\n'
        '• <code>+продлить 2 часа @username</code> — продлить рест.\n'
        '• <code>причина @username новая причина</code> — изменить причину.\n'
        '• <code>запрос рест 3 дня | причина</code> — отправить запрос админу.\n'
        '• <code>кто @username</code> — проверить рест.\n'
        '• <code>ресты</code> — активные ресты.\n'
        '• <code>мой рест</code> — информация о вашем ресте.\n'
        '• <code>топ</code> / <code>статистика</code> — статистика рестов.\n\n'
        '💰 <b>НЯ-КОИНЫ И ПРОФИЛЬ</b>\n'
        '• <code>/bonus</code> / <code>бонус</code> — раз в час 1-100 коинов.\n'
        '• <code>/balance</code> / <code>баланс</code> — ваш баланс.\n'
        '• <code>/profile</code> / <code>профиль</code> — профиль, инвентарь и статус питомца.\n'
        '• <code>/achievements</code> / <code>ачивки</code> — ваши достижения.\n'
        '• <code>передать 100</code> (ответом) или <code>/pay @username 100</code> — перевести коины.\n'
        '• <code>/promo КОД</code> — активировать промокод.\n\n'
        '🎰 <b>АЗАРТНЫЕ ИГРЫ</b>\n'
        '• <code>/dice 100</code>, <code>/slots 100</code>, <code>/roulette 100</code>.\n\n'
        '🧠 <b>РАЗВЛЕЧЕНИЯ И СТАТИСТИКА</b>\n'
        '• <code>/iq</code>, <code>/fat</code>, <code>/foot</code> — симуляторы.\n'
        '• <code>/top</code> — рейтинги игроков.\n\n'
        '🏪 <b>МАГАЗИН</b>\n'
        '• <code>/shop</code> — магазин значков, пассов, титулов и питомцев.\n\n'
        '⚙️ <b>ДЛЯ АДМИНОВ</b>\n'
        '• <code>/settings</code> — настройки чата.\n'
        '• <code>/export</code> — экспорт рестов в CSV.\n'
        '• <code>отчет</code> / <code>логи</code> — аналитика.\n'
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

# --- МЕНЮ ПРОФИЛЯ, ИНВЕНТАРЯ И НАСТРОЕК ---
def send_user_profile(chat_id, user_tag, user_id, message_to_reply=None):
    econ = get_user_econ(user_id, user_tag)
    markup = InlineKeyboardMarkup()
    
    pass_enabled = econ.get('nya_pass_enabled', True)
    pass_status_text = "❌ Отсутствует"
    purchased_titles = econ.get('titles', [])
    
    if purchased_titles:
        title_row = []
        for title_key in purchased_titles:
            if title_key in TITLES:
                title_row.append(InlineKeyboardButton(f"Надеть {TITLES[title_key]['text']}", callback_data=f"set_title_{title_key}"))
                if len(title_row) == 2:
                    markup.add(*title_row)
                    title_row = []
        if title_row:
            markup.add(*title_row)
        markup.add(InlineKeyboardButton('❌ Снять титул', callback_data='remove_title'))

    if time.time() < econ.get('nya_pass_until', 0):
        rem_sec = int(econ['nya_pass_until'] - time.time())
        days = rem_sec // 86400
        hours = (rem_sec % 86400) // 3600
        time_left = f"{days}д {hours}ч"
        if pass_enabled:
            pass_status_text = f"✅ Активен (Осталось: {time_left})"
        else:
            pass_status_text = f"⏸ Отключен вручную (Осталось: {time_left})"

    current_badge = econ.get('badge') or "Отсутствует"
    current_title = TITLES.get(econ.get('active_title'), {}).get('text', 'Отсутствует')
    inv = econ.get('inventory', [])
    inv_str = " ".join(inv) if inv else "Пусто (купите значки в магазине)"
    
    fish_inv = ', '.join(f'{name} × {count}' for name, count in econ.get('fish_inventory', {}).items()) or 'Пусто'
    hunt_inv = ', '.join(f'{name} × {count}' for name, count in econ.get('hunt_inventory', {}).items()) or 'Пусто'
    
    pet_info = "Отсутствует (Купите в <code>/pet_shop</code>)"
    if econ.get('pet'):
        p = econ['pet']
        pet_info = f"{p['name']} (🍖 Сытость: {p['hunger']}%, 🧼 Чистота: {p['cleanliness']}%)"

    unlocked_ach = len(econ.get('achievements', []))
    total_ach = len(ACHIEVEMENTS)

    rest_rewards = econ.get('rest_rewards_count', 0)
    rest_rewards_str = f"{rest_rewards}/5 (150 🪙)" if rest_rewards < 5 else "5/5 (Лимит бонусов исчерпан ⛔️)"

    text = (
        f"🌐 <b>Единый Профиль: {make_link(chat_id, user_tag, user_id, ping=False)}</b>\n"
        f"<i>(Статистика синхронизирована во всех чатах и ЛС)</i>\n\n"
        f"💵 Баланс: <b>{econ['balance']} Ня-коинов 💸</b>\n"
        f"💼 Опыт работы: <b>{econ.get('work_exp', 0)} EXP</b>\n"
        f"🐾 Питомец: <b>{pet_info}</b>\n"
        f"🏆 Достижения: <b>{unlocked_ach}/{total_ach} (Команда: /achievements)</b>\n"
        f"😂 Смехуятинка: <b>{econ.get('smeh', 0)} балл(ов)</b>\n"
        f"🧠 Айкью (IQ): <b>{econ.get('iq', 100)}</b>\n"
        f"🍔 Процент жира: <b>{econ.get('fat', 20)}%</b>\n"
        f"🦶 Размер пятки: <b>{econ.get('foot_size', 25)} см</b>\n"
        f"🎁 Награды за ресты: <b>{rest_rewards_str}</b>\n"
        f"🏷 Активный значок: <b>{current_badge}</b>\n"
        f"👑 Активный титул: <b>{current_title}</b>\n"
        f"🎒 Значки: {inv_str}\n"
        f"🐟 Рыболовный инвентарь: {fish_inv}\n"
        f"🏹 Охотничий инвентарь: {hunt_inv}\n"
        f"🎟 Ня-Пасс от мата: <b>{pass_status_text}</b>"
    )

    if inv:
        row = []
        for emoji in inv:
            row.append(InlineKeyboardButton(f"Надеть {emoji}", callback_data=f"set_badge_{emoji}"))
            if len(row) == 3:
                markup.add(*row)
                row = []
        if row:
            markup.add(*row)
        markup.add(InlineKeyboardButton("❌ Снять значок", callback_data="remove_badge"))

    if time.time() < econ.get('nya_pass_until', 0):
        btn_text = "⏸ Выключить Ня-Пасс" if pass_enabled else "▶️ Включить Ня-Пасс"
        markup.add(InlineKeyboardButton(btn_text, callback_data="toggle_nya_pass"))

    if message_to_reply:
        bot.reply_to(message_to_reply, text, reply_markup=markup, parse_mode='HTML')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

# --- ВЫЗОВ МАГАЗИНА С КАТЕГОРИЯМИ ---
def send_shop_menu(chat_id, user_id, user_tag, message_id=None):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton('🎟 Пассы', callback_data='shop_cat_passes'))
    markup.add(InlineKeyboardButton('✨ Значки и смайлы', callback_data='shop_cat_badges'))
    markup.add(InlineKeyboardButton('👑 Титулы', callback_data='shop_cat_titles'))
    markup.add(InlineKeyboardButton('🐾 Магазин Питомцев', callback_data='shop_cat_pets'))

    text = "🏪 <b>Глобальный Магазин Ня-коинов:</b>\n\nВыберите интересующую вас категорию:"
    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

# ---------------------------------------------------------
# ОБРАБОТЧИКИ КОМАНД СИСТЕМЫ РАБОТЫ И ПИТОМЦЕВ
# ---------------------------------------------------------

@bot.message_handler(commands=['work', 'работа'])
def cmd_work(message):
    user_tag = clean_tag(message.from_user.username or message.from_user.first_name)
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_tag)
    
    markup = InlineKeyboardMarkup()
    for job_id, job in JOBS.items():
        btn_text = f"{job['name']} (Нужно: {job['req_exp']} EXP)"
        markup.add(InlineKeyboardButton(btn_text, callback_data=f"do_job_{job_id}"))

    text = (
        f"💼 <b>Биржа Труда и Вакансий</b>\n\n"
        f"👤 Ваш текущий опыт работы: <b>{econ.get('work_exp', 0)} EXP</b>\n\n"
        f"📌 Чем выше уровень работы, тем больше зарплата, но <b>ниже шанс успешного выполнения</b>.\n"
        f"Выберите профессию для работы:"
    )
    bot.reply_to(message, text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['pet', 'питомец'])
def cmd_pet(message):
    user_tag = clean_tag(message.from_user.username or message.from_user.first_name)
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_tag)
    pet = econ.get('pet')

    if not pet:
        bot.reply_to(
            message,
            "❌ У вас еще нет питомца!\nКупите себе питомца в магазине: <code>/pet_shop</code> или <code>/shop</code>.",
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

    status_luck = "✅ Бонус к удаче активен!" if pet['hunger'] >= 30 and pet['cleanliness'] >= 30 else "⚠️ Питомец голоден или грязный! Бонус временно не работает."

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
    user_tag = clean_tag(message.from_user.username or message.from_user.first_name)
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_tag)
    pet = econ.get('pet')

    if not pet:
        bot.reply_to(message, "❌ У вас нет питомца!")
        return

    if econ['balance'] < 20:
        bot.reply_to(message, "❌ На еду питомцу нужно 20 Ня-коинов!")
        return

    econ['balance'] -= 20
    pet['hunger'] = min(100, pet.get('hunger', 100) + 40)
    save_data()
    bot.reply_to(message, f"🍖 Вы вкусно покормили {pet['name']}! Сытость: <b>{pet['hunger']}%</b>", parse_mode='HTML')

@bot.message_handler(commands=['wash', 'помыть'])
def cmd_wash(message):
    user_tag = clean_tag(message.from_user.username or message.from_user.first_name)
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_tag)
    pet = econ.get('pet')

    if not pet:
        bot.reply_to(message, "❌ У вас нет питомца!")
        return

    if econ['balance'] < 15:
        bot.reply_to(message, "❌ На шампунь нужно 15 Ня-коинов!")
        return

    econ['balance'] -= 15
    pet['cleanliness'] = min(100, pet.get('cleanliness', 100) + 50)
    save_data()
    bot.reply_to(message, f"🧼 Вы искупали {pet['name']}! Чистота: <b>{pet['cleanliness']}%</b>", parse_mode='HTML')

@bot.message_handler(commands=['sell', 'продать'])
def cmd_sell(message):
    user_tag = clean_tag(message.from_user.username or message.from_user.first_name)
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_tag)
    
    total_earned = 0
    items_sold = 0

    # Продажа рыбы
    for fish_name, count in list(econ.get('fish_inventory', {}).items()):
        price = 20
        for f_item in FISH_TYPES:
            if f_item[0] == fish_name:
                price = f_item[2]
                break
        total_earned += price * count
        items_sold += count
    econ['fish_inventory'] = {}

    # Продажа трофеев
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
    bot.reply_to(
        message,
        f"💰 Вы успешно продали улов и трофеи (всего предметов: {items_sold}) на сумму <b>+{total_earned} Ня-коинов 🪙</b>!\n"
        f"Ваш баланс: <b>{econ['balance']} 🪙</b>",
        parse_mode='HTML'
    )

# --- ОБРАБОТКА ДРУГИХ КОМАНД ---
@bot.message_handler(commands=['profile'])
def cmd_profile(message):
    user_tag = clean_tag(message.from_user.username or message.from_user.first_name)
    send_user_profile(message.chat.id, user_tag, message.from_user.id, message)

@bot.message_handler(commands=['achievements', 'ачивки'])
def cmd_achievements(message):
    user_tag = clean_tag(message.from_user.username or message.from_user.first_name)
    user_id = message.from_user.id
    econ = get_user_econ(user_id, user_tag)
    unlocked = econ.get('achievements', [])

    lines = [f"🏆 <b>Достижения пользователя {make_link(message.chat.id, user_tag, user_id, ping=False)}:</b>\n"]
    
    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id in unlocked:
            lines.append(f"✅ <b>{ach['title']}</b> — {ach['desc']} (Получено +{ach['reward']} 🪙)")
        else:
            lines.append(f"🔒 <b>{ach['title']}</b> — {ach['desc']} (Награда: <b>+{ach['reward']} 🪙</b>)")

    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')

@bot.message_handler(commands=['balance'])
def cmd_balance(message):
    user_tag = clean_tag(message.from_user.username or message.from_user.first_name)
    econ = get_user_econ(message.from_user.id, user_tag)
    bot.reply_to(
        message,
        f"💵 <b>Ваш кошелек {make_link(message.chat.id, user_tag, message.from_user.id, ping=False)}:</b>\n"
        f"• Баланс: <b>{econ['balance']} Ня-коинов 💸</b>",
        parse_mode='HTML'
    )

@bot.message_handler(commands=['shop', 'pet_shop'])
def cmd_shop(message):
    user_tag = clean_tag(message.from_user.username or message.from_user.first_name)
    send_shop_menu(message.chat.id, message.from_user.id, user_tag)

@bot.message_handler(commands=['tasks'])
def cmd_tasks(message):
    user_tag = clean_tag(message.from_user.username or message.from_user.first_name)
    bot.reply_to(message, format_daily_tasks(message.from_user.id, user_tag), parse_mode='HTML')

@bot.message_handler(commands=['iq'])
def cmd_iq(message):
    user_tag = clean_tag(message.from_user.username or message.from_user.first_name)
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_tag)
    now_ts = time.time()
    cooldown = 1800
    
    if now_ts - econ.get('last_iq_time', 0) < cooldown:
        left_sec = int(cooldown - (now_ts - econ.get('last_iq_time', 0)))
        minutes = left_sec // 60
        seconds = left_sec % 60
        bot.reply_to(message, f"⏳ Тест на IQ можно проходить раз в 30 минут!\nПодождите еще: <b>{minutes} мин {seconds} сек</b>.", parse_mode='HTML')
        return

    change = random.randint(-5, 15)
    econ['iq'] = max(0, econ.get('iq', 100) + change)
    econ['last_iq_time'] = now_ts
    save_data()
    completed = track_daily_task(user_id, user_tag, 'iq', 1, chat_id)
    
    sign = "+" if change >= 0 else ""
    bot.reply_to(message, f"🧠 {make_link(chat_id, user_tag, user_id, ping=True)}, ваш тест на IQ завершен!\nИзменение: <b>{sign}{change} IQ</b>\nТекущий уровень интеллекта: <b>{econ['iq']} IQ 📊</b>", parse_mode='HTML')
    for task_name, task_reward in completed:
        bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')

@bot.message_handler(commands=['fat'])
def cmd_fat(message):
    user_tag = clean_tag(message.from_user.username or message.from_user.first_name)
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_tag)
    now_ts = time.time()
    cooldown = 1800
    
    if now_ts - econ.get('last_fat_time', 0) < cooldown:
        left_sec = int(cooldown - (now_ts - econ.get('last_fat_time', 0)))
        minutes = left_sec // 60
        seconds = left_sec % 60
        bot.reply_to(message, f"⏳ Замер жира можно проводить раз в 30 минут!\nПодождите еще: <b>{minutes} мин {seconds} сек</b>.", parse_mode='HTML')
        return

    change = random.randint(-4, 6)
    econ['fat'] = max(0, min(100, econ.get('fat', 20) + change))
    econ['last_fat_time'] = now_ts
    save_data()
    completed = track_daily_task(user_id, user_tag, 'fat', 1, chat_id)
    
    sign = "+" if change >= 0 else ""
    bot.reply_to(message, f"🥩 {make_link(chat_id, user_tag, user_id, ping=True)}, сканирование жирового слоя завершено!\nИзменение: <b>{sign}{change}%</b>\nТекущий процент жира: <b>{econ['fat']}% 🍔</b>", parse_mode='HTML')
    for task_name, task_reward in completed:
        bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')

@bot.message_handler(commands=['foot'])
def cmd_foot(message):
    user_tag = clean_tag(message.from_user.username or message.from_user.first_name)
    user_id = message.from_user.id
    chat_id = message.chat.id
    econ = get_user_econ(user_id, user_tag)
    now_ts = time.time()
    cooldown = 1200
    
    if now_ts - econ.get('last_foot_time', 0) < cooldown:
        left_sec = int(cooldown - (now_ts - econ.get('last_foot_time', 0)))
        minutes = left_sec // 60
        seconds = left_sec % 60
        bot.reply_to(message, f"⏳ Измерить пятку можно раз в 20 минут!\nПодождите еще: <b>{minutes} мин {seconds} сек</b>.", parse_mode='HTML')
        return

    change = random.randint(-3, 4)
    econ['foot_size'] = max(5, min(60, econ.get('foot_size', 25) + change))
    econ['last_foot_time'] = now_ts
    save_data()
    
    sign = "+" if change >= 0 else ""
    bot.reply_to(message, f"🦶 {make_link(chat_id, user_tag, user_id, ping=True)}, замер вашей пятки завершен!\nИзменение: <b>{sign}{change} см</b>\nТекущий размер пятки: <b>{econ['foot_size']} см 🦶</b>", parse_mode='HTML')

@bot.message_handler(commands=['top'])
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
    user_tag = clean_tag(message.from_user.username or message.from_user.first_name)
    text_lower = text.lower()

    # Учет активности сообщений в заданиях и ачивках
    completed_tasks = track_daily_task(user_id, user_tag, 'messages', 1, chat_id)
    if completed_tasks:
        for task_name, reward in completed_tasks:
            try:
                bot.send_message(chat_id, f'🎉 {make_link(chat_id, user_tag, user_id, ping=True)} выполнил(а) задание: <b>{task_name}</b>! +{reward} 🪙', parse_mode='HTML')
            except Exception:
                pass

    # Ответ полноценной ГИФКОЙ на слово "ПОЧЕМУ"
    if re.search(r'\b(почему|почему\??)\b', text_lower, re.IGNORECASE):
        chosen_gif = random.choice(WHY_GIFS)
        try:
            bot.send_animation(chat_id, chosen_gif, reply_to_message_id=message.message_id)
        except Exception:
            bot.reply_to(message, chosen_gif)

    # Проверка "Кто ты [юзер/айди]"
    who_match = re.search(r'^(?:кто\s+ты|кто\s+такой|кто|что\s+за)\s+(?:@([a-zA-Z0-9_]{1,32})|(\d{5,20}))\s*$', text_lower)
    if who_match:
        target_str = clean_tag(who_match.group(1) or who_match.group(2))
        
        in_rest = False
        rest_info = None
        target_found_tag = target_str
        target_found_id = None

        if str_chat in db.get('rests', {}):
            for u_tag, info in db['rests'][str_chat].items():
                u_id = str(info.get('user_id', ''))
                if u_tag.lower() == target_str.lower() or u_id == target_str:
                    in_rest = True
                    rest_info = info
                    target_found_tag = u_tag
                    target_found_id = info.get('user_id')
                    break
        
        if in_rest and rest_info:
            user_link = make_link(chat_id, target_found_tag, target_found_id, ping=False)
            rem_str = ''
            if rest_info.get('end_time'):
                rem = int(rest_info['end_time'] - time.time())
                if rem > 0:
                    hours, remainder = divmod(rem, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    rem_str = f' (Осталось: {hours}ч {minutes}мин)'
            bot.reply_to(
                message,
                f"🌴 <b>Пользователь {user_link} находится в ресте!</b>\n"
                f"📝 <b>Причина:</b> {rest_info.get('reason', 'Не указана')}\n"
                f"⏱ <b>Срок:</b> {rest_info.get('duration', 'Не указан')}{rem_str}",
                parse_mode='HTML'
            )
        else:
            bot.reply_to(message, f"✅ Пользователь <b>{target_str}</b> сейчас не находится в ресте!", parse_mode='HTML')
        return

    # 1. Автоответы
    triggered = False
    for pattern, responses in ALWAYS_ACTIVE_PATTERNS.items():
        if re.search(pattern, text_lower, re.IGNORECASE):
            bot.reply_to(message, random.choice(responses))
            triggered = True
            break

    # 2. Фильтр мата
    if not triggered and not is_nya_pass_active(user_id, user_tag):
        normalized_text = normalize_text_for_bad_words(text)
        for pattern, responses in MUTABLE_BAD_WORDS_PATTERNS.items():
            if re.search(pattern, normalized_text, re.IGNORECASE) or re.search(pattern, text_lower, re.IGNORECASE):
                bot.reply_to(message, random.choice(responses))
                break

    # Авто-удаление сообщений находящихся в ресте
    sett = get_chat_settings(chat_id)
    if sett.get('delete_rest_msg', False) and str_chat in db['rests']:
        if user_tag in db['rests'][str_chat]:
            try:
                bot.delete_message(chat_id, message.message_id)
                user_link = make_link(chat_id, user_tag, user_id, ping=True)
                warn = bot.send_message(chat_id, f'⚠️ {user_link}, вы находитесь в ресте! Ваше сообщение удалено.', parse_mode='HTML')
                threading.Timer(5, lambda: bot.delete_message(chat_id, warn.message_id)).start()
                return
            except Exception:
                pass

    # Команда +смехуятинка
    if text_lower in ['+смехуятинка', 'смехуятинка']:
        if message.reply_to_message:
            target_u = message.reply_to_message.from_user
            target_tag = clean_tag(target_u.username or target_u.first_name)
            target_id = target_u.id
            
            econ = get_user_econ(target_id, target_tag)
            econ['smeh'] = econ.get('smeh', 0) + 1
            save_data()
            
            u_link = make_link(chat_id, target_tag, target_id, ping=True)
            bot.reply_to(message, f"😂 Пользователю {u_link} начислено +1 очко <b>Смехуятинки</b>!\nВсего очков: <b>{econ['smeh']}</b>", parse_mode='HTML')
        else:
            bot.reply_to(message, "❌ Ответьте этой командой на сообщение человека, которому хотите начислить смехуятинку!")
        return

    # Команды симуляторов
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

    # Глобальные топы
    elif text_lower in ['топ жира', 'топ жирных', 'топ по жиру']:
        if 'economy' in db and db['economy']:
            sorted_fat = sorted(db['economy'].items(), key=lambda x: x[1].get('fat', 0), reverse=True)
            resp = "🌐 <b>Глобальный топ участников по проценту жира:</b>\n\n"
            for idx, (k, info) in enumerate(sorted_fat[:10], 1):
                u_name = info.get('display_name', 'Пользователь')
                u_id = info.get('user_id')
                resp += f"{idx}. {make_link(chat_id, u_name, u_id, ping=False)} — <b>{info.get('fat', 20)}%</b>\n"
            bot.reply_to(message, resp, parse_mode='HTML')
        else:
            bot.reply_to(message, "📊 Статистика пока пуста.")
        return

    elif text_lower in ['топ iq', 'топ айкью', 'топ умных']:
        if 'economy' in db and db['economy']:
            sorted_iq = sorted(db['economy'].items(), key=lambda x: x[1].get('iq', 0), reverse=True)
            resp = "🌐 <b>Глобальный топ самых умных участников (IQ):</b>\n\n"
            for idx, (k, info) in enumerate(sorted_iq[:10], 1):
                u_name = info.get('display_name', 'Пользователь')
                u_id = info.get('user_id')
                resp += f"{idx}. {make_link(chat_id, u_name, u_id, ping=False)} — <b>{info.get('iq', 100)} IQ</b>\n"
            bot.reply_to(message, resp, parse_mode='HTML')
        else:
            bot.reply_to(message, "📊 Статистика пока пуста.")
        return

    elif text_lower in ['топ пяток', 'топ пяточек', 'топ пятка']:
        if 'economy' in db and db['economy']:
            sorted_foot = sorted(db['economy'].items(), key=lambda x: x[1].get('foot_size', 0), reverse=True)
            resp = "🌐 <b>Глобальный топ участников по размеру пятки:</b>\n\n"
            for idx, (k, info) in enumerate(sorted_foot[:10], 1):
                u_name = info.get('display_name', 'Пользователь')
                u_id = info.get('user_id')
                resp += f"{idx}. {make_link(chat_id, u_name, u_id, ping=False)} — <b>{info.get('foot_size', 25)} см</b>\n"
            bot.reply_to(message, resp, parse_mode='HTML')
        else:
            bot.reply_to(message, "📊 Статистика пока пуста.")
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
        else:
            bot.reply_to(message, "🪙 Статистика коинов пока пуста.")
        return

    # Текстовые эквиваленты
    if text_lower in ['баланс', 'коины', 'ня-коины']:
        cmd_balance(message)
        return

    elif text_lower in ['инвентарь', 'профиль', 'мои значки']:
        cmd_profile(message)
        return

    elif text_lower in ['бонус', 'коин', 'собрать']:
        econ = get_user_econ(user_id, user_tag)
        now_ts = time.time()
        if now_ts - econ.get('last_hourly', 0) >= 3600:
            reward = random.randint(1, 100)
            econ['balance'] += reward
            econ['last_hourly'] = now_ts
            save_data()
            check_achievements(user_id, user_tag, 'bonuses', 1, chat_id)
            completed = track_daily_task(user_id, user_tag, 'bonus', 1, chat_id)
            bot.reply_to(message, f"🎲 Вы собрали: <b>+{reward} Ня-коинов 🪙</b>!\nЕдиный баланс: <b>{econ['balance']} 💸</b>", parse_mode='HTML')
            for task_name, task_reward in completed:
                bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        else:
            left_sec = 3600 - (now_ts - econ.get('last_hourly', 0))
            minutes = int(left_sec // 60)
            seconds = int(left_sec % 60)
            bot.reply_to(message, f"⏳ Можно собирать коины каждый час! Следующий сбор через: <b>{minutes} мин {seconds} сек</b>.", parse_mode='HTML')
        return

    elif text_lower in ['задания', 'ня-пасс', 'ня пасс', 'daily', 'квесты']:
        cmd_tasks(message)
        return

    elif text_lower.startswith(('кости', '/dice')):
        match = re.search(r'(?:кости|/dice)\s*(\d+)?', text, re.IGNORECASE)
        bet = int(match.group(1) or 0) if match else 0
        econ = get_user_econ(user_id, user_tag)
        if bet < 0:
            bot.reply_to(message, '❌ Ставка не может быть отрицательной.')
            return
        if bet > econ['balance']:
            bot.reply_to(message, '❌ Недостаточно Ня-коинов для ставки!')
            return
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
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
        save_data()
        check_achievements(user_id, user_tag, 'games', 1, chat_id)
        completed = track_daily_task(user_id, user_tag, 'dice', 1, chat_id)
        bot.reply_to(message, result + f"\n💰 Баланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
        for task_name, task_reward in completed:
            bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        return

    elif text_lower.startswith(('слоты', '/slots')):
        match = re.search(r'(?:слоты|/slots)\s*(\d+)?', text, re.IGNORECASE)
        bet = int(match.group(1) or 0) if match else 0
        econ = get_user_econ(user_id, user_tag)
        if bet < 0 or bet > econ['balance']:
            bot.reply_to(message, '❌ Некорректная ставка или недостаточно Ня-коинов.')
            return
        symbols = ['🍒', '🍋', '🍉', '⭐', '💎']
        roll = [random.choice(symbols) for _ in range(3)]
        result = f"🎰 {' | '.join(roll)}"
        if bet:
            if roll[0] == roll[1] == roll[2]:
                win = bet * 5
                econ['balance'] += win
                result += f'\n💎 Три одинаковых! Выигрыш <b>+{win} 🪙</b>!'
            elif len(set(roll)) == 2:
                win = bet * 2
                econ['balance'] += win
                result += f'\n✨ Две одинаковых! Выигрыш <b>+{win} 🪙</b>!'
            else:
                econ['balance'] -= bet
                result += f'\n💸 Проигрыш <b>{bet} 🪙</b>.'
        save_data()
        check_achievements(user_id, user_tag, 'games', 1, chat_id)
        completed = track_daily_task(user_id, user_tag, 'slots', 1, chat_id)
        bot.reply_to(message, result + f"\n💰 Баланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
        for task_name, task_reward in completed:
            bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        return

    elif text_lower.startswith(('рулетка', '/roulette')):
        match = re.search(r'(?:рулетка|/roulette)\s*(\d+)?', text, re.IGNORECASE)
        bet = int(match.group(1) or 0) if match else 0
        econ = get_user_econ(user_id, user_tag)
        if bet < 0 or bet > econ['balance']:
            bot.reply_to(message, '❌ Некорректная ставка или недостаточно Ня-коинов.')
            return
        number = random.randint(0, 36)
        color = 'зелёное' if number == 0 else ('красное' if number in {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36} else 'чёрное')
        result = f'🎡 Рулетка: <b>{number}</b> ({color}).'
        if bet:
            if number == 0:
                econ['balance'] -= bet
                result += f'\n💸 Проигрыш <b>{bet} 🪙</b>.'
            elif number % 2 == 0:
                econ['balance'] += bet
                result += f'\n🎉 Чётное! Вы выиграли <b>+{bet} 🪙</b>!'
            else:
                econ['balance'] -= bet
                result += f'\n💸 Нечётное. Вы проиграли <b>{bet} 🪙</b>.'
        save_data()
        check_achievements(user_id, user_tag, 'games', 1, chat_id)
        completed = track_daily_task(user_id, user_tag, 'roulette', 1, chat_id)
        bot.reply_to(message, result + f"\n💰 Баланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
        for task_name, task_reward in completed:
            bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        return

    # РЫБАЛКА С УЧЕТОМ УДАЧИ ПИТОМЦА
    elif text_lower in ['рыбалка', '/fish', 'рыба', 'fish']:
        econ = get_user_econ(user_id, user_tag)
        left = cooldown_text(econ.get('last_fish_time', 0), 7200)
        if left:
            bot.reply_to(message, f'⏳ Рыбалка доступна раз в 2 часа. Осталось: <b>{left}</b>.', parse_mode='HTML')
            return

        luck_bonus = 0
        if econ.get('pet'):
            p = econ['pet']
            update_pet_stats(p)
            if p.get('hunger', 0) >= 30 and p.get('cleanliness', 0) >= 30:
                luck_bonus = p.get('luck_bonus', 0)

        weights = [max(1, int(f[3] * (1 + luck_bonus / 100.0))) for f in FISH_TYPES]
        caught_fish = random.choices(FISH_TYPES, weights=weights, k=1)[0]

        econ['last_fish_time'] = time.time()
        add_inventory_item(econ['fish_inventory'], caught_fish[0])
        save_data()

        check_achievements(user_id, user_tag, 'fish', 1, chat_id)
        completed = track_daily_task(user_id, user_tag, 'fish', 1, chat_id)

        luck_msg = f"\n🐾 Ваш питомец помог выудить более редкую рыбу!" if luck_bonus else ""
        bot.reply_to(
            message,
            f'🎣 Вы поймали: <b>{caught_fish[0]}</b> [{caught_fish[1]}]!\n'
            f'💰 Базовая цена: <b>{caught_fish[2]} 🪙</b>{luck_msg}\n'
            f'💡 Чтобы продать улов, введите: <code>/sell</code>',
            parse_mode='HTML'
        )
        for task_name, task_reward in completed:
            bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        return

    # ОХОТА С УЧЕТОМ УДАЧИ ПИТОМЦА
    elif text_lower in ['охота', '/hunt', 'hunt']:
        econ = get_user_econ(user_id, user_tag)
        left = cooldown_text(econ.get('last_hunt_time', 0), 7200)
        if left:
            bot.reply_to(message, f'⏳ Охота доступна раз в 2 часа. Осталось: <b>{left}</b>.', parse_mode='HTML')
            return

        luck_bonus = 0
        if econ.get('pet'):
            p = econ['pet']
            update_pet_stats(p)
            if p.get('hunger', 0) >= 30 and p.get('cleanliness', 0) >= 30:
                luck_bonus = p.get('luck_bonus', 0)

        weights = [max(1, int(h[3] * (1 + luck_bonus / 100.0))) for h in HUNT_TYPES]
        caught_hunt = random.choices(HUNT_TYPES, weights=weights, k=1)[0]

        econ['last_hunt_time'] = time.time()
        add_inventory_item(econ['hunt_inventory'], caught_hunt[0])
        save_data()

        check_achievements(user_id, user_tag, 'hunt', 1, chat_id)
        completed = track_daily_task(user_id, user_tag, 'hunt', 1, chat_id)

        luck_msg = f"\n🐾 Ваш питомец помог выследить редкую добычу!" if luck_bonus else ""
        bot.reply_to(
            message,
            f'🏹 Охота успешна! Добыча: <b>{caught_hunt[0]}</b> [{caught_hunt[1]}]!\n'
            f'💰 Базовая цена: <b>{caught_hunt[2]} 🪙</b>{luck_msg}\n'
            f'💡 Чтобы продать трофеи, введите: <code>/sell</code>',
            parse_mode='HTML'
        )
        for task_name, task_reward in completed:
            bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        return

    # ПРОМОКОДЫ
    elif text_lower.startswith('промокод') or text_lower.startswith('/promo'):
        match = re.search(r'(?:промокод|/promo)\s+(.+)', text, re.IGNORECASE)
        if match:
            code = match.group(1).strip().upper()
            if code == 'ADMIN1000':
                if user_username == ADMIN_USERNAME:
                    add_coins(user_id, user_tag, 10000)
                    bot.reply_to(message, "🎁 <b>Разработчик активировал промокод!</b>\nВам начислено <b>+10000 Ня-коинов 🪙</b>!", parse_mode='HTML')
                else:
                    bot.reply_to(message, "❌ Этот промокод только для разработчика!")
            elif code in ['OHAYO500', 'OHAYO']:
                if 'promos' not in db: db['promos'] = {}
                if 'OHAYO500' not in db['promos']: db['promos']['OHAYO500'] = []
                user_key = get_global_user_key(user_id, user_tag)
                if user_key in db['promos']['OHAYO500']:
                    bot.reply_to(message, "❌ Вы уже активировали этот промокод!")
                else:
                    db['promos']['OHAYO500'].append(user_key)
                    add_coins(user_id, user_tag, 500)
                    save_data()
                    bot.reply_to(message, "🎉 Промокод активирован! Вам начислено <b>+500 Ня-коинов 🪙</b>!", parse_mode='HTML')
            else:
                bot.reply_to(message, "❌ Неверный промокод!")
        else:
            bot.reply_to(message, "❌ Формат: <code>/promo OHAYO500</code>", parse_mode='HTML')
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
                target_u = clean_tag(replied_user.username or replied_user.first_name)
                target_id = replied_user.id
            else:
                bot.reply_to(message, "❌ Укажите сумму! Пример: <code>передать 50</code> ответом.", parse_mode='HTML')
                return
        else:
            match = re.search(r'(?:перевод|передать|/pay)\s+@?([a-zA-Z0-9_а-яА-ЯёЁ]+)\s+(\d+)', text, re.IGNORECASE)
            if match:
                target_u = clean_tag(match.group(1))
                amount = int(match.group(2))
                target_id = find_known_user_id(chat_id, target_u)
            else:
                bot.reply_to(message, "❌ Формат перевода:\n• Ответом: <code>передать 50</code>\n• По юзернейму: <code>/pay @username 50</code>", parse_mode='HTML')
                return

        if amount <= 0:
            bot.reply_to(message, "❌ Сумма перевода должна быть больше 0!")
            return

        if target_id == user_id:
            bot.reply_to(message, "❌ Нельзя переводить коины самому себе!")
            return

        sender_econ = get_user_econ(user_id, user_tag)
        if sender_econ['balance'] < amount:
            bot.reply_to(message, "❌ Недостаточно Ня-коинов для перевода!")
            return

        sender_econ['balance'] -= amount
        add_coins(target_id, target_u, amount)
        save_data()

        check_achievements(user_id, user_tag, 'transfers', 1, chat_id)
        completed = track_daily_task(user_id, user_tag, 'transfer', 1, chat_id)
        
        log_event('ПЕРЕВОД', f'Отправлено: <b>{amount} 🪙</b>\nОт: {make_link(chat_id, user_tag, user_id, ping=False)}\nКому: {make_link(chat_id, target_u, target_id, ping=False)}')
        bot.reply_to(message, f"💸 Вы успешно перевели <b>{amount} 🪙</b> пользователю {make_link(chat_id, target_u, target_id, ping=True)}!", parse_mode='HTML')
        for task_name, reward in completed:
            bot.send_message(chat_id, f'🎉 Задание выполнено: <b>{task_name}</b>! +{reward} 🪙', parse_mode='HTML')
        return

    elif text_lower in ['магазин', 'лавка', 'shop']:
        cmd_shop(message)
        return

    # ЗАПРОС И УПРАВЛЕНИЕ РЕСТАМИ
    if text_lower.startswith('запрос рест'):
        match = re.search(r'запрос\s+рест\s+(.+)', text, re.IGNORECASE)
        if not match:
            bot.reply_to(message, '❌ Формат: <code>запрос рест 3 дня | причина</code>', parse_mode='HTML')
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

        user_link = make_link(chat_id, user_tag, user_id, ping=True)
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
            
            reward_given, count = apply_rest(chat_id, target_user, duration_text, reason, target_user_id)
            user_link = make_link(chat_id, target_user, target_user_id, ping=True)
            
            coin_msg = f"\n🪙 Выдано +150 Ня-коинов за рест! ({count}/5)" if reward_given else f"\n⛔️ Лимит бонусов за рест исчерпан ({count}/5)!"
            bot.reply_to(message, f'✅ Рест для {user_link} добавлен!\n⏱ Срок: {duration_text}\n📝 Причина: {reason}{coin_msg}', parse_mode='HTML')
        else:
            bot.reply_to(message, '❌ Формат: <code>+рест 3 дня | отпуск @username</code>', parse_mode='HTML')

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
                user_link = make_link(chat_id, target_user, target_user_id, ping=True)
                bot.reply_to(message, f'✅ Рест для {user_link} продлен на {add_text}!', parse_mode='HTML')

    elif text_lower.startswith('причина'):
        if not is_admin(chat_id, user_id):
            return

        target_user, target_user_id, new_reason = parse_target_and_args(message, 'причина')

        if target_user and new_reason and str_chat in db['rests'] and target_user in db['rests'][str_chat]:
            db['rests'][str_chat][target_user]['reason'] = new_reason
            if not target_user_id:
                target_user_id = db['rests'][str_chat][target_user].get('user_id')
            save_data()
            user_link = make_link(chat_id, target_user, target_user_id, ping=True)
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
                user_link = make_link(chat_id, target_user, target_user_id, ping=True)
                log_event('СНЯТИЕ РЕСТА', f'Админ: {make_link(chat_id, user_tag, user_id, ping=False)}\nПользователь: {user_link}')
                bot.reply_to(message, f'🗑 Рест с {user_link} успешно снят.', parse_mode='HTML')

    elif text_lower in ['ресты', 'рест']:
        if str_chat not in db['rests'] or not db['rests'][str_chat]:
            bot.reply_to(message, '🌴 В данный момент никто не находится в ресте.')
        else:
            resp = '📋 <b>Список активных рестов:</b>\n\n'
            for u, info in db['rests'][str_chat].items():
                reason_text = info.get('reason', 'Не указана')
                u_link = make_link(chat_id, u, info.get('user_id'), ping=False)
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
                u_link = make_link(chat_id, u, user_ids.get(u), ping=False)
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
                u_link = make_link(chat_id, u, u_id, ping=False)
                resp += f'• {date} — {u_link}: {dur} ({reas})\n'
            bot.reply_to(message, resp, parse_mode='HTML')

# ---------------------------------------------------------
# ОБРАБОТКА ИНТЕРАКТИВНЫХ КНОПОК Callback
# ---------------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    user_tag = clean_tag(call.from_user.username or call.from_user.first_name)

    # ОБРАБОТКА ВАКАНСИЙ И РАБОТЫ
    if call.data.startswith('do_job_'):
        job_id = call.data.replace('do_job_', '')
        if job_id in JOBS:
            job = JOBS[job_id]
            econ = get_user_econ(user_id, user_tag)
            
            if econ.get('work_exp', 0) < job['req_exp']:
                bot.answer_callback_query(call.id, f"❌ Для работы нужно минимум {job['req_exp']} EXP опыта!", show_alert=True)
                return

            now = time.time()
            if now - econ.get('last_work_time', 0) < 1800:
                left = int(1800 - (now - econ.get('last_work_time', 0)))
                bot.answer_callback_query(call.id, f"⏳ Перерыв! Отдохните еще {left // 60} мин {left % 60} сек.", show_alert=True)
                return

            econ['last_work_time'] = now
            roll = random.randint(1, 100)

            if roll <= job['chance']:
                pay = random.randint(job['min_pay'], job['max_pay'])
                econ['balance'] += pay
                econ['work_exp'] = econ.get('work_exp', 0) + job['exp_gain']
                save_data()
                bot.answer_callback_query(call.id, f"✅ Смена окончена! +{pay} 🪙 и +{job['exp_gain']} EXP!", show_alert=True)
                bot.send_message(
                    chat_id,
                    f"💼 {make_link(chat_id, user_tag, user_id, ping=True)} отлично поработал(а) на должности <b>{job['name']}</b>!\n"
                    f"💰 Зарплата: <b>+{pay} Ня-коинов 🪙</b>\n"
                    f"📈 Опыт за смену: <b>+{job['exp_gain']} EXP</b> (Всего: {econ['work_exp']} EXP)",
                    parse_mode='HTML'
                )
            else:
                econ['work_exp'] = econ.get('work_exp', 0) + 2
                save_data()
                bot.answer_callback_query(call.id, "❌ Вы совершили ошибку и остались без зарплаты!", show_alert=True)
                bot.send_message(
                    chat_id,
                    f"🤕 {make_link(chat_id, user_tag, user_id, ping=True)} работал(а) на должности <b>{job['name']}</b>, но завалил(а) смену.\n"
                    f"Зарплату не выплатили, но получен опыт (+2 EXP)!",
                    parse_mode='HTML'
                )

    # ОБРАБОТКА УХОДА ЗА ПИТОМЦЕМ
    elif call.data == 'pet_feed':
        cmd_feed(call.message)
    elif call.data == 'pet_wash':
        cmd_wash(call.message)

    # НАСТРОЙКИ ЧАТА
    elif call.data == 'set_max_days':
        if not is_admin(chat_id, user_id): return
        sett = get_chat_settings(chat_id)
        opts = [14, 30, 60]
        next_opt = opts[(opts.index(sett['max_days']) + 1) % len(opts)]
        sett['max_days'] = next_opt
        save_data()
        bot.answer_callback_query(call.id, f'✅ Лимит изменен на {next_opt} дней!')
        chat_settings_cmd(call.message)

    elif call.data == 'toggle_del_msg':
        if not is_admin(chat_id, user_id): return
        sett = get_chat_settings(chat_id)
        sett['delete_rest_msg'] = not sett['delete_rest_msg']
        save_data()
        bot.answer_callback_query(call.id, f"✅ Авто-удаление: {'Включено' if sett['delete_rest_msg'] else 'Выключено'}")
        chat_settings_cmd(call.message)

    elif call.data == 'set_remind_time':
        if not is_admin(chat_id, user_id): return
        sett = get_chat_settings(chat_id)
        opts = [10, 60, 1440]
        next_opt = opts[(opts.index(sett.get('remind_minutes', 60)) + 1) % len(opts)]
        sett['remind_minutes'] = next_opt
        save_data()
        bot.answer_callback_query(call.id, f'✅ Напоминание установлено за {next_opt} мин!')
        chat_settings_cmd(call.message)

    # МЕНЮ МАГАЗИНА
    elif call.data == 'shop_main':
        send_shop_menu(chat_id, user_id, user_tag, call.message.message_id)

    elif call.data == 'shop_cat_passes':
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('🎟 Купить Ня-Пасс от мата (500 🪙)', callback_data='buy_nya_pass'))
        markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data='shop_main'))
        
        pass_status = "❌ Не куплен"
        if is_nya_pass_active(user_id, user_tag):
            pass_status = "✅ Активен"
        
        text = (
            "🎟 <b>Категория: Пассы</b>\n\n"
            "• <b>Ня-Пасс от мата (на 1 неделю) — 500 🪙</b>\n"
            "Защищает от автоответов бота на мат и слово 'коч'.\n\n"
            f"Текущий статус: <b>{pass_status}</b>"
        )
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'shop_cat_titles':
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton('👑 Кинг (2500 🪙)', callback_data='buy_title_king'),
            InlineKeyboardButton('💤 Соня (1800 🪙)', callback_data='buy_title_sonya')
        )
        markup.add(
            InlineKeyboardButton('🔥 Легенда (3000 🪙)', callback_data='buy_title_legend'),
            InlineKeyboardButton('🐉 Дракон (3500 🪙)', callback_data='buy_title_dragon')
        )
        markup.add(InlineKeyboardButton('🥐 Булочка (1500 🪙)', callback_data='buy_title_bun'))
        markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data='shop_main'))

        text = "👑 <b>Категория: Титулы для профиля</b>\n\nКупленный титул отображается возле вашего имени во всех сообщениях бота!"
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'shop_cat_badges':
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton('🌟 Звезда (100 🪙)', callback_data='buy_badge_badge_star'),
            InlineKeyboardButton('🍡 Данго (150 🪙)', callback_data='buy_badge_badge_dango')
        )
        markup.add(
            InlineKeyboardButton('🐾 Лапка (200 🪙)', callback_data='buy_badge_badge_paw'),
            InlineKeyboardButton('💖 Сердце (200 🪙)', callback_data='buy_badge_badge_heart')
        )
        markup.add(
            InlineKeyboardButton('🔥 Огонек (250 🪙)', callback_data='buy_badge_badge_fire'),
            InlineKeyboardButton('⚡️ Молния (300 🪙)', callback_data='buy_badge_badge_lightning')
        )
        markup.add(
            InlineKeyboardButton('👑 Корона (300 🪙)', callback_data='buy_badge_badge_crown'),
            InlineKeyboardButton('🍀 Клевер (350 🪙)', callback_data='buy_badge_badge_clover')
        )
        markup.add(
            InlineKeyboardButton('🌸 Сакура (400 🪙)', callback_data='buy_badge_badge_sakura'),
            InlineKeyboardButton('💎 Бриллиант (500 🪙)', callback_data='buy_badge_badge_diamond')
        )
        markup.add(
            InlineKeyboardButton('💀 Череп (600 🪙)', callback_data='buy_badge_badge_skull'),
            InlineKeyboardButton('🚀 Ракета (700 🪙)', callback_data='buy_badge_badge_rocket')
        )
        markup.add(
            InlineKeyboardButton('🦊 Лисичка (800 🪙)', callback_data='buy_badge_badge_fox'),
            InlineKeyboardButton('👽 Инопланетянин (900 🪙)', callback_data='buy_badge_badge_alien')
        )
        markup.add(
            InlineKeyboardButton('🦄 Единорог (1000 🪙)', callback_data='buy_badge_badge_unicorn'),
            InlineKeyboardButton('🐉 Дракон (1500 🪙)', callback_data='buy_badge_badge_dragon')
        )
        markup.add(
            InlineKeyboardButton('👻 Призрак (2000 🪙)', callback_data='buy_badge_badge_ghost'),
            InlineKeyboardButton('🦶 Пятка (3000 🪙)', callback_data='buy_badge_badge_foot')
        )
        markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data='shop_main'))

        text = "✨ <b>Категория: Значки и смайлы</b>"
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    elif call.data == 'shop_cat_pets':
        markup = InlineKeyboardMarkup()
        for p_id, p in PETS_DATA.items():
            markup.add(InlineKeyboardButton(f"{p['name']} ({p['price']} 🪙)", callback_data=f"buy_pet_{p_id}"))
        markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data='shop_main'))

        text = "🐾 <b>Магазин Домашних Питомцев</b>\n\nПитомцы требуют ухода (кормить и мыть), но они дают **бонус к удаче** на охоте и рыбалке!"
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

    # ПОКУПКИ
    elif call.data == 'buy_nya_pass':
        econ = get_user_econ(user_id, user_tag)
        if econ['balance'] < 500:
            bot.answer_callback_query(call.id, '❌ Недостаточно Ня-коинов! Нужно 500 🪙', show_alert=True)
            return
        
        econ['balance'] -= 500
        econ['nya_pass_until'] = max(time.time(), econ.get('nya_pass_until', 0)) + 604800
        econ['nya_pass_enabled'] = True
        save_data()
        
        bot.answer_callback_query(call.id, '🎉 Вы купили Ня-Пасс от мата на 1 неделю!', show_alert=True)
        log_event('ПОКУПКА', f'Пользователь: {make_link(chat_id, user_tag, user_id, ping=False)}\nТовар: <b>Ня-Пасс</b>')

    elif call.data.startswith('buy_pet_'):
        pet_id = call.data.replace('buy_pet_', '')
        if pet_id in PETS_DATA:
            p_data = PETS_DATA[pet_id]
            econ = get_user_econ(user_id, user_tag)

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

            bot.answer_callback_query(call.id, f"🎉 Вы приобрели питомца {p_data['name']}!", show_alert=True)
            bot.send_message(
                chat_id,
                f"🎉 {make_link(chat_id, user_tag, user_id, ping=True)} завел(а) нового питомца — <b>{p_data['name']}</b>!\nНе забывайте ухаживать за ним через <code>/pet</code>!",
                parse_mode='HTML'
            )

    elif call.data.startswith('buy_title_'):
        title_key = call.data.replace('buy_title_', '')
        if title_key in TITLES:
            item = TITLES[title_key]
            econ = get_user_econ(user_id, user_tag)
            if title_key in econ.get('titles', []):
                bot.answer_callback_query(call.id, '❌ Этот титул уже куплен!', show_alert=True)
                return
            if econ['balance'] < item['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {item['price']} 🪙!", show_alert=True)
                return
            econ['balance'] -= item['price']
            econ.setdefault('titles', []).append(title_key)
            econ['active_title'] = title_key
            save_data()
            bot.answer_callback_query(call.id, f"🎉 Титул {item['text']} куплен!", show_alert=True)
            send_user_profile(chat_id, user_tag, user_id)

    elif call.data.startswith('buy_badge_'):
        badge_key = call.data.replace('buy_badge_', '')
        if badge_key in BADGES:
            item = BADGES[badge_key]
            econ = get_user_econ(user_id, user_tag)
            
            if item['emoji'] in econ.get('inventory', []):
                bot.answer_callback_query(call.id, f"Значок {item['emoji']} уже есть в инвентаре!", show_alert=True)
                return

            if econ['balance'] < item['price']:
                bot.answer_callback_query(call.id, f"❌ Нужно {item['price']} 🪙!", show_alert=True)
                return

            econ['balance'] -= item['price']
            econ.setdefault('inventory', []).append(item['emoji'])
            econ['badge'] = item['emoji']
            save_data()

            bot.answer_callback_query(call.id, f"🎉 Вы купили значок {item['emoji']}!", show_alert=True)

    # НАДЕВАНИЕ И СНЯТИЕ ПРЕДМЕТОВ
    elif call.data.startswith('set_title_'):
        title_key = call.data.replace('set_title_', '')
        econ = get_user_econ(user_id, user_tag)
        if title_key in econ.get('titles', []) and title_key in TITLES:
            econ['active_title'] = title_key
            save_data()
            bot.answer_callback_query(call.id, f"✅ Вы надели титул {TITLES[title_key]['text']}!", show_alert=True)
            send_user_profile(chat_id, user_tag, user_id)

    elif call.data == 'remove_title':
        econ = get_user_econ(user_id, user_tag)
        econ['active_title'] = None
        save_data()
        bot.answer_callback_query(call.id, '❌ Титул снят!', show_alert=True)
        send_user_profile(chat_id, user_tag, user_id)

    elif call.data.startswith('set_badge_'):
        selected_emoji = call.data.replace('set_badge_', '')
        econ = get_user_econ(user_id, user_tag)
        if selected_emoji in econ.get('inventory', []):
            econ['badge'] = selected_emoji
            save_data()
            bot.answer_callback_query(call.id, f"✅ Вы надели значок {selected_emoji}!", show_alert=True)
            send_user_profile(chat_id, user_tag, user_id)

    elif call.data == 'remove_badge':
        econ = get_user_econ(user_id, user_tag)
        econ['badge'] = None
        save_data()
        bot.answer_callback_query(call.id, "❌ Значок снят!", show_alert=True)
        send_user_profile(chat_id, user_tag, user_id)

    elif call.data == 'toggle_nya_pass':
        econ = get_user_econ(user_id, user_tag)
        econ['nya_pass_enabled'] = not econ.get('nya_pass_enabled', True)
        save_data()
        status_msg = "включен" if econ['nya_pass_enabled'] else "выключен"
        bot.answer_callback_query(call.id, f"⚙️ Ня-Пасс {status_msg}!", show_alert=True)
        send_user_profile(chat_id, user_tag, user_id)

    # ОБРАБОТКА ЗАПРОСОВ НА РЕСТ (КНОПКИ АДМИНА)
    elif call.data.startswith(('app_', 'qs_')):
        if not is_admin(chat_id, user_id):
            bot.answer_callback_query(call.id, '❌ Принимать решения могут только админы!', show_alert=True)
            return

        parts = call.data.split('_')
        req_id = parts[1]
        req_info = pending_requests.get(req_id)

        if not req_info:
            bot.answer_callback_query(call.id, '❌ Запрос устарел!', show_alert=True)
            return

        target_user = req_info['user_tag']
        duration_text = req_info['duration']
        reason = parts[2] if len(parts) > 2 else req_info['reason']
        target_user_id = req_info['user_id']

        reward_given, count = apply_rest(chat_id, target_user, duration_text, reason, target_user_id)
        admin_link = make_link(chat_id, call.from_user.username or call.from_user.first_name, user_id, ping=False)
        user_link = make_link(chat_id, target_user, target_user_id, ping=True)
        
        coin_msg = f"\n🪙 Выдано +150 Ня-коинов ({count}/5)!" if reward_given else f"\n⛔️ Лимит 5/5 бонусов достигнут!"
        
        bot.edit_message_text(
            f'✅ <b>Запрос принят админом {admin_link}!</b>\n'
            f'Пользователю {user_link} выдан рест на {duration_text} (Причина: {reason}).{coin_msg}',
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
        user_link = make_link(chat_id, target_user, user_id_val, ping=False)
        bot.edit_message_text(
            f'❌ <b>Запрос от {user_link} отклонен.</b>',
            chat_id=chat_id,
            message_id=call.message.message_id,
            parse_mode='HTML'
        )

# ---------------------------------------------------------
# ЗАПУСК БОТА
# ---------------------------------------------------------
setup_bot_commands()
restore_timers()
keep_alive()

print('Бот успешно запущен...')
bot.infinity_polling()
