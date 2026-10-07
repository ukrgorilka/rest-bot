import ast
import csv
import copy
import functools
from datetime import datetime, timedelta, timezone
import html
import json

import os
import random
import re
import threading
import time
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, ReactionTypeEmoji, LabeledPrice, InputMediaAnimation, WebAppInfo
from flask import Flask, jsonify, request, send_from_directory, Response
import hashlib
import hmac
import secrets
from urllib.parse import parse_qsl

from config import (
    ADMIN_ID,
    ALLOW_JSON_BOOTSTRAP,
    BOT_VERSION,
    BUSINESS_SELL_RATE,
    BUSINESS_TAX_RATE,
    ADMIN_USERNAME,
    AUTOSAVE_DEBOUNCE,
    AUTOSAVE_INTERVAL,
    BACKUP_INTERVAL,
    BOT_TOKEN,
    DATA_FILE,
    DATABASE_URL,
    DB_CHANNEL_ID,
    LOG_CHANNEL_ID,
    MEDIA_TG_CHAT_ID,
    MINIAPP_DAILY_REWARD_CAP,
    MINIAPP_DIR as CONFIG_MINIAPP_DIR,
    MINIAPP_GAME_TTL,
    MINIAPP_URL as CONFIG_MINIAPP_URL,
    PORT,
    VD_CHAT_ID,
    MSK_TZ,
    now_msk as config_now_msk,
    normalize_tg_id,
)
from core.database import load_data as database_load_data, save_snapshot
from core.localization import (
    _CALLBACK_LANG_BY_ID,
    _CALLBACK_LANG_LOCK,
    _LOCALE_CONTEXT,
    _bot_output_language,
    apply_global_premium_emojis,
    configure as configure_localization,
    format_large_numbers,
    install_telegram_localization,
    premium_emoji,
)
from core.locks import (
    DB_SAVE_LOCK,
    CALLBACK_STATE_LOCK,
    STARS_PAYMENT_LOCK,
    TRANSFER_LOCK,
    BALANCE_TX_LOCK,
    CASINO_LOCK,
    GUILD_LOCK,
    SAFE_LOCK,
    PLAYER_MARKET_LOCK,
    LOTTERY_LOCK,
    MEME_LOCK,
    MARKET_LOCK,
    QUIZ_LOCK,
    _get_user_action_lock,
    serialized_multi_user_action,
    serialize_user_action,
    serialize_stars_payment,
)
from services import (
    economy as economy_service,
    inventory as inventory_service,
    stars as stars_service,
    users as users_service,
    saving as saving_service,
)
from handlers import register_all as register_handlers

# ---------------------------------------------------------
# ЕДИНЫЙ ЧАСОВОЙ ПОЯС (МСК / UTC+3)
# ---------------------------------------------------------
def now_msk():
    return config_now_msk()

# ---------------------------------------------------------
# ВЕБ-СЕРВЕР ДЛЯ KEEP-ALIVE (RENDER / REPLIT / VPS)
# ---------------------------------------------------------
app = Flask('')

# ---------------------------------------------------------
# NYABOT v0.3 — MINI APP
# ---------------------------------------------------------
MINIAPP_DIR = CONFIG_MINIAPP_DIR
MINIAPP_URL = CONFIG_MINIAPP_URL
MINIAPP_GAMES = {}
MINIAPP_LOCK = threading.RLock()


BOT_VERSION_TEXT = f"NyaBot v{BOT_VERSION}"


def _miniapp_user(init_data):
    if not init_data or not TOKEN:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop('hash', None)
        if not received_hash:
            return None
        check = '\n'.join(f'{k}={pairs[k]}' for k in sorted(pairs))
        secret_key = hmac.new(b'WebAppData', TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret_key, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, received_hash):
            return None
        user = json.loads(pairs.get('user', '{}'))
        if not user.get('id'):
            return None
        auth_date = int(pairs.get('auth_date', '0') or 0)
        if auth_date <= 0:
            return None
        age = time.time() - auth_date
        if age < -60 or age > 86400:
            return None
        return user
    except Exception:
        return None

def _miniapp_auth(payload):
    return _miniapp_user(str((payload or {}).get('initData', '')))

@app.route('/minigames')
def miniapp_index():
    if not os.path.exists(os.path.join(MINIAPP_DIR, 'index.html')):
        return 'Mini App is not installed', 404
    return send_from_directory(MINIAPP_DIR, 'index.html')

@app.route('/minigames/<path:filename>')
def miniapp_static(filename):
    return send_from_directory(MINIAPP_DIR, filename)

def _mini_add_notification(econ, text):
    rows = econ.setdefault('mini_notifications', [])
    if not isinstance(rows, list):
        rows = []
        econ['mini_notifications'] = rows
    rows.append({'text': str(text)[:300], 'time': now_msk().strftime('%d.%m.%Y %H:%M')})
    del rows[:-50]


@app.route('/api/mini/profile', methods=['POST'])
def mini_profile_api():
    user = _miniapp_auth(request.get_json(silent=True) or {})
    if not user:
        return jsonify({'ok': False, 'error': 'invalid_telegram_auth'}), 403
    uid = int(user['id'])
    name = (user.get('first_name') or user.get('username') or 'Игрок')
    econ = get_user_econ(uid, name, username=user.get('username'))
    lvl, exp, nxt, bar = get_account_level(econ.get('account_exp', 0))
    st = econ.get('msg_stats', {}) or {}
    return jsonify({'ok': True, 'version': BOT_VERSION, 'user': {'id': uid, 'name': name, 'username': user.get('username')}, 'balance': int(econ.get('balance',0) or 0), 'stars': int(econ.get('stars_donated',0) or 0), 'level': lvl, 'exp': int(exp), 'next_exp': int(nxt), 'bar': bar, 'activity': {'day': int(st.get('day_count',0) or 0), 'week': int(st.get('week_count',0) or 0), 'month': int(st.get('month_count',0) or 0), 'all': int(st.get('total_count',0) or 0)}, 'achievements': len(econ.get('achievements',[]) or []), 'streak': int(econ.get('bonus_streak',0) or 0), 'games_played': int(econ.get('mini_games_played',0) or 0), 'game_wins': int(econ.get('mini_games_wins',0) or 0), 'records': econ.get('mini_records',{}) or {}, 'language': econ.get('language','ru')})


@app.route('/api/mini/empire', methods=['POST'])
def mini_empire_api():
    """Return the live player's business empire from the Neon-backed state."""
    user = _miniapp_auth(request.get_json(silent=True) or {})
    if not user:
        return jsonify({'ok': False, 'error': 'invalid_telegram_auth'}), 403
    uid = int(user['id'])
    name = user.get('first_name') or user.get('username') or 'Игрок'
    econ = get_user_econ(uid, name, username=user.get('username'))
    _migrate_legacy_businesses(econ)

    rows = []
    gross_hourly = 0
    owned = econ.get('businesses', {}) if isinstance(econ.get('businesses'), dict) else {}
    donor_owned = econ.get('donor_businesses', {}) if isinstance(econ.get('donor_businesses'), dict) else {}
    for number, b_id, info, is_donor in _business_catalog():
        source = donor_owned if is_donor else owned
        if b_id not in source:
            continue
        level = _business_level(econ, b_id)
        hourly = _business_hourly_income(b_id, level)
        gross_hourly += hourly
        purchase_price = _business_purchase_price(econ, b_id) if not is_donor else 0
        rows.append({
            'number': number,
            'id': b_id,
            'name': info.get('name', b_id),
            'short': info.get('short', info.get('name', b_id)),
            'world': info.get('world', 'earth'),
            'level': level,
            'max_level': 5,
            'hourly_gross': hourly,
            'hourly_net_estimate': int(hourly * (1.0 - BUSINESS_TAX_RATE)),
            'purchase_price': purchase_price,
            'legacy': any(
                isinstance(x, dict) and x.get('to') == b_id
                for x in (econ.get('legacy_assets') or [])
            ),
            'donor': bool(is_donor),
        })

    return jsonify({
        'ok': True,
        'version': BOT_VERSION,
        'business_tax_rate': BUSINESS_TAX_RATE,
        'sell_rate': BUSINESS_SELL_RATE,
        'business_count': len(rows),
        'gross_hourly': int(gross_hourly),
        'net_hourly_estimate': int(gross_hourly * (1.0 - BUSINESS_TAX_RATE)),
        'tax_paid': int(econ.get('business_tax_paid', 0) or 0),
        'legacy_assets': len(econ.get('legacy_assets', []) or []),
        'rows': rows,
    })


def _mini_world_snapshot():
    """Compute bounded world statistics from the live in-memory state."""
    with db_lock:
        snapshot = list((db.get('economy') or {}).items())
        news = list(db.get('bot_news') or [])[-20:]
    unique_users = set()
    total_coins = total_bank = 0
    business_counts = {b_id: 0 for b_id in BUSINESSES}
    donor_counts = {b_id: 0 for b_id in DONOR_BUSINESSES}
    for key, econ in snapshot:
        if not isinstance(econ, dict):
            continue
        uid = econ.get('user_id')
        try:
            if int(uid) > 0:
                unique_users.add(int(uid))
        except (TypeError, ValueError):
            # Old tag-only records are still useful for economy totals, but are
            # not counted as a unique Telegram account.
            pass
        total_coins += int(econ.get('balance', 0) or 0)
        total_bank += int(econ.get('bank_deposit', 0) or 0)
        for b_id in business_counts:
            if b_id in (econ.get('businesses') or {}):
                business_counts[b_id] += 1
        for b_id in donor_counts:
            if b_id in (econ.get('donor_businesses') or {}):
                donor_counts[b_id] += 1
    return {
        'players': len(unique_users),
        'profiles': len(snapshot),
        'coins': int(total_coins),
        'bank': int(total_bank),
        'total_wealth': int(total_coins + total_bank),
        'businesses': int(sum(business_counts.values())),
        'donor_businesses': int(sum(donor_counts.values())),
        'mars': int(business_counts.get('mars_colony', 0)),
        'intergalactic_port': int(business_counts.get('intergalactic_port', 0)),
        'business_counts': business_counts,
        'donor_counts': donor_counts,
        'news': news,
    }


@app.route('/api/mini/world', methods=['POST'])
def mini_world_api():
    user = _miniapp_auth(request.get_json(silent=True) or {})
    if not user:
        return jsonify({'ok': False, 'error': 'invalid_telegram_auth'}), 403
    world = _mini_world_snapshot()
    return jsonify({'ok': True, 'version': BOT_VERSION, 'tax_rate': BUSINESS_TAX_RATE, **world})


@app.route('/api/mini/tasks', methods=['POST'])
def mini_tasks_api():
    payload = request.get_json(silent=True) or {}
    user = _miniapp_auth(payload)
    if not user:
        return jsonify({'ok': False, 'error': 'invalid_telegram_auth'}), 403

    uid = int(user['id'])
    name = user.get('first_name') or user.get('username') or 'Игрок'
    username = user.get('username')
    daily_defs, econ = get_daily_tasks(uid, name, username=username)
    weekly_defs, _ = get_weekly_tasks(uid, name, username=username)

    daily_progress = econ.get('daily_progress', {}) or {}
    daily_claimed = set(econ.get('daily_claimed', []) or [])
    weekly_progress = econ.get('weekly_progress', {}) or {}
    weekly_claimed = set(econ.get('weekly_claimed', []) or [])

    def serialize(defs, progress_map, claimed):
        rows = []
        for key, description, target, reward in defs:
            progress = max(0, int(progress_map.get(key, 0) or 0))
            rows.append({
                'id': key,
                'description': description,
                'target': int(target),
                'reward': int(reward),
                'progress': min(progress, int(target)),
                'completed': progress >= int(target),
                'claimed': key in claimed,
            })
        return rows

    return jsonify({
        'ok': True,
        'streak': int(econ.get('bonus_streak', 0) or 0),
        'daily': serialize(daily_defs, daily_progress, daily_claimed),
        'weekly': serialize(weekly_defs, weekly_progress, weekly_claimed),
    })

@app.route('/api/mini/tasks/claim', methods=['POST'])
def mini_task_claim_api():
    payload = request.get_json(silent=True) or {}
    user = _miniapp_auth(payload)
    if not user:
        return jsonify({'ok': False, 'error': 'invalid_telegram_auth'}), 403
    uid = int(user['id'])
    name = user.get('first_name') or user.get('username') or 'Игрок'
    username = user.get('username')
    task_id = str(payload.get('task_id', '') or '')[:80]
    kind = str(payload.get('kind', 'daily') or 'daily').lower()
    if kind not in {'daily', 'weekly'} or not task_id:
        return jsonify({'ok': False, 'error': 'invalid_task'}), 400
    with _get_user_action_lock(uid):
        with MINIAPP_LOCK:
            econ = get_user_econ(uid, name, username=username)
        defs, _ = get_daily_tasks(uid, name, username=username) if kind == 'daily' else (get_weekly_tasks(uid, name, username=username)[0], econ)
        task = next((x for x in defs if x[0] == task_id), None)
        if not task:
            return jsonify({'ok': False, 'error': 'unknown_task'}), 404
        _, description, target, reward = task
        progress_key = 'daily_progress' if kind == 'daily' else 'weekly_progress'
        claimed_key = 'daily_claimed' if kind == 'daily' else 'weekly_claimed'
        progress = econ.get(progress_key, {}) or {}
        claimed = econ.setdefault(claimed_key, [])
        if task_id in claimed:
            return jsonify({'ok': False, 'error': 'already_claimed'}), 400
        if int(progress.get(task_id, 0) or 0) < int(target):
            return jsonify({'ok': False, 'error': 'not_completed'}), 400
        reward = max(0, int(reward))
        _set_balance(econ, int(econ.get('balance', 0) or 0) + reward)
        claimed.append(task_id)
        tx = econ.setdefault('mini_transactions', [])
        tx.append({'text': f'Mini App: задание — {description}', 'amount': reward, 'time': now_msk().strftime('%d.%m.%Y %H:%M')})
        del tx[:-100]
        _mini_add_notification(econ, f'📋 Задание выполнено: +{reward:,} 🪙')
        add_account_exp(uid, name, 15, username)
        mark_dirty()
        save_data(send_backup=False)
        return jsonify({'ok': True, 'reward': reward, 'task_id': task_id, 'kind': kind})


@app.route('/api/mini/achievements', methods=['POST'])
def mini_achievements_api():
    user=_miniapp_auth(request.get_json(silent=True) or {})
    if not user: return jsonify({'ok':False,'error':'invalid_telegram_auth'}),403
    uid=int(user['id']); econ=get_user_econ(uid,user.get('first_name') or user.get('username') or 'Игрок',username=user.get('username'))
    unlocked=set(econ.get('achievements',[]) or []); rows=[]
    for key, info in (ACHIEVEMENTS or {}).items():
        if not isinstance(info,dict): continue
        rows.append({'id':key,'title':info.get('name') or info.get('title') or key,'desc':info.get('description') or info.get('desc') or '','reward':int(info.get('reward',0) or 0),'progress':1 if key in unlocked else 0,'target':1,'unlocked':key in unlocked})
    return jsonify({'ok':True,'unlocked':len(unlocked),'rows':rows[:100]})

@app.route('/api/mini/stats', methods=['POST'])
def mini_stats_api():
    user=_miniapp_auth(request.get_json(silent=True) or {})
    if not user: return jsonify({'ok':False,'error':'invalid_telegram_auth'}),403
    uid=int(user['id']); econ=get_user_econ(uid,user.get('first_name') or user.get('username') or 'Игрок',username=user.get('username'))
    return jsonify({'ok':True,'games_played':int(econ.get('mini_games_played',0) or 0),'wins':int(econ.get('mini_games_wins',0) or 0),'records':econ.get('mini_records',{}) or {}})

@app.route('/api/mini/notifications', methods=['POST'])
def mini_notifications_api():
    user=_miniapp_auth(request.get_json(silent=True) or {})
    if not user: return jsonify({'ok':False,'error':'invalid_telegram_auth'}),403
    uid=int(user['id']); econ=get_user_econ(uid,user.get('first_name') or user.get('username') or 'Игрок',username=user.get('username'))
    return jsonify({'ok':True,'rows':list(econ.get('mini_notifications',[]) or [])[-50:]})

@app.route('/api/mini/transactions', methods=['POST'])
def mini_transactions_api():
    user=_miniapp_auth(request.get_json(silent=True) or {})
    if not user: return jsonify({'ok':False,'error':'invalid_telegram_auth'}),403
    uid=int(user['id']); econ=get_user_econ(uid,user.get('first_name') or user.get('username') or 'Игрок',username=user.get('username'))
    return jsonify({'ok':True,'rows':list(econ.get('mini_transactions',[]) or [])[-100:]})

@app.route('/api/mini/shop', methods=['POST'])
def mini_shop_api():
    user=_miniapp_auth(request.get_json(silent=True) or {})
    if not user: return jsonify({'ok':False,'error':'invalid_telegram_auth'}),403
    grouped = {}
    type_names = {'theme': '🎨 Темы', 'title_cert': '🏷 Титулы', 'donor_title': '👑 Донатные титулы', 'badge': '✨ Значки', 'pet': '🐾 Питомцы', 'gif': '🎞 GIF профиля', 'donor_vehicle': '🏎 Машины', 'donor_business': '🏢 Донатные бизнесы', 'limited_effect': '✨ Stars-эффекты'}
    for key,item in {**(STARS_COSMETICS or {}), **(STARS_LIMITED_ITEMS or {})}.items():
        if not isinstance(item,dict): continue
        category = type_names.get(item.get('type'), '⭐ Stars')
        grouped.setdefault(category, []).append({'id': key, 'name': item.get('name') or key, 'desc': item.get('description') or item.get('desc') or '', 'stars': int(item.get('stars',item.get('price',0)) or 0)})
    cats=[{'title': title, 'items': items} for title,items in grouped.items()]
    return jsonify({'ok':True,'categories':cats[:20]})

@app.route('/api/mini/settings', methods=['POST'])
def mini_settings_api():
    payload=request.get_json(silent=True) or {}; user=_miniapp_auth(payload)
    if not user: return jsonify({'ok':False,'error':'invalid_telegram_auth'}),403
    lang=str(payload.get('language','ru')).lower()
    if lang not in {'ru','uk','en'}: return jsonify({'ok':False,'error':'invalid_language'}),400
    uid=int(user['id']); econ=get_user_econ(uid,user.get('first_name') or user.get('username') or 'Игрок',username=user.get('username'))
    econ['language']=lang; mark_dirty()
    return jsonify({'ok':True,'language':lang})

@app.route('/api/mini/bonus', methods=['POST'])
def mini_bonus_api():
    payload = request.get_json(silent=True) or {}
    user = _miniapp_auth(payload)
    if not user:
        return jsonify({'ok': False, 'error': 'invalid_telegram_auth'}), 403

    uid = int(user['id'])
    name = user.get('first_name') or user.get('username') or 'Игрок'
    username = user.get('username')
    with _get_user_action_lock(uid):
        with MINIAPP_LOCK:
            econ = get_user_econ(uid, name, username=username)
        now = now_msk().date().isoformat()
        if econ.get('mini_daily_claimed') == now:
            return jsonify({'ok': False, 'error': 'already_claimed'})

        last_streak = float(econ.get('last_streak_time', 0) or 0)
        elapsed = time.time() - last_streak if last_streak > 0 else 10**9
        streak = int(econ.get('bonus_streak', 0) or 0)
        if 20 * 3600 <= elapsed < 48 * 3600:
            streak += 1
        elif elapsed >= 48 * 3600:
            streak = 1
        # Keep legacy Mini App fields synchronized for older clients, but the
        # canonical streak is now the same bonus_streak used by the bot.
        reward = min(5000, 500 + streak * 100)

        econ['mini_daily_claimed'] = now
        econ['mini_daily_date'] = now
        econ['mini_daily_streak'] = streak
        econ['bonus_streak'] = streak
        econ['last_streak_time'] = time.time()
        _set_balance(econ, int(econ.get('balance', 0) or 0) + reward)
        tx = econ.setdefault('mini_transactions', [])
        tx.append({'text': 'Mini App: ежедневный бонус', 'amount': reward, 'time': now_msk().strftime('%d.%m.%Y %H:%M')})
        del tx[:-100]
        _mini_add_notification(econ, f'🎁 Ежедневный бонус: +{reward:,} 🪙 (серия {streak})')
        mark_dirty()
        save_data(send_backup=False)
        return jsonify({'ok': True, 'reward': reward, 'streak': streak})

@app.route('/api/mini/leaderboard', methods=['POST'])
def mini_leaderboard_api():
    payload=request.get_json(silent=True) or {}; user=_miniapp_auth(payload)
    if not user: return jsonify({'ok':False,'error':'invalid_telegram_auth'}),403
    game=str(payload.get('game','') or '').lower()
    rows=[]
    with db_lock:
        economy_snapshot = list(db.get('economy', {}).items())
    for uid,econ in economy_snapshot:
        if not isinstance(econ,dict): continue
        try:
            exp=int(econ.get('account_exp',0) or 0); balance=int(econ.get('balance',0) or 0)
            if game:
                records=econ.get('mini_records',{}) or {}; score=int(records.get(game,0) or 0)
                if score <= 0: continue
            else:
                score=exp
        except Exception: continue
        rows.append({'name':clean_tag(econ.get('display_name') or econ.get('name') or econ.get('tag') or str(uid)),'level':get_account_level(exp)[0],'exp':exp,'score':score,'balance':balance})
    rows.sort(key=lambda x:(x['score'],x['balance']),reverse=True)
    return jsonify({'ok':True,'rows':rows[:20]})

@app.route('/api/mini/game/start', methods=['POST'])
def mini_game_start_api():
    payload = request.get_json(silent=True) or {}
    user = _miniapp_auth(payload)
    if not user:
        return jsonify({'ok': False, 'error': 'invalid_telegram_auth'}), 403

    game = str(payload.get('game', '') or '').lower()
    if game not in {'mines', 'snake', 'flappy', '2048', 'reaction', 'shooter'}:
        return jsonify({'ok': False, 'error': 'unknown_game'}), 400

    uid = int(user['id'])
    now = time.time()
    with MINIAPP_LOCK:
        # Remove abandoned sessions and make the newest session the only active one.
        stale = [gid for gid, item in MINIAPP_GAMES.items() if now - float(item.get('started', now)) > MINIAPP_GAME_TTL]
        for stale_gid in stale:
            MINIAPP_GAMES.pop(stale_gid, None)
        for old_gid, item in list(MINIAPP_GAMES.items()):
            if item.get('user_id') == uid:
                MINIAPP_GAMES.pop(old_gid, None)

        gid = secrets.token_urlsafe(16)
        MINIAPP_GAMES[gid] = {
            'user_id': uid,
            'game': game,
            'difficulty': str(payload.get('difficulty', 'easy'))[:32],
            'started': now,
        }

    return jsonify({'ok': True, 'game_id': gid})


@app.route('/api/mini/game/finish', methods=['POST'])
def mini_game_finish_api():
    payload = request.get_json(silent=True) or {}
    user = _miniapp_auth(payload)
    if not user:
        return jsonify({'ok': False, 'error': 'invalid_telegram_auth'}), 403

    gid = str(payload.get('game_id', '') or '')
    # Client-provided scores are untrusted and cannot grant progression or currency.
    try:
        client_score = max(0, min(int(payload.get('score', 0) or 0), 100000))
    except (TypeError, ValueError, OverflowError):
        client_score = 0

    uid = int(user['id'])
    now = time.time()
    with _get_user_action_lock(uid):
        with MINIAPP_LOCK:
            game = MINIAPP_GAMES.pop(gid, None)
        if not game or game.get('user_id') != uid:
            return jsonify({'ok': False, 'error': 'invalid_game'}), 400

        elapsed = now - float(game.get('started', now))
        if elapsed < 0.5:
            return jsonify({'ok': False, 'error': 'too_fast'}), 400
        if elapsed > MINIAPP_GAME_TTL:
            return jsonify({'ok': False, 'error': 'game_expired'}), 400

        game_name = game['game']
        difficulty = str(game.get('difficulty', 'easy')).lower()
        # Scores are still client-reported, so this endpoint is not a cryptographic
        # anti-cheat system. We nevertheless enforce per-game plausibility caps and
        # derive rewards/wins on the server instead of blindly trusting the browser.
        score_limits = {
            'mines': {'easy': 71, 'medium': 216, 'hard': 304, 'insane': 450},
            'snake': max(1, int(elapsed / 0.145) + 2),
            'flappy': max(1, int(elapsed / 0.95) + 1),
            # 2048 is browser-controlled, so its accepted score is bounded by
            # elapsed server time too. This is not a full anti-cheat system, but
            # prevents an instant fabricated six-figure score from minting coins.
            '2048': max(128, int(elapsed * 140)),
            'reaction': 1200,
            'shooter': 20,
        }
        limit = score_limits.get(game_name, 0)
        if isinstance(limit, dict):
            limit = limit.get(difficulty, limit.get('easy', 71))
        score = min(client_score, max(0, int(limit)))
        if client_score > int(limit):
            return jsonify({'ok': False, 'error': 'score_out_of_range'}), 400

        name = user.get('first_name') or user.get('username') or 'Игрок'
        username = user.get('username')
        econ = get_user_econ(uid, name, username=username)

        econ['mini_games_played'] = int(econ.get('mini_games_played', 0) or 0) + 1
        records = econ.setdefault('mini_records', {})
        old = int(records.get(game_name, 0) or 0)
        if score > old:
            records[game_name] = score

        win_thresholds = {
            'mines': {'easy': 71, 'medium': 216, 'hard': 304, 'insane': 450},
            'snake': 10, 'flappy': 5, '2048': 2048, 'reaction': 900, 'shooter': 15,
        }
        threshold = win_thresholds.get(game_name)
        if isinstance(threshold, dict):
            threshold = threshold.get(difficulty, threshold.get('easy'))
        if threshold is not None and score >= int(threshold):
            econ['mini_games_wins'] = int(econ.get('mini_games_wins', 0) or 0) + 1

        reward_caps = {'mines': 2500, 'snake': 2000, 'flappy': 2000, '2048': 2500, 'reaction': 1500, 'shooter': 2500}
        # Reward is based on the bounded score. It is additionally constrained by
        # the per-day Mini App cap, so a client cannot drain the whole economy.
        if game_name == 'mines':
            safe_cells = {'easy': 71, 'medium': 216, 'hard': 304, 'insane': 450}.get(difficulty, 71)
            raw_reward = reward_caps['mines'] if score >= safe_cells else min(250, score * 3)
        elif game_name == 'snake':
            raw_reward = min(reward_caps['snake'], score * 8)
        elif game_name == 'flappy':
            raw_reward = min(reward_caps['flappy'], score * 12)
        elif game_name == '2048':
            raw_reward = min(reward_caps['2048'], score // 2)
        elif game_name == 'reaction':
            raw_reward = min(reward_caps['reaction'], score)
        else:
            raw_reward = min(reward_caps['shooter'], score * 20)

        reward_day = now_msk().date().isoformat()
        if econ.get('mini_game_reward_date') != reward_day:
            econ['mini_game_reward_date'] = reward_day
            econ['mini_game_reward_today'] = 0
        already_paid = int(econ.get('mini_game_reward_today', 0) or 0)
        remaining = max(0, MINIAPP_DAILY_REWARD_CAP - already_paid)
        reward = min(raw_reward, remaining)
        if reward:
            _set_balance(econ, int(econ.get('balance', 0) or 0) + reward)
            econ['mini_game_reward_today'] = already_paid + reward

        tx = econ.setdefault('mini_transactions', [])
        tx.append({
            'text': f'Mini Game: {game_name}',
            'amount': reward,
            'time': now_msk().strftime('%d.%m.%Y %H:%M'),
        })
        del tx[:-100]

        mark_dirty()
        save_data(send_backup=False)
        return jsonify({'ok': True, 'reward': reward, 'record': records.get(game_name, 0), 'validated': False})

MINIAPP_MUSIC = {
    'city': 'CQACAgIAAxkBAAI8KGqycDp6EgnMb6IYmeYcQ30P4lZYAAI5ewAC2r4QSiHiCGMmfw2iPQQ',
    'moog': 'CQACAgIAAxkBAAI7c2qxoKtO0jM_j2VfHWHg3qzIkYhuAAK0mAACt-8pS74P-OfxOrdgPQQ',
    'doki': 'CQACAgIAAxkBAAI8OGqye6dxzMArn5Z8_oN-Zfxpwad_AAKjlQACzEIhSbF9j2pSNFhAPQQ',
    'plenka': 'CQACAgIAAxkBAAI8O2qye8_F-Q_cGII2umP6qPi8-zcoAAJWgQACw5kBSoZ0PAKSKD5uPQQ',
}

@app.route('/api/mini/music/<track>')
def mini_music(track):
    file_id=MINIAPP_MUSIC.get(track)
    if not file_id: return 'Not found',404
    try:
        f=bot.get_file(file_id)
        data=bot.download_file(f.file_path)
        mime='audio/mp4' if f.file_path.lower().endswith(('.m4a','.mp4')) else 'audio/mpeg'
        return Response(data,mimetype=mime,headers={'Cache-Control':'public,max-age=86400'})
    except Exception as e:
        print(f'[MINI MUSIC ERROR] {e}')
        return 'Music unavailable',502

@app.route('/health')
def health():
    return "Nya Bot is alive and running! 😺"


def run_web():
    port = PORT
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

# ---------------------------------------------------------
# НАСТРОЙКИ БОТА И БАЗЫ ДАННЫХ
# ---------------------------------------------------------
TOKEN = BOT_TOKEN
if not TOKEN:
    print("[ВНИМАНИЕ] BOT_TOKEN не задан в переменных окружения (ENV)! Бот ожидает BOT_TOKEN в Render.")
bot = telebot.TeleBot(TOKEN)

# ---------------------------------------------------------
# ЛОКАЛИЗАЦИЯ И PREMIUM EMOJI
# ---------------------------------------------------------
# Реализация вынесена в core/localization.py.
# Подключение выполняется после объявления get_user_econ/get_chat_settings.
# ---------------------------------------------------------

db_lock = threading.RLock()
last_db_change_at = 0.0
db_dirty = False
db_version = 0


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

# ID каналов и чатов
# PostgreSQL/Neon is now the primary persistent database.
# All values come from config.py so there is a single configuration source.

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

STREAM_LEVELS = [
    (0, '🎥 Новичок'), (100, '📹 Начинающий'), (500, '⭐ Стример'),
    (1500, '🔥 Популярный'), (5000, '💎 Топ-стример'), (15000, '👑 Легенда стримов')
]
STREAM_FORMATS = {
    'обычный': {'name': '🎥 Обычный стрим', 'mult': 1.0, 'risk': 0.05},
    'марафон': {'name': '⏱ Стрим-марафон', 'mult': 1.45, 'risk': 0.12},
    'турнир': {'name': '🏆 Турнирный стрим', 'mult': 1.7, 'risk': 0.18},
    'общение': {'name': '💬 Общение с чатом', 'mult': 1.25, 'risk': 0.04},
}
STREAM_EVENTS = [
    ('🔥 Виральный клип разлетелся по чатам!', 1.65, 0.15),
    ('🎁 Зрители устроили массовый рейд!', 1.45, 0.10),
    ('💰 Спонсор заметил стрим и прислал бонус!', 1.30, 0.00),
    ('😹 Чат устроил безумный флуд мемами!', 1.20, 0.02),
    ('📉 Связь начала лагать, часть зрителей ушла.', 0.72, 0.00),
]

def get_stream_level(followers):
    level, title = 1, STREAM_LEVELS[0][1]
    for need, name in STREAM_LEVELS:
        if followers >= need:
            level, title = STREAM_LEVELS.index((need, name)) + 1, name
    return level, title


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
    # Stars-донатные титулы. Они не продаются за коины и доступны только через /stars.
    'donor_sponsor': {'name': 'Золотой Спонсор', 'text': '💎 Золотой Спонсор', 'price': 0, 'donor_only': True,
                      'donor_buffs': {'work_bonus': 0.10, 'bonus_mult': 0.10, 'business_bonus': 0.05},
                      'desc': '+10% к зарплате, +10% к /bonus, +5% к прибыли бизнесов'},
    'donor_diamond': {'name': 'Алмазный Спонсор', 'text': '💠 Алмазный Спонсор', 'price': 0, 'donor_only': True,
                      'donor_buffs': {'work_bonus': 0.15, 'bonus_mult': 0.15, 'business_bonus': 0.10},
                      'desc': '+15% к зарплате, +15% к /bonus, +10% к прибыли бизнесов'},
    'donor_emperor': {'name': 'Император Доната', 'text': '👑 Император Доната', 'price': 0, 'donor_only': True,
                      'donor_buffs': {'work_bonus': 0.20, 'bonus_mult': 0.20, 'business_bonus': 0.15},
                      'desc': '+20% к зарплате, +20% к /bonus, +15% к прибыли бизнесов'},
    'donor_void_lord': {'name': 'Властелин Пустоты', 'text': '🕳️ Властелин Пустоты', 'price': 0, 'donor_only': True,
                      'donor_buffs': {'work_bonus': 0.35, 'bonus_mult': 0.40, 'business_bonus': 0.30},
                      'desc': '+35% к зарплате, +40% к /bonus, +30% к прибыли бизнесов — усиленный лимитный титул'},
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
    'default': {'name': 'Классическая', 'price': 0, 'border': '━━━━━━━━━━━━━━━━━━━━', 'header': '👤 <b>КАРТОЧКА ИГРОКА</b>', 'icon': '🔹'},
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
    'stars_galaxy': {'name': '🌌 Бездна Сингулярности VIP', 'price': 0, 'border': '🪐══════ 🌀 ══════🌌', 'header': '🌌 <b>БЕЗДНА КОСМИЧЕСКОЙ СИНГУЛЯРНОСТИ</b> 🛸', 'icon': '🪐'},
    'stars_moonlit': {'name': '🌙 Лунная Ночь VIP', 'price': 0, 'border': '🌙══════ ✦ ══════🌙', 'header': '🌙 <b>ЛУННАЯ НОЧЬ — VIP ID</b> ✦', 'icon': '🌙'}
}

# ---------------------------------------------------------
# GIF ДЛЯ ПРОФИЛЯ (покупка только за Telegram Stars)
# Ссылки ведут на прямые GIF-файлы Tenor. После покупки GIF автоматически экипируется.
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

# ---------------------------------------------------------
# ЭКОНОМИКА TELEGRAM STARS (ЗВЁЗДЫ) & VIP PASS
# ---------------------------------------------------------
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
    'donor_lambo': {'name': '🏎 Lamborghini Aventador SVJ VIP', 'short': '🏎 Lambo VIP', 'stars': 8, 'cd_cut': 0.34, 'desc': '-34% ко всем таймерам', 'tier': 15, 'donor_only': True, 'class': 'luxury', 'work_bonus': 0.12},
    'donor_batmobile': {'name': '🦇 Batmobile Nya Edition', 'short': '🦇 Batmobile', 'stars': 12, 'cd_cut': 0.42, 'desc': '-42% ко всем таймерам', 'tier': 16, 'donor_only': True, 'class': 'hyper', 'work_bonus': 0.16},
    'donor_ufo': {'name': '🛸 НЛО Императора Ня', 'short': '🛸 НЛО', 'stars': 18, 'cd_cut': 0.50, 'desc': '-50% ко всем таймерам', 'tier': 17, 'donor_only': True, 'class': 'galactic', 'work_bonus': 0.2},
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

# Stars-визуалы без общего лимита. STARS_HARD_LIMITED_ITEMS ниже — единственные товары с глобальным лимитом 5.
STARS_LIMITED_MAX = 5
# Глобальный лимит 5 действует только на три новые позиции.
STARS_HARD_LIMITED_MAX = 5
STARS_HARD_LIMITED_LOCK = threading.Lock()
STARS_HARD_LIMITED_ITEMS = {
    'pet_moon_fox': {'name': '🌙 Питомец: Лунный Фокс'},
    'theme_moonlit': {'name': '🌙 Тема: Лунная Ночь VIP'},
    'title_donor_void_lord': {'name': '🕳️ Титул: Властелин Пустоты'},
}

