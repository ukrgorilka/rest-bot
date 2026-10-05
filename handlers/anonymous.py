"""Anonymous inline whispers and real Telegram Gifts."""
from __future__ import annotations
import html
import re
import secrets
import time


def _inject(ctx):
    for k,v in ctx.items():
        if k not in {"__name__","__package__","__loader__","__spec__","__cached__","__builtins__"}:
            globals()[k]=v

HANDLER_NAMES=['cmd_gifttg','handle_anonymous_inline','handle_tgift_state','handle_anonymous_callbacks']


def _state(uid):
    return db.setdefault('tgift_states',{}).setdefault(str(uid),{})


def _clear_state(uid):
    db.setdefault('tgift_states',{}).pop(str(uid),None)
    mark_dirty()


def _gift_list():
    result = bot.get_available_gifts()
    gifts = getattr(result, 'gifts', None) if result is not None else None
    available = []
    for gift in list(gifts or []):
        # Do not show gifts that Telegram currently cannot send from this bot.
        if bool(getattr(gift, 'is_burned', False)):
            continue
        if bool(getattr(gift, 'is_premium', False)):
            continue
        remaining = getattr(gift, 'remaining_count', None)
        if remaining is not None and int(remaining) <= 0:
            continue
        personal_remaining = getattr(gift, 'personal_remaining_count', None)
        if personal_remaining is not None and int(personal_remaining) <= 0:
            continue
        available.append(gift)
    return available


def _gift_fields(g):
    gid=str(getattr(g,'id',''))
    stars=int(getattr(g,'star_count',0) or 0)
    sticker=getattr(g,'sticker',None)
    emoji=getattr(sticker,'emoji',None) or '🎁'
    return gid,stars,emoji


def _resolve_recipient(raw):
    raw=raw.strip()
    if raw.startswith('@'):
        username=raw[1:].strip().lower()
        # Telegram Bot API does not reliably resolve arbitrary user usernames
        # through getChat; use the bot's own observed-user index first.
        for item in db.get('economy', {}).values():
            if not isinstance(item, dict):
                continue
            if str(item.get('username') or '').lstrip('@').lower() == username and item.get('user_id'):
                uid=int(item['user_id'])
                return uid, (item.get('display_name') or username), username
        for item in db.get('started_users', {}).values():
            if not isinstance(item, dict):
                continue
            if str(item.get('username') or '').lstrip('@').lower() == username:
                try:
                    uid=int(next(k for k,v in db.get('started_users', {}).items() if v is item))
                except Exception:
                    continue
                return uid, (item.get('display_name') or username), username
        return None,None,username
    if raw.isdigit():
        uid=int(raw)
        try:
            econ=get_user_econ(user_id=uid)
            name=econ.get('display_name') or f'ID:{uid}'
            return uid,name,econ.get('username')
        except Exception:
            return None,None,raw
    return None,None,raw


def _recipient_started(uid):
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return False
    marker = db.setdefault('started_users', {}).get(str(uid))
    if isinstance(marker, dict) and marker.get('started') is True:
        return True
    try:
        chat=bot.get_chat(uid)
        if getattr(chat,'type','') != 'private':
            return False
        try:
            record_started_user(uid, getattr(chat, 'username', None), getattr(chat, 'first_name', None))
        except Exception:
            pass
        return True
    except Exception:
        return False


