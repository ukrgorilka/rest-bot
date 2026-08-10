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
TOKEN = 'ВСТАВЬ_СЮДА_ТОКЕН_БОТА'
if not TOKEN:
    raise RuntimeError('Не задан токен бота')
bot = telebot.TeleBot(TOKEN)

# ID вашего приватного канала для авто-бекапов
DB_CHANNEL_ID = int(os.environ.get('DB_CHANNEL_ID', '-1004334874700'))
# Отдельный канал для логов рестов, переводов и покупок.
LOG_CHANNEL_ID = int(os.environ.get('LOG_CHANNEL_ID', '-5587336891'))
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

# Кастомные титулы для профиля. Титул можно купить в магазине и выбрать в профиле.
TITLES = {
    'king': {'name': 'Кинг', 'text': '👑 Кинг', 'price': 2500},
    'sonya': {'name': 'Соня', 'text': '💤 Соня', 'price': 1800},
    'legend': {'name': 'Легенда', 'text': '🔥 Легенда', 'price': 3000},
    'dragon': {'name': 'Дракон', 'text': '🐉 Дракон', 'price': 3500},
    'bun': {'name': 'Булочка', 'text': '🥐 Булочка', 'price': 1500},
}

# Динамические ежедневные задания Ня-Пасса. Индекс 0 = понедельник.
DAILY_TASKS = {
    0: [
        ('messages', 'Написать 30 сообщений', 30),
        ('transfer', 'Перевести 100 коинов', 100),
        ('bonus', 'Собрать 2 часовых бонуса', 2),
    ],
    1: [
        ('messages', 'Написать 40 сообщений', 40),
        ('dice', 'Сыграть в кости 3 раза', 3),
        ('fish', 'Поймать 1 рыбу', 1),
    ],
    2: [
        ('messages', 'Написать 30 сообщений', 30),
        ('slots', 'Испытать слоты 2 раза', 2),
        ('iq', 'Измерить IQ', 1),
    ],
    3: [
        ('messages', 'Написать 50 сообщений', 50),
        ('transfer', 'Перевести 50 коинов', 50),
        ('hunt', 'Сходить на охоту', 1),
    ],
    4: [
        ('messages', 'Написать 35 сообщений', 35),
        ('dice', 'Сыграть в кости 5 раз', 5),
        ('fat', 'Измерить жир', 1),
    ],
    5: [
        ('messages', 'Написать 45 сообщений', 45),
        ('bonus', 'Собрать 3 часовых бонуса', 3),
        ('fish', 'Поймать 2 рыбы', 2),
    ],
    6: [
        ('messages', 'Написать 60 сообщений', 60),
        ('transfer', 'Перевести 150 коинов', 150),
        ('hunt', 'Сходить на охоту 2 раза', 2),
    ],
}
DAILY_TASK_REWARD = 100

# --- ВСЕГДА АКТИВНЫЕ ТРИГГЕРЫ (Работают даже с Ня-Пассом) ---
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

# --- МАТЫ И СЛОВО КОЧ (Отключаются у тех, у кого активен Ня-Пасс) ---
MUTABLE_BAD_WORDS_PATTERNS = {
    # 1. Слово "Коч"
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
    # 2. Оскорбления личности
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
    # 3. Пездюк, пиздюк и мелкие оскорбления
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
    # 4. Пидр, пидорас и ЛГБТ-оскорбления
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
    # 5. Медицинские/Умственные оскорбления
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
    # 6. Вахуе, вахуи, в ахуе
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
    # 7. Залупа и анатомические оскорбления
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
    # 8. Сосать / соси
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
    # 9. Трахать / пошлости
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
    # 10. Шлюха, проститутка, шалава
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
    # 11. Мудак, презерватив, уебище, мразь, сука
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
    # 12. Пизда, пиздец, хуесос, пиздос
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
    # 13. Блять, бля, бл, бль
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
    # 14. Нахуй, похуй, нафиг
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
    # 15. Хуй, хуйня, заебись
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
    # 16. Ахуеть, охуеть, охуел, ахуел
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

def clean_junk_rests():
    """Удаляет сбойные ресты вроде '8' из базы данных"""
    changed = False
    for str_chat in list(db.get('rests', {}).keys()):
        for user_key in list(db['rests'][str_chat].keys()):
            if user_key == '8' or user_key.isdigit():
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
def clean_tag(user_str):
    if not user_str:
        return 'Пользователь'
    return user_str.replace('@', '').strip()

def get_global_user_key(user_id=None, user_tag=None):
    """Генерирует единый ключ пользователя для глобальной базы"""
    if user_id:
        return f"id_{user_id}"
    if user_tag:
        return f"tag_{clean_tag(user_tag).lower()}"
    return "unknown_user"

def get_user_econ(user_id=None, user_tag=None):
    """Возвращает общую статистику пользователя по всей сети бота"""
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
            'fish_inventory': {},      # Инвентарь рыбы
            'hunt_inventory': {},      # Инвентарь охотничьих трофеев
            'last_fish_time': 0,       # КД рыбалки 2 часа
            'last_hunt_time': 0,       # КД охоты 2 часа
            'rest_rewards_count': 0    # Счетчик выданных 150 коинов (макс 5 навсегда)
        }
        save_data()

    u_data = db['economy'][key]
    if user_tag:
        u_data['display_name'] = clean_tag(user_tag)
    if user_id:
        u_data['user_id'] = user_id
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
    if 'fish_inventory' not in u_data: u_data['fish_inventory'] = {}
    if 'hunt_inventory' not in u_data: u_data['hunt_inventory'] = {}
    if 'last_fish_time' not in u_data: u_data['last_fish_time'] = 0
    if 'last_hunt_time' not in u_data: u_data['last_hunt_time'] = 0

    return u_data