def stars_hard_limited_available(item_key):
    if item_key not in STARS_HARD_LIMITED_ITEMS:
        return None
    with STARS_HARD_LIMITED_LOCK:
        sold = db.setdefault('stars_hard_limited_stock', {})
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
        sold = db.setdefault('stars_hard_limited_stock', {})
        try:
            used = int(sold.get(item_key, 0) or 0)
        except (TypeError, ValueError):
            used = 0
        if used >= STARS_HARD_LIMITED_MAX:
            return False
        sold[item_key] = used + 1
        mark_dirty()
        return True

def release_stars_hard_limited(item_key):
    """Вернуть один резерв глобального лимита после неудачной выдачи."""
    if item_key not in STARS_HARD_LIMITED_ITEMS:
        return
    with STARS_HARD_LIMITED_LOCK:
        sold = db.setdefault('stars_hard_limited_stock', {})
        try:
            used = int(sold.get(item_key, 0) or 0)
        except (TypeError, ValueError):
            used = 0
        sold[item_key] = max(0, used - 1)
        mark_dirty()

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
    if not text_str:
        return text_str
    text_str = format_large_numbers(text_str)
    if font_key == 'default':
        return text_str
    if font_key == 'monospace':
        parts = re.split(r'(<[^>]+>)', str(text_str))
        return ''.join(p if (p.startswith('<') and p.endswith('>')) else f"<code>{p}</code>" for p in parts if p)
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
    # v0.3 starter tier — replaces the three weakest businesses.
    'smoothie_bar': {'name': '🍓 Смуси-бар', 'short': 'Смуси-бар', 'price': 900, 'base_income': 10, 'upgrade_cost': 650, 'world': 'earth'},
    'food_truck': {'name': '🚚 Фудтрак', 'short': 'Фудтрак', 'price': 1600, 'base_income': 16, 'upgrade_cost': 1100, 'world': 'earth'},
    'pizzeria': {'name': '🍕 Пиццерия', 'short': 'Пиццерия', 'price': 2200, 'base_income': 22, 'upgrade_cost': 1600, 'world': 'earth'},
    'coffee': {'name': '☕️ Уютная Кофейня', 'short': 'Кофейня', 'price': 2400, 'base_income': 24, 'upgrade_cost': 1800, 'world': 'earth'},
    'bakery': {'name': '🥐 Пекарня Булочек', 'short': 'Пекарня', 'price': 6000, 'base_income': 54, 'upgrade_cost': 4500, 'world': 'earth'},
    'crypto_farm': {'name': '💻 Крипто-Ферма', 'short': 'Крипто-Ферма', 'price': 18000, 'base_income': 150, 'upgrade_cost': 13000, 'world': 'earth'},
    'club': {'name': '🏰 Ночной Клуб', 'short': 'Ночной Клуб', 'price': 54000, 'base_income': 420, 'upgrade_cost': 38000, 'world': 'earth'},
    'autoshow': {'name': '🏎 Автосалон Спорткаров', 'short': 'Автосалон', 'price': 120000, 'base_income': 900, 'upgrade_cost': 85000, 'world': 'earth'},
    'space_station': {'name': '🛰 Космическая Станция', 'short': 'Космостанция', 'price': 450000, 'base_income': 3150, 'upgrade_cost': 300000, 'world': 'space'},
    'megacorp': {'name': '🏢 Мегакорпорация', 'short': 'Мегакорп', 'price': 1500000, 'base_income': 10500, 'upgrade_cost': 1000000, 'world': 'earth'},
    'oil_rig': {'name': '🛢 Нефтяная вышка', 'short': 'Нефтевышка', 'price': 3500000, 'base_income': 24000, 'upgrade_cost': 2200000, 'world': 'earth'},
    'shipyard': {'name': '🚀 Космодромная верфь', 'short': 'Верфь', 'price': 10000000, 'base_income': 66000, 'upgrade_cost': 6500000, 'world': 'space'},
    'mars_colony': {'name': '🪐 Колония на Марсе', 'short': 'Марс', 'price': 80000000, 'base_income': 220000, 'upgrade_cost': 30000000, 'world': 'mars', 'legacy_price': 50000000},
    'lunar_corporation': {'name': '🌕 Лунная Корпорация', 'short': 'Лунная Корпорация', 'price': 130000000, 'base_income': 245000, 'upgrade_cost': 45000000, 'world': 'moon'},
    'solar_station': {'name': '☀️ Солнечная Станция', 'short': 'Солнечная Станция', 'price': 220000000, 'base_income': 270000, 'upgrade_cost': 70000000, 'world': 'solar'},
    'intergalactic_port': {'name': '🌌 Межгалактический Порт', 'short': 'Межгалактический Порт', 'price': 400000000, 'base_income': 300000, 'upgrade_cost': 120000000, 'world': 'galaxy'},
}

# Старые три стартовых предприятия исчезают из нового каталога, но их ID используются
# только для безопасной миграции живых Neon-профилей. Никакое состояние из rests_data.json
# при этом не подмешивается в Neon.
LEGACY_BUSINESS_REPLACEMENTS = {
    'bottles': 'smoothie_bar',
    'lemonade': 'food_truck',
    'shawarma': 'pizzeria',
}
LEGACY_BUSINESS_INFO = {
    'bottles': {'name': '🥫 Приём стеклотары', 'price': 200},
    'lemonade': {'name': '🍋 Лоток с лимонадом', 'price': 450},
    'shawarma': {'name': '🌯 Ларек с Шаурмой', 'price': 800},
}

CUSTOM_TITLE_CERT_PRICE = 15000

# ---------------------------------------------------------
# НОВЫЕ СИСТЕМЫ КЛАНА: ПУБЛИЧНЫЕ БИЗНЕСЫ / ОДЕЖДА / ДОМА / МОНОПОЛИЯ
# ---------------------------------------------------------
PET_CLOTHES = {
    'work_cap': {'name': '🧢 Кепка работяги', 'price': 2500, 'work_bonus': 0.15, 'desc': '+15% к зарплате и доходу от работы'},
    'garden_apron': {'name': '🧑‍🌾 Фартук садовода', 'price': 4000, 'garden_bonus': 1, 'desc': '+1 слот для растения'},
    'lucky_scarf': {'name': '🧣 Шарфик удачи', 'price': 6500, 'work_bonus': 0.10, 'garden_bonus': 1, 'desc': '+10% к работе и +1 слот сада'},
    'business_suit': {'name': '👔 Деловой костюм', 'price': 12000, 'business_bonus': 0.15, 'desc': '+15% к прибыли публичного бизнеса'},
    'royal_crown': {'name': '👑 Королевская корона', 'price': 30000, 'work_bonus': 0.20, 'business_bonus': 0.20, 'desc': '+20% к работе и публичному бизнесу'},
}

PERSONAL_HOUSES = {
    'room': {'name': '🛏 Комната в общежитии', 'price': 8000, 'income': 4, 'city': 'Ня-Сити'},
    'flat': {'name': '🏢 Уютная квартира', 'price': 30000, 'income': 15, 'city': 'Ня-Сити'},
    'cottage': {'name': '🏡 Загородный коттедж', 'price': 85000, 'income': 45, 'city': 'Пригород'},
    'mansion': {'name': '🏰 Роскошный особняк', 'price': 250000, 'income': 140, 'city': 'Элитный район'},
}

MONOPOLY_BOARD = [
    ('Старт', 0, 0), ('🍕 Пиццерия', 1200, 120), ('🎰 Казино', 1800, 180), ('🏖 Пляж', 2500, 250),
    ('🚉 Вокзал', 3200, 320), ('🍔 Бургерная', 4200, 420), ('🏬 ТЦ', 5500, 550), ('💎 Ювелирка', 7000, 700),
    ('🏨 Отель', 9000, 900), ('🚀 Космопорт', 12000, 1200), ('🏦 Банк', 15000, 1500), ('🏰 Замок', 20000, 2000)
]
active_monopoly = {}

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
    'slippers': {'name': '🩴 Дырявые сланцы', 'short': '🩴 Сланцы', 'price': 100, 'cd_cut': 0.01, 'desc': '-1% ко всем таймерам · Эконом: +1% к зарплате', 'tier': 0, 'msg_id': None, 'class': 'economy', 'work_bonus': 0.01},
    'rusty_bike': {'name': '🚲 Ржавый велосипед «Салют»', 'short': '🚲 Велосипед', 'price': 250, 'cd_cut': 0.02, 'desc': '-2% ко всем таймерам · Эконом: +1.5% к зарплате', 'tier': 1, 'msg_id': None, 'class': 'economy', 'work_bonus': 0.015},
    'skateboard': {'name': '🛹 Скейтборд Pro', 'short': '🛹 Скейт', 'price': 500, 'cd_cut': 0.03, 'desc': '-3% ко всем таймерам · Эконом: +2% к зарплате', 'tier': 2, 'msg_id': None, 'class': 'economy', 'work_bonus': 0.02},
    'scooter': {'name': '🛴 Электросамокат', 'short': '🛴 Самокат', 'price': 1500, 'cd_cut': 0.05, 'desc': '-5% ко всем таймерам · Эконом: +2.5% к зарплате', 'tier': 3, 'msg_id': 274, 'class': 'economy', 'work_bonus': 0.025},
    'vaz_2107': {'name': '🚗 ВАЗ-2107 «Семёрка» Боевая', 'short': '🚗 ВАЗ-2107', 'price': 3500, 'cd_cut': 0.08, 'desc': '-8% ко всем таймерам · Спорт: +3% к зарплате', 'tier': 4, 'msg_id': None, 'class': 'sport', 'work_bonus': 0.03},
    'bike': {'name': '🏍 Спортбайк Yamaha R1', 'short': '🏍 Спортбайк', 'price': 7500, 'cd_cut': 0.12, 'desc': '-12% ко всем таймерам · Спорт: +4% к зарплате', 'tier': 5, 'msg_id': 275, 'class': 'sport', 'work_bonus': 0.04},
    'supra': {'name': '🏎 Toyota Supra A80 Twin-Turbo', 'short': '🏎 Supra', 'price': 15000, 'cd_cut': 0.16, 'desc': '-16% ко всем таймерам · Спорт: +5% к зарплате', 'tier': 6, 'msg_id': None, 'class': 'sport', 'work_bonus': 0.05},
    'bmw': {'name': '🚗 BMW M5 CS', 'short': '🚗 BMW M5', 'price': 30000, 'cd_cut': 0.22, 'desc': '-22% ко всем таймерам · Luxury: +6% к зарплате', 'tier': 7, 'msg_id': 276, 'class': 'luxury', 'work_bonus': 0.06},
    'ferrari': {'name': '🏎 Ferrari SF90 Stradale', 'short': '🏎 Ferrari', 'price': 95000, 'cd_cut': 0.30, 'desc': '-30% ко всем таймерам · Luxury: +8% к зарплате', 'tier': 8, 'msg_id': 277, 'class': 'luxury', 'work_bonus': 0.08},
    'helicopter': {'name': '🚁 Вертолёт Robinson R44', 'short': '🚁 Вертолёт', 'price': 200000, 'cd_cut': 0.38, 'desc': '-38% ко всем таймерам · Luxury: +10% к зарплате', 'tier': 9, 'msg_id': None, 'class': 'luxury', 'work_bonus': 0.1},
    'rocket': {'name': '🚀 Ракета SpaceX Starship', 'short': '🚀 Starship', 'price': 350000, 'cd_cut': 0.45, 'desc': '-45% ко всем таймерам · Hyper: +12% к зарплате', 'tier': 10, 'msg_id': 278, 'class': 'hyper', 'work_bonus': 0.12},
    'yacht': {'name': '🛥 Суперяхта Олигарха Eclipse', 'short': '🛥 Суперяхта', 'price': 650000, 'cd_cut': 0.52, 'desc': '-52% ко всем таймерам · Hyper: +14% к зарплате', 'tier': 11, 'msg_id': None, 'class': 'hyper', 'work_bonus': 0.14},
    'teleport': {'name': '🌀 Квантовый Телепорт', 'short': '🌀 Телепорт', 'price': 1000000, 'cd_cut': 0.60, 'desc': '-60% ко всем таймерам · Hyper: +16% к зарплате', 'tier': 12, 'msg_id': None, 'class': 'hyper', 'work_bonus': 0.16},
    'private_jet': {'name': '🛩 Частный Бизнес-джет Gulfstream G650', 'short': '🛩 Бизнес-джет', 'price': 2500000, 'cd_cut': 0.68, 'desc': '-68% ко всем таймерам · Galactic: +18% к зарплате', 'tier': 13, 'msg_id': None, 'class': 'galactic', 'work_bonus': 0.18},
    'star_cruiser': {'name': '🛸 Космический Крейсер Империи', 'short': '🛸 Космокрейсер', 'price': 10000000, 'cd_cut': 0.75, 'desc': '-75% ко всем таймерам · Galactic: +20% к зарплате', 'tier': 14, 'msg_id': None, 'class': 'galactic', 'work_bonus': 0.2}
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
    'vip_griffin': {'name': '👑 Королевский Грифон', 'short': '👑 Грифон', 'price': 0, 'luck_bonus': 150, 'desc': '+150% ко всей удаче, благословение небес (VIP Питомец за 5 ⭐️)'},
    'moon_fox': {'name': '🌙 Лунный Фокс', 'short': '🌙 Лунный Фокс', 'price': 0, 'luck_bonus': 200, 'desc': '+200% к удаче во всем, усиленное ночное благословение (лимит 5 Stars-питомцев)'}
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
    'mars_owner': {'title': '🪐 Первопроходец Марса', 'desc': 'Стать владельцем Марса', 'stat': 'mars_owned', 'target': 1, 'reward': 5000},
    'port_owner': {'title': '🌌 Владелец Межгалактического Порта', 'desc': 'Стать владельцем Межгалактического Порта', 'stat': 'port_owned', 'target': 1, 'reward': 15000},
    'empire_10': {'title': '👑 Империя', 'desc': 'Одновременно владеть 10 предприятиями', 'stat': 'biz_owned_total', 'target': 10, 'reward': 8000},
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
stars_payment_lock = threading.RLock()
last_chat_activity = {}
BOT_STARTED_AT = time.time()


# ---------------------------------------------------------
# ЗАЩИТА ОТ ГОНOК / DOUBLE-CLICK / DOUBLE-SPEND
# ---------------------------------------------------------
# Реализация вынесена в core/locks.py.
# ---------------------------------------------------------

# ---------------------------------------------------------
# БАЗА ДАННЫХ И АТОМАРНЫЕ БЕКАПЫ
# ---------------------------------------------------------
def _default_data():
    return {
        'rests': {},
        'history': {},
        'settings': {},
        'moderation': {},
        'chat_admins': {},
        'admin_permissions': {},
        'anonymous_messages': {},
        'tgift_states': {},
        'tgift_orders': {},
        'economy': {},
        'promos': {
            'FIX': {'reward': 5000, 'exp': 100, 'claimed': []},
            'fix': {'reward': 5000, 'exp': 100, 'claimed': []}
        },
        'market': {},
        'marriages': {},
        'lottery': {'tickets': {}, 'pot': 0, 'last_draw': 0},
        'bot_active': True,
        'bot_status_note': '',
        'bot_maintenance_started_at': 0,
        'casino_pool': 1000000,
        'safe': {'code': f"{random.randint(0, 9999):04d}", 'pot': 30000, 'tried_codes': []},
        'daily_memes': [],
        'processed_stars_charges': [],
        'crypto_transactions': [],
        'stars_payment_log': {},
        'meme_winners': [],
        'chest_claims': {},
        'bot_chats': {},
        'bot_news': [],
        'banned_chats': [],
        'guilds': {},
        'player_market': {},
        'raid': {},
        'season': {'number': 1, 'started_at': time.time(), 'archive': []},
        'economic_event': {'id': None, 'started_at': 0},
        'stars_hard_limited_stock': {},
        'stars_limited_stock': {},
        '_meta': {'saved_at': 0.0}
    }

def _normalize_loaded_data(data):
    """Keep the same defaults/compatibility rules as the old JSON loader."""
    if not isinstance(data, dict):
        data = {}
    base = _default_data()
    # Keep unknown top-level fields from older/newer bot versions instead of
    # silently deleting them on the next save. Known defaults below still
    # normalize the structures this version relies on.
    base.update(data)
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
    if not isinstance(base.get('crypto_transactions'), list):
        base['crypto_transactions'] = []
    if not isinstance(base.get('stars_payment_log'), dict):
        base['stars_payment_log'] = {}
    if 'meme_winners' not in base:
        base['meme_winners'] = []
    if 'chest_claims' not in base:
        base['chest_claims'] = {}
    if not isinstance(base.get('bot_chats'), dict):
        base['bot_chats'] = {}
    if not isinstance(base.get('banned_chats'), (list, dict, set)):
        base['banned_chats'] = []
    elif isinstance(base.get('banned_chats'), set):
        base['banned_chats'] = list(base['banned_chats'])
    if not isinstance(base.get('stars_hard_limited_stock'), dict):
        base['stars_hard_limited_stock'] = {}
    if not isinstance(base.get('stars_limited_stock'), dict):
        base['stars_limited_stock'] = {}
    for _dict_key in ('rests', 'history', 'settings', 'moderation', 'chat_admins', 'admin_permissions', 'anonymous_messages', 'economy', 'market', 'marriages'):
        if not isinstance(base.get(_dict_key), dict):
            base[_dict_key] = {}
    if not isinstance(base.get('lottery'), dict):
        base['lottery'] = {'tickets': {}, 'pot': 0, 'last_draw': 0}
    else:
        lottery = base['lottery']
        if not isinstance(lottery.get('tickets'), dict): lottery['tickets'] = {}
        try: lottery['pot'] = max(0, int(lottery.get('pot', 0) or 0))
        except (TypeError, ValueError): lottery['pot'] = 0
        try: lottery['last_draw'] = float(lottery.get('last_draw', 0) or 0)
        except (TypeError, ValueError): lottery['last_draw'] = 0
    if not isinstance(base.get('moderation'), dict):
        base['moderation'] = {}
    if not isinstance(base.get('guilds'), dict): base['guilds'] = {}
    if not isinstance(base.get('player_market'), dict): base['player_market'] = {}
    if not isinstance(base.get('raid'), dict): base['raid'] = {}
    if not isinstance(base.get('started_users'), dict): base['started_users'] = {}
    if not isinstance(base.get('anonymous_messages'), dict): base['anonymous_messages'] = {}
    if not isinstance(base.get('tgift_states'), dict): base['tgift_states'] = {}
    if not isinstance(base.get('tgift_orders'), dict): base['tgift_orders'] = {}
    if not isinstance(base.get('season'), dict): base['season'] = {'number': 1, 'started_at': time.time(), 'archive': []}
    if not isinstance(base.get('economic_event'), dict): base['economic_event'] = {'id': None, 'started_at': 0}
    if not isinstance(base.get('_meta'), dict): base['_meta'] = {'saved_at': 0.0}
    base['_meta']['saved_at'] = float(base['_meta'].get('saved_at', 0) or 0)
    return base

def load_data():
    """Load bot state through the shared persistence service."""
    return saving_service.load_data(
        _default_data,
        _normalize_loaded_data,
    )


def mark_dirty():
    global db_dirty, db_version, last_db_change_at
    with db_lock:
        db_dirty = True
        db_version += 1
        last_db_change_at = time.time()

def save_data(send_backup=False):
    with DB_SAVE_LOCK:
        with BALANCE_TX_LOCK:
            return _save_data_locked(send_backup)


def critical_save(reason='critical state change', send_backup=False, retries=2):
    """Force persistence for money/purchase changes; never silently ignore Neon failures."""
    last_error = None
    retries = max(1, int(retries))
    for attempt in range(1, retries + 1):
        try:
            ok = bool(save_data(send_backup=send_backup))
            if ok:
                return True
            last_error = RuntimeError('Neon persistence failed')
        except Exception as exc:
            last_error = exc
        if attempt < retries:
            time.sleep(0.35 * attempt)
    print(f'[CRITICAL SAVE FAILED] {reason}: {last_error}')
    return False


def _save_data_locked(send_backup=False):
    with db_lock:
        snapshot = copy.deepcopy(db)
        snapshot['_meta'] = {'saved_at': time.time()}
        snapshot_version = db_version

    def _get_version():
        with db_lock:
            return db_version

    def _set_dirty(value):
        global db_dirty
        with db_lock:
            db_dirty = bool(value)

    return saving_service.save_data(
        db,
        db_lock=db_lock,
        db_version=db_version,
        db_version_getter=_get_version,
        db_dirty_setter=_set_dirty,
        data_file=DATA_FILE,
        send_backup=send_backup,
        db_channel_id=DB_CHANNEL_ID,
        bot_instance=bot,
    )

# База загружается один раз после объявления loader/normalizer.
# Это сохраняет исходную архитектуру монолита и делает db доступной
# всем обработчикам и сервисам ниже.
db = load_data()

# ---------------------------------------------------------
# МОНИТОРИНГ ГРУПП, ГДЕ НАХОДИТСЯ БОТ
# ---------------------------------------------------------
def _chat_type_label(chat_type):
    return {'group': 'Группа', 'supergroup': 'Супергруппа', 'channel': 'Канал', 'private': 'Личка'}.get(chat_type, str(chat_type or 'Неизвестно'))

def track_bot_chat(chat, status='active', touch_activity=True):
    """Сохраняет актуальную информацию о группах без удаления старых записей."""
    if not chat or getattr(chat, 'type', '') not in ('group', 'supergroup'):
        return None
    try:
        chat_id = str(int(chat.id))
    except Exception:
        return None
    now_ts = time.time()
    chats = db.setdefault('bot_chats', {})
    item = chats.setdefault(chat_id, {
        'chat_id': int(chat.id), 'title': getattr(chat, 'title', None) or 'Без названия',
        'username': getattr(chat, 'username', None), 'type': getattr(chat, 'type', 'group'),
        'first_seen': now_ts, 'last_seen': now_ts, 'last_activity': now_ts, 'status': 'active',
        'join_notified_at': 0
    })
    changed = False
    for field, value in [('title', getattr(chat, 'title', None) or 'Без названия'), ('username', getattr(chat, 'username', None)), ('type', getattr(chat, 'type', 'group')), ('status', status)]:
        if item.get(field) != value:
            item[field] = value; changed = True
    previous_seen = float(item.get('last_seen', 0) or 0)
    if now_ts - previous_seen >= 60:
        item['last_seen'] = now_ts
        changed = True
    if touch_activity:
        previous_activity = float(item.get('last_activity', 0) or 0)
        item['last_activity'] = now_ts
        last_chat_activity[int(chat.id)] = now_ts
        # Persist activity at most once per minute; the live cache stays exact.
        if now_ts - previous_activity >= 60:
            changed = True
    if changed:
        mark_dirty()
    return item

def group_info_refresh_worker():
    """Периодически обновляет число участников сохранённых активных групп.
    Названия, username, статус и последняя активность обновляются по входящим
    событиям, а количество участников — отдельным редким запросом Telegram.
    """
    while True:
        time.sleep(1800)  # раз в 30 минут, чтобы не создавать лишнюю нагрузку на API
        if not db.get('bot_active', True):
            continue
        try:
            changed = False
            for item in list(db.get('bot_chats', {}).values()):
                if not isinstance(item, dict) or item.get('status') != 'active':
                    continue
                cid = item.get('chat_id')
                if not cid:
                    continue
                try:
                    members = bot.get_chat_member_count(int(cid))
                    if item.get('member_count') != members:
                        item['member_count'] = members
                        item['member_count_updated_at'] = time.time()
                        changed = True
                except Exception as e:
                    # Группа могла быть удалена/бот мог потерять доступ — не падаем всем воркером.
                    print(f'[GROUP INFO REFRESH] {cid}: {e}')
            if changed:
                mark_dirty()
                save_data()
        except Exception as e:
            print(f'[GROUP INFO WORKER ERROR] {e}')

def _fmt_duration(seconds):
    seconds = max(0, int(seconds))
    days, seconds = divmod(seconds, 86400); hours, seconds = divmod(seconds, 3600); minutes, seconds = divmod(seconds, 60)
    parts = []
    if days: parts.append(f'{days}д')
    if hours or days: parts.append(f'{hours}ч')
    if minutes or hours or days: parts.append(f'{minutes}м')
    parts.append(f'{seconds}с')
    return ' '.join(parts)

def _fmt_seen(ts):
    if not ts: return 'нет данных'
    try: return datetime.fromtimestamp(float(ts), tz=now_msk().tzinfo).strftime('%d.%m.%Y %H:%M')
    except Exception: return 'нет данных'


MAINTENANCE_MESSAGE = (
    "🔧 <b>ТЕХНИЧЕСКИЕ РАБОТЫ</b>\n\n"
    "<blockquote>NyaBot временно приостановил работу.\n"
    "Сейчас мы исправляем технические проблемы и обновляем системы.</blockquote>\n\n"
    "🕐 Игровые и экономические операции временно недоступны.\n"
    "😺 Спасибо за терпение!"
)

RESTORE_MESSAGE = (
    "🟢 <b>NYABOT СНОВА В СТРОЮ</b>\n\n"
    "<blockquote>Технические работы завершены.\n"
    "Все системы снова работают.</blockquote>\n\n"
    "💾 Данные сохранены.\n"
    "😼 Можно возвращаться к игре."
)


def _known_broadcast_chat_ids():
    """Return deduplicated chats that NyaBot has learned about from live traffic."""
    ids = set()
    with db_lock:
        for item in (db.get('bot_chats') or {}).values():
            if not isinstance(item, dict) or item.get('status') != 'active':
                continue
            try:
                cid = int(item.get('chat_id'))
            except (TypeError, ValueError):
                continue
            if cid:
                ids.add(cid)
        for econ in (db.get('economy') or {}).values():
            if not isinstance(econ, dict):
                continue
            for cid in econ.get('chat_ids', []) or []:
                try:
                    normalized = int(cid)
                except (TypeError, ValueError):
                    continue
                if normalized:
                    ids.add(normalized)
    return sorted(ids)


def _broadcast_error_means_inactive(exc):
    msg = str(exc).lower()
    return any(marker in msg for marker in (
        'bot was kicked', 'chat not found', 'user is deactivated',
        'forbidden: bot was blocked', 'forbidden: bot is not a member',
        'have no rights to send a message', 'not enough rights'
    ))


def broadcast_system_message(text):
    """Broadcast a system notice to every known chat, without stopping the bot."""
    sent = failed = 0
    for chat_id in _known_broadcast_chat_ids():
        try:
            bot.send_message(chat_id, text, parse_mode='HTML', disable_web_page_preview=True)
            sent += 1
        except Exception as exc:
            failed += 1
            if _broadcast_error_means_inactive(exc) and chat_id < 0:
                with db_lock:
                    item = (db.get('bot_chats') or {}).get(str(chat_id))
                    if isinstance(item, dict):
                        item['status'] = 'inactive'
                        item['broadcast_failed_at'] = time.time()
                        item['broadcast_error'] = str(exc)[:300]
                        mark_dirty()
            print(f'[SYSTEM BROADCAST] {chat_id}: {exc}')
    if sent or failed:
        mark_dirty()
    return sent, failed


def publish_bot_news(title, text, kind='system'):
    """Append a bounded live-world news item; this is a Neon-backed game feed."""
    item = {
        'title': str(title)[:120],
        'text': str(text)[:500],
        'kind': str(kind)[:32],
        'time': time.time(),
        'created_at': now_msk().strftime('%d.%m.%Y %H:%M'),
    }
    with db_lock:
        news = db.setdefault('bot_news', [])
        if not isinstance(news, list):
            news = []
            db['bot_news'] = news
        news.append(item)
        del news[:-100]
        mark_dirty()
    return item

def _bot_chat_items(active_only=False):
    with db_lock:
        snapshot = list(db.get('bot_chats', {}).values())
    items = []
    for item in snapshot:
        if isinstance(item, dict) and (not active_only or item.get('status') == 'active'):
            items.append(item)
    return sorted(items, key=lambda x: x.get('last_activity', x.get('last_seen', 0)), reverse=True)

def _owner_only(message):
    if not message or not getattr(message, 'from_user', None) or message.from_user.id != ADMIN_ID:
        try: bot.reply_to(message, '❌ Эта команда доступна только владельцу бота.')
        except Exception: pass
        return False
    return True

def _global_message_stats():
    with db_lock:
        total = users = 0
        for econ in list(db.get('economy', {}).values()):
            if not isinstance(econ, dict):
                continue
            count = int((econ.get('msg_stats') or {}).get('total_count', 0) or 0)
            if count:
                users += 1
                total += count
        return total, users

def setup_bot_commands():
    # Короткое меню Telegram. Остальные команды остаются рабочими при ручном вводе.
    commands = [
        BotCommand('menu', '📱 Меню'),
        BotCommand('profile', '👤 Профиль'),
        BotCommand('balance', '🪙 Баланс'),
        BotCommand('business', '🏢 Бизнесы: купить и улучшать'),
        BotCommand('collect', '💰 Собрать прибыль бизнесов'),
        BotCommand('shop', '🏪 Обычный магазин'),
        BotCommand('bank', '🏦 Банк'),
        BotCommand('miner', '💻 Крипто-ферма'),
        BotCommand('market', '📈 Биржа'),
        BotCommand('portfolio', '💼 Крипто-портфель'),
        BotCommand('pet', '🐾 Питомец'),
        BotCommand('tasks', '📋 Задания'),
        BotCommand('achievements', '🏆 Достижения'),
        BotCommand('lottery', '🎟 Лотерея'),
        BotCommand('games', '🎮 Игры и мини-игры'),
        BotCommand('coinflip', '🪙 Монетка'),
        BotCommand('garage', '🏎 Гараж'),
        BotCommand('stars', '⭐️ Stars магазин'),
        BotCommand('help', '❓ Помощь'),
        BotCommand('settings', '⚙️ Настройки'),
        BotCommand('gifttg', '🎁 Telegram Gifts'),
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
            'flood_admins': False,
            'auto_reactions': True,
            'welcome_enabled': True,
            'timezone_offset': 3,
            'remind_minutes': 60,
            'language': 'ru',
            'warn_limit': 3,
            'admin_functions_enabled': True
        }
    else:
        # Новые настройки добавляются без сброса старых параметров.
        sett = db['settings'][str_chat]
        sett.setdefault('rp_enabled', True)
        sett.setdefault('flood_protection', False)
        sett.setdefault('flood_admins', False)
        sett.setdefault('auto_reactions', True)
        sett.setdefault('welcome_enabled', True)
        sett.setdefault('language', 'ru')
        sett.setdefault('warn_limit', 3)
        sett.setdefault('admin_functions_enabled', True)
        # Раньше стоял жёсткий лимит 30/60 дней — теперь ограничения нет.
        # Не вызываем mark_dirty() при обычном чтении настроек.
        if sett.get('max_days') is not None:
            sett['max_days'] = None
            mark_dirty()
    return db['settings'][str_chat]

def get_market_data():
    with MARKET_LOCK:
        return _get_market_data_locked()

def _get_market_data_locked():
    if 'market' not in db or not db['market']:
        db['market'] = json.loads(json.dumps(MARKET_DEFAULT))
        mark_dirty()

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


def account_exp_for_level(level):
    """Минимальный account_exp, необходимый для указанного уровня."""
    try:
        level = max(1, int(level))
    except (TypeError, ValueError):
        return 0
    if level <= 1:
        return 0
    # get_account_level() использует порог следующего уровня: 100 * level^1.5.
    return int(100 * ((level - 1) ** 1.5))

def is_vip_active(econ):
    return bool(econ and (econ.get('vip_forever') or econ.get('vip_until', 0) > time.time()))

def get_donor_title_buffs(econ):
    if not econ or not isinstance(econ, dict):
        return {}
    active_t = econ.get('active_title')
    if active_t in TITLES:
        return TITLES[active_t].get('donor_buffs', {}) or {}
    return {}

def get_title_work_bonus(econ):
    return float(get_donor_title_buffs(econ).get('work_bonus', 0.0))

def get_title_bonus_multiplier(econ):
    return float(get_donor_title_buffs(econ).get('bonus_mult', 0.0))

def get_title_business_bonus(econ):
    return float(get_donor_title_buffs(econ).get('business_bonus', 0.0))

def get_vip_work_bonus(econ):
    return 0.10 if is_vip_active(econ) else 0.0

def get_vip_business_bonus(econ):
    return 0.10 if is_vip_active(econ) else 0.0

