"""Telegram Stars service for NyaBot.

Catalogs and pure purchase/entitlement logic are kept here. Telegram payment
handlers remain in newfile.py until the service layer is fully verified.
"""
import copy
import threading
import time

_db = None
_db_lock = threading.RLock()
_mark_dirty = lambda: None
_get_user = None
_titles = {}
_themes = {}
_pets_data = {}

def configure(*, db, db_lock=None, mark_dirty=None, get_user=None,
              titles=None, themes=None, pets_data=None):
    global _db, _db_lock, _mark_dirty, _get_user, _titles, _themes, _pets_data
    _db = db
    _db_lock = db_lock or threading.RLock()
    _mark_dirty = mark_dirty or (lambda: None)
    _get_user = get_user
    _titles = titles or {}
    _themes = themes or {}
    _pets_data = pets_data or {}

PROFILE_GIFS = {
    'gulya': {
        'name': '🌸 Гуль',
        'price': 4,
        'url': 'https://media1.tenor.com/m/glvYPm3HLN0AAAAd/flower.gif',
        'source_url': 'https://tenor.com/ll3KWzRLUOn.gif',
    },
    'sakura_gif': {
        'name': '🌸 Сакура',
        'price': 3,
        'url': 'https://media1.tenor.com/m/pJ2ItvfaQlQAAAAd/trapxgen.gif',
        'source_url': 'https://tenor.com/oipg5GrIYEi.gif',
    },
    'mogger': {
        'name': '😎 Могер',
        'price': 5,
        'url': 'https://media1.tenor.com/m/sFC5l-YzoQAAAAAd/nikitas-venizelos.gif',
        'source_url': 'https://tenor.com/piGyaE6af6a.gif',
    },
    'cat': {
        'name': '🐈 Кот',
        'price': 2,
        'url': 'https://media1.tenor.com/m/gY02kH2GWL4AAAAd/cat-city.gif',
        'source_url': 'https://tenor.com/lhLnkKMfDNG.gif',
    },
}

STARS_COIN_PACKS = {
    'coins_1_star': {'name': '💰 35,000 Ня-коинов', 'coins': 35000, 'stars': 1, 'desc': 'Стартовый мешочек коинов — всего 1 ⭐️'},
    'coins_3_stars': {'name': '💵 100,000 Ня-коинов', 'coins': 100000, 'stars': 3, 'desc': 'Народный пак: 100к коинов всего за 3 ⭐️!'},
    'coins_5_stars': {'name': '💳 200,000 Ня-коинов', 'coins': 200000, 'stars': 5, 'desc': 'Крупный капитал для предприятий и бизнеса'},
    'coins_10_stars': {'name': '🏦 500,000 Ня-коинов', 'coins': 500000, 'stars': 10, 'desc': 'Капитал магната для покорения биржи и топов'},
    'coins_20_stars': {'name': '💎 1,200,000 Ня-коинов', 'coins': 1200000, 'stars': 20, 'desc': 'Миллионный фонд для абсолютного богатства'}
}

STARS_VIP_PASS = {
    'pass_7_days': {'name': '⭐️ VIP Nya Pass (7 дней)', 'days': 7, 'stars': 3, 'desc': '-35% кулдаунов, 2.25x /bonus, +10% к работе и бизнесу, +25% EXP, защита от ограблений'},
    'pass_30_days': {'name': '⭐️ VIP Nya Pass (30 дней)', 'days': 30, 'stars': 5, 'desc': 'Месяц VIP: -35% кулдаунов, 2.25x /bonus, +10% работа/бизнес, +25% EXP'},
    'pass_forever': {'name': '👑 VIP Nya Pass НАВСЕГДА', 'days': -1, 'stars': 20, 'desc': 'Пожизненный VIP: -35% кулдаунов, 2.25x /bonus, +10% работа/бизнес, +25% EXP, защита навсегда'}
}

