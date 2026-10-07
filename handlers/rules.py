"""Lightweight data-driven fun rules/law interactions."""
from __future__ import annotations

import re

from services.rules import game_sentence, random_law

HANDLER_NAMES = ['cmd_law_joke']

_TRIGGER_PHRASES = {
    'под что я попал',
    'какой закон я нарушил',
    'какой закон я нарушаю',
    'что я нарушил',
    'какой закон мне попался',
    'мой закон',
}


def _normalize(text):
    text = str(text or '').casefold().strip()
    text = re.sub(r'[!?.,:;]+$', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def is_law_trigger(message):
    text = _normalize(getattr(message, 'text', ''))
    if not text:
        return False
    if text in _TRIGGER_PHRASES:
        return True
    return text in {'/law', '/закон', '/законы', '/приговор'}


def cmd_law_joke(message):
    if not can_process_user_message(message):
        return
    user_id = int(message.from_user.id)
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton('🇺🇦 Украина', callback_data=f'law_country:UA:{user_id}'),
        InlineKeyboardButton('🇷🇺 Россия', callback_data=f'law_country:RU:{user_id}'),
    )
    bot.reply_to(
        message,
        '⚖️ <b>НЯ-СУД</b> 😼\n\n'
        'Выберите страну, по законам которой вас сегодня будут судить:',
        reply_markup=markup,
        parse_mode='HTML',
    )


def register(ctx, only=None):
    _inject(ctx)
    bot = ctx['bot']
    wanted = set(only) if only is not None else set(HANDLER_NAMES)
    registered = []
    if 'cmd_law_joke' in wanted:
        _handler = cmd_law_joke
        bot.message_handler(content_types=['text'], func=is_law_trigger)(_handler)
        ctx['cmd_law_joke'] = _handler
        globals()['cmd_law_joke'] = _handler
        registered.append('cmd_law_joke')
    return registered


def _inject(ctx):
    for _name, _value in ctx.items():
        if _name not in {'__name__', '__package__', '__loader__', '__spec__', '__cached__', '__builtins__'}:
            globals()[_name] = _value