def get_user_cd_reduction(econ):
    if not econ or not isinstance(econ, dict):
        return 0.0
    reduction = 0.0
    veh = econ.get('equipped_vehicle') or econ.get('vehicle')
    veh_info = VEHICLES.get(veh) or DONOR_VEHICLES.get(veh)
    if veh_info:
        reduction += float(veh_info.get('cd_cut', 0.0) or 0.0)

    active_t = econ.get('active_title')
    if active_t and active_t in TITLES:
        t_info = TITLES[active_t]
        if t_info.get('buff') == 'cd_reduction':
            reduction += (t_info.get('val', 0) / 100.0)

    if is_vip_active(econ):
        reduction += 0.35

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

    for num_field in ['balance', 'bank_deposit', 'account_exp', 'work_exp', 'smeh', 'cooked_meals', 'bonus_streak', 'stars_donated', 'bp_exp', 'season_points']:
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

    # Объединяем полный гараж, а не только одну ранее экипированную машину.
    dest_vehicles = dest.setdefault('vehicle_inventory', [])
    src_vehicles = src.get('vehicle_inventory', [])
    if not isinstance(dest_vehicles, list):
        dest_vehicles = []
        dest['vehicle_inventory'] = dest_vehicles
    for vid in src_vehicles if isinstance(src_vehicles, list) else []:
        if vid in VEHICLES or vid in DONOR_VEHICLES:
            if vid not in dest_vehicles:
                dest_vehicles.append(vid)

    v_dest = dest.get('equipped_vehicle') or dest.get('vehicle')
    v_src = src.get('equipped_vehicle') or src.get('vehicle')
    tier_dest = VEHICLES[v_dest]['tier'] if v_dest in VEHICLES else -1
    tier_src = VEHICLES[v_src]['tier'] if v_src in VEHICLES else -1
    if v_dest not in dest_vehicles and v_dest in (VEHICLES.keys() | DONOR_VEHICLES.keys()):
        dest_vehicles.append(v_dest)
    if v_src not in dest_vehicles and v_src in (VEHICLES.keys() | DONOR_VEHICLES.keys()):
        dest_vehicles.append(v_src)
    if v_src and (not v_dest or tier_src > tier_dest):
        dest['equipped_vehicle'] = v_src
        dest['vehicle'] = v_src
    elif v_dest:
        dest['equipped_vehicle'] = v_dest
        dest['vehicle'] = v_dest

    for eq in ['equipped_rod', 'equipped_bow', 'active_title', 'custom_title', 'badge', 'profile_theme', 'pfp_file_id', 'profile_font', 'premium_emoji_theme', 'premium_emoji_enabled']:
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

    donor_biz_dest = dest.setdefault('donor_businesses', {})
    donor_biz_src = src.get('donor_businesses', {})
    if isinstance(donor_biz_src, dict):
        for b_k, b_v in donor_biz_src.items():
            if b_k in DONOR_BUSINESSES:
                donor_biz_dest[b_k] = max(int(donor_biz_dest.get(b_k, 1) or 1), int(b_v or 1))

    biz_dest = dest.setdefault('businesses', {})
    biz_src = src.get('businesses', {})
    for b_k, b_v in biz_src.items():
        if b_k not in biz_dest:
            biz_dest[b_k] = b_v

    bl_dest = dest.setdefault('biz_levels', {})
    bl_src = src.get('biz_levels', {})
    for bl_k, bl_v in bl_src.items():
        bl_dest[bl_k] = max(bl_dest.get(bl_k, 1), bl_v)

    price_dest = dest.setdefault('biz_purchase_price', {})
    price_src = src.get('biz_purchase_price', {})
    for price_k, price_v in price_src.items():
        if price_k not in price_dest:
            price_dest[price_k] = price_v
    tx_dest = dest.setdefault('business_transactions', [])
    tx_src = src.get('business_transactions', [])
    if isinstance(tx_src, list):
        tx_dest.extend(tx_src[-200:])
        del tx_dest[:-200]
    dest['business_tax_paid'] = int(dest.get('business_tax_paid', 0) or 0) + int(src.get('business_tax_paid', 0) or 0)

    pet_dest=dest.setdefault('pet_inventory',[])
    for pet_id in src.get('pet_inventory',[]) or []:
        if pet_id in PETS_DATA and pet_id not in pet_dest: pet_dest.append(pet_id)
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
        # Telegram display names are not unique. Using a display name here can
        # merge two unrelated legacy accounts and literally move their coins/items.
        # A known user ID may only inherit an old tag account when the tag is the
        # current unique username. Legacy no-username accounts must be migrated
        # explicitly rather than guessed.
        target_tags = [clean_u] if clean_u else []

        for tag_candidate in set(target_tags):
            old_tag_key = f"tag_{tag_candidate}"
            if old_tag_key in db['economy'] and old_tag_key != key:
                old_data = db['economy'].get(old_tag_key)
                # Never merge an old username/tag account that is already bound
                # to a different Telegram ID: usernames can be reused.
                old_owner = old_data.get('user_id') if isinstance(old_data, dict) else None
                if old_owner not in (None, user_id):
                    continue
                old_data = db['economy'].pop(old_tag_key)
                if key in db['economy']:
                    merge_user_econ_data(db['economy'][key], old_data)
                else:
                    db['economy'][key] = old_data
                mark_dirty()

    if key not in db['economy']:
        db['economy'][key] = {
            'display_name': clean_d or 'Пользователь',
            'username': clean_u,
            'user_id': user_id,
            'balance': 50,
            'karma': 0,
            'language': 'ru'
        }
        mark_dirty()

    u_data = db['economy'][key]
    u_data.setdefault('language', 'ru')

    # Миграция старых донатных значков: в прошлой версии они имели
    # ключи vip_badge_*. Не удаляем старые права и не заставляем игрока
    # покупать их заново — переносим их на текущие canonical ID.
    _legacy_badges = {
        'vip_badge_crown': 'badge_crown',
        'vip_badge_star': 'badge_star',
        'vip_badge_gem': 'badge_gem',
        'vip_badge_angel': 'badge_angel',
        'vip_badge_galaxy': 'badge_galaxy',
        'vip_badge_dragon': 'badge_dragon',
    }
    _paid = u_data.setdefault('paid_stars_items', [])
    if not isinstance(_paid, list):
        _paid = []
        u_data['paid_stars_items'] = _paid
    # Durable Stars entitlements: restore convenience flags if an older
    # snapshot lost them but retained the paid entitlement list.
    if 'bp_premium' in _paid and not u_data.get('bp_premium'):
        u_data['bp_premium'] = True
        mark_dirty()
    if 'pass_forever' in _paid and not u_data.get('vip_forever'):
        u_data['vip_forever'] = True
        mark_dirty()
    _inv = u_data.setdefault('inventory', [])
    if not isinstance(_inv, list):
        _inv = []
        u_data['inventory'] = _inv
    for _old_badge, _new_badge in _legacy_badges.items():
        if _old_badge in _paid:
            if _new_badge not in _paid:
                _paid.append(_new_badge)
            _emoji = STARS_COSMETICS[_new_badge]['emoji']
            if _emoji not in _inv:
                _inv.append(_emoji)
            _paid.remove(_old_badge)
            mark_dirty()

    # Даже если старый entitlement хранился только в inventory, сохраняем
    # соответствующий Stars-entitlement, чтобы предмет снова отображался
    # как купленный и не терялся из донатной коллекции.
    _emoji_to_badge = {
        '👑': 'badge_crown', '⭐️': 'badge_star', '⭐': 'badge_star',
        '💎': 'badge_gem', '🪽': 'badge_angel', '🌌': 'badge_galaxy',
        '🐲': 'badge_dragon', '🐉': 'badge_dragon',
    }
    for _emoji, _badge_id in _emoji_to_badge.items():
        if _emoji in _inv and _badge_id not in _paid:
            _paid.append(_badge_id)
            mark_dirty()

    # Миграция гаража: все купленные машины сохраняются, а vehicle/equipped_vehicle
    # остаётся совместимым алиасом для текущей экипированной машины.
    vehicle_inventory = u_data.setdefault('vehicle_inventory', [])
    if not isinstance(vehicle_inventory, list):
        vehicle_inventory = []
        u_data['vehicle_inventory'] = vehicle_inventory
    legacy_vehicle = u_data.get('vehicle')
    if legacy_vehicle in VEHICLES or legacy_vehicle in DONOR_VEHICLES:
        if legacy_vehicle not in vehicle_inventory:
            vehicle_inventory.append(legacy_vehicle)
    equipped = u_data.get('equipped_vehicle')
    if equipped not in vehicle_inventory:
        equipped = legacy_vehicle if legacy_vehicle in vehicle_inventory else (vehicle_inventory[-1] if vehicle_inventory else None)
        u_data['equipped_vehicle'] = equipped
    if equipped and u_data.get('vehicle') != equipped:
        u_data['vehicle'] = equipped
        mark_dirty()
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
        ('last_dick_time', 0), ('fap_count', 0), ('fap_date', ''), ('last_fap_time', 0), ('mog_count', 0),
        ('chromosomes', 46), ('last_chromosomes_time', 0), ('last_wheel_time', 0),
        ('last_pet_walk', 0), ('last_pet_care', 0), ('rest_rewards_count', 0),
        ('titles', []), ('active_title', None), ('custom_title', None),
        ('has_custom_title_cert', False), ('rings', []), ('active_ring', None),
        ('marriage', None), ('businesses', {}), ('biz_levels', {}), ('biz_purchase_price', {}), ('business_transactions', []), ('business_tax_paid', 0),
        ('last_biz_collect', time.time()), ('biz_last_collect', {}), ('biz_income_carry', {}), ('donor_business_purchased_at', {}), ('vehicle', None), ('vehicle_inventory', []), ('equipped_vehicle', None), ('donor_businesses', {}),
        ('equipped_rod', None), ('equipped_bow', None), ('rod_inventory', []), ('bow_inventory', []), ('daily_tasks_date', ''),
        ('daily_progress', {}), ('daily_claimed', []), ('weekly_tasks_yearweek', ''),
        ('weekly_progress', {}), ('weekly_claimed', []), ('fish_inventory', {}),
        ('hunt_inventory', {}), ('cooked_meals', 0), ('crypto_portfolio', {}),
        ('last_fish_time', 0), ('last_hunt_time', 0), ('achievements', []),
        ('stats', {}), ('work_exp', 0), ('last_work_time', 0), ('last_train_time', 0),
        ('pet', None), ('pet_inventory', []), ('paid_stars_items', []), ('chest_streak', 0), ('bank_deposit', 0), ('last_bank_calc', time.time()),
        ('last_case_time', 0), ('last_rob_time', 0), ('last_trash_time', 0),
        ('profile_theme', 'default'), ('purchased_themes', ['default']),
        ('profile_font', 'default'), ('purchased_fonts', ['default']),
        ('profile_gifs', []), ('profile_gif', None), ('active_limited_effect', None),
        ('premium_emoji_theme', 'nya'), ('premium_emoji_enabled', True),
        ('backpack', {'energy_drink': 0, 'luck_clover': 0, 'alarm_system': 0, 'invis_mask': 0, 'garden_fertilizer': 0}),
        ('luck_clover_until', 0), ('invis_until', 0), ('daily_casino_win', 0),
        ('daily_casino_profit', 0), ('daily_transferred', 0), ('daily_stats_date', ''),
        ('karma', 0), ('chat_ids', []), ('world_titles', []), ('legacy_assets', []), ('news_seen', 0), ('garden', None), ('garden_capacity', 1), ('pet_clothes', []), ('equipped_pet_clothes', None), ('public_business', None), ('public_business_workers', []), ('employer_salary', None), ('home', None), ('home_installment', None), ('stream_studio', {'mic': 1, 'webcam': 1, 'light': 1}), 
        ('last_stream_time', 0), ('last_cmd_time', 0), ('last_cmd_text', ""), ('last_activity_reward_time', 0),
        ('loan', {'amount': 0, 'due': 0, 'defaulted': False}),
        ('bonus_streak', 0), ('last_streak_time', 0),
        ('mini_daily_claimed', ''), ('mini_daily_date', ''), ('mini_daily_streak', 0),
        ('last_energy_drink_time', 0), ('vip_until', 0), ('vip_forever', False), ('stars_donated', 0), ('is_sheriff', False), ('jail_until', 0), ('disease', None), ('disease_immunity_until', 0), ('bp_exp', 0), ('bp_claimed_free', []), ('bp_claimed_prem', []), ('bp_premium', False), ('last_safe_try', 0), ('guild_id', None), ('season_points', 0), ('season_claimed', False), ('crafted_items', {}), ('crypto_trade_history', []),
    ]:
        if field not in u_data:
            u_data[field] = default

    # Инвентарь питомцев: старый активный питомец автоматически переносится в коллекцию.
    pet_inventory = u_data.setdefault('pet_inventory', [])
    if not isinstance(pet_inventory, list):
        pet_inventory = []; u_data['pet_inventory'] = pet_inventory
    legacy_pet = u_data.get('pet')
    if isinstance(legacy_pet, dict) and legacy_pet.get('id') and legacy_pet.get('id') in PETS_DATA and legacy_pet.get('id') not in pet_inventory:
        pet_inventory.append(legacy_pet.get('id'))
        mark_dirty()

    # Старые сохранения: уже надетая снасть считается купленной, чтобы после
    # обновления игрок не мог потерять её статус или быть ошибочно списан повторно.
    if u_data.get('equipped_rod') and u_data.get('equipped_rod') in RODS:
        rods = u_data.setdefault('rod_inventory', [])
        if u_data['equipped_rod'] not in rods:
            rods.append(u_data['equipped_rod'])
    for _num_field in ('balance', 'bank_deposit', 'account_exp', 'work_exp', 'stars_donated', 'bp_exp', 'season_points'):
        try:
            u_data[_num_field] = int(u_data.get(_num_field, 0) or 0)
        except (TypeError, ValueError):
            u_data[_num_field] = 0

    if u_data.get('equipped_bow') and u_data.get('equipped_bow') in BOWS:
        bows = u_data.setdefault('bow_inventory', [])
        if u_data['equipped_bow'] not in bows:
            bows.append(u_data['equipped_bow'])

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

    # v0.3 business migration is lazy and idempotent. Neon remains the source
    # of truth; only legacy business IDs already present in this live profile
    # are transformed. The helper is defined later in this monolith but exists
    # by the time runtime requests reach this getter.
    migration_fn = globals().get('_migrate_legacy_businesses')
    if migration_fn:
        migration_fn(u_data)

    return u_data

# get_user_econ mutates shared economy records during lazy migrations/defaulting.
# Protect the whole operation so Flask requests and background workers cannot
# interleave a read-modify-write sequence for the same process. RLock is used
# because helper functions invoked by get_user_econ may also touch the DB lock.
_get_user_econ_unlocked = get_user_econ
def get_user_econ(user_id=None, user_tag=None, username=None):
    with db_lock:
        return _get_user_econ_unlocked(user_id, user_tag, username)


# Подключаем staged service layer после объявления канонического get_user_econ.
# Старые функции остаются совместимыми точками входа; сервисы используют ту же
# общую db/lock/mark_dirty и не создают вторую систему хранения.
economy_service.configure(
    db=db,
    db_lock=db_lock,
    mark_dirty=mark_dirty,
    get_user_econ=get_user_econ,
    titles=TITLES,
    vehicles=VEHICLES,
    donor_vehicles=DONOR_VEHICLES,
    season_rollover=lambda: globals().get('season_rollover', lambda: None)(),
)
inventory_service.configure(
    db=db,
    db_lock=db_lock,
    mark_dirty=mark_dirty,
)
stars_service.configure(
    db=db,
    db_lock=db_lock,
    mark_dirty=mark_dirty,
    save_now=lambda: save_data(send_backup=False),
    get_user=get_user_econ,
    titles=TITLES,
    themes=THEMES,
    pets_data=PETS_DATA,
)
# Подключаем локализацию после объявления зависимых функций.
configure_localization(
    get_user_econ=get_user_econ,
    get_chat_settings=get_chat_settings,
)
install_telegram_localization(bot)

def recover_stars_entitlements_from_journal():
    """Repair durable Stars Pass entitlements from completed payment journals."""
    logs = db.get('stars_payment_log', {}) or {}
    if not isinstance(logs, dict):
        return False
    changed = False
    now = time.time()
    for charge_id, entry in list(logs.items()):
        if not isinstance(entry, dict):
            continue
        status = str(entry.get('status', '') or '')
        grant_status = str(entry.get('grant_status', '') or '')
        # If the entitlement was applied and journaled but the final processed
        # marker was interrupted, complete the journal without granting twice.
        if status == 'processing' and grant_status == 'granted':
            entry['status'] = 'completed'
            entry['finished_at'] = time.time()
            processed = db.setdefault('processed_stars_charges', [])
            charge_key = str(charge_id)
            if charge_key not in processed:
                processed.append(charge_key)
                if len(processed) > 10000:
                    del processed[:-10000]
            changed = True
            status = 'completed'
        if status != 'completed':
            continue
        payload = str(entry.get('payload', '') or '')
        buyer_id = int(entry.get('buyer_id', 0) or 0)
        if buyer_id <= 0:
            continue
        try:
            econ = get_user_econ(user_id=buyer_id)
        except Exception:
            continue
        if payload.startswith('vippass_'):
            pass_key = payload.split(':', 1)[0].replace('vippass_', '', 1)
            item = STARS_VIP_PASS.get(pass_key)
            if not item:
                continue
            paid = econ.setdefault('paid_stars_items', [])
            if not isinstance(paid, list):
                paid = []
                econ['paid_stars_items'] = paid
                changed = True
            days = int(item.get('days', 0) or 0)
            if days == -1:
                if 'pass_forever' not in paid:
                    paid.append('pass_forever')
                    changed = True
                if not econ.get('vip_forever'):
                    econ['vip_forever'] = True
                    changed = True
            else:
                entitlement_until = float(entry.get('entitlement_until', 0) or 0)
                if entitlement_until > now and entitlement_until > float(econ.get('vip_until', 0) or 0):
                    econ['vip_until'] = entitlement_until
                    changed = True
        elif payload.startswith('bpprem_') or payload == 'cosm_bp_premium':
            paid = econ.setdefault('paid_stars_items', [])
            if not isinstance(paid, list):
                paid = []
                econ['paid_stars_items'] = paid
                changed = True
            if 'bp_premium' not in paid:
                paid.append('bp_premium')
                changed = True
            if not econ.get('bp_premium'):
                econ['bp_premium'] = True
                changed = True
    if changed:
        mark_dirty()
    return changed

def change_karma(user_id, user_tag, amount, username=None):
    with db_lock:
        econ = _get_user_econ_unlocked(user_id, user_tag, username=username)
        econ['karma'] = max(-100, min(100, econ.get('karma', 0) + amount))
        value = econ['karma']
        mark_dirty()
    return value