VIP_BADGES = {
    'vip_badge_crown': {'name': 'Корона VIP', 'emoji': '👑', 'stars': 4, 'desc': 'Символ элиты чата'},
    'vip_badge_star': {'name': 'Звезда Покровителя', 'emoji': '⭐️', 'stars': 4, 'desc': 'Знак поддержки бота'},
    'vip_badge_gem': {'name': 'Сияющий Алмаз', 'emoji': '💎', 'stars': 4, 'desc': 'Драгоценный статус'},
    'vip_badge_angel': {'name': 'Крылья Ангела', 'emoji': '🪽', 'stars': 5, 'desc': 'Светлый хранитель'},
    'vip_badge_galaxy': {'name': 'Космос', 'emoji': '🌌', 'stars': 5, 'desc': 'Межгалактический покровитель'},
    'vip_badge_dragon': {'name': 'Дракон Империи', 'emoji': '🐲', 'stars': 5, 'desc': 'Мощь древнего дракона'}
}

DONOR_VEHICLES = {
    'donor_lambo': {'name': '🏎 Lamborghini Aventador SVJ VIP', 'short': '🏎 Lambo VIP', 'stars': 8, 'cd_cut': 0.34, 'desc': '-34% ко всем таймерам', 'tier': 15, 'donor_only': True},
    'donor_batmobile': {'name': '🦇 Batmobile Nya Edition', 'short': '🦇 Batmobile', 'stars': 12, 'cd_cut': 0.42, 'desc': '-42% ко всем таймерам', 'tier': 16, 'donor_only': True},
    'donor_ufo': {'name': '🛸 НЛО Императора Ня', 'short': '🛸 НЛО', 'stars': 18, 'cd_cut': 0.50, 'desc': '-50% ко всем таймерам', 'tier': 17, 'donor_only': True},
}

DONOR_BUSINESSES = {
    'donor_nightclub': {'name': '💎 VIP Ночной клуб', 'stars': 8, 'base_income': 4500, 'upgrade_cost': 3500, 'desc': 'Премиальный бизнес: 4,500 🪙/ч'},
    'donor_casino': {'name': '🎰 Императорское казино', 'stars': 12, 'base_income': 8000, 'upgrade_cost': 6000, 'desc': 'Премиальный бизнес: 8,000 🪙/ч'},
    'donor_spacecorp': {'name': '🚀 Космическая корпорация', 'stars': 18, 'base_income': 14000, 'upgrade_cost': 10000, 'desc': 'Премиальный бизнес: 14,000 🪙/ч'},
}

