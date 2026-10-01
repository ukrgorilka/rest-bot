"""Extracted Telegram handlers for staged NyaBot architecture.

The handlers keep their original function bodies. During migration, register(ctx)
receives the legacy newfile.py globals so business logic and shared state remain
unchanged.
"""

from __future__ import annotations


def _inject(ctx):
    for _name, _value in ctx.items():
        if _name not in {"__name__", "__package__", "__loader__", "__spec__", "__cached__", "__builtins__"}:
            globals()[_name] = _value


HANDLER_NAMES = ['callback_inline', 'process_stars_pre_checkout', 'process_stars_successful_payment']


def callback_inline(call):
    try:
        if not call or not getattr(call, 'from_user', None) or not getattr(call, 'message', None):
            return
        try:
            cb_uid = int(call.from_user.id)
            cb_lang = _bot_output_language(call.message.chat.id, cb_uid)
            with _CALLBACK_LANG_LOCK:
                now_locale = time.time()
                stale = [k for k, v in _CALLBACK_LANG_BY_ID.items() if now_locale - float(v[1]) > 300]
                for k in stale:
                    _CALLBACK_LANG_BY_ID.pop(k, None)
                _CALLBACK_LANG_BY_ID[str(call.id)] = (cb_lang, now_locale)
            _LOCALE_CONTEXT.user_id = cb_uid
            _LOCALE_CONTEXT.chat_id = int(call.message.chat.id)
        except Exception:
            pass
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        user_username = (call.from_user.username or '').lower()
        user_name = (f"{call.from_user.first_name or ''} {call.from_user.last_name or ''}").strip() or call.from_user.username or 'Пользователь'
        now_ts = time.time()

        if is_chat_banned(chat_id):
            bot.answer_callback_query(call.id, "❌ Работа бота в этом чате запрещена!", show_alert=True)
            return

        flood_key = f"{chat_id}:{user_id}"
        user_hist = [t for t in user_flood_history.get(flood_key, []) if now_ts - t <= 2.0]
        user_hist.append(now_ts)
        user_flood_history[flood_key] = user_hist
        if len(user_hist) >= 5:
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
            if action_data == 'toggle_flood_admins':
                if not is_chat_owner(chat_id, user_id):
                    bot.answer_callback_query(call.id, "❌ Лимит антифлуда для админов может менять только владелец чата!", show_alert=True)
                    return
            elif action_data in ['set_max_days', 'set_remind_time', 'toggle_rp', 'toggle_flood', 'toggle_reactions', 'toggle_welcome']:
                if not is_admin(chat_id, user_id):
                    bot.answer_callback_query(call.id, "❌ Настройки доступны только администраторам!", show_alert=True)
                    return
            else:
                bot.answer_callback_query(call.id, "❌ Это меню открыто другим пользователем!", show_alert=True)
                return


        if action_data == 'toggle_admin_functions':
            if not is_chat_owner(chat_id, user_id):
                bot.answer_callback_query(call.id, '❌ Только владелец чата может менять эту настройку.', show_alert=True); return
            sett=get_chat_settings(chat_id); sett['admin_functions_enabled']=not sett.get('admin_functions_enabled',True); mark_dirty()
            render_settings_view(chat_id,user_id,call.message.message_id); bot.answer_callback_query(call.id, '👮 Настройка изменена.'); return

        if action_data == 'profile_stats':
            econ=get_user_econ(user_id,user_name,username=user_username); st=econ.get('msg_stats',{}) or {}
            text=(f"📊 <b>СТАТИСТИКА</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                  f"🗓 День: <b>{st.get('day_count',0)}</b>\n📅 Неделя: <b>{st.get('week_count',0)}</b>\n🗓 Месяц: <b>{st.get('month_count',0)}</b>\n♾ Всё время: <b>{st.get('total_count',0)}</b>\n\n"
                  f"🎮 Игр Mini App: <b>{econ.get('mini_games_played',0)}</b>\n🏆 Побед Mini App: <b>{econ.get('mini_games_wins',0)}</b>")
            bot.edit_message_text(text,chat_id=chat_id,message_id=call.message.message_id,parse_mode='HTML',reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton('🔙 Профиль',callback_data=f'ps_back_profile:{user_id}')))
            bot.answer_callback_query(call.id); return

        if action_data == 'profile_rating':
            rows=[]
            for uid,e in db.get('economy',{}).items():
                if isinstance(e,dict): rows.append((int(e.get('account_exp',0) or 0),clean_tag(e.get('name') or e.get('tag') or uid)))
            rows.sort(reverse=True); lines=['🏆 <b>РЕЙТИНГ ПО XP</b>','━━━━━━━━━━━━━━━━━━━━']
            for i,(xp,nm) in enumerate(rows[:10],1): lines.append(f'<b>{i}.</b> {html.escape(nm)} — {xp:,} XP')
            bot.edit_message_text('\n'.join(lines),chat_id=chat_id,message_id=call.message.message_id,parse_mode='HTML',reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton('🔙 Профиль',callback_data=f'ps_back_profile:{user_id}')))
            bot.answer_callback_query(call.id); return

        if action_data == 'profile_bonus':
            econ=get_user_econ(user_id,user_name,username=user_username)
            bot.edit_message_text(f"🎁 <b>БОНУСЫ</b>\n━━━━━━━━━━━━━━━━━━━━\n🔥 Серия: <b>{econ.get('bonus_streak',0)} дн.</b>\n🎁 Ежедневный бонус: команда <code>/chest</code>\n📋 Задания: <code>/tasks</code>",chat_id=chat_id,message_id=call.message.message_id,parse_mode='HTML',reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton('🔙 Профиль',callback_data=f'ps_back_profile:{user_id}')))
            bot.answer_callback_query(call.id); return

        if action_data == 'profile_notifications':
            bot.edit_message_text("🔔 <b>УВЕДОМЛЕНИЯ</b>\n━━━━━━━━━━━━━━━━━━━━\nНастройки уведомлений чата находятся в <code>/settings</code>.\nЗдесь профиль не перегружается лишними переключателями.",chat_id=chat_id,message_id=call.message.message_id,parse_mode='HTML',reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton('🔙 Профиль',callback_data=f'ps_back_profile:{user_id}')))
            bot.answer_callback_query(call.id); return

        if action_data == 'profile_account':
            econ=get_user_econ(user_id,user_name,username=user_username); lvl,exp,nxt,bar=get_account_level(econ.get('account_exp',0))
            bot.edit_message_text(f"👤 <b>ЦЕНТР АККАУНТА</b>\n━━━━━━━━━━━━━━━━━━━━\n🆔 ID: <code>{user_id}</code>\n⭐ Уровень: <b>{lvl}</b>\n📈 XP: <b>{exp}/{nxt}</b>\n{bar}\n🪙 Баланс: <b>{econ.get('balance',0):,}</b>\n⭐ Stars поддержки: <b>{econ.get('stars_donated',0)}</b>",chat_id=chat_id,message_id=call.message.message_id,parse_mode='HTML',reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton('🔙 Профиль',callback_data=f'ps_back_profile:{user_id}')))
            bot.answer_callback_query(call.id); return


        # МЕМЫ: ГОЛОСОВАНИЕ
        if action_data.startswith('meme_l_') or action_data.startswith('meme_d_'):
            meme_id = action_data[7:]
            meme = active_memes.get(meme_id)
            if not meme:
                bot.answer_callback_query(call.id, "❌ Мем устарел!", show_alert=True)
                return
            is_like = action_data.startswith('meme_l_')
            ok_vote, vote_msg = record_meme_vote(meme_id, user_id, is_like)
            if not ok_vote:
                bot.answer_callback_query(call.id, vote_msg, show_alert=True)
                return
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton(f"🔥 {len(meme['likes'])}", callback_data=f"meme_l_{meme_id}"),
                InlineKeyboardButton(f"💩 {len(meme['dislikes'])}", callback_data=f"meme_d_{meme_id}")
            )
            try: bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup)
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            bot.answer_callback_query(call.id, "Ваш голос учтён! 😸")
            return

        # СЕМЕЙНЫЙ ДОМ: КНОПКИ
        elif action_data.startswith('buy_house_'):
            h_k = action_data.replace('buy_house_', '')
            if h_k in FAMILY_HOUSES:
                h_info = FAMILY_HOUSES[h_k]
                econ = get_user_econ(user_id, user_name, username=user_username)
                m = econ.get('marriage')
                if not m:
                    bot.answer_callback_query(call.id, "❌ Только для пар в браке!", show_alert=True)
                    return
                if econ['balance'] < h_info['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {h_info['price']:,} 🪙! 😿", show_alert=True)
                    return
                _adjust_balance(econ, -(h_info['price']))
                m['house'] = h_k
                m['furniture'] = []
                m['last_house_calc'] = time.time()
                p_econ = get_user_econ(m.get('partner_id'))
                if p_econ.get('marriage'):
                    p_econ['marriage']['house'] = h_k
                    p_econ['marriage']['furniture'] = []
                    p_econ['marriage']['last_house_calc'] = time.time()
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Вы приобрели {h_info['name']}! 😻", show_alert=True)
                render_house_view(chat_id, user_id, user_name, message_id=call.message.message_id)
            return

        elif action_data.startswith('buy_furn_'):
            f_k = action_data.replace('buy_furn_', '')
            if f_k in FAMILY_FURNITURE:
                f_info = FAMILY_FURNITURE[f_k]
                econ = get_user_econ(user_id, user_name, username=user_username)
                m = econ.get('marriage')
                if not m: return
                furn_list = m.setdefault('furniture', [])
                if f_k in furn_list:
                    bot.answer_callback_query(call.id, "❌ Этот предмет мебели уже куплен!", show_alert=True)
                    return
                if econ['balance'] < f_info['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {f_info['price']:,} 🪙! 😿", show_alert=True)
                    return
                _adjust_balance(econ, -(f_info['price']))
                furn_list.append(f_k)
                p_econ = get_user_econ(m.get('partner_id'))
                if p_econ.get('marriage'):
                    p_econ['marriage'].setdefault('furniture', []).append(f_k)
                mark_dirty()
                bot.answer_callback_query(call.id, f"🛋 Куплена мебель: {f_info['name']}! 😻", show_alert=True)
                render_house_view(chat_id, user_id, user_name, message_id=call.message.message_id)
            return

        elif action_data == 'house_refresh':
            render_house_view(chat_id, user_id, user_name, message_id=call.message.message_id)
            bot.answer_callback_query(call.id, "Статус дома обновлен! 😸")
            return

        # САД: НЕСКОЛЬКО ГРЯДОК
        elif action_data.startswith('water_slot_') or action_data.startswith('fertilize_slot_') or action_data.startswith('harvest_slot_') or action_data.startswith('uproot_slot_'):
            m=re.match(r'(water|fertilize|harvest|uproot)_slot_(\d+)$',action_data)
            if not m: return
            idx=int(m.group(2)); econ=get_user_econ(user_id,user_name,username=user_username); slots=econ.get('garden') or []
            if not isinstance(slots,list): slots=[slots]
            if idx<0 or idx>=len(slots): bot.answer_callback_query(call.id,'Грядка уже исчезла.',show_alert=True); return
            g=slots[idx]; seed=GARDEN_SEEDS.get(g.get('seed'))
            if not seed: return
            if m.group(1)=='water':
                with TRANSFER_LOCK:
                    live=get_user_econ(user_id,user_name,username=user_username)
                    live_slots=live.get('garden') or []
                    if not isinstance(live_slots,list): live_slots=[live_slots]
                    if idx<0 or idx>=len(live_slots): bot.answer_callback_query(call.id,'Грядка уже исчезла.',show_alert=True); return
                    live_g=live_slots[idx]; live_seed=GARDEN_SEEDS.get(live_g.get('seed'))
                    if not live_seed: return
                    if int(live.get('balance',0) or 0)<15: bot.answer_callback_query(call.id,'Нужно 15 🪙!',show_alert=True); return
                    if int(live_g.get('water_count',0) or 0)>=live_seed['water_req']: bot.answer_callback_query(call.id,'Земля уже достаточно влажная.',show_alert=True); return
                    _set_balance(live, int(live.get('balance',0) or 0)-15)
                    live_g['water_count']=int(live_g.get('water_count',0) or 0)+1
                    live_g['last_dry_calc']=time.time()
                    mark_dirty()
                bot.answer_callback_query(call.id,'💦 Полито! -15 🪙'); render_garden_view(chat_id,user_id,user_name,call.message.message_id); return
            if m.group(1)=='fertilize':
                bp=econ.setdefault('backpack', {})
                fert=int(bp.get('garden_fertilizer',0) or 0); used=int(g.get('fertilizer_used',0) or 0)
                if fert<=0: bot.answer_callback_query(call.id,'Нет удобрения. Купите его в магазине!',show_alert=True); return
                if used>=3: bot.answer_callback_query(call.id,'Для этой грядки уже использовано максимум 3 удобрения!',show_alert=True); return
                bp['garden_fertilizer']=fert-1; g['fertilizer_used']=used+1
                g['planted_at']=float(g.get('planted_at',time.time()))-seed['grow_time']*0.10
                mark_dirty(); bot.answer_callback_query(call.id,'🧪 Грядка удобрена! Рост ускорен на 10%! 😻'); render_garden_view(chat_id,user_id,user_name,call.message.message_id); return
            if m.group(1)=='harvest':
                if time.time()-g.get('planted_at',time.time())<seed['grow_time'] or g.get('water_count',0)<seed['water_req']:
                    bot.answer_callback_query(call.id,'❌ Растение ещё не готово или ему не хватило воды.',show_alert=True); return
                reward=random.randint(seed['reward_min'],seed['reward_max']); reward=int(reward*(1+0.10*pet_bonus(econ,'garden_bonus'))); _adjust_balance(econ, reward); slots.pop(idx); econ['garden']=slots; mark_dirty(); bot.answer_callback_query(call.id,f'🧺 Урожай: +{reward} 🪙',show_alert=True); render_garden_view(chat_id,user_id,user_name,call.message.message_id); return
            # uproot
            slots.pop(idx); econ['garden']=slots; mark_dirty(); bot.answer_callback_query(call.id,'❌ Растение выкорчевано.',show_alert=True); render_garden_view(chat_id,user_id,user_name,call.message.message_id); return

        # ПУБЛИЧНЫЕ БИЗНЕСЫ / ОДЕЖДА / ДОМА / МОНОПОЛИЯ
        elif action_data == 'pubbiz_view':
            render_public_business_view(chat_id,user_id,user_name,call.message.message_id); bot.answer_callback_query(call.id); return
        elif action_data == 'pubbiz_jobs':
            render_public_jobs(chat_id,user_id,user_name,call.message.message_id); bot.answer_callback_query(call.id); return
        elif action_data.startswith('pubbiz_create_'):
            b_id=action_data.replace('pubbiz_create_','')
            econ=get_user_econ(user_id,user_name,username=user_username)
            if econ.get('public_business'):
                bot.answer_callback_query(call.id,'У вас уже есть публичный бизнес!',show_alert=True); return
            if b_id not in BUSINESSES: return
            price=max(3000,BUSINESSES[b_id]['price']*2)
            if econ['balance']<price:
                bot.answer_callback_query(call.id,f'Нужно {price:,} 🪙!',show_alert=True); return
            _adjust_balance(econ, -(price))
            creation_now=time.time(); econ['public_business']={'name':BUSINESSES[b_id]['name'],'salary_per_worker':max(100,BUSINESSES[b_id]['base_income']*20),'created_at':creation_now,'last_salary':creation_now}
            econ['public_business_workers']=[]
            mark_dirty(); bot.answer_callback_query(call.id,'🏢 Публичный бизнес создан!'); render_public_business_view(chat_id,user_id,user_name,call.message.message_id); return
        elif action_data.startswith('pubbiz_join_'):
            owner_id=int(action_data.replace('pubbiz_join_',''))
            if owner_id==user_id: return
            owner=get_user_econ(owner_id)
            pb=owner.get('public_business')
            workers=owner.setdefault('public_business_workers',[])
            if not pb or len(workers)>=5:
                bot.answer_callback_query(call.id,'❌ Вакансия уже закрыта!',show_alert=True); return
            if any(w.get('id')==user_id for w in workers):
                bot.answer_callback_query(call.id,'Вы уже работаете здесь.',show_alert=True); return
            my=get_user_econ(user_id,user_name,username=user_username)
            old=my.get('employer_salary')
            if old and old.get('owner_id'):
                old_owner=get_user_econ(int(old.get('owner_id')))
                old_workers=old_owner.get('public_business_workers',[])
                still_employed=any(int(w.get('id',0) or 0)==user_id for w in old_workers)
                if not still_employed:
                    my['employer_salary']=None; old=None
                elif int(old.get('owner_id'))!=owner_id:
                    bot.answer_callback_query(call.id,'❌ Вы уже работаете в другом публичном бизнесе!',show_alert=True); return
            workers.append({'id':user_id,'name':user_name,'joined_at':time.time()})
            my['employer_salary']={'owner_id':owner_id,'joined_at':time.time(),'next_due':time.time()+3*86400,'business_name':pb.get('name','Бизнес')}
            mark_dirty(); bot.answer_callback_query(call.id,'💼 Вы устроились на работу! Зарплата будет доступна через 3 дня.'); render_public_jobs(chat_id,user_id,user_name,call.message.message_id); return
        elif action_data == 'pubbiz_pay':
            econ=get_user_econ(user_id,user_name,username=user_username); pb=econ.get('public_business'); workers=econ.get('public_business_workers',[])
            if not pb or not workers:
                bot.answer_callback_query(call.id, '❌ Некому выплачивать зарплату.', show_alert=True); return
            now = time.time()
            if now-float(pb.get('last_salary',0) or 0)<3*86400:
                left=cooldown_text(pb.get('last_salary',0),3*86400,econ); bot.answer_callback_query(call.id,f'⏳ Следующая выплата через {left}.',show_alert=True); return
            eligible=[]
            for w in list(workers):
                wid=w.get('id')
                if not wid: continue
                we=get_user_econ(wid,w.get('name','Игрок'))
                es=we.get('employer_salary') or {}
                if float(es.get('next_due', now+3*86400) or now+3*86400) <= now:
                    eligible.append((w,we,es))
            if not eligible:
                due_times=[]
                for w in workers:
                    wid=w.get('id')
                    if not wid:
                        continue
                    we=get_user_econ(wid,w.get('name','Игрок'))
                    due_times.append(max(now, float((we.get('employer_salary') or {}).get('next_due', now+3*86400) or now+3*86400)))
                left=max(0.0, (min(due_times) if due_times else now+3*86400) - now)
                bot.answer_callback_query(call.id,f'⏳ Зарплата ещё не готова. Ближайшая выплата через {_fmt_duration(left)}.',show_alert=True)
                return
            bonus=1+pet_bonus(econ,'business_bonus')+get_title_business_bonus(econ)+get_vip_business_bonus(econ)
            salary_each=max(1,int(pb.get('salary_per_worker',100)*bonus))
            gross=salary_each*len(eligible)
            profit=max(1,int(gross*0.25))
            with TRANSFER_LOCK:
                owner=get_user_econ(user_id,user_name,username=user_username)
                if owner.get('balance',0)<gross:
                    bot.answer_callback_query(call.id,f'❌ Для выплаты выбранным сотрудникам нужно {gross:,} 🪙. У вас: {owner.get("balance",0):,} 🪙.',show_alert=True); return
                _adjust_balance(owner, -(gross))
                paid=0
                for w,we,es in eligible:
                    _adjust_balance(we, salary_each)
                    es['next_due']=now+3*86400
                    we['employer_salary']=es
                    paid += salary_each
                _adjust_balance(owner, profit)
                pb=owner.get('public_business') or pb
                pb['last_salary']=now
                owner['public_business']=pb
                mark_dirty()
            bot.answer_callback_query(call.id,f'💰 Зарплаты выплачены: {paid:,} 🪙. Ваша чистая прибыль: +{profit:,} 🪙.',show_alert=True); render_public_business_view(chat_id,user_id,user_name,call.message.message_id); return
        elif action_data == 'pubbiz_workers':
            econ=get_user_econ(user_id,user_name,username=user_username); workers=econ.get('public_business_workers',[])
            if not econ.get('public_business'):
                bot.answer_callback_query(call.id,'Публичного бизнеса нет.',show_alert=True); return
            kb=InlineKeyboardMarkup(row_width=1)
            for w in workers:
                wid=int(w.get('id',0) or 0); kb.add(InlineKeyboardButton(f"❌ Уволить {str(w.get('name','Игрок'))[:30]}",callback_data=f'pubbiz_fire_{wid}:{user_id}'))
            kb.add(InlineKeyboardButton('🔙 Назад',callback_data=f'pubbiz_view:{user_id}'))
            bot.edit_message_text('👥 <b>СОТРУДНИКИ</b>\n\nВыберите сотрудника для увольнения.',chat_id=chat_id,message_id=call.message.message_id,reply_markup=kb,parse_mode='HTML'); bot.answer_callback_query(call.id); return
        elif action_data.startswith('pubbiz_fire_'):
            target=int(action_data.replace('pubbiz_fire_','')); econ=get_user_econ(user_id,user_name,username=user_username); workers=econ.get('public_business_workers',[])
            found=next((w for w in workers if int(w.get('id',0) or 0)==target),None)
            if not found: bot.answer_callback_query(call.id,'Сотрудник уже отсутствует.',show_alert=True); return
            workers.remove(found); we=get_user_econ(target,found.get('name','Игрок'))
            if int((we.get('employer_salary') or {}).get('owner_id',0) or 0)==user_id: we['employer_salary']=None
            mark_dirty(); bot.answer_callback_query(call.id,'Сотрудник уволен.'); render_public_business_view(chat_id,user_id,user_name,call.message.message_id); return
        elif action_data == 'pubbiz_quit':
            econ=get_user_econ(user_id,user_name,username=user_username)
            if econ.get('public_business'):
                for w in econ.get('public_business_workers',[]):
                    we=get_user_econ(int(w.get('id',0) or 0),w.get('name','Игрок')); we['employer_salary']=None
                econ['public_business']=None; econ['public_business_workers']=[]; mark_dirty(); bot.answer_callback_query(call.id,'🏢 Бизнес закрыт.'); render_public_business_view(chat_id,user_id,user_name,call.message.message_id); return
            bot.answer_callback_query(call.id,'Публичного бизнеса нет.',show_alert=True); return
        elif action_data == 'pubbiz_change':
            econ=get_user_econ(user_id,user_name,username=user_username)
            if not econ.get('public_business'): bot.answer_callback_query(call.id,'Сначала создайте бизнес.',show_alert=True); return
            kb=InlineKeyboardMarkup(row_width=1)
            for bid,b in BUSINESSES.items(): kb.add(InlineKeyboardButton(f"🏢 {b['short']}",callback_data=f'pubbiz_change_to_{bid}:{user_id}'))
            kb.add(InlineKeyboardButton('🔙 Назад',callback_data=f'pubbiz_view:{user_id}'))
            bot.edit_message_text('🔄 <b>СМЕНА ПУБЛИЧНОГО БИЗНЕСА</b>\n\nВыберите новый тип.',chat_id=chat_id,message_id=call.message.message_id,reply_markup=kb,parse_mode='HTML'); bot.answer_callback_query(call.id); return
        elif action_data.startswith('pubbiz_change_to_'):
            bid=action_data.replace('pubbiz_change_to_',''); econ=get_user_econ(user_id,user_name,username=user_username)
            if bid not in BUSINESSES or not econ.get('public_business'): return
            b=BUSINESSES[bid]; econ['public_business']['name']=b['name']; econ['public_business']['salary_per_worker']=max(100,b['base_income']*20); mark_dirty(); bot.answer_callback_query(call.id,'🔄 Бизнес изменён!'); render_public_business_view(chat_id,user_id,user_name,call.message.message_id); return
        elif action_data == 'pubbiz_leave':
            me=get_user_econ(user_id,user_name,username=user_username); es=me.get('employer_salary') or {}; owner_id=int(es.get('owner_id',0) or 0)
            if not owner_id: bot.answer_callback_query(call.id,'Вы нигде не работаете.',show_alert=True); return
            owner=get_user_econ(owner_id); owner['public_business_workers']=[w for w in owner.get('public_business_workers',[]) if int(w.get('id',0) or 0)!=user_id]; me['employer_salary']=None; mark_dirty(); bot.answer_callback_query(call.id,'🚪 Вы уволились.'); render_public_jobs(chat_id,user_id,user_name,call.message.message_id); return
        elif action_data == 'pet_clothes':
            render_pet_clothes(chat_id,user_id,user_name,call.message.message_id); bot.answer_callback_query(call.id); return
        elif action_data.startswith('petcloth_buy_'):
            k=action_data.replace('petcloth_buy_',''); v=PET_CLOTHES.get(k); econ=get_user_econ(user_id,user_name,username=user_username)
            if not v: return
            if not econ.get('pet'):
                bot.answer_callback_query(call.id,'❌ Сначала заведите питомца!',show_alert=True); return
            if k in econ.setdefault('pet_clothes',[]): bot.answer_callback_query(call.id,'Уже куплено!',show_alert=True); return
            if econ['balance']<v['price']: bot.answer_callback_query(call.id,f'Нужно {v["price"]:,} 🪙!',show_alert=True); return
            _adjust_balance(econ, -(v['price'])); econ['pet_clothes'].append(k); econ['equipped_pet_clothes']=k; mark_dirty(); bot.answer_callback_query(call.id,'👗 Одежда куплена и надета!'); render_pet_clothes(chat_id,user_id,user_name,call.message.message_id); return
        elif action_data.startswith('petcloth_equip_'):
            k=action_data.replace('petcloth_equip_',''); econ=get_user_econ(user_id,user_name,username=user_username)
            if k in econ.setdefault('pet_clothes',[]): econ['equipped_pet_clothes']=k; mark_dirty(); bot.answer_callback_query(call.id,'👗 Одежда надета!'); render_pet_clothes(chat_id,user_id,user_name,call.message.message_id)
            return
        elif action_data == 'garden_seeds':
            markup=InlineKeyboardMarkup(row_width=2)
            for k,v in GARDEN_SEEDS.items(): markup.add(InlineKeyboardButton(f"{v['emoji']} {v['price']} 🪙",callback_data=f"garden_buy_{k}:{user_id}"))
            bot.edit_message_text('🌱 <b>ВЫБЕРИТЕ РАСТЕНИЕ</b>',chat_id=chat_id,message_id=call.message.message_id,reply_markup=markup,parse_mode='HTML'); return
        elif action_data.startswith('garden_buy_'):
            k=action_data.replace('garden_buy_',''); v=GARDEN_SEEDS.get(k); econ=get_user_econ(user_id,user_name,username=user_username)
            slots=econ.get('garden') or []; slots=slots if isinstance(slots,list) else [slots]
            if len(slots)>=get_garden_capacity(econ): bot.answer_callback_query(call.id,'❌ Нет свободных грядок!',show_alert=True); return
            if not v or econ['balance']<v['price']: bot.answer_callback_query(call.id,'❌ Недостаточно коинов!',show_alert=True); return
            _adjust_balance(econ, -(v['price'])); slots.append({'seed':k,'planted_at':time.time(),'water_count':0,'last_dry_calc':time.time()}); econ['garden']=slots; mark_dirty(); bot.answer_callback_query(call.id,'🌱 Растение посажено!'); render_garden_view(chat_id,user_id,user_name,call.message.message_id); return
        elif action_data.startswith('home_buy_'):
            k=action_data.replace('home_buy_',''); h=PERSONAL_HOUSES.get(k); econ=get_user_econ(user_id,user_name,username=user_username)
            if not h or econ.get('home') or econ.get('home_installment'): return
            down=int(h['price']*0.25); remaining=h['price']-down; payment=max(1,remaining//8)
            if econ['balance']<down: bot.answer_callback_query(call.id,f'Первый взнос: {down:,} 🪙',show_alert=True); return
            _adjust_balance(econ, -(down)); econ['home_installment']={'id':k,'remaining':remaining,'payment':payment,'next_due':time.time()+2*86400,'down':down}; mark_dirty(); bot.answer_callback_query(call.id,'🏠 Дом оформлен в рассрочку!'); render_personal_home(chat_id,user_id,user_name,call.message.message_id); return
        elif action_data == 'home_pay':
            econ=get_user_econ(user_id,user_name,username=user_username); inst=econ.get('home_installment')
            if not inst: return
            if time.time()<inst.get('next_due',0): bot.answer_callback_query(call.id,'⏳ Следующий платёж ещё не наступил.',show_alert=True); return
            pay=min(inst['payment'],inst['remaining'])
            if econ['balance']<pay: bot.answer_callback_query(call.id,f'Нужно {pay:,} 🪙!',show_alert=True); return
            _adjust_balance(econ, -(pay)); inst['remaining']-=pay; inst['next_due']=time.time()+2*86400
            if inst['remaining']<=0: econ['home']={'id':inst['id'],'bought_at':time.time()}; econ['home_installment']=None
            mark_dirty(); bot.answer_callback_query(call.id,'💳 Платёж внесён!'); render_personal_home(chat_id,user_id,user_name,call.message.message_id); return
        # МОНОПОЛИЯ
        elif action_data.startswith('mono_'):
            gid=action_data.split(':',1)[1] if ':' in action_data else action_data.split('mono_',1)[1]
            game=active_monopoly.get(gid)
            if not game: bot.answer_callback_query(call.id,'Игра завершена.',show_alert=True); return
            uid=user_id
            if action_data.startswith('mono_join'):
                if game['started']: return
                if uid not in game['players'] and len(game['players'])<6: game['players'][uid]={'name':user_name,'money':30000,'pos':0}
                render_monopoly(chat_id,game,call.message.message_id); bot.answer_callback_query(call.id); return
            if action_data.startswith('mono_start'):
                if len(game['players'])<2: bot.answer_callback_query(call.id,'Нужно минимум 2 игрока.',show_alert=True); return
                game['started']=True; game['turn']=next(iter(game['players'])); render_monopoly(chat_id,game,call.message.message_id); bot.answer_callback_query(call.id,'Игра началась!'); return
            if not game.get('started') or uid!=game['turn']: bot.answer_callback_query(call.id,'Сейчас не ваш ход.',show_alert=True); return
            player=game['players'][uid]
            if action_data.startswith('mono_roll'):
                roll=random.randint(1,6); player['pos']=(player['pos']+roll)%len(MONOPOLY_BOARD); cell=MONOPOLY_BOARD[player['pos']]; owner=game['owners'].get(player['pos'])
                msg=f'🎲 Выпало {roll}: <b>{cell[0]}</b>'
                if owner and owner!=uid:
                    rent=cell[2]; player['money']-=rent; game['players'][owner]['money']+=rent; msg+=f'\n💸 Аренда: {rent:,} 🪙'
                bot.answer_callback_query(call.id,msg.replace('<b>','').replace('</b>',''),show_alert=True)
            elif action_data.startswith('mono_buy'):
                idx=player['pos']; cell=MONOPOLY_BOARD[idx]
                if idx==0 or idx in game['owners']: bot.answer_callback_query(call.id,'Эту клетку купить нельзя.',show_alert=True); return
                if player['money']<cell[1]: bot.answer_callback_query(call.id,'Недостаточно денег.',show_alert=True); return
                player['money']-=cell[1]; game['owners'][idx]=uid; bot.answer_callback_query(call.id,f'🏠 Куплено: {cell[0]}');
            elif action_data.startswith('mono_skip'):
                pass
            ids=list(game['players']); pos=ids.index(uid); game['turn']=ids[(pos+1)%len(ids)]; render_monopoly(chat_id,game,call.message.message_id); return

        # АПТЕКА: КНОПКИ
        elif action_data.startswith('buy_med_'):
            med_k = action_data.replace('buy_med_', '')
            if med_k in PHARMACY_ITEMS:
                med = PHARMACY_ITEMS[med_k]
                econ = get_user_econ(user_id, user_name, username=user_username)
                if econ['balance'] < med['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {med['price']} 🪙! 😿", show_alert=True)
                    return
                _adjust_balance(econ, -(med['price']))
                cur_d = econ.get('disease')
                if med['cure'] == 'all':
                    econ['disease'] = None
                    econ['disease_immunity_until'] = time.time() + 86400
                    bot.answer_callback_query(call.id, "🧪 Панацея Айболита исцелила от всего и дала иммунитет на 24 часа! 😻", show_alert=True)
                elif cur_d == med['cure']:
                    econ['disease'] = None
                    bot.answer_callback_query(call.id, f"✅ Вы выпили лекарство и полностью исцелились от {MEME_DISEASES[cur_d]['name']}! 😸", show_alert=True)
                else:
                    bot.answer_callback_query(call.id, f"💊 Препарат куплен, но у вас другой диагноз! 😸")
                mark_dirty()
                render_pharmacy_view(chat_id, user_id, user_name, message_id=call.message.message_id)
            return

        # ХЕЛЛОУИН BATTLE PASS: КНОПКИ
        elif action_data == 'claim_bp_rewards':
            econ = get_user_econ(user_id, user_name, username=user_username)
            bp_exp = econ.get('bp_exp', 0)
            lvl, _, _, _ = get_user_bp_level(bp_exp)
            is_prem = econ.get('bp_premium', False)
            claimed_free = econ.setdefault('bp_claimed_free', [])
            claimed_prem = econ.setdefault('bp_claimed_prem', [])

            free_gains = 0
            for l in range(1, lvl + 1):
                if l not in claimed_free:
                    claimed_free.append(l)
                    free_gains += 100 * l
                    milestone_free = {5: '🎃 Маленький фонарь', 10: '🕸 Паутинка', 25: '🦇 Летучая мышь'}
                    if l in milestone_free:
                        econ.setdefault('inventory', [])
                        if milestone_free[l] not in econ['inventory']:
                            econ['inventory'].append(milestone_free[l])
                    if l == 15 and '🎃' not in econ.get('inventory', []):
                        econ.setdefault('inventory', []).append('🎃')
                    if l == 30 and 'pumpkin_lord' not in econ.get('titles', []):
                        econ.setdefault('titles', []).append('pumpkin_lord')
                        econ['active_title'] = 'pumpkin_lord'

            prem_gains = 0
            if is_prem:
                for l in range(1, lvl + 1):
                    if l not in claimed_prem:
                        claimed_prem.append(l)
                        prem_gains += 350 * l
                        if l == 10:
                            econ.setdefault('inventory', [])
                            if '🎃 Премиум-тыква' not in econ['inventory']:
                                econ['inventory'].append('🎃 Премиум-тыква')
                        if l == 20:
                            p_info = PETS_DATA['pumpkin_cat']
                            activate_pet(econ, 'pumpkin_cat')
                        if l == 30:
                            p_th = econ.setdefault('purchased_themes', ['default'])
                            if 'halloween' not in p_th: p_th.append('halloween')
                            econ['profile_theme'] = 'halloween'

            tot_coins = free_gains + prem_gains
            _adjust_balance(econ, tot_coins)
            mark_dirty()
            if tot_coins > 0:
                bot.answer_callback_query(call.id, f"🎉 Награды получены: +{tot_coins:,} 🪙 и трофеи сезона! 😻", show_alert=True)
            else:
                bot.answer_callback_query(call.id, "Все доступные награды уже получены! Повышайте уровень BP. 😸", show_alert=True)
            render_halloween_bp_view(chat_id, user_id, user_name, message_id=call.message.message_id)
            return

        elif action_data == 'buy_bp_prem_stars':
            try:
                bot.send_invoice(
                    chat_id=chat_id,
                    title="🎃 Премиум Хеллоуинский Pass",
                    description="Доступ к премиум-ветке наград: Тыквокот, Тёмная тема, горы коинов!",
                    invoice_payload=f"bpprem_self:{user_id}:{int(time.time())}",
                    provider_token="",
                    currency="XTR",
                    prices=[LabeledPrice(label="Хеллоуин Pass", amount=STARS_COSMETICS['bp_premium']['stars'])]
                )
                bot.answer_callback_query(call.id, "⭐️ Счёт на 4 ⭐️ выставлен!")
            except Exception as e:
                bot.answer_callback_query(call.id, "❌ Ошибка выставления счёта.", show_alert=True)
            return

        # НАСТРОЙКИ ПРОФИЛЯ
        elif action_data == 'ps_back_settings':
            render_profile_settings_view(chat_id, user_id, user_name, call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        elif action_data == 'ps_back_profile':
            send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)
            bot.answer_callback_query(call.id)
            return

        elif action_data == 'ps_fonts':
            bot.answer_callback_query(call.id, 'Шрифты профиля отключены.', show_alert=True)
            return

        elif action_data == 'ps_themes':
            econ = get_user_econ(user_id, user_name, username=user_username)
            cur_t = econ.get('profile_theme', 'default')
            purchased = econ.get('purchased_themes', ['default'])
            markup = InlineKeyboardMarkup(row_width=1)
            for t_k in purchased:
                if t_k in THEMES:
                    active_mark = " (Выбрана)" if t_k == cur_t else ""
                    markup.add(InlineKeyboardButton(f"{THEMES[t_k]['name']}{active_mark}", callback_data=f"set_theme_{t_k}:{user_id}"))
            markup.add(InlineKeyboardButton("🏪 Купить новые темы в Магазине", callback_data=f"shop_cat_themes:{user_id}"))
            markup.add(InlineKeyboardButton("🔙 Назад в настройки", callback_data=f"ps_back_settings:{user_id}"))
            try:
                bot.edit_message_text(
                    "🎨 <b>ВЫБОР ТЕМЫ ОФОРМЛЕНИЯ ПРОФИЛЯ</b> 😺\n━━━━━━━━━━━━━━━━━━━━\nВыберите тему из купленных или приобретите новые в магазине: 😻",
                    chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML'
                )
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            bot.answer_callback_query(call.id)
            return

        elif action_data == 'ps_badges':
            econ = get_user_econ(user_id, user_name, username=user_username)
            inv = econ.get('inventory', [])
            current_badge = econ.get('badge')
            markup = InlineKeyboardMarkup(row_width=3)
            row = []
            for emoji in inv:
                if emoji == current_badge:
                    continue
                row.append(InlineKeyboardButton(f"Надеть {emoji}", callback_data=f"set_badge_{emoji}:{user_id}"))
                if len(row) == 3:
                    markup.add(*row); row = []
            if row: markup.add(*row)
            if current_badge:
                markup.add(InlineKeyboardButton("❌ Снять текущий значок", callback_data=f"remove_badge:{user_id}"))
            markup.add(InlineKeyboardButton("🔙 Назад в настройки", callback_data=f"ps_back_settings:{user_id}"))
            text = f"🏷 <b>НАСТРОЙКА ЗНАЧКА ПРОФИЛЯ</b>\n━━━━━━━━━━━━━━━━━━━━\nТекущий: <b>{current_badge or 'Отсутствует'}</b>"
            try: bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            bot.answer_callback_query(call.id); return

        elif action_data == 'ps_titles':
            econ = get_user_econ(user_id, user_name, username=user_username)
            owned = econ.get('titles', [])
            active = econ.get('active_title')
            markup = InlineKeyboardMarkup(row_width=1)
            for title_key in owned:
                if title_key in TITLES and title_key != active:
                    markup.add(InlineKeyboardButton(f"Надеть {TITLES[title_key]['text']}", callback_data=f"set_title_{title_key}:{user_id}"))
            if active or econ.get('custom_title'):
                markup.add(InlineKeyboardButton("❌ Снять текущий титул", callback_data=f"remove_title:{user_id}"))
            markup.add(InlineKeyboardButton("🔙 Назад в настройки", callback_data=f"ps_back_settings:{user_id}"))
            text = "👑 <b>НАСТРОЙКА ТИТУЛА ПРОФИЛЯ</b>\n━━━━━━━━━━━━━━━━━━━━\nВыберите купленный титул или снимите текущий."
            try: bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            bot.answer_callback_query(call.id); return

        # МАГАЗИН: ГЛАВНОЕ МЕНЮ
                # КАТЕГОРИИ МАГАЗИНА STARS
        elif action_data == 'shop_cat_stars_main' or action_data == 'stars_cat_main':
            render_stars_shop(chat_id, user_id, user_name, category='main', message_id=call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        elif action_data == 'stars_cat_coins':
            render_stars_shop(chat_id, user_id, user_name, category='coins', message_id=call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        elif action_data == 'stars_cat_pass':
            render_stars_shop(chat_id, user_id, user_name, category='pass', message_id=call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        elif action_data == 'stars_cat_cosm':
            render_stars_shop(chat_id, user_id, user_name, category='cosm', message_id=call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        # ИНИЦИАЦИЯ ПОДАРКА TELEGRAM STARS ДРУГУ
        # Новый callback: gift2|kind|item_key|target_id|buyer_id
        elif action_data.startswith('gift2|'):
            try:
                parts_cb = action_data.split('|')
                if len(parts_cb) != 5 or parts_cb[0] != 'gift2':
                    raise ValueError('invalid gift callback')
                gift_kind = parts_cb[1]
                item_key = parts_cb[2]
                target_id = int(parts_cb[3])
                buyer_id = int(parts_cb[4])
            except (TypeError, ValueError):
                bot.answer_callback_query(call.id, "❌ Некорректный подарок!", show_alert=True)
                return

            if buyer_id != user_id or (owner_id and owner_id != user_id):
                bot.answer_callback_query(call.id, "❌ Этот подарок может оформить только его отправитель!", show_alert=True)
                return
            if target_id == buyer_id:
                bot.answer_callback_query(call.id, "❌ Нельзя подарить товар самому себе. Используйте /stars!", show_alert=True)
                return

            catalogs = {'coins': STARS_COIN_PACKS, 'pass': STARS_VIP_PASS, 'cosm': STARS_COSMETICS}
            item = catalogs.get(gift_kind, {}).get(item_key)
            # Спец-подарки, которые могут существовать вне STARS_COSMETICS.
            if gift_kind == 'cosm' and item is None and item_key == 'bp_premium':
                item = {'name': '🎃 Премиум Хеллоуин Pass', 'stars': 3}
            if gift_kind == 'cosm' and item is None and item_key == 'custom_title':
                item = {'name': '🌟 Сертификат Кастомного Титула', 'stars': 4}
            if gift_kind == 'cosm' and item is None and item_key == 'pet_griffin':
                item = {'name': '🐱 Королевский Грифон', 'stars': 5}
            if not item:
                bot.answer_callback_query(call.id, "❌ Товар подарка не найден!", show_alert=True)
                return

            target_econ = get_user_econ(user_id=target_id)
            owned_error = None
            if gift_kind == 'pass':
                owned_error = stars_purchase_error(target_econ, 'vippass', item_key)
            elif gift_kind == 'cosm':
                if item_key == 'bp_premium' and target_econ.get('bp_premium'):
                    owned_error = 'У получателя уже есть Премиум Pass.'
                elif item_key == 'custom_title' and target_econ.get('has_custom_title_cert'):
                    owned_error = 'У получателя уже есть сертификат титула.'
                elif item_key == 'pet_griffin' and 'pet_griffin' in target_econ.get('paid_stars_items', []):
                    owned_error = 'У получателя уже есть Королевский Грифон.'
                elif item_key in STARS_COSMETICS or item_key in STARS_LIMITED_ITEMS:
                    owned_error = stars_purchase_error(target_econ, 'cosm', item_key)
            if owned_error:
                bot.answer_callback_query(call.id, "❌ " + owned_error.replace('❌ ', ''), show_alert=True)
                return

            try:
                payload = f"gift2|{gift_kind}|{item_key}|{target_id}|{buyer_id}"
                bot.send_invoice(
                    chat_id=chat_id,
                    title=f"🎁 Подарок: {item['name']}",
                    description=f"Подарок для пользователя ID:{target_id}",
                    invoice_payload=payload,
                    provider_token="",
                    currency="XTR",
                    prices=[LabeledPrice(label=item['name'], amount=item['stars'])]
                )
                bot.answer_callback_query(call.id, f"⭐️ Счёт на {item['stars']} ⭐️ выставлен!")
            except Exception as e:
                print(f"[STARS GIFT INVOICE ERROR] {e}")
                bot.answer_callback_query(call.id, "❌ Не удалось выставить счёт.", show_alert=True)
            return

        # ИНИЦИАЦИЯ ОПЛАТЫ STARS: ПАКЕТЫ КОИНОВ
        elif action_data.startswith('star_buy_coins_'):
            pack_key = action_data.replace('star_buy_coins_', '')
            if pack_key in STARS_COIN_PACKS:
                pack = STARS_COIN_PACKS[pack_key]
                try:
                    bot.send_invoice(
                        chat_id=chat_id,
                        title=pack['name'],
                        description=pack['desc'],
                        invoice_payload=f"coinpack_{pack_key}:{user_id}:{int(time.time())}",
                        provider_token="",
                        currency="XTR",
                        prices=[LabeledPrice(label=pack['name'], amount=pack['stars'])]
                    )
                    bot.answer_callback_query(call.id, f"⭐️ Счёт на {pack['stars']} ⭐️ выставлен!")
                except Exception as e:
                    bot.answer_callback_query(call.id, "❌ Ошибка выставления счёта.", show_alert=True)
            return

        # ИНИЦИАЦИЯ ОПЛАТЫ STARS: VIP PASS
        elif action_data.startswith('star_buy_pass_'):
            pass_key = action_data.replace('star_buy_pass_', '')
            if pass_key in STARS_VIP_PASS:
                item = STARS_VIP_PASS[pass_key]
                econ = get_user_econ(user_id, user_name, username=user_username)
                purchase_error = stars_purchase_error(econ, 'vippass', pass_key)
                if purchase_error:
                    bot.answer_callback_query(call.id, purchase_error, show_alert=True)
                    return
                try:
                    bot.send_invoice(
                        chat_id=chat_id,
                        title=item['name'],
                        description=item['desc'],
                        invoice_payload=f"vippass_{pass_key}:{user_id}:{int(time.time())}",
                        provider_token="",
                        currency="XTR",
                        prices=[LabeledPrice(label=item['name'], amount=item['stars'])]
                    )
                    bot.answer_callback_query(call.id, f"⭐️ Счёт на {item['stars']} ⭐️ выставлен!")
                except Exception as e:
                    bot.answer_callback_query(call.id, "❌ Ошибка выставления счёта.", show_alert=True)
            return

        # ИНИЦИАЦИЯ ОПЛАТЫ STARS: КОСМЕТИКА И СТАТУС
        elif action_data.startswith('star_buy_cosm_'):
            cosm_key = action_data.replace('star_buy_cosm_', '')
            if cosm_key in STARS_COSMETICS or cosm_key in STARS_LIMITED_ITEMS:
                item = STARS_COSMETICS.get(cosm_key) or STARS_LIMITED_ITEMS.get(cosm_key)
                econ = get_user_econ(user_id, user_name, username=user_username)
                purchase_error = stars_purchase_error(econ, 'cosm', cosm_key)
                if purchase_error:
                    bot.answer_callback_query(call.id, purchase_error, show_alert=True)
                    return
                try:
                    bot.send_invoice(
                        chat_id=chat_id,
                        title=item['name'],
                        description=item['desc'],
                        invoice_payload=f"cosm_{cosm_key}:{user_id}:{int(time.time())}",
                        provider_token="",
                        currency="XTR",
                        prices=[LabeledPrice(label=item['name'], amount=item['stars'])]
                    )
                    bot.answer_callback_query(call.id, f"⭐️ Счёт на {item['stars']} ⭐️ выставлен!")
                except Exception as e:
                    bot.answer_callback_query(call.id, "❌ Ошибка выставления счёта.", show_alert=True)
            return

        if action_data == 'shop_main':
            send_shop_menu(chat_id, user_id, user_name, message_id=call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        elif action_data.startswith('stars_cat_'):
            cat = action_data.replace('stars_cat_', '', 1)
            render_stars_shop(chat_id, user_id, user_name, category=cat, message_id=call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        # ПЕРЕХОД В РАЗДЕЛ «ГАРАЖ» ИЗ МАГАЗИНА
        elif action_data == 'shop_cat_garage':
            render_garage_view(chat_id, user_id, user_name, message_id=call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        # ИНТЕРАКТИВНОЕ ПЕРЕКЛЮЧЕНИЕ ТОПОВ
        elif action_data.startswith('top_cat_'):
            cat = action_data.replace('top_cat_', '')
            render_top_menu(chat_id, user_id=user_id, category=cat, message_id=call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        # ОТМЕНА ПАРТИИ В ДУРАКА (С ВОЗВРАТОМ СТАВОК)
        elif action_data.startswith('durak_cancel_'):
            game_id = action_data.replace('durak_cancel_', '')
            game = active_durak.get(game_id)
            if not game:
                bot.answer_callback_query(call.id, "❌ Игра уже завершена или не найдена!", show_alert=True)
                return
            creator_id = game['players'][0]['id'] if game.get('players') else None
            if user_id != creator_id and not is_admin(chat_id, user_id):
                bot.answer_callback_query(call.id, "❌ Отменить игру может только её создатель или администратор!", show_alert=True)
                return
            bet = game.get('bet', 0)
            for p in game.get('players', []):
                if p.get('id') and p['id'] != 'bot' and bet > 0:
                    add_coins(p['id'], p.get('name'), bet)
            active_durak.pop(game_id, None)
            mark_dirty()
            bot.answer_callback_query(call.id, "✅ Партия в «Дурака» отменена, ставки возвращены!")
            try:
                bot.edit_message_text("❌ <b>Партия в «Дурака» отменена создателем.</b> Все ставки возвращены игрокам. 😸", chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML')
            except Exception:
                pass
            return

        # ИСПРАВЛЕННЫЙ ПЕРЕХОД В РАЗДЕЛ «КОЛЬЦА» В МАГАЗИНЕ
        elif action_data == 'shop_cat_rings':
            lines = [
                "💍 <b>КАТАЛОГ СВАДЕБНЫХ КОЛЕЦ</b> 💒 😺",
                "━━━━━━━━━━━━━━━━━━━━",
                "<i>Кольца необходимы для заключения брака (/marry) и украшают ваш профиль!</i>\n"
            ]
            for r_k, r_v in RINGS.items():
                lines.append(f"• {r_v['emoji']} <b>{r_v['name']}</b> — <code>{r_v['price']} 🪙</code>")
            lines.append("━━━━━━━━━━━━━━━━━━━━")

            markup = InlineKeyboardMarkup(row_width=1)
            for r_k, r_v in RINGS.items():
                markup.add(InlineKeyboardButton(f"Купить {r_v['emoji']} {r_v['name']} ({r_v['price']} 🪙)", callback_data=f"buy_ring_{r_k}:{user_id}"))
            markup.add(InlineKeyboardButton("🔙 Назад в магазин", callback_data=f"shop_main:{user_id}"))

            try:
                bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            bot.answer_callback_query(call.id)
            return

        # САД: УДОБРЕНИЕ (старый callback)
        elif action_data == 'fertilize_plant':
            bot.answer_callback_query(call.id, "🌱 Выберите грядку для удобрения.")
            render_garden_view(chat_id, user_id, user_name, call.message.message_id)
            return

        elif action_data == 'garden_view':
            render_garden_view(chat_id, user_id, user_name, call.message.message_id)
            bot.answer_callback_query(call.id)
            return

        # САД: ПЛАТНЫЙ ПОЛИВ (15 коинов)
        elif action_data == 'water_plant':
            econ = get_user_econ(user_id, user_name, username=user_username)
            garden = econ.get('garden')
            if isinstance(garden, list):
                bot.answer_callback_query(call.id, "🌱 Сад обновлён: выберите конкретную грядку.")
                render_garden_view(chat_id, user_id, user_name, call.message.message_id)
                return
            if not garden: return
            seed_info = GARDEN_SEEDS[garden['seed']]
            
            now = time.time()
            last_dry_calc = garden.get('last_dry_calc', garden.get('planted_at', now))
            dry_interval = 3600 * 2
            lost_water = int((now - last_dry_calc) // dry_interval)
            if lost_water > 0:
                garden['water_count'] = max(0, garden.get('water_count', 0) - lost_water)
                garden['last_dry_calc'] = last_dry_calc + (lost_water * dry_interval)

            if garden['water_count'] >= seed_info['water_req']:
                bot.answer_callback_query(call.id, "💦 Земля максимально увлажнена! Полив сейчас не требуется. 😸", show_alert=True)
                return

            water_cost = 15
            if econ['balance'] < water_cost:
                bot.answer_callback_query(call.id, f"❌ На ведро воды нужно {water_cost} 🪙! 😿", show_alert=True)
                return

            _adjust_balance(econ, -(water_cost))
            garden['water_count'] += 1
            garden['last_dry_calc'] = time.time()
            mark_dirty()
            bot.answer_callback_query(call.id, "💦 Растение полито свежей водой (-15 🪙)! 😸")
            render_garden_view(chat_id, user_id, user_name, call.message.message_id)
            return

        # ДУРАК: ВЫБОР РЕЖИМА
        elif action_data.startswith('durak_mode_'):
            m_parts = action_data.split('_')
            mode_num = int(m_parts[2])
            bet = int(m_parts[3])

            econ = get_user_econ(user_id, user_name, username=user_username)
            if bet > 0 and econ['balance'] < bet:
                bot.answer_callback_query(call.id, f"❌ Недостаточно средств для ставки {bet} 🪙!", show_alert=True)
                return

            creator_pm_msg_id = None
            if mode_num > 1:
                try:
                    dm = bot.send_message(user_id, "🃏 <b>Лобби «Дурак» создано!</b>\nЭто сообщение будет превращено в ваши карты, когда соберутся игроки. 😺", parse_mode='HTML')
                    creator_pm_msg_id = dm.message_id
                except Exception:
                    bot.answer_callback_query(call.id, "❌ Сначала откройте ЛС с ботом и нажмите START. После этого создайте мультиплеерную игру ещё раз.", show_alert=True)
                    return

            if bet > 0:
                _adjust_balance(econ, -(bet))
                mark_dirty()

            game_id = f"durak_{user_id}_{time.time_ns()}"
            deck = create_durak_deck()
            trump_card = deck[0]
            trump_suit = trump_card['suit']

            if mode_num == 1:
                bet = 0  # Против бота игра без ставок (множитель 2х отключен)
                p_human = {'id': user_id, 'name': user_name, 'hand': [], 'pm_msg_id': None}
                p_bot = {'id': 'bot', 'name': '🤖 Ня-Бот', 'hand': []}
                players = [p_human, p_bot]
                game = {
                    'mode_name': 'Соло против Бота',
                    'target_players': 2,
                    'bet': bet,
                    'players': players,
                    'deck': deck,
                    'trump': trump_suit,
                    'table': [],
                    'attacker_idx': 0,
                    'defender_idx': 1,
                    'started': True,
                    'finished': False,
                    'status_text': 'Игра началась! Вы ходите первым.',
                    'start_time': time.time(),
                    'chat_id': chat_id,
                    'msg_id': call.message.message_id
                }
                durak_deal_cards(game)
                active_durak[game_id] = game
                text, markup = render_durak_board(game_id, viewer_id=user_id)
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
            else:
                players = [{'id': user_id, 'name': user_name, 'hand': [], 'pm_msg_id': creator_pm_msg_id}]
                game = {
                    'mode_name': f'Мультиплеер ({mode_num} игроков)',
                    'target_players': mode_num,
                    'bet': bet,
                    'players': players,
                    'deck': deck,
                    'trump': trump_suit,
                    'table': [],
                    'attacker_idx': 0,
                    'defender_idx': 1,
                    'started': False,
                    'finished': False,
                    'status_text': f'Ожидание игроков... (1/{mode_num})',
                    'start_time': time.time(),
                    'chat_id': chat_id,
                    'msg_id': call.message.message_id
                }
                active_durak[game_id] = game
                text, markup = render_durak_board(game_id, viewer_id=user_id)
                try: bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")

        # ДУРАК: ПРИСОЕДИНЕНИЕ (С ПРОВЕРКОЙ ЛС)
        elif action_data.startswith('durak_join_'):
            game_id = action_data.replace('durak_join_', '')
            game = active_durak.get(game_id)
            if not game or game['started']:
                bot.answer_callback_query(call.id, "❌ Игра уже началась или завершена!", show_alert=True)
                return

            if any(p['id'] == user_id for p in game['players']):
                bot.answer_callback_query(call.id, "Вы уже присоединились к этому столу!", show_alert=True)
                return

            try:
                test_msg = bot.send_message(user_id, "🤝 <b>Вы успешно подключились к столу игры «Дурак»!</b>\nВаши карты будут отправлены сюда, как только наберется вся команда! 🃏 😻", parse_mode='HTML')
                user_pm_msg_id = test_msg.message_id
            except Exception:
                b_name = ""
                try: b_name = bot.get_me().username
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
                tag_str = f"@{b_name}" if b_name else "бота"
                bot.answer_callback_query(call.id, f"❌ Вы должны сначала открыть диалог с ботом ({tag_str}) в ЛС и нажать START (Запустить), чтобы бот мог выдать вам карты!", show_alert=True)
                return

            bet = game['bet']
            econ = get_user_econ(user_id, user_name, username=user_username)
            if bet > 0 and econ['balance'] < bet:
                bot.answer_callback_query(call.id, f"❌ Для входа нужно {bet} 🪙!", show_alert=True)
                return

            if bet > 0:
                _adjust_balance(econ, -(bet))
                mark_dirty()

            game['players'].append({'id': user_id, 'name': user_name, 'hand': [], 'pm_msg_id': user_pm_msg_id})
            cur_cnt = len(game['players'])
            req_cnt = game['target_players']

            if cur_cnt >= req_cnt:
                game['started'] = True
                durak_deal_cards(game)
                game['status_text'] = f"Все игроки в сборе! Ходит {game['players'][0]['name']}! Карты розданы в ЛС."
                sync_durak_pm(game_id)

            game['chat_id'] = chat_id
            game['msg_id'] = call.message.message_id
            refresh_durak_group_board(game_id)
            bot.answer_callback_query(call.id, "✅ Вы успешно сели за игровой стол! Карты придут в ЛС! 😸")

        # ДУРАК: ХОД КАРТОЙ
        elif action_data.startswith('durak_card_'):
            m_parts = action_data.split('_')
            game_id = f"{m_parts[2]}_{m_parts[3]}_{m_parts[4]}"
            card_idx = int(m_parts[5])
            game = active_durak.get(game_id)

            if not game or game.get('finished'):
                bot.answer_callback_query(call.id, "❌ Игра завершена!", show_alert=True)
                return

            players = game['players']
            p_idx = next((i for i, p in enumerate(players) if p['id'] == user_id), None)
            if p_idx is None:
                bot.answer_callback_query(call.id, "❌ Вы не участник этой партии!", show_alert=True)
                return

            p = players[p_idx]
            if card_idx >= len(p['hand']):
                bot.answer_callback_query(call.id, "Карта уже сыграна!")
                return
            card = p['hand'][card_idx]
            trump = game['trump']

            is_attacker = (p_idx == game['attacker_idx'])
            is_defender = (p_idx == game['defender_idx'])

            def_hand_len = len(game['players'][game['defender_idx']]['hand'])
            unbeaten_cards = sum(1 for pair in game['table'] if pair.get('defend') is None)

            if not is_attacker and not is_defender:
                table_ranks = {pair['attack']['rank'] for pair in game['table']} | {pair['defend']['rank'] for pair in game['table'] if pair.get('defend')}
                if card['rank'] not in table_ranks or len(game['table']) >= 6 or unbeaten_cards >= def_hand_len:
                    bot.answer_callback_query(call.id, "❌ Нельзя подкинуть (лимит карт у защитника или неподходящий ранг)!", show_alert=True)
                    return
                p['hand'].pop(card_idx)
                game['table'].append({'attack': card, 'defend': None})
                game['status_text'] = f"{p['name']} подкинул(а) {card_to_str(card)}!"
            elif is_attacker:
                if not game['table']:
                    p['hand'].pop(card_idx)
                    game['table'].append({'attack': card, 'defend': None})
                    game['status_text'] = f"{p['name']} пошёл(ла) с {card_to_str(card)}!"
                else:
                    table_ranks = {pair['attack']['rank'] for pair in game['table']} | {pair['defend']['rank'] for pair in game['table'] if pair.get('defend')}
                    if card['rank'] not in table_ranks or len(game['table']) >= 6 or unbeaten_cards >= def_hand_len:
                        bot.answer_callback_query(call.id, "❌ Нельзя подкинуть (лимит карт у защитника или неподходящий ранг)!", show_alert=True)
                        return
                    p['hand'].pop(card_idx)
                    game['table'].append({'attack': card, 'defend': None})
                    game['status_text'] = f"{p['name']} подкинул(а) {card_to_str(card)}!"
            elif is_defender:
                unbeaten_idx = next((i for i, pair in enumerate(game['table']) if pair.get('defend') is None), None)
                if unbeaten_idx is None:
                    bot.answer_callback_query(call.id, "Все карты на столе уже отбиты!")
                    return
                target_attack = game['table'][unbeaten_idx]['attack']
                if not can_beat_card(target_attack, card, trump):
                    bot.answer_callback_query(call.id, f"❌ Карта {card_to_str(card)} не бьёт {card_to_str(target_attack)}!", show_alert=True)
                    return
                p['hand'].pop(card_idx)
                game['table'][unbeaten_idx]['defend'] = card
                game['status_text'] = f"{p['name']} отбил(а) {card_to_str(target_attack)} картой {card_to_str(card)}!"

            if game['target_players'] == 2 and game['players'][1]['id'] == 'bot':
                durak_bot_turn(game)

            survivors = [pl for pl in players if len(pl['hand']) > 0 or len(game['deck']) > 0]
            if len(survivors) <= 1:
                game['finished'] = True
                loser = survivors[0] if survivors else None
                is_vs_bot = any(pl['id'] == 'bot' for pl in players)
                if is_vs_bot:
                    tot_pot = game['bet']  # Без умножителя 2х за победу над ботом
                else:
                    tot_pot = game['bet'] * len(players)
                win_text = f"🏁 <b>ИГРА ОКОНЧЕНА!</b>\n"
                if loser:
                    win_text += f"🃏 В дураках остался: <b>{loser['name']}</b>! 🙀\n"
                else:
                    win_text += "🤝 Боевая ничья! Все вышли из игры! 😸\n"

                winners = [pl for pl in players if pl != loser and pl['id'] != 'bot']
                if winners and tot_pot > 0:
                    split_win = tot_pot // len(winners)
                    for w in winners:
                        add_coins(w['id'], w['name'], split_win)
                    if is_vs_bot:
                        win_text += f"💰 Возврат ставки: <b>+{split_win} 🪙</b> (умножитель 2х против бота отключен)!"
                    else:
                        win_text += f"💰 Победители разделили банк: <b>+{split_win} 🪙</b> каждому!"

                game['status_text'] = win_text
                for pl in players:
                    if pl.get('id') == 'bot':
                        continue
                    pecon = get_user_econ(pl.get('id'), pl.get('name'))
                    if loser and pl.get('id') == loser.get('id'):
                        pecon['durak_losses'] = int(pecon.get('durak_losses', 0) or 0) + 1
                    else:
                        pecon['durak_wins'] = int(pecon.get('durak_wins', 0) or 0) + 1
                mark_dirty()
                refresh_durak_group_board(game_id)
                sync_durak_pm(game_id)
                active_durak.pop(game_id, None)
                return

            refresh_durak_group_board(game_id)
            sync_durak_pm(game_id)
            bot.answer_callback_query(call.id)

        # ДУРАК: ВЗЯТЬ КАРТЫ
        elif action_data.startswith('durak_take_'):
            game_id = action_data.replace('durak_take_', '')
            game = active_durak.get(game_id)
            if not game: return
            p_idx = next((i for i, pl in enumerate(game['players']) if pl['id'] == user_id), None)
            if p_idx != game['defender_idx']:
                bot.answer_callback_query(call.id, "Только защищающийся может взять карты!", show_alert=True)
                return

            taken = []
            for pair in game['table']:
                taken.append(pair['attack'])
                if pair.get('defend'): taken.append(pair['defend'])
            if not game.get('table'):
                bot.answer_callback_query(call.id, "❌ На столе уже нет карт!", show_alert=True)
                return
            old_attacker = game['attacker_idx']; old_defender = game['defender_idx']
            game['players'][p_idx]['hand'].extend(taken)
            game['table'] = []
            durak_deal_cards(game)
            game['attacker_idx'] = old_attacker
            game['defender_idx'] = old_defender if len(game['players']) == 2 else (old_defender + 1) % len(game['players'])
            game['status_text'] = f"{user_name} забрал(а) карты со стола!"

            if game['target_players'] == 2 and game['players'][1]['id'] == 'bot' and game['attacker_idx'] == 1:
                durak_bot_turn(game)

            refresh_durak_group_board(game_id)
            sync_durak_pm(game_id)
            bot.answer_callback_query(call.id)

        # ДУРАК: БИТО
        elif action_data.startswith('durak_bito_'):
            game_id = action_data.replace('durak_bito_', '')
            game = active_durak.get(game_id)
            if not game: return
            players_now = game.get('players', [])
            attacker_idx = int(game.get('attacker_idx', 0))
            if attacker_idx < 0 or attacker_idx >= len(players_now) or players_now[attacker_idx].get('id') != user_id:
                bot.answer_callback_query(call.id, "❌ Сейчас не ваш ход!", show_alert=True)
                return
            if not game.get('table') or not all(pair.get('defend') for pair in game['table']):
                bot.answer_callback_query(call.id, "❌ Не все карты отбиты!", show_alert=True)
                return
            game['table'] = []
            durak_deal_cards(game)
            game['attacker_idx'] = game['defender_idx']
            game['defender_idx'] = (game['defender_idx'] + 1) % len(game['players'])
            game['status_text'] = "✅ Бито! Карты ушли в отбой!"

            if game['target_players'] == 2 and game['players'][1]['id'] == 'bot':
                durak_bot_turn(game)

            refresh_durak_group_board(game_id)
            sync_durak_pm(game_id)
            bot.answer_callback_query(call.id)

        # ИГРА КИРПИЧ
        elif action_data.startswith('brick_step_'):
            game_id = action_data.replace('brick_step_', '')
            game = active_brick.get(game_id)
            if not game or game.get('finished'):
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

            if random.random() < risk:
                game['finished'] = True
                try:
                    bot.edit_message_text(
                        f"🧱 <b>КРАШ НА СТРОЙКЕ!</b> 🙀\n\n"
                        f"👤 Игрок: {make_link(chat_id, user_name, user_id, ping=False)}\n"
                        f"💥 Кирпич сорвался на шаге {step+1} (Множитель: {mult:.2f}x)!\n"
                        f"💸 Ставка <b>{game['bet']} 🪙</b> утеряна... 😿",
                        chat_id=chat_id,
                        message_id=call.message.message_id,
                        parse_mode='HTML'
                    )
                except Exception:
                    pass
                del active_brick[game_id]
                return

            game['step'] = step + 1
            cashout_amt = int(game['bet'] * mult)

            markup = InlineKeyboardMarkup()
            if game['step'] < len(game['mults']) - 1:
                markup.add(InlineKeyboardButton(f"🏗 Сделать шаг (Риск {int(game['risks'][game['step']+1]*100)}%)", callback_data=f"brick_step_{game_id}:{user_id}"))
            markup.add(InlineKeyboardButton(f"💰 Забрать куш ({cashout_amt} 🪙 | {mult:.2f}x) 😻", callback_data=f"brick_cashout_{game_id}:{user_id}"))

            bar = "🟩" * (game['step'] + 1) + "⬜️" * (len(game['mults']) - game['step'] - 1)
            try:
                bot.edit_message_text(
                    f"🧱 <b>ИГРА КИРПИЧ (СТРОЙКА)</b> 😺\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 Строитель: {make_link(chat_id, user_name, user_id, ping=False)}\n"
                    f"💰 Ставка: <b>{game['bet']} 🪙</b>\n"
                    f"📈 Текущий множитель: <b>{mult:.2f}x</b>\n"
                    f"🏗 Прогресс: [{bar}]\n"
                    f"━━━━━━━━━━━━━━━━━━━━",
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    reply_markup=markup,
                    parse_mode='HTML'
                )
            except Exception:
                pass

        elif action_data.startswith('brick_cashout_'):
            game_id = action_data.replace('brick_cashout_', '')
            game = active_brick.get(game_id)
            if not game or game.get('finished'):
                bot.answer_callback_query(call.id, "❌ Игра окончена!", show_alert=True)
                return
            if user_id != game['user_id']:
                bot.answer_callback_query(call.id, "❌ Не ваша игра!", show_alert=True)
                return

            game['finished'] = True
            mult = game['mults'][game['step']]
            win_amt = int(game['bet'] * mult)
            win_amt = process_casino_win(win_amt)

            econ = get_user_econ(user_id, user_name, username=user_username)
            _adjust_balance(econ, win_amt)
            econ['daily_casino_win'] = econ.get('daily_casino_win', 0) + (win_amt - game['bet'])
            econ['daily_casino_profit'] = econ.get('daily_casino_profit', 0) + (win_amt - game['bet'])
            check_achievements(user_id, user_name, 'games', 1, chat_id, username=user_username)
            mark_dirty()

            try:
                bot.edit_message_text(
                    f"💰 <b>ВЫ УСПЕШНО ЗАБРАЛИ КУШ!</b> 😻\n\n"
                    f"👤 Строитель: {make_link(chat_id, user_name, user_id, ping=False)}\n"
                    f"🎉 Выигрыш: <b>+{win_amt} Ня-коинов 🪙</b> (Множитель: <b>{mult:.2f}x</b>)!\n"
                    f"💵 Баланс: <b>{econ['balance']} 🪙</b> 😸",
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    parse_mode='HTML'
                )
            except Exception:
                pass
            del active_brick[game_id]

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
            game['finished'] = True
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

            bot.answer_callback_query(call.id, f"🎉 Куш забран: +{win_amt} 🪙 ({mult:.2f}x)! 😻", show_alert=True)
            try:
                bot.edit_message_text(
                    f"💰 <b>УСПЕШНЫЙ CASHOUT В КРАШЕ!</b> 😺\n\n"
                    f"👤 Пилот: {make_link(chat_id, user_name, user_id, ping=False)}\n"
                    f"🎉 Зафиксирован выигрыш: <b>+{win_amt} Ня-коинов 🪙</b> (Множитель: <b>{mult:.2f}x</b>)! 😻\n"
                    f"💵 Баланс: <b>{econ['balance']} 🪙</b>",
                    chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML'
                )
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            active_crash.pop(game_id, None)

        # РАСХОДНИКИ
        elif action_data == 'use_item_energy_drink':
            econ = get_user_econ(user_id, user_name, username=user_username)
            bp = econ.setdefault('backpack', {})
            if bp.get('energy_drink', 0) <= 0:
                bot.answer_callback_query(call.id, "❌ У вас нет энергетика!", show_alert=True)
                return

            now = time.time()
            last_drink = econ.get('last_energy_drink_time', 0)
            cooldown_drink = 1800
            left = cooldown_text(last_drink, cooldown_drink)
            if left:
                bot.answer_callback_query(call.id, f"⏳ Энергетик можно пить не чаще 1 раза в 30 минут! Ждать: {left} 😿", show_alert=True)
                return

            bp['energy_drink'] -= 1
            econ['last_energy_drink_time'] = now
            econ['last_work_time'] = 0; econ['last_fish_time'] = 0; econ['last_hunt_time'] = 0
            econ['last_train_time'] = 0; econ['last_iq_time'] = 0; econ['last_fat_time'] = 0
            econ['last_foot_time'] = 0; econ['last_chromosomes_time'] = 0; econ['last_dick_time'] = 0
            econ['last_trash_time'] = 0
            mark_dirty()
            bot.answer_callback_query(call.id, "⚡️ Энергетик выпит! Все таймеры сброшены! 😻", show_alert=True)
            render_backpack_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'use_item_luck_clover':
            econ = get_user_econ(user_id, user_name, username=user_username)
            bp = econ.setdefault('backpack', {})
            if bp.get('luck_clover', 0) <= 0:
                bot.answer_callback_query(call.id, "❌ У вас нет клевера! 😿", show_alert=True)
                return
            bp['luck_clover'] -= 1
            econ['luck_clover_until'] = time.time() + 3600
            mark_dirty()
            bot.answer_callback_query(call.id, "🍀 Клевер активирован! +15% к удаче в играх на 1 час! 😺", show_alert=True)
            render_backpack_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'use_item_invis_mask':
            econ = get_user_econ(user_id, user_name, username=user_username)
            bp = econ.setdefault('backpack', {})
            if bp.get('invis_mask', 0) <= 0:
                bot.answer_callback_query(call.id, "❌ У вас нет маски-невидимки! 😿", show_alert=True)
                return
            bp['invis_mask'] -= 1
            econ['invis_until'] = time.time() + 86400
            mark_dirty()
            bot.answer_callback_query(call.id, "🥷 Маска надета! Ваши замеры скрыты из топов на 24 часа! 😼", show_alert=True)
            render_backpack_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'backpack_alarm':
            econ = get_user_econ(user_id, user_name, username=user_username)
            bp = econ.setdefault('backpack', {})
            if bp.get('alarm_system', 0) <= 0:
                bot.answer_callback_query(call.id, "❌ У вас нет сигнализации!", show_alert=True)
                return
            bot.answer_callback_query(call.id, "🛡️ Сигнализация работает автоматически и не требует активации! 😺", show_alert=True)
            render_backpack_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'profile_self':
            try:
                send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)
            except Exception as e:
                print(f"[NONFATAL ERROR] {e}")

        # СТУДИЯ СТРИМЕРА
        elif action_data == 'shop_cat_stream':
            econ = get_user_econ(user_id, user_name)
            studio = econ.setdefault('stream_studio', {'mic': 1, 'webcam': 1, 'light': 1})
            lines = [
                "🎙 <b>СТУДИЯ СТРИМЕРА (АПГРЕЙДЫ)</b> 😺", "━━━━━━━━━━━━━━━━━━━━",
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

            lines.append("━━━━━━━━━━━━━━━━━━━━")
            markup.add(InlineKeyboardButton("🔙 Назад в магазин", callback_data=f"shop_main:{user_id}"))
            try: bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('buy_studio_'):
            equip_key = action_data.replace('buy_studio_', '')
            econ = get_user_econ(user_id, user_name, username=user_username)
            studio = econ.setdefault('stream_studio', {'mic': 1, 'webcam': 1, 'light': 1})
            lvl = studio.get(equip_key, 1)
            if lvl >= 4:
                bot.answer_callback_query(call.id, "❌ Максимальный уровень! 🙀", show_alert=True)
                return
            cost = STREAM_EQUIP[equip_key]['levels'][lvl]
            if econ['balance'] < cost:
                bot.answer_callback_query(call.id, f"❌ Нужно {cost} 🪙! 😿", show_alert=True)
                return
            _adjust_balance(econ, -(cost))
            studio[equip_key] = lvl + 1
            mark_dirty()
            bot.answer_callback_query(call.id, f"🎉 Вы улучшили {STREAM_EQUIP[equip_key]['name']} до {lvl+1} уровня! 😻")
            send_shop_menu(chat_id, user_id, user_name, message_id=call.message.message_id)

        # СЕМЕНА САДА
        elif action_data == 'shop_cat_garden':
            lines = [
                "🪴 <b>СЕМЕНА ОРАНЖЕРЕИ БОНСАЙ</b> 😺", "━━━━━━━━━━━━━━━━━━━━",
                "<i>Посадите семечко, поливайте его и соберите ценный урожай!</i> 😸\n"
            ]
            for s_id, s_info in GARDEN_SEEDS.items():
                hrs = s_info['grow_time'] // 3600
                lines.append(f"• {s_info['emoji']} <b>{s_info['name']}</b> — <code>{s_info['price']} 🪙</code>\n  <i>(Рост: {hrs} ч., Поливов: {s_info['water_req']}, Прибыль: {s_info['reward_min']}-{s_info['reward_max']} 🪙)</i>\n")
            lines.append("━━━━━━━━━━━━━━━━━━━━")

            markup = InlineKeyboardMarkup(row_width=2)
            btns = [InlineKeyboardButton(f"{s['emoji']} {s['price']} 🪙", callback_data=f"buy_seed_{s_id}:{user_id}") for s_id, s in GARDEN_SEEDS.items()]
            for i in range(0, len(btns), 2):
                markup.add(*btns[i:i+2])
            markup.add(InlineKeyboardButton("🔙 Назад в магазин", callback_data=f"shop_main:{user_id}"))
            try: bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('buy_seed_'):
            s_id = action_data.replace('buy_seed_', '')
            if s_id in GARDEN_SEEDS:
                seed = GARDEN_SEEDS[s_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                slots=econ.get('garden') or []
                if not isinstance(slots,list): slots=[slots]
                if len(slots)>=get_garden_capacity(econ):
                    bot.answer_callback_query(call.id, '❌ Нет свободной грядки!', show_alert=True); return
                if econ['balance'] < seed['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {seed['price']} 🪙! 😿", show_alert=True)
                    return
                _adjust_balance(econ, -(seed['price']))
                slots.append({'seed': s_id, 'planted_at': time.time(), 'water_count': 0, 'last_dry_calc': time.time()})
                econ['garden'] = slots
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Вы посадили {seed['name']}! Зайдите в /garden 😻", show_alert=True)
                render_garden_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'harvest_plant':
            econ = get_user_econ(user_id, user_name)
            garden = econ.get('garden')
            if isinstance(garden, list):
                bot.answer_callback_query(call.id, "🌱 Сад обновлён: выберите конкретную грядку.")
                render_garden_view(chat_id, user_id, user_name, call.message.message_id)
                return
            if not garden: return
            seed_info = GARDEN_SEEDS[garden['seed']]
            elapsed = time.time() - garden['planted_at']
            if elapsed < seed_info['grow_time']:
                bot.answer_callback_query(call.id, "❌ Урожай еще не созрел! 😿", show_alert=True)
                return
            if garden['water_count'] < seed_info['water_req']:
                bot.answer_callback_query(call.id, "❌ Растению не хватило полива! Земля высохла. 😾", show_alert=True)
                return
            reward = random.randint(seed_info['reward_min'], seed_info['reward_max'])
            _adjust_balance(econ, reward)
            econ['garden'] = None
            change_karma(user_id, user_name, 2)
            mark_dirty()
            bot.answer_callback_query(call.id, f"🎉 Урожай собран: +{reward} 🪙! 😻")
            try:
                bot.edit_message_text(
                    f"🪴 <b>СБОР УРОЖАЯ</b> 😺\n━━━━━━━━━━━━━━━━━━━━\n"
                    f"Вы собрали великолепный урожай {seed_info['name']} и продали его за <b>{reward} Ня-коинов 🪙</b>!\n"
                    f"Карма повышена: <b>+2 😇</b>",
                    chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML'
                )
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data == 'uproot_plant':
            econ = get_user_econ(user_id, user_name)
            if isinstance(econ.get('garden'), list):
                bot.answer_callback_query(call.id, "🌱 Сад обновлён: выберите конкретную грядку.")
                render_garden_view(chat_id, user_id, user_name, call.message.message_id)
                return
            econ['garden'] = None
            mark_dirty()
            bot.answer_callback_query(call.id, "❌ Растение выкорчевано. 😿")
            render_garden_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'shop_cat_buffs':
            lines = [
                "🧰 <b>МАГАЗИН РАСХОДНИКОВ И БАФФОВ</b> 😺", "━━━━━━━━━━━━━━━━━━━━",
                "<i>Используйте расходники из рюкзака (/backpack) для преимуществ!</i> 😸\n"
            ]
            for b_id, b_info in BUFF_ITEMS.items():
                lines.append(f"• <b>{b_info['name']}</b> — <code>{b_info['price']} 🪙</code>\n  <i>{b_info['desc']}</i>\n")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            markup = InlineKeyboardMarkup(row_width=2)
            btns = [InlineKeyboardButton(f"{b['short']} • {b['price']} 🪙", callback_data=f"buy_buff_{b_id}:{user_id}") for b_id, b in BUFF_ITEMS.items()]
            for i in range(0, len(btns), 2):
                markup.add(*btns[i:i+2])
            markup.add(InlineKeyboardButton("🔙 Назад в магазин", callback_data=f"shop_main:{user_id}"))
            try: bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('buy_buff_'):
            b_id = action_data.replace('buy_buff_', '')
            if b_id in BUFF_ITEMS:
                item = BUFF_ITEMS[b_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                if econ['balance'] < item['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {item['price']} 🪙! 😿", show_alert=True)
                    return
                _adjust_balance(econ, -(item['price']))
                bp = econ.setdefault('backpack', {})
                bp[b_id] = bp.get(b_id, 0) + 1
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Куплен предмет: {item['short']}! Откройте /backpack 😻", show_alert=True)

        elif action_data == 'shop_cat_themes':
            lines = [
                "🎨 <b>КАТАЛОГ ТЕМ ОФОРМЛЕНИЯ ПРОФИЛЯ</b> 😺", "━━━━━━━━━━━━━━━━━━━━",
                "<i>Тема полностью меняет графический стиль и рамки команды /profile!</i> 😸\n"
            ]
            coin_themes = [(t_k, t_v) for t_k, t_v in THEMES.items() if t_k != 'default' and t_k not in STARS_ONLY_THEME_IDS]
            for t_k, t_v in coin_themes:
                lines.append(f"• <b>{t_v['name']}</b> — <code>{t_v['price']} 🪙</code>")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            markup = InlineKeyboardMarkup(row_width=2)
            btns = [InlineKeyboardButton(f"{t_v['name']} • {t_v['price']} 🪙", callback_data=f"buy_theme_{t_k}:{user_id}") for t_k, t_v in coin_themes]
            for i in range(0, len(btns), 2):
                markup.add(*btns[i:i+2])
            markup.add(InlineKeyboardButton("🔙 Назад в магазин", callback_data=f"shop_main:{user_id}"))
            try: bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('buy_theme_'):
            t_key = action_data.replace('buy_theme_', '')
            if t_key in THEMES:
                if t_key in STARS_ONLY_THEME_IDS:
                    bot.answer_callback_query(call.id, '⭐️ Эта тема доступна только в /stars. В обычном магазине её купить нельзя.', show_alert=True)
                    return
                theme = THEMES[t_key]
                econ = get_user_econ(user_id, user_name, username=user_username)
                purchased = econ.setdefault('purchased_themes', ['default'])
                if t_key in purchased:
                    bot.answer_callback_query(call.id, "❌ Эта тема уже куплена! 😾", show_alert=True)
                    return
                if econ['balance'] < theme['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {theme['price']} 🪙! 😿", show_alert=True)
                    return
                _adjust_balance(econ, -(theme['price']))
                purchased.append(t_key)
                econ['profile_theme'] = t_key
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Куплена тема {theme['name']}! 😻", show_alert=True)
                send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)

        elif action_data.startswith('set_theme_'):
            t_key = action_data.replace('set_theme_', '')
            econ = get_user_econ(user_id, user_name, username=user_username)
            if t_key in econ.get('purchased_themes', ['default']):
                econ['profile_theme'] = t_key
                mark_dirty()
                bot.answer_callback_query(call.id, f"✅ Установлен стиль: {THEMES[t_key]['name']}! 😸")
                send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)

        # САПЁР
        elif action_data.startswith('msz_'):
            m_parts = action_data.split('_')
            game_id = f"{m_parts[1]}_{m_parts[2]}_{m_parts[3]}"
            try:
                chosen_size = int(m_parts[4])
            except (IndexError, ValueError):
                bot.answer_callback_query(call.id, "❌ Некорректный размер поля.", show_alert=True)
                return
            if chosen_size not in (3, 4, 5, 6):
                bot.answer_callback_query(call.id, "❌ Такой размер поля недоступен.", show_alert=True)
                return
            game = active_mines.get(game_id)
            if not game:
                bot.answer_callback_query(call.id, "❌ Игра устарела!", show_alert=True)
                return
            if user_id != game.get('user_id'):
                bot.answer_callback_query(call.id, '❌ Это не ваша игра! 😾', show_alert=True)
                return
            game['size'] = chosen_size
            markup = InlineKeyboardMarkup(row_width=3)
            mines_options = [1, 2, 3, 5] if chosen_size == 3 else [2, 3, 5, 8] if chosen_size == 4 else [3, 5, 8, 12] if chosen_size == 5 else [4, 6, 9, 12, 16]
            btns = [InlineKeyboardButton(f"💣 {cnt} мин", callback_data=f"mbm_{game_id}_{cnt}:{user_id}") for cnt in mines_options]
            markup.add(*btns)
            markup.add(InlineKeyboardButton("❌ Отмена (вернуть ставку)", callback_data=f"mcancel_{game_id}:{user_id}"))

            try:
                bot.edit_message_text(
                    f"💣 <b>НАСТРОЙКА ИГРЫ «САПЁР» ({chosen_size}х{chosen_size})</b> 😺\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 Ставка: <b>{game['bet']} 🪙</b>\n\n"
                    f"Шаг 2: <b>Сколько мин разместить на поле?</b>\n"
                    f"<i>(Больше мин = выше множитель выигрыша!)</i> 😻",
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    reply_markup=markup,
                    parse_mode='HTML'
                )
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('mbm_'):
            m_parts = action_data.split('_')
            try:
                game_id = f"{m_parts[1]}_{m_parts[2]}_{m_parts[3]}"
                mines_count = int(m_parts[4])
            except (IndexError, ValueError):
                bot.answer_callback_query(call.id, "❌ Некорректное количество мин.", show_alert=True)
                return
            game = active_mines.get(game_id)
            if not game:
                bot.answer_callback_query(call.id, "❌ Игра устарела!", show_alert=True)
                return
            if user_id != game.get('user_id'):
                bot.answer_callback_query(call.id, '❌ Это не ваша игра! 😾', show_alert=True)
                return

            total_cells = game['size'] * game['size']
            allowed_mines = {3: {1, 2, 3, 5}, 4: {2, 3, 5, 8}, 5: {3, 5, 8, 12}, 6: {4, 6, 9, 12, 16}}
            if mines_count not in allowed_mines.get(int(game.get('size', 4)), set()) or mines_count >= total_cells:
                bot.answer_callback_query(call.id, "❌ Некорректное количество мин для этого поля.", show_alert=True)
                return
            game['bombs'] = set(random.sample(range(total_cells), mines_count))
            text_board, markup = render_mines_board(game_id)
            try: bot.edit_message_text(text_board, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('mop_'):
            m_parts = action_data.split('_')
            game_id = f"{m_parts[1]}_{m_parts[2]}_{m_parts[3]}"
            cell_idx = int(m_parts[4])
            game = active_mines.get(game_id)

            if not game or game.get('finished'):
                bot.answer_callback_query(call.id, "❌ Игра уже завершена! 😿", show_alert=True)
                return
            if user_id != game['user_id']:
                bot.answer_callback_query(call.id, "❌ Это не ваше игровое поле! 😾", show_alert=True)
                return

            total_cells = game['size'] * game['size']
            if cell_idx < 0 or cell_idx >= total_cells:
                bot.answer_callback_query(call.id, '❌ Некорректная клетка.', show_alert=True)
                return
            mines_count = len(game['bombs'])

            if cell_idx in game['bombs']:
                game['finished'] = True
                text_board, markup = render_mines_board(game_id)
                loss_text = (
                    f"💥 <b>БАБАХ! ВЫ НАСТУПИЛИ НА МИНУ!</b> 🙀\n\n"
                    f"💸 Ставка <b>{game['bet']} Ня-коинов 🪙</b> сгорела...\n\n{text_board}"
                )
                try: bot.edit_message_text(loss_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
                del active_mines[game_id]
                return
            else:
                game['revealed'].add(cell_idx)
                safe_opened = len(game['revealed'])
                game['current_multiplier'] = calculate_mines_multiplier(total_cells, mines_count, safe_opened)

                max_safe = total_cells - mines_count
                if safe_opened >= max_safe:
                    game['finished'] = True
                    win_amt = int(game['bet'] * game['current_multiplier'])
                    win_amt = process_casino_win(win_amt)
                    add_coins(user_id, user_name, win_amt, username=user_username)
                    add_account_exp(user_id, user_name, 50, username=user_username)
                    check_achievements(user_id, user_name, 'mines_wins', 1, chat_id, username=user_username)
                    mark_dirty()

                    text_board, markup = render_mines_board(game_id)
                    win_text = (
                        f"🏆 <b>НЕВЕРОЯТНО! ВСЕ {max_safe} КРИСТАЛЛОВ НАЙДЕНЫ!</b> 😻\n\n"
                        f"💰 Начислено: <b>+{win_amt} Ня-коинов 🪙</b> (Коэфф: <b>{game['current_multiplier']:.2f}x</b>)!\n\n{text_board}"
                    )
                    try: bot.edit_message_text(win_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                    except Exception as e: print(f"[NONFATAL ERROR] {e}")
                    del active_mines[game_id]
                    return

                text_board, markup = render_mines_board(game_id)
                try: bot.edit_message_text(text_board, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('mco_'):
            game_id = action_data.replace('mco_', '')
            game = active_mines.get(game_id)
            if not game or game.get('finished'):
                bot.answer_callback_query(call.id, "❌ Игра окончена! 😿", show_alert=True)
                return
            if user_id != game['user_id']:
                bot.answer_callback_query(call.id, "❌ Это не ваша игра! 😾", show_alert=True)
                return

            game['finished'] = True
            win_amt = int(game['bet'] * game['current_multiplier'])
            win_amt = process_casino_win(win_amt)
            add_coins(user_id, user_name, win_amt, username=user_username)
            add_account_exp(user_id, user_name, 15, username=user_username)
            check_achievements(user_id, user_name, 'mines_wins', 1, chat_id, username=user_username)
            mark_dirty()

            text_board, markup = render_mines_board(game_id)
            cash_text = (
                f"💰 <b>ВЫ УСПЕШНО ЗАБРАЛИ КУШ!</b> 😻\n\n"
                f"🎉 Начислено: <b>+{win_amt} Ня-коинов 🪙</b> (Коэффициент: <b>{game['current_multiplier']:.2f}x</b>)!\n\n{text_board}"
            )
            try: bot.edit_message_text(cash_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            del active_mines[game_id]

        elif action_data.startswith('mcancel_'):
            game_id = action_data.replace('mcancel_', '')
            game = active_mines.get(game_id)
            if not game:
                bot.answer_callback_query(call.id, "❌ Игра не найдена или уже завершена! 😿", show_alert=True)
                return
            if user_id != game.get('user_id'):
                bot.answer_callback_query(call.id, "❌ Это не ваша игра! 😾", show_alert=True)
                return
            econ = get_user_econ(user_id, user_name, username=user_username)
            _adjust_balance(econ, game['bet'])
            reverse_casino_bet(game['bet'], chat_id=game.get('chat_id', chat_id))
            mark_dirty()
            del active_mines[game_id]
            try: bot.edit_message_text("❌ Игра отменена, ставка возвращена на баланс. 😸", chat_id=chat_id, message_id=call.message.message_id)
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            bot.answer_callback_query(call.id)

        # КЛАССИЧЕСКИЙ САПЁР
        elif action_data.startswith('cstart_'):
            diff_key = action_data.replace('cstart_', '')
            if diff_key in CSAPER_DIFFICULTIES:
                d_info = CSAPER_DIFFICULTIES[diff_key]
                cols = d_info.get('cols', 5)
                rows = d_info.get('rows', 5)
                game_id = f"cm_{user_id}_{time.time_ns()}"
                active_c_mines[game_id] = {
                    'user_id': user_id,
                    'user_name': user_name,
                    'username': user_username,
                    'cols': cols,
                    'rows': rows,
                    'mines_count': d_info['mines'],
                    'reward': d_info['reward'],
                    'exp': d_info['exp'],
                    'diff_name': d_info['name'],
                    'bombs': set(),
                    'numbers': {},
                    'revealed': set(),
                    'flags': set(),
                    'mode': 'dig',
                    'first_click': True,
                    'finished': False,
                    'start_time': time.time()
                }
                text_board, markup = render_classic_mines_board(game_id)
                try: bot.edit_message_text(text_board, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('cmmode_'):
            game_id = action_data.replace('cmmode_', '')
            game = active_c_mines.get(game_id)
            if not game or game.get('finished'): return
            if user_id != game['user_id']: return

            game['mode'] = 'flag' if game.get('mode', 'dig') == 'dig' else 'dig'
            bot.answer_callback_query(call.id, "🚩 Режим флага" if game['mode'] == 'flag' else "⛏ Режим копания")
            text_board, markup = render_classic_mines_board(game_id)
            try: bot.edit_message_text(text_board, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('cmo_'):
            m_parts = action_data.split('_')
            game_id = f"{m_parts[1]}_{m_parts[2]}_{m_parts[3]}"
            cell_arg = m_parts[4]
            game = active_c_mines.get(game_id)

            if not game or game.get('finished'):
                bot.answer_callback_query(call.id, "❌ Игра завершена!", show_alert=True)
                return
            if user_id != game['user_id']:
                bot.answer_callback_query(call.id, "❌ Это не ваша игра!", show_alert=True)
                return

            cols = game.get('cols', 5)
            rows = game.get('rows', 5)
            total_cells = cols * rows

            cell_idx = int(cell_arg)
            if cell_idx < 0 or cell_idx >= total_cells:
                bot.answer_callback_query(call.id, '❌ Некорректная клетка.', show_alert=True)
                return

            if game.get('mode') == 'flag':
                if cell_idx in game['revealed']: return
                if cell_idx in game['flags']: game['flags'].remove(cell_idx)
                else: game['flags'].add(cell_idx)
                text_board, markup = render_classic_mines_board(game_id)
                try: bot.edit_message_text(text_board, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
                bot.answer_callback_query(call.id)
                return

            if cell_idx in game['flags']:
                bot.answer_callback_query(call.id, "🚩 Сначала снимите флаг!", show_alert=True)
                return

            if game.get('first_click', True):
                game['first_click'] = False
                forbidden = set(get_adjacent_indices(cell_idx, cols, rows) + [cell_idx])
                available = [i for i in range(total_cells) if i not in forbidden]
                if len(available) < game['mines_count']:
                    available = [i for i in range(total_cells) if i != cell_idx]
                    
                game['bombs'] = set(random.sample(available, game['mines_count']))
                numbers = {}
                for i in range(total_cells):
                    if i not in game['bombs']:
                        numbers[i] = sum(1 for neighbor in get_adjacent_indices(i, cols, rows) if neighbor in game['bombs'])
                game['numbers'] = numbers

            if cell_idx in game['bombs']:
                game['finished'] = True
                text_board, markup = render_classic_mines_board(game_id)
                loss_text = f"💥 <b>БАБАХ! МИНА СДЕТОНИРОВАЛА!</b> 🙀\n\n{text_board}"
                try: bot.edit_message_text(loss_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
                del active_c_mines[game_id]
                return

            reveal_cascade_cells(game, cell_idx)
            max_safe = total_cells - len(game['bombs'])
            if len(game['revealed']) >= max_safe:
                game['finished'] = True
                reward = game['reward']
                exp_gain = game['exp']
                add_coins(user_id, user_name, reward, username=user_username)
                add_account_exp(user_id, user_name, exp_gain, username=user_username)
                check_achievements(user_id, user_name, 'mines_wins', 1, chat_id, username=user_username)

                text_board, markup = render_classic_mines_board(game_id)
                win_text = f"🏆🧠 <b>ПОЛЕ ПОЛНОСТЬЮ РАЗМИНИРОВАНО!</b> 😻\n\n🎉 Награда: <b>+{reward} Ня-коинов 🪙</b> (+{exp_gain} EXP)!\n\n{text_board}"
                try: bot.edit_message_text(win_text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
                del active_c_mines[game_id]
                return

            text_board, markup = render_classic_mines_board(game_id)
            try: bot.edit_message_text(text_board, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")
            bot.answer_callback_query(call.id)

        # ПИТОМЕЦ
        elif action_data == 'pet_feed':
            econ = get_user_econ(user_id, user_name, username=user_username)
            pet = econ.get('pet')
            if not pet: return
            if pet.get('hunger', 100) >= 100:
                bot.answer_callback_query(call.id, "🍖 Питомец сыт! 😸", show_alert=True)
                return
            if econ['balance'] < 30:
                bot.answer_callback_query(call.id, "❌ Нужно 30 🪙 для корма! 😿", show_alert=True)
                return
            _adjust_balance(econ, -(30))
            pet['hunger'] = min(100, pet.get('hunger', 0) + 35)
            pet['pet_exp'] = pet.get('pet_exp', 0) + 10
            check_achievements(user_id, user_name, 'pet_care', 1, chat_id, username=user_username)
            mark_dirty()
            bot.answer_callback_query(call.id, "🍖 Питомец вкусно покушал (+10 EXP)! 😻")
            render_pet_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'pet_wash':
            econ = get_user_econ(user_id, user_name, username=user_username)
            pet = econ.get('pet')
            if not pet: return
            if pet.get('cleanliness', 100) >= 100:
                bot.answer_callback_query(call.id, "🧼 Питомец уже чистый! 😸", show_alert=True)
                return
            if econ['balance'] < 20:
                bot.answer_callback_query(call.id, "❌ Нужно 20 🪙 на шампунь! 😿", show_alert=True)
                return
            _adjust_balance(econ, -(20))
            pet['cleanliness'] = min(100, pet.get('cleanliness', 0) + 40)
            pet['pet_exp'] = pet.get('pet_exp', 0) + 10
            check_achievements(user_id, user_name, 'pet_care', 1, chat_id, username=user_username)
            mark_dirty()
            bot.answer_callback_query(call.id, "🧼 Питомец искупан до блеска (+10 EXP)! 😻")
            render_pet_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'pet_walk_btn':
            bot.answer_callback_query(call.id)
            process_pet_walk(chat_id, user_id, user_name)

        # БИЗНЕС
        elif action_data.startswith('upg_donor_biz_'):
            b_id = action_data.replace('upg_donor_biz_', '')
            if b_id not in DONOR_BUSINESSES:
                bot.answer_callback_query(call.id, '❌ Донатный бизнес не найден.', show_alert=True)
                return
            econ = get_user_econ(user_id, user_name, username=user_username)
            owned = econ.get('donor_businesses', {})
            if b_id not in owned:
                bot.answer_callback_query(call.id, '❌ Сначала приобретите этот бизнес в донатном магазине.', show_alert=True)
                return
            biz_levels = econ.setdefault('biz_levels', {})
            cur_lvl = max(1, int(biz_levels.get(b_id, 1)))
            if cur_lvl >= 5:
                bot.answer_callback_query(call.id, '❌ Максимальный 5-й уровень.', show_alert=True)
                return
            cost = int(DONOR_BUSINESSES[b_id].get('upgrade_cost', 5000)) * cur_lvl
            if econ.get('balance', 0) < cost:
                bot.answer_callback_query(call.id, f'❌ Нужно {cost:,} 🪙.', show_alert=True)
                return
            # Сначала фиксируем накопленное по старой ставке. Иначе апгрейд
            # задним числом применился бы ко всему времени с прошлого сбора.
            old_profit = _settle_one_business(econ, b_id, time.time(), credit=True)
            _adjust_balance(econ, -(cost))
            biz_levels[b_id] = cur_lvl + 1
            owned[b_id] = cur_lvl + 1
            mark_dirty()
            settled_note = f' Накопленное до апгрейда: +{old_profit:,} 🪙.' if old_profit else ''
            bot.answer_callback_query(call.id, f'🎉 {DONOR_BUSINESSES[b_id]["name"]} улучшен до {cur_lvl+1} уровня!{settled_note}')
            # Показываем уже новую ставку и новый баланс.
            render_business_view(chat_id, user_id, user_name, message_id=call.message.message_id)

        elif action_data.startswith('upg_biz_'):
            b_id = action_data.replace('upg_biz_', '')
            if b_id in BUSINESSES:
                b_info = BUSINESSES[b_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                biz_levels = econ.setdefault('biz_levels', {})
                cur_lvl = max(1, min(5, int(biz_levels.get(b_id, 1) or 1)))
                if cur_lvl >= 5:
                    bot.answer_callback_query(call.id, "❌ Достигнут максимальный 5-й уровень! 😸", show_alert=True)
                    return
                cost = b_info['upgrade_cost'] * cur_lvl
                if econ['balance'] < cost:
                    bot.answer_callback_query(call.id, f"❌ Нужно {cost:,} 🪙! 😿", show_alert=True)
                    return
                # Зафиксировать старую ставку до повышения уровня.
                _settle_one_business(econ, b_id, time.time(), credit=True)
                _adjust_balance(econ, -(cost))
                biz_levels[b_id] = cur_lvl + 1
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 {b_info['short']} улучшен(а) до {cur_lvl+1} уровня! 😻")
                render_business_view(chat_id, user_id, user_name, message_id=call.message.message_id)

        elif action_data.startswith('buy_biz_'):
            b_id = action_data.replace('buy_biz_', '')
            if b_id in BUSINESSES:
                b_info = BUSINESSES[b_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                user_biz = econ.setdefault('businesses', {})
                biz_levels = econ.setdefault('biz_levels', {})
                if b_id in user_biz:
                    bot.answer_callback_query(call.id, "❌ Этот бизнес уже куплен! 😾", show_alert=True)
                    return
                if econ['balance'] < b_info['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {b_info['price']} 🪙! 😿", show_alert=True)
                    return
                purchase_now = time.time()
                _adjust_balance(econ, -(b_info['price']))
                user_biz[b_id] = purchase_now
                econ.setdefault('biz_last_collect', {})[b_id] = purchase_now
                econ.setdefault('biz_income_carry', {})[b_id] = 0.0
                biz_levels[b_id] = 1
                check_achievements(user_id, user_name, 'biz_bought', 1, chat_id, username=user_username)
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Вы приобрели {b_info['name']}! 😻")
                render_business_view(chat_id, user_id, user_name, message_id=call.message.message_id)

        elif action_data == 'business_refresh':
            render_business_view(chat_id, user_id, user_name, message_id=call.message.message_id)
            bot.answer_callback_query(call.id, '🔄 Бизнесы обновлены! 😸')
            return

        elif action_data == 'collect_biz_profit':
            econ = get_user_econ(user_id, user_name, username=user_username)
            if not (econ.get('businesses') or econ.get('donor_businesses')):
                bot.answer_callback_query(call.id, '❌ Сначала купите обычный бизнес через /business или донатный через /stars.', show_alert=True)
                return
            now = time.time()
            base_profit = collect_business_base_profit(econ, now)
            if base_profit <= 0:
                bot.answer_callback_query(call.id, "⏳ Пока накопилось меньше 1 🪙. Подождите немного! 😿", show_alert=True)
                return
            total_profit, event_text = _apply_business_payout_modifiers(econ, base_profit, chat_id, user_id, user_name)
            _adjust_balance(econ, total_profit)
            mark_dirty()
            bot.answer_callback_query(call.id, f"💰 Собрано: +{total_profit:,} 🪙! 😻")
            render_business_view(chat_id, user_id, user_name, message_id=call.message.message_id)

        elif action_data.startswith('equip_veh_'):
            v_id = action_data.replace('equip_veh_', '')
            econ = get_user_econ(user_id, user_name, username=user_username)
            owned = econ.setdefault('vehicle_inventory', [])
            if v_id not in owned or (v_id not in VEHICLES and v_id not in DONOR_VEHICLES):
                bot.answer_callback_query(call.id, "❌ Эта машина не находится в вашем гараже.", show_alert=True)
                return
            econ['equipped_vehicle'] = v_id
            econ['vehicle'] = v_id
            mark_dirty()
            info = DONOR_VEHICLES.get(v_id) or VEHICLES.get(v_id)
            bot.answer_callback_query(call.id, f"🚘 Надета: {info['name']}")
            render_garage_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data.startswith('buy_veh_'):
            v_id = action_data.replace('buy_veh_', '')
            if v_id in VEHICLES:
                v_info = VEHICLES[v_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                owned = econ.setdefault('vehicle_inventory', [])
                if v_id in owned:
                    bot.answer_callback_query(call.id, "❌ Этот транспорт уже куплен. Надеть его можно из гаража! 😸", show_alert=True)
                    return
                if econ['balance'] < v_info['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {v_info['price']} 🪙! 😿", show_alert=True)
                    return

                _adjust_balance(econ, -(v_info['price']))
                owned.append(v_id)
                # Новая машина автоматически надевается только если ничего не надето.
                if not econ.get('equipped_vehicle') and not econ.get('vehicle'):
                    econ['equipped_vehicle'] = v_id
                    econ['vehicle'] = v_id
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Вы приобрели {v_info['name']}! Машина сохранена в гараже. 😻")
                render_garage_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data.startswith('buy_rod_'):
            r_id = action_data.replace('buy_rod_', '')
            if r_id in RODS:
                r_info = RODS[r_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                owned = econ.setdefault('rod_inventory', [])
                if r_id not in owned:
                    if econ['balance'] < r_info['price']:
                        bot.answer_callback_query(call.id, f"❌ Нужно {r_info['price']} 🪙! 😿", show_alert=True)
                        return
                    _adjust_balance(econ, -(r_info['price']))
                    owned.append(r_id)
                    action_text = f"🎉 Куплена и надета {r_info['name']}! 😻"
                else:
                    action_text = f"✅ Надета {r_info['name']}! 😸"
                econ['equipped_rod'] = r_id
                mark_dirty()
                bot.answer_callback_query(call.id, action_text)
                return

        elif action_data.startswith('buy_bow_'):
            b_id = action_data.replace('buy_bow_', '')
            if b_id in BOWS:
                b_info = BOWS[b_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                owned = econ.setdefault('bow_inventory', [])
                if b_id not in owned:
                    if econ['balance'] < b_info['price']:
                        bot.answer_callback_query(call.id, f"❌ Нужно {b_info['price']} 🪙! 😿", show_alert=True)
                        return
                    _adjust_balance(econ, -(b_info['price']))
                    owned.append(b_id)
                    action_text = f"🎉 Куплен и надет {b_info['name']}! 😻"
                else:
                    action_text = f"✅ Надет {b_info['name']}! 😸"
                econ['equipped_bow'] = b_id
                mark_dirty()
                bot.answer_callback_query(call.id, action_text)
                return

        # БАНК КНОПКИ
        elif action_data == 'bank_refresh':
            render_bank_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'bank_dep_100':
            econ = get_user_econ(user_id, user_name, username=user_username)
            if econ['balance'] < 100:
                bot.answer_callback_query(call.id, "❌ Недостаточно средств на руках! 😿", show_alert=True)
                return
            _adjust_balance(econ, -(100))
            econ['bank_deposit'] = econ.get('bank_deposit', 0) + 100
            check_achievements(user_id, user_name, 'bank_deposit', 100, chat_id, username=user_username)
            mark_dirty()
            bot.answer_callback_query(call.id, "✅ Внесено 100 🪙 на депозит! 😸")
            render_bank_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'bank_dep_all':
            econ = get_user_econ(user_id, user_name, username=user_username)
            b = econ.get('balance', 0)
            if b <= 0:
                bot.answer_callback_query(call.id, "❌ У вас нет наличных коинов! 😿", show_alert=True)
                return
            _set_balance(econ, 0)
            econ['bank_deposit'] = econ.get('bank_deposit', 0) + b
            check_achievements(user_id, user_name, 'bank_deposit', b, chat_id, username=user_username)
            mark_dirty()
            bot.answer_callback_query(call.id, f"✅ Внесено {b} 🪙 на депозит! 😻")
            render_bank_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'bank_wd_100':
            econ = get_user_econ(user_id, user_name, username=user_username)
            if econ.get('bank_deposit', 0) < 100:
                bot.answer_callback_query(call.id, "❌ В банке меньше 100 🪙! 😿", show_alert=True)
                return
            econ['bank_deposit'] -= 100
            _adjust_balance(econ, 100)
            mark_dirty()
            bot.answer_callback_query(call.id, "✅ Снято 100 🪙 с депозита! 😸")
            render_bank_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'bank_wd_all':
            econ = get_user_econ(user_id, user_name, username=user_username)
            dep = econ.get('bank_deposit', 0)
            if dep <= 0:
                bot.answer_callback_query(call.id, "❌ В банке нет средств! 😿", show_alert=True)
                return
            econ['bank_deposit'] = 0
            _adjust_balance(econ, dep)
            mark_dirty()
            bot.answer_callback_query(call.id, f"✅ Снят весь вклад: {dep} 🪙! 😻")
            render_bank_view(chat_id, user_id, user_name, call.message.message_id)

        # ЛОТЕРЕЯ
        elif action_data in ['buy_ticket_1', 'buy_ticket_5']:
            count = 1 if action_data == 'buy_ticket_1' else 5
            with LOTTERY_LOCK:
                lottery = db.setdefault('lottery', {'tickets': {}, 'pot': 0, 'last_draw': 0})
                t_dict = lottery.setdefault('tickets', {})
                current_total = sum(int(v or 0) for v in t_dict.values())
                if current_total + count > 10:
                    remaining = max(0, 10 - current_total)
                    bot.answer_callback_query(call.id, f'❌ Свободно только {remaining} мест(а) до тиража. Купите по 1 билету.', show_alert=True)
                    return
                cost = count * 100
                econ = get_user_econ(user_id, user_name, username=user_username)
                if econ['balance'] < cost:
                    bot.answer_callback_query(call.id, f"❌ Нужно {cost} 🪙! 😿", show_alert=True)
                    return

                _adjust_balance(econ, -(cost))
                t_dict[str(user_id)] = t_dict.get(str(user_id), 0) + count
                lottery['pot'] = lottery.get('pot', 0) + cost

                total_tickets = sum(int(v or 0) for v in t_dict.values())
                draw_result = None
                if total_tickets >= 10:
                    pool = []
                    for uid, t_count in t_dict.items(): pool.extend([uid] * int(t_count or 0))
                    winner_id = int(random.choice(pool))
                    win_pot = int(lottery.get('pot', 0) or 0)
                    w_econ = get_user_econ(user_id=winner_id)
                    _adjust_balance(w_econ, win_pot)
                    lottery['tickets'] = {}
                    lottery['pot'] = 0
                    lottery['last_draw'] = time.time()
                    draw_result = (winner_id, win_pot, w_econ.get('display_name', 'Игрок'))
                    mark_dirty()
                else:
                    mark_dirty()

            bot.answer_callback_query(call.id, f"🎟 Куплено {count} бил.! 😸")
            if draw_result:
                winner_id, win_pot, winner_name = draw_result
                w_link = make_link(chat_id, winner_name, winner_id, ping=True)
                log_event('ЛОТЕРЕЯ: ДЖЕКПОТ', f'Победитель {w_link} сорвал джекпот <b>{win_pot} 🪙</b>!')
                bot.send_message(chat_id, f"🎉 <b>РОЗЫГРЫШ ЛОТЕРЕИ СОСТОЯЛСЯ!</b> 😻\n\n🏆 Джекпот <b>+{win_pot} Ня-коинов 🪙</b> забирает {w_link}!\nСледующий тираж уже открыт! 😸", parse_mode='HTML')
            else:
                render_lottery_view(chat_id, user_id, user_name, call.message.message_id)

        # ЧАТ-ДРОПЫ
        elif raw_data.startswith('claim_drop_') or action_data.startswith('claim_drop_'):
            drop_id = raw_data.replace('claim_', '').split(':')[0]
            drop = active_drops.get(drop_id)
            if not drop or drop.get('claimed'):
                bot.answer_callback_query(call.id, "❌ Этот подарок уже кто-то забрал! 😿", show_alert=True)
                return

            if int(drop.get('chat_id', 0) or 0) != int(chat_id):
                bot.answer_callback_query(call.id, "❌ Этот подарок принадлежит другому чату! 😾", show_alert=True)
                return
            drop['claimed'] = True
            reward = max(0, int(drop.get('reward', 0) or 0))
            add_coins(user_id, user_name, reward, username=user_username)
            add_account_exp(user_id, user_name, 15, username=user_username)

            bot.answer_callback_query(call.id, f"🎉 Вы забрали +{reward} 🪙! 😻")
            u_link = make_link(chat_id, user_name, user_id, ping=True)
            try:
                bot.edit_message_text(
                    f"🎁 <b>ПОДАРОК ЗАБРАН!</b> 😺\n\nБыстрее всех оказался(лась) {u_link} и забрал(а) <b>+{reward} Ня-коинов 🪙</b>! 😸",
                    chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML'
                )
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        # ТРЕНИРОВКА ОПЫТА
        elif action_data == 'train_exp_btn':
            success, text_resp = train_work_exp(user_id, user_name, username=user_username)
            bot.answer_callback_query(call.id, text_resp.replace('<b>', '').replace('</b>', ''), show_alert=True)

        # РАБОТА
        elif action_data.startswith('do_job_'):
            job_id = action_data.replace('do_job_', '')
            if job_id in JOBS:
                job = JOBS[job_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                if econ.get('work_exp', 0) < job['req_exp']:
                    bot.answer_callback_query(call.id, f"❌ Нужно минимум {job['req_exp']} EXP опыта! 😿", show_alert=True)
                    return
                now = time.time()
                cooldown = 1800
                left = cooldown_text(econ.get('last_work_time', 0), cooldown, econ)
                if left:
                    bot.answer_callback_query(call.id, f"⏳ Отдохните еще: {left} 😿", show_alert=True)
                    return
                econ['last_work_time'] = now
                if random.randint(1, 100) <= job['chance']:
                    pay = random.randint(job['min_pay'], job['max_pay'])
                    pay = int(pay * (1 + pet_bonus(econ, 'work_bonus') + get_title_work_bonus(econ) + get_vip_work_bonus(econ)))
                    _adjust_balance(econ, pay)
                    econ['work_exp'] = econ.get('work_exp', 0) + job['exp_gain']
                    add_account_exp(user_id, user_name, job['exp_gain'], username=user_username)
                    check_achievements(user_id, user_name, 'work_shifts', 1, chat_id, username=user_username)
                    mark_dirty()
                    bot.answer_callback_query(call.id, f"✅ Зарплата: +{pay} 🪙 (+{job['exp_gain']} EXP)! 😻", show_alert=True)
                    bot.send_message(chat_id, f"💼 {make_link(chat_id, user_name, user_id, ping=True)} заработал(а) <b>+{pay} 🪙</b> на должности <b>{job['name']}</b>! 😸", parse_mode='HTML')
                else:
                    econ['work_exp'] = econ.get('work_exp', 0) + 2
                    add_account_exp(user_id, user_name, 2, username=user_username)
                    mark_dirty()
                    bot.answer_callback_query(call.id, "❌ Вы ошиблись на смене! Получено +2 EXP. 😿", show_alert=True)

        # БРАКИ
        elif raw_data.startswith('m_yes_') or raw_data.startswith('m_no_'):
            prop_id = raw_data[6:].split(':')[0]
            prop = pending_marriages.get(prop_id)
            if not prop:
                bot.answer_callback_query(call.id, "❌ Предложение устарело! 😿", show_alert=True)
                return
            if user_id != prop['to_id'] and prop['to_id'] is not None:
                bot.answer_callback_query(call.id, "❌ Это предложение адресовано не вам! 😾", show_alert=True)
                return

            if raw_data.startswith('m_yes_'):
                with serialized_multi_user_action(int(user_id), int(prop['from_id'])):
                    live_prop = pending_marriages.get(prop_id)
                    if not live_prop or int(live_prop.get('to_id')) != int(user_id):
                        bot.answer_callback_query(call.id, "❌ Предложение уже недействительно! 😿", show_alert=True)
                        return
                    from_econ = get_user_econ(int(live_prop['from_id']), live_prop['from_tag'])
                    to_econ = get_user_econ(user_id, user_name, username=user_username)
                    if from_econ.get('marriage') or to_econ.get('marriage'):
                        pending_marriages.pop(prop_id, None)
                        bot.answer_callback_query(call.id, "❌ Один из пользователей уже состоит в браке! 😿", show_alert=True)
                        return
                    m_time = time.time()
                    from_econ['marriage'] = {'partner_id': user_id, 'partner_name': user_name, 'ring': live_prop['ring'], 'married_at': m_time, 'vault': 0}
                    to_econ['marriage'] = {'partner_id': live_prop['from_id'], 'partner_name': live_prop['from_tag'], 'ring': live_prop['ring'], 'married_at': m_time, 'vault': 0}
                    check_achievements(live_prop['from_id'], live_prop['from_tag'], 'marriages', 1, chat_id)
                    check_achievements(user_id, user_name, 'marriages', 1, chat_id, username=user_username)
                    pending_marriages.pop(prop_id, None)
                    mark_dirty()
                prop = live_prop
                ring_emoji = RINGS.get(prop['ring'], {}).get('emoji', '💍')
                try:
                    bot.edit_message_text(
                        f"💒 <b>Горько! Свадьба состоялась!</b> 🎉 😻\n\n{ring_emoji} {make_link(chat_id, prop['from_tag'], prop['from_id'], ping=True)} и {make_link(chat_id, user_name, user_id, ping=True)} теперь законные супруги! ❤️",
                        chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML'
                    )
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
            else:
                with CALLBACK_STATE_LOCK:
                    pending_marriages.pop(prop_id, None)
                try:
                    bot.edit_message_text(
                        f"💔 {make_link(chat_id, user_name, user_id, ping=False)} отклонил(а) предложение руки и сердца. 😿",
                        chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML'
                    )
                except Exception as e: print(f"[NONFATAL ERROR] {e}")

        # БЛЭКДЖЕК
        elif action_data.startswith('bj_hit_') or action_data.startswith('bj_stand_'):
            game_id = action_data.split('_', 2)[2]
            game = active_bj_games.get(game_id)
            if not game or game.get('finished'):
                bot.answer_callback_query(call.id, "❌ Игра окончена! 😿", show_alert=True)
                return
            if user_id != game['user_id']:
                bot.answer_callback_query(call.id, "❌ Это не ваша игра! 😾", show_alert=True)
                return

            if action_data.startswith('bj_hit_'):
                if len(game['deck']) == 0:
                    game['deck'] = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 2
                    random.shuffle(game['deck'])
                game['p_cards'].append(game['deck'].pop())
                p_score = calculate_bj_score(game['p_cards'])
                if p_score > 21:
                    game['finished'] = True
                    try:
                        bot.edit_message_text(f"💥 <b>Перебор ({p_score})!</b> Вы проиграли <b>{game['bet']} 🪙</b>. 😿\nВаши карты: {game['p_cards']}", chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML')
                    except Exception as e: print(f"[NONFATAL ERROR] {e}")
                    del active_bj_games[game_id]
                    return
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🃏 Взять карту", callback_data=f"bj_hit_{game_id}:{user_id}"), InlineKeyboardButton("✋ Хватит", callback_data=f"bj_stand_{game_id}:{user_id}"))
                try:
                    bot.edit_message_text(f"🃏 Ваши карты: {game['p_cards']} (Сумма: <b>{p_score}</b>)\nДилер: [{game['d_cards'][0]}, ❓] 😺", chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
            else:
                game['finished'] = True
                p_score = calculate_bj_score(game['p_cards'])
                while calculate_bj_score(game['d_cards']) < 17:
                    if len(game['deck']) == 0:
                        game['deck'] = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 2
                        random.shuffle(game['deck'])
                    game['d_cards'].append(game['deck'].pop())
                d_score = calculate_bj_score(game['d_cards'])

                if d_score > 21 or p_score > d_score:
                    win = process_casino_win(int(game['bet'] * 1.8))
                    add_coins(user_id, user_name, win, username=user_username)
                    add_account_exp(user_id, user_name, 10, username=user_username)
                    res = f"🎉 <b>Вы выиграли +{win} 🪙 (x1.8)!</b> 😻"
                elif p_score == d_score:
                    add_coins(user_id, user_name, game['bet'], username=user_username)
                    reverse_casino_bet(game['bet'], chat_id=game.get('chat_id', chat_id))
                    res = f"🤝 <b>Ничья!</b> Ставка {game['bet']} 🪙 возвращена. 😸"
                else:
                    res = f"💸 <b>Дилер выиграл!</b> Проигрыш {game['bet']} 🪙. 😿"

                try:
                    bot.edit_message_text(f"{res}\n\n👤 Ваши карты: {game['p_cards']} ({p_score})\n🤖 Карты дилера: {game['d_cards']} ({d_score})", chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
                del active_bj_games[game_id]

        # ЦУЕФА
        elif action_data.startswith('rps_'):
            m_rps = re.match(r"^rps_([rsp])_(rps_\d+_\d+_\d+)$", action_data)
            if not m_rps:
                bot.answer_callback_query(call.id, "❌ Ошибка данных дуэли!", show_alert=True)
                return
            choice = m_rps.group(1)
            game_id = m_rps.group(2)
            game = active_rps_games.get(game_id)
            if not game or game.get('finished'):
                bot.answer_callback_query(call.id, "❌ Игра уже завершена или устарела!", show_alert=True)
                return

            if user_id == game['p1_id']:
                if game['p1_choice']:
                    bot.answer_callback_query(call.id, "Вы уже сделали выбор! Ожидаем соперника. ⏳", show_alert=True)
                    return
                game['p1_choice'] = choice
            elif user_id == game['p2_id']:
                if game['p2_choice']:
                    bot.answer_callback_query(call.id, "Вы уже сделали выбор! Ожидаем соперника. ⏳", show_alert=True)
                    return
                game['p2_choice'] = choice
            else:
                bot.answer_callback_query(call.id, "❌ Вы не являетесь участником этой дуэли! 😾", show_alert=True)
                return

            bot.answer_callback_query(call.id, "✅ Ваш выбор принят! 😸")

            if game['p1_choice'] and game['p2_choice']:
                game['finished'] = True
                c_map = {'r': '🪨 Камень', 's': '✂️ Ножницы', 'p': '📄 Бумага'}
                c1, c2 = game['p1_choice'], game['p2_choice']
                bet = game['bet']
                total_pot = bet * 2
                
                if c1 == c2:
                    add_coins(game['p1_id'], game['p1_tag'], bet)
                    add_coins(game['p2_id'], game['p2_tag'], bet)
                    res = "🤝 <b>Ничья!</b> Ставки возвращены обоим игрокам. 😸"
                elif (c1 == 'r' and c2 == 's') or (c1 == 's' and c2 == 'p') or (c1 == 'p' and c2 == 'r'):
                    win_val = int(total_pot * 0.95)
                    add_coins(game['p1_id'], game['p1_tag'], win_val)
                    res = f"🏆 Победил(а) {make_link(chat_id, game['p1_tag'], game['p1_id'], ping=True)}! (+{win_val} 🪙) 😻"
                else:
                    win_val = int(total_pot * 0.95)
                    add_coins(game['p2_id'], game['p2_tag'], win_val)
                    res = f"🏆 Победил(а) {make_link(chat_id, game['p2_tag'], game['p2_id'], ping=True)}! (+{win_val} 🪙) 😻"

                try:
                    bot.edit_message_text(
                        f"✌️ <b>ИТОГИ ДУЭЛИ ЦУ-Е-ФА:</b> 😺\n━━━━━━━━━━━━━━━━━━━━\n"
                        f"• {game['p1_tag']}: {c_map[c1]}\n"
                        f"• {game['p2_tag']}: {c_map[c2]}\n\n{res}",
                        chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML'
                    )
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
                active_rps_games.pop(game_id, None)

        # СНЯТИЕ РЕСТА
        elif action_data == 'rest_remove_menu':
            if not is_admin(chat_id, user_id):
                bot.answer_callback_query(call.id, "❌ Только для администраторов чата!", show_alert=True)
                return

            chat_rests = db.get('rests', {}).get(str(chat_id), {})
            if not chat_rests:
                bot.answer_callback_query(call.id, "🌴 В ресте никого нет!", show_alert=True)
                return

            markup = InlineKeyboardMarkup(row_width=1)
            for r_key, info in chat_rests.items():
                u_name = info.get('user_name', r_key)
                markup.add(InlineKeyboardButton(f"❌ Снять: {u_name}", callback_data=f"del_rest_user_{r_key}:{user_id}"))
            markup.add(InlineKeyboardButton("🔙 Назад", callback_data=f"rest_cancel_menu:{user_id}"))

            try:
                bot.edit_message_text(
                    "🗑 <b>ВЫБЕРИТЕ ПОЛЬЗОВАТЕЛЯ ДЛЯ СНЯТИЯ С РЕСТА:</b> 😺\n━━━━━━━━━━━━━━━━━━━━\nНажмите на кнопку с именем нужного человека:",
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    reply_markup=markup,
                    parse_mode='HTML'
                )
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('del_rest_user_'):
            if not is_admin(chat_id, user_id):
                bot.answer_callback_query(call.id, "❌ Только для администраторов чата!", show_alert=True)
                return

            target_r_key = action_data.replace('del_rest_user_', '')
            str_chat = str(chat_id)
            chat_rests = db.get('rests', {}).get(str_chat, {})

            if target_r_key in chat_rests:
                info = chat_rests.pop(target_r_key)
                u_name = info.get('user_name', target_r_key)
                t_uid = info.get('user_id')
                
                add_to_history(str_chat, u_name, 'Снят', 'Досрочно по кнопке админом', t_uid, "Снят рест (кнопка)")
                mark_dirty()

                u_link = make_link(chat_id, u_name, t_uid, ping=True)
                log_event('РЕСТ СНЯТ (КНОПКА)', f'Чат: <code>{chat_id}</code>\nАдмин: ID:{user_id}\nПользователь: {u_link}')
                bot.answer_callback_query(call.id, f"✅ Рест с {u_name} снят!")
                try:
                    bot.edit_message_text(f"🗑 Рест с {u_link} успешно снят по кнопке! 😺", chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML')
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
            else:
                bot.answer_callback_query(call.id, "❌ Пользователь уже не в ресте!", show_alert=True)

        elif action_data == 'rest_cancel_menu':
            chat_rests = db.get('rests', {}).get(str(chat_id), {})
            if not chat_rests:
                try: bot.edit_message_text('🌴 В данный момент никто не находится в ресте. 😸', chat_id=chat_id, message_id=call.message.message_id)
                except Exception as e: print(f"[NONFATAL ERROR] {e}")
                return

            resp = '📋 <b>СПИСОК АКТИВНЫХ РЕСТОВ:</b> 😺\n━━━━━━━━━━━━━━━━━━━━\n'
            for r_key, info in chat_rests.items():
                u_name = info.get('user_name', r_key)
                u_id = info.get('user_id')
                resp += f"• {make_link(chat_id, u_name, u_id, ping=False)} — {info['duration']} (Причина: {html.escape(str(info.get('reason', 'Не указана')))})\n"
            resp += '━━━━━━━━━━━━━━━━━━━━'

            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🗑 Снять рест (Выбрать)", callback_data=f"rest_remove_menu:{user_id}"))
            try: bot.edit_message_text(resp, chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        # НАСТРОЙКИ
        elif action_data == 'set_max_days':
            if not is_admin(chat_id, user_id): return
            sett = get_chat_settings(chat_id)
            sett['max_days'] = None
            mark_dirty()
            bot.answer_callback_query(call.id, '✅ Лимит реста полностью отключён! 😸')
            render_settings_view(chat_id, user_id=user_id, message_id=call.message.message_id)

        elif action_data == 'toggle_rp':
            if not is_admin(chat_id, user_id): return
            sett = get_chat_settings(chat_id)
            sett['rp_enabled'] = not sett.get('rp_enabled', True)
            mark_dirty()
            bot.answer_callback_query(call.id, f"🎭 РП-команды {'включены' if sett['rp_enabled'] else 'выключены'}!")
            render_settings_view(chat_id, user_id=user_id, message_id=call.message.message_id)

        elif action_data == 'toggle_flood':
            if not is_admin(chat_id, user_id): return
            sett = get_chat_settings(chat_id)
            sett['flood_protection'] = not sett.get('flood_protection', False)
            mark_dirty()
            bot.answer_callback_query(call.id, f"🛡 Антифлуд {'включён' if sett['flood_protection'] else 'выключен'}!")
            render_settings_view(chat_id, user_id=user_id, message_id=call.message.message_id)

        elif action_data == 'toggle_flood_admins':
            if not is_chat_owner(chat_id, user_id):
                bot.answer_callback_query(call.id, "❌ Эту настройку может менять только владелец чата!", show_alert=True)
                return
            sett = get_chat_settings(chat_id)
            sett['flood_admins'] = not sett.get('flood_admins', False)
            mark_dirty()
            bot.answer_callback_query(call.id, f"👮 Антифлуд для админов {'включён' if sett['flood_admins'] else 'выключен'}!")
            render_settings_view(chat_id, user_id=user_id, message_id=call.message.message_id)

        elif action_data == 'toggle_reactions':
            if not is_admin(chat_id, user_id): return
            sett = get_chat_settings(chat_id)
            sett['auto_reactions'] = not sett.get('auto_reactions', True)
            mark_dirty()
            bot.answer_callback_query(call.id, f"✨ Авто-реакции {'включены' if sett['auto_reactions'] else 'выключены'}!")
            render_settings_view(chat_id, user_id=user_id, message_id=call.message.message_id)

        elif action_data == 'toggle_welcome':
            if not is_admin(chat_id, user_id): return
            sett = get_chat_settings(chat_id)
            sett['welcome_enabled'] = not sett.get('welcome_enabled', True)
            mark_dirty()
            bot.answer_callback_query(call.id, f"👋 Приветствия {'включены' if sett['welcome_enabled'] else 'выключены'}!")
            render_settings_view(chat_id, user_id=user_id, message_id=call.message.message_id)

        elif action_data == 'set_remind_time':
            if not is_admin(chat_id, user_id): return
            sett = get_chat_settings(chat_id)
            opts = [10, 60, 1440]
            next_opt = opts[(opts.index(sett.get('remind_minutes', 60)) + 1) % len(opts)]
            sett['remind_minutes'] = next_opt
            mark_dirty()
            bot.answer_callback_query(call.id, f'✅ Напоминание установлено за {next_opt} мин! 😸')
            render_settings_view(chat_id, user_id=user_id, message_id=call.message.message_id)

        elif action_data.startswith('set_user_lang_'):
            if chat_id <= 0 or owner_id != user_id: return
            lang = action_data.rsplit('_', 1)[-1]
            if lang not in MOD_LANGS: return
            econ = get_user_econ(user_id=user_id)
            if not econ:
                return
            econ['language'] = lang
            mark_dirty()
            with _CALLBACK_LANG_LOCK:
                _CALLBACK_LANG_BY_ID[str(call.id)] = (lang, time.time())
            bot.answer_callback_query(call.id, '✅ Язык сохранён!')
            render_private_settings(chat_id, user_id, call.message.message_id)

        elif action_data.startswith('set_chat_lang_'):
            if not is_admin(chat_id, user_id): return
            lang = action_data.rsplit('_', 1)[-1]
            if lang not in MOD_LANGS: return
            get_chat_settings(chat_id)['language'] = lang
            mark_dirty()
            with _CALLBACK_LANG_LOCK:
                _CALLBACK_LANG_BY_ID[str(call.id)] = (lang, time.time())
            bot.answer_callback_query(call.id, '✅ Язык группы сохранён!')
            render_settings_view(chat_id, user_id, call.message.message_id)

        elif action_data == 'set_warn_limit':
            if not is_admin(chat_id,user_id): return
            sett=get_chat_settings(chat_id)
            vals=[1,2,3,4,5,7,10]
            cur=int(sett.get('warn_limit',3) or 3); nxt=vals[(vals.index(cur)+1)%len(vals)] if cur in vals else 3
            sett['warn_limit']=nxt; mark_dirty()
            bot.answer_callback_query(call.id,f'⚠️ Лимит варнов: {nxt}')
            render_settings_view(chat_id,user_id,call.message.message_id)

        # GIF ДЛЯ ПРОФИЛЯ — ТОЛЬКО TELEGRAM STARS
        elif action_data == 'shop_cat_gifs':
            econ = get_user_econ(user_id, user_name, username=user_username)
            owned = set(econ.get('profile_gifs', []))
            current = econ.get('profile_gif')

            lines = [
                '🎞 <b>GIF ДЛЯ ПРОФИЛЯ</b> 😺',
                '━━━━━━━━━━━━━━━━━━━━',
                'GIF прикрепляется прямо к карточке профиля и покупается только за <b>Telegram Stars ⭐️</b>.',
                ''
            ]
            markup = InlineKeyboardMarkup(row_width=1)
            for gif_id, gif in PROFILE_GIFS.items():
                star_key = next((k for k, v in STARS_COSMETICS.items() if v.get('type') == 'gif' and v.get('gif_id') == gif_id), None)
                star_item = STARS_COSMETICS.get(star_key, {}) if star_key else {}
                stars_price = int(star_item.get('stars', 0))
                status = ' ✅ КУПЛЕНО' if gif_id in owned else ''
                active = ' 👑 АКТИВЕН' if current == gif_id else ''
                lines.append(f"• <b>{html.escape(gif['name'])}</b> — <code>{stars_price} ⭐️</code>{status}{active}")
                if gif_id in owned:
                    markup.add(InlineKeyboardButton(f"{gif['name']} — уже куплено", callback_data=f'profile_gif_noop:{user_id}'))
                elif star_key:
                    markup.add(InlineKeyboardButton(f"Купить {gif['name']} — {stars_price} ⭐️", callback_data=f'star_buy_cosm_{star_key}:{user_id}'))

            lines.append('━━━━━━━━━━━━━━━━━━━━')
            markup.add(InlineKeyboardButton('⭐️ Открыть весь Stars-магазин', callback_data=f'shop_cat_stars_main:{user_id}'))
            markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data=f'shop_main:{user_id}'))
            try:
                bot.edit_message_text('\n'.join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e:
                print(f'[NONFATAL ERROR] {e}')
            bot.answer_callback_query(call.id)
            return

        elif action_data == 'profile_gif_noop':
            bot.answer_callback_query(call.id, '🎞 Этот GIF уже есть у вас! 😸', show_alert=False)
            return

        # ПАГИНАЦИЯ МАГАЗИНА
        elif action_data.startswith('shop_cat_badges_'):
            page = int(action_data.replace('shop_cat_badges_', ''))
            items_per_page = 6
            items = list(BADGES.items())
            total_pages = (len(items) + items_per_page - 1) // items_per_page
            
            start_idx = page * items_per_page
            end_idx = start_idx + items_per_page
            current_items = items[start_idx:end_idx]

            lines = ["✨ <b>КАТАЛОГ ЗНАЧКОВ ДЛЯ ПРОФИЛЯ</b> 😺", "━━━━━━━━━━━━━━━━━━━━", "<i>Значок отображается рядом с вашим ником в чате!</i> 😸\n"]
            for b_k, b_v in current_items:
                lines.append(f"• {b_v['emoji']} <b>{b_v['name']}</b> — <code>{b_v['price']} 🪙</code>")
            lines.append(f"\nСтраница {page+1} из {total_pages}")
            lines.append("━━━━━━━━━━━━━━━━━━━━")

            markup = InlineKeyboardMarkup(row_width=3)
            btns = [InlineKeyboardButton(f"{b_v['emoji']} {b_v['price']} 🪙", callback_data=f"buy_badge_{b_k}:{user_id}") for b_k, b_v in current_items]
            markup.add(*btns)
            
            nav_row = []
            if page > 0: nav_row.append(InlineKeyboardButton('⬅️ Назад', callback_data=f'shop_cat_badges_{page-1}:{user_id}'))
            if page < total_pages - 1: nav_row.append(InlineKeyboardButton('Вперед ➡️', callback_data=f'shop_cat_badges_{page+1}:{user_id}'))
            if nav_row: markup.add(*nav_row)
            
            markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data=f'shop_main:{user_id}'))
            try: bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('shop_cat_titles_'):
            page = int(action_data.replace('shop_cat_titles_', ''))
            items_per_page = 5
            items = [(k, v) for k, v in TITLES.items() if not v.get('donor_only')]
            total_pages = (len(items) + items_per_page - 1) // items_per_page
            
            start_idx = page * items_per_page
            end_idx = start_idx + items_per_page
            current_items = items[start_idx:end_idx]

            lines = ["👑 <b>КАТАЛОГ ТИТУЛОВ С ПАССИВНЫМИ БАФФАМИ</b> 😺", "━━━━━━━━━━━━━━━━━━━━", "<i>Каждый титул дает постоянный бонус к удаче или доходу!</i> 😸\n"]
            for t_k, t_v in current_items:
                lines.append(f"• <b>{t_v['text']}</b> — <code>{t_v['price']} 🪙</code> ({t_v['desc']})")
            lines.append(f"\nСтраница {page+1} из {total_pages}")
            lines.append("━━━━━━━━━━━━━━━━━━━━")

            markup = InlineKeyboardMarkup(row_width=1)
            for t_key, t_info in current_items:
                markup.add(InlineKeyboardButton(f"{t_info['text']} • {t_info['price']} 🪙", callback_data=f"buy_title_{t_key}:{user_id}"))
            
            # Сертификат кастомного титула теперь продаётся только за Telegram Stars в /stars.

            nav_row = []
            if page > 0: nav_row.append(InlineKeyboardButton('⬅️ Назад', callback_data=f'shop_cat_titles_{page-1}:{user_id}'))
            if page < total_pages - 1: nav_row.append(InlineKeyboardButton('Вперед ➡️', callback_data=f'shop_cat_titles_{page+1}:{user_id}'))
            if nav_row: markup.add(*nav_row)
            
            markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data=f'shop_main:{user_id}'))
            try: bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('shop_cat_pets_'):
            page = int(action_data.replace('shop_cat_pets_', ''))
            items_per_page = 4
            items = [(p_k, p_v) for p_k, p_v in PETS_DATA.items() if p_k not in STARS_ONLY_PET_IDS]
            total_pages = (len(items) + items_per_page - 1) // items_per_page
            
            start_idx = page * items_per_page
            end_idx = start_idx + items_per_page
            current_items = items[start_idx:end_idx]

            lines = ["🐾 <b>ЗОМАГАЗИН: ПИТОМЦЫ 2.0</b> 😺", "━━━━━━━━━━━━━━━━━━━━", "<i>Питомцы помогают в охоте, рыбалке, и дают бонусы!</i> 😸\n"]
            for p_k, p_v in current_items:
                lines.append(f"• <b>{p_v['name']}</b> — <code>{p_v['price']} 🪙</code>\n  <i>{p_v['desc']}</i>")
            lines.append(f"\nСтраница {page+1} из {total_pages}")
            lines.append("━━━━━━━━━━━━━━━━━━━━")

            econ=get_user_econ(user_id,user_name,username=user_username)
            owned=set(econ.get('pet_inventory',[]) or [])
            active=(econ.get('pet') or {}).get('id')
            markup = InlineKeyboardMarkup(row_width=2)
            btns = []
            for p_id,p in current_items:
                if p_id in owned:
                    label='✅ Активен' if p_id==active else '🐾 Выбрать'
                    btns.append(InlineKeyboardButton(f"{label}: {p['short']}", callback_data=f"equip_pet_{p_id}:{user_id}"))
                else:
                    btns.append(InlineKeyboardButton(f"Купить {p['short']} — {p['price']} 🪙", callback_data=f"buy_pet_{p_id}:{user_id}"))
            for i in range(0, len(btns), 2):
                markup.add(*btns[i:i+2])
            
            nav_row = []
            if page > 0: nav_row.append(InlineKeyboardButton('⬅️ Назад', callback_data=f'shop_cat_pets_{page-1}:{user_id}'))
            if page < total_pages - 1: nav_row.append(InlineKeyboardButton('Вперед ➡️', callback_data=f'shop_cat_pets_{page+1}:{user_id}'))
            if nav_row: markup.add(*nav_row)

            markup.add(InlineKeyboardButton('🔙 Назад в магазин', callback_data=f'shop_main:{user_id}'))
            try: bot.edit_message_text("\n".join(lines), chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception as e: print(f"[NONFATAL ERROR] {e}")

        elif action_data.startswith('buy_ring_'):
            r_id = action_data.replace('buy_ring_', '')
            if r_id in RINGS:
                r_info = RINGS[r_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                if econ['balance'] < r_info['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {r_info['price']} 🪙! 😿", show_alert=True)
                    return
                _adjust_balance(econ, -(r_info['price']))
                econ.setdefault('rings', []).append(r_id)
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Вы приобрели {r_info['name']}! 😻", show_alert=True)

        elif action_data.startswith('buy_title_'):
            title_key = action_data.replace('buy_title_', '')
            if title_key in TITLES:
                item = TITLES[title_key]
                if item.get('donor_only'):
                    bot.answer_callback_query(call.id, '💎 Этот титул доступен только за Telegram Stars в /stars.', show_alert=True)
                    return
                econ = get_user_econ(user_id, user_name, username=user_username)
                if title_key in econ.get('titles', []):
                    bot.answer_callback_query(call.id, '❌ Титул уже куплен! 😾', show_alert=True)
                    return
                if econ['balance'] < item['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {item['price']} 🪙! 😿", show_alert=True)
                    return
                _adjust_balance(econ, -(item['price']))
                econ.setdefault('titles', []).append(title_key)
                econ['active_title'] = title_key
                econ['custom_title'] = None
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Куплен титул {item['text']}! 😻", show_alert=True)
                send_user_profile(chat_id, user_name, user_id, message_id_to_edit=call.message.message_id, username=user_username)

        elif action_data.startswith('buy_badge_'):
            badge_key = action_data.replace('buy_badge_', '')
            if badge_key in BADGES:
                item = BADGES[badge_key]
                econ = get_user_econ(user_id, user_name, username=user_username)
                if item['emoji'] in econ.get('inventory', []):
                    bot.answer_callback_query(call.id, f"Значок {item['emoji']} уже есть! 😾", show_alert=True)
                    return
                if econ['balance'] < item['price']:
                    bot.answer_callback_query(call.id, f"❌ Нужно {item['price']} 🪙! 😿", show_alert=True)
                    return
                _adjust_balance(econ, -(item['price']))
                econ.setdefault('inventory', []).append(item['emoji'])
                econ['badge'] = item['emoji']
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Куплен значок {item['emoji']}! 😻", show_alert=True)

        elif action_data.startswith('equip_pet_'):
            pet_id=action_data.replace('equip_pet_',''); econ=get_user_econ(user_id,user_name,username=user_username)
            if pet_id not in econ.get('pet_inventory',[]): bot.answer_callback_query(call.id,'❌ Питомца нет в инвентаре.',show_alert=True); return
            activate_pet(econ,pet_id); bot.answer_callback_query(call.id,'🐾 Питомец выбран!'); render_pet_view(chat_id,user_id,user_name,call.message.message_id); return

        elif action_data.startswith('buy_pet_'):
            pet_id = action_data.replace('buy_pet_', '')
            if pet_id in PETS_DATA:
                if pet_id in STARS_ONLY_PET_IDS:
                    bot.answer_callback_query(call.id, '⭐️ Этот питомец доступен только в /stars. В обычном магазине его купить нельзя.', show_alert=True)
                    return
                p_data = PETS_DATA[pet_id]
                econ = get_user_econ(user_id, user_name, username=user_username)
                if econ.get('pet', {}).get('id') == pet_id:
                    bot.answer_callback_query(call.id, "❌ Этот питомец уже у вас. 😸", show_alert=True)
                    return
                if pet_id == 'vip_griffin':
                    # Грифон — Stars-only. Нулевой price в каталоге никогда не означает бесплатную выдачу.
                    if 'pet_griffin' not in econ.setdefault('paid_stars_items', []):
                        bot.answer_callback_query(call.id, "❌ Королевский Грифон доступен только после успешной оплаты 5 ⭐️ в Stars-магазине.", show_alert=True)
                        return
                else:
                    if econ['balance'] < p_data['price']:
                        bot.answer_callback_query(call.id, f"❌ Нужно {p_data['price']} 🪙! 😿", show_alert=True)
                        return
                    _adjust_balance(econ, -(p_data['price']))
                activate_pet(econ, pet_id)
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎉 Вы завели питомца {p_data['name']}! 😻", show_alert=True)
                render_pet_view(chat_id, user_id, user_name, call.message.message_id)

        # НОВЫЕ СИСТЕМЫ: РЕСУРСЫ / КРАФТ / ГИЛЬДИИ / РЫНОК / РЕЙД / СЕЗОН
        elif action_data == 'resources_main':
            render_resources_view(chat_id, user_id, user_name, call.message.message_id)
            bot.answer_callback_query(call.id); return
        elif action_data == 'resources_fish':
            _render_resource_list(call, 'fish')
            bot.answer_callback_query(call.id); return
        elif action_data == 'resources_hunt':
            _render_resource_list(call, 'hunt')
            bot.answer_callback_query(call.id); return
        elif action_data == 'resources_craft':
            render_craft_view(chat_id, user_id, user_name, call.message.message_id)
            bot.answer_callback_query(call.id); return
        elif action_data.startswith('craft_'):
            recipe_id = action_data.replace('craft_', '', 1)
            ok, msg = craft_item(get_user_econ(user_id, user_name, username=user_username), recipe_id)
            bot.answer_callback_query(call.id, msg, show_alert=not ok)
            render_craft_view(chat_id, user_id, user_name, call.message.message_id)
            return
        elif action_data == 'backpack_open':
            render_backpack_view(chat_id, user_id, user_name, call.message.message_id)
            bot.answer_callback_query(call.id); return
        elif action_data == 'guild_view':
            render_guild_view(chat_id, user_id, user_name, call.message.message_id)
            bot.answer_callback_query(call.id); return
        elif action_data == 'guild_list':
            guilds = db.get('guilds', {})
            lines = ['🏰 <b>СПИСОК ГИЛЬДИЙ</b>', '━━━━━━━━━━━━━━━━━━━━']
            for gid, g in list(guilds.items())[:20]:
                lines.append(f'<code>{gid}</code> — <b>{html.escape(g.get("name", "Гильдия"))}</b> ({len(g.get("members", []))}/30)')
            if not guilds: lines.append('Гильдий пока нет. 😿')
            lines.append('\nВступить: <code>/guild вступить NYA-1234</code>')
            back_markup = InlineKeyboardMarkup(); back_markup.add(InlineKeyboardButton('🔙 Назад', callback_data=f'guild_view:{user_id}'))
            bot.edit_message_text('\n'.join(lines), chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML', reply_markup=back_markup)
            bot.answer_callback_query(call.id); return
        elif action_data == 'guild_deposit':
            with GUILD_LOCK:
                econ = get_user_econ(user_id, user_name, username=user_username)
                guild = get_user_guild(econ)
                if not guild or guild.get('owner_id') != user_id:
                    bot.answer_callback_query(call.id, '❌ Только владелец гильдии.', show_alert=True); return
                if econ.get('balance', 0) < 1000:
                    bot.answer_callback_query(call.id, '❌ Нужно 1,000 🪙.', show_alert=True); return
                _adjust_balance(econ, -(1000)); guild['bank'] = int(guild.get('bank', 0)) + 1000; guild['exp'] = int(guild.get('exp', 0)) + 100
                mark_dirty()
            bot.answer_callback_query(call.id, '💰 +1,000 🪙 в казну!'); render_guild_view(chat_id, user_id, user_name, call.message.message_id); return
        elif action_data == 'guild_leave':
            with GUILD_LOCK:
                econ = get_user_econ(user_id, user_name, username=user_username); gid = econ.get('guild_id'); guild = db.get('guilds', {}).get(gid) if gid else None
                if guild and guild.get('owner_id') != user_id:
                    guild['members'] = [x for x in guild.get('members', []) if x != user_id]; econ['guild_id'] = None; mark_dirty()
                    left_ok = True
                else:
                    left_ok = False
            if left_ok:
                bot.answer_callback_query(call.id, '🚪 Вы вышли из гильдии.'); render_guild_view(chat_id, user_id, user_name, call.message.message_id); return
            bot.answer_callback_query(call.id, '❌ Владелец не может просто выйти — распустите гильдию.', show_alert=True); return
        elif action_data == 'guild_disband':
            with GUILD_LOCK:
                econ = get_user_econ(user_id, user_name, username=user_username); gid = econ.get('guild_id'); guild = db.get('guilds', {}).get(gid) if gid else None
                if guild and guild.get('owner_id') == user_id:
                    for mid in list(guild.get('members', [])):
                        me = get_user_econ(mid, str(mid)); me['guild_id'] = None
                    db['guilds'].pop(gid, None); mark_dirty(); disbanded = True
                else:
                    disbanded = False
            if disbanded:
                bot.answer_callback_query(call.id, '🗑 Гильдия распущена.'); render_guild_view(chat_id, user_id, user_name, call.message.message_id); return
            bot.answer_callback_query(call.id, '❌ Только владелец может распустить гильдию.', show_alert=True); return
        elif action_data == 'pmarket_view':
            render_player_market(chat_id, user_id, user_name, call.message.message_id); bot.answer_callback_query(call.id); return
        elif action_data.startswith('pmarket_buy_'):
            lid = action_data.replace('pmarket_buy_', '', 1)
            with PLAYER_MARKET_LOCK:
                listing = db.get('player_market', {}).get(lid)
                if not listing:
                    bot.answer_callback_query(call.id, '❌ Объявление уже продано или удалено.', show_alert=True); return
                seller_id = int(listing.get('seller_id', 0) or 0)
                if seller_id == user_id:
                    bot.answer_callback_query(call.id, '❌ Нельзя купить собственное объявление.', show_alert=True); return
                if seller_id <= 0:
                    db['player_market'].pop(lid, None); mark_dirty()
                    bot.answer_callback_query(call.id, '❌ Повреждённое объявление удалено.', show_alert=True); return

                # Рынок — перевод денег между двумя аккаунтами, поэтому сначала
                # фиксируем порядок user-locks, затем ещё раз читаем объявление.
                with serialized_multi_user_action(user_id, seller_id):
                    listing = db.get('player_market', {}).get(lid)
                    if not listing:
                        bot.answer_callback_query(call.id, '❌ Объявление уже продано или удалено.', show_alert=True); return
                    seller_id = int(listing.get('seller_id', 0) or 0)
                    if seller_id == user_id or seller_id <= 0:
                        bot.answer_callback_query(call.id, '❌ Некорректное объявление.', show_alert=True); return
                    econ = get_user_econ(user_id, user_name, username=user_username)
                    price = int(listing.get('price', 0))
                    if price <= 0:
                        db['player_market'].pop(lid, None); mark_dirty()
                        bot.answer_callback_query(call.id, '❌ Повреждённое объявление удалено.', show_alert=True); return
                    if econ.get('balance', 0) < price:
                        bot.answer_callback_query(call.id, f'❌ Нужно {price:,} 🪙.', show_alert=True); return
                    seller = get_user_econ(seller_id, listing.get('seller_name', 'Игрок'))
                    qty = max(1, int(listing.get('qty', 1) or 1))
                    _adjust_balance(econ, -price)
                    _adjust_balance(seller, price)
                    inv = econ.setdefault('fish_inventory', {}) if listing.get('kind') == 'fish' else econ.setdefault('hunt_inventory', {})
                    inv[listing['item_name']] = int(inv.get(listing['item_name'], 0)) + qty
                    db['player_market'].pop(lid, None); mark_dirty()
            bot.answer_callback_query(call.id, '🛒 Покупка совершена!'); render_player_market(chat_id, user_id, user_name, call.message.message_id); return
        elif action_data == 'raid_view':
            render_raid(chat_id, user_id, user_name, call.message.message_id); bot.answer_callback_query(call.id); return
        elif action_data == 'raid_start':
            raid = db.setdefault('raid', {}); now = time.time()
            if raid.get('active') and float(raid.get('ends_at', 0)) > now:
                bot.answer_callback_query(call.id, '🐉 Рейд уже идёт!', show_alert=True); return
            econ = get_user_econ(user_id, user_name, username=user_username)
            if econ.get('balance', 0) < 1000:
                bot.answer_callback_query(call.id, '❌ Создание рейда стоит 1,000 🪙.', show_alert=True); return
            _adjust_balance(econ, -(1000))
            hp = random.randint(25000, 45000)
            raid.clear(); raid.update({'active': True, 'name': random.choice(['🐉 Древний Дракон', '👹 Ня-Демон', '🤖 Кибер-Босс']), 'hp': hp, 'max_hp': hp, 'ends_at': now + 3600, 'participants': {}, 'last_attack': {}})
            raid['participants'][str(user_id)] = 0; mark_dirty(); bot.answer_callback_query(call.id, '🐉 Рейд создан!'); render_raid(chat_id, user_id, user_name, call.message.message_id); return
        elif action_data == 'raid_attack':
            raid = db.setdefault('raid', {}); now = time.time()
            if not raid.get('active') or float(raid.get('ends_at', 0)) <= now:
                bot.answer_callback_query(call.id, '❌ Рейд уже закончился.', show_alert=True); return
            last = float(raid.setdefault('last_attack', {}).get(str(user_id), 0) or 0)
            if now - last < 30:
                bot.answer_callback_query(call.id, f'⏳ Атака доступна через {int(30-(now-last))}с.', show_alert=True); return
            econ = get_user_econ(user_id, user_name, username=user_username)
            dmg = random.randint(300, 900) + int(econ.get('account_exp', 0) ** 0.5) * 10
            if econ.get('pet'): dmg += int(econ['pet'].get('luck_bonus', 0) * 2)
            raid['hp'] = max(0, int(raid.get('hp', 0)) - dmg); raid.setdefault('participants', {})[str(user_id)] = int(raid.setdefault('participants', {}).get(str(user_id), 0)) + dmg; raid.setdefault('last_attack', {})[str(user_id)] = now
            add_season_points(econ, max(5, dmg // 100)); mark_dirty()
            if raid['hp'] <= 0:
                total_damage = sum(int(v) for v in raid.get('participants', {}).values()) or 1
                for pid, pdmg in raid.get('participants', {}).items():
                    reward = max(500, int(25000 * pdmg / total_damage))
                    pe = get_user_econ(int(pid), str(pid)); _adjust_balance(pe, reward); pe['season_points'] = int(pe.get('season_points', 0)) + 50
                raid['active'] = False; raid['finished_at'] = now; raid['rewarded'] = True; msg = '🏆 Босс повержен! Награды выданы участникам.'
            else:
                msg = f'⚔️ Вы нанесли <b>{dmg:,}</b> урона!'
            bot.answer_callback_query(call.id, msg, show_alert=True); render_raid(chat_id, user_id, user_name, call.message.message_id); return
        elif action_data == 'season_view':
            render_season(chat_id, user_id, user_name, call.message.message_id); bot.answer_callback_query(call.id); return
        elif action_data.startswith('world_'):
            target = action_data.replace('world_', '')
            if target == 'business': render_business_view(chat_id, user_id, user_name)
            elif target == 'fish':
                bot.send_message(chat_id, '🌊 Озеро ждёт! Используйте /fish 🎣')
            elif target == 'hunt': bot.send_message(chat_id, '🌲 Лес ждёт! Используйте /hunt 🏹')
            elif target == 'raid': render_raid(chat_id, user_id, user_name)
            bot.answer_callback_query(call.id); return

        # УПРАВЛЕНИЕ ПРОФИЛЕМ
        elif action_data.startswith('set_title_'):
            title_key = action_data.replace('set_title_', '')
            econ = get_user_econ(user_id, user_name, username=user_username)
            if title_key in econ.get('titles', []) and title_key in TITLES:
                econ['active_title'] = title_key
                econ['custom_title'] = None
                mark_dirty()
                bot.answer_callback_query(call.id, f"✅ Надет титул {TITLES[title_key]['text']}! 😸")
                render_profile_settings_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'remove_title':
            econ = get_user_econ(user_id, user_name, username=user_username)
            econ['active_title'] = None
            econ['custom_title'] = None
            mark_dirty()
            bot.answer_callback_query(call.id, '❌ Титул снят! 😿', show_alert=True)
            render_profile_settings_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data.startswith('set_badge_'):
            selected_emoji = action_data.replace('set_badge_', '')
            econ = get_user_econ(user_id, user_name, username=user_username)
            if selected_emoji in econ.get('inventory', []):
                econ['badge'] = selected_emoji
                mark_dirty()
                bot.answer_callback_query(call.id, f"✅ Надет значок {selected_emoji}! 😸")
                render_profile_settings_view(chat_id, user_id, user_name, call.message.message_id)

        elif action_data == 'remove_badge':
            econ = get_user_econ(user_id, user_name, username=user_username)
            econ['badge'] = None
            mark_dirty()
            bot.answer_callback_query(call.id, "❌ Значок снят! 😿", show_alert=True)
            render_profile_settings_view(chat_id, user_id, user_name, call.message.message_id)

    except Exception as e:
        print(f"[CALLBACK ERROR] Исключение в callback: {e}")
        try: bot.answer_callback_query(call.id, "⚠️ Произошла ошибка!", show_alert=False)
        except Exception as e: print(f"[NONFATAL ERROR] {e}")
    finally:
        try:
            _LOCALE_CONTEXT.user_id = None
            _LOCALE_CONTEXT.chat_id = None
        except Exception:
            pass
        try:
            with _CALLBACK_LANG_LOCK:
                _CALLBACK_LANG_BY_ID.pop(str(call.id), None)
        except Exception:
            pass

def process_stars_pre_checkout(pre_checkout_query):
    try:
        ok, reason = validate_stars_payload(
            pre_checkout_query.invoice_payload,
            pre_checkout_query.total_amount,
            pre_checkout_query.from_user.id,
            getattr(pre_checkout_query, 'currency', 'XTR')
        )
        bot.answer_pre_checkout_query(pre_checkout_query.id, ok=ok, error_message=None if ok else reason)
    except Exception as e:
        print(f"[PRE-CHECKOUT ERROR] {e}")
        try: bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message='Платёж не прошёл проверку.')
        except Exception as e: print(f"[NONFATAL ERROR] {e}")

def process_stars_successful_payment(message):
    try:
        sp = message.successful_payment
        payload = sp.invoice_payload
        stars_amount = sp.total_amount

        ok, reason = validate_stars_payload(
            payload,
            stars_amount,
            message.from_user.id,
            getattr(sp, 'currency', 'XTR')
        )
        if not ok:
            print(f"[STARS SECURITY] rejected payment: {reason}; payload={payload!r}")
            return

        # Реальный Telegram Gift: платёж только резервирует заказ, а сам подарок
        # отправляется через sendGift после подтверждённой оплаты.
        if payload.startswith('tgift:'):
            token=payload.split(':',1)[1]
            order=db.setdefault('tgift_orders',{}).get(token)
            if not order:
                return
            if int(order.get('buyer_id',0) or 0)!=int(message.from_user.id) or int(order.get('amount',0) or 0)!=int(stars_amount):
                print(f'[TGIFT SECURITY] invalid order/payment: {payload!r}')
                return
            if float(order.get('expires_at',0) or 0)<time.time():
                try: bot.refund_star_payment(message.from_user.id, sp.telegram_payment_charge_id)
                except Exception as refund_error: print(f'[TGIFT REFUND ERROR] {refund_error}')
                db.get('tgift_orders',{}).pop(token,None); mark_dirty(); return
            try:
                target_id=int(order['target_id']); gift_id=str(order['gift_id']); gift_text=str(order.get('text',''))[:128]
                if not bot.send_gift(user_id=target_id,gift_id=gift_id,text=gift_text or None):
                    raise RuntimeError('Telegram не подтвердил отправку подарка')
                db.get('tgift_orders',{}).pop(token,None); mark_stars_charge_processed(getattr(sp,'telegram_payment_charge_id',None)); mark_dirty()
                bot.send_message(message.chat.id,'🎁 Подарок успешно отправлен! 😻')
            except Exception as gift_error:
                print(f'[TGIFT SEND ERROR] {gift_error}')
                try: bot.refund_star_payment(message.from_user.id, sp.telegram_payment_charge_id)
                except Exception as refund_error: print(f'[TGIFT REFUND ERROR] {refund_error}')
                db.get('tgift_orders',{}).pop(token,None); mark_stars_charge_processed(getattr(sp,'telegram_payment_charge_id',None)); mark_dirty()
                bot.send_message(message.chat.id,'❌ Не удалось отправить подарок. Оплата возвращена, если Telegram разрешил возврат.')
            return

        # Telegram can retry delivery of an update. Process each successful
        # payment only once using its unique charge id.
        charge_id = getattr(sp, 'telegram_payment_charge_id', None)
        processed = db.setdefault('processed_stars_charges', [])
        if charge_id and charge_id in processed:
            print(f"[STARS] duplicate payment ignored: {charge_id}")
            mark_stars_charge_processed(charge_id)
            return
        chat_id = message.chat.id
        
        parts = payload.split(':')
        prod_type_key = parts[0]
        if payload.startswith('gift2|'):
            gift_parts = payload.split('|')
            if len(gift_parts) != 5:
                print(f'[STARS SECURITY] malformed gift2 payload: {payload!r}')
                mark_stars_charge_processed(charge_id)
                return
            buyer_id = int(gift_parts[4])
        elif prod_type_key.startswith('gift_'):
            buyer_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else message.from_user.id
        else:
            buyer_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else message.from_user.id
        
        u = message.from_user
        user_name = (f"{u.first_name or ''} {u.last_name or ''}").strip() or u.username or "Пользователь"
        econ = get_user_econ(buyer_id, user_name, username=u.username)
        
        user_link = make_link(chat_id, user_name, buyer_id, ping=True)

        # Повторно не выдаём вечные подарки/покупки, даже если платёж создан до
        # предыдущей покупки. Монеты и временный VIP остаются многократными.
        if prod_type_key.startswith('vippass_'):
            _pk = prod_type_key.replace('vippass_', '', 1)
            _err = stars_purchase_error(econ, 'vippass', _pk)
            if _err:
                print(f"[STARS SECURITY] permanent VIP replay blocked: {_pk} buyer={buyer_id}")
                mark_stars_charge_processed(charge_id)
                return
        elif prod_type_key.startswith('cosm_'):
            _ck = prod_type_key.replace('cosm_', '', 1)
            _err = stars_purchase_error(econ, 'cosm', _ck)
            if _err:
                print(f"[STARS SECURITY] permanent cosmetic replay blocked: {_ck} buyer={buyer_id}")
                mark_stars_charge_processed(charge_id)
                return
        elif prod_type_key.startswith('bpprem_') and econ.get('bp_premium'):
            print(f"[STARS SECURITY] premium pass replay blocked: buyer={buyer_id}")
            mark_stars_charge_processed(charge_id)
            return

        # Только после успешной проверки товара учитываем Stars в статистике поддержки.
        econ['stars_donated'] = econ.get('stars_donated', 0) + stars_amount

        # 0. Проверка на подарок другому человеку
        is_gift = payload.startswith('gift2|') or prod_type_key.startswith('gift_')
        if is_gift:
            if payload.startswith('gift2|'):
                gift_parts = payload.split('|')
                _, gift_kind, actual_prod, target_raw, actual_buyer_raw = gift_parts
            else:
                gift_kind = None
                actual_prod = prod_type_key.replace('gift_', '', 1)
                target_raw = parts[1]
                actual_buyer_raw = parts[2] if len(parts) > 2 else str(buyer_id)
            target_id = int(target_raw)
            actual_buyer_id = int(actual_buyer_raw)

            target_econ = get_user_econ(user_id=target_id)
            target_name = target_econ.get('display_name', f"ID:{target_id}")
            t_link = make_link(chat_id, target_name, target_id, ping=True)

            # Re-check one-time entitlements at delivery time: the target can
            # have bought the same item after pre-checkout but before payment
            # delivery. Coins/temporary VIP may still be gifted repeatedly.
            if gift_kind == 'pass':
                duplicate_error = stars_purchase_error(target_econ, 'vippass', actual_prod)
            elif gift_kind == 'cosm':
                duplicate_error = stars_purchase_error(target_econ, 'cosm', actual_prod)
            else:
                duplicate_error = None
            if duplicate_error:
                print(f"[STARS SECURITY] gift delivery blocked after target ownership changed: target={target_id} item={actual_prod}")
                mark_stars_charge_processed(charge_id)
                return

            # Начисление подарка
            if actual_prod in STARS_COIN_PACKS:
                pack = STARS_COIN_PACKS[actual_prod]
                _adjust_balance(target_econ, pack['coins'])
                prod_name = pack['name']
            elif actual_prod in STARS_VIP_PASS:
                v_item = STARS_VIP_PASS[actual_prod]
                days = v_item['days']
                if days == -1: target_econ['vip_forever'] = True
                else: target_econ['vip_until'] = max(time.time(), target_econ.get('vip_until', 0)) + (days * 86400)
                prod_name = v_item['name']
            elif actual_prod == 'bp_premium':
                if target_econ.get('bp_premium'):
                    print(f"[STARS SECURITY] duplicate gifted premium pass blocked: target={target_id}")
                    mark_stars_charge_processed(charge_id)
                    return
                target_econ['bp_premium'] = True
                target_econ.setdefault('paid_stars_items', [])
                if 'bp_premium' not in target_econ['paid_stars_items']:
                    target_econ['paid_stars_items'].append('bp_premium')
                prod_name = "🎃 Премиум Хеллоуин Pass"
            elif actual_prod == 'custom_title':
                target_econ['has_custom_title_cert'] = True
                prod_name = "🌟 Сертификат Кастомного Титула"
            elif actual_prod == 'pet_griffin':
                p_info = PETS_DATA['vip_griffin']
                target_econ.setdefault('paid_stars_items', [])
                if 'pet_griffin' not in target_econ['paid_stars_items']:
                    target_econ['paid_stars_items'].append('pet_griffin')
                activate_pet(target_econ, 'vip_griffin')
                prod_name = p_info['name']
            elif actual_prod in STARS_HARD_LIMITED_ITEMS:
                duplicate_error = stars_purchase_error(target_econ, 'cosm', actual_prod)
                if duplicate_error:
                    print(f'[STARS SECURITY] duplicate/limit gifted hard-limited item blocked: target={target_id} item={actual_prod}')
                    mark_stars_charge_processed(charge_id); return
                if not reserve_stars_hard_limited(actual_prod):
                    print(f'[STARS SECURITY] limited item sold out at delivery: {actual_prod}')
                    mark_stars_charge_processed(charge_id); return
                try:
                    prod_name = grant_hard_limited_stars_item(target_econ, actual_prod)
                except Exception as grant_error:
                    print(f'[STARS SECURITY] hard-limited gift grant failed: {actual_prod}: {grant_error}')
                    release_stars_hard_limited(actual_prod)
                    mark_stars_charge_processed(charge_id); return
            elif actual_prod in STARS_COSMETICS:
                cosm = STARS_COSMETICS[actual_prod]
                c_type = cosm.get('type')
                if c_type == 'title_cert':
                    target_econ['has_custom_title_cert'] = True
                elif c_type == 'donor_title':
                    title_id = cosm.get('title_id')
                    if title_id in TITLES and TITLES[title_id].get('donor_only'):
                        target_econ.setdefault('paid_stars_items', [])
                        if actual_prod not in target_econ['paid_stars_items']:
                            target_econ['paid_stars_items'].append(actual_prod)
                        target_econ.setdefault('titles', [])
                        if title_id not in target_econ['titles']:
                            target_econ['titles'].append(title_id)
                        target_econ['active_title'] = title_id
                        target_econ['custom_title'] = None
                elif c_type == 'theme':
                    theme_id = cosm.get('theme_id')
                    purchased = target_econ.setdefault('purchased_themes', ['default'])
                    if theme_id and theme_id not in purchased:
                        purchased.append(theme_id)
                    if theme_id:
                        target_econ['profile_theme'] = theme_id
                elif c_type == 'badge':
                    badge_emoji = cosm.get('emoji')
                    target_econ.setdefault('paid_stars_items', [])
                    if actual_prod not in target_econ['paid_stars_items']:
                        target_econ['paid_stars_items'].append(actual_prod)
                    if badge_emoji:
                        inv = target_econ.setdefault('inventory', [])
                        if badge_emoji not in inv:
                            inv.append(badge_emoji)
                        target_econ['badge'] = badge_emoji
                elif c_type == 'pet':
                    pet_id = cosm.get('pet_id')
                    if pet_id in PETS_DATA:
                        target_econ.setdefault('paid_stars_items', [])
                        if actual_prod not in target_econ['paid_stars_items']:
                            target_econ['paid_stars_items'].append(actual_prod)
                        p_info = PETS_DATA[pet_id]
                        activate_pet(target_econ, pet_id)
                elif c_type == 'donor_vehicle':
                    vid = cosm.get('vehicle_id')
                    if vid in DONOR_VEHICLES:
                        target_econ.setdefault('vehicle_inventory', [])
                        if vid not in target_econ['vehicle_inventory']:
                            target_econ['vehicle_inventory'].append(vid)
                        if not target_econ.get('equipped_vehicle'):
                            target_econ['equipped_vehicle'] = vid
                            target_econ['vehicle'] = vid
                    prod_name = cosm.get('name', actual_prod)
                elif c_type == 'donor_business':
                    bid = cosm.get('business_id')
                    if bid in DONOR_BUSINESSES:
                        donor_owned = target_econ.setdefault('donor_businesses', {})
                        already_owned = bid in donor_owned
                        donor_owned[bid] = max(1, int(donor_owned.get(bid, 1)))
                        if not already_owned:
                            purchase_now = time.time()
                            target_econ.setdefault('donor_business_purchased_at', {})[bid] = purchase_now
                            target_econ.setdefault('biz_last_collect', {})[bid] = purchase_now
                            target_econ.setdefault('biz_income_carry', {})[bid] = 0.0
                    prod_name = cosm.get('name', actual_prod)
                elif c_type == 'gif':
                    gif_id = cosm.get('gif_id')
                    if gif_id in PROFILE_GIFS:
                        target_econ.setdefault('profile_gifs', [])
                        if gif_id not in target_econ['profile_gifs']:
                            target_econ['profile_gifs'].append(gif_id)
                        target_econ['profile_gif'] = gif_id
                prod_name = cosm.get('name', actual_prod)
            else:
                # Never silently convert an unknown paid product into coins.
                print(f"[STARS] unknown gift product: {actual_prod}")
                prod_name = f"неизвестный товар {actual_prod}"

            mark_dirty()
            log_event('STARS ПОДАРОК', f'{user_link} подарил {t_link} товар: {prod_name} за {stars_amount} ⭐️!')
            bot.send_message(
                chat_id,
                f"🎁⭐️ <b>РОСКОШНЫЙ ПОДАРОК ЗА ЗВЁЗДЫ!</b> 😻\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 Щедрый даритель: {user_link}\n"
                f"🎉 Счастливый получатель: {t_link}\n"
                f"📦 Подарок: <b>{prod_name}</b> ({stars_amount} ⭐️)!\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>Огромное спасибо за поддержку сервера и доброту!</i> 😸",
                parse_mode='HTML'
            )
            mark_stars_charge_processed(charge_id)
            return

        # Покупка bp_premium себе
        if prod_type_key.startswith('bpprem_') or prod_type_key == 'cosm_bp_premium':
            econ['bp_premium'] = True
            econ.setdefault('paid_stars_items', [])
            if 'bp_premium' not in econ['paid_stars_items']:
                econ['paid_stars_items'].append('bp_premium')
            mark_dirty()
            log_event('STARS BP PREM', f'{user_link} активировал Премиум Хеллоуин Pass!')
            bot.reply_to(message, f"🎃 <b>ПРЕМИУМ ХЕЛЛОУИН PASS АКТИВИРОВАН!</b> 😻\nТеперь вам доступны все премиум-награды, Тыквокот и Тёмная тема в <code>/pass</code>!", parse_mode='HTML')
            mark_stars_charge_processed(charge_id)
            return

        # 1. Покупка пакета коинов
        if prod_type_key.startswith('coinpack_'):
            pack_id = prod_type_key.replace('coinpack_', '')
            if pack_id in STARS_COIN_PACKS:
                pack = STARS_COIN_PACKS[pack_id]
                coins_to_add = pack['coins']
                _adjust_balance(econ, coins_to_add)
                add_account_exp(buyer_id, user_name, int(stars_amount * 50), username=u.username)
                mark_dirty()
                
                log_event('STARS ПОКУПКА', f'Игрок {user_link} приобрёл {pack["name"]} за {stars_amount} ⭐️!')
                success_msg = (
                    f"🎉 <b>ОПЛАТА УСПЕШНО ПРОШЛА!</b> 😻\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 Покупатель: {user_link}\n"
                    f"⭐️ Списано: <b>{stars_amount} Звёзд</b>\n"
                    f"💰 Начислено: <b>+{coins_to_add:,} Ня-коинов 🪙</b>!\n"
                    f"💵 Новый баланс: <b>{econ['balance']:,} 🪙</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"<i>Огромное спасибо за поддержку сервера и бота!</i> 😸"
                )
                bot.reply_to(message, success_msg, parse_mode='HTML')
                mark_stars_charge_processed(charge_id)
                return

        # 2. Покупка VIP Nya Pass
        elif prod_type_key.startswith('vippass_'):
            pass_id = prod_type_key.replace('vippass_', '')
            if pass_id in STARS_VIP_PASS:
                item = STARS_VIP_PASS[pass_id]
                days = item['days']
                now_ts = time.time()
                
                if days == -1:
                    econ['vip_forever'] = True
                    dur_str = "НАВСЕГДА 👑"
                else:
                    cur_vip = max(now_ts, econ.get('vip_until', 0))
                    econ['vip_until'] = cur_vip + (days * 86400)
                    exp_date = datetime.fromtimestamp(econ['vip_until'], tz=MSK_TZ).strftime('%d.%m.%Y %H:%M')
                    dur_str = f"на {days} дней (до {exp_date})"
                    
                add_account_exp(buyer_id, user_name, int(stars_amount * 100), username=u.username)
                mark_dirty()
                
                log_event('STARS VIP PASS', f'Игрок {user_link} активировал VIP Nya Pass ({dur_str}) за {stars_amount} ⭐️!')
                success_msg = (
                    f"👑 <b>VIP NYA PASS АКТИВИРОВАН!</b> 😻\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 Владелец: {user_link}\n"
                    f"⏳ Срок действия: <b>{dur_str}</b>\n"
                    f"⭐️ Ваши привилегии:\n"
                    f"• ⚡️ -35% ко всем кулдаунам бота\n"
                    f"• 🎁 2.25x часового бонуса /bonus\n"
                    f"• 🛡 100% защита от карманных краж и ограблений\n"
                    f"• 💼 +10% к зарплате и прибыли бизнесов\n"
                    f"• ⭐️ +25% к опыту профиля\n"
                    f"• 🌟 VIP отметка в профиле\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"<i>Приятной игры с максимальным комфортом!</i> 😸"
                )
                bot.reply_to(message, success_msg, parse_mode='HTML')
                mark_stars_charge_processed(charge_id)
                return

        # 3. Покупка эксклюзивной косметики
        elif prod_type_key.startswith('cosm_'):
            cosm_id = prod_type_key.replace('cosm_', '')
            if cosm_id in STARS_COSMETICS or cosm_id in STARS_LIMITED_ITEMS:
                cosm = STARS_COSMETICS.get(cosm_id) or STARS_LIMITED_ITEMS.get(cosm_id)
                c_type = cosm['type']
                
                if cosm_id in STARS_HARD_LIMITED_ITEMS:
                    if stars_purchase_error(econ, 'cosm', cosm_id):
                        bot.reply_to(message, stars_purchase_error(econ, 'cosm', cosm_id), parse_mode='HTML')
                        mark_stars_charge_processed(charge_id); return
                    if not reserve_stars_hard_limited(cosm_id):
                        bot.reply_to(message, '❌ Лимит этого предмета уже исчерпан (5/5).', parse_mode='HTML')
                        mark_stars_charge_processed(charge_id); return
                    try:
                        granted_name = grant_hard_limited_stars_item(econ, cosm_id)
                    except Exception as grant_error:
                        print(f'[STARS SECURITY] hard-limited grant failed: {cosm_id}: {grant_error}')
                        release_stars_hard_limited(cosm_id)
                        bot.reply_to(message, '⚠️ Не удалось выдать лимитированный предмет. Платёж помечен как обработанный для защиты от повторной выдачи.', parse_mode='HTML')
                        mark_stars_charge_processed(charge_id); return
                    remaining = stars_hard_limited_available(cosm_id)
                    bot.reply_to(message, f"🔥 <b>ЛИМИТИРОВАННЫЙ ПРЕДМЕТ ПОЛУЧЕН!</b> 😻\n\n<b>{html.escape(granted_name)}</b> — вы получили экземпляр. Осталось: <b>{remaining}/5</b>.", parse_mode='HTML')
                    mark_stars_charge_processed(charge_id); return
                if c_type == 'title_cert':

                    econ['has_custom_title_cert'] = True
                    mark_dirty()
                    log_event('STARS ТИТУЛ', f'Игрок {user_link} купил сертификат кастомного титула за {stars_amount} ⭐️!')
                    bot.reply_to(
                        message,
                        f"🌟 <b>СЕРТИФИКАТ ТИТУЛА ПОЛУЧЕН!</b> 😻\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"{user_link}, теперь вы можете установить любой личный титул командой:\n"
                        f"<code>/custom_title Ваш Титул</code> 😸",
                        parse_mode='HTML'
                    )
                    mark_stars_charge_processed(charge_id)
                    return
                elif c_type == 'theme':
                    theme_id = cosm['theme_id']
                    purchased = econ.setdefault('purchased_themes', ['default'])
                    if theme_id not in purchased:
                        purchased.append(theme_id)
                    econ['profile_theme'] = theme_id
                    mark_dirty()
                    log_event('STARS ТЕМА', f'Игрок {user_link} разблокировал тему {cosm["name"]} за {stars_amount} ⭐️!')
                    bot.reply_to(
                        message,
                        f"🎨 <b>VIP ТЕМА УСПЕШНО АКТИВИРОВАНА!</b> 😻\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"Вам установлена тема: <b>{cosm['name']}</b>!\n"
                        f"Проверьте свой новый визуал командой: <code>/profile</code> 😸",
                        parse_mode='HTML'
                    )
                    mark_stars_charge_processed(charge_id)
                    return
                elif c_type == 'donor_title':
                    title_id = cosm.get('title_id')
                    if title_id not in TITLES or not TITLES[title_id].get('donor_only'):
                        bot.reply_to(message, '❌ Некорректный донатный титул.', parse_mode='HTML')
                        mark_stars_charge_processed(charge_id)
                        return
                    econ.setdefault('paid_stars_items', [])
                    if cosm_id not in econ['paid_stars_items']:
                        econ['paid_stars_items'].append(cosm_id)
                    econ.setdefault('titles', [])
                    if title_id not in econ['titles']:
                        econ['titles'].append(title_id)
                    econ['active_title'] = title_id
                    econ['custom_title'] = None
                    mark_dirty()
                    log_event('STARS ТИТУЛ', f'Игрок {user_link} активировал донатный титул {TITLES[title_id]["name"]} за {stars_amount} ⭐️!')
                    bot.reply_to(message, f"👑 <b>ДОНАТНЫЙ ТИТУЛ АКТИВИРОВАН!</b> 😻\n━━━━━━━━━━━━━━━━━━━━\n<b>{TITLES[title_id]['text']}</b>\n{TITLES[title_id]['desc']}\n\nТитул сразу надет в профиль. 😸", parse_mode='HTML')
                    mark_stars_charge_processed(charge_id)
                    return
                elif c_type == 'badge':
                    badge_emoji = cosm['emoji']
                    econ.setdefault('paid_stars_items', [])
                    if cosm_id not in econ['paid_stars_items']:
                        econ['paid_stars_items'].append(cosm_id)
                    inv = econ.setdefault('inventory', [])
                    if badge_emoji not in inv:
                        inv.append(badge_emoji)
                    econ['badge'] = badge_emoji
                    mark_dirty()
                    log_event('STARS ЗНАЧОК', f'Игрок {user_link} разблокировал значок {badge_emoji} за {stars_amount} ⭐️!')
                    bot.reply_to(
                        message,
                        f"✨ <b>VIP ЗНАЧОК НАДЕТ!</b> 😻\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"Значок <b>{badge_emoji} ({cosm['name']})</b> теперь красуется в вашем профиле и в чате! 😸",
                        parse_mode='HTML'
                    )
                    mark_stars_charge_processed(charge_id)
                    return
                elif c_type == 'pet':
                    pet_id = cosm['pet_id']
                    econ.setdefault('paid_stars_items', [])
                    if cosm_id not in econ['paid_stars_items']:
                        econ['paid_stars_items'].append(cosm_id)
                    p_info = PETS_DATA[pet_id]
                    activate_pet(econ, pet_id)
                    mark_dirty()
                    log_event('STARS ПИТОМЕЦ', f'Игрок {user_link} приручил {p_info["name"]} за {stars_amount} ⭐️!')
                    bot.reply_to(
                        message,
                        f"👑 <b>КОРОЛЕВСКИЙ ГРИФОН ТЕПЕРЬ ВАШ!</b> 😻\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"Вы приручили мифического зверя <b>{p_info['name']}</b>!\n"
                        f"Бонус удачи: <b>+{p_info['luck_bonus']}%</b> ко всем играм, рыбалке и охоте! 😸",
                        parse_mode='HTML'
                    )
                    mark_stars_charge_processed(charge_id)
                    return
                elif c_type == 'donor_vehicle':
                    vid = cosm.get('vehicle_id')
                    if vid not in DONOR_VEHICLES:
                        bot.reply_to(message, '❌ Донатная машина не найдена.', parse_mode='HTML')
                        mark_stars_charge_processed(charge_id)
                        return
                    econ.setdefault('vehicle_inventory', [])
                    if vid not in econ['vehicle_inventory']:
                        econ['vehicle_inventory'].append(vid)
                    if not econ.get('equipped_vehicle'):
                        econ['equipped_vehicle'] = vid
                        econ['vehicle'] = vid
                    mark_dirty()
                    info = DONOR_VEHICLES[vid]
                    log_event('STARS DONOR VEHICLE', f'Игрок {user_link} получил {info["name"]} за {stars_amount} ⭐️!')
                    bot.reply_to(message, f"🏎 <b>ДОНАТНАЯ МАШИНА ПОЛУЧЕНА!</b> 😻\n━━━━━━━━━━━━━━━━━━━━\n<b>{html.escape(info['name'])}</b> сохранена в гараже. Надеть её можно командой /garage. 😸", parse_mode='HTML')
                    mark_stars_charge_processed(charge_id)
                    return
                elif c_type == 'donor_business':
                    bid = cosm.get('business_id')
                    if bid not in DONOR_BUSINESSES:
                        bot.reply_to(message, '❌ Донатный бизнес не найден.', parse_mode='HTML')
                        mark_stars_charge_processed(charge_id)
                        return
                    donor_owned = econ.setdefault('donor_businesses', {})
                    already_owned = bid in donor_owned
                    donor_owned[bid] = max(1, int(donor_owned.get(bid, 1)))
                    if not already_owned:
                        purchase_now = time.time()
                        econ.setdefault('donor_business_purchased_at', {})[bid] = purchase_now
                        econ.setdefault('biz_last_collect', {})[bid] = purchase_now
                        econ.setdefault('biz_income_carry', {})[bid] = 0.0
                    mark_dirty()
                    info = DONOR_BUSINESSES[bid]
                    log_event('STARS DONOR BUSINESS', f'Игрок {user_link} получил {info["name"]} за {stars_amount} ⭐️!')
                    bot.reply_to(message, f"💎 <b>ДОНАТНЫЙ БИЗНЕС ПОЛУЧЕН!</b> 😻\n━━━━━━━━━━━━━━━━━━━━\n<b>{html.escape(info['name'])}</b> добавлен навсегда. {html.escape(info['desc'])}. 😸", parse_mode='HTML')
                    mark_stars_charge_processed(charge_id)
                    return
                elif c_type == 'gif':
                    gif_id = cosm.get('gif_id')
                    if gif_id not in PROFILE_GIFS:
                        bot.reply_to(message, '❌ GIF профиля не найден.', parse_mode='HTML')
                        mark_stars_charge_processed(charge_id)
                        return
                    econ.setdefault('profile_gifs', [])
                    if gif_id not in econ['profile_gifs']:
                        econ['profile_gifs'].append(gif_id)
                    econ['profile_gif'] = gif_id
                    mark_dirty()
                    log_event('STARS GIF', f'Игрок {user_link} купил GIF профиля {PROFILE_GIFS[gif_id]["name"]} за {stars_amount} ⭐️!')
                    bot.reply_to(
                        message,
                        f"🎞 <b>GIF ПРОФИЛЯ КУПЛЕН!</b> 😻\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"{user_link}, установлен GIF: <b>{html.escape(PROFILE_GIFS[gif_id]['name'])}</b>.\n"
                        f"Он будет прикреплён прямо к вашей карточке профиля. 😸",
                        parse_mode='HTML'
                    )
                    mark_stars_charge_processed(charge_id)
                    return

        # Неизвестный/неподдерживаемый товар нельзя превращать в коины.
        print(f"[STARS SECURITY] unsupported product rejected: {prod_type_key!r}")
        bot.reply_to(message, "❌ Неизвестный товар. Платёж не был автоматически преобразован в коины.", parse_mode='HTML')

    except Exception as e:
        print(f"[SUCCESSFUL PAYMENT ERROR] {e}")

def register(ctx, only=None):
    """Register selected handlers from this feature module."""
    _inject(ctx)
    bot = ctx["bot"]
    wanted = set(only) if only is not None else set(HANDLER_NAMES)
    registered = []
    if "callback_inline" in wanted:
        _handler = callback_inline
        _handler = serialize_user_action(_handler)
        bot.callback_query_handler(func=lambda call: True)(_handler)
        ctx["callback_inline"] = _handler
        globals()["callback_inline"] = _handler
        registered.append("callback_inline")
    if "process_stars_pre_checkout" in wanted:
        _handler = process_stars_pre_checkout
        _handler = serialize_user_action(_handler)
        bot.pre_checkout_query_handler(func=lambda query: True)(_handler)
        ctx["process_stars_pre_checkout"] = _handler
        globals()["process_stars_pre_checkout"] = _handler
        registered.append("process_stars_pre_checkout")
    if "process_stars_successful_payment" in wanted:
        _handler = process_stars_successful_payment
        _handler = serialize_stars_payment(_handler)
        _handler = serialize_user_action(_handler)
        bot.message_handler(content_types=['successful_payment'])(_handler)
        ctx["process_stars_successful_payment"] = _handler
        globals()["process_stars_successful_payment"] = _handler
        registered.append("process_stars_successful_payment")
    return registered