def handle_anonymous_inline(inline_query):
    try:
        query=(inline_query.query or '').strip()
        m=re.search(r'\s+@([A-Za-z0-9_]{3,32})$',query)
        if not m:
            bot.answer_inline_query(inline_query.id,[],cache_time=0,is_personal=True,button=telebot.types.InlineQueryResultsButton(text='Формат: текст @username',start_parameter='inline_help'))
            return
        username=m.group(1)
        secret=query[:m.start()].strip()
        if not secret or len(secret)>2000:
            bot.answer_inline_query(inline_query.id,[],cache_time=0,is_personal=True)
            return
        # Username must resolve to a real user known to Telegram. This also prevents
        # an arbitrary mention from becoming an unreadable dead whisper.
        target_id,target_name,_=_resolve_recipient('@'+username)
        if not target_id:
            bot.answer_inline_query(inline_query.id,[],cache_time=0,is_personal=True,button=telebot.types.InlineQueryResultsButton(text='Получатель не найден',start_parameter='inline_help'))
            return
        token=secrets.token_urlsafe(18).replace('-','').replace('_','')[:28]
        db.setdefault('anonymous_messages',{})[token]={
            'recipient_id':int(target_id),'recipient_username':username,'recipient_name':str(target_name or username),
            'text':secret,'created_at':time.time(),'sender_id':int(inline_query.from_user.id),
            'expires_at':time.time()+7*86400
        }
        mark_dirty()
        mention=f'<a href="tg://user?id={int(target_id)}">@{html.escape(username)}</a>'
        content=telebot.types.InputTextMessageContent(
            f'🔒 <b>Это сообщение было отправлено анонимно</b> {mention}',
            parse_mode='HTML'
        )
        markup=telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton('🔐 Прочитать содержимое',callback_data=f'anonread:{token}'))
        result=telebot.types.InlineQueryResultArticle(
            id=token,title='📨 Отправить анонимно',description=f'Получатель: @{username}',
            input_message_content=content,reply_markup=markup
        )
        bot.answer_inline_query(inline_query.id,[result],cache_time=0,is_personal=True)
    except Exception as e:
        print(f'[ANON INLINE ERROR] {e}')
        try: bot.answer_inline_query(inline_query.id,[],cache_time=0,is_personal=True)
        except Exception: pass


def cmd_gifttg(message):
    if not can_process_user_message(message): return
    try:
        record_started_user(message.from_user.id, getattr(message.from_user, 'username', None), getattr(message.from_user, 'first_name', None))
    except Exception:
        pass
    if getattr(message.chat,'type','')!='private':
        bot.reply_to(message,'🎁 /gifttg нужно использовать в личных сообщениях с ботом.')
        return
    try: gifts=_gift_list()
    except Exception as e:
        print(f'[TG GIFT LIST ERROR] {e}'); bot.reply_to(message,'❌ Не удалось получить каталог Telegram Gifts. Попробуйте позже.'); return
    if not gifts:
        bot.reply_to(message,'❌ Сейчас нет доступных Telegram Gifts для отправки.')
        return
    rows=[]
    for g in gifts:
        gid,stars,emoji=_gift_fields(g)
        if not gid or stars<=0: continue
        personal_remaining=getattr(g,'personal_remaining_count',None)
        if personal_remaining is not None and int(personal_remaining)<=0: continue
        rows.append((gid,stars,emoji))
    if not rows:
        bot.reply_to(message,'❌ Сейчас нет доступных Gifts.')
        return
    st=_state(message.from_user.id); st.clear(); st['step']='gift'; st['buyer_id']=int(message.from_user.id); mark_dirty()
    kb=telebot.types.InlineKeyboardMarkup(row_width=2)
    for gid,stars,emoji in rows[:40]:
        kb.add(telebot.types.InlineKeyboardButton(f'{emoji} {stars+1} ⭐️',callback_data=f'tgift_pick:{gid}'))
    kb.add(telebot.types.InlineKeyboardButton('❌ Отмена',callback_data='tgift_cancel'))
    bot.send_message(message.chat.id,'🎁 <b>TELEGRAM GIFTS</b>\n\nВыберите подарок. Цена для оплаты через бота: цена подарка + 1 ⭐️.',reply_markup=kb,parse_mode='HTML')