def add_coins(user_id=None, user_tag=None, amount=0):
    user_data = get_user_econ(user_id, user_tag)
    user_data['balance'] += amount
    save_data()
    return user_data['balance']

def is_nya_pass_active(user_id=None, user_tag=None):
    user_data = get_user_econ(user_id, user_tag)
    until = user_data.get('nya_pass_until', 0)
    enabled = user_data.get('nya_pass_enabled', True)
    return enabled and (time.time() < until)

def log_event(event_type, message_text):
    """Пишет важные действия в отдельный Telegram-канал логов."""
    if not LOG_CHANNEL_ID:
        return
    try:
        bot.send_message(LOG_CHANNEL_ID, f'📌 <b>{event_type}</b>\n{message_text}', parse_mode='HTML')
    except Exception as e:
        print(f'Ошибка записи в канал логов: {e}')


def daily_task_date():
    return datetime.now().strftime('%Y-%m-%d')


def get_daily_tasks(user_id=None, user_tag=None):
    econ = get_user_econ(user_id, user_tag)
    today = daily_task_date()
    if econ.get('daily_tasks_date') != today:
        econ['daily_tasks_date'] = today
        econ['daily_progress'] = {}
        econ['daily_claimed'] = []
    return DAILY_TASKS[datetime.now().weekday()], econ


def track_daily_task(user_id, user_tag, task_key, amount=1):
    if not is_nya_pass_active(user_id, user_tag):
        return []
    tasks, econ = get_daily_tasks(user_id, user_tag)
    progress = econ.setdefault('daily_progress', {})
    old_value = progress.get(task_key, 0)
    if task_key == 'messages':
        progress[task_key] = old_value + amount
    else:
        progress[task_key] = old_value + amount

    completed = []
    for key, description, target in tasks:
        if key not in econ.get('daily_claimed', []) and progress.get(key, 0) >= target:
            econ.setdefault('daily_claimed', []).append(key)
            econ['balance'] += DAILY_TASK_REWARD
            completed.append((description, DAILY_TASK_REWARD))
    save_data(send_backup=False)
    return completed


def format_daily_tasks(user_id, user_tag):
    tasks, econ = get_daily_tasks(user_id, user_tag)
    weekdays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    active = is_nya_pass_active(user_id, user_tag)
    lines = [f'🎟 <b>Ежедневные задания Ня-Пасса — {weekdays[datetime.now().weekday()]}</b>', '',
             ('🟢 Ня-Пасс активен. Задания не требуют реста. За каждое выполненное задание: <b>+100 🪙</b>.' if active else '🔴 Ня-Пасс не активен. Купите его в магазине, чтобы выполнять задания.'), '']
    for key, description, target in tasks:
        current = min(econ.get('daily_progress', {}).get(key, 0), target)
        done = key in econ.get('daily_claimed', [])
        status = '✅' if done else '🔄'
        lines.append(f'{status} {description}: <b>{current}/{target}</b>')
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
    """Нормализует текст: удаляет спецсимволы, точки, пробелы и заменяет латиницу на кириллицу"""
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

def make_link(chat_id, user_name, user_id=None):
    name = clean_tag(user_name)
    badge_str = ""
    title_str = ""
    user_econ = get_user_econ(user_id, user_name)
    if user_econ.get('badge'):
        badge_str = f" [{user_econ['badge']}]"
    active_title = user_econ.get('active_title')
    if active_title in TITLES:
        title_str = f" [{TITLES[active_title]['text']}]"

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
        return target_user, None, raw_args

    if '|' in body:
        parts = body.split('|')
        potential_name = parts[-1].strip()
        if not re.search(r'\d', potential_name) and len(potential_name.split()) == 1:
            target_user = clean_tag(potential_name)
            raw_args = '|'.join(parts[:-1]).strip()
            return target_user, None, raw_args

    words = body.split()
    if len(words) > 1:
        if not re.search(r'\d', words[-1]):
            target_user = clean_tag(words[-1])
            raw_args = ' '.join(words[:-1]).strip()
            return target_user, None, raw_args

    return None, None, body

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
    
    if clean_user == '8' or clean_user.isdigit():
        return False, 0
        
    seconds = parse_duration_to_seconds(duration_text, chat_id)
    end_time = (time.time() + seconds) if seconds else None
    db['rests'][str_chat][clean_user] = {
        'duration': duration_text,
        'reason': reason,
        'end_time': end_time,
        'user_id': target_user_id,
    }
    add_to_history(str_chat, clean_user, duration_text, reason, target_user_id)
    
    # ПРОВЕРКА ЛИМИТА: Максимум 5 раз по 150 коинов НАВСЕГДА
    econ = get_user_econ(target_user_id, clean_user)
    reward_given = False
    if econ['rest_rewards_count'] < 5:
        econ['balance'] += 150
        econ['rest_rewards_count'] += 1
        reward_given = True
    
    save_data()
    log_event('РЕСТ', f'Чат: <code>{chat_id}</code>\nПользователь: {make_link(chat_id, clean_user, target_user_id)}\nСрок: <b>{duration_text}</b>\nПричина: {reason}')
    if end_time:
        schedule_rest_timers(chat_id, clean_user, end_time, target_user_id)
        
    return reward_given, econ['rest_rewards_count']