def add_account_exp(user_id, user_tag, exp_amount=1, username=None):
    # Season rollover may award coins, so it must run before taking db_lock.
    if 'season_rollover' in globals():
        season_rollover()
    with db_lock:
        econ = _get_user_econ_unlocked(user_id, user_tag, username)
        active_t = econ.get('active_title')
        bonus = 1.0
        if active_t and active_t in TITLES and TITLES[active_t].get('buff') == 'exp_bonus':
            bonus += (TITLES[active_t]['val'] / 100.0)
        # Улучшенный VIP: +25% к получаемому опыту профиля.
        if is_vip_active(econ):
            bonus += 0.25

        gained_exp = int(exp_amount * bonus)
        econ['account_exp'] = econ.get('account_exp', 0) + gained_exp
        # Сезонный рейтинг растёт вместе с обычной активностью, но не превращается в огромный счёт.
        econ['season_points'] = int(econ.get('season_points', 0) or 0) + max(1, gained_exp // 5)
        mark_dirty()
def add_message_stat(user_id, user_tag, username=None, chat_id=None):
    # Статистика профиля должна изменяться атомарно и попадать в autosave.
    with db_lock:
        econ = _get_user_econ_unlocked(user_id, user_tag, username)
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

        m_stats['day_count'] = int(m_stats.get('day_count', 0) or 0) + 1
        m_stats['week_count'] = int(m_stats.get('week_count', 0) or 0) + 1
        m_stats['month_count'] = int(m_stats.get('month_count', 0) or 0) + 1
        m_stats['total_count'] = int(m_stats.get('total_count', 0) or 0) + 1
        if chat_id is not None and int(chat_id) < 0:
            # Keep full day/week/month/all-time counters per group. Older
            # versions stored a plain integer here; it is migrated on read.
            chat_stats = econ.setdefault('msg_stats_chats', {})
            ckey = str(int(chat_id))
            current = chat_stats.get(ckey, 0)
            if not isinstance(current, dict):
                current = {
                    'day_date': today_str, 'week_key': week_str, 'month_key': month_str,
                    'day_count': 0, 'week_count': 0, 'month_count': 0,
                    'total_count': int(current or 0),
                }
                chat_stats[ckey] = current
            if current.get('day_date') != today_str:
                current['day_date'] = today_str; current['day_count'] = 0
            if current.get('week_key') != week_str:
                current['week_key'] = week_str; current['week_count'] = 0
            if current.get('month_key') != month_str:
                current['month_key'] = month_str; current['month_count'] = 0
            current['day_count'] = int(current.get('day_count', 0) or 0) + 1
            current['week_count'] = int(current.get('week_count', 0) or 0) + 1
            current['month_count'] = int(current.get('month_count', 0) or 0) + 1
            current['total_count'] = int(current.get('total_count', 0) or 0) + 1
        mark_dirty()


def _adjust_balance(econ, amount):
    """Change an already-resolved account balance under the DB lock."""
    with BALANCE_TX_LOCK:
        with db_lock:
            current = int(econ.get('balance', 0) or 0)
            new_balance = current + int(amount or 0)
            econ['balance'] = new_balance
            mark_dirty()
            return new_balance


def _set_balance(econ, value):
    """Set an already-resolved account balance under the DB lock."""
    with BALANCE_TX_LOCK:
        with db_lock:
            new_balance = int(value or 0)
            econ['balance'] = new_balance
            mark_dirty()
            return new_balance

def debit_coins(user_id, user_tag=None, amount=0, username=None):
    """Atomically debit coins if the account has enough money.

    The balance check and the subtraction happen under the same per-user and
    monetary transaction locks, so rapid duplicate commands cannot overspend.
    Returns (econ, new_balance) on success, or (None, current_balance) when
    there are insufficient funds.
    """
    try:
        uid = int(user_id)
        amount = int(amount)
    except (TypeError, ValueError):
        return None, 0
    if uid <= 0 or amount <= 0:
        return None, 0
    with _get_user_action_lock(uid):
        with BALANCE_TX_LOCK:
            with db_lock:
                econ = _get_user_econ_unlocked(uid, user_tag, username)
                current = int(econ.get('balance', 0) or 0)
                if current < amount:
                    return None, current
                new_balance = current - amount
                econ['balance'] = new_balance
                mark_dirty()
                return econ, new_balance

def transfer_coins(from_user_id, from_tag, to_user_id, to_tag, amount,
                   from_username=None, to_username=None):
    """Atomically move coins between two users without lost updates."""
    try:
        sender_id = int(from_user_id)
        receiver_id = int(to_user_id)
        amount = int(amount)
    except (TypeError, ValueError):
        return False, 0, 0
    if sender_id <= 0 or receiver_id <= 0 or sender_id == receiver_id or amount <= 0:
        return False, 0, 0

    with serialized_multi_user_action(sender_id, receiver_id):
        with BALANCE_TX_LOCK:
            with db_lock:
                sender = _get_user_econ_unlocked(sender_id, from_tag, from_username)
                receiver = _get_user_econ_unlocked(receiver_id, to_tag, to_username)
                sender_balance = int(sender.get('balance', 0) or 0)
                receiver_balance = int(receiver.get('balance', 0) or 0)
                if sender_balance < amount:
                    return False, sender_balance, receiver_balance
                sender['balance'] = sender_balance - amount
                receiver['balance'] = receiver_balance + amount
                mark_dirty()
                return True, sender['balance'], receiver['balance']

def record_started_user(user_id, username=None, display_name=None):
    """Remember that the user has actually interacted with the bot."""
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return
    if uid <= 0:
        return
    with db_lock:
        started = db.setdefault('started_users', {})
        item = started.setdefault(str(uid), {})
        changed = False
        if username:
            uname = clean_tag(str(username)).lower()
            if item.get('username') != uname:
                item['username'] = uname
                changed = True
        if display_name:
            name = clean_tag(str(display_name))
            if item.get('display_name') != name:
                item['display_name'] = name
                changed = True
        if item.get('started') is not True:
            item['started'] = True
            changed = True
        item['last_seen'] = time.time()
        if changed:
            mark_dirty()


def add_coins(user_id=None, user_tag=None, amount=0, username=None):
    try:
        lock_uid = int(user_id or 0)
    except (TypeError, ValueError):
        lock_uid = 0

    # Важно: не держим db_lock перед _adjust_balance().
    # _adjust_balance() использует порядок BALANCE_TX_LOCK -> db_lock;
    # прежний код держал db_lock -> BALANCE_TX_LOCK и мог намертво зациклиться
    # при одновременной выплате/списании в другом потоке.
    if lock_uid:
        with _get_user_action_lock(lock_uid):
            user_data = get_user_econ(lock_uid, user_tag, username=username)
            new_balance = _adjust_balance(user_data, amount)
    else:
        user_data = get_user_econ(user_id, user_tag, username=username)
        new_balance = _adjust_balance(user_data, amount)

    check_achievements(user_id, user_tag, 'balance_check', 0, username=username)
    return new_balance

# Economy service takeover for helpers whose legacy behavior is equivalent.
def get_global_user_key(user_id=None, user_tag=None):
    return economy_service.get_global_user_key(user_id=user_id, user_tag=user_tag, clean_tag=clean_tag)

users_service.configure(
    get_user_econ=get_user_econ,
    get_global_user_key=get_global_user_key,
    merge_user_econ_data=merge_user_econ_data,
    clean_tag=clean_tag,
)

def get_account_level(exp):
    return economy_service.get_account_level(exp)

def account_exp_for_level(level):
    return economy_service.account_exp_for_level(level)

def is_vip_active(econ):
    return economy_service.is_vip_active(econ)

def get_donor_title_buffs(econ):
    return economy_service.get_donor_title_buffs(econ)

def get_title_work_bonus(econ):
    return economy_service.get_title_work_bonus(econ)

def get_title_bonus_multiplier(econ):
    return economy_service.get_title_bonus_multiplier(econ)

def get_title_business_bonus(econ):
    return economy_service.get_title_business_bonus(econ)

def get_vip_work_bonus(econ):
    return economy_service.get_vip_work_bonus(econ)

def get_vip_business_bonus(econ):
    return economy_service.get_vip_business_bonus(econ)

def get_user_cd_reduction(econ):
    return economy_service.get_user_cd_reduction(econ)

def cooldown_text(last_time, cooldown, user_econ=None):
    return economy_service.cooldown_text(last_time, cooldown, user_econ)

def update_pet_stats(pet):
    return economy_service.update_pet_stats(pet)

def update_bank_interest(econ):
    return economy_service.update_bank_interest(econ)

def change_karma(user_id, user_tag, amount, username=None):
    return economy_service.change_karma(user_id, user_tag, amount, username=username)

def add_account_exp(user_id, user_tag, exp_amount=1, username=None):
    economy_service.add_account_exp(user_id, user_tag, exp_amount, username=username)
    return None

def check_casino_limits(econ, bet, is_multiplayer=False):
    return True


def get_chat_safe(chat_id):
    """Return a safe state isolated per chat and initialize/migrate it atomically."""
    changed = False
    with SAFE_LOCK:
        safe_root = db.setdefault('safe', {})
        # Backward compatibility: migrate legacy global safe into the current chat once.
        if 'code' in safe_root or 'pot' in safe_root or 'tried_codes' in safe_root:
            legacy = safe_root.copy()
            db['safe'] = {}
            if chat_id is not None:
                db['safe'][str(chat_id)] = legacy
            safe_root = db['safe']
            changed = True
        key = str(chat_id)
        if key not in safe_root:
            safe_root[key] = {
                'code': f"{random.randint(0, 9999):04d}",
                'pot': 30000,
                'tried_codes': []
            }
            changed = True
        safe = safe_root[key]
        if not isinstance(safe, dict):
            safe = {'code': f"{random.randint(0, 9999):04d}", 'pot': 30000, 'tried_codes': []}
            safe_root[key] = safe
            changed = True
        if 'code' not in safe:
            safe['code'] = f"{random.randint(0, 9999):04d}"
            changed = True
        if 'pot' not in safe:
            safe['pot'] = 30000
            changed = True
        if not isinstance(safe.get('tried_codes'), list):
            safe['tried_codes'] = []
            changed = True
    if changed:
        mark_dirty()
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

def atomic_safe_attempt(chat_id, econ, code_entered, user_id, user_name, username, now_ts):
    """Atomically consume a safe attempt and resolve win/miss for the shared chat safe."""
    with SAFE_LOCK:
        safe = get_chat_safe(chat_id)
        pot = int(safe.get('pot', 30000) or 0)
        tried = safe.setdefault('tried_codes', [])
        left = cooldown_text(econ.get('last_safe_try', 0), 1200, econ)
        if left:
            return ('cooldown', left, pot)
        if code_entered in tried:
            return ('duplicate', None, pot)
        econ['last_safe_try'] = now_ts
        if code_entered == safe.get('code'):
            won_pot = pot
            _adjust_balance(econ, won_pot)
            add_account_exp(user_id, user_name, 200, username=username)
            change_karma(user_id, user_name, 5)
            safe['code'] = f"{random.randint(0, 9999):04d}"
            safe['pot'] = 15000
            safe['tried_codes'] = []
            mark_dirty()
            return ('win', won_pot, pot)
        tried.append(code_entered)
        add_account_exp(user_id, user_name, 5, username=username)
        mark_dirty()
        return ('miss', None, pot)


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
    bet = int(bet or 0)
    if bet <= 0:
        return
    with CASINO_LOCK:
        db['casino_pool'] = max(10000, db.get('casino_pool', 1000000) + bet)
        add_to_safe_pot(bet, chat_id=chat_id)
        mark_dirty()

def reverse_casino_bet(bet, chat_id=None):
    bet = int(bet or 0)
    if bet <= 0:
        return
    with CASINO_LOCK:
        pool = db.get('casino_pool', 1000000)
        db['casino_pool'] = max(10000, int(pool) - bet)
        if chat_id is not None:
            safe = get_chat_safe(chat_id)
            safe_add = max(1, int(bet * 0.5))
            safe['pot'] = max(0, int(safe.get('pot', 0) or 0) - safe_add)
        mark_dirty()

def process_casino_win(win):
    if win <= 0:
        return 0
    with CASINO_LOCK:
        pool = max(10000, db.get('casino_pool', 1000000))
        actual_win = max(1, min(int(win), pool))
        db['casino_pool'] = max(10000, pool - actual_win)
        mark_dirty()
        return actual_win



# Все slash-команды и русские алиасы для единого антифлуда.
REGISTERED_COMMAND_ALIASES = frozenset(['21', 'achievements', 'activity', 'backpack', 'bail', 'balance', 'ball', 'bank', 'basketball', 'battle_pass', 'biz', 'bj', 'blackjack', 'bowling', 'bp', 'brick', 'business', 'case', 'catch', 'chance', 'chest', 'chromosomes', 'collect', 'collection', 'cook', 'crash', 'crypto', 'csaper', 'daily_heroes', 'darts', 'dashboard', 'detector', 'dick', 'divorce', 'donate', 'durak', 'economystats', 'escape', 'fact_vd', 'family', 'fanfic', 'fap', 'fat', 'findgroup', 'foot', 'football', 'gamestats', 'garage', 'garden', 'gear', 'gift', 'gift_stars', 'give', 'give_gif', 'grant', 'groupinfo', 'groups', 'guild', 'help', 'history', 'home', 'house', 'info', 'inventory', 'iq', 'jail', 'jobs', 'loan', 'lottery', 'market', 'marry', 'meme', 'memes', 'menu', 'miner', 'mines', 'minesweeper', 'monopoly', 'pass', 'pet', 'pet_fight', 'petclothes', 'pharmacy', 'pmarket', 'portfolio', 'profile', 'profile_settings', 'promo', 'raid', 'repay', 'resources', 'rps', 'safe', 'salary', 'season', 'sell', 'set_profile', 'settings', 'sheriff', 'shop', 'stars', 'start', 'stats', 'status', 'story', 'stream', 'tasks', 'top', 'top_daily', 'top_weekly', 'train', 'trash', 'user', 'vd_fact', 'vip', 'walk', 'wheel', 'work', 'world', 'активность', 'аптека', 'ачивки', 'баланс', 'банк', 'баскетбол', 'бизнес', 'бизнесы', 'биржа', 'битвы_питомцев', 'блэкджек', 'бой_питомцев', 'больница', 'боулинг', 'брак', 'вакансии', 'выдать', 'выдать_gif', 'гараж', 'герои_дня', 'гильдия', 'группы', 'гулять', 'дартс', 'депозит', 'детектор', 'дом', 'донат', 'дроч', 'дурак', 'жилье', 'жильё', 'задания', 'залог', 'замер', 'зарплата', 'звезды', 'игрыстат', 'инв', 'инвентарь', 'инвентарь_баффов', 'инфогруппы', 'история', 'история_дня', 'карта', 'квесты', 'кейс', 'кирпич', 'клан', 'колесо', 'коллекция', 'кпз', 'краш', 'кредит', 'крипта', 'кулинария', 'лотерея', 'магазин', 'майнер', 'майнинг', 'мем', 'мемы', 'мины', 'мир', 'монополия', 'мусорка', 'найтигруппу', 'настройки', 'настройки_профиля', 'одежда_питомца', 'опыт', 'панель', 'пасс', 'пенальти',
 'пет', 'писюн', 'питомец', 'побег', 'погасить', 'подарить_звезды', 'подарок', 'подарок_звезды', 'подрочить', 'поймать', 'пользователь', 'помойка', 'портфель', 'правда', 'прибыль', 'приготовить', 'продать', 'промо', 'промокод', 'профиль', 'работа', 'развод', 'ракета', 'рейд', 'рейтинг_сезона', 'ресурсы', 'рулетка', 'рынок_игроков', 'рюкзак', 'сад', 'сапер', 'сапер_классик', 'сапёр_классик', 'сезон', 'сейф', 'семья', 'снасти', 'статистика', 'статус', 'стрим', 'сундук', 'топ', 'топ_день', 'топ_неделя', 'тюрьма', 'ударники', 'ферма', 'футбол', 'хеллоуин', 'хромосома', 'хромосомы', 'цуефа', 'чест', 'шанс', 'шар', 'шериф', 'экономика', 'юзер']) | frozenset({'custom_title', 'кастомный_титул', 'ban', 'bans', 'biometry', 'force_save', 'games', 'give_stars_all', 'kick', 'miniigry', 'minigames', 'mute', 'mutes', 'save_json', 'stars_all', 'unban', 'unmute', 'warn', 'warns', 'анмут', 'бан', 'баны', 'биометрия', 'варн', 'варны', 'выдать_все_звезды', 'замеры', 'игры', 'кик', 'мут', 'муты', 'налаштування_профілю', 'разбан', 'снятьмут', 'сохранить', 'сохранить_json'})



def is_registered_command_text(text):
    text = str(text or '').strip().lower()
    if not text:
        return False
    token = text.split()[0].split('@', 1)[0].lstrip('/')
    return token in REGISTERED_COMMAND_ALIASES

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

    try:
        track_bot_chat(message.chat, status='active', touch_activity=True)
    except Exception as e:
        print(f'[GROUP TRACK ERROR] {e}')

    user_id = message.from_user.id
    user_username = (message.from_user.username or '').lower()
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username or 'Пользователь'
    is_super_admin = (user_id == ADMIN_ID)
    text = str(getattr(message, 'text', '') or '').strip()

    # В режиме полной остановки единственным разрешённым пользовательским
    # сообщением остаётся команда запуска владельца. Все остальные действия,
    # включая кнопки/текстовые игровые команды, должны молчать.
    if not db.get('bot_active', True):
        return bool(is_super_admin and text.lower() in {
            '/start_bot', '/resume', 'включить бота', 'запустить бота'
        })

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

    # АНТИФЛУД КОМАНД: проверяем здесь, чтобы лимит работал и для
    # отдельных command-handler'ов, которые завершаются до общего обработчика.
    # Настройка действует только в конкретной группе/супергруппе.
    is_private_chat = getattr(message.chat, 'type', '') == 'private'
    if not is_private_chat and is_registered_command_text(text) and not is_super_admin:
        chat_settings = get_chat_settings(message.chat.id)
        is_owner = is_chat_owner(message.chat.id, user_id)
        is_admin_user = is_admin(message.chat.id, user_id)
        admins_allowed = chat_settings.get('flood_admins', False)
        # Владелец (creator) всегда освобождён от антифлуда.
        # Обычные админы попадают под антифлуд только если это включено в настройках.
        flood_applies = (not is_owner) and (not is_admin_user or admins_allowed)
        if flood_applies and chat_settings.get('flood_protection', False):
            flood_key = f"{message.chat.id}:{user_id}"
            now_ts = time.time()
            cmd_hist = [t for t in command_rate_history.get(flood_key, []) if now_ts - t < 3600]

            if len(cmd_hist) > 4:
                command_rate_history[flood_key] = cmd_hist
                remaining = max(1, int(3600 - (now_ts - cmd_hist[0])))
                mins = max(1, (remaining + 59) // 60)
                try:
                    u_link = make_link(message.chat.id, user_name, user_id, ping=True)
                    bot.send_message(
                        message.chat.id,
                        f"🛡 {u_link}, <b>антифлуд сработал.</b>\n"
                        f"Лимит — <b>5 команд в час</b>. Следующая команда будет доступна примерно через <b>{mins} мин.</b> 😾",
                        parse_mode='HTML'
                    )
                except Exception as e:
                    print(f"[FLOOD WARN ERROR] {e}")
                return False

            cmd_hist.append(now_ts)
            command_rate_history[flood_key] = cmd_hist
            count = len(cmd_hist)
            if count in (4, 5):
                try:
                    u_link = make_link(message.chat.id, user_name, user_id, ping=True)
                    if count == 4:
                        warn = f"⚠️ {u_link}, предупреждение антифлуда: использовано <b>4/5 команд</b> за последний час."
                    else:
                        warn = f"⚠️ {u_link}, использовано <b>5/5 команд</b>. Следующая команда будет заблокирована до окончания лимита."
                    bot.send_message(message.chat.id, warn, parse_mode='HTML')
                except Exception as e:
                    print(f"[FLOOD WARN ERROR] {e}")

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
    # Money rewards and achievement state are committed under the canonical
    # BALANCE_TX_LOCK -> db_lock order. This avoids the old db_lock -> balance
    # inversion that could deadlock simultaneous economy operations.
    unlocked_new = []
    with BALANCE_TX_LOCK:
        with db_lock:
            econ = _get_user_econ_unlocked(user_id, user_tag, username)
            stats = econ.setdefault('stats', {})
            unlocked = econ.setdefault('achievements', [])

            if stat_name == 'balance_check':
                stats['balance_check'] = econ.get('balance', 0)
            elif stat_name == 'bank_deposit':
                stats['bank_deposit'] = econ.get('bank_deposit', 0)
            elif stat_name == 'smeh_check':
                stats['smeh_check'] = econ.get('smeh', 0)
            else:
                stats[stat_name] = int(stats.get(stat_name, 0) or 0) + int(amount or 0)

            for ach_id, ach_info in ACHIEVEMENTS.items():
                if ach_id in unlocked:
                    continue
                req_stat = ach_info['stat']
                target_val = ach_info['target']
                current_val = stats.get(req_stat, 0)
                if current_val >= target_val:
                    unlocked.append(ach_id)
                    reward = int(ach_info.get('reward', 0) or 0)
                    econ['balance'] = int(econ.get('balance', 0) or 0) + reward
                    # Keep XP update in the same locked transaction. add_account_exp
                    # is safe here because it now acquires the same lock order and
                    # both are reentrant locks for this thread.
                    add_account_exp(user_id, user_tag, 50, username)
                    unlocked_new.append((ach_info['title'], ach_info['desc'], reward))

            mark_dirty()

    if unlocked_new and chat_id:
        u_link = make_link(chat_id, user_tag, user_id, ping=True)
        for title, desc, reward in unlocked_new:
            msg = (
                f"🏆 <b>НОВОЕ ДОСТИЖЕНИЕ РАЗБЛОКИРОВАНО!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 Игрок: {u_link}\n"
                f"🎖 <b>{title}</b>\n"
                f"📜 <i>{desc}</i>\n"
                f"💰 Награда: <b>+{reward} Ня-коинов 🪙</b> (+50 EXP)\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )
            try:
                bot.send_message(chat_id, msg, parse_mode='HTML')
            except Exception as exc:
                print(f"[ACHIEVEMENT SEND ERROR] {exc}")


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
        mark_dirty()
    return DAILY_TASKS[now_msk().weekday()], econ

def get_weekly_tasks(user_id=None, user_tag=None, username=None):
    econ = get_user_econ(user_id, user_tag, username)
    w_key = weekly_task_key()
    if econ.get('weekly_tasks_yearweek') != w_key:
        econ['weekly_tasks_yearweek'] = w_key
        econ['weekly_progress'] = {}
        econ['weekly_claimed'] = []
        mark_dirty()
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
            _adjust_balance(econ, reward)
            add_account_exp(user_id, user_tag, 25, username)
            completed.append((f"Ежедневное: {description}", reward))

    w_tasks, _ = get_weekly_tasks(user_id, user_tag, username)
    w_progress = econ.setdefault('weekly_progress', {})
    w_progress[task_key] = w_progress.get(task_key, 0) + amount

    for key, description, target, reward in w_tasks:
        if key not in econ.get('weekly_claimed', []) and w_progress.get(key, 0) >= target:
            econ.setdefault('weekly_claimed', []).append(key)
            _adjust_balance(econ, reward)
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
        "━━━━━━━━━━━━━━━━━━━━",
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
    lines.append("━━━━━━━━━━━━━━━━━━━━")

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
    if user_econ.get('active_limited_effect'):
        badge_str += f" [{user_econ['active_limited_effect']}]"

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

ADMIN_LEVEL_NAMES = {0: 'Участник', 1: 'Младший админ', 2: 'Админ', 3: 'Старший админ', 4: 'Владелец'}
DEFAULT_ADMIN_PERMISSIONS = {'warn': 1, 'mute': 2, 'kick': 2, 'ban': 3, 'settings': 2, 'admin_manage': 4}

def get_admin_level(chat_id, user_id):
    try:
        chat_id, user_id = int(chat_id), int(user_id)
    except (TypeError, ValueError):
        return 0
    if chat_id > 0:
        return 4 if user_id == ADMIN_ID else 0
    try:
        member = bot.get_chat_member(chat_id, user_id)
        if getattr(member, 'status', '') == 'creator':
            return 4
    except Exception:
        pass
    roles = db.setdefault('chat_admins', {}).setdefault(str(chat_id), {})
    try:
        stored = int(roles.get(str(user_id), 0) or 0)
    except (TypeError, ValueError):
        stored = 0
    # Existing Telegram admins are migrated as level 2 until explicitly changed.
    if stored <= 0:
        try:
            member = bot.get_chat_member(chat_id, user_id)
            if getattr(member, 'status', '') == 'administrator':
                roles[str(user_id)] = 2
                mark_dirty()
                return 2
        except Exception:
            pass
    return max(0, min(4, stored))

def get_admin_permission_level(chat_id, action):
    perms = db.setdefault('admin_permissions', {}).setdefault(str(chat_id), {})
    if action not in perms:
        perms[action] = DEFAULT_ADMIN_PERMISSIONS.get(action, 4)
    try:
        return max(1, min(4, int(perms[action])))
    except (TypeError, ValueError):
        return DEFAULT_ADMIN_PERMISSIONS.get(action, 4)

def can_admin_action(chat_id, user_id, action):
    if not get_chat_settings(chat_id).get('admin_functions_enabled', True):
        return False
    return get_admin_level(chat_id, user_id) >= get_admin_permission_level(chat_id, action)

def is_admin(chat_id, user_id):
    return get_admin_level(chat_id, user_id) >= 1

def is_chat_owner(chat_id, user_id):
    """True only for the Telegram owner/creator of this chat."""
    try:
        chat_id = int(chat_id)
        user_id = int(user_id)
    except (TypeError, ValueError):
        return False
    if chat_id > 0:
        return False
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status == 'creator'
    except Exception:
        return False


# ---------------------------------------------------------
# МОДЕРАЦИЯ ГРУПП: WARN / MUTE / BAN / KICK
# ---------------------------------------------------------
MOD_DURATION_RE = re.compile(
    r'(\d+)\s*(?:секунд(?:а|ы)?|сек|с|минут(?:а|ы)?|мин|час(?:а|ов)?|ч|д(?:ень|ня|ней)?|сут(?:ки|ок)?|недел(?:я|и|ь)|н|месяц(?:а|ев)?|мес|год(?:а|ов)?|г|м)',
    re.IGNORECASE
)
MOD_ACTIONS = ('warn', 'mute', 'ban', 'kick')
MOD_LANGS = {'ru', 'uk', 'en'}

def _mod_chat(chat_id):
    key = str(chat_id)
    if key not in db.setdefault('moderation', {}) or not isinstance(db['moderation'][key], dict):
        db['moderation'][key] = {'users': {}}
        mark_dirty()
    db['moderation'][key].setdefault('users', {})
    return db['moderation'][key]

def _mod_user(chat_id, user_id):
    data = _mod_chat(chat_id)['users']
    key = str(user_id)
    if key not in data or not isinstance(data[key], dict):
        data[key] = {'warns': 0, 'warn_history': [], 'mute_until': None, 'ban_until': None, 'mute_active': False, 'ban_active': False}
        mark_dirty()
    data[key].setdefault('warns', 0)
    data[key].setdefault('warn_history', [])
    data[key].setdefault('mute_until', None)
    data[key].setdefault('ban_until', None)
    data[key].setdefault('mute_active', bool(data[key].get('mute_until')))
    data[key].setdefault('ban_active', bool(data[key].get('ban_until')))
    return data[key]

def _parse_mod_duration(raw):
    """Return seconds or None for permanent. Empty duration is permanent for ban/mute."""
    text = (raw or '').strip().lower()
    if not text or re.search(r'^(?:навсегда|бессрочно|без\s+срока|перманент(?:но)?|perm)$', text):
        return None
    m = MOD_DURATION_RE.search(text)
    if not m:
        return None
    value = int(m.group(1))
    unit = m.group(0).lower()
    if re.search(r'сек|с$', unit): mult = 1
    elif re.search(r'мин|м$', unit): mult = 60
    elif re.search(r'час|ч$', unit): mult = 3600
    elif re.search(r'д|сут', unit): mult = 86400
    elif re.search(r'нед|\bн$', unit): mult = 7 * 86400
    elif re.search(r'мес', unit): mult = 30 * 86400
    elif re.search(r'год|г$', unit): mult = 365 * 86400
    elif re.search(r'м$', unit): mult = 60
    else: return None
    return max(1, value * mult)

def _format_mod_until(until):
    if not until:
        return 'навсегда'
    left = max(0, int(float(until) - time.time()))
    d, rem = divmod(left, 86400); h, rem = divmod(rem, 3600); m, _ = divmod(rem, 60)
    if d: return f'{d} д.'
    if h: return f'{h} ч.'
    return f'{max(1,m)} мин.'

def _mod_target(message, raw_target=''):
    if getattr(message, 'reply_to_message', None):
        u = message.reply_to_message.from_user
        return int(u.id), (f'{u.first_name or ""} {u.last_name or ""}').strip() or u.username or f'ID:{u.id}'
    raw = (raw_target or '').strip()
    if not raw:
        return None, None
    m = re.search(r'(?:tg://(?:openmessage\?user_id=|user\?id=)|@)?(\d+)$', raw)
    if m and raw.replace('@','').isdigit():
        uid = int(m.group(1)); econ = get_user_econ(user_id=uid)
        return uid, econ.get('display_name', f'ID:{uid}')
    m = re.search(r'@([A-Za-z0-9_]{3,32})', raw)
    q = m.group(1) if m else raw.split()[0]
    uid, name = resolve_user_from_string(message.chat.id, q)
    if uid: return int(uid), name or q
    # If no DB match, Telegram cannot reliably resolve an arbitrary username to ID.
    return None, q

def _mod_parse(message, command):
    text = (message.text or '').strip()
    body = re.sub(r'^/?' + re.escape(command) + r'\s*', '', text, flags=re.IGNORECASE).strip()
    if message.reply_to_message:
        target_id, target_name = _mod_target(message)
        return target_id, target_name, body
    parts = body.split(None, 1)
    if not parts: return None, None, ''
    target_raw = parts[0]
    rest = parts[1] if len(parts) > 1 else ''
    target_id, target_name = _mod_target(message, target_raw)
    return target_id, target_name, rest

def _mod_is_group(message):
    return getattr(message.chat, 'type', '') in ('group', 'supergroup')

def _mod_can_act(message, target_id, action):
    if not _mod_is_group(message):
        return False, 'Эти команды работают только в группах.'
    if not can_admin_action(message.chat.id, message.from_user.id, action):
        return False, 'Недостаточно прав для этой команды или функции админов отключены.'
    if not target_id:
        return False, 'Не удалось определить пользователя. Ответь на его сообщение или укажи @username/ID.'

    actor_id = int(message.from_user.id)
    target_id = int(target_id)
    actor_level = get_admin_level(message.chat.id, actor_id)
    target_level = get_admin_level(message.chat.id, target_id)
    if target_level > 0 and target_level >= actor_level:
        return False, 'Нельзя модерировать администратора равного или более высокого уровня.'
    if target_id == actor_id:
        return False, 'Нельзя применить модерацию к себе.'

    try:
        target_member = bot.get_chat_member(message.chat.id, target_id)
        if target_member.status in ('creator', 'administrator'):
            return False, 'Нельзя модерировать владельца или администратора с такими правами.'
    except Exception:
        # High-impact moderation must fail closed. If Telegram cannot confirm
        # the target role, do not risk banning/muting an administrator.
        return False, 'Не удалось проверить права пользователя в Telegram. Повторите действие позже.'
    return True, ''

def _bot_can_restrict(chat_id):
    try:
        me = bot.get_me()
        member = bot.get_chat_member(chat_id, me.id)
        return member.status in ('administrator', 'creator') and bool(getattr(member, 'can_restrict_members', False) or member.status == 'creator')
    except Exception:
        return False

def _mod_restrict(chat_id, user_id, until=None):
    # Permanent mute: no until_date. Temporary mute: Telegram receives an absolute timestamp.
    from telebot.types import ChatPermissions
    perms = ChatPermissions(can_send_messages=False, can_send_audios=False, can_send_documents=False,
                            can_send_photos=False, can_send_videos=False, can_send_video_notes=False,
                            can_send_voice_notes=False, can_send_polls=False, can_send_other_messages=False,
                            can_add_web_page_previews=False)
    kwargs = {'chat_id': chat_id, 'user_id': user_id, 'permissions': perms, 'use_independent_chat_permissions': True}
    if until: kwargs['until_date'] = int(until)
    bot.restrict_chat_member(**kwargs)

def _mod_unmute(chat_id, user_id):
    from telebot.types import ChatPermissions
    perms = ChatPermissions(can_send_messages=True, can_send_audios=True, can_send_documents=True,
                            can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                            can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
                            can_add_web_page_previews=True)
    bot.restrict_chat_member(chat_id, user_id, permissions=perms, use_independent_chat_permissions=True)

def _mod_ban(chat_id, user_id, until=None):
    kwargs = {'chat_id': chat_id, 'user_id': user_id, 'revoke_messages': False}
    if until: kwargs['until_date'] = int(until)
    bot.ban_chat_member(**kwargs)

def _mod_unban(chat_id, user_id):
    bot.unban_chat_member(chat_id, user_id, only_if_banned=True)

def _clear_moderation(message, action):
    if not _mod_is_group(message):
        bot.reply_to(message,'❌ Эта команда работает только в группе.'); return
    if not can_admin_action(message.chat.id,message.from_user.id, 'mute' if action=='unmute' else 'ban'):
        bot.reply_to(message,'❌ Недостаточно прав или функции админов отключены.'); return
    target_id,target_name,args=_mod_parse(message,action)
    if not target_id:
        bot.reply_to(message,'❌ Укажи пользователя или ответь на его сообщение.'); return
    rec=_mod_user(message.chat.id,target_id); rec['name']=target_name
    try:
        if action=='unmute':
            _mod_unmute(message.chat.id,target_id); rec['mute_until']=None; rec['mute_active']=False
            bot.reply_to(message,f'🔊 {make_link(message.chat.id,target_name,target_id,ping=True)} снова может писать.',parse_mode='HTML')
        else:
            _mod_unban(message.chat.id,target_id); rec['ban_until']=None; rec['ban_active']=False
            bot.reply_to(message,f'🔓 {make_link(message.chat.id,target_name,target_id,ping=True)} разблокирован.',parse_mode='HTML')
        mark_dirty()
    except Exception as exc:
        bot.reply_to(message,f'❌ Не удалось снять ограничение: <code>{html.escape(str(exc))}</code>',parse_mode='HTML')

def _mod_list(message, kind):
    if not _mod_is_group(message):
        bot.reply_to(message, 'Списки модерации доступны только в группах.')
        return
    if not can_admin_action(message.chat.id, message.from_user.id, kind):
        bot.reply_to(message, '❌ Недостаточно прав или функции админов отключены.')
        return
    users = _mod_chat(message.chat.id)['users']
    now = time.time(); lines=[]
    for uid, info in users.items():
        if kind == 'warn' and int(info.get('warns',0)) > 0:
            lines.append(f'• {make_link(message.chat.id, info.get("name", f"ID:{uid}"), int(uid), ping=False)} — {info["warns"]} варн(ов)')
        elif kind == 'mute' and info.get('mute_active'):
            lines.append(f'• {make_link(message.chat.id, info.get("name", f"ID:{uid}"), int(uid), ping=False)} — {_format_mod_until(info["mute_until"])}')
        elif kind == 'ban' and info.get('ban_active'):
            lines.append(f'• {make_link(message.chat.id, info.get("name", f"ID:{uid}"), int(uid), ping=False)} — {_format_mod_until(info["ban_until"])}')
    title = {'warn':'⚠️ ВАРНЫ','mute':'🔇 МУТЫ','ban':'🔨 БАНЫ'}[kind]
    bot.reply_to(message, f'{title}\n━━━━━━━━━━━━━━━━━━━━\n' + ('\n'.join(lines) if lines else 'Список пуст.') + f'\n\nЛимит варнов: {get_chat_settings(message.chat.id).get("warn_limit",3)}', parse_mode='HTML')

def _execute_moderation(message, action):
    if not _mod_is_group(message):
        bot.reply_to(message, '❌ Эта команда работает только в группе.')
        return
    target_id, target_name, args = _mod_parse(message, action)
    ok, err = _mod_can_act(message, target_id, action)
    if not ok:
        bot.reply_to(message, '❌ ' + err)
        return
    args = args.strip()
    duration = None; reason = 'Не указана'
    if action == 'warn':
        reason = args or reason
    elif action == 'kick':
        reason = args or reason
    else:
        dm = re.match(r'^(?P<dur>\d+\s*(?:сек|с|мин|м|час|ч|д|дн(?:я|ей)?|н|нед(?:еля|ели)?|мес(?:яц|яца|яцев)?|г|год(?:а|ов)?)|навсегда|бессрочно|без\s+срока)\b(?:\s+|$)(?P<reason>.*)$', args, re.IGNORECASE)
        if dm:
            duration = _parse_mod_duration(dm.group('dur'))
            reason = dm.group('reason').strip() or reason
        elif args:
            # No duration => permanent for ban/mute.
            duration = None; reason = args
    now = time.time()
    until = now + duration if duration else None
    rec = _mod_user(message.chat.id, target_id)
    rec['name'] = target_name
    try:
        if action == 'warn':
            rec['warns'] = int(rec.get('warns',0)) + 1
            rec['warn_history'].append({'time': now, 'reason': reason, 'by': message.from_user.id})
            limit = max(1, int(get_chat_settings(message.chat.id).get('warn_limit',3) or 3))
            mark_dirty()
            if rec['warns'] >= limit:
                _mod_ban(message.chat.id, target_id, None)
                rec['ban_until'] = None
                rec['ban_active'] = True
                rec['warns'] = 0
                rec['warn_history'].append({'time': now, 'reason': f'Лимит варнов {limit}', 'by': message.from_user.id, 'auto_ban': True})
                mark_dirty()
                bot.reply_to(message, f'🔨 {make_link(message.chat.id,target_name,target_id,ping=True)} получил последний варн и автоматически заблокирован: лимит {limit}/{limit}.', parse_mode='HTML')
            else:
                bot.reply_to(message, f'⚠️ {make_link(message.chat.id,target_name,target_id,ping=True)} получил варн {rec["warns"]}/{limit}.\nПричина: {html.escape(reason)}', parse_mode='HTML')
        elif action == 'mute':
            _mod_restrict(message.chat.id, target_id, until)
            rec['mute_until'] = until
            rec['mute_active'] = True
            mark_dirty()
            bot.reply_to(message, f'🔇 {make_link(message.chat.id,target_name,target_id,ping=True)} получил мут: {_format_mod_until(until)}.\nПричина: {html.escape(reason)}', parse_mode='HTML')
        elif action == 'ban':
            _mod_ban(message.chat.id, target_id, until)
            rec['ban_until'] = until
            rec['ban_active'] = True
            mark_dirty()
            bot.reply_to(message, f'🔨 {make_link(message.chat.id,target_name,target_id,ping=True)} заблокирован: {_format_mod_until(until)}.\nПричина: {html.escape(reason)}', parse_mode='HTML')
        elif action == 'kick':
            _mod_ban(message.chat.id, target_id, None)
            _mod_unban(message.chat.id, target_id)
            bot.reply_to(message, f'👢 {make_link(message.chat.id,target_name,target_id,ping=True)} исключён из группы.\nПричина: {html.escape(reason)}', parse_mode='HTML')
    except Exception as exc:
        bot.reply_to(message, f'❌ Не удалось выполнить действие: <code>{html.escape(str(exc))}</code>', parse_mode='HTML')

def _moderation_worker():
    while True:
        time.sleep(10)
        if not db.get('bot_active', True):
            continue
        now = time.time()
        try:
            for chat_id, data in list(db.get('moderation', {}).items()):
                try: cid = int(chat_id)
                except Exception: continue
                users = data.get('users', {}) if isinstance(data, dict) else {}
                for uid, rec in list(users.items()):
                    try: user_id = int(uid)
                    except Exception: continue
                    changed = False
                    if rec.get('mute_until') and rec['mute_until'] <= now:
                        try:
                            _mod_unmute(cid, user_id)
                        except Exception as exc:
                            print(f'[MOD WORKER] unmute failed chat={cid} user={user_id}: {exc}')
                        else:
                            rec['mute_until'] = None
                            rec['mute_active'] = False
                            changed = True
                    if rec.get('ban_until') and rec['ban_until'] <= now:
                        try:
                            _mod_unban(cid, user_id)
                        except Exception as exc:
                            print(f'[MOD WORKER] unban failed chat={cid} user={user_id}: {exc}')
                        else:
                            rec['ban_until'] = None
                            rec['ban_active'] = False
                            changed = True
                    if changed: mark_dirty()
        except Exception as exc:
            print(f'[MOD WORKER ERROR] {exc}')


def start_moderation_worker():
    t = threading.Thread(target=_moderation_worker, daemon=True, name='moderation-expiry')
    t.start()

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
        display_matches = []
        for k, v in list(db['economy'].items()):
            if not isinstance(v, dict):
                continue
            disp = str(v.get('display_name', '') or '').lower()
            if disp == clean_q or clean_tag(disp).lower() == clean_q:
                display_matches.append((v.get('user_id'), v.get('display_name')))
        if len(display_matches) == 1:
            return display_matches[0]
        if len(display_matches) > 1:
            # Ambiguous display names are unsafe for destructive/admin actions.
            return None, query.replace('@', '').strip()

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
            if diff <= 0 and match_date.group(3):
                return -1
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
        if not db.get('bot_active', True):
            continue
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
    clean_user = clean_tag(user_name)
    seconds = parse_duration_to_seconds(duration_text, chat_id)
    if seconds == -1:
        return False, None
    if str_chat not in db['rests']:
        db['rests'][str_chat] = {}
    is_indefinite = any(marker in duration_text.lower() for marker in ('на неопределённый срок', 'бессрочно', 'навсегда'))
    end_time = (time.time() + seconds) if seconds is not None else None
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
        # Рест больше не начисляет коины. Старый бонус +150 удалён.
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
        if not db.get('bot_active', True):
            continue
        now = time.time()
        try:
            # Авто-удаление лобби и просроченных игр выполняется под общим callback lock,
            # чтобы таймер не мог одновременно удалить/вернуть ту же игру, что и callback.
            expired_refunds = []
            expired_deletes = []
            with CALLBACK_STATE_LOCK:
                # Сначала только фиксируем, какие игры истекли, и удаляем их из
                # общего состояния. Денежные возвраты выполняются после release
                # CALLBACK_STATE_LOCK, чтобы фоновый поток не создавал lock-cycle
                # с callback-ами пользователей.
                for d_k in list(active_durak.keys()):
                    d_game = active_durak[d_k]
                    if not d_game.get('started') and (now - d_game.get('start_time', now) > 600):
                        expired_deletes.append((d_game.get('chat_id'), d_game.get('msg_id')))
                        bet_lobby = int(d_game.get('bet', 0) or 0)
                        if bet_lobby > 0:
                            for pl in d_game.get('players', []):
                                if pl.get('id') and pl['id'] != 'bot':
                                    expired_refunds.append((int(pl['id']), pl.get('name'), bet_lobby, None))
                        del active_durak[d_k]

                for dict_ref in [active_crash, active_mines, active_bj_games, active_rps_games, active_brick, active_c_mines, active_durak]:
                    for k in list(dict_ref.keys()):
                        game_obj = dict_ref[k]
                        if now - game_obj.get('start_time', now) > 900:
                            bet_amt = int(game_obj.get('bet', 0) or 0)
                            if bet_amt > 0 and not game_obj.get('finished', False):
                                if dict_ref is active_rps_games:
                                    if game_obj.get('p1_id'): expired_refunds.append((int(game_obj['p1_id']), game_obj.get('p1_tag'), bet_amt, None))
                                    if game_obj.get('p2_id'): expired_refunds.append((int(game_obj['p2_id']), game_obj.get('p2_tag'), bet_amt, None))
                                elif dict_ref is active_durak:
                                    for pl in game_obj.get('players', []):
                                        if pl.get('id') and pl['id'] != 'bot':
                                            expired_refunds.append((int(pl['id']), pl.get('name'), bet_amt, None))
                                elif game_obj.get('user_id'):
                                    reverse_chat = game_obj.get('chat_id') if dict_ref is active_crash or dict_ref is active_mines or dict_ref is active_bj_games or dict_ref is active_brick else None
                                    expired_refunds.append((int(game_obj['user_id']), game_obj.get('user_name') or game_obj.get('user_tag'), bet_amt, reverse_chat))
                            del dict_ref[k]

            for uid, tag, amount, reverse_chat in expired_refunds:
                add_coins(uid, tag, amount)
                if reverse_chat is not None:
                    reverse_casino_bet(amount, chat_id=reverse_chat)
            for chat_id_lobby, msg_id_lobby in expired_deletes:
                if chat_id_lobby and msg_id_lobby:
                    try: bot.delete_message(chat_id_lobby, msg_id_lobby)
                    except Exception as e: print(f"[NONFATAL ERROR] {e}")

            for k in list(pending_marriages.keys()):
                if now - pending_marriages[k].get('start_time', now) > 900:
                    del pending_marriages[k]

            with CALLBACK_STATE_LOCK:
                for k in list(active_drops.keys()):
                    try:
                        drop_ts = int(str(k).split('_')[1])
                    except (IndexError, ValueError):
                        drop_ts = 0
                    if drop_ts and now - drop_ts > 1800:
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

            # Коллекторы по кредитам. Каждый счёт блокируется отдельно в
            # каноническом порядке: user-lock -> BALANCE_TX_LOCK -> db_lock.
            # Это не позволяет автосписанию затереть результат покупки/перевода.
            with db_lock:
                economy_items = list(db.get('economy', {}).items())
            for key, account_ref in economy_items:
                try:
                    account_user_id = int(account_ref.get('user_id', 0) or 0)
                except (TypeError, ValueError):
                    account_user_id = 0
                if account_user_id <= 0:
                    continue
                with _get_user_action_lock(account_user_id):
                    with BALANCE_TX_LOCK:
                        with db_lock:
                            econ = db.get('economy', {}).get(key)
                            if not isinstance(econ, dict):
                                continue
                            loan = econ.get('loan')
                            if not (loan and loan.get('amount', 0) > 0 and now > loan.get('due', 0) and not loan.get('defaulted')):
                                continue
                            amount = max(0, int(loan.get('amount', 0) or 0))
                            pocket = max(0, int(econ.get('balance', 0) or 0))
                            bank_dep = max(0, int(econ.get('bank_deposit', 0) or 0))
                            total_funds = pocket + bank_dep
                            if total_funds >= amount:
                                from_pocket = min(pocket, amount)
                                econ['balance'] = pocket - from_pocket
                                econ['bank_deposit'] = max(0, bank_dep - (amount - from_pocket))
                                econ['loan'] = {'amount': 0, 'due': 0, 'defaulted': False}
                            else:
                                econ['balance'] = 0
                                econ['bank_deposit'] = 0
                                econ['loan']['amount'] = max(0, amount - total_funds)
                                econ['loan']['defaulted'] = True
                                econ['karma'] = max(-100, int(econ.get('karma', 0) or 0) - 20)
                            mark_dirty()
        except Exception as e:
            print(f"[MEMORY WORKER ERROR] {e}")

def vd_facts_worker():
    while True:
        time.sleep(random.randint(7200, 14400))
        if not db.get('bot_active', True):
            continue
        try:
            if VD_CHAT_ID and not is_chat_banned(VD_CHAT_ID):
                title, desc = random.choice(VD_FACTS)
                msg_text = (
                    "🩸 <b>ИНТЕРЕСНЫЙ ФАКТ | VIOLENCE DISTRICT</b> 🔪\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 <b>{title}</b>\n"
                    f"📖 <i>{desc}</i>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "💡 <i>Хотите еще? Введите в чате:</i> <code>факт вд</code> 😺"
                )
                bot.send_message(VD_CHAT_ID, msg_text, parse_mode='HTML')
        except Exception:
            pass

def gold_rush_worker():
    global gold_rush_event
    while True:
        time.sleep(random.randint(14400, 28800))
        if not db.get('bot_active', True):
            continue
        try:
            gold_rush_event['active'] = True
            gold_rush_event['until'] = time.time() + 5400
            rush_msg = (
                "🌟🔥 <b>ВНИМАНИЕ! НАЧАЛАСЬ «ЗОЛОТАЯ ЛИХОРАДКА»!</b> 🔥🌟\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "⏳ <b>Длительность:</b> 1.5 часа (90 минут)!\n"
                "🎣 <b>Рыбалка и Охота:</b> Шанс редкой и легендарной добычи увеличен в <b>2 РАЗА</b>! 😻\n"
                "💰 <b>Скупщик:</b> Повышенные цены на продажу улова (<code>/sell</code>)!\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "<i>Хватайте снасти и отправляйтесь на /fish и /hunt прямо сейчас!</i> 😺"
            )
            active_chats = [cid for cid in list(db.get('settings', {}).keys()) if int(cid) < 0]
            for str_chat_id in active_chats:
                try:
                    bot.send_message(int(str_chat_id), rush_msg, parse_mode='HTML')
                    time.sleep(0.05)
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
            
            time.sleep(5400)
            if not db.get('bot_active', True):
                gold_rush_event['active'] = False
                continue
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
        if not db.get('bot_active', True):
            continue
        try:
            active_chats = [cid for cid in list(db.get('settings', {}).keys()) if int(cid) < 0]
            if not active_chats: continue
            target_chat = int(random.choice(active_chats))
            reward = random.randint(60, 250)
            drop_id = f"drop_{int(time.time())}_{random.randint(100, 999)}"
            with CALLBACK_STATE_LOCK:
                active_drops[drop_id] = {'chat_id': target_chat, 'reward': reward, 'claimed': False}
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🎁 Забрать подарок! 😻", callback_data=f"claim_{drop_id}"))
            msg_text = (
                "📦 <b>ВНЕЗАПНЫЙ ДРОП В ЧАТЕ!</b> 😺\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
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
        if not db.get('bot_active', True):
            continue
        try:
            with MARKET_LOCK:
                market = _get_market_data_locked()
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
            active_chats = [cid for cid in list(db.get('settings', {}).keys()) if int(cid) < 0]
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
        if not db.get('bot_active', True):
            continue
        try:
            active_chats = [cid for cid in list(db.get('settings', {}).keys()) if int(cid) < 0]
            if not active_chats: continue
            target_chat = int(random.choice(active_chats))
            q_data = random.choice(quiz_questions)
            with QUIZ_LOCK:
                current_quiz[target_chat] = {'question': q_data[0], 'answer': q_data[1].lower().strip(), 'reward': q_data[2], 'chat_id': target_chat}
            msg_text = (
                "⚡️ <b>ЭКСПРЕСС-ВИКТОРИНА В ЧАТЕ!</b> 😺\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"{q_data[0]}\n\n"
                f"💰 Награда первому верному ответу: <b>+{q_data[2]} Ня-коинов 🪙</b> 😻\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
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
        if not db.get('bot_active', True):
            continue
        try:
            now = time.time()
            active_chats = [int(cid) for cid in list(db.get('settings', {}).keys()) if int(cid) < 0]
            for cid in active_chats:
                last_act = last_chat_activity.get(cid, now)
                if now - last_act >= 18000:
                    last_chat_activity[cid] = now
                    bot.send_message(cid, random.choice(silence_prompts), parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")

BACKGROUND_THREADS_STARTED = False
BACKGROUND_THREADS_LOCK = threading.Lock()

_background_threads_started = False
_background_threads_start_lock = threading.Lock()

def start_background_threads():
    global _background_threads_started
    with _background_threads_start_lock:
        if _background_threads_started:
            return
        _background_threads_started = True
    global BACKGROUND_THREADS_STARTED
    with BACKGROUND_THREADS_LOCK:
        if BACKGROUND_THREADS_STARTED:
            return
        BACKGROUND_THREADS_STARTED = True
    leave_banned_chats()
    # Start moderation expiry only after the singleton guard has been acquired.
    start_moderation_worker()
    threading.Thread(target=vd_facts_worker, daemon=True).start()
    threading.Thread(target=gold_rush_worker, daemon=True).start()
    threading.Thread(target=random_chat_drops_worker, daemon=True).start()
    threading.Thread(target=market_news_worker, daemon=True).start()
    threading.Thread(target=chat_quiz_worker, daemon=True).start()
    threading.Thread(target=chat_silence_worker, daemon=True).start()
    threading.Thread(target=group_info_refresh_worker, daemon=True).start()
    saving_service.start_periodic_backup_worker(
        data_file=DATA_FILE,
        db_channel_id=DB_CHANNEL_ID,
        bot_instance=bot,
        interval=BACKUP_INTERVAL,
    )
    saving_service.start_autosave_worker(
        is_dirty=lambda: db_dirty,
        last_change_at=lambda: last_db_change_at,
        save_callback=save_data,
        debounce=AUTOSAVE_DEBOUNCE,
        interval=AUTOSAVE_INTERVAL,
    )
    threading.Thread(target=rest_manager_worker, daemon=True).start()
    threading.Thread(target=memory_and_debt_worker, daemon=True).start()

# ---------------------------------------------------------
# ПРИВЕТСТВИЕ И ПРОЩАНИЕ
# ---------------------------------------------------------


# ---------------------------------------------------------
# ГЛАВНОЕ МЕНЮ И СПРАВОЧНИК
# ---------------------------------------------------------


# ---------------------------------------------------------
# ОБРАБОТЧИК ФАКТОВ VIOLENCE DISTRICT
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# ПРОМОКОДЫ (/promo FIX)
# ---------------------------------------------------------

# ---------------------------------------------------------
# ИГРА КИРПИЧ (/brick)
# ---------------------------------------------------------
    # ---------------------------------------------------------
# ИГРА КРАШ (/crash)
# ---------------------------------------------------------
def crash_game_thread(game_id, chat_id, message_id, user_id, user_name, bet, crash_point):
    steps = [1.03, 1.08, 1.15, 1.25, 1.38, 1.55, 1.75, 2.00, 2.35, 2.80, 3.40, 4.20, 5.20, 6.50, 8.00, 10.00]

    for mult in steps:
        time.sleep(1.2)
        with CALLBACK_STATE_LOCK:
            game = active_crash.get(game_id)
            if not game or game.get('cashed_out') or game.get('exploded'):
                return
            if mult >= crash_point:
                game['exploded'] = True
                game['finished'] = True
                should_explode = True
            else:
                game['current_mult'] = mult
                should_explode = False

        if should_explode:
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
            with CALLBACK_STATE_LOCK:
                active_crash.pop(game_id, None)
            return

        cashout_amt = int(bet * mult)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(f"💰 Забрать куш ({cashout_amt} 🪙 | {mult:.2f}x) 😻", callback_data=f"crash_cashout_{game_id}:{user_id}"))

        bar_len = min(8, int(mult * 1.5))
        sky_bar = "☁️" * (8 - bar_len) + "🚀" + "🔥" * bar_len

        try:
            bot.edit_message_text(
                f"🚀 <b>ИГРА КРАШ (CRASH ROCKET)</b> 😺\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 Пилот: {make_link(chat_id, user_name, user_id, ping=False)}\n"
                f"💰 Ставка: <b>{bet} 🪙</b>\n"
                f"📈 Текущий множитель: <b>{mult:.2f}x</b>\n"
                f"🛰 Полет: [{sky_bar}]\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>Успейте зафиксировать выигрыш до взрыва ракеты!</i> 😸",
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=markup,
                parse_mode='HTML'
            )
        except Exception:
            pass


# ---------------------------------------------------------
# СИМУЛЯТОР СТРИМЕРА (/stream)
# ---------------------------------------------------------
def stream_thread(chat_id, user_id, user_name, genre, message_id):
    econ = get_user_econ(user_id, user_name)
    studio = econ.get('stream_studio', {'mic': 1, 'webcam': 1, 'light': 1})
    followers = int(econ.get('stream_followers', 0) or 0)
    stream_level, stream_title = get_stream_level(followers)
    fmt_key = str(econ.get('stream_format', 'обычный')).lower()
    fmt = STREAM_FORMATS.get(fmt_key, STREAM_FORMATS['обычный'])
    
    base_viewers = (studio.get('mic', 1) + studio.get('webcam', 1) + studio.get('light', 1)) * 40
    base_viewers += stream_level * 25 + int(followers ** 0.5) * 3
    viewers = max(1, int((base_viewers + random.randint(10, 80)) * fmt['mult']))
    
    text = (
        f"🔴 <b>СТРИМ ЗАПУЩЕН!</b> 😺\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
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

    # Дополнительные события расширенного стримерства
    if random.random() < 0.55:
        event2, event_mult, _ = random.choice(STREAM_EVENTS)
        event = event + "\n" + event2
        viewers = max(1, int(viewers * event_mult))
        
    text += f"\n\n⚡️ <b>Событие:</b> {event}\n<i>(👁 {viewers} зрителей)</i>"
    try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode='HTML')
    except Exception as e: print(f"[NONFATAL ERROR] {e}")
        
    time.sleep(3)
    
    donates = int(viewers * random.uniform(0.4, 1.2) * fmt['mult'])
    sponsor_bonus = 0
    if random.random() < (0.10 + stream_level * 0.02):
        sponsor_bonus = random.randint(100, 500) * max(1, stream_level)
        donates += sponsor_bonus
    new_followers = max(1, int(viewers * random.uniform(0.03, 0.10)))
    if 'Трэш-ток' in genre.title(): karma_diff = -2
    else: karma_diff = 1

    # This worker runs outside the message handler. Re-read the live account
    # under the per-user lock so concurrent /work, /bonus, /collect, etc. cannot
    # overwrite stream earnings/followers with a stale dictionary snapshot.
    with _get_user_action_lock(user_id):
        live_econ = get_user_econ(user_id, user_name)
        live_followers = int(live_econ.get('stream_followers', 0) or 0)
        live_streams = int(live_econ.get('stream_streams', 0) or 0) + 1
        live_viewers_total = int(live_econ.get('stream_viewers_total', 0) or 0) + viewers
        live_donates_total = int(live_econ.get('stream_donates_total', 0) or 0) + donates
        live_followers += new_followers
        live_econ['stream_followers'] = live_followers
        live_econ['stream_streams'] = live_streams
        live_econ['stream_viewers_total'] = live_viewers_total
        live_econ['stream_donates_total'] = live_donates_total
        _set_balance(live_econ, max(0, int(live_econ.get('balance', 0) or 0)) + max(0, donates))
        change_karma(user_id, user_name, karma_diff)
        mark_dirty()

    followers = live_followers
    stream_total = live_streams
    viewers_total = live_viewers_total

    k_sign = "+" if karma_diff > 0 else ""
    text += (
        f"\n\n🏁 <b>СТРИМ ЗАВЕРШЕН!</b> 😺\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💸 Заработано донатов: <b>+{donates} 🪙</b> 😻\n"
        f"👥 Новых подписчиков: <b>+{new_followers}</b> (всего {followers})\n"
        f"📺 Всего стримов: <b>{stream_total}</b> | 👁 Просмотров: <b>{viewers_total}</b>\n"
        f"🏅 Уровень: <b>{stream_title}</b>\n"
        f"⚖️ Влияние на Карму: <b>{k_sign}{karma_diff}</b> 😸"
    )
    try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode='HTML')
    except Exception as e: print(f"[NONFATAL ERROR] {e}")


# ---------------------------------------------------------
# ПУБЛИЧНЫЕ БИЗНЕСЫ КЛАНА
# ---------------------------------------------------------
def pet_bonus(econ, key):
    clothes = econ.get('pet_clothes', [])
    equipped = econ.get('equipped_pet_clothes')
    if equipped and equipped in clothes and equipped in PET_CLOTHES:
        return PET_CLOTHES[equipped].get(key, 0)
    return 0

def get_garden_capacity(econ):
    base = int(econ.get('garden_capacity', 1) or 1)
    return max(1, base + int(pet_bonus(econ, 'garden_bonus')))

def public_business_income(econ):
    pb = econ.get('public_business') or {}
    if not pb.get('name'):
        return 0
    base = int(pb.get('salary_per_worker', 100)) * len(econ.get('public_business_workers', []))
    return int(base * (1 + pet_bonus(econ, 'business_bonus')))

def render_public_business_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    pb = econ.get('public_business')
    if not pb:
        markup = InlineKeyboardMarkup(row_width=2)
        for b_id, b in BUSINESSES.items():
            price = max(3000, b['price'] * 2)
            markup.add(InlineKeyboardButton(f"🏢 {b['short']} — {price:,} 🪙", callback_data=f"pubbiz_create_{b_id}:{user_id}"))
        text = "🏢 <b>ПУБЛИЧНЫЕ БИЗНЕСЫ</b> 😺\n━━━━━━━━━━━━━━━━━━━━\nСоздайте предприятие, куда другие игроки смогут устроиться. Работникам зарплата доступна раз в 3 дня, а владелец получает прибыль с каждой выплаченной зарплаты.\n\n<b>Выберите тип бизнеса:</b>"
    else:
        workers = econ.get('public_business_workers', [])
        income = public_business_income(econ)
        text = (f"🏢 <b>{html.escape(pb.get('name','Бизнес'))}</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                f"👥 Работников: <b>{len(workers)}/5</b>\n💵 Зарплата: <b>{pb.get('salary_per_worker',100):,} 🪙 каждые 3 дня</b>\n"
                f"💰 Ваша прибыль с текущего состава: <b>~{income:,} 🪙</b> за выплату\n")
        if workers:
            text += "\n<b>Сотрудники:</b>\n" + "\n".join(f"• {html.escape(str(w.get('name','Игрок')))}" for w in workers)
        else:
            text += "\n<i>Пока никто не работает. Отправьте игрокам /бизнес и они смогут устроиться.</i>"
        markup = InlineKeyboardMarkup(row_width=2)
        if workers:
            markup.add(InlineKeyboardButton("💰 Выплатить зарплаты", callback_data=f"pubbiz_pay:{user_id}"))
        markup.add(InlineKeyboardButton("👥 Управление сотрудниками", callback_data=f"pubbiz_workers:{user_id}"))
        markup.add(InlineKeyboardButton("🔄 Сменить бизнес", callback_data=f"pubbiz_change:{user_id}"))
        markup.add(InlineKeyboardButton("🚪 Закрыть публичный бизнес", callback_data=f"pubbiz_quit:{user_id}"))
        markup.add(InlineKeyboardButton("📋 Обновить", callback_data=f"pubbiz_view:{user_id}"))
    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception as exc: print(f'[UI EDIT ERROR] public business view: {exc}')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

def render_public_jobs(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    rows=[]
    with db_lock:
        economy_snapshot = list(db.get('economy', {}).items())
    for key, e in economy_snapshot:
        pb=e.get('public_business')
        if pb and len(e.get('public_business_workers', [])) < 5 and e.get('user_id') != user_id:
            rows.append((e, key))
    markup=InlineKeyboardMarkup(row_width=1)
    lines=["💼 <b>ПУБЛИЧНЫЕ ВАКАНСИИ</b>","━━━━━━━━━━━━━━━━━━━━"]
    if not rows:
        lines.append("Пока нет свободных вакансий. 😿")
    for e,key in rows[:30]:
        pb=e['public_business']
        lines.append(f"🏢 <b>{html.escape(pb.get('name','Бизнес'))}</b> — {html.escape(e.get('display_name','Владелец'))}\n💵 Зарплата: {pb.get('salary_per_worker',100):,} 🪙 / 3 дня")
        markup.add(InlineKeyboardButton(f"Устроиться: {pb.get('name','Бизнес')[:30]}", callback_data=f"pubbiz_join_{e.get('user_id')}:{user_id}"))
    me=get_user_econ(user_id,user_name)
    if me.get('employer_salary'):
        markup.add(InlineKeyboardButton('🚪 Уволиться с текущей работы', callback_data=f'pubbiz_leave:{user_id}'))
    markup.add(InlineKeyboardButton("🔄 Обновить", callback_data=f"pubbiz_jobs:{user_id}"))
    text="\n".join(lines)
    if message_id:
        try: bot.edit_message_text(text,chat_id=chat_id,message_id=message_id,reply_markup=markup,parse_mode='HTML')
        except Exception as exc: print(f'[UI EDIT ERROR] public jobs view: {exc}')
    else: bot.send_message(chat_id,text,reply_markup=markup,parse_mode='HTML')



# ---------------------------------------------------------
# ПИТОМЕЦ: ОДЕЖДА И БАФФЫ
# ---------------------------------------------------------
def render_pet_clothes(chat_id,user_id,user_name,message_id=None):
    econ=get_user_econ(user_id,user_name)
    owned=econ.setdefault('pet_clothes',[])
    equipped=econ.get('equipped_pet_clothes')
    lines=["👗 <b>ГАРДЕРОБ ПИТОМЦА</b>","━━━━━━━━━━━━━━━━━━━━"]
    markup=InlineKeyboardMarkup(row_width=1)
    for k,v in PET_CLOTHES.items():
        if k in owned:
            state='✅ Надето' if equipped==k else '👕 Надеть'
            markup.add(InlineKeyboardButton(f"{state}: {v['name']}",callback_data=f"petcloth_equip_{k}:{user_id}"))
        else:
            markup.add(InlineKeyboardButton(f"Купить {v['name']} — {v['price']:,} 🪙",callback_data=f"petcloth_buy_{k}:{user_id}"))
        lines.append(f"• {v['name']} — {v['desc']}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"Надето: <b>{PET_CLOTHES[equipped]['name'] if equipped in PET_CLOTHES else 'ничего'}</b>")
    if message_id:
        try: bot.edit_message_text("\n".join(lines),chat_id=chat_id,message_id=message_id,reply_markup=markup,parse_mode='HTML')
        except Exception as exc: print('[UI EDIT ERROR] home installment:', exc)
    else: bot.send_message(chat_id,"\n".join(lines),reply_markup=markup,parse_mode='HTML')

# ---------------------------------------------------------
# ЛИЧНЫЕ ДОМА И РАССРОЧКА
# ---------------------------------------------------------
def render_personal_home(chat_id,user_id,user_name,message_id=None):
    econ=get_user_econ(user_id,user_name)
    home=econ.get('home')
    inst=econ.get('home_installment')
    markup=InlineKeyboardMarkup(row_width=1)
    lines=["🏠 <b>ЛИЧНЫЙ ДОМ</b>","━━━━━━━━━━━━━━━━━━━━"]
    if home:
        h=PERSONAL_HOUSES.get(home['id'],PERSONAL_HOUSES['room'])
        lines += [f"🏠 {h['name']}",f"📍 {h['city']}",f"💰 Пассивный бонус: +{h['income']} 🪙/ч"]
    elif inst:
        h=PERSONAL_HOUSES.get(inst['id'],PERSONAL_HOUSES['room'])
        lines += [f"🏗 <b>Дом в рассрочку: {h['name']}</b>",f"💳 Осталось: <b>{inst['remaining']:,} 🪙</b>",f"💵 Следующий платёж: <b>{inst['payment']:,} 🪙</b>",f"📅 Платёж раз в 2 дня"]
        markup.add(InlineKeyboardButton(f"💳 Внести платёж {inst['payment']:,} 🪙",callback_data=f"home_pay:{user_id}"))
    else:
        lines.append("Выберите дом. Первые 25% оплачиваются сразу, остальное — в рассрочку раз в 2 дня.")
        for k,h in PERSONAL_HOUSES.items():
            markup.add(InlineKeyboardButton(f"🏠 {h['name']} — {h['price']:,} 🪙",callback_data=f"home_buy_{k}:{user_id}"))
    if home: lines.append("\nДом уже полностью выплачен. 😻")
    lines.append("\n<i>Кредит /кредит можно использовать отдельно от рассрочки.</i>")
    if message_id:
        try: bot.edit_message_text("\n".join(lines),chat_id=chat_id,message_id=message_id,reply_markup=markup,parse_mode='HTML')
        except Exception: pass
    else: bot.send_message(chat_id,"\n".join(lines),reply_markup=markup,parse_mode='HTML')

# ---------------------------------------------------------
# МОНОПОЛИЯ
# ---------------------------------------------------------
def monopoly_text(game):
    lines=["🎩 <b>НЯ-МОНОПОЛИЯ</b>","━━━━━━━━━━━━━━━━━━━━"]
    for uid,p in game['players'].items():
        marker='👉' if uid==game['turn'] else '  '
        lines.append(f"{marker} {html.escape(p['name'])}: позиция {p['pos']}, {p['money']:,} 🪙")
    lines.append(f"\nХод: <b>{html.escape(game['players'][game['turn']]['name'])}</b>")
    lines.append("Клетки с 🏠 можно купить. Попав на чужую — платите аренду.")
    return "\n".join(lines)

def render_monopoly(chat_id,game,message_id=None):
    markup=InlineKeyboardMarkup(row_width=2)
    if game.get('started'):
        markup.add(InlineKeyboardButton("🎲 Бросить кубик",callback_data=f"mono_roll:{game['id']}"))
        markup.add(InlineKeyboardButton("🏠 Купить клетку",callback_data=f"mono_buy:{game['id']}"),InlineKeyboardButton("⏭ Пропустить",callback_data=f"mono_skip:{game['id']}"))
    else:
        markup.add(InlineKeyboardButton("➕ Присоединиться",callback_data=f"mono_join:{game['id']}"),InlineKeyboardButton("▶️ Начать",callback_data=f"mono_start:{game['id']}"))
    if message_id:
        try: bot.edit_message_text(monopoly_text(game),chat_id=chat_id,message_id=message_id,reply_markup=markup,parse_mode='HTML')
        except Exception: pass
    else: bot.send_message(chat_id,monopoly_text(game),reply_markup=markup,parse_mode='HTML')


# ---------------------------------------------------------
# САД БОНСАЙ (/garden)
# ---------------------------------------------------------
def render_garden_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    raw = econ.get('garden')
    if raw is None:
        slots = []
    elif isinstance(raw, list):
        slots = raw
    else:
        slots = [raw]
    if raw is not slots:
        econ['garden'] = slots
        mark_dirty()
    cap=get_garden_capacity(econ)
    lines=[f"🪴 <b>ОГОРОД БОНСАЙ</b> — {len(slots)}/{cap} грядок","━━━━━━━━━━━━━━━━━━━━"]
    markup=InlineKeyboardMarkup(row_width=2)
    now=time.time()
    for idx,garden in enumerate(slots):
        seed=GARDEN_SEEDS.get(garden.get('seed'))
        if not seed: continue
        elapsed=now-garden.get('planted_at',now)
        pct=min(100,int(elapsed/seed['grow_time']*100))
        ready=elapsed>=seed['grow_time'] and garden.get('water_count',0)>=seed['water_req']
        lines.append(f"{idx+1}. {seed['emoji']} <b>{seed['name']}</b> — {pct}% | 💦 {garden.get('water_count',0)}/{seed['water_req']}")
        if ready: markup.add(InlineKeyboardButton(f"🧺 Собрать #{idx+1}",callback_data=f"harvest_slot_{idx}:{user_id}"))
        else: markup.add(InlineKeyboardButton(f"💦 Полить #{idx+1} (-15 🪙)",callback_data=f"water_slot_{idx}:{user_id}"))
        fert = int(econ.get('backpack', {}).get('garden_fertilizer', 0) or 0)
        if fert > 0 and int(garden.get('fertilizer_used', 0) or 0) < 3:
            markup.add(InlineKeyboardButton(f"🧪 Удобрить #{idx+1} ({fert} шт.)",callback_data=f"fertilize_slot_{idx}:{user_id}"))
        markup.add(InlineKeyboardButton(f"❌ Выкорчевать #{idx+1}",callback_data=f"uproot_slot_{idx}:{user_id}"))
    if len(slots)<cap:
        markup.add(InlineKeyboardButton("🌱 Посадить растение",callback_data=f"garden_seeds:{user_id}"))
    lines.append(f"\n🐾 Бонус питомца: +{int(pet_bonus(econ,'garden_bonus'))} слот(ов)")
    if message_id:
        try: bot.edit_message_text("\n".join(lines),chat_id=chat_id,message_id=message_id,reply_markup=markup,parse_mode='HTML')
        except Exception: pass
    else: bot.send_message(chat_id,"\n".join(lines),reply_markup=markup,parse_mode='HTML')


# ---------------------------------------------------------
# КРЕДИТЫ (НЯ-БАНК)
# ---------------------------------------------------------


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

    with _get_user_action_lock(user_id):
        # Re-read the balance immediately before the external Telegram call.
        econ = get_user_econ(user_id, user_name, username=user_username)
        if int(econ.get('balance', 0) or 0) < bet:
            bot.reply_to(message, f"❌ Недостаточно средств! У вас: <b>{econ.get('balance', 0)} 🪙</b> 😿", parse_mode='HTML')
            return
        _adjust_balance(econ, -(bet))
        process_casino_bet(bet, chat_id)

    emoji_map = {'football': '⚽', 'basketball': '🏀', 'darts': '🎯', 'bowling': '🎳'}
    dice_emoji = emoji_map.get(game_type, '🎲')
    try:
        dice_msg = bot.send_dice(chat_id, emoji=dice_emoji)
        val = dice_msg.dice.value
    except Exception as e:
        # The stake was already reserved. Refund it if Telegram could not
        # create the dice message, otherwise a transient API error becomes a
        # permanent loss with no game/result.
        with _get_user_action_lock(user_id):
            live_econ = get_user_econ(user_id, user_name, username=user_username)
            _set_balance(live_econ, max(0, int(live_econ.get('balance', 0) or 0)) + bet)
            reverse_casino_bet(bet, chat_id)
            mark_dirty()
        print(f"[SPORT DICE SEND ERROR] {e}")
        try:
            bot.reply_to(message, '❌ Не удалось запустить бросок. Ставка возвращена. 😿', parse_mode='HTML')
        except Exception:
            pass
        return

    def resolve_dice_async():
        time.sleep(3.5)
        with _get_user_action_lock(user_id):
            try:
                # Refresh the live account after the 3.5s Telegram delay. The
                # original closure could overwrite newer balance changes made
                # while the dice message was in flight.
                econ = get_user_econ(user_id, user_name, username=user_username)
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
                        _adjust_balance(econ, win_amount)
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
                        _adjust_balance(econ, win_amount)
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
                        _adjust_balance(econ, win_amount)
                        econ['daily_casino_win'] = econ.get('daily_casino_win', 0) + (win_amount - bet)
                        econ['daily_casino_profit'] = econ.get('daily_casino_profit', 0) + (win_amount - bet)
                        result_text = f"🎯👑 <b>ПРЯМО В ЯБЛОЧКО (BULLSEYE)!</b> 🙀\n🎉 Куш: <b>+{win_amount} 🪙</b> (x{mult}){clover_str}!"
                    elif actual_val == 5:
                        mult = 1.25
                        win_amount = int(bet * mult)
                        win_amount = process_casino_win(win_amount)
                        _adjust_balance(econ, win_amount)
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
                        _adjust_balance(econ, win_amount)
                        econ['daily_casino_win'] = econ.get('daily_casino_win', 0) + (win_amount - bet)
                        econ['daily_casino_profit'] = econ.get('daily_casino_profit', 0) + (win_amount - bet)
                        result_text = f"🎳👑 <b>СТРАААЙК! ВСЕ КЕГЛИ РАЗБИТЫ!</b> 😹\n🎉 Точный бросок: <b>+{win_amount} 🪙</b> (x{mult}){clover_str}!"
                    elif actual_val in [4, 5]:
                        win_amount = int(bet * 0.85)
                        win_amount = process_casino_win(win_amount)
                        _adjust_balance(econ, win_amount)
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




# ---------------------------------------------------------
# УДАРНИКИ И ГЕРОИ ДНЯ
# ---------------------------------------------------------

# ---------------------------------------------------------
# РЮКЗАК И РАСХОДНИКИ
# ---------------------------------------------------------
def render_backpack_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    bp = econ.setdefault('backpack', {'energy_drink': 0, 'luck_clover': 0, 'alarm_system': 0, 'invis_mask': 0, 'garden_fertilizer': 0})

    markup = InlineKeyboardMarkup(row_width=1)
    energy = int(bp.get('energy_drink', 0) or 0)
    clover = int(bp.get('luck_clover', 0) or 0)
    invis = int(bp.get('invis_mask', 0) or 0)
    fert = int(bp.get('garden_fertilizer', 0) or 0)
    alarm = int(bp.get('alarm_system', 0) or 0)
    markup.add(InlineKeyboardButton(f"⚡️ Выпить Энергетик ({energy} шт.)" if energy > 0 else "⚡️ Энергетик — 0 шт. | 🛒 Купить", callback_data=f"use_item_energy_drink:{user_id}" if energy > 0 else f"shop_cat_buffs:{user_id}"))
    markup.add(InlineKeyboardButton(f"🍀 Активировать Клевер ({clover} шт.)" if clover > 0 else "🍀 Клевер — 0 шт. | 🛒 Купить", callback_data=f"use_item_luck_clover:{user_id}" if clover > 0 else f"shop_cat_buffs:{user_id}"))
    markup.add(InlineKeyboardButton(f"🥷 Надеть Невидимку ({invis} шт.)" if invis > 0 else "🥷 Невидимка — 0 шт. | 🛒 Купить", callback_data=f"use_item_invis_mask:{user_id}" if invis > 0 else f"shop_cat_buffs:{user_id}"))
    markup.add(InlineKeyboardButton(f"🧪 Удобрить Сад ({fert} шт.) | 🌱 Выбрать грядку" if fert > 0 else "🧪 Удобрение — 0 шт. | 🛒 Купить", callback_data=f"garden_view:{user_id}" if fert > 0 else f"shop_cat_buffs:{user_id}"))
    markup.add(InlineKeyboardButton(f"🛡️ Сигнализация ({alarm} шт.) — авто-защита", callback_data=f"backpack_alarm:{user_id}" if alarm > 0 else f"shop_cat_buffs:{user_id}"))
    markup.add(InlineKeyboardButton("📦 Рыба / Дичь / Крафт", callback_data=f"resources_main:{user_id}"))
    markup.add(InlineKeyboardButton("🏪 Купить расходники в Магазине", callback_data=f"shop_cat_buffs:{user_id}"))
    markup.add(InlineKeyboardButton("👤 Профиль", callback_data=f"profile_self:{user_id}"))

    clover_status = "✅ Активен" if econ.get('luck_clover_until', 0) > time.time() else "❌ Не активен"
    invis_status = "✅ Включена" if econ.get('invis_until', 0) > time.time() else "❌ Выключена"

    text = (
        f"🎒 <b>РЮКЗАК БАФФОВ И РАСХОДНИКОВ</b> 😺\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Владелец: {make_link(chat_id, user_name, user_id, ping=False)}\n\n"
        f"• ⚡️ Энергетик Red Cat: <b>{bp.get('energy_drink', 0)} шт.</b>\n"
        f"• 🍀 Клевер удачи: <b>{bp.get('luck_clover', 0)} шт.</b> (Статус: {clover_status})\n"
        f"• 🛡 Охранная сигнализация: <b>{bp.get('alarm_system', 0)} шт.</b> (Авто-защита)\n"
        f"• 🥷 Маска-невидимка: <b>{bp.get('invis_mask', 0)} шт.</b> (Статус: {invis_status})\n"
        f"• 🧪 Супер-Удобрение для сада: <b>{bp.get('garden_fertilizer', 0)} шт.</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>Нажмите кнопку под сообщением, чтобы использовать предмет!</i> 😸"
    )

    if message_id:
        try:
            bot.edit_message_text(
                text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=markup,
                parse_mode='HTML'
            )
            return
        except Exception as e:
            print(f"[NONFATAL ERROR] {e}")
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')


# ---------------------------------------------------------
# КОЛЕСО ФОРТУНЫ (/wheel)
# ---------------------------------------------------------

# ---------------------------------------------------------
# САПЁР / МИНЫ (/mines)
# ---------------------------------------------------------
def calculate_mines_multiplier(total_cells, mines_count, safe_opened, rtp=0.72):
    """Консервативный множитель для азартного Сапёра.

    Старая формула давала огромный экспоненциальный рост на редких минах
    (например, 6x6 + 4 мины), из-за чего поздние безопасные клетки были
    непропорционально выгодными. Теперь сохраняется принцип "больше мин =
    выше риск = выше потенциальный множитель", но итог ограничен плотностью мин.
    """
    try:
        total_cells = int(total_cells)
        mines_count = int(mines_count)
        safe_opened = int(safe_opened)
    except (TypeError, ValueError):
        return 1.05
    if total_cells <= 1 or mines_count <= 0 or mines_count >= total_cells:
        return 1.05
    safe_opened = max(0, min(safe_opened, total_cells - mines_count))

    prob = 1.0
    for i in range(safe_opened):
        numerator = total_cells - mines_count - i
        denominator = total_cells - i
        if denominator <= 0 or numerator <= 0:
            prob = 0.0
            break
        prob *= numerator / denominator

    if prob <= 0:
        raw_mult = float('inf')
    else:
        raw_mult = (1.0 / prob) * float(rtp)

    # Потолок зависит от плотности мин: редкие мины не дают "бесплатных"
    # x10-x100, а высокая плотность всё ещё заметно повышает риск/награду.
    density = mines_count / float(total_cells)
    density_cap = 1.50 + 4.50 * (density ** 0.70)
    density_cap = max(1.80, min(5.50, density_cap))
    mult = min(raw_mult, density_cap)
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
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Игрок: {game['user_tag']}\n"
        f"💰 Ставка: <b>{game['bet']} 🪙</b> | Мин на поле: <b>{len(game['bombs'])} шт.</b>\n"
        f"💎 Найдено кристаллов: <b>{len(game['revealed'])}/{max_safe}</b>\n"
        f"📈 Множитель: <b>{game['current_multiplier']:.2f}x</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Открывайте безопасные клетки или заберите куш!</i> 😸"
    )
    return text, markup


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
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Сапёр: {game['user_name']}\n"
        f"💣 Мин на поле: <b>{game['mines_count']} шт.</b> | Осталось: <b>{mines_left}</b>\n"
        f"🎯 Режим: <b>{'⛏ Открывать клетки' if mode == 'dig' else '🚩 Ставить / Убирать флаги'}</b>\n"
        f"🏆 Награда за разминирование: <b>+{game['reward']} 🪙</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Используйте логику! Первый ход всегда безопасен.</i> 😸"
    )
    return text, markup


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
        if not game.get('table'):
            return
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
                if game.get('table') and all(pair.get('defend') for pair in game['table']):
                    game['table'] = []
                    durak_deal_cards(game)
                    game['attacker_idx'] = game['defender_idx']
                    game['defender_idx'] = (game['defender_idx'] + 1) % len(game['players'])
                    game['status_text'] = "✅ Бито! Ход переходит дальше!"
                else:
                    game['status_text'] = "⏳ Бот ждёт, пока защищающийся отобьётся."

def sync_durak_pm(game_id):
    game = active_durak.get(game_id)
    if not game or not game.get('started'):
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

        role_str = "🏁 ИГРА ОКОНЧЕНА!" if game.get('finished') else ("⚔️ ВЫ АТАКУЕТЕ!" if is_attacker else "🛡 ВЫ ЗАЩИЩАЕТЕСЬ!" if is_defender else "⏳ Ожидайте своего хода")
        lines = [
            f"🃏 <b>ДУРАК (ВАШИ КАРТЫ В ЛС)</b> 😺",
            "━━━━━━━━━━━━━━━━━━━━",
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
        lines.append("━━━━━━━━━━━━━━━━━━━━\n<b>Ваша рука (нажмите для хода):</b>")

        markup = InlineKeyboardMarkup(row_width=3)
        if not game.get('finished'):
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

def refresh_durak_group_board(game_id):
    """Обновляет именно групповое сообщение Дурака, даже когда callback пришёл из ЛС."""
    game = active_durak.get(game_id)
    if not game:
        return
    group_chat_id = game.get('chat_id')
    group_msg_id = game.get('msg_id')
    if not group_chat_id or not group_msg_id:
        return
    text, markup = render_durak_board(game_id)
    try:
        bot.edit_message_text(
            text,
            chat_id=group_chat_id,
            message_id=group_msg_id,
            reply_markup=markup,
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"[NONFATAL ERROR] Не удалось обновить стол Дурака: {e}")

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
        "━━━━━━━━━━━━━━━━━━━━",
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
    lines.append("━━━━━━━━━━━━━━━━━━━━")

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

    # ---------------------------------------------------------
# МЕМНЫЕ СИМУЛЯТОРЫ: ПИСЮН И ФАП
# ---------------------------------------------------------


# ---------------------------------------------------------
# ГАРАЖ (РАСШИРЕННЫЙ КАТАЛОГ)
# ---------------------------------------------------------
def _vehicle_class_label(info):
    labels = {
        'economy': '🟢 ECONOMY',
        'sport': '🔵 SPORT',
        'luxury': '🟣 LUXURY',
        'hyper': '🟠 HYPER',
        'galactic': '🌌 GALACTIC',
    }
    return labels.get(str(info.get('class', '')).lower(), '🚗 CLASSIC')

def _vehicle_benefit_text(info):
    parts=[]
    if info.get('cd_cut'):
        parts.append(f"-{int(float(info.get('cd_cut',0))*100)}% таймеров")
    try:
        wb=float(info.get('work_bonus',0) or 0)
    except (TypeError, ValueError):
        wb=0.0
    if wb:
        parts.append(f"+{wb*100:.1f}% зарплаты")
    return ' · '.join(parts) or 'Без дополнительных бонусов'

def render_garage_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    equipped = econ.get('equipped_vehicle') or econ.get('vehicle')
    if equipped in DONOR_VEHICLES:
        cur_info = DONOR_VEHICLES[equipped]
    else:
        cur_info = VEHICLES.get(equipped)
    cur_name = cur_info['name'] if cur_info else "Пешеход 🚶‍♂️"
    cur_class = _vehicle_class_label(cur_info) if cur_info else '🚶 PEDESTRIAN'

    owned = list(dict.fromkeys(econ.get('vehicle_inventory', [])))
    lines = [
        "🏎 <b>ЛИЧНЫЙ АВТОГАРАЖ</b> 😺",
        "━━━━━━━━━━━━━━━━━━━━",
        f"👤 Владелец: {make_link(chat_id, user_name, user_id, ping=False)}",
        f"🚘 Надет сейчас: <b>{cur_name}</b>",
        f"🏷 Класс: <b>{cur_class}</b>",
        "",
        "<i>Купленные машины сохраняются навсегда. Надеть одновременно можно только одну.</i>",
        "",
        "<b>Мои машины:</b>"
    ]
    markup = InlineKeyboardMarkup(row_width=2)
    owned_btns=[]
    for vid in owned:
        info = DONOR_VEHICLES.get(vid) or VEHICLES.get(vid)
        if not info:
            continue
        status = " ✅ НАДЕТА" if vid == equipped else ""
        lines.append(f"• <b>{info['name']}</b>{status} — {html.escape(_vehicle_class_label(info))} — {html.escape(_vehicle_benefit_text(info))}")
        if vid != equipped:
            owned_btns.append(InlineKeyboardButton(f"Надеть {info['short']}", callback_data=f"equip_veh_{vid}:{user_id}"))
    if owned_btns:
        for i in range(0, len(owned_btns), 2):
            markup.add(*owned_btns[i:i+2])
    if not owned:
        lines.append("• Пока нет купленного транспорта.")

    lines += ["", "<b>Обычный каталог:</b>"]
    catalog_btns=[]
    for v_id, v_info in VEHICLES.items():
        if v_id in owned:
            continue
        lines.append(f"• <b>{v_info['name']}</b> — <code>{v_info['price']:,} 🪙</code> — {html.escape(_vehicle_class_label(v_info))} — {html.escape(_vehicle_benefit_text(v_info))}")
        catalog_btns.append(InlineKeyboardButton(f"Купить {v_info['short']} — {v_info['price']} 🪙", callback_data=f"buy_veh_{v_id}:{user_id}"))
    for i in range(0, len(catalog_btns), 2):
        markup.add(*catalog_btns[i:i+2])
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    text = "\n".join(lines)

    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            return
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
    try:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception as e: print(f"[NONFATAL ERROR] {e}")


# ---------------------------------------------------------
# КУЛИНАРИЯ (/cook)
# ---------------------------------------------------------

# ---------------------------------------------------------
# ПИТОМЕЦ (/pet)
# ---------------------------------------------------------
def activate_pet(econ, pet_id):
    info=PETS_DATA.get(pet_id)
    if not info: return False
    inv=econ.setdefault('pet_inventory', [])
    if pet_id not in inv: inv.append(pet_id)
    current=econ.get('pet') or {}
    if current.get('id')==pet_id: return True
    econ['pet']={'id':pet_id,'name':info['name'],'luck_bonus':info.get('luck_bonus',0),'hunger':100,'cleanliness':100,'pet_exp':int(current.get('pet_exp',0) or 0) if current.get('id')==pet_id else 0,'last_update':time.time()}
    mark_dirty(); return True

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
        InlineKeyboardButton("🐾 Зоомагазин", callback_data=f"shop_cat_pets_0:{user_id}"),
        InlineKeyboardButton("👗 Одежда", callback_data=f"pet_clothes:{user_id}")
    )

    text = (
        f"🐾 <b>КАРТОЧКА ПИТОМЦА: {pet['name']}</b> 😺\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Хозяин: {make_link(chat_id, user_name, user_id, ping=False)}\n"
        f"⭐ Опыт питомца: <b>{pet.get('pet_exp', 0)} EXP</b>\n"
        f"🍗 Сытость: <b>{pet.get('hunger', 100)}%</b> [{hunger_bar or '❌ Голоден'}]\n"
        f"🧼 Чистота: <b>{pet.get('cleanliness', 100)}%</b> [{clean_bar or '❌ Грязнуля'}]\n"
        f"✨ Бонус: <b>+{pet.get('luck_bonus', 10)}% к удаче</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>Используйте кнопки для ухода за питомцем!</i> 😸"
    )

    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return
    try: bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception as e: print(f"[NONFATAL ERROR] {e}")


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
        _adjust_balance(econ, ev_val)
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
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Во время прогулки питомец {ev_desc}!\n"
            f"{res_str}\n"
            f"⭐ Опыт питомца: <b>+25 EXP</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode='HTML'
        )
    except Exception:
        pass


# ---------------------------------------------------------
# МАГАЗИН СНАСТЕЙ (/gear)
# ---------------------------------------------------------

# ---------------------------------------------------------
# БИЗНЕСЫ 2.1 — АУДИТ: РАЗДЕЛЬНОЕ НАКОПЛЕНИЕ И ЕДИНЫЙ РАСЧЁТ
# ---------------------------------------------------------
def _migrate_legacy_businesses(econ):
    """Convert only legacy business IDs already present in the live Neon profile.

    This is deliberately lazy and idempotent: no JSON snapshot is consulted.
    If the replacement is already owned, the removed business is compensated at its
    legacy purchase price * 80% so no purchased asset simply vanishes.
    """
    if not isinstance(econ, dict):
        return False
    businesses = econ.setdefault('businesses', {})
    levels = econ.setdefault('biz_levels', {})
    prices = econ.setdefault('biz_purchase_price', {})
    legacy_assets = econ.setdefault('legacy_assets', [])
    tx = econ.setdefault('business_transactions', [])
    changed = False
    for old_id, new_id in LEGACY_BUSINESS_REPLACEMENTS.items():
        if old_id not in businesses:
            continue
        old_value = businesses.pop(old_id)
        old_level = max(1, min(5, int(levels.pop(old_id, 1) or 1)))
        old_price = int(prices.pop(old_id, LEGACY_BUSINESS_INFO[old_id]['price']) or LEGACY_BUSINESS_INFO[old_id]['price'])
        if new_id not in businesses:
            businesses[new_id] = old_value if old_value else time.time()
            levels[new_id] = old_level
            prices[new_id] = old_price
            legacy_assets.append({'type': 'business_conversion', 'from': old_id, 'to': new_id, 'old_price': old_price, 'time': time.time()})
            tx.append({'type':'migration','business':new_id,'from':old_id,'old_price':old_price,'time':time.time()})
        else:
            refund = int(old_price * BUSINESS_SELL_RATE)
            econ['balance'] = int(econ.get('balance', 0) or 0) + refund
            tx.append({'type':'migration_compensation','business':old_id,'refund':refund,'time':time.time()})
            changed = True
        changed = True
        clocks = econ.setdefault('biz_last_collect', {})
        carries = econ.setdefault('biz_income_carry', {})
        if old_id in clocks:
            clocks[new_id] = clocks.pop(old_id)
        elif new_id not in clocks:
            clocks[new_id] = float(businesses.get(new_id) or time.time())
        if old_id in carries:
            carries[new_id] = carries.pop(old_id)
        else:
            carries.setdefault(new_id, 0.0)
    if len(tx) > 200:
        del tx[:-200]
    if changed:
        mark_dirty()
    return changed

def _business_catalog():
    rows=[]
    for idx, (b_id, info) in enumerate(BUSINESSES.items(), 1):
        rows.append((idx, b_id, info, False))
    donor_start = len(rows) + 1
    for idx, (b_id, info) in enumerate(DONOR_BUSINESSES.items(), donor_start):
        rows.append((idx, b_id, info, True))
    return rows

def _business_by_number(number):
    try:
        number=int(number)
    except (TypeError, ValueError):
        return None
    for idx, b_id, info, donor in _business_catalog():
        if idx == number:
            return idx, b_id, info, donor
    return None

def _business_user_owns(econ, b_id, donor=False):
    return b_id in (econ.get('donor_businesses', {}) if donor else econ.get('businesses', {}))

def _business_purchase_price(econ, b_id):
    prices=econ.setdefault('biz_purchase_price', {})
    if b_id not in prices:
        info=_business_info(b_id)
        if info and b_id in BUSINESSES:
            prices[b_id]=int(info.get('price', 0) or 0)
            mark_dirty()
    return int(prices.get(b_id, 0) or 0)

def _business_stars_price(b_id):
    item = next((v for v in (STARS_COSMETICS or {}).values()
                 if isinstance(v, dict) and v.get('type') == 'donor_business'
                 and v.get('business_id') == b_id), None)
    try:
        return int(item.get('stars', item.get('price', 0)) or 0) if item else 0
    except (TypeError, ValueError, AttributeError):
        return 0

def _render_business_catalog(chat_id, user_id, user_name, message_id=None):
    econ=get_user_econ(user_id,user_name)
    _migrate_legacy_businesses(econ)
    rows=[]
    ordinary=[]
    donor=[]
    for idx,b_id,info,is_donor in _business_catalog():
        owned = _business_user_owns(econ, b_id, is_donor)
        status = '✅ Куплен' if owned else '❌ Не куплен'
        if is_donor:
            price_text = f"{_business_stars_price(b_id)} ⭐"
            line=f"{idx}. {info['name']} — {price_text} — {status}"
            donor.append(line)
        else:
            price_text = f"{int(info.get('price', 0) or 0):,} 🪙"
            line=f"{idx}. {info['name']} — {price_text} — {status}"
            ordinary.append(line)
    lines=[
        '🏢 <b>БИЗНЕСЫ NYABOT</b>',
        '',
        *[f'<blockquote>{html.escape(line)}</blockquote>' for line in ordinary],
        '',
        '💎 <b>ДОНАТНЫЕ</b>',
        *[f'<blockquote>{html.escape(line)}</blockquote>' for line in donor],
        '',
        '━━━━━━━━━━━━━━━━━━━━',
        '💡 Откройте конкретное предприятие сообщением:',
        '<code>бизнес 1</code>',
        f'🪙 Ваш баланс: <b>{int(econ.get("balance",0) or 0):,}</b>'
    ]
    text='\n'.join(lines)
    if message_id:
        try:
            bot.edit_message_text(text,chat_id=chat_id,message_id=message_id,parse_mode='HTML')
            return
        except Exception:
            pass
    bot.send_message(chat_id,text,parse_mode='HTML')

def render_business_detail(chat_id,user_id,user_name,number,message_id=None):
    target=_business_by_number(number)
    if not target:
        bot.send_message(chat_id,'❌ Такого номера бизнеса нет. Напишите <code>бизнесы</code>.',parse_mode='HTML')
        return
    idx,b_id,info,is_donor=target
    econ=get_user_econ(user_id,user_name)
    _migrate_legacy_businesses(econ)
    owned=_business_user_owns(econ,b_id,is_donor)
    lvl=_business_level(econ,b_id) if owned else 1
    inc=_business_hourly_income(b_id,lvl)
    price=int(info.get('price',0) or 0)
    if owned:
        pending=_business_pending_amount(econ,b_id,time.time())
        purchase_price=_business_purchase_price(econ,b_id)
        sell_value=int(purchase_price*BUSINESS_SELL_RATE)
        text=(f"🏢 <b>ВАШ БИЗНЕС #{idx}</b>\n\n"
              f'<blockquote>{html.escape(info["name"])}\n'
              f'👤 Владелец: {html.escape(user_name)}\n'
              f'⭐ Уровень: <b>{lvl}/5</b>\n'
              f'📈 Доход: <b>{inc:,} 🪙/ч</b>\n'
              f'💰 Накоплено: <b>{pending:,} 🪙</b></blockquote>\n'
              f'━━━━━━━━━━━━━━━━━━━━\n'
              f'💸 При продаже вы получите <b>{sell_value:,} 🪙</b> (80% от цены покупки).')
        kb=InlineKeyboardMarkup(row_width=2)
        if lvl<5: kb.add(InlineKeyboardButton('⬆️ Улучшить',callback_data=f'biz_detail_up:{b_id}:{user_id}'))
        kb.add(InlineKeyboardButton('💸 Продать',callback_data=f'biz_detail_sell:{b_id}:{user_id}'))
    else:
        text=(f"🏢 <b>БИЗНЕС #{idx}</b>\n\n"
              f'<blockquote>{html.escape(info["name"])}\n'
              f'❌ У вас пока нет этого бизнеса.</blockquote>\n'
              f'💰 Стоимость: <b>{price:,} 🪙</b>\n'
              f'📈 Доход: <b>{inc:,} 🪙/ч</b>')
        kb=InlineKeyboardMarkup()
        cb=f'biz_detail_buy:{b_id}:{user_id}' if not is_donor else f'biz_detail_donor:{b_id}:{user_id}'
        kb.add(InlineKeyboardButton('🛒 Купить' if not is_donor else '💎 Открыть в Stars-магазине',callback_data=cb))
    if message_id:
        try:
            bot.edit_message_text(text,chat_id=chat_id,message_id=message_id,reply_markup=kb,parse_mode='HTML')
            return
        except Exception:
            pass
    bot.send_message(chat_id,text,reply_markup=kb,parse_mode='HTML')

def _delete_message_quietly(chat_id,message_id):
    try:
        bot.delete_message(chat_id,message_id)
    except Exception:
        pass

def _record_business_tx(econ, entry):
    tx=econ.setdefault('business_transactions',[])
    tx.append(entry)
    del tx[:-200]

def _business_info(b_id):
    return BUSINESSES.get(b_id) or DONOR_BUSINESSES.get(b_id)


def _business_level(econ, b_id):
    levels = econ.get('biz_levels', {}) or {}
    try:
        return max(1, min(5, int(levels.get(b_id, 1))))
    except (TypeError, ValueError):
        return 1


def _business_hourly_income(b_id, level):
    info = _business_info(b_id)
    if not info:
        return 0
    level = max(1, min(5, int(level or 1)))
    return int(info.get('base_income', 0) * (1 + (level - 1) * 0.45))


def _ensure_business_clocks(econ, now=None):
    """Migrate old business timing to per-business timing without retroactive overpayment."""
    now = float(now or time.time())
    with db_lock:
        changed = False
        clocks = econ.get('biz_last_collect')
        if not isinstance(clocks, dict):
            clocks = {}
            econ['biz_last_collect'] = clocks
            changed = True
        carries = econ.get('biz_income_carry')
        if not isinstance(carries, dict):
            carries = {}
            econ['biz_income_carry'] = carries
            changed = True
        try:
            global_last = float(econ.get('last_biz_collect', now) or now)
        except (TypeError, ValueError):
            global_last = now
            if econ.get('last_biz_collect') != now:
                econ['last_biz_collect'] = now
                changed = True

        businesses = econ.get('businesses', {})
        if not isinstance(businesses, dict):
            businesses = {}
            econ['businesses'] = businesses
            changed = True
        for b_id, purchased_at in businesses.items():
            if b_id not in BUSINESSES or b_id in clocks:
                continue
            try:
                purchase_ts = float(purchased_at)
            except (TypeError, ValueError):
                purchase_ts = global_last
            clocks[b_id] = max(global_last, purchase_ts)
            carries.setdefault(b_id, 0.0)
            changed = True

        donor_purchases = econ.get('donor_business_purchased_at', {})
        if not isinstance(donor_purchases, dict):
            donor_purchases = {}
            econ['donor_business_purchased_at'] = donor_purchases
            changed = True
        donor_businesses = econ.get('donor_businesses', {})
        if not isinstance(donor_businesses, dict):
            donor_businesses = {}
            econ['donor_businesses'] = donor_businesses
            changed = True
        for b_id in donor_businesses.keys():
            if b_id not in DONOR_BUSINESSES or b_id in clocks:
                continue
            try:
                purchase_ts = float(donor_purchases.get(b_id, global_last) or global_last)
            except (TypeError, ValueError):
                purchase_ts = global_last
            clocks[b_id] = max(global_last, purchase_ts)
            carries.setdefault(b_id, 0.0)
            changed = True

        if changed:
            mark_dirty()
        return clocks, carries

def _business_pending_amount(econ, b_id, now=None):
    now = float(now or time.time())
    clocks, carries = _ensure_business_clocks(econ, now)
    if b_id not in clocks:
        return 0
    try:
        last = float(clocks.get(b_id, now))
    except (TypeError, ValueError):
        last = now
    elapsed = max(0.0, now - last)
    try:
        carry = float(carries.get(b_id, 0.0) or 0.0)
    except (TypeError, ValueError):
        carry = 0.0
    raw = (_business_hourly_income(b_id, _business_level(econ, b_id)) * elapsed / 3600.0) + carry
    return max(0, int(raw))


def _settle_one_business(econ, b_id, now=None, credit=True):
    """Settle one business at its CURRENT level and preserve fractional income."""
    now = float(now or time.time())
    clocks, carries = _ensure_business_clocks(econ, now)
    if b_id not in clocks:
        return 0
    try:
        last = float(clocks.get(b_id, now))
    except (TypeError, ValueError):
        last = now
    elapsed = max(0.0, now - last)
    try:
        carry = float(carries.get(b_id, 0.0) or 0.0)
    except (TypeError, ValueError):
        carry = 0.0
    raw = (_business_hourly_income(b_id, _business_level(econ, b_id)) * elapsed / 3600.0) + carry
    amount = max(0, int(raw))
    clocks[b_id] = now
    carries[b_id] = max(0.0, raw - amount)
    if credit and amount > 0:
        _set_balance(econ, int(econ.get('balance', 0) or 0) + amount)
    return amount


def _settle_business_net_profit(econ, b_id, now=None):
    """Settle one business at its current level and apply the 20% tax once.

    Used for boundary events such as upgrade/sale. Normal collection uses the
    aggregate event/bonus engine below, so those operations keep their existing
    gameplay modifiers.
    """
    raw = _settle_one_business(econ, b_id, now, credit=False)
    if raw <= 0:
        return 0, 0
    tax = int(raw * BUSINESS_TAX_RATE)
    net = max(0, raw - tax)
    econ['business_tax_paid'] = int(econ.get('business_tax_paid', 0) or 0) + tax
    if net:
        _adjust_balance(econ, net)
    mark_dirty()
    return net, tax


def collect_business_base_profit(econ, now=None):
    """Collect all ordinary/donor business income using exactly the same engine everywhere."""
    now = float(now or time.time())
    total = 0
    _ensure_business_clocks(econ, now)
    ordinary = econ.get('businesses', {})
    donor = econ.get('donor_businesses', {})
    if not isinstance(ordinary, dict):
        ordinary = {}
        econ['businesses'] = ordinary
        mark_dirty()
    if not isinstance(donor, dict):
        donor = {}
        econ['donor_businesses'] = donor
        mark_dirty()
    valid_businesses = 0
    for b_id in list(ordinary.keys()) + list(donor.keys()):
        if b_id not in BUSINESSES and b_id not in DONOR_BUSINESSES:
            continue
        valid_businesses += 1
        total += _settle_one_business(econ, b_id, now, credit=False)
    # Settlement advances clocks/carries even if less than one coin accumulated.
    if valid_businesses:
        econ['last_biz_collect'] = now
        mark_dirty()
    return total


def _apply_business_payout_modifiers(econ, base_profit, chat_id, user_id, user_name):
    """Apply events/bonuses, then the v0.3 20% business tax exactly once."""
    if base_profit <= 0:
        return 0, ''
    gross = int(base_profit)
    profit = gross
    event_text = ''
    econ_event = get_economic_event() if 'get_economic_event' in globals() else None
    if econ_event and econ_event.get('biz_income'):
        mult = float(econ_event['biz_income'])
        profit = int(profit * mult)
        event_text += f"\n🌍 Событие <b>{html.escape(str(econ_event['name']))}</b>: ×{mult:.2f}"

    if random.random() < 0.15:
        if random.random() < 0.70:
            boost = int(profit * 0.5)
            profit += boost
            event_text += f"\n🌟 <b>Вирусный тренд!</b> Бонус <b>+{boost:,} 🪙</b>."
        else:
            extra = int(profit * 0.15)
            profit = max(0, profit - extra)
            event_text += f"\n⚠️ Техобслуживание: <b>-{extra:,} 🪙</b>."

    active_t = econ.get('active_title')
    if active_t and active_t in TITLES and TITLES[active_t].get('buff') == 'biz_bonus':
        bonus_t = int(profit * (TITLES[active_t]['val'] / 100.0))
        profit += bonus_t
        event_text += f"\n👑 Бонус титула: <b>+{bonus_t:,} 🪙</b>"

    donor_biz = get_title_business_bonus(econ)
    vip_biz = get_vip_business_bonus(econ)
    if donor_biz or vip_biz:
        bonus_biz = int(profit * (donor_biz + vip_biz))
        profit += bonus_biz
        event_text += f"\n💎 VIP/донат-бонус: <b>+{bonus_biz:,} 🪙</b>"

    tax = int(max(0, profit) * BUSINESS_TAX_RATE)
    net = max(0, profit - tax)
    econ['business_tax_paid'] = int(econ.get('business_tax_paid', 0) or 0) + tax
    event_text = (f"\n💰 Валовая прибыль: <b>+{profit:,} 🪙</b>"
                  f"\n📉 Налог бизнеса ({BUSINESS_TAX_RATE:.0%}): <b>-{tax:,} 🪙</b>"
                  f"\n🪙 <b>К получению: +{net:,} 🪙</b>" + event_text)
    return net, event_text


def render_business_view(chat_id, user_id, user_name, message_id=None):
    # v0.3: catalog first; concrete cards are opened by "бизнес N".
    return _render_business_catalog(chat_id, user_id, user_name, message_id=message_id)



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
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Владелец: {make_link(chat_id, user_name, user_id, ping=False)}\n\n"
        f"💳 На депозите: <b>{deposit} Ня-коинов 🪙</b>\n"
        f"💵 В кармане: <b>{pocket} 🪙</b>\n\n"
        f"📈 <b>Ставка:</b> <b>+0.25% каждые 6 часов (1% в сутки)</b>\n"
        f"🛡 <b>Защита:</b> Депозит защищен от любых карманных краж на 100%!\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
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



def render_lottery_view(chat_id, user_id, user_name, message_id=None):
    lottery = db.setdefault('lottery', {'tickets': {}, 'pot': 0, 'last_draw': 0})
    tickets = lottery.get('tickets', {})
    pot = lottery.get('pot', 0)
    total_tickets = sum(tickets.values())

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎟 Купить 1 билет (100 🪙)", callback_data=f"buy_ticket_1:{user_id}"))
    # При 6–9 билетах кнопка на 5 скрывается: иначе старый callback мог перевести тираж за лимит 10.
    if total_tickets <= 5:
        markup.add(InlineKeyboardButton("🎟 Купить 5 билетов (500 🪙)", callback_data=f"buy_ticket_5:{user_id}"))

    my_tickets = tickets.get(str(user_id), 0)

    text = (
        f"🎟 <b>СЕРВЕРНАЯ ДЖЕКПОТ-ЛОТЕРЕЯ</b> 😺\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Текущий Джекпот: <b>{pot} Ня-коинов 🪙</b>\n"
        f"🎫 Продано билетов: <b>{total_tickets}/10</b>\n"
        f"👤 Ваших билетов: <b>{my_tickets} шт.</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 При достижении <b>10 билетов</b> бот автоматически разыграет весь банк между участниками! 😸"
    )
    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return
    try: bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception as e: print(f"[NONFATAL ERROR] {e}")


# ---------------------------------------------------------
# ИСТОРИЯ РЕСТОВ И НАСТРОЙКИ ЧАТА
# ---------------------------------------------------------

def _lang_keyboard(chat_id, user_id, group=False):
    prefix = 'set_chat_lang' if group else 'set_user_lang'
    uid = int(user_id or 0)
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(InlineKeyboardButton('🇷🇺 Русский', callback_data=f'{prefix}_ru:{uid}'),
           InlineKeyboardButton('🇺🇦 Українська', callback_data=f'{prefix}_uk:{uid}'),
           InlineKeyboardButton('🇬🇧 English', callback_data=f'{prefix}_en:{uid}'))
    return kb

def render_private_settings(chat_id, user_id, message_id=None):
    econ = get_user_econ(user_id=user_id)
    lang = econ.get('language', 'ru') if econ else 'ru'
    text = {
        'ru': '⚙️ <b>ЛИЧНЫЕ НАСТРОЙКИ</b>\nВыбери язык ответов бота в личных сообщениях.',
        'uk': '⚙️ <b>ОСОБИСТІ НАЛАШТУВАННЯ</b>\nОбери мову відповідей бота в особистих повідомленнях.',
        'en': '⚙️ <b>PERSONAL SETTINGS</b>\nChoose the language for bot replies in private chat.'
    }.get(lang, '⚙️ <b>PERSONAL SETTINGS</b>\nChoose the language for bot replies in private chat.')
    text += f'\n\n🌐 {lang.upper()}'
    markup = _lang_keyboard(chat_id, user_id, False)
    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            return
        except Exception as exc:
            if 'message is not modified' in str(exc).lower():
                return
            print(f'[LANG SETTINGS EDIT] {exc}')
            try:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
            except Exception as send_exc:
                print(f'[LANG SETTINGS SEND] {send_exc}')
            return
    try:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception as exc:
        print(f'[LANG SETTINGS SEND] {exc}')

def render_settings_view(chat_id, user_id=None, message_id=None):
    sett=get_chat_settings(chat_id); lang=sett.get('language','ru')
    labels={
      'ru':('⚙️ <b>НАСТРОЙКИ НЯ-БОТА ДЛЯ ЧАТА</b> 😺','РП-команды','Антифлуд','Антифлуд для админов','Авто-реакции','Приветствия','Напоминание','Лимит варнов','Язык'),
      'uk':('⚙️ <b>НАЛАШТУВАННЯ Nya-БОТА ДЛЯ ЧАТУ</b> 😺','РП-команди','Антифлуд','Антифлуд для адмінів','Авто-реакції','Привітання','Нагадування','Ліміт варнів','Мова'),
      'en':('⚙️ <b>NYA BOT CHAT SETTINGS</b> 😺','RP commands','Anti-flood','Anti-flood for admins','Auto reactions','Welcome messages','Reminder','Warn limit','Language')
    }[lang]
    rp='✅' if sett.get('rp_enabled',True) else '❌'; flood='✅' if sett.get('flood_protection',False) else '❌'; fa='✅' if sett.get('flood_admins',False) else '❌'; react='✅' if sett.get('auto_reactions',True) else '❌'; welcome='✅' if sett.get('welcome_enabled',True) else '❌'
    uid_tag=f':{user_id}' if user_id else ''
    kb=InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f'🎭 {labels[1]}: {rp}',callback_data=f'toggle_rp{uid_tag}'))
    kb.add(InlineKeyboardButton(f'🛡 {labels[2]}: {flood}',callback_data=f'toggle_flood{uid_tag}'))
    kb.add(InlineKeyboardButton(f'👮 {labels[3]}: {fa}',callback_data=f'toggle_flood_admins{uid_tag}'))
    kb.add(InlineKeyboardButton(f'✨ {labels[4]}: {react}',callback_data=f'toggle_reactions{uid_tag}'))
    kb.add(InlineKeyboardButton(f'👋 {labels[5]}: {welcome}',callback_data=f'toggle_welcome{uid_tag}'))
    kb.add(InlineKeyboardButton(f'🔔 {labels[6]}: {sett.get("remind_minutes",60)} min',callback_data=f'set_remind_time{uid_tag}'))
    kb.add(InlineKeyboardButton(f'⚠️ {labels[7]}: {sett.get("warn_limit",3)}',callback_data=f'set_warn_limit{uid_tag}'))
    admin_funcs='✅' if sett.get('admin_functions_enabled', True) else '❌'
    kb.add(InlineKeyboardButton(f'👮 Функции админов: {admin_funcs}', callback_data=f'toggle_admin_functions{uid_tag}'))
    kb.add(*_lang_keyboard(chat_id,user_id,True).keyboard[0])
    text=(f'{labels[0]}\n━━━━━━━━━━━━━━━━━━━━\n🌐 {labels[8]}: <b>{lang.upper()}</b>\n⚠️ {labels[7]}: <b>{sett.get("warn_limit",3)}</b>\n\n<i>Настройки группы доступны администраторам.</i>')
    if message_id:
        bot.edit_message_text(text,chat_id=chat_id,message_id=message_id,reply_markup=kb,parse_mode='HTML')
    else:
        bot.send_message(chat_id,text,reply_markup=kb,parse_mode='HTML')


# ---------------------------------------------------------
# НАСТРОЙКИ ПРОФИЛЯ
# Аватарки профиля отключены: старое поле pfp_file_id намеренно не трогаем
# для совместимости со старыми данными, но больше нигде не используем.
# ---------------------------------------------------------
def render_profile_settings_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    cur_theme = econ.get('profile_theme', 'default')
    theme_name = THEMES.get(cur_theme, {}).get('name', 'Классическая')

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🎨 Сменить Тему", callback_data=f"ps_themes:{user_id}")
    )
    markup.add(
        InlineKeyboardButton("🏷 Значки", callback_data=f"ps_badges:{user_id}"),
        InlineKeyboardButton("👑 Титулы", callback_data=f"ps_titles:{user_id}")
    )
    markup.add(
        InlineKeyboardButton("🎞 GIF профиля", callback_data=f"shop_cat_gifs:{user_id}")
    )
    markup.add(
        InlineKeyboardButton("🔙 В Профиль", callback_data=f"ps_back_profile:{user_id}")
    )

    text = (
        f"{premium_emoji('profile', '🐱')} ⚙️ <b>НАСТРОЙКИ ВНЕШНЕГО ВИДА ПРОФИЛЯ</b> 😺\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Игрок: {make_link(chat_id, user_name, user_id, ping=False)}\n"
        f"🎨 Активная тема: <b>{theme_name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Используйте кнопки ниже для индивидуальной кастомизации вашей карточки игрока!</i> 😻"
    )

    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return
    try: bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception as e: print(f"[NONFATAL ERROR] {e}")