def handle_tgift_state(message):
    if not message or not getattr(message,'from_user',None) or getattr(message.chat,'type','')!='private': return
    try:
        record_started_user(message.from_user.id, getattr(message.from_user, 'username', None), getattr(message.from_user, 'first_name', None))
    except Exception:
        pass
    st=db.setdefault('tgift_states',{}).get(str(message.from_user.id))
    if not st or st.get('step') not in ('target','text'): return
    text=(message.text or '').strip()
    if not text: return
    if text.lower() in ('отмена','cancel','нет'):
        _clear_state(message.from_user.id); bot.reply_to(message,'❌ Отменено.'); return
    if st['step']=='target':
        uid,name,username=_resolve_recipient(text)
        if not uid:
            bot.reply_to(message,'❌ Не удалось найти пользователя. Укажи @username или Telegram ID.'); return
        if uid==message.from_user.id:
            bot.reply_to(message,'❌ Нельзя отправить подарок самому себе.'); return
        if not _recipient_started(uid):
            _clear_state(message.from_user.id); bot.reply_to(message,'❌ Извините, но этот человек не запустил бота. Мы не можем отправить ему подарок.'); return
        st['target_id']=uid; st['target_name']=name or username or f'ID:{uid}'; st['target_username']=username; st['step']='target_confirm'; mark_dirty()
        kb=telebot.types.InlineKeyboardMarkup(); kb.add(telebot.types.InlineKeyboardButton('❌ Нет',callback_data='tgift_target_no'),telebot.types.InlineKeyboardButton('✅ Да',callback_data='tgift_target_yes'))
        bot.send_message(message.chat.id,f'У человека, которому вы хотите отправить подарок, username/ID: <b>{html.escape(str(st["target_name"]))}</b>?',reply_markup=kb,parse_mode='HTML'); return
    if st['step']=='text':
        if len(text)>128:
            bot.reply_to(message,'❌ Текст подарка не должен превышать 128 символов.'); return
        st['gift_text']=text; st['step']='text_confirm'; mark_dirty()
        kb=telebot.types.InlineKeyboardMarkup(); kb.add(telebot.types.InlineKeyboardButton('❌ Нет, переписать',callback_data='tgift_text_no'),telebot.types.InlineKeyboardButton('✅ Да',callback_data='tgift_text_yes'))
        bot.send_message(message.chat.id,f'📝 Текст подарка:\n\n<blockquote>{html.escape(text)}</blockquote>\n\nВсё правильно?',reply_markup=kb,parse_mode='HTML'); return


def _send_invoice_for_state(call):
    uid=call.from_user.id; st=db.setdefault('tgift_states',{}).get(str(uid)) or {}
    gid=st.get('gift_id'); target=int(st.get('target_id',0) or 0); text=str(st.get('gift_text',''))[:128]
    if not gid or target<=0 or not _recipient_started(target):
        _clear_state(uid); bot.answer_callback_query(call.id,'❌ Получатель больше недоступен.',show_alert=True); return
    try:
        gift=next((g for g in _gift_list() if str(getattr(g,'id',''))==str(gid)),None)
        if not gift: raise RuntimeError('Gift недоступен')
        base=int(getattr(gift,'star_count',0) or 0); amount=base+1
        if amount<=1: raise RuntimeError('Некорректная цена')
        token=secrets.token_urlsafe(18).replace('-','').replace('_','')[:28]
        db.setdefault('tgift_orders',{})[token]={'buyer_id':uid,'target_id':target,'gift_id':str(gid),'text':text,'amount':amount,'created_at':time.time(),'expires_at':time.time()+15*60}
        _clear_state(uid)
        bot.send_invoice(call.message.chat.id,'Telegram Gift',f'Подарок {getattr(getattr(gift,"sticker",None),"emoji",None) or "🎁"} для {st.get("target_name",target)}',f'tgift:{token}','', 'XTR',[telebot.types.LabeledPrice('Telegram Gift',amount)])
        bot.answer_callback_query(call.id,'💳 Открываю оплату…')
    except Exception as e:
        print(f'[TG GIFT INVOICE ERROR] {e}'); bot.answer_callback_query(call.id,'❌ Не удалось создать оплату.',show_alert=True)


