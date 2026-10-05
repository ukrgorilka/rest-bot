import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parent
code=(ROOT/'newfile.py').read_text(encoding='utf-8')
ast.parse(code)

# Static contract checks: keep critical v0.3 strings/functions present.
for needle in (
    "BUSINESS_TAX_RATE",
    "BUSINESS_SELL_RATE",
    "LEGACY_BUSINESS_REPLACEMENTS",
    "intergalactic_port",
    "render_business_detail",
    "broadcast_system_message",
    "biz_detail_buy:",
    "biz_detail_up:",
    "biz_detail_sell:",
):
    assert needle in code, needle

print('v0.3 static contract: PASS')

mod_code=(ROOT/'handlers/moderation.py').read_text(encoding='utf-8')
biz_code=(ROOT/'handlers/businesses.py').read_text(encoding='utf-8')
source_code=(ROOT/'newfile.py').read_text(encoding='utf-8')
cb_code=(ROOT/'handlers/callbacks.py').read_text(encoding='utf-8')
assert "re.fullmatch(r'бизнес\\s+\\d+', text_lower)" in mod_code
assert "render_business_detail(message.chat.id,user_id,user_name,number)" in biz_code
# Catalog remains button-free; concrete owned/unowned cards use only their intended action buttons.
assert "_render_business_catalog(chat_id, user_id, user_name, message_id=None)" in source_code
assert "kb.add(InlineKeyboardButton('⬆️ Улучшить'" in source_code
assert "kb.add(InlineKeyboardButton('💸 Продать'" in source_code
assert "kb.add(InlineKeyboardButton('🛒 Купить'" in source_code
assert "_delete_message_quietly(chat_id,call.message.message_id)" in cb_code
print('v0.3 business UX contract: PASS')