def _send_user_profile_impl(chat_id, user_tag, user_id, message_to_reply=None, message_id_to_edit=None, username=None):
    """Компактная тематическая карточка статистики без inline-кнопок."""
    econ = get_user_econ(user_id, user_tag, username=username)
    theme_key = econ.get('profile_theme', 'default')
    theme_info = THEMES.get(theme_key, THEMES['default'])
    border = theme_info.get('border', '━━━━━━━━━━━━━━━━━━━━')
    header = theme_info.get('header', '👤 <b>КАРТОЧКА ИГРОКА</b>')
    icon = theme_info.get('icon', '🔹')

    lvl, cur_exp, next_exp, bar = get_account_level(econ.get('account_exp', 0))
    st = econ.get('msg_stats', {}) or {}
    day_count = max(0, int(st.get('day_count', 0) or 0))
    week_count = max(0, int(st.get('week_count', 0) or 0))
    month_count = max(0, int(st.get('month_count', 0) or 0))
    total_count = max(0, int(st.get('total_count', 0) or 0))
    if int(chat_id) < 0:
        chat_stat = (econ.get('msg_stats_chats') or {}).get(str(int(chat_id)), 0)
        if isinstance(chat_stat, dict):
            # For a group, all four message counters are chat-local.
            day_count = max(0, int(chat_stat.get('day_count', 0) or 0))
            week_count = max(0, int(chat_stat.get('week_count', 0) or 0))
            month_count = max(0, int(chat_stat.get('month_count', 0) or 0))
            total_count = max(0, int(chat_stat.get('total_count', 0) or 0))

    balance = max(0, int(econ.get('balance', 0) or 0))
    bank = max(0, int(econ.get('bank_deposit', 0) or 0))
    games = max(0, int(st.get('games', econ.get('games_played', 0)) or 0))
    mines_wins = max(0, int(st.get('mines_wins', econ.get('mines_wins', 0)) or 0))
    fish_count = sum(max(0, int(v or 0)) for v in (econ.get('fish_inventory', {}) or {}).values())
    hunt_count = sum(max(0, int(v or 0)) for v in (econ.get('hunt_inventory', {}) or {}).values())

    active_title = econ.get('active_title')
    custom_title = econ.get('custom_title')
    if custom_title:
        title = html.escape(str(custom_title))
    elif active_title in TITLES:
        title = html.escape(str(TITLES[active_title].get('text', active_title)))
    else:
        title = '—'

    gif_key = econ.get('profile_gif')
    gif_info = PROFILE_GIFS.get(gif_key) if gif_key else None

    raw_text = (
        f"{header}\n"
        f"{border}\n"
        f"{icon} <b>{make_link(chat_id, user_tag, user_id, ping=False)}</b>\n"
        f"{icon} <b>Уровень:</b> {lvl} LVL · {cur_exp:,}/{next_exp:,} XP\n"
        f"{icon} <b>Прогресс:</b> [{bar}]\n"
        f"{icon} <b>Баланс:</b> {balance:,} 🪙 · <b>Банк:</b> {bank:,} 🏦\n"
        f"{icon} <b>Титул:</b> {title}\n"
        f"{border}\n"
        f"📊 <b>СТАТИСТИКА</b>\n"
        f"├ Сегодня · <b>{day_count:,}</b> сообщений\n"
        f"├ Неделя · <b>{week_count:,}</b> сообщений\n"
        f"├ Месяц · <b>{month_count:,}</b> сообщений\n"
        f"└ Всё время · <b>{total_count:,}</b> сообщений\n"
        f"{border}\n"
        f"🎮 Игр · <b>{games:,}</b>  |  💣 Побед в Минах · <b>{mines_wins:,}</b>\n"
        f"🎣 Рыба · <b>{fish_count:,}</b>  |  🏹 Добыча · <b>{hunt_count:,}</b>\n"
        f"{border}"
    ).strip()

    if gif_info and len(raw_text) > 1000:
        raw_text = raw_text[:997].rstrip() + '…'

    def _send_new():
        if gif_info:
            if message_to_reply is not None:
                return bot.send_animation(chat_id, gif_info['url'], caption=raw_text, parse_mode='HTML', reply_to_message_id=message_to_reply.message_id)
            return bot.send_animation(chat_id, gif_info['url'], caption=raw_text, parse_mode='HTML')
        if message_to_reply is not None:
            return bot.reply_to(message_to_reply, raw_text, parse_mode='HTML')
        return bot.send_message(chat_id, raw_text, parse_mode='HTML')

    if message_id_to_edit:
        try:
            if gif_info:
                media = InputMediaAnimation(media=gif_info['url'], caption=raw_text, parse_mode='HTML')
                bot.edit_message_media(media, chat_id=chat_id, message_id=message_id_to_edit)
            else:
                bot.edit_message_text(raw_text, chat_id=chat_id, message_id=message_id_to_edit, parse_mode='HTML')
            return
        except Exception as edit_error:
            if 'message is not modified' in str(edit_error).lower():
                return
            print(f'[PROFILE EDIT] replacing old profile message: {edit_error}')
            try:
                bot.delete_message(chat_id, message_id_to_edit)
            except Exception:
                pass
            try:
                _send_new()
            except Exception as send_error:
                print(f'[PROFILE REPLACE ERROR] {send_error}')
            return

    try:
        _send_new()
    except Exception as e:
        print(f'[PROFILE SEND ERROR] {e}')




