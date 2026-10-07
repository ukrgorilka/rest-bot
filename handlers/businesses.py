"""Extracted Telegram handlers for staged NyaBot architecture.

The handlers keep their original function bodies. During migration, register(ctx)
receives the legacy newfile.py globals so business logic and shared state remain
unchanged.
"""

from __future__ import annotations

import copy


def _inject(ctx):
    for _name, _value in ctx.items():
        if _name not in {"__name__", "__package__", "__loader__", "__spec__", "__cached__", "__builtins__"}:
            globals()[_name] = _value


HANDLER_NAMES = ['cmd_business', 'cmd_miner', 'cmd_collect']


def cmd_business(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    parts=(message.text or '').strip().split()
    number=None
    if len(parts) >= 2 and parts[1].isdigit():
        number=int(parts[1])
    if number is not None:
        render_business_detail(message.chat.id,user_id,user_name,number)
    else:
        render_business_view(message.chat.id, user_id, user_name)

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
            "💻 <b>КРИПТО-ФЕРМА</b> 😺\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Крипто-Ферма — это обычный пассивный бизнес. Она приносит <b>Ня-коины 🪙</b> как предприятие; отдельного автоматического майнинга NYA в портфель здесь нет.\n"
            "\nНажмите кнопку ниже, чтобы купить её. 😻\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        bot.reply_to(message, text, reply_markup=markup, parse_mode='HTML')
        return

    lvl = _business_level(econ, 'crypto_farm')
    market = get_market_data()
    nya_price = market.get('NYA', {}).get('price', 120.0)
    pending = _business_pending_amount(econ, 'crypto_farm', time.time())

    markup = InlineKeyboardMarkup()
    if lvl < 5:
        upg_cost = BUSINESSES['crypto_farm']['upgrade_cost'] * lvl
        markup.add(InlineKeyboardButton(f"⬆️ Улучшить видеокарты (ур. {lvl+1}) — {upg_cost:,} 🪙", callback_data=f"upg_biz_crypto_farm:{user_id}"))
    markup.add(InlineKeyboardButton("💰 Собрать прибыль с фермы", callback_data=f"collect_biz_profit:{user_id}"))
    markup.add(InlineKeyboardButton("🏢 Открыть все бизнесы", callback_data=f"business_refresh:{user_id}"))

    text = (
        f"💻 <b>КРИПТО-ФЕРМА (УРОВЕНЬ {lvl}/5)</b> 😺\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Владелец: {make_link(message.chat.id, user_name, user_id, ping=False)}\n"
        f"⚡️ Хешрейт: <b>{lvl * 145} MH/s</b>\n"
        f"💵 Доходность: <b>{_business_hourly_income('crypto_farm', lvl):,} 🪙/ч</b>\n"
        f"💰 Накоплено: <b>~{pending:,} 🪙</b>\n"
        f"📈 Курс NYA: <b>{nya_price:.2f} 🪙</b> (информационный)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 Прибыль фермы собирается вместе с остальными бизнесами."
    )
    bot.reply_to(message, text, reply_markup=markup, parse_mode='HTML')

def cmd_collect(message):
    if not can_process_user_message(message):
        return
    user_id = message.from_user.id
    user_name = (f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}").strip() or message.from_user.username
    econ = get_user_econ(user_id, user_name, username=message.from_user.username)

    if not (econ.get('businesses') or econ.get('donor_businesses')):
        bot.reply_to(message, "❌ У вас нет купленных бизнесов! Откройте <code>/business</code> и нажмите «Купить» напротив нужного предприятия. 😾", parse_mode='HTML')
        return

    now = time.time()
    base_profit = collect_business_base_profit(econ, now)
    if base_profit <= 0:
        bot.reply_to(message, "⏳ Пока накопилось меньше 1 🪙. Подождите немного! 😿")
        return

    state_before = copy.deepcopy(econ)
    total_profit, event_text = _apply_business_payout_modifiers(econ, base_profit, message.chat.id, user_id, user_name)
    _adjust_balance(econ, total_profit)
    mark_dirty()
    if not critical_save('business profit collection command', retries=3):
        econ.clear(); econ.update(state_before); mark_dirty()
        bot.reply_to(message, "❌ Не удалось сохранить прибыль в Neon. Начисление отменено.")
        return
    bot.reply_to(message, f"💰 Собрана прибыль предприятий: <b>+{total_profit:,} Ня-коинов 🪙</b>!{event_text}\nБаланс: <b>{econ['balance']:,} 🪙</b> 😸", parse_mode='HTML')

def register(ctx, only=None):
    """Register selected handlers from this feature module."""
    _inject(ctx)
    bot = ctx["bot"]
    wanted = set(only) if only is not None else set(HANDLER_NAMES)
    registered = []
    if "cmd_business" in wanted:
        _handler = cmd_business
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['business', 'бизнес', 'бизнесы', 'biz'])(_handler)
        ctx["cmd_business"] = _handler
        globals()["cmd_business"] = _handler
        registered.append("cmd_business")
    if "cmd_miner" in wanted:
        _handler = cmd_miner
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['miner', 'майнер', 'майнинг', 'ферма'])(_handler)
        ctx["cmd_miner"] = _handler
        globals()["cmd_miner"] = _handler
        registered.append("cmd_miner")
    if "cmd_collect" in wanted:
        _handler = cmd_collect
        _handler = serialize_user_action(_handler)
        bot.message_handler(commands=['collect', 'прибыль'])(_handler)
        ctx["cmd_collect"] = _handler
        globals()["cmd_collect"] = _handler
        registered.append("cmd_collect")
    return registered