STARS_COSMETICS = {
    'bp_premium': {'name': '🎃 Премиум Хеллоуинский Pass', 'stars': 4, 'type': 'bp_premium', 'desc': 'Открывает премиум-ветку наград, Тыквокота и Тёмную тему!'},
    'custom_title': {'name': '🌟 Сертификат Кастомного Титула', 'stars': 4, 'type': 'title_cert', 'desc': 'Возможность поставить любой свой титул в /custom_title'},
    'title_donor_sponsor': {'name': '💎 Титул: Золотой Спонсор', 'stars': 4, 'type': 'donor_title', 'title_id': 'donor_sponsor', 'desc': '+10% к работе, +10% к /bonus, +5% к прибыли бизнесов'},
    'title_donor_diamond': {'name': '💠 Титул: Алмазный Спонсор', 'stars': 6, 'type': 'donor_title', 'title_id': 'donor_diamond', 'desc': '+15% к работе, +15% к /bonus, +10% к прибыли бизнесов'},
    'title_donor_emperor': {'name': '👑 Титул: Император Доната', 'stars': 8, 'type': 'donor_title', 'title_id': 'donor_emperor', 'desc': '+20% к работе, +20% к /bonus, +15% к прибыли бизнесов'},
    'title_donor_void_lord': {'name': '🕳️ Титул: Властелин Пустоты', 'stars': 7, 'type': 'donor_title', 'title_id': 'donor_void_lord', 'desc': 'Лимит: 5 экземпляров. +35% к работе, +40% к /bonus, +30% к прибыли бизнесов.'},
    'pet_griffin': {'name': '👑 Питомец: Королевский Грифон', 'stars': 5, 'type': 'pet', 'pet_id': 'vip_griffin', 'desc': 'Эксклюзивный питомец (+150% к удаче)'},
    'pet_moon_fox': {'name': '🌙 Питомец: Лунный Фокс', 'stars': 6, 'type': 'pet', 'pet_id': 'moon_fox', 'desc': 'Лимит: 5 экземпляров. Усиленный Stars-питомец с максимальной удачей.'},
    'theme_gold': {'name': '🌟 Тема: Императорское Золото VIP', 'stars': 3, 'type': 'theme', 'theme_id': 'stars_gold', 'desc': 'Роскошная золотая рамка профиля'},
    'theme_anime': {'name': '🎀 Тема: Аниме Люкс VIP', 'stars': 3, 'type': 'theme', 'theme_id': 'stars_anime', 'desc': 'Премиальный аниме стиль профиля'},
    'theme_galaxy': {'name': '🌌 Тема: Бездна Сингулярности VIP', 'stars': 4, 'type': 'theme', 'theme_id': 'stars_galaxy', 'desc': 'Космическая стилистика сингулярности'},
    'theme_moonlit': {'name': '🌙 Тема: Лунная Ночь VIP', 'stars': 5, 'type': 'theme', 'theme_id': 'stars_moonlit', 'desc': 'Лимит: 5 экземпляров. Эксклюзивная постоянная VIP-тема без экономического баффа.'},
    # Донатные значки. Старые vip_badge_* ID оставлены как алиасы ниже,
    # чтобы уже купленные предметы не исчезали после обновления бота.
    'badge_crown': {'name': '👑 Значок: Корона VIP', 'stars': 3, 'type': 'badge', 'emoji': '👑', 'desc': 'VIP значок рядом с ником'},
    'badge_star': {'name': '⭐️ Значок: Звезда Покровителя', 'stars': 3, 'type': 'badge', 'emoji': '⭐️', 'desc': 'Значок спонсора бота'},
    'badge_gem': {'name': '💎 Значок: Сияющий Алмаз', 'stars': 3, 'type': 'badge', 'emoji': '💎', 'desc': 'Драгоценный значок'},
    'badge_angel': {'name': '🪽 Значок: Крылья Ангела', 'stars': 4, 'type': 'badge', 'emoji': '🪽', 'desc': 'Ангельские крылья в чате'},
    'badge_galaxy': {'name': '🌌 Значок: Космос', 'stars': 4, 'type': 'badge', 'emoji': '🌌', 'desc': 'Галактический значок'},
    'badge_dragon': {'name': '🐉 Значок: Дракон Империи', 'stars': 4, 'type': 'badge', 'emoji': '🐉', 'desc': 'Значок дракона'},
    # GIF-профили теперь покупаются только за Telegram Stars. Числа сохранены как цена в ⭐️.
    'gif_gulya': {'name': '🌸 GIF профиля: Гуль', 'stars': 4, 'type': 'gif', 'gif_id': 'gulya', 'desc': 'Анимация, прикреплённая к карточке профиля'},
    'gif_sakura': {'name': '🌸 GIF профиля: Сакура', 'stars': 3, 'type': 'gif', 'gif_id': 'sakura_gif', 'desc': 'Анимация, прикреплённая к карточке профиля'},
    'gif_mogger': {'name': '😎 GIF профиля: Могер', 'stars': 5, 'type': 'gif', 'gif_id': 'mogger', 'desc': 'Анимация, прикреплённая к карточке профиля'},
    'gif_cat': {'name': '🐈 GIF профиля: Кот', 'stars': 2, 'type': 'gif', 'gif_id': 'cat', 'desc': 'Анимация, прикреплённая к карточке профиля'},
    'business_donor_nightclub': {'name': '💎 Донатный бизнес: VIP Ночной клуб', 'stars': 8, 'type': 'donor_business', 'business_id': 'donor_nightclub', 'desc': 'Навсегда: 4,500 🪙/ч'},
    'business_donor_casino': {'name': '🎰 Донатный бизнес: Императорское казино', 'stars': 12, 'type': 'donor_business', 'business_id': 'donor_casino', 'desc': 'Навсегда: 8,000 🪙/ч'},
    'business_donor_spacecorp': {'name': '🚀 Донатный бизнес: Космическая корпорация', 'stars': 18, 'type': 'donor_business', 'business_id': 'donor_spacecorp', 'desc': 'Навсегда: 14,000 🪙/ч'},
    'vehicle_donor_lambo': {'name': '🏎 Донатная машина: Lamborghini VIP', 'stars': 8, 'type': 'donor_vehicle', 'vehicle_id': 'donor_lambo', 'desc': '-34% ко всем таймерам'},
    'vehicle_donor_batmobile': {'name': '🦇 Донатная машина: Batmobile', 'stars': 12, 'type': 'donor_vehicle', 'vehicle_id': 'donor_batmobile', 'desc': '-42% ко всем таймерам'},
    'vehicle_donor_ufo': {'name': '🛸 Донатный транспорт: НЛО Императора', 'stars': 18, 'type': 'donor_vehicle', 'vehicle_id': 'donor_ufo', 'desc': '-50% ко всем таймерам'}
}