def get_durak_rank(wins):
    """Возвращает ранг по победам в Дураке. Не ломает старые профили."""
    try:
        wins = max(0, int(wins or 0))
    except (TypeError, ValueError):
        wins = 0
    if wins >= 500:
        return "👑 Император Дурака"
    if wins >= 250:
        return "💎 Мастер Дурака"
    if wins >= 100:
        return "🔥 Ветеран Дурака"
    if wins >= 50:
        return "⭐ Опытный игрок"
    if wins >= 20:
        return "🎲 Игрок"
    if wins >= 5:
        return "🌱 Новичок"
    return "🪶 Ученик"


def send_user_profile(chat_id, user_tag, user_id, message_to_reply=None, message_id_to_edit=None, username=None):
    """Безопасный вход в профиль: ошибка оформления не может убить /profile."""
    try:
        return _send_user_profile_impl(chat_id, user_tag, user_id, message_to_reply, message_id_to_edit, username)
    except Exception as profile_error:
        print(f"[PROFILE BUILD ERROR] {profile_error}")
        try:
            econ = get_user_econ(user_id, user_tag, username=username)
            balance = int(econ.get('balance', 0) or 0)
            level, exp, next_exp, bar = get_account_level(econ.get('account_exp', 0))
            fallback = (
                f"👤 <b>ПРОФИЛЬ</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Игрок: {html.escape(str(user_tag or 'Пользователь'))}\n"
                f"💰 Баланс: <b>{balance:,}</b> Ня-коинов\n"
                f"⭐ Уровень: <b>{level} LVL</b> [{bar}]\n"
                f"📈 EXP: <b>{exp:,}/{next_exp:,}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ Основная карточка временно не загрузилась, но команда /profile работает."
            )
            if message_to_reply:
                return bot.reply_to(message_to_reply, fallback, parse_mode='HTML')
            return bot.send_message(chat_id, fallback, parse_mode='HTML')
        except Exception as fallback_error:
            print(f"[PROFILE FALLBACK ERROR] {fallback_error}")
            return None

# ---------------------------------------------------------
# ЗАЩИТА ПОКУПОК TELEGRAM STARS
# ---------------------------------------------------------
def stars_limited_stock(item_key):
    sold = db.setdefault('stars_limited_stock', {})
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
        if title_id not in TITLES or not TITLES[title_id].get('donor_only'):
            raise ValueError(f'Invalid limited donor title: {item_key}')
    elif c_type == 'theme':
        if theme_id and theme_id not in THEMES:
            raise ValueError(f'Invalid limited theme: {item_key}')
    elif c_type == 'pet':
        if pet_id not in PETS_DATA:
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
            p_info = PETS_DATA[pet_id]
            activate_pet(econ, pet_id)
        mark_dirty()
        return item['name']
    except Exception:
        for key in ('paid_stars_items', 'titles', 'purchased_themes', 'active_title', 'custom_title', 'profile_theme', 'pet'):
            if key in snapshot:
                econ[key] = snapshot[key]
            elif key in econ and key in {'paid_stars_items', 'titles', 'purchased_themes'}:
                econ.pop(key, None)
        raise


# ---------------------------------------------------------
# ФУНКЦИИ МАГАЗИНА TELEGRAM STARS
# ---------------------------------------------------------
def render_stars_shop(chat_id, user_id, user_name, category='main', message_id=None):
    """Отдельный донатный магазин с категориями. Все товары здесь покупаются только за Telegram Stars."""
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
            "⭐️ <b>ДОНАТНЫЙ МАГАЗИН NYA</b> 😺",
            "━━━━━━━━━━━━━━━━━━━━",
            f"👤 Игрок: {make_link(chat_id, user_name, user_id, ping=False)}",
            f"⭐️ VIP: <b>{vip_status}</b>",
            f"🌟 Всего поддержано: <b>{donated} ⭐️</b>",
            "",
            "<i>Все товары ниже приобретаются только за Telegram Stars. Донатные предметы не появляются в обычном магазине.</i> 😻",
            "",
            "<b>Выберите категорию:</b>"
        ]
        markup.add(
            InlineKeyboardButton("💰 Коин-паки", callback_data=f"stars_cat_coins:{user_id}"),
            InlineKeyboardButton("👑 VIP Pass", callback_data=f"stars_cat_pass:{user_id}"),
            InlineKeyboardButton("🎨 Темы", callback_data=f"stars_cat_themes:{user_id}"),
            InlineKeyboardButton("✨ Stars-эффекты", callback_data=f"stars_cat_limited:{user_id}"),
            InlineKeyboardButton("👑 Титулы", callback_data=f"stars_cat_titles:{user_id}"),
            InlineKeyboardButton("✨ Значки", callback_data=f"stars_cat_badges:{user_id}"),
            InlineKeyboardButton("🎞 GIF профиля", callback_data=f"stars_cat_gifs:{user_id}"),
            InlineKeyboardButton("🐾 Донатные питомцы", callback_data=f"stars_cat_pets:{user_id}"),
            InlineKeyboardButton("🏢 Донатные бизнесы", callback_data=f"stars_cat_businesses:{user_id}"),
            InlineKeyboardButton("🏎 Донатные машины", callback_data=f"stars_cat_vehicles:{user_id}"),
        )
        markup.add(InlineKeyboardButton("🔙 Обычный магазин", callback_data=f"shop_main:{user_id}"))

    elif category == 'coins':
        lines = ["💰 <b>КОИНЫ ЗА STARS</b>", "━━━━━━━━━━━━━━━━━━━━"]
        for k, v in STARS_COIN_PACKS.items():
            lines.append(f"• <b>{v['name']}</b> — <b>{v['stars']} ⭐️</b>\n  <i>{v['desc']}</i>")
            markup.add(InlineKeyboardButton(f"Купить {v['name']} — {v['stars']} ⭐️", callback_data=f"star_buy_coins_{k}:{user_id}"))
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        markup.add(InlineKeyboardButton("🔙 Назад", callback_data=f"stars_cat_main:{user_id}"))

    elif category == 'pass':
        lines = ["👑 <b>VIP NYA PASS</b>", "━━━━━━━━━━━━━━━━━━━━", "• ⚡️ -35% таймеров\n• 🎁 2.25x /bonus\n• 🛡 защита от ограблений\n• 💼 +10% к работе и бизнесу\n• ⭐️ +25% EXP\n"]
        for k, v in STARS_VIP_PASS.items():
            if not stars_item_owned(econ, 'vippass', k):
                markup.add(InlineKeyboardButton(f"Купить {v['name']} — {v['stars']} ⭐️", callback_data=f"star_buy_pass_{k}:{user_id}"))
            else:
                lines.append(f"• {v['name']} — уже куплен ✅")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        markup.add(InlineKeyboardButton("🔙 Назад", callback_data=f"stars_cat_main:{user_id}"))

    else:
        type_map = {
            'themes': ('🎨 <b>ДОНАТНЫЕ ТЕМЫ</b>', {'theme'}),
            'limited': ('✨ <b>STARS-ЭФФЕКТЫ БЕЗ ОБЩЕГО ЛИМИТА</b>', {'limited_effect'}),
            'titles': ('👑 <b>ДОНАТНЫЕ ТИТУЛЫ</b>', {'donor_title', 'title_cert'}),
            'badges': ('✨ <b>ДОНАТНЫЕ ЗНАЧКИ</b>', {'badge'}),
            'gifs': ('🎞 <b>GIF ДЛЯ ПРОФИЛЯ</b>', {'gif'}),
            'pets': ('🐾 <b>ДОНАТНЫЕ ПИТОМЦЫ</b>', {'pet'}),
            'businesses': ('🏢 <b>ДОНАТНЫЕ БИЗНЕСЫ</b>', {'donor_business'}),
            'vehicles': ('🏎 <b>ДОНАТНЫЕ МАШИНЫ</b>', {'donor_vehicle'}),
        }
        if category not in type_map:
            return render_stars_shop(chat_id, user_id, user_name, 'main', message_id)
        title, wanted = type_map[category]
        lines = [title, "━━━━━━━━━━━━━━━━━━━━"]
        items = [(k, v) for k, v in STARS_COSMETICS.items() if v.get('type') in wanted]
        if category == 'limited': items += list(STARS_LIMITED_ITEMS.items())
        if not items:
            lines.append("Пока товаров нет.")
        for k, v in items:
            owned = stars_item_owned(econ, 'cosm', k)
            limited = k in STARS_HARD_LIMITED_ITEMS
            stock = f" | Осталось: {stars_hard_limited_available(k)}/5" if limited else ''
            status = ' ✅ УЖЕ КУПЛЕНО' if owned else ''
            lines.append(f"• <b>{v['name']}</b> — <b>{v['stars']} ⭐️</b>{stock}{status}\n  <i>{v['desc']}</i>")
            if not owned and (not limited or stars_hard_limited_available(k) > 0):
                markup.add(InlineKeyboardButton(f"Купить {v['name']} — {v['stars']} ⭐️", callback_data=f"star_buy_cosm_{k}:{user_id}"))
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        markup.add(InlineKeyboardButton("🔙 Назад в донатный магазин", callback_data=f"stars_cat_main:{user_id}"))

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