def handle_anonymous_callbacks(call):
    data=str(getattr(call,'data','') or '')
    uid=int(call.from_user.id)
    if data.startswith('anonread:'):
        token=data.split(':',1)[1]; item=db.setdefault('anonymous_messages',{}).get(token)
        if not item or float(item.get('expires_at',0) or 0)<time.time():
            bot.answer_callback_query(call.id,'❌ Сообщение истекло.',show_alert=True); return True
        if int(item.get('recipient_id',0))!=uid:
            bot.answer_callback_query(call.id,'🔒 Это сообщение предназначено другому пользователю.',show_alert=True); return True
        # Inline-mode callback queries may contain only inline_message_id and no
        # call.message. The secret itself remains recipient-only; the button can
        # only be pressed from the inline message shown in the group.
        callback_message = getattr(call, 'message', None)
        if callback_message is not None and getattr(callback_message, 'chat', None) is not None:
            if getattr(callback_message.chat,'type','') in ('group','supergroup'):
                try:
                    m=bot.get_chat_member(callback_message.chat.id,uid)
                    if getattr(m,'status','') in ('left','kicked'):
                        bot.answer_callback_query(call.id,'❌ Получатель не состоит в этой группе.',show_alert=True); return True
                except Exception:
                    bot.answer_callback_query(call.id,'❌ Не удалось подтвердить участие в группе.',show_alert=True); return True
        bot.answer_callback_query(call.id,item.get('text',''),show_alert=True)
        return True
    if data=='tgift_cancel': _clear_state(uid); bot.answer_callback_query(call.id,'Отменено.'); return True
    st=db.setdefault('tgift_states',{}).get(str(uid))
    if not st: return False
    if data=='tgift_target_no':
        st['step']='target'; st.pop('target_id',None); mark_dirty(); bot.answer_callback_query(call.id,'Введите username или ID заново.'); bot.send_message(call.message.chat.id,'👤 Укажите получателя: @username или Telegram ID.'); return True
    if data=='tgift_target_yes':
        st['step']='text'; mark_dirty(); bot.answer_callback_query(call.id); bot.send_message(call.message.chat.id,'📝 Напишите текст для подарка (до 128 символов).'); return True
    if data=='tgift_text_no':
        st['step']='text'; st.pop('gift_text',None); mark_dirty(); bot.answer_callback_query(call.id,'Введите текст заново.'); bot.send_message(call.message.chat.id,'📝 Напишите новый текст (до 128 символов).'); return True
    if data=='tgift_text_yes':
        _send_invoice_for_state(call); return True
    if data.startswith('tgift_pick:'):
        gid=data.split(':',1)[1]
        try:
            gift=next((g for g in _gift_list() if str(getattr(g,'id',''))==gid),None)
            if not gift: raise RuntimeError()
            st['gift_id']=gid; st['step']='target'; mark_dirty(); bot.answer_callback_query(call.id,'Подарок выбран.'); bot.send_message(call.message.chat.id,f'🎁 Выбрано: {getattr(getattr(gift,"sticker",None),"emoji",None) or "🎁"} за {int(getattr(gift,"star_count",0) or 0)+1} ⭐️\n\n👤 Укажите username или ID получателя.'); return True
        except Exception:
            bot.answer_callback_query(call.id,'❌ Подарок больше недоступен.',show_alert=True); return True
    return False


def register(ctx, only=None):
    _inject(ctx); bot=ctx['bot']; wanted=set(only) if only is not None else set(HANDLER_NAMES); registered=[]
    if 'cmd_gifttg' in wanted:
        _handler=cmd_gifttg
        _handler=serialize_user_action(_handler)
        bot.message_handler(commands=['gifttg'])(_handler)
        ctx['cmd_gifttg']=_handler; globals()['cmd_gifttg']=_handler; registered.append('cmd_gifttg')
    if 'handle_anonymous_inline' in wanted:
        bot.inline_handler(func=lambda q: True)(handle_anonymous_inline); ctx['handle_anonymous_inline']=handle_anonymous_inline; globals()['handle_anonymous_inline']=handle_anonymous_inline; registered.append('handle_anonymous_inline')
    if 'handle_tgift_state' in wanted:
        _handler=serialize_user_action(handle_tgift_state)
        bot.message_handler(func=lambda m: bool(getattr(m,'from_user',None)) and getattr(getattr(m,'chat',None),'type','')=='private' and str(getattr(m,'from_user',None).id) in db.setdefault('tgift_states',{}))(_handler)
        ctx['handle_tgift_state']=_handler; globals()['handle_tgift_state']=_handler; registered.append('handle_tgift_state')
    if 'handle_anonymous_callbacks' in wanted:
        _handler=serialize_user_action(handle_anonymous_callbacks)
        bot.callback_query_handler(func=lambda c: str(getattr(c,'data','') or '').startswith(('anonread:','tgift_')))(_handler)
        ctx['handle_anonymous_callbacks']=_handler; globals()['handle_anonymous_callbacks']=_handler; registered.append('handle_anonymous_callbacks')
    return registered