# ---------------------------------------------------------
# ПРИВЕТСТВИЕ И ПРОЩАНИЕ (ВХОД / ВЫХОД ИЗ ЧАТА)
# ---------------------------------------------------------
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_members(message):
    for member in message.new_chat_members:
        user_link = make_link(message.chat.id, member.username or member.first_name, member.id)
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
    user_link = make_link(message.chat.id, member.username or member.first_name, member.id)
    farewell_text = f"👋 <b>{user_link}</b> покинул(а) наш чат. Пожелаем удачи! 🌸"
    bot.send_message(message.chat.id, farewell_text, parse_mode='HTML')

# ---------------------------------------------------------
# ОБРАБОТЧИКИ КОМАНД И ПОЛНОЕ ОПИСАНИЕ БОТА
# ---------------------------------------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    help_text = (
        '🤖 <b>НЯ-БОТ — ПОЛНЫЙ СПИСОК ВОЗМОЖНОСТЕЙ</b>\n\n'
        '🌴 <b>РЕСТЫ</b>\n'
        '• <code>+рест 3 дня | отпуск @username</code> — выдать рест. Можно также ответить на сообщение.\n'
        '• <code>-рест @username</code> — снять рест.\n'
        '• <code>+продлить 2 часа @username</code> — продлить рест.\n'
        '• <code>причина @username новая причина</code> — изменить причину.\n'
        '• <code>запрос рест 3 дня | причина</code> — отправить запрос админу.\n'
        '• <code>кто @username</code> / <code>кто ты @username</code> / <code>кто такой @username</code> — проверить рест.\n'
        '• <code>кто 123456789</code> — проверка по цифровому ID.\n'
        '• <code>ресты</code> — активные ресты.\n'
        '• <code>мой рест</code> — информация о вашем ресте.\n'
        '• <code>топ</code> / <code>статистика</code> — статистика рестов.\n\n'

        '💰 <b>НЯ-КОИНЫ И ПРОФИЛЬ</b>\n'
        '• <code>бонус</code> / <code>/bonus</code> — от 1 до 100 🪙 раз в час.\n'
        '• <code>баланс</code> / <code>/balance</code> — ваш баланс.\n'
        '• <code>профиль</code> / <code>инвентарь</code> — профиль, значки, титулы и трофеи.\n'
        '• <code>+смехуятинка</code> — ответом на сообщение дать +1 очко.\n'
        '• <code>промокод КОД</code> — активировать промокод.\n'
        '• <code>/pay @username 100</code> / <code>передать @username 100</code> / <code>перевод @username 100</code> — передать коины.\n\n'

        '🎰 <b>АЗАРТНЫЕ ИГРЫ</b>\n'
        '• <code>кости 100</code> / <code>/dice 100</code> — сыграть в кости.\n'
        '• <code>слоты 100</code> / <code>/slots 100</code> — испытать слоты.\n'
        '• <code>рулетка 100</code> / <code>/roulette 100</code> — рулетка.\n\n'

        '🎣 <b>РЫБАЛКА И ОХОТА</b>\n'
        '• <code>рыбалка</code> / <code>/fish</code> — поймать рыбу, КД 2 часа.\n'
        '• <code>охота</code> / <code>/hunt</code> — получить охотничий трофей, КД 2 часа.\n'
        '• Все трофеи сохраняются в вашем профиле.\n\n'

        '🎟 <b>НЯ-ПАСС И ЕЖЕДНЕВНЫЕ ЗАДАНИЯ</b>\n'
        '• <code>задания</code> / <code>ня-пасс</code> — задания текущего дня.\n'
        '• Задания меняются каждый день недели.\n'
        '• Для выполнения заданий не требуется находиться в ресте — нужен активный Ня-Пасс.\n'
        '• За каждое выполненное задание: <b>+100 🪙</b>.\n\n'

        '🧠 <b>РАЗВЛЕЧЕНИЯ И СТАТИСТИКА</b>\n'
        '• <code>айкью</code> / <code>iq</code> — изменить IQ, КД 30 минут.\n'
        '• <code>жир</code> / <code>жирок</code> — измерить жир, КД 30 минут.\n'
        '• <code>пятка</code> / <code>пяточка</code> — измерить пятку, КД 20 минут.\n'
        '• <code>топ богачей</code> — топ по коинам.\n'
        '• <code>топ iq</code> — топ по IQ.\n'
        '• <code>топ жира</code> — топ по жиру.\n'
        '• <code>топ пяток</code> — топ по размеру пятки.\n\n'

        '🏪 <b>МАГАЗИН</b>\n'
        '• <code>магазин</code> — открыть магазин.\n'
        '• 🎟 Ня-Пасс — 500 🪙 на 7 дней.\n'
        '• 🏷 Титулы: 👑 Кинг, 💤 Соня, 🔥 Легенда, 🐉 Дракон, 🥐 Булочка.\n'
        '• ✨ Значки — покупаются и надеваются через профиль.\n\n'

        '💬 <b>АВТООТВЕТЫ</b>\n'
        '• Бот реагирует на приветствия, «семпай», «ня», «охаё», «даттебайо», «кавай», «аригато» и другие фразы.\n'
        '• Есть фильтр мата и оскорблений.\n\n'

        '⚙️ <b>ДЛЯ АДМИНОВ</b>\n'
        '• <code>/settings</code> — настройки чата.\n'
        '• <code>/export</code> — экспорт истории рестов в CSV.\n'
        '• <code>отчет</code> — аналитика по рестам.\n'
        '• <code>логи</code> — последние ресты в текущем чате.\n\n'
        '💡 <b>Совет:</b> большинство команд можно использовать как обычным текстом, так и через указанные slash-команды.'
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
    
    rest_rewards = econ.get('rest_rewards_count', 0)
    rest_rewards_str = f"{rest_rewards}/5 (150 🪙)" if rest_rewards < 5 else "5/5 (Лимит бонусов исчерпан ⛔️)"

    text = (
        f"🌐 <b>Единый Профиль: {make_link(chat_id, user_tag, user_id)}</b>\n"
        f"<i>(Статистика синхронизирована во всех чатах и ЛС)</i>\n\n"
        f"💵 Баланс: <b>{econ['balance']} Ня-коинов 💸</b>\n"
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

    markup = InlineKeyboardMarkup()
    
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

    # Любое сообщение засчитывается в дневное задание сообщений.
    completed_tasks = track_daily_task(user_id, user_tag, 'messages', 1)
    if completed_tasks:
        for task_name, reward in completed_tasks:
            try:
                bot.send_message(chat_id, f'🎉 {make_link(chat_id, user_tag, user_id)} выполнил(а) задание Ня-Пасса: <b>{task_name}</b>! +{reward} 🪙', parse_mode='HTML')
            except Exception:
                pass

    # --- НОВАЯ ФУНКЦИЯ: "Кто ты [юзер/айди]" (ПРОВЕРКА РЕСТА ЧЕЛОВЕКА) ---
    who_match = re.search(r'^(?:кто\s+ты|кто\s+такой|кто|что\s+за)\s+(?:@([a-zA-Z0-9_]{1,32})|(\d{5,20}))\s*$', text_lower)
    if who_match:
        target_str = clean_tag(who_match.group(1) or who_match.group(2))
        
        # Поиск информации в текущем чате или по всем чатам
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
            user_link = make_link(chat_id, target_found_tag, target_found_id)
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

    # 1. ПРОВЕРКА ВСЕГДА АКТИВНЫХ СЛОВ (Мама, Охаё, Аниме, Кавай, Семпай)
    triggered = False
    for pattern, responses in ALWAYS_ACTIVE_PATTERNS.items():
        if re.search(pattern, text_lower, re.IGNORECASE):
            bot.reply_to(message, random.choice(responses))
            triggered = True
            break

    # 2. ПРОВЕРКА НА МАТ И СЛОВО КОЧ (Усиленный фильтр с нормализацией символов)
    if not triggered and not is_nya_pass_active(user_id, user_tag):
        normalized_text = normalize_text_for_bad_words(text)
        for pattern, responses in MUTABLE_BAD_WORDS_PATTERNS.items():
            if re.search(pattern, normalized_text, re.IGNORECASE) or re.search(pattern, text_lower, re.IGNORECASE):
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

    # --- КОМАНДА СМЕХУЯТИНКА ---
    if text_lower in ['+смехуятинка', 'смехуятинка']:
        if message.reply_to_message:
            target_u = message.reply_to_message.from_user
            target_tag = clean_tag(target_u.username or target_u.first_name)
            target_id = target_u.id
            
            econ = get_user_econ(target_id, target_tag)
            econ['smeh'] = econ.get('smeh', 0) + 1
            save_data()
            
            u_link = make_link(chat_id, target_tag, target_id)
            bot.reply_to(message, f"😂 Пользователю {u_link} начислено +1 очко <b>Смехуятинки</b>!\nВсего очков: <b>{econ['smeh']}</b>", parse_mode='HTML')
        else:
            bot.reply_to(message, "❌ Ответьте этой командой на сообщение человека, которому хотите начислить смехуятинку!")
        return

    # --- СИМУЛЯТОР АЙКЬЮ (С КД 30 МИНУТ) ---
    elif text_lower in ['айкью', 'iq', 'iqи', 'айкю']:
        econ = get_user_econ(user_id, user_tag)
        now_ts = time.time()
        cooldown = 1800  # КД 30 минут (1800 секунд)
        
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
        completed = track_daily_task(user_id, user_tag, 'iq', 1)
        
        sign = "+" if change >= 0 else ""
        bot.reply_to(message, f"🧠 {make_link(chat_id, user_tag, user_id)}, ваш тест на IQ завершен!\nИзменение: <b>{sign}{change} IQ</b>\nТекущий уровень интеллекта: <b>{econ['iq']} IQ 📊</b>", parse_mode='HTML')
        for task_name, task_reward in completed:
            bot.send_message(chat_id, f'🎉 Задание Ня-Пасса выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        return

    # --- СИМУЛЯТОР ЖИРА (С КД 30 МИНУТ) ---
    elif text_lower in ['жир', 'жирок', 'жирность', 'процент жира']:
        econ = get_user_econ(user_id, user_tag)
        now_ts = time.time()
        cooldown = 1800  # КД 30 минут (1800 секунд)
        
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
        completed = track_daily_task(user_id, user_tag, 'fat', 1)
        
        sign = "+" if change >= 0 else ""
        bot.reply_to(message, f"🥩 {make_link(chat_id, user_tag, user_id)}, сканирование жирового слоя завершено!\nИзменение: <b>{sign}{change}%</b>\nТекущий процент жира: <b>{econ['fat']}% 🍔</b>", parse_mode='HTML')
        for task_name, task_reward in completed:
            bot.send_message(chat_id, f'🎉 Задание Ня-Пасса выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        return

    # --- СИМУЛЯТОР ПЯТКИ (С КД 20 МИНУТ) ---
    elif text_lower in ['пятка', 'пяточка', 'размер пятки', 'пятки']:
        econ = get_user_econ(user_id, user_tag)
        now_ts = time.time()
        cooldown = 1200  # КД 20 минут (1200 секунд)
        
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
        bot.reply_to(message, f"🦶 {make_link(chat_id, user_tag, user_id)}, замер вашей пятки завершен!\nИзменение: <b>{sign}{change} см</b>\nТекущий размер пятки: <b>{econ['foot_size']} см 🦶</b>", parse_mode='HTML')
        return

    # --- БЛОК ГЛОБАЛЬНЫХ ТОПОВ И СТАТИСТИКИ ---
    elif text_lower in ['топ жира', 'топ жирных', 'топ по жиру']:
        if 'economy' in db and db['economy']:
            sorted_fat = sorted(db['economy'].items(), key=lambda x: x[1].get('fat', 0), reverse=True)
            resp = "🌐 <b>Глобальный топ участников по проценту жира:</b>\n\n"
            for idx, (k, info) in enumerate(sorted_fat[:10], 1):
                u_name = info.get('display_name', 'Пользователь')
                u_id = info.get('user_id')
                resp += f"{idx}. {make_link(chat_id, u_name, u_id)} — <b>{info.get('fat', 20)}%</b>\n"
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
                resp += f"{idx}. {make_link(chat_id, u_name, u_id)} — <b>{info.get('iq', 100)} IQ</b>\n"
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
                resp += f"{idx}. {make_link(chat_id, u_name, u_id)} — <b>{info.get('foot_size', 25)} см</b>\n"
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
                resp += f"{idx}. {make_link(chat_id, u_name, u_id)} — <b>{info.get('balance', 0)} 🪙</b>\n"
            bot.reply_to(message, resp, parse_mode='HTML')
        else:
            bot.reply_to(message, "🪙 Статистика коинов пока пуста.")
        return

    # --- БЛОК НЯ-КОИНОВ И ИНВЕНТАРЯ ---
    if text_lower in ['баланс', '/balance', 'коины', 'ня-коины']:
        econ = get_user_econ(user_id, user_tag)
        bot.reply_to(
            message,
            f"💵 <b>Ваш единый кошелек {make_link(chat_id, user_tag, user_id)}:</b>\n"
            f"• Баланс: <b>{econ['balance']} Ня-коинов 💸</b>",
            parse_mode='HTML'
        )
        return

    elif text_lower in ['инвентарь', 'профиль', '/profile', 'мои значки']:
        send_user_profile(chat_id, user_tag, user_id, message)
        return

    elif text_lower in ['бонус', '/bonus', 'коин', 'собрать']:
        econ = get_user_econ(user_id, user_tag)
        now_ts = time.time()
        if now_ts - econ.get('last_hourly', 0) >= 3600:
            reward = random.randint(1, 100)
            econ['balance'] += reward
            econ['last_hourly'] = now_ts
            save_data()
            completed = track_daily_task(user_id, user_tag, 'bonus', 1)
            bot.reply_to(message, f"🎲 Вы собрали: <b>+{reward} Ня-коинов 🪙</b>!\nЕдиный баланс: <b>{econ['balance']} 💸</b>", parse_mode='HTML')
            for task_name, task_reward in completed:
                bot.send_message(chat_id, f'🎉 Задание Ня-Пасса выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        else:
            left_sec = 3600 - (now_ts - econ.get('last_hourly', 0))
            minutes = int(left_sec // 60)
            seconds = int(left_sec % 60)
            bot.reply_to(message, f"⏳ Можно собирать коины каждый час! Следующий сбор через: <b>{minutes} мин {seconds} сек</b>.", parse_mode='HTML')
        return

    # --- ЕЖЕДНЕВНЫЕ ЗАДАНИЯ НЯ-ПАССА ---
    elif text_lower in ['задания', 'ня-пасс', 'ня пасс', 'daily']:
        bot.reply_to(message, format_daily_tasks(user_id, user_tag), parse_mode='HTML')
        return

    # --- КОСТИ ---
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
        completed = track_daily_task(user_id, user_tag, 'dice', 1)
        bot.reply_to(message, result + f"\n💰 Баланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
        for task_name, task_reward in completed:
            bot.send_message(chat_id, f'🎉 Задание Ня-Пасса выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        return

    # --- СЛОТЫ ---
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
                econ['balance += win'] if False else None
                econ['balance'] += win
                result += f'\n✨ Две одинаковых! Выигрыш <b>+{win} 🪙</b>!'
            else:
                econ['balance'] -= bet
                result += f'\n💸 Проигрыш <b>{bet} 🪙</b>.'
        save_data()
        completed = track_daily_task(user_id, user_tag, 'slots', 1)
        bot.reply_to(message, result + f"\n💰 Баланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
        for task_name, task_reward in completed:
            bot.send_message(chat_id, f'🎉 Задание Ня-Пасса выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        return

    # --- РУЛЕТКА ---
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
        bot.reply_to(message, result + f"\n💰 Баланс: <b>{econ['balance']} 🪙</b>", parse_mode='HTML')
        return

    # --- РЫБАЛКА ---
    elif text_lower in ['рыбалка', '/fish', 'рыба', 'fish']:
        econ = get_user_econ(user_id, user_tag)
        left = cooldown_text(econ.get('last_fish_time', 0), 7200)
        if left:
            bot.reply_to(message, f'⏳ Рыбалка доступна раз в 2 часа. Осталось: <b>{left}</b>.', parse_mode='HTML')
            return
        catches = [
            ('🐟 Карась', 1), ('🐠 Окунь', 1), ('🐡 Щука', 1),
            ('🦀 Краб', 1), ('🐙 Осьминог', 1), ('🦐 Креветка', 1)
        ]
        catch, count = random.choice(catches)
        econ['last_fish_time'] = time.time()
        add_inventory_item(econ['fish_inventory'], catch)
        econ['balance'] += random.randint(5, 30)
        save_data()
        completed = track_daily_task(user_id, user_tag, 'fish', 1)
        bot.reply_to(message, f'🎣 Вы поймали: <b>{catch}</b>!\n🪙 Бонус за улов: начислен в баланс.\n🐟 Инвентарь: <b>{catch} × {econ["fish_inventory"][catch]}</b>', parse_mode='HTML')
        for task_name, task_reward in completed:
            bot.send_message(chat_id, f'🎉 Задание Ня-Пасса выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        return

    # --- ОХОТА ---
    elif text_lower in ['охота', '/hunt', 'hunt']:
        econ = get_user_econ(user_id, user_tag)
        left = cooldown_text(econ.get('last_hunt_time', 0), 7200)
        if left:
            bot.reply_to(message, f'⏳ Охота доступна раз в 2 часа. Осталось: <b>{left}</b>.', parse_mode='HTML')
            return
        trophies = [('🦌 Олень', 1), ('🐗 Кабан', 1), ('🦊 Лиса', 1), ('🐺 Волк', 1), ('🐇 Заяц', 1)]
        trophy, count = random.choice(trophies)
        econ['last_hunt_time'] = time.time()
        add_inventory_item(econ['hunt_inventory'], trophy)
        econ['balance'] += random.randint(10, 40)
        save_data()
        completed = track_daily_task(user_id, user_tag, 'hunt', 1)
        bot.reply_to(message, f'🏹 Охота успешна! Трофей: <b>{trophy}</b> × {econ["hunt_inventory"][trophy]}\n🪙 Награда за охоту начислена в баланс.', parse_mode='HTML')
        for task_name, task_reward in completed:
            bot.send_message(chat_id, f'🎉 Задание Ня-Пасса выполнено: <b>{task_name}</b>! +{task_reward} 🪙', parse_mode='HTML')
        return

    # --- ПРОМОКОДЫ ---
    elif text_lower.startswith('промокод') or text_lower.startswith('/promo'):
        match = re.search(r'(?:промокод|/promo)\s+(.+)', text, re.IGNORECASE)
        if match:
            code = match.group(1).strip().upper()
            
            # Промокод для администратора
            if code == 'ADMIN1000':
                if user_username == ADMIN_USERNAME:
                    add_coins(user_id, user_tag, 1000)
                    bot.reply_to(message, "🎁 <b>Разработчик активировал секретный промокод!</b>\nВам начислено +1000 Ня-коинов 🪙!", parse_mode='HTML')
                else:
                    bot.reply_to(message, "❌ Этот промокод только для администратора/разработчика проекта!")
            
            # Общий промокод на 400 коинов
            elif code in ['NYA400', '400']:
                if 'promos' not in db:
                    db['promos'] = {}
                if 'NYA400' not in db['promos']:
                    db['promos']['NYA400'] = []

                user_key = get_global_user_key(user_id, user_tag)
                if user_key in db['promos']['NYA400']:
                    bot.reply_to(message, "❌ Вы уже активировали этот промокод!")
                else:
                    db['promos']['NYA400'].append(user_key)
                    add_coins(user_id, user_tag, 400)
                    save_data()
                    bot.reply_to(message, "🎉 <b>Промокод успешно активирован!</b>\nВам начислено <b>+400 Ня-коинов 🪙</b>!", parse_mode='HTML')
            else:
                bot.reply_to(message, "❌ Неверный промокод!")
        else:
            bot.reply_to(message, "❌ Формат: <code>промокод NYA400</code>", parse_mode='HTML')
        return

    elif text_lower.startswith(('перевод', 'передать', '/pay')):
        match = re.search(r'(?:перевод|передать|/pay)\s+@?(\w+)\s+(\d+)', text, re.IGNORECASE)
        if match:
            target_u = clean_tag(match.group(1))
            amount = int(match.group(2))
            
            if amount <= 0:
                bot.reply_to(message, "❌ Сумма перевода должна быть больше 0!")
                return
                
            sender_econ = get_user_econ(user_id, user_tag)
            if sender_econ['balance'] < amount:
                bot.reply_to(message, "❌ У вас недостаточно Ня-коинов для перевода!")
                return
                
            sender_econ['balance'] -= amount
            add_coins(None, target_u, amount)
            save_data()
            completed = track_daily_task(user_id, user_tag, 'transfer', amount)
            log_event('ПЕРЕВОД', f'Отправитель: {make_link(chat_id, user_tag, user_id)}\nПолучатель: {make_link(chat_id, target_u)}\nСумма: <b>{amount} 🪙</b>')
            bot.reply_to(message, f"💸 Вы успешно перевели <b>{amount} 🪙</b> пользователю {make_link(chat_id, target_u)}!", parse_mode='HTML')
            for task_name, reward in completed:
                bot.send_message(chat_id, f'🎉 Задание Ня-Пасса выполнено: <b>{task_name}</b>! +{reward} 🪙', parse_mode='HTML')
        else:
            bot.reply_to(message, "❌ Формат: <code>/pay @username 50</code> или <code>передать @username 50</code>", parse_mode='HTML')
        return

    elif text_lower in ['магазин', 'лавка', 'shop']:
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton('🎟 Ня-Пасс от мата (500 🪙)', callback_data='buy_nya_pass')
        )
        markup.add(
            InlineKeyboardButton('👑 Кинг (2500 🪙)', callback_data='buy_title_king'),
            InlineKeyboardButton('💤 Соня (1800 🪙)', callback_data='buy_title_sonya')
        )
        markup.add(
            InlineKeyboardButton('🔥 Легенда (3000 🪙)', callback_data='buy_title_legend'),
            InlineKeyboardButton('🐉 Дракон (3500 🪙)', callback_data='buy_title_dragon')
        )
        markup.add(InlineKeyboardButton('🥐 Булочка (1500 🪙)', callback_data='buy_title_bun'))
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
        
        pass_status = "❌ Не куплен"
        if is_nya_pass_active(user_id, user_tag):
            pass_status = "✅ Активен"

        bot.reply_to(
            message,
            "🏪 <b>Глобальная Лавка Ня-коинов и Значков:</b>\n\n"
            "🎟 <b>Ня-Пасс от мата (на 1 неделю) — 500 🪙</b>\n"
            f"• Статус пасса: <b>{pass_status}</b>\n\n"
            "✨ <b>Значки и смайлы для профиля и топов:</b>\n"
            "• 🌟 Звезда — 100 🪙 | 🍡 Данго — 150 🪙\n"
            "• 🐾 Лапка — 200 🪙 | 💖 Сердечко — 200 🪙\n"
            "• 🔥 Огонек — 250 🪙 | ⚡️ Молния — 300 🪙\n"
            "• 👑 Корона — 300 🪙 | 🍀 Клевер — 350 🪙\n"
            "• 🌸 Сакура — 400 🪙 | 💎 Бриллиант — 500 🪙\n"
            "• 💀 Череп — 600 🪙 | 🚀 Ракета — 700 🪙\n"
            "• 🦊 Лисичка — 800 🪙 | 👽 Инопланетянин — 900 🪙\n"
            "• 🦄 Единорог — 1000 🪙 | 🐉 Дракон — 1500 🪙\n"
            "• 👻 Призрак — 2000 🪙 | 🦶 Пятка — 3000 🪙\n\n"
            "Выбери товар кнопкой ниже:",
            reply_markup=markup,
            parse_mode='HTML'
        )
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
            
            reward_given, count = apply_rest(chat_id, target_user, duration_text, reason, target_user_id)
            user_link = make_link(chat_id, target_user, target_user_id)
            
            coin_msg = f"\n🪙 Выдано +150 Ня-коинов за рест! ({count}/5)" if reward_given else f"\n⛔️ Лимит бонусов за рест исчерпан ({count}/5)!"
            bot.reply_to(message, f'✅ Рест для {user_link} добавлен!\n⏱ Срок: {duration_text}\n📝 Причина: {reason}{coin_msg}', parse_mode='HTML')
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
                log_event('СНЯТИЕ РЕСТА', f'Админ: {make_link(chat_id, user_tag, user_id)}\nПользователь: {user_link}')
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
        econ = get_user_econ(user_id, user_tag)
        if econ['balance'] < 500:
            bot.answer_callback_query(call.id, '❌ Недостаточно Ня-коинов! Нужно 500 🪙', show_alert=True)
            return
        
        econ['balance'] -= 500
        current_time = time.time()
        base_time = max(current_time, econ.get('nya_pass_until', 0))
        econ['nya_pass_until'] = base_time + 604800  # 7 дней
        econ['nya_pass_enabled'] = True
        save_data()
        
        bot.answer_callback_query(call.id, '🎉 Вы успешно купили Ня-Пасс от мата на 1 неделю!', show_alert=True)
        log_event('ПОКУПКА', f'Пользователь: {make_link(chat_id, user_tag, user_id)}\nТовар: <b>Ня-Пасс</b>\nЦена: <b>500 🪙</b>')
        bot.send_message(
            chat_id, 
            f"🎟 Пользователь {make_link(chat_id, user_tag, user_id)} купил <b>Ня-Пасс от мата</b> на 7 дней! Бот не будет замечать мат и слово 'коч' от него в течение недели.",
            parse_mode='HTML'
        )

    # --- ПОКУПКА КАСТОМНЫХ ТИТУЛОВ ---
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
            log_event('ПОКУПКА', f'Пользователь: {make_link(chat_id, user_tag, user_id)}\nТовар: <b>{item["text"]}</b>\nЦена: <b>{item["price"]} 🪙</b>')
            bot.answer_callback_query(call.id, f"🎉 Титул {item['text']} куплен и надет!", show_alert=True)
            send_user_profile(chat_id, user_tag, user_id)

    # --- ПОКУПКА СМАЙЛИКОВ/ЗНАЧКОВ ---
    elif call.data.startswith('buy_badge_'):
        badge_key = call.data.replace('buy_badge_', '')
        if badge_key in BADGES:
            item = BADGES[badge_key]
            econ = get_user_econ(user_id, user_tag)
            
            if item['emoji'] in econ.get('inventory', []):
                bot.answer_callback_query(call.id, f"У вас уже есть значок {item['emoji']}! Вы можете надеть его в профиле.", show_alert=True)
                return

            if econ['balance'] < item['price']:
                bot.answer_callback_query(call.id, f"❌ Недостаточно Ня-коинов! Нужно {item['price']} 🪙", show_alert=True)
                return

            econ['balance'] -= item['price']
            if item['emoji'] not in econ['inventory']:
                econ['inventory'].append(item['emoji'])
            econ['badge'] = item['emoji']
            save_data()

            log_event('ПОКУПКА', f'Пользователь: {make_link(chat_id, user_tag, user_id)}\nТовар: <b>{item["emoji"]}</b>\nЦена: <b>{item["price"]} 🪙</b>')
            bot.answer_callback_query(call.id, f"🎉 Вы купили значок {item['emoji']}! Он добавлен в ваш инвентарь.", show_alert=True)
            bot.send_message(
                chat_id,
                f"✨ Пользователь {make_link(chat_id, user_tag, user_id)} приобрел кастомный значок <b>{item['emoji']}</b> в магазине!",
                parse_mode='HTML'
            )

    # --- СМЕНА И УПРАВЛЕНИЕ ТИТУЛАМИ ---
    elif call.data.startswith('set_title_'):
        title_key = call.data.replace('set_title_', '')
        econ = get_user_econ(user_id, user_tag)
        if title_key in econ.get('titles', []) and title_key in TITLES:
            econ['active_title'] = title_key
            save_data()
            bot.answer_callback_query(call.id, f"✅ Вы надели титул {TITLES[title_key]['text']}!", show_alert=True)
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except Exception:
                pass
            send_user_profile(chat_id, user_tag, user_id)

    elif call.data == 'remove_title':
        econ = get_user_econ(user_id, user_tag)
        econ['active_title'] = None
        save_data()
        bot.answer_callback_query(call.id, '❌ Титул снят!', show_alert=True)
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        send_user_profile(chat_id, user_tag, user_id)

    # --- СМЕНА И УПРАВЛЕНИЕ ЗНАЧКАМИ В ИНВЕНТАРЕ ---
    elif call.data.startswith('set_badge_'):
        selected_emoji = call.data.replace('set_badge_', '')
        econ = get_user_econ(user_id, user_tag)
        if selected_emoji in econ.get('inventory', []):
            econ['badge'] = selected_emoji
            save_data()
            bot.answer_callback_query(call.id, f"✅ Вы успешно надели значок {selected_emoji}!", show_alert=True)
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except Exception:
                pass
            send_user_profile(chat_id, user_tag, user_id)

    elif call.data == 'remove_badge':
        econ = get_user_econ(user_id, user_tag)
        econ['badge'] = None
        save_data()
        bot.answer_callback_query(call.id, "❌ Значок снят!", show_alert=True)
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        send_user_profile(chat_id, user_tag, user_id)

    # --- ВКЛЮЧЕНИЕ / ВЫКЛЮЧЕНИЕ НЯ-ПАССА ---
    elif call.data == 'toggle_nya_pass':
        econ = get_user_econ(user_id, user_tag)
        econ['nya_pass_enabled'] = not econ.get('nya_pass_enabled', True)
        save_data()
        status_msg = "включен" if econ['nya_pass_enabled'] else "выключен"
        bot.answer_callback_query(call.id, f"⚙️ Ня-Пасс {status_msg}!", show_alert=True)
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        send_user_profile(chat_id, user_tag, user_id)

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

        reward_given, count = apply_rest(chat_id, target_user, duration_text, reason, target_user_id)
        admin_link = make_link(chat_id, call.from_user.username or call.from_user.first_name, user_id)
        user_link = make_link(chat_id, target_user, target_user_id)
        
        coin_msg = f"\n🪙 Начислено +150 Ня-коинов ({count}/5)!" if reward_given else f"\n⛔️ Награда не начислена: достигнут лимит 5/5!"
        
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

print('Бот успешно запущен...')
bot.infinity_polling() 