# Stars-only товары НИКОГДА не показываются и не выдаются через обычный магазин.
# Это отдельно защищено и на уровне кнопок, чтобы нельзя было купить их старым callback-ом.
STARS_ONLY_THEME_IDS = {'stars_gold', 'stars_anime', 'stars_galaxy', 'stars_moonlit'}
STARS_ONLY_PET_IDS = {'vip_griffin', 'moon_fox'}


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
    markup.add(InlineKeyboardButton('🎞 GIF для профиля', callback_data=f'shop_cat_gifs:{user_id}'))

    text = (
        "🏪 <b>ГЛОБАЛЬНЫЙ МАГАЗИН НЯ-БОТА</b> 😺\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
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

    _adjust_balance(econ, -(bet))
    process_casino_bet(bet, chat_id)

    game_id = f"bj_{user_id}_{time.time_ns()}"
    deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4
    random.shuffle(deck)

    p_cards = [deck.pop(), deck.pop()]
    d_cards = [deck.pop(), deck.pop()]

    active_bj_games[game_id] = {
        'user_id': user_id, 'user_tag': user_name, 'username': message.from_user.username,
        'chat_id': chat_id, 'bet': bet, 'deck': deck, 'p_cards': p_cards, 'd_cards': d_cards, 'finished': False, 'start_time': time.time()
    }

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🃏 Взять карту", callback_data=f"bj_hit_{game_id}:{user_id}"),
        InlineKeyboardButton("✋ Хватит", callback_data=f"bj_stand_{game_id}:{user_id}")
    )

    p_score = calculate_bj_score(p_cards)
    try:
        bot.send_message(
            chat_id,
            f"🃏 <b>БЛЭКДЖЕК (21 ОЧКО)</b> 😺\n━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Игрок: {make_link(chat_id, user_name, user_id, ping=True)}\n💰 Ставка: <b>{bet} 🪙</b>\n\n"
            f"🎴 Ваши карты: {p_cards} (Сумма: <b>{p_score}</b>)\n🤖 Дилер: [{d_cards[0]}, ❓]\n━━━━━━━━━━━━━━━━━━━━",
            reply_markup=markup, parse_mode='HTML'
        )
    except Exception as exc:
        active_bj_games.pop(game_id, None)
        _adjust_balance(econ, bet)
        reverse_casino_bet(bet, chat_id)
        print(f"[BJ START SEND ERROR] {exc}")
        try:
            bot.reply_to(message, '❌ Не удалось запустить Блэкджек. Ставка возвращена. 😿', parse_mode='HTML')
        except Exception:
            pass



# ---------------------------------------------------------
# КРИПТО-БИРЖА И ТОРГОВЛЯ
# ---------------------------------------------------------


def trade_crypto(chat_id, user_id, user_tag, action, ticker, amount_str, reply_msg=None, username=None):
    """Atomically execute one crypto trade and persist the transaction."""
    import math

    ticker = str(ticker or '').upper().strip()
    try:
        amount = float(amount_str)
        if math.isnan(amount) or math.isinf(amount) or amount <= 0 or amount > 1e12:
            raise ValueError
    except (ValueError, TypeError):
        msg = "❌ Укажите корректное положительное число монет! 😾"
        if reply_msg:
            bot.reply_to(reply_msg, msg, parse_mode='HTML')
        else:
            bot.send_message(chat_id, msg, parse_mode='HTML')
        return

    action = str(action or '').lower().strip()
    if action not in {'buy', 'sell'}:
        return

    result_msg = "❌ Не удалось выполнить сделку."
    with _get_user_action_lock(int(user_id)):
        with MARKET_LOCK:
            market = _get_market_data_locked()
            if ticker not in market:
                result_msg = f"❌ Неверный тикер! Доступные активы: <b>{', '.join(market.keys())}</b> 😾"
            else:
                econ = get_user_econ(user_id, user_tag, username=username)
                trade_snapshot = copy.deepcopy(econ)
                portfolio = econ.setdefault('crypto_portfolio', {})
                asset = market[ticker]
                price = float(asset.get('price', 0) or 0)
                total_cost = round(price * amount, 2)

                if total_cost <= 0 or total_cost > 10**18:
                    result_msg = "❌ Некорректная стоимость сделки. Попробуйте ещё раз."
                elif action == 'buy':
                    charge_cost = max(1, math.ceil(total_cost))
                    balance = int(econ.get('balance', 0) or 0)
                    if balance < charge_cost:
                        result_msg = (
                            f"❌ Недостаточно коинов! Нужно <b>{charge_cost} 🪙</b> "
                            f"(у вас: {balance} 🪙). 😿"
                        )
                    else:
                        _adjust_balance(econ, -charge_cost)
                        portfolio[ticker] = float(portfolio.get(ticker, 0.0) or 0.0) + amount
                        _record_crypto_transaction(econ, 'buy', ticker, amount, price, charge_cost)
                        check_achievements(user_id, user_tag, 'crypto_trades', 1, chat_id, username=username)
                        add_account_exp(user_id, user_tag, 10, username=username)
                        mark_dirty()
                        if not critical_save('crypto buy', retries=3):
                            # Internal trade: never report success when the durable
                            # snapshot was not committed. Roll the trade back.
                            econ.clear()
                            econ.update(trade_snapshot)
                            mark_dirty()
                            critical_save('crypto buy rollback', retries=2)
                            result_msg = '⚠️ Сделка отменена: база не подтвердила сохранение. Коины и крипта не изменены.'
                        else:
                            result_msg = (
                            f"✅ <b>УСПЕШНАЯ ПОКУПКА!</b> 😻\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"Куплено: <b>{amount:.8f} {ticker}</b> ({html.escape(str(asset.get('name', ticker)))})\n"
                            f"Цена: <b>{price:.8f} 🪙</b> за 1 {ticker}\n"
                            f"Списано: <b>-{charge_cost} 🪙</b>\n"
                            f"В портфеле: <b>{portfolio[ticker]:.8f} {ticker}</b>\n"
                            f"Остаток баланса: <b>{econ['balance']} 🪙</b>"
                            )
                else:
                    user_amount = float(portfolio.get(ticker, 0.0) or 0.0)
                    if user_amount + 1e-12 < amount:
                        result_msg = f"❌ Недостаточно {ticker}! В наличии: <b>{user_amount:.8f} шт.</b> 😿"
                    else:
                        new_amount = user_amount - amount
                        if new_amount <= 1e-9:
                            portfolio.pop(ticker, None)
                            new_amount = 0.0
                        else:
                            portfolio[ticker] = new_amount
                        earned = max(1, int(round(total_cost)))
                        _adjust_balance(econ, earned)
                        _record_crypto_transaction(econ, 'sell', ticker, amount, price, earned)
                        check_achievements(user_id, user_tag, 'crypto_trades', 1, chat_id, username=username)
                        add_account_exp(user_id, user_tag, 10, username=username)
                        mark_dirty()
                        if not critical_save('crypto sell', retries=3):
                            # Internal trade: restore both the asset and coins if the
                            # database rejected the committed snapshot.
                            econ.clear()
                            econ.update(trade_snapshot)
                            mark_dirty()
                            critical_save('crypto sell rollback', retries=2)
                            result_msg = '⚠️ Сделка отменена: база не подтвердила сохранение. Крипта и баланс восстановлены.'
                        else:
                            result_msg = (
                            f"💰 <b>УСПЕШНАЯ ПРОДАЖА!</b> 😸\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"Продано: <b>{amount:.8f} {ticker}</b>\n"
                            f"Цена: <b>{price:.8f} 🪙</b> за 1 {ticker}\n"
                            f"Выручка: <b>+{earned} 🪙</b>\n"
                            f"Остаток {ticker}: <b>{new_amount:.8f}</b>\n"
                            f"Новый баланс: <b>{econ['balance']} 🪙</b>"
                            )

    if reply_msg:
        bot.reply_to(reply_msg, result_msg, parse_mode='HTML')
    else:
        bot.send_message(chat_id, result_msg, parse_mode='HTML')


def _record_crypto_transaction(econ, action, ticker, amount, price, coins):
    rows = econ.setdefault('crypto_trade_history', [])
    rows.append({
        'time': time.time(), 'action': action, 'ticker': ticker,
        'amount': float(amount), 'price': float(price), 'coins': int(coins),
        'balance_after': int(econ.get('balance', 0) or 0),
        'portfolio_after': float(econ.get('crypto_portfolio', {}).get(ticker, 0.0) or 0.0),
    })
    del rows[:-200]


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













# ---------------------------------------------------------
# БИОМЕТРИЯ: IQ, ЖИР, ПЯТКА, ХРОМОСОМЫ
# ---------------------------------------------------------




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
        def _chat_message_count(info):
            chat_rows = info.get('msg_stats_chats', {}) or {}
            row = chat_rows.get(str(int(chat_id)), {})
            if isinstance(row, dict):
                return int(row.get('total_count', 0) or 0)
            # Backward compatibility with the old integer-only per-chat counter.
            return int(row or 0)
        sorted_data = sorted(visible_items.items(), key=lambda x: _chat_message_count(x[1]), reverse=True)
        title = "💬 <b>ТОП ПО СООБЩЕНИЯМ В ЧАТЕ</b> 😻"
        val_formatter = lambda info: f"<b>{_chat_message_count(info)} смс</b>"
    else:
        sorted_data = []
        title = "🏆 <b>ТОП УЧАСТНИКОВ</b>"
        val_formatter = lambda info: ""

    lines = [title, "━━━━━━━━━━━━━━━━━━━━"]
    for idx, (k, info) in enumerate(sorted_data[:10], 1):
        u_name = info.get('display_name', 'Пользователь')
        u_id = info.get('user_id')
        lines.append(f"{idx}. {make_link(chat_id, u_name, u_id, ping=False)} — {val_formatter(info)}")

    if not sorted_data: lines.append("<i>Данных для отображения пока нет... 😿</i>")
    lines.extend(["━━━━━━━━━━━━━━━━━━━━", "👇 <i>Нажмите категорию ниже для переключения:</i> 😺"])

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
    chat_key = str(int(chat_id))
    for info in db.get('economy',{}).values():
        chat_rows = info.get('msg_stats_chats', {}) or {}
        row = chat_rows.get(chat_key, {})
        if isinstance(row, dict):
            count = int(row.get(key, 0) or 0)
        else:
            # Old counter format only knew all-time totals, so do not fabricate
            # day/week values from it.
            count = 0
        if count>0: items.append((count,info))
    items.sort(key=lambda x:x[0],reverse=True)
    lines=[f'🏆 <b>ТОП АКТИВНОСТИ {label}</b>','━━━━━━━━━━━━━━━━━━━━']
    for i,(count,info) in enumerate(items[:10],1): lines.append(f"{i}. {make_link(chat_id,info.get('display_name','Пользователь'),info.get('user_id'),ping=False)} — <b>{count} смс</b>")
    if not items: lines.append('<i>Активности пока нет.</i>')
    bot.send_message(chat_id,'\n'.join(lines),parse_mode='HTML')




# ---------------------------------------------------------
# ГЛАВНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ И КОМАНД
# ---------------------------------------------------------

# ---------------------------------------------------------
# ИГРА СЕЙФ (ВЗЛОМ 4-ЗНАЧНОГО ШИФРА)
# ---------------------------------------------------------


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
            "━━━━━━━━━━━━━━━━━━━━",
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
            "━━━━━━━━━━━━━━━━━━━━",
            f"📍 Город: <b>{h_info['city']}</b>",
            f"👫 Владельцы: <b>{m.get('partner_name')}</b> & {make_link(chat_id, user_name, user_id, ping=False)}",
            f"🛋 Интерьер и мебель: <i>{furn_str}</i>",
            f"💰 Пассивный доход дома: <b>+{hourly_total} 🪙 в час</b> прямо в семейный сейф!",
            f"🏦 В семейном сейфе: <b>{m.get('vault', 0):,} 🪙</b>",
            "━━━━━━━━━━━━━━━━━━━━",
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




# ---------------------------------------------------------
# КРИМИНАЛ И ПОЛИЦИЯ ЧАТА (ШЕРИФ, РОЗЫСК, КПЗ, ПОБЕГ, ЗАЛОГ)
# ---------------------------------------------------------





# ---------------------------------------------------------
# ПОДПОЛЬНЫЕ БОИ ПИТОМЦЕВ (/pet_fight, /бой)
# ---------------------------------------------------------

# ---------------------------------------------------------
# БИРЖА КОНТЕНТА И МЕМОДЕЛЬНЯ (/meme)
# ---------------------------------------------------------
# ---------------------------------------------------------
# МЕМ-КОНКУРС 2.0
# ---------------------------------------------------------
def finalize_meme_contests(current_date=None):
    current_date = current_date or daily_task_date()
    with MEME_LOCK:
        return _finalize_meme_contests_locked(current_date)

def _finalize_meme_contests_locked(current_date):
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
                _adjust_balance(econ, 1500)
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
    with MEME_LOCK:
        return _record_meme_vote_locked(meme_id, user_id, is_like)

def _record_meme_vote_locked(meme_id, user_id, is_like):
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



# ---------------------------------------------------------
# ГЕНЕРАТОР ИСТОРИЙ И ФАНФИКОВ (/story, /fanfic)
# ---------------------------------------------------------
STORY_TEMPLATES = [
    "📖 <b>ХРОНИКИ ЧАТА: ДЕЛО О ШАУРМЕ</b> 🌯\n━━━━━━━━━━━━━━━━━━━━\nОднажды <b>{u1}</b> и <b>{u2}</b> решили открыть подпольный ларёк с шаурмой прямо в подвале Кровавой Бани. {u1} отвечал за секретный соус из кошачьих слёзок, а {u2} лично заманивал голодных участников чата. Бизнес шёл в гору, пока за шаурмой не пришёл местный шериф с ручным драконом! Теперь они оба флексят в центре площади и делают вид, что просто гуляли... 😹",
    "📖 <b>ХРОНИКИ ЧАТА: ИСЕКАЙ В МИР ТАПОК</b> 🩴\n━━━━━━━━━━━━━━━━━━━━\nВчера <b>{u1}</b> случайно уронил(а) золотой тапок на ногу <b>{u2}</b>, и открылся пространственный портал! Они очнулись в фэнтези-мире, где королём был Гигачад, а вместо магии все спорили о размере писюна и количестве хромосом. {u1} стал(а) верховным магом кошачьего тыгыдыка, а {u2} победил(а) финального босса, метко метнув в него жареного карася! 😻",
    "📖 <b>ХРОНИКИ ЧАТА: ОГРАБЛЕНИЕ ВЕКА</b> 🏦\n━━━━━━━━━━━━━━━━━━━━\n<b>{u1}</b> надел(а) маску-невидимку и позвал(а) <b>{u2}</b> грабить Ня-Банк. План был надёжен как швейцарские часы: {u1} отвлекает охрану танцем аниме-девочки, а {u2} взламывает сейф с помощью скрепки и молитвы семпаю. Всё шло идеально, пока сигнализация не заиграла гимн котиков на полную громкость! Пришлось убегать на дырявых сланцах с мешком коинов в зубах! 🏃‍♂️💨",
    "📖 <b>ХРОНИКИ ЧАТА: ТАЙНА ПОДВАЛА</b> 🩸\n━━━━━━━━━━━━━━━━━━━━\nПоздней ночью <b>{u1}</b> и <b>{u2}</b> исследовали больницу милосердия в поисках редкого лута. Вдруг из темноты раздался зловещий шорох... {u1} схватил(а) бамбуковую удочку, а {u2} прикрылся(лась) питомцем-капибарой. Оказалось, это Джейсон Вурхиз просто варил ночной пельменный суп и забыл посолить! В итоге все трое мирно пили чай с ромашкой до самого утра. 🍵✨",
    "📖 <b>ХРОНИКИ ЧАТА: КИБЕРПАНК 2077</b> 🤖\n━━━━━━━━━━━━━━━━━━━━\nВ неоновом мегаполисе <b>{u1}</b> прокачал(а) нейро-имплант для скоростного фапа, а <b>{u2}</b> установил(а) кибер-руку с лазерным бластером. Корпорация котиков объявила на них охоту за взлом биржи Ня-Биткоина. Уходя от дронов на боевой девятке ВАЗ-2107, они ворвались в стратосферу и навсегда вошли в легенды Ня-Стрит! 🚀🔥"
]


# ---------------------------------------------------------
# СЕЗОННЫЙ ХЕЛЛОУИНСКИЙ PASS (/pass, /bp, /хеллоуин)
# ---------------------------------------------------------
def render_halloween_bp_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    bp_exp = econ.get('bp_exp', 0)
    is_prem = bool(econ.get('bp_premium') or 'bp_premium' in (econ.get('paid_stars_items', []) or []))

    lvl, in_exp, req_exp, bar = get_user_bp_level(bp_exp)

    prem_status = "👑 Премиум Ветка АКТИВНА" if is_prem else "🔒 Бесплатная Ветка (Премиум за 4 ⭐️)"

    lines = [
        "🎃 <b>ХЕЛЛОУИНСКИЙ СЕЗОН: BATTLE PASS</b> 🦇 😺",
        "━━━━━━━━━━━━━━━━━━━━",
        f"👤 Участник: {make_link(chat_id, user_name, user_id, ping=False)}",
        f"🏆 Уровень пропуска: <b>{lvl}/30 LVL</b> [{bar}] ({in_exp}/{req_exp} EXP)",
        f"⭐️ Статус: <b>{prem_status}</b>\n",
        "<i>Опыт даётся за смс в чате, работу, рыбалку, охоту, мусорку и игры!</i>\n",
        "<b>Главные награды Хеллоуина:</b>",
        "• <b>Ур. 15 (Free):</b> 🎃 Эксклюзивный значок Тыквы",
        "• <b>Ур. 30 (Free):</b> 👑 Титул «🎃 Повелитель Тыкв» (+15% к удаче)",
        "• <b>Ур. 20 (Premium):</b> 🐱 Питомец: 🎃 Тыквоголовый Кот (+120% к удаче!)",
        "• <b>Ур. 30 (Premium):</b> 🎨 Тема профиля: «🎃 Тёмный Хеллоуин: Тыквенная Ночь»! 🦇",
        "━━━━━━━━━━━━━━━━━━━━"
    ]

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎁 Забрать доступные награды", callback_data=f"claim_bp_rewards:{user_id}"))

    if not is_prem:
        markup.add(InlineKeyboardButton("⭐️ Купить Премиум Pass (4 ⭐️ Stars)", callback_data=f"buy_bp_prem_stars:{user_id}"))

    text = "\n".join(lines)
    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')


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
        "━━━━━━━━━━━━━━━━━━━━",
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

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    text = "\n".join(lines)

    if message_id:
        try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
        return
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')


# ---------------------------------------------------------
# ПОДАРОК УСЛУГИ TELEGRAM STARS ДРУГУ (/gift_stars)
# ---------------------------------------------------------

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
    """Выдать владельцу ВСЕ постоянные товары из Stars-магазина. Идемпотентно."""
    econ['vip_forever'] = True
    econ['bp_premium'] = True
    econ['has_custom_title_cert'] = True
    paid = econ.setdefault('paid_stars_items', [])
    purchased_themes = econ.setdefault('purchased_themes', ['default'])
    titles = econ.setdefault('titles', [])
    profile_gifs = econ.setdefault('profile_gifs', [])
    vehicle_inventory = econ.setdefault('vehicle_inventory', [])
    donor_businesses = econ.setdefault('donor_businesses', {})
    inventory = econ.setdefault('inventory', [])

    for item_id, item in STARS_COSMETICS.items():
        item_type = item.get('type')
        hard_owned = item_id in STARS_HARD_LIMITED_ITEMS and stars_item_owned(econ, 'cosm', item_id)
        if item_id in STARS_HARD_LIMITED_ITEMS and item_id not in paid and not hard_owned:
            if not reserve_stars_hard_limited(item_id):
                continue
        if item_id not in paid:
            paid.append(item_id)

        if item_type == 'theme':
            theme_id = item.get('theme_id')
            if theme_id and theme_id not in purchased_themes:
                purchased_themes.append(theme_id)

        elif item_type == 'badge':
            emoji = item.get('emoji')
            if emoji and emoji not in inventory:
                inventory.append(emoji)

        elif item_type == 'donor_title':
            title_id = item.get('title_id')
            if title_id and title_id in TITLES and title_id not in titles:
                titles.append(title_id)
            if title_id and not econ.get('active_title'):
                econ['active_title'] = title_id

        elif item_type == 'pet':
            pet_id = item.get('pet_id')
            if pet_id in PETS_DATA:
                pinfo = PETS_DATA[pet_id]
                activate_pet(econ, pet_id)

        elif item_type == 'gif':
            gif_id = item.get('gif_id')
            if gif_id in PROFILE_GIFS and gif_id not in profile_gifs:
                profile_gifs.append(gif_id)
            if gif_id in PROFILE_GIFS and not econ.get('profile_gif'):
                econ['profile_gif'] = gif_id

        elif item_type == 'donor_vehicle':
            vid = item.get('vehicle_id')
            if vid in DONOR_VEHICLES and vid not in vehicle_inventory:
                vehicle_inventory.append(vid)
            if vid in DONOR_VEHICLES and not econ.get('equipped_vehicle'):
                econ['equipped_vehicle'] = vid
                econ['vehicle'] = vid

        elif item_type == 'donor_business':
            bid = item.get('business_id')
            if bid in DONOR_BUSINESSES:
                already_owned = bid in donor_businesses
                donor_businesses[bid] = max(1, int(donor_businesses.get(bid, 1)))
                if not already_owned:
                    purchase_now = time.time()
                    econ.setdefault('donor_business_purchased_at', {})[bid] = purchase_now
                    econ.setdefault('biz_last_collect', {})[bid] = purchase_now
                    econ.setdefault('biz_income_carry', {})[bid] = 0.0

    for item_id in STARS_LIMITED_ITEMS:
        if item_id not in paid:
            paid.append(item_id)
    # Старые отдельные VIP-значки тоже возвращаем, чтобы у старого владельца
    # после миграций не исчезали ранее купленные варианты.
    for badge_id, badge in VIP_BADGES.items():
        emoji = badge.get('emoji')
        if emoji and emoji not in inventory:
            inventory.append(emoji)


def _admin_grant(message):
    if not _is_owner_admin(message):
        return False
    raw = (message.text or '').strip()
    parts = raw.split()
    if len(parts) < 3:
        bot.reply_to(message, (
            "❌ Формат: <code>/give @user coins 100000</code>\n"
            "<code>/give @user level 50</code>\n"
            "<code>/give @user exp 5000</code>\n"
            "<code>/give @user work_exp 5000</code>\n"
            "<code>/give @user bank 100000</code>\n"
            "<code>/give @user all</code>"
        ), parse_mode='HTML')
        return True

    target_raw = parts[1]
    target_id = None
    target_name = None
    if message.reply_to_message and (target_raw.lower() in ('reply', '.', '-', '@reply', 'this')):
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

    def positive_int(value, label):
        try:
            n = int(value or '0')
        except (TypeError, ValueError):
            n = 0
        if n <= 0:
            bot.reply_to(message, f"❌ {label} должно быть положительным числом.")
            return None
        return n

    if item in ('coins', 'coin', 'коины', 'монеты'):
        value = positive_int(amount, 'Количество коинов')
        if value is None: return True
        _set_balance(econ, int(econ.get('balance', 0) or 0) + value)
        changed.append(f'+{value:,} 🪙')

    elif item in ('bank', 'банк', 'cash', 'касса'):
        value = positive_int(amount, 'Сумма')
        if value is None: return True
        econ['bank_deposit'] = int(econ.get('bank_deposit', 0) or 0) + value
        changed.append(f'+{value:,} 🏦 в банк/кассу')

    elif item in ('level', 'lvl', 'уровень'):
        value = positive_int(amount, 'Уровень')
        if value is None: return True
        econ['account_exp'] = account_exp_for_level(value)
        actual_level, _, _, _ = get_account_level(econ['account_exp'])
        changed.append(f'уровень профиля: {actual_level} LVL')

    elif item in ('exp', 'xp', 'account_exp', 'опыт'):
        value = positive_int(amount, 'Количество EXP')
        if value is None: return True
        econ['account_exp'] = int(econ.get('account_exp', 0) or 0) + value
        lvl, _, _, _ = get_account_level(econ['account_exp'])
        changed.append(f'+{value:,} EXP профиля → {lvl} LVL')

    elif item in ('set_exp', 'setexp'):
        value = positive_int(amount, 'EXP')
        if value is None: return True
        econ['account_exp'] = value
        lvl, _, _, _ = get_account_level(value)
        changed.append(f'установлен EXP: {value:,} → {lvl} LVL')

    elif item in ('work_exp', 'workexp', 'работа_exp', 'опыт_работы'):
        value = positive_int(amount, 'Опыт работы')
        if value is None: return True
        econ['work_exp'] = int(econ.get('work_exp', 0) or 0) + value
        changed.append(f'+{value:,} EXP работы')

    elif item in ('set_work_exp', 'set_workexp'):
        value = positive_int(amount, 'Опыт работы')
        if value is None: return True
        econ['work_exp'] = value
        changed.append(f'установлен EXP работы: {value:,}')

    elif item in ('vip', 'vip_days'):
        try: days = int(amount or '30')
        except (TypeError, ValueError): days = 0
        if days <= 0:
            bot.reply_to(message, "❌ Количество дней должно быть больше 0.")
            return True
        econ['vip_until'] = max(time.time(), econ.get('vip_until', 0)) + days * 86400
        changed.append(f'VIP +{days} дн.')

    elif item in ('vip_forever', 'vip_forever_25', 'вечный_vip'):
        econ['vip_forever'] = True
        changed.append('VIP навсегда')

    elif item in ('gif', 'profile_gif', 'гив'):
        gif_id = (amount or '').lower()
        if gif_id not in PROFILE_GIFS:
            bot.reply_to(message, "❌ GIF не найден. Доступны: <code>gulya</code>, <code>sakura_gif</code>, <code>mogger</code>, <code>cat</code>.", parse_mode='HTML')
            return True
        owned = econ.setdefault('profile_gifs', [])
        if gif_id not in owned: owned.append(gif_id)
        econ['profile_gif'] = gif_id
        changed.append(f"GIF: {PROFILE_GIFS[gif_id]['name']}")

    elif item in ('all', 'everything', 'донаты', 'donates', 'all_stars', 'stars_all'):
        _grant_all_donations(econ)
        changed.append('все Stars-донаты: VIP, питомцы, GIF, темы, титулы, значки, машины, бизнесы')

    elif item in ('vehicle', 'машина', 'транспорт'):
        vehicle_id = (amount or '').lower()
        if vehicle_id in VEHICLES:
            inv = econ.setdefault('vehicle_inventory', [])
            if vehicle_id not in inv:
                inv.append(vehicle_id)
            econ['equipped_vehicle'] = vehicle_id
            econ['vehicle'] = vehicle_id
            changed.append(f'машина {VEHICLES[vehicle_id]["name"]}')
        elif vehicle_id in DONOR_VEHICLES:
            inv = econ.setdefault('vehicle_inventory', [])
            if vehicle_id not in inv:
                inv.append(vehicle_id)
            econ['equipped_vehicle'] = vehicle_id
            econ['vehicle'] = vehicle_id
            paid = econ.setdefault('paid_stars_items', [])
            paid_id = next((k for k,v in STARS_COSMETICS.items() if v.get('type') == 'donor_vehicle' and v.get('vehicle_id') == vehicle_id), None)
            if paid_id and paid_id not in paid: paid.append(paid_id)
            changed.append(f'донатный транспорт {DONOR_VEHICLES[vehicle_id]["name"]}')
        else:
            bot.reply_to(message, "❌ Машина не найдена. Пример: <code>/give @user vehicle donor_lambo</code>.", parse_mode='HTML')
            return True

    elif item in ('rod', 'удочка'):
        rod_id = (amount or '').lower()
        if rod_id not in RODS:
            bot.reply_to(message, "❌ Удочка не найдена. Укажи ID из каталога RODS.")
            return True
        econ['equipped_rod'] = rod_id
        changed.append(f'удочка {RODS[rod_id]["name"]}')

    elif item in ('bow', 'лук'):
        bow_id = (amount or '').lower()
        if bow_id not in BOWS:
            bot.reply_to(message, "❌ Лук не найден. Укажи ID из каталога BOWS.")
            return True
        econ['equipped_bow'] = bow_id
        changed.append(f'лук {BOWS[bow_id]["name"]}')

    elif item in ('pet', 'питомец'):
        pet_id = (amount or '').lower()
        if pet_id not in PETS_DATA:
            bot.reply_to(message, "❌ Питомец не найден. Укажи его ID из PETS_DATA.")
            return True
        # Глобально лимитированный Лунный Фокс не должен выдаваться
        # через общий /give pet ... обходным путём. Админская выдача
        # тоже расходует один из пяти экземпляров.
        if pet_id == 'moon_fox':
            limited_key = 'pet_moon_fox'
            if stars_item_owned(econ, 'cosm', limited_key):
                changed.append(f"{STARS_COSMETICS[limited_key]['name']} — уже выдан")
            elif not reserve_stars_hard_limited(limited_key):
                bot.reply_to(message, "❌ Лимит Лунного Фокса уже исчерпан: 5/5 экземпляров.", parse_mode='HTML')
                return True
            else:
                try:
                    changed.append(grant_hard_limited_stars_item(econ, limited_key))
                except Exception as grant_error:
                    print(f'[ADMIN STARS] hard-limited pet grant failed: {limited_key}: {grant_error}')
                    release_stars_hard_limited(limited_key)
                    bot.reply_to(message, '❌ Не удалось выдать лимитированного питомца.', parse_mode='HTML')
                    return True
        else:
            pi = PETS_DATA[pet_id]
            econ['pet'] = {'id': pet_id, 'name': pi['name'], 'luck_bonus': pi['luck_bonus'], 'hunger': 100, 'cleanliness': 100, 'pet_exp': 0, 'last_update': time.time()}
            changed.append(f'питомец {pi["name"]}')

    elif item in ('item', 'предмет'):
        item_id = amount or ''
        if not item_id:
            bot.reply_to(message, "❌ Укажи ID предмета: <code>/give @user item ITEM_ID</code>.", parse_mode='HTML')
            return True
        econ.setdefault('inventory', [])
        if item_id not in econ['inventory']:
            econ['inventory'].append(item_id)
        changed.append(f'предмет {item_id}')

    elif item in ('business', 'biz', 'бизнес'):
        biz_id = (amount or '').lower()
        level_arg = parts[4] if len(parts) > 4 else '1'
        if biz_id in BUSINESSES:
            try: level = max(1, min(5, int(level_arg)))
            except (TypeError, ValueError): level = 1
            econ.setdefault('businesses', {})[biz_id] = True
            econ.setdefault('biz_levels', {})[biz_id] = level
            changed.append(f'бизнес {BUSINESSES[biz_id]["short"]} → уровень {level}')
        elif biz_id in DONOR_BUSINESSES:
            try: level = max(1, min(5, int(level_arg)))
            except (TypeError, ValueError): level = 1
            econ.setdefault('donor_businesses', {})[biz_id] = level
            econ.setdefault('biz_levels', {})[biz_id] = level
            paid = econ.setdefault('paid_stars_items', [])
            paid_id = next((k for k,v in STARS_COSMETICS.items() if v.get('type') == 'donor_business' and v.get('business_id') == biz_id), None)
            if paid_id and paid_id not in paid: paid.append(paid_id)
            changed.append(f'донатный бизнес {DONOR_BUSINESSES[biz_id]["name"]} → уровень {level}')
        else:
            bot.reply_to(message, "❌ Бизнес не найден. Укажи ID, например <code>club</code> или <code>donor_nightclub</code>.", parse_mode='HTML')
            return True

    elif item in STARS_HARD_LIMITED_ITEMS:
        if stars_item_owned(econ, 'cosm', item):
            changed.append(f"{STARS_COSMETICS[item]['name']} — уже выдан")
        elif not reserve_stars_hard_limited(item):
            bot.reply_to(message, "❌ Лимит этого предмета уже исчерпан: 5/5 экземпляров.", parse_mode='HTML')
            return True
        else:
            try:
                changed.append(grant_hard_limited_stars_item(econ, item))
            except Exception as grant_error:
                print(f'[ADMIN STARS] hard-limited grant failed: {item}: {grant_error}')
                release_stars_hard_limited(item)
                bot.reply_to(message, '❌ Не удалось выдать лимитированный Stars-предмет.', parse_mode='HTML')
                return True

    elif item in STARS_LIMITED_ITEMS:
        c = STARS_LIMITED_ITEMS[item]
        econ.setdefault('paid_stars_items', [])
        if item not in econ['paid_stars_items']:
            econ['paid_stars_items'].append(item)
        econ['active_limited_effect'] = c.get('emoji', '✨')
        changed.append(c.get('name', item))

    elif item in STARS_COSMETICS:
        c = STARS_COSMETICS[item]
        t = c.get('type')
        if t == 'bp_premium':
            econ['bp_premium'] = True
        elif t == 'title_cert':
            econ['has_custom_title_cert'] = True
        elif t == 'theme':
            th = c.get('theme_id'); purchased = econ.setdefault('purchased_themes', ['default'])
            if th and th not in purchased: purchased.append(th)
            if th: econ['profile_theme'] = th
        elif t == 'badge':
            em = c.get('emoji'); inv = econ.setdefault('inventory', [])
            if em and em not in inv: inv.append(em)
            econ['badge'] = em
        elif t == 'donor_title':
            tid = c.get('title_id')
            if tid and tid not in econ.setdefault('titles', []): econ['titles'].append(tid)
            if tid: econ['active_title'] = tid
        elif t == 'gif':
            gid = c.get('gif_id')
            if gid and gid not in econ.setdefault('profile_gifs', []): econ['profile_gifs'].append(gid)
            if gid: econ['profile_gif'] = gid
        elif t == 'pet':
            pid = c.get('pet_id'); econ.setdefault('paid_stars_items', [])
            if item not in econ['paid_stars_items']: econ['paid_stars_items'].append(item)
            if pid in PETS_DATA:
                pi = PETS_DATA[pid]
                econ['pet'] = {'id': pid, 'name': pi['name'], 'luck_bonus': pi['luck_bonus'], 'hunger': 100, 'cleanliness': 100, 'pet_exp': 0, 'last_update': time.time()}
        elif t == 'donor_vehicle':
            vid = c.get('vehicle_id')
            if vid in DONOR_VEHICLES:
                inv = econ.setdefault('vehicle_inventory', [])
                if vid not in inv: inv.append(vid)
                econ['equipped_vehicle'] = vid; econ['vehicle'] = vid
        elif t == 'donor_business':
            bid = c.get('business_id')
            if bid in DONOR_BUSINESSES:
                donor_owned = econ.setdefault('donor_businesses', {})
                already_owned = bid in donor_owned
                donor_owned[bid] = max(1, int(donor_owned.get(bid, 1)))
                if not already_owned:
                    purchase_now = time.time()
                    econ.setdefault('donor_business_purchased_at', {})[bid] = purchase_now
                    econ.setdefault('biz_last_collect', {})[bid] = purchase_now
                    econ.setdefault('biz_income_carry', {})[bid] = 0.0
        paid = econ.setdefault('paid_stars_items', [])
        if item not in paid: paid.append(item)
        changed.append(c.get('name', item))

    elif item in ('pass_forever', 'vip_pass_forever'):
        econ['vip_forever'] = True
        paid = econ.setdefault('paid_stars_items', [])
        if 'pass_forever' not in paid:
            paid.append('pass_forever')
        changed.append('VIP навсегда')

    elif item in ('bp_premium', 'premium_pass'):
        econ['bp_premium'] = True; econ.setdefault('paid_stars_items', [])
        if 'bp_premium' not in econ['paid_stars_items']: econ['paid_stars_items'].append('bp_premium')
        changed.append('Премиум Pass')

    elif item.startswith('theme_'):
        key = item.replace('theme_', '', 1)
        if key in THEMES:
            purchased = econ.setdefault('purchased_themes', ['default'])
            if key not in purchased: purchased.append(key)
            econ['profile_theme'] = key; changed.append(THEMES[key]['name'])
        else:
            bot.reply_to(message, "❌ Такой темы нет."); return True

    elif item.startswith('badge_'):
        key = item
        if key in STARS_COSMETICS and STARS_COSMETICS[key].get('type') == 'badge':
            em = STARS_COSMETICS[key]['emoji']; inv = econ.setdefault('inventory', [])
            if em and em not in inv: inv.append(em)
            econ['badge'] = em; changed.append(em)
        elif key in VIP_BADGES:
            em = VIP_BADGES[key]['emoji']; inv = econ.setdefault('inventory', [])
            if em not in inv: inv.append(em)
            econ['badge'] = em; changed.append(em)
        else:
            bot.reply_to(message, "❌ Такой VIP-значок не найден."); return True

    elif item in ('pet_griffin', 'vip_griffin'):
        econ.setdefault('paid_stars_items', [])
        if 'pet_griffin' not in econ['paid_stars_items']: econ['paid_stars_items'].append('pet_griffin')
        if 'vip_griffin' in PETS_DATA:
            activate_pet(econ, 'vip_griffin')
        changed.append('👑 Королевский Грифон')

    elif item == 'stars':
        value = positive_int(amount, 'Количество Stars')
        if value is None: return True
        econ['stars_donated'] = int(econ.get('stars_donated', 0) or 0) + value
        changed.append(f'+{value} ⭐️ в статистику донатов')

    else:
        bot.reply_to(message, "❌ Неизвестный предмет. Используй <code>all</code>, <code>coins</code>, <code>level</code>, <code>exp</code>, <code>work_exp</code>, <code>bank</code>, <code>business</code> или ID товара из Stars-магазина.", parse_mode='HTML')
        return True

    mark_dirty()
    bot.reply_to(message, f"✅ <b>Выдача выполнена</b>\n👤 {html.escape(str(target_name or target_id))}\n🎁 {html.escape(', '.join(changed))}", parse_mode='HTML')
    return True





