STARS_LIMITED_MAX = 5

STARS_HARD_LIMITED_MAX = 5

STARS_HARD_LIMITED_ITEMS = {
    'pet_moon_fox': {'name': '🌙 Питомец: Лунный Фокс'},
    'theme_moonlit': {'name': '🌙 Тема: Лунная Ночь VIP'},
    'title_donor_void_lord': {'name': '🕳️ Титул: Властелин Пустоты'},
}

STARS_LIMITED_ITEMS = {
    'limited_moon_aura': {'name': '🌙 Аура Луны', 'stars': 6, 'type': 'limited_effect', 'emoji': '🌙', 'desc': 'Постоянно доступен в каталоге. Без общего лимита.'},
    'limited_inferno_frame': {'name': '🔥 Рамка Инферно', 'stars': 7, 'type': 'limited_effect', 'emoji': '🔥', 'desc': 'Постоянно доступен в каталоге. Без общего лимита.'},
    'limited_frost_crown': {'name': '❄️ Ледяная Корона', 'stars': 8, 'type': 'limited_effect', 'emoji': '❄️', 'desc': 'Постоянно доступен в каталоге. Без общего лимита.'},
    'limited_galaxy_frame': {'name': '🌌 Рамка Галактики', 'stars': 9, 'type': 'limited_effect', 'emoji': '🌌', 'desc': 'Постоянно доступен в каталоге. Без общего лимита.'},
    'limited_celestial_wings': {'name': '🪽 Небесные Крылья', 'stars': 10, 'type': 'limited_effect', 'emoji': '🪽', 'desc': 'Постоянно доступен в каталоге. Без общего лимита.'},
    'limited_shadow_title': {'name': '🌑 Титул Тени', 'stars': 6, 'type': 'limited_effect', 'emoji': '🌑', 'desc': 'Постоянно доступен в каталоге. Без общего лимита.'},
    'limited_diamond_name': {'name': '💎 Алмазное Имя', 'stars': 8, 'type': 'limited_effect', 'emoji': '💎', 'desc': 'Постоянно доступен в каталоге. Без общего лимита.'},
    'limited_void_eye': {'name': '👁️ Око Пустоты', 'stars': 9, 'type': 'limited_effect', 'emoji': '👁️', 'desc': 'Постоянно доступен в каталоге. Без общего лимита.'},
    'limited_dragon_aura': {'name': '🐉 Аура Дракона', 'stars': 12, 'type': 'limited_effect', 'emoji': '🐉', 'desc': 'Постоянно доступен в каталоге. Без общего лимита.'},
    'limited_comet': {'name': '☄️ Комета', 'stars': 7, 'type': 'limited_effect', 'emoji': '☄️', 'desc': 'Постоянно доступен в каталоге. Без общего лимита.'},
}

STARS_HARD_LIMITED_LOCK = threading.Lock()

def stars_hard_limited_available(item_key):
    if item_key not in STARS_HARD_LIMITED_ITEMS:
        return None
    with STARS_HARD_LIMITED_LOCK:
        sold = _db.setdefault('stars_hard_limited_stock', {})
        try:
            used = int(sold.get(item_key, 0) or 0)
        except (TypeError, ValueError):
            used = 0
            sold[item_key] = 0
        return max(0, STARS_HARD_LIMITED_MAX - used)

def reserve_stars_hard_limited(item_key):
    if item_key not in STARS_HARD_LIMITED_ITEMS:
        return False
    with STARS_HARD_LIMITED_LOCK:
        sold = _db.setdefault('stars_hard_limited_stock', {})
        try:
            used = int(sold.get(item_key, 0) or 0)
        except (TypeError, ValueError):
            used = 0
        if used >= STARS_HARD_LIMITED_MAX:
            return False
        sold[item_key] = used + 1
        _mark_dirty()
        return True

