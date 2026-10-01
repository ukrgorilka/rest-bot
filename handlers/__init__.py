"""Handler package for the staged NyaBot architecture."""

from . import profile, shop, games, economy, pets, businesses, bank, family, moderation, admin, callbacks, anonymous

MODULES = {
    "profile": profile,
    "shop": shop,
    "games": games,
    "economy": economy,
    "pets": pets,
    "businesses": businesses,
    "bank": bank,
    "family": family,
    "moderation": moderation,
    "admin": admin,
    "callbacks": callbacks,
    "anonymous": anonymous,
}

REGISTRATION_ORDER = ['handle_bot_chat_membership', 'welcome_new_members', 'cmd_mini_games', 'send_welcome', 'cmd_fact_vd', 'cmd_trash', 'cmd_promo', 'cmd_brick', 'cmd_crash', 'cmd_stream', 'cmd_public_salary', 'cmd_public_jobs', 'cmd_monopoly', 'cmd_garden', 'cmd_coinflip', 'cmd_loan', 'cmd_repay', 'cmd_football', 'cmd_basketball', 'cmd_darts', 'cmd_bowling', 'cmd_magic_ball', 'cmd_chance', 'cmd_detector', 'cmd_daily_heroes', 'cmd_backpack', 'cmd_wheel', 'cmd_mines', 'cmd_classic_mines', 'cmd_durak', 'cmd_dick', 'cmd_fap', 'cmd_garage', 'cmd_cook', 'cmd_pet', 'cmd_walk_pet', 'cmd_gear', 'cmd_business', 'cmd_miner', 'cmd_collect', 'cmd_bank', 'cmd_case', 'cmd_lottery', 'cmd_history', 'cmd_settings', 'cmd_custom_title', 'cmd_profile_settings', 'cmd_biometry', 'cmd_marry', 'cmd_family', 'cmd_gift', 'cmd_divorce', 'cmd_bj', 'cmd_rps', 'cmd_market', 'cmd_portfolio', 'cmd_work', 'cmd_train', 'cmd_sell', 'cmd_profile', 'cmd_achievements', 'cmd_balance', 'cmd_stars', 'cmd_inventory', 'cmd_shop', 'cmd_tasks', 'cmd_iq', 'cmd_fat', 'cmd_foot', 'cmd_chromosomes', 'cmd_top_daily', 'cmd_top_weekly', 'cmd_top', 'cmd_safe', 'cmd_personal_home', 'cmd_pet_clothes', 'cmd_house', 'cmd_sheriff', 'cmd_catch', 'cmd_jail', 'cmd_escape', 'cmd_bail', 'cmd_pet_fight', 'cmd_memes', 'cmd_meme', 'cmd_story', 'cmd_halloween_pass', 'cmd_pharmacy', 'cmd_gift_stars', 'cmd_groups', 'cmd_find_group', 'cmd_activity', 'cmd_user_lookup', 'cmd_global_stats', 'cmd_economy_stats', 'cmd_game_stats', 'cmd_bot_status', 'cmd_dashboard', 'cmd_group_info', 'cmd_admins', 'cmd_admin_control', 'cmd_gifttg', 'handle_anonymous_inline', 'handle_tgift_state', 'handle_anonymous_callbacks', 'admin_force_save_command', 'admin_give_gif_command', 'admin_give_stars_all_command', 'admin_give_command', 'cmd_resources_command', 'cmd_guild_command', 'cmd_player_market_command', 'cmd_raid_command', 'cmd_season_command', 'cmd_world_command', 'dragon_audio_file_id', 'cmd_ban', 'cmd_mute', 'cmd_kick', 'cmd_warn', 'cmd_unban', 'cmd_unmute', 'cmd_bans', 'cmd_mutes', 'cmd_warns', 'handle_messages', 'callback_inline', 'process_stars_pre_checkout', 'process_stars_successful_payment']
GROUP_BY_HANDLER = {'handle_bot_chat_membership': 'moderation', 'welcome_new_members': 'moderation', 'handle_messages': 'moderation', 'cmd_groups': 'moderation', 'cmd_find_group': 'moderation', 'cmd_user_lookup': 'moderation', 'cmd_group_info': 'moderation', 'cmd_admins': 'moderation', 'cmd_admin_control': 'moderation', 'cmd_gifttg': 'anonymous', 'handle_anonymous_inline': 'anonymous', 'handle_tgift_state': 'anonymous', 'handle_anonymous_callbacks': 'anonymous', 'cmd_ban': 'moderation', 'cmd_mute': 'moderation', 'cmd_kick': 'moderation', 'cmd_warn': 'moderation', 'cmd_unban': 'moderation', 'cmd_unmute': 'moderation', 'cmd_bans': 'moderation', 'cmd_mutes': 'moderation', 'cmd_warns': 'moderation', 'send_welcome': 'profile', 'cmd_profile': 'profile', 'cmd_profile_settings': 'profile', 'cmd_biometry': 'profile', 'cmd_achievements': 'profile', 'cmd_balance': 'profile', 'cmd_settings': 'profile', 'cmd_top_daily': 'profile', 'cmd_top_weekly': 'profile', 'cmd_top': 'profile', 'cmd_activity': 'profile', 'cmd_stars': 'shop', 'cmd_inventory': 'shop', 'cmd_shop': 'shop', 'cmd_tasks': 'shop', 'cmd_custom_title': 'shop', 'cmd_gift_stars': 'shop', 'cmd_halloween_pass': 'shop', 'cmd_pharmacy': 'shop', 'cmd_garage': 'shop', 'cmd_mini_games': 'games', 'cmd_fact_vd': 'games', 'cmd_trash': 'games', 'cmd_promo': 'games', 'cmd_brick': 'games', 'cmd_crash': 'games', 'cmd_stream': 'games', 'cmd_monopoly': 'games', 'cmd_garden': 'games', 'cmd_coinflip': 'games', 'cmd_football': 'games', 'cmd_basketball': 'games', 'cmd_darts': 'games', 'cmd_bowling': 'games', 'cmd_magic_ball': 'games', 'cmd_chance': 'games', 'cmd_detector': 'games', 'cmd_daily_heroes': 'games', 'cmd_backpack': 'games', 'cmd_wheel': 'games', 'cmd_mines': 'games', 'cmd_classic_mines': 'games', 'cmd_durak': 'games', 'cmd_dick': 'games', 'cmd_fap': 'games', 'cmd_bj': 'games', 'cmd_rps': 'games', 'cmd_memes': 'games', 'cmd_meme': 'games', 'cmd_story': 'games', 'cmd_resources_command': 'games', 'cmd_guild_command': 'games', 'cmd_player_market_command': 'games', 'cmd_raid_command': 'games', 'cmd_season_command': 'games', 'cmd_world_command': 'games', 'cmd_public_salary': 'economy', 'cmd_public_jobs': 'economy', 'cmd_work': 'economy', 'cmd_train': 'economy', 'cmd_sell': 'economy', 'cmd_iq': 'economy', 'cmd_fat': 'economy', 'cmd_foot': 'economy', 'cmd_chromosomes': 'economy', 'cmd_cook': 'economy', 'cmd_market': 'economy', 'cmd_portfolio': 'economy', 'cmd_pet': 'pets', 'cmd_walk_pet': 'pets', 'cmd_gear': 'pets', 'cmd_pet_clothes': 'pets', 'cmd_catch': 'pets', 'cmd_pet_fight': 'pets', 'cmd_business': 'businesses', 'cmd_miner': 'businesses', 'cmd_collect': 'businesses', 'cmd_loan': 'bank', 'cmd_repay': 'bank', 'cmd_bank': 'bank', 'cmd_case': 'bank', 'cmd_lottery': 'bank', 'cmd_history': 'bank', 'cmd_safe': 'bank', 'cmd_marry': 'family', 'cmd_family': 'family', 'cmd_gift': 'family', 'cmd_divorce': 'family', 'cmd_personal_home': 'family', 'cmd_house': 'family', 'cmd_sheriff': 'family', 'cmd_jail': 'family', 'cmd_escape': 'family', 'cmd_bail': 'family', 'admin_force_save_command': 'admin', 'admin_give_gif_command': 'admin', 'admin_give_stars_all_command': 'admin', 'admin_give_command': 'admin', 'cmd_global_stats': 'admin', 'cmd_economy_stats': 'admin', 'cmd_game_stats': 'admin', 'cmd_bot_status': 'admin', 'cmd_dashboard': 'admin', 'dragon_audio_file_id': 'admin', 'callback_inline': 'callbacks', 'process_stars_pre_checkout': 'callbacks', 'process_stars_successful_payment': 'callbacks'}


def register_all(ctx):
    """Register handlers in the exact order used by the legacy newfile.py."""
    registered = []
    for _name in REGISTRATION_ORDER:
        _group = GROUP_BY_HANDLER[_name]
        registered.extend(MODULES[_group].register(ctx, only=(_name,)))
    # Refresh every handler module after all handlers have been exported to the
    # shared newfile namespace. This preserves cross-module global references.
    for _module in MODULES.values():
        _module._inject(ctx)
    return registered