# ---------------------------------------------------------
# ОБРАБОТКА CALLBACK КНОПОК
# ---------------------------------------------------------
# ---------------------------------------------------------
# DRAGON GAME AUDIO: получение file_id для музыки и эффектов
# Только владелец бота и только в личке.
# После отправки аудио бот возвращает стабильный Telegram file_id.
# ---------------------------------------------------------












# ---------------------------------------------------------
# НОВЫЕ СИСТЕМЫ: РЕСУРСЫ / КРАФТ / ГИЛЬДИИ / РЫНОК / РЕЙДЫ / СЕЗОН
# ---------------------------------------------------------
CRAFT_RECIPES = {
    'energy_pack': {
        'name': '⚡ Энергетический набор',
        'need': {'fish': 2},
        'give': ('backpack', 'energy_drink', 1),
        'desc': '2 любые рыбы → +1 энергетик в рюкзаке.'
    },
    'lucky_bait': {
        'name': '🍀 Счастливая наживка',
        'need': {'fish': 3},
        'give': ('backpack', 'luck_clover', 1),
        'desc': '3 любые рыбы → +1 клевер удачи.'
    },
    'garden_fertilizer': {
        'name': '🌱 Супер-удобрение',
        'need': {'fish': 1, 'hunt': 1},
        'give': ('backpack', 'garden_fertilizer', 1),
        'desc': '1 рыба + 1 трофей → +1 удобрение.'
    },
    'alarm_system': {
        'name': '🚨 Система защиты',
        'need': {'hunt': 2, 'fish': 1},
        'give': ('backpack', 'alarm_system', 1),
        'desc': '2 трофея + 1 рыба → +1 систему защиты.'
    },
    'invis_mask': {
        'name': '🥷 Маска невидимки',
        'need': {'hunt': 3},
        'give': ('backpack', 'invis_mask', 1),
        'desc': '3 охотничьих трофея → +1 маску невидимки.'
    },
}

ECONOMIC_EVENTS = [
    {'id': 'fish_fest', 'name': '🎣 Фестиваль рыбы', 'desc': 'Продажа рыбы приносит +25%.', 'fish_sell': 1.25},
    {'id': 'hunt_season', 'name': '🏹 Охотничий сезон', 'desc': 'Продажа дичи приносит +25%.', 'hunt_sell': 1.25},
    {'id': 'business_week', 'name': '🏢 Золотая неделя бизнеса', 'desc': 'Прибыль обычных бизнесов +20%.', 'biz_income': 1.20},
    {'id': 'craft_fever', 'name': '🔨 Неделя крафта', 'desc': 'Крафт даёт двойной результат.', 'craft_mult': 2},
    {'id': 'quiet_market', 'name': '📉 Тихий рынок', 'desc': 'Прибыль бизнесов немного снижена: -10%.', 'biz_income': 0.90},
]

SEASON_LENGTH = 30 * 86400

def get_economic_event():
    root = db.setdefault('economic_event', {'id': None, 'started_at': 0})
    now = time.time()
    if not root.get('id') or now - float(root.get('started_at', 0) or 0) >= 6 * 3600:
        ev = random.choice(ECONOMIC_EVENTS)
        root['id'] = ev['id']
        root['started_at'] = now
        mark_dirty()
    return next((e for e in ECONOMIC_EVENTS if e['id'] == root.get('id')), ECONOMIC_EVENTS[0])

def season_rollover():
    # Awards and season reset are serialized with money mutations.
    with BALANCE_TX_LOCK:
        with db_lock:
            root = db.setdefault('season', {'number': 1, 'started_at': time.time(), 'archive': []})
            now = time.time()
            try:
                started_at = float(root.get('started_at', now) or now)
            except (TypeError, ValueError):
                started_at = now
            if now - started_at < SEASON_LENGTH:
                return
            old_number = int(root.get('number', 1) or 1)
            ranking = sorted(
                ((int(e.get('season_points', 0) or 0), e.get('user_id'), e.get('display_name', 'Игрок'))
                 for e in list(db.get('economy', {}).values()) if isinstance(e, dict) and e.get('user_id')),
                reverse=True
            )[:10]
            root.setdefault('archive', []).append({'number': old_number, 'top': ranking, 'ended_at': now})
            root['archive'] = root['archive'][-10:]
            root['number'] = old_number + 1
            root['started_at'] = now
            for e in list(db.get('economy', {}).values()):
                if isinstance(e, dict):
                    e['season_points'] = 0
                    e['season_claimed'] = False
            rewards = [15000, 9000, 5000]
            for idx, row in enumerate(ranking[:3]):
                uid = row[1]
                if uid:
                    target = _get_user_econ_unlocked(uid, row[2])
                    target['balance'] = int(target.get('balance', 0) or 0) + rewards[idx]
            mark_dirty()

def add_season_points(econ, points):
    season_rollover()
    with db_lock:
        econ['season_points'] = int(econ.get('season_points', 0) or 0) + max(0, int(points))
        mark_dirty()

def total_resources(econ):
    fish = sum(int(v or 0) for v in econ.get('fish_inventory', {}).values())
    hunt = sum(int(v or 0) for v in econ.get('hunt_inventory', {}).values())
    return fish, hunt

def _take_any_resources(inv, amount):
    left = int(amount)
    if left <= 0:
        return True
    for name, count in list(inv.items()):
        take = min(left, int(count or 0))
        if take:
            inv[name] = int(count) - take
            if inv[name] <= 0:
                inv.pop(name, None)
            left -= take
        if left <= 0:
            break
    return left <= 0

def craft_item(econ, recipe_id):
    recipe = CRAFT_RECIPES.get(recipe_id)
    if not recipe:
        return False, 'Рецепт не найден.'
    fish_need = int(recipe['need'].get('fish', 0))
    hunt_need = int(recipe['need'].get('hunt', 0))
    fish, hunt = total_resources(econ)
    if fish < fish_need or hunt < hunt_need:
        return False, f"❌ Нужно: 🐟 {fish_need}, 🏹 {hunt_need}. Сейчас: 🐟 {fish}, 🏹 {hunt}."
    if fish_need and not _take_any_resources(econ.setdefault('fish_inventory', {}), fish_need):
        return False, '❌ Не удалось списать рыбу.'
    if hunt_need and not _take_any_resources(econ.setdefault('hunt_inventory', {}), hunt_need):
        return False, '❌ Не удалось списать трофеи.'
    target_type, target_key, base_count = recipe['give']
    count = int(base_count)
    ev = get_economic_event()
    if ev.get('craft_mult'):
        count *= int(ev['craft_mult'])
    if target_type == 'backpack':
        econ.setdefault('backpack', {})[target_key] = econ.setdefault('backpack', {}).get(target_key, 0) + count
    econ.setdefault('crafted_items', {})[recipe_id] = econ.setdefault('crafted_items', {}).get(recipe_id, 0) + count
    add_season_points(econ, 10 * count)
    mark_dirty()
    return True, f"✅ Скрафчено: <b>{recipe['name']}</b> ×{count}!"

def render_resources_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    fish, hunt = total_resources(econ)
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(f'🐟 Рыба — {fish}', callback_data=f'resources_fish:{user_id}'),
        InlineKeyboardButton(f'🏹 Дичь — {hunt}', callback_data=f'resources_hunt:{user_id}')
    )
    markup.add(InlineKeyboardButton('🔨 Крафт', callback_data=f'resources_craft:{user_id}'))
    markup.add(InlineKeyboardButton('🎒 Рюкзак', callback_data=f'backpack_open:{user_id}'))
    text = (
        '📦 <b>РЕСУРСЫ</b> 😺\n━━━━━━━━━━━━━━━━━━━━\n'
        f'🐟 Рыбы: <b>{fish}</b>\n'
        f'🏹 Охотничьих трофеев: <b>{hunt}</b>\n\n'
        'Выберите раздел ниже. Здесь удобно собирать материалы для крафта. 🔨'
    )
    try:
        if message_id:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        else:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception as e:
        print(f'[RESOURCES VIEW ERROR] {e}')

def _render_resource_list(call, kind):
    econ = get_user_econ(call.from_user.id, call.from_user.first_name or 'Игрок')
    data = econ.get('fish_inventory', {}) if kind == 'fish' else econ.get('hunt_inventory', {})
    catalog = FISH_TYPES if kind == 'fish' else HUNT_TYPES
    emoji_title = '🐟 РЫБА' if kind == 'fish' else '🏹 ДИЧЬ'
    lines = [f'<b>{emoji_title}</b>', '━━━━━━━━━━━━━━━━━━━━']
    total = 0
    for name, rarity, price, _ in catalog:
        count = int(data.get(name, 0) or 0)
        if count:
            lines.append(f'• {html.escape(name)} × <b>{count}</b> — {rarity} — {price} 🪙')
            total += count
    if not total:
        lines.append('Пока пусто. 😿')
    lines += ['━━━━━━━━━━━━━━━━━━━━', f'Всего: <b>{total}</b>']
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton('🔨 Крафт', callback_data=f'resources_craft:{call.from_user.id}'))
    markup.add(InlineKeyboardButton('🔙 Ресурсы', callback_data=f'resources_main:{call.from_user.id}'))
    bot.edit_message_text('\n'.join(lines), chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')

def render_craft_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    fish, hunt = total_resources(econ)
    ev = get_economic_event()
    lines = ['🔨 <b>КРАФТ</b> 😺', '━━━━━━━━━━━━━━━━━━━━', f'🐟 Рыба: <b>{fish}</b> | 🏹 Дичь: <b>{hunt}</b>', f'🌍 Событие: <b>{ev["name"]}</b> — {ev["desc"]}', '']
    markup = InlineKeyboardMarkup(row_width=1)
    for rid, recipe in CRAFT_RECIPES.items():
        lines.append(f'• <b>{recipe["name"]}</b> — {recipe["desc"]}')
        markup.add(InlineKeyboardButton(f'🔨 Скрафтить: {recipe["name"]}', callback_data=f'craft_{rid}:{user_id}'))
    markup.add(InlineKeyboardButton('🔙 Ресурсы', callback_data=f'resources_main:{user_id}'))
    text = '\n'.join(lines)
    if message_id:
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

def _guild_code():
    guilds = db.setdefault('guilds', {})
    while True:
        code = f'NYA-{random.randint(1000, 9999)}'
        if code not in guilds:
            return code

def get_user_guild(econ):
    with db_lock:
        gid = econ.get('guild_id')
        guilds = db.get('guilds', {})
        if gid and isinstance(guilds, dict) and gid in guilds:
            return guilds[gid]
        if gid:
            econ['guild_id'] = None
            mark_dirty()
        return None

def render_guild_view(chat_id, user_id, user_name, message_id=None):
    econ = get_user_econ(user_id, user_name)
    guild = get_user_guild(econ)
    markup = InlineKeyboardMarkup(row_width=2)
    if not guild:
        markup.add(InlineKeyboardButton('📜 Список гильдий', callback_data=f'guild_list:{user_id}'))
        text = '🏰 <b>ГИЛЬДИИ</b>\n━━━━━━━━━━━━━━━━━━━━\nВы пока не состоите в гильдии.\n\nСоздание: <code>/guild создать Название</code>\nВступление: <code>/guild вступить NYA-1234</code>'
    else:
        gid = econ.get('guild_id')
        members = guild.get('members', [])
        owner = guild.get('owner_id') == user_id
        text = (
            f'🏰 <b>{html.escape(guild.get("name", "Гильдия"))}</b> <code>{gid}</code>\n'
            '━━━━━━━━━━━━━━━━━━━━\n'
            f'👑 Владелец: <code>{guild.get("owner_id")}</code>\n'
            f'👥 Участников: <b>{len(members)}/30</b>\n'
            f'💰 Казна: <b>{guild.get("bank", 0):,} 🪙</b>\n'
            f'⭐ Уровень: <b>{1 + int(guild.get("exp", 0)) // 1000}</b>\n'
        )
        if owner:
            markup.add(InlineKeyboardButton('💰 Положить 1000 🪙', callback_data=f'guild_deposit:{user_id}'))
            markup.add(InlineKeyboardButton('🗑 Распустить', callback_data=f'guild_disband:{user_id}'))
        else:
            markup.add(InlineKeyboardButton('🚪 Выйти', callback_data=f'guild_leave:{user_id}'))
        markup.add(InlineKeyboardButton('🔄 Обновить', callback_data=f'guild_view:{user_id}'))
    try:
        if message_id:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
        else:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception as e:
        print(f'[GUILD VIEW ERROR] {e}')

def cmd_guild(message):
    if not can_process_user_message(message): return
    uid = message.from_user.id
    name = (f'{message.from_user.first_name or ""} {message.from_user.last_name or ""}').strip() or message.from_user.username or 'Игрок'
    econ = get_user_econ(uid, name, username=message.from_user.username)
    args = message.text.split(maxsplit=2)[1:] if message.text else []
    if not args:
        render_guild_view(message.chat.id, uid, name)
        return
    action = args[0].lower()
    if action in ('создать', 'create') and len(args) >= 2:
        gname = args[1][:32].strip()
        if len(gname) < 2:
            bot.reply_to(message, '❌ Название слишком короткое.'); return
        with GUILD_LOCK:
            econ = get_user_econ(uid, name, username=message.from_user.username)
            if econ.get('guild_id'):
                bot.reply_to(message, '❌ Вы уже состоите в гильдии.'); return
            if econ.get('balance', 0) < 5000:
                bot.reply_to(message, '❌ Создание гильдии стоит 5,000 🪙.'); return
            gid = _guild_code()
            guilds = db.setdefault('guilds', {})
            while gid in guilds:
                gid = _guild_code()
            guilds[gid] = {'name': gname, 'owner_id': uid, 'members': [uid], 'bank': 0, 'exp': 0, 'created_at': time.time()}
            _adjust_balance(econ, -(5000))
            econ['guild_id'] = gid
            mark_dirty()
        bot.reply_to(message, f'🏰 Гильдия <b>{gname}</b> создана!\nКод: <code>{gid}</code>', parse_mode='HTML')
        return
    if action in ('вступить', 'join') and len(args) >= 2:
        gid = args[1].upper()
        with GUILD_LOCK:
            econ = get_user_econ(uid, name, username=message.from_user.username)
            if econ.get('guild_id'):
                bot.reply_to(message, '❌ Вы уже состоите в гильдии.'); return
            guild = db.setdefault('guilds', {}).get(gid)
            if not guild:
                bot.reply_to(message, '❌ Гильдия не найдена.'); return
            members = guild.setdefault('members', [])
            if len(members) >= 30:
                bot.reply_to(message, '❌ В гильдии уже 30 участников.'); return
            if uid in members:
                econ['guild_id'] = gid
                mark_dirty()
            else:
                members.append(uid)
                econ['guild_id'] = gid
                guild['exp'] = int(guild.get('exp', 0)) + 25
                mark_dirty()
        bot.reply_to(message, f'✅ Вы вступили в <b>{html.escape(guild.get("name", "Гильдию"))}</b>!', parse_mode='HTML')
        return
    bot.reply_to(message, 'Формат: <code>/guild</code>, <code>/guild создать Название</code> или <code>/guild вступить NYA-1234</code>.', parse_mode='HTML')

def render_player_market(chat_id, user_id, user_name, message_id=None):
    listings = db.setdefault('player_market', {})
    now = time.time()
    # Просроченное объявление возвращает товар продавцу, а не сжигает его.
    with PLAYER_MARKET_LOCK:
        for lid, item in list(listings.items()):
            try:
                expired = now - float(item.get('created_at', now)) > 86400
            except (TypeError, ValueError):
                expired = True
            if not expired:
                continue
            seller_id = item.get('seller_id')
            kind = item.get('kind')
            item_name = item.get('item_name')
            qty = max(1, int(item.get('qty', 1) or 1))
            if seller_id and item_name and kind in ('fish', 'hunt'):
                seller = get_user_econ(user_id=int(seller_id), user_tag=item.get('seller_name', 'Игрок'))
                inv_key = 'fish_inventory' if kind == 'fish' else 'hunt_inventory'
                inv = seller.setdefault(inv_key, {})
                inv[item_name] = int(inv.get(item_name, 0) or 0) + qty
            listings.pop(lid, None)
            mark_dirty()
    lines = ['🛒 <b>РЫНОК ИГРОКОВ</b>', '━━━━━━━━━━━━━━━━━━━━']
    markup = InlineKeyboardMarkup(row_width=1)
    visible = 0
    for lid, item in list(listings.items())[:20]:
        visible += 1
        lines.append(f'#{lid} • {html.escape(item["name"])} ×{item["qty"]} — <b>{item["price"]:,} 🪙</b>\n👤 {html.escape(item.get("seller_name", "Игрок"))}')
        if int(item.get('seller_id', 0)) != user_id:
            markup.add(InlineKeyboardButton(f'🛒 Купить #{lid} — {item["price"]:,} 🪙', callback_data=f'pmarket_buy_{lid}:{user_id}'))
    if not visible:
        lines.append('Пока объявлений нет. 😿')
    lines += ['', 'Продажа: <code>/pmarket sell fish 1 500</code>', '<i>1 — номер ресурса из списка /resources.</i>']
    markup.add(InlineKeyboardButton('🔄 Обновить', callback_data=f'pmarket_view:{user_id}'))
    text = '\n'.join(lines)
    if message_id:
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

def cmd_player_market(message):
    if not can_process_user_message(message): return
    uid = message.from_user.id
    name = (f'{message.from_user.first_name or ""} {message.from_user.last_name or ""}').strip() or message.from_user.username or 'Игрок'
    econ = get_user_econ(uid, name, username=message.from_user.username)
    args = message.text.split() if message.text else []
    if len(args) == 1:
        render_player_market(message.chat.id, uid, name); return
    if len(args) >= 5 and args[1].lower() == 'sell':
        kind = args[2].lower()
        try:
            idx = int(args[3]) - 1
            total_price = int(args[4])
        except ValueError:
            bot.reply_to(message, '❌ Формат: <code>/pmarket sell fish 1 500</code>', parse_mode='HTML'); return
        catalog = FISH_TYPES if kind == 'fish' else HUNT_TYPES if kind == 'hunt' else None
        inv = econ.get('fish_inventory', {}) if kind == 'fish' else econ.get('hunt_inventory', {}) if kind == 'hunt' else None
        if catalog is None or not (0 <= idx < len(catalog)) or total_price <= 0:
            bot.reply_to(message, '❌ Укажи fish/hunt, номер ресурса и цену.'); return
        item_name = catalog[idx][0]
        with PLAYER_MARKET_LOCK:
            if int(inv.get(item_name, 0) or 0) <= 0:
                bot.reply_to(message, '❌ У вас нет этого ресурса. Откройте /resources.'); return
            lid = str(random.randint(100000, 999999))
            while lid in db.setdefault('player_market', {}): lid = str(random.randint(100000, 999999))
            inv[item_name] -= 1
            if inv[item_name] <= 0: inv.pop(item_name, None)
            db['player_market'][lid] = {'seller_id': uid, 'seller_name': name, 'kind': kind, 'item_name': item_name, 'name': item_name, 'qty': 1, 'price': total_price, 'created_at': time.time()}
            mark_dirty()
        bot.reply_to(message, f'🛒 Объявление <code>#{lid}</code> создано: {html.escape(item_name)} за <b>{total_price:,} 🪙</b>.', parse_mode='HTML')
        return
    bot.reply_to(message, 'Формат: <code>/pmarket</code> или <code>/pmarket sell fish 1 500</code>.', parse_mode='HTML')

def render_raid(chat_id, user_id, user_name, message_id=None):
    raid = db.setdefault('raid', {})
    now = time.time()
    active = raid.get('active') and float(raid.get('ends_at', 0)) > now
    markup = InlineKeyboardMarkup(row_width=2)
    if not active:
        text = '🐉 <b>РЕЙД НА БОССА</b>\n━━━━━━━━━━━━━━━━━━━━\nСейчас босса нет. Создайте рейд за 1,000 🪙 и зовите участников!'
        markup.add(InlineKeyboardButton('🐉 Создать рейд — 1,000 🪙', callback_data=f'raid_start:{user_id}'))
    else:
        hp = max(0, int(raid.get('hp', 0)))
        max_hp = max(1, int(raid.get('max_hp', 1)))
        participants = raid.get('participants', {})
        text = (
            '🐉 <b>МИРОВОЙ БОСС</b>\n━━━━━━━━━━━━━━━━━━━━\n'
            f'👹 {html.escape(raid.get("name", "Босс"))}\n'
            f'❤️ HP: <b>{hp:,}/{max_hp:,}</b>\n'
            f'👥 Участников: <b>{len(participants)}</b>\n'
            f'⏳ Осталось: <b>{_fmt_duration(max(0, float(raid.get("ends_at", 0)) - time.time()))}</b>\n'
        )
        markup.add(InlineKeyboardButton('⚔️ Атаковать', callback_data=f'raid_attack:{user_id}'))
        markup.add(InlineKeyboardButton('🔄 Обновить', callback_data=f'raid_view:{user_id}'))
        if user_id in [int(x) for x in participants.keys()]:
            dmg = int(participants.get(str(user_id), 0))
            text += f'\n💥 Ваш урон: <b>{dmg:,}</b>'
    if message_id:
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

def cmd_raid(message):
    if not can_process_user_message(message): return
    uid = message.from_user.id
    name = (f'{message.from_user.first_name or ""} {message.from_user.last_name or ""}').strip() or message.from_user.username or 'Игрок'
    render_raid(message.chat.id, uid, name)


def render_season(chat_id, user_id, user_name, message_id=None):
    season_rollover()
    root = db.setdefault('season', {'number': 1, 'started_at': time.time(), 'archive': []})
    with db_lock:
        economy_snapshot = list(db.get('economy', {}).values())
    rows = sorted(((int(e.get('season_points', 0) or 0), e.get('display_name', 'Игрок'), e.get('user_id')) for e in economy_snapshot if isinstance(e, dict) and e.get('user_id')), reverse=True)[:10]
    lines = [f'🏆 <b>СЕЗОН {root.get("number", 1)}</b>', '━━━━━━━━━━━━━━━━━━━━']
    me = get_user_econ(user_id, user_name)
    lines.append(f'⭐ Ваш рейтинг: <b>{me.get("season_points", 0)}</b>')
    for i, (pts, nm, uid) in enumerate(rows, 1):
        lines.append(f'{i}. {html.escape(str(nm))} — <b>{pts}</b>')
    lines.append('━━━━━━━━━━━━━━━━━━━━')
    lines.append('🥇 15,000 🪙 • 🥈 9,000 🪙 • 🥉 5,000 🪙 в конце сезона.')
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton('🔄 Обновить', callback_data=f'season_view:{user_id}'))
    text = '\n'.join(lines)
    if message_id:
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

def cmd_season(message):
    if not can_process_user_message(message): return
    uid = message.from_user.id
    name = (f'{message.from_user.first_name or ""} {message.from_user.last_name or ""}').strip() or message.from_user.username or 'Игрок'
    render_season(message.chat.id, uid, name)

def cmd_collection(message):
    if not can_process_user_message(message): return
    uid = message.from_user.id
    name = (f'{message.from_user.first_name or ""} {message.from_user.last_name or ""}').strip() or message.from_user.username or 'Игрок'
    econ = get_user_econ(uid, name, username=message.from_user.username)
    fish, hunt = total_resources(econ)
    cosmetics = len(set(econ.get('inventory', []))) + len(set(econ.get('titles', []))) + len(set(econ.get('profile_gifs', [])))
    text = f'📚 <b>КОЛЛЕКЦИЯ</b>\n━━━━━━━━━━━━━━━━━━━━\n🐟 Рыба: <b>{fish}</b>\n🏹 Дичь: <b>{hunt}</b>\n✨ Косметика: <b>{cosmetics}</b>\n🏆 Достижения: <b>{len(econ.get("achievements", []))}/{len(ACHIEVEMENTS)}</b>'
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton('🐟 Рыба', callback_data=f'resources_fish:{uid}'), InlineKeyboardButton('🏹 Дичь', callback_data=f'resources_hunt:{uid}'))
    markup.add(InlineKeyboardButton('🔨 Крафт', callback_data=f'resources_craft:{uid}'))
    bot.reply_to(message, text, reply_markup=markup, parse_mode='HTML')

def cmd_world(message):
    if not can_process_user_message(message): return
    text = ('🗺 <b>МИР NYA</b>\n━━━━━━━━━━━━━━━━━━━━\n'
            '🏙 Ня-Сити — экономика, бизнес и рынок\n'
            '🌊 Лунное озеро — рыбалка и редкая рыба\n'
            '🌲 Дикий лес — охота и трофеи\n'
            '🏰 Крепость — гильдии\n'
            '🐉 Долина дракона — мировые рейды\n'
            '🎪 Площадь — сезонные события и мини-игры\n\n'
            'Путешествия пока работают как игровые разделы: используйте кнопки меню ниже.')
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton('🏢 Бизнес', callback_data=f'world_business:{message.from_user.id}'), InlineKeyboardButton('🎣 Озеро', callback_data=f'world_fish:{message.from_user.id}'))
    markup.add(InlineKeyboardButton('🏹 Лес', callback_data=f'world_hunt:{message.from_user.id}'), InlineKeyboardButton('🐉 Рейд', callback_data=f'world_raid:{message.from_user.id}'))
    bot.reply_to(message, text, reply_markup=markup, parse_mode='HTML')




# ---------------------------------------------------------
# ОБРАБОТЧИКИ ОПЛАТЫ TELEGRAM STARS (PRE-CHECKOUT & SUCCESS)
# ---------------------------------------------------------
def validate_stars_payload(payload, amount, buyer_id, currency='XTR'):
    try:
        if str(payload or '').startswith('tgift:'):
            token=str(payload).split(':',1)[1]
            order=db.setdefault('tgift_orders',{}).get(token)
            if not order or float(order.get('expires_at',0) or 0)<time.time():
                return False, 'Счёт подарка истёк.'
            if int(order.get('buyer_id',0) or 0)!=int(buyer_id):
                return False, 'Плательщик не совпадает с заказом.'
            if int(order.get('amount',0) or 0)!=int(amount):
                return False, 'Неверная сумма подарка.'
            if not order.get('gift_id') or int(order.get('target_id',0) or 0)<=0:
                return False, 'Повреждённый заказ подарка.'
            return True, ''
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
            if not item and gift_kind == 'cosm': item = STARS_LIMITED_ITEMS.get(item_key)
            if not item:
                return False, 'Товар подарка не найден.'
            if gift_kind == 'cosm' and item_key in STARS_HARD_LIMITED_ITEMS and stars_hard_limited_available(item_key) <= 0:
                return False, 'Лимит этого предмета уже исчерпан (5/5).';
            if int(amount) != int(item['stars']):
                return False, 'Неверная сумма товара.'
            try:
                target_id = int(target_raw); payload_buyer = int(payload_buyer_raw)
            except ValueError:
                return False, 'Некорректный пользователь в подарке.'
            if payload_buyer != int(buyer_id):
                return False, 'Плательщик не совпадает с владельцем счёта.'
            if target_id <= 0 or target_id == payload_buyer:
                return False, 'Некорректный или совпадающий получатель.'
            target_econ = get_user_econ(user_id=target_id)
            if gift_kind == 'pass':
                err = stars_purchase_error(target_econ, 'vippass', item_key)
                if err: return False, 'Получатель уже владеет этим VIP.'
            elif gift_kind == 'cosm':
                if item_key == 'bp_premium' and target_econ.get('bp_premium'): return False, 'Получатель уже владеет Премиум Pass.'
                if item_key == 'custom_title' and target_econ.get('has_custom_title_cert'): return False, 'Получатель уже владеет сертификатом.'
                if item_key == 'pet_griffin' and 'pet_griffin' in target_econ.get('paid_stars_items', []): return False, 'Получатель уже владеет Грифоном.'
                if item_key in STARS_COSMETICS or item_key in STARS_LIMITED_ITEMS:
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
            item_key = key.replace('cosm_', '')
            item = STARS_COSMETICS.get(item_key) or STARS_LIMITED_ITEMS.get(item_key)
            expected = item.get('stars') if item else None
            payload_buyer = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            # GIF профиля также являются одноразовой Stars-косметикой и проверяются выше/ниже через stars_item_owned.
        elif key.startswith('bpprem_'):
            expected = STARS_COSMETICS.get('bp_premium', {}).get('stars')
            payload_buyer = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            # Не разрешаем даже выставлять новый счёт за вечный Pass, если он уже есть.
            if payload_buyer is not None:
                buyer_econ = get_user_econ(user_id=payload_buyer)
                if buyer_econ.get('bp_premium'):
                    return False, 'Премиум Pass уже куплен.'
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
        return True, ''
    except Exception:
        return False, 'Некорректный платёжный payload.'


def mark_stars_charge_processed(charge_id):
    if not charge_id:
        return
    processed = db.setdefault('processed_stars_charges', [])
    if charge_id in processed:
        return
    processed.append(charge_id)
    if len(processed) > 10000:
        del processed[:-10000]
    mark_dirty()


# Stars service takeover: payment handlers below keep their public names/signatures.
stars_item_owned = stars_service.stars_item_owned
stars_purchase_error = stars_service.stars_purchase_error
grant_hard_limited_stars_item = stars_service.grant_hard_limited_stars_item
validate_stars_payload = stars_service.validate_stars_payload
start_stars_payment_journal = stars_service.start_stars_payment_journal
update_stars_payment_journal = stars_service.update_stars_payment_journal
mark_stars_charge_refunded = stars_service.mark_stars_charge_refunded
_mark_stars_charge_processed_service = stars_service.mark_stars_charge_processed

def mark_stars_charge_processed(charge_id):
    return _mark_stars_charge_processed_service(charge_id)

# ---------------------------------------------------------
# РЕГИСТРАЦИЯ ВЫНЕСЕННЫХ HANDLERS
# ---------------------------------------------------------
register_handlers(globals())

# ---------------------------------------------------------
# ЗАПУСК ПРИЛОЖЕНИЯ
# ---------------------------------------------------------
def run_bot():
    """Initialize runtime workers and start Telegram long polling.

    Importing this module no longer starts the bot. This lets bot.py own the
    process lifecycle and makes the module safe to import for tests/tools.
    """
    # bot.py owns the Neon singleton lock. Do not acquire it a second time here.
    recovered = recover_stars_entitlements_from_journal()
    if recovered and db_dirty:
        critical_save('Stars entitlement recovery', retries=3)
    setup_bot_commands()
    start_background_threads()
    keep_alive()
    print('Бот успешно запущен со всеми обновлениями и исправлениями! 😸')
    bot.infinity_polling()


def get_application():
    """Return the Flask application and Telegram bot for integrations/tests."""
    return app, bot


if __name__ == '__main__':
    # Direct execution remains supported for emergency/manual local runs.
    run_bot()