def release_stars_hard_limited(item_key):
    if item_key not in STARS_HARD_LIMITED_ITEMS:
        return
    with STARS_HARD_LIMITED_LOCK:
        sold = _db.setdefault('stars_hard_limited_stock', {})
        try:
            used = int(sold.get(item_key, 0) or 0)
        except (TypeError, ValueError):
            used = 0
        sold[item_key] = max(0, used - 1)
        _mark_dirty()

def stars_limited_stock(item_key):
    sold = _db.setdefault('stars_limited_stock', {})
    try: return max(0, int(sold.get(item_key, 0) or 0))
    except (TypeError, ValueError):
        sold[item_key] = 0; return 0

def stars_limited_available(item_key):
    # Все 10 визуальных эффектов Stars доступны без общего лимита.
    return None if item_key in STARS_LIMITED_ITEMS else 0

def reserve_stars_limited(item_key):
    # Legacy compatibility; global limit is handled only by STARS_HARD_LIMITED_ITEMS.
    return item_key in STARS_LIMITED_ITEMS

def stars_item_is_one_time(item):
    """Косметика, питомцы и pass навсегда покупаются только один раз."""
    if not item:
        return False
    item_type = item.get('type')
    return item_type in {'theme', 'badge', 'pet', 'title_cert', 'donor_title', 'bp_premium', 'gif', 'donor_business', 'donor_vehicle', 'limited_effect'}

def stars_item_owned(econ, kind, item_key):
    if kind == 'vippass':
        return item_key == 'pass_forever' and bool(econ.get('vip_forever'))
    if kind == 'cosm':
        item = STARS_COSMETICS.get(item_key) or STARS_LIMITED_ITEMS.get(item_key)
        if not item:
            return False
        t = item.get('type')
        if t == 'bp_premium':
            return bool(econ.get('bp_premium'))
        if t == 'title_cert':
            return bool(econ.get('has_custom_title_cert'))
        if item_key == 'pet_moon_fox':
            if item_key in econ.get('paid_stars_items', []):
                return True
            pet = econ.get('pet')
            return isinstance(pet, dict) and pet.get('id') == 'moon_fox'
        if item_key == 'theme_moonlit':
            if item_key in econ.get('paid_stars_items', []):
                return True
            return 'stars_moonlit' in (econ.get('purchased_themes', []) or []) or econ.get('profile_theme') == 'stars_moonlit'
        if item_key == 'title_donor_void_lord':
            if item_key in econ.get('paid_stars_items', []):
                return True
            return 'donor_void_lord' in (econ.get('titles', []) or []) or econ.get('active_title') == 'donor_void_lord'
        if t == 'donor_title':
            title_id = item.get('title_id')
            return item_key in econ.get('paid_stars_items', []) or bool(title_id and title_id in (econ.get('titles', []) or []))
        if t == 'theme':
            return item.get('theme_id') in econ.get('purchased_themes', ['default'])
        if t == 'badge':
            return item_key in econ.get('paid_stars_items', [])
        if t == 'pet':
            return item_key in econ.get('paid_stars_items', [])
        if t == 'gif':
            gif_id = item.get('gif_id')
            return bool(gif_id) and gif_id in econ.get('profile_gifs', [])
        if t == 'donor_vehicle':
            vid = item.get('vehicle_id')
            return bool(vid) and vid in econ.get('vehicle_inventory', [])
        if t == 'donor_business':
            bid = item.get('business_id')
            return bool(bid) and bid in econ.get('donor_businesses', {})
        if t == 'limited_effect':
            return item_key in econ.get('paid_stars_items', [])
    return False

def stars_purchase_error(econ, kind, item_key):
    if kind == 'cosm' and item_key in STARS_HARD_LIMITED_ITEMS and stars_hard_limited_available(item_key) <= 0:
        return '❌ Лимит этого предмета уже исчерпан: 5/5 экземпляров.'
    if not stars_item_owned(econ, kind, item_key):
        return None
    if kind == 'vippass':
        return '❌ Вечный VIP уже куплен. Его нельзя купить повторно. 😸'
    return '❌ Этот вечный Stars-предмет уже есть у вас. Повторная покупка запрещена. 😸'

def grant_hard_limited_stars_item(econ, item_key):
    """Выдача одного из трёх глобально лимитированных Stars-предметов.
    Сначала валидирует товар, затем изменяет аккаунт. При ошибке изменения
    пользователя откатываются; глобальный резерв откатывается вызывающим кодом.
    """
    item = STARS_COSMETICS.get(item_key)
    if item_key not in STARS_HARD_LIMITED_ITEMS or not item:
        raise ValueError(f'Unknown hard-limited Stars item: {item_key}')

    c_type = item.get('type')
    title_id = item.get('title_id')
    theme_id = item.get('theme_id')
    pet_id = item.get('pet_id')

    if c_type == 'donor_title':
        if title_id not in _titles or not _titles[title_id].get('donor_only'):
            raise ValueError(f'Invalid limited donor title: {item_key}')
    elif c_type == 'theme':
        if theme_id and theme_id not in _themes:
            raise ValueError(f'Invalid limited theme: {item_key}')
    elif c_type == 'pet':
        if pet_id not in _pets_data:
            raise ValueError(f'Invalid limited pet: {item_key}')
    else:
        raise ValueError(f'Unsupported hard-limited item type: {c_type}')

    snapshot = {}
    for key in ('paid_stars_items', 'titles', 'purchased_themes', 'active_title', 'custom_title', 'profile_theme', 'pet'):
        if key in econ:
            snapshot[key] = copy.deepcopy(econ[key])

    try:
        paid = econ.setdefault('paid_stars_items', [])
        if not isinstance(paid, list):
            paid = []
            econ['paid_stars_items'] = paid
        if item_key not in paid:
            paid.append(item_key)

        if c_type == 'donor_title':
            titles = econ.setdefault('titles', [])
            if not isinstance(titles, list):
                titles = []
                econ['titles'] = titles
            if title_id not in titles:
                titles.append(title_id)
            econ['active_title'] = title_id
            econ['custom_title'] = None
        elif c_type == 'theme':
            purchased = econ.setdefault('purchased_themes', ['default'])
            if not isinstance(purchased, list):
                purchased = ['default']
                econ['purchased_themes'] = purchased
            if theme_id and theme_id not in purchased:
                purchased.append(theme_id)
            if theme_id:
                econ['profile_theme'] = theme_id
        else:
            p_info = _pets_data[pet_id]
            econ['pet'] = {
                'id': pet_id,
                'name': p_info['name'],
                'luck_bonus': p_info['luck_bonus'],
                'hunger': 100,
                'cleanliness': 100,
                'pet_exp': 0,
                'last_update': time.time()
            }
        _mark_dirty()
        return item['name']
    except Exception:
        for key in ('paid_stars_items', 'titles', 'purchased_themes', 'active_title', 'custom_title', 'profile_theme', 'pet'):
            if key in snapshot:
                econ[key] = snapshot[key]
            elif key in econ and key in {'paid_stars_items', 'titles', 'purchased_themes'}:
                econ.pop(key, None)
        raise

def validate_stars_payload(payload, amount, buyer_id, currency='XTR'):
    """Drop-in replacement for the monolith's pre-checkout validator."""
    try:
        if str(currency or '').upper() != 'XTR':
            return False, 'Неверная валюта платежа.'
        buyer_id = int(buyer_id)
        if buyer_id <= 0:
            return False, 'Некорректный плательщик.'
        raw_payload = str(payload or '')
        if raw_payload.startswith('gift2|'):
            g = raw_payload.split('|')
            if len(g) != 5:
                return False, 'Некорректный подарочный payload.'
            _, gift_kind, item_key, target_raw, payload_buyer_raw = g
            catalogs = {'coins': STARS_COIN_PACKS, 'pass': STARS_VIP_PASS, 'cosm': STARS_COSMETICS}
            item = catalogs.get(gift_kind, {}).get(item_key)
            if not item and gift_kind == 'cosm':
                item = STARS_LIMITED_ITEMS.get(item_key)
            if not item:
                return False, 'Товар подарка не найден.'
            if gift_kind == 'cosm' and item_key in STARS_HARD_LIMITED_ITEMS and stars_hard_limited_available(item_key) <= 0:
                return False, 'Лимит этого предмета уже исчерпан (5/5).'
            if int(amount) != int(item['stars']):
                return False, 'Неверная сумма товара.'
            try:
                target_id = int(target_raw)
                payload_buyer = int(payload_buyer_raw)
            except ValueError:
                return False, 'Некорректный пользователь в подарке.'
            if payload_buyer != int(buyer_id):
                return False, 'Плательщик не совпадает с владельцем счёта.'
            if target_id <= 0 or target_id == payload_buyer:
                return False, 'Некорректный или совпадающий получатель.'
            target_econ = _get_user(user_id=target_id) if _get_user else {}
            if gift_kind == 'pass':
                err = stars_purchase_error(target_econ, 'vippass', item_key)
                if err:
                    return False, 'Получатель уже владеет этим VIP.'
            elif gift_kind == 'cosm':
                if item_key == 'bp_premium' and target_econ.get('bp_premium'):
                    return False, 'Получатель уже владеет Премиум Pass.'
                if item_key == 'custom_title' and target_econ.get('has_custom_title_cert'):
                    return False, 'Получатель уже владеет сертификатом.'
                if item_key == 'pet_griffin' and 'pet_griffin' in target_econ.get('paid_stars_items', []):
                    return False, 'Получатель уже владеет Грифоном.'
                if item_key in STARS_COSMETICS or item_key in STARS_LIMITED_ITEMS:
                    err = stars_purchase_error(target_econ, 'cosm', item_key)
                    if err:
                        return False, 'Получатель уже владеет этим Stars-предметом.'
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
            item_key = key.replace('cosm_', '')
            item = STARS_COSMETICS.get(item_key) or STARS_LIMITED_ITEMS.get(item_key)
            expected = item.get('stars') if item else None
            payload_buyer = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        elif key.startswith('bpprem_'):
            expected = STARS_COSMETICS.get('bp_premium', {}).get('stars')
            payload_buyer = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            if payload_buyer is not None and _get_user:
                buyer_econ = _get_user(user_id=payload_buyer)
                if buyer_econ.get('bp_premium'):
                    return False, 'Премиум Pass уже куплен.'
        else:
            return False, 'Неизвестный товар.'
        if expected is None or int(amount) != int(expected):
            return False, 'Неверная сумма товара.'
        if payload_buyer is not None and int(payload_buyer) != int(buyer_id):
            return False, 'Плательщик не совпадает с владельцем счёта.'

        buyer_econ = _get_user(user_id=buyer_id) if _get_user else {}
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
        return True, ''
    except Exception:
        return False, 'Некорректный платёжный payload.'

# Friendly compatibility alias for code that used the draft service name.
validate_payment = validate_stars_payload

def mark_charge_processed(charge_id):
    if not charge_id:
        return False
    with _db_lock:
        processed = _db.setdefault('processed_stars_charges', [])
        if charge_id in processed:
            return False
        processed.append(charge_id)
        if len(processed) > 10000:
            del processed[:-10000]
        _mark_dirty()
        return True

def mark_stars_charge_processed(charge_id):
    if not charge_id:
        return
    with _db_lock:
        processed = _db.setdefault('processed_stars_charges', [])
        if charge_id in processed:
            return
        processed.append(charge_id)
        if len(processed) > 10000:
            del processed[:-10000]
        _mark_dirty()


def add_donated_stars(econ, amount):
    with _db_lock:
        econ['stars_donated'] = int(econ.get('stars_donated', 0) or 0) + int(amount)
        _mark_dirty()
        return econ['stars_donated']

__all__ = [
    'configure', 'PROFILE_GIFS', 'STARS_COIN_PACKS', 'STARS_VIP_PASS',
    'VIP_BADGES', 'DONOR_VEHICLES', 'DONOR_BUSINESSES', 'STARS_COSMETICS',
    'STARS_LIMITED_ITEMS', 'STARS_HARD_LIMITED_ITEMS', 'stars_hard_limited_available',
    'reserve_stars_hard_limited', 'release_stars_hard_limited',
    'stars_limited_stock', 'stars_limited_available', 'reserve_stars_limited',
    'stars_item_is_one_time', 'stars_item_owned', 'stars_purchase_error',
    'grant_hard_limited_stars_item', 'validate_stars_payload', 'validate_payment',
    'mark_charge_processed', 'mark_stars_charge_processed',
    'add_donated_stars',
]
