"""Release changelog registry for NyaBot (/update command).

Versions are ordered oldest -> newest so the last element is always the
latest release. Adding a new release (e.g. 1.1, 1.2) automatically enables
inline Previous/Next navigation buttons in /update.
"""

from __future__ import annotations

from core.ui import card


CHANGELOG = [
    {
        "version": "1.0",
        "date": "23.11.2026",
        "title": "Большое обновление стиля, отношений и чат-механик",
        "added": [
            "Новый стиль карточек с <code>blockquote</code>, сворачиваемыми списками и прогресс-барами.",
            "Команда <code>/update</code> (<code>обнова</code>) с историей релизов и кнопками перелистывания.",
            "Интерактивное меню команд <code>/help</code> (<code>команды</code>) с вкладками-кнопками.",
            "Сводка дня <code>дейли</code> (<code>/daily</code>) и команда <code>собрать всё</code> для пассивного дохода.",
            "Инлайн-кнопки в <code>отн</code> (принятие, профиль пары, расставание), стрик пары, <code>отн топ</code>, улучшение домов и расширенный магазин подарков.",
            "PvP-дуэли на коины (<code>дуэль @user 500</code>), командные ограбления банка (<code>ограбление</code>) со связкой с тюрьмой и шерифом.",
            "Случайные чат-ивенты, итоги дня чата (<code>чат дня</code>), репутация (<code>+реп</code> / <code>топ реп</code>) и выбор бейджа из ачивок (<code>бейдж</code>).",
            "Живая биржа с мини-графиками тренда и новостью дня, «Ночной торговец» (<code>торговец</code>), недельная цель гильдии (<code>гильдия цель</code>), финансовый <code>чек</code> за 24 часа и уведомления в ЛС (<code>уведомления</code>).",
            "Новые автоответы на триггерные слова + админ-переключатели <code>автоответы вкл/выкл</code>, <code>ивенты вкл/выкл</code> и автоудаление приветствий.",
        ],
        "fixed": [
            "Починена кнопка перехода к Teletype-гайду в <code>/start</code>.",
            "Исправлены текстовые команды банка (<code>банк положить</code> / <code>банк снять</code>).",
            "Исправлено форматирование больших чисел, защита ссылок и фолбэк кастомных эмодзи в локализации.",
            "Ежедневные задания в <code>отн</code> теперь автоматически создаются при любом действии в новый день.",
            "Исправлен ложный ответ <code>отн отказать</code> без входящего предложения и лишние пробелы в командах.",
            "Удалены случайные пустые файлы-артефакты из репозитория.",
        ],
    },
]


def latest_index() -> int:
    return max(0, len(CHANGELOG) - 1)


def latest_version() -> str:
    return CHANGELOG[-1]["version"] if CHANGELOG else "1.0"


def get_entry(index: int) -> tuple[dict, int]:
    if not CHANGELOG:
        return ({"version": "1.0", "date": "", "title": "Релиз", "added": [], "fixed": []}, 0)
    clamped = max(0, min(len(CHANGELOG) - 1, int(index)))
    return CHANGELOG[clamped], clamped


def render_changelog_message(index: int | None = None) -> tuple[str, int, str | None, str | None]:
    """Return (html_text, clamped_index, prev_version, next_version)."""
    idx = latest_index() if index is None else int(index)
    entry, idx = get_entry(idx)
    version = entry["version"]
    date_str = entry.get("date", "")
    title_str = entry.get("title", "Обновление")

    header = f"🚀 <b>Обновление NyaBot v{version}</b>"
    if date_str:
        header += f" · <i>{date_str}</i>"

    summary = f"<b>{title_str}</b>"

    details = []
    added = entry.get("added") or []
    fixed = entry.get("fixed") or []
    if added:
        details.append("✨ <b>Что нового:</b>")
        for item in added:
            details.append(f"• {item}")
    if fixed:
        if details:
            details.append("")
        details.append("🛠 <b>Исправлено:</b>")
        for item in fixed:
            details.append(f"• {item}")

    prev_ver = CHANGELOG[idx - 1]["version"] if idx > 0 else None
    next_ver = CHANGELOG[idx + 1]["version"] if idx + 1 < len(CHANGELOG) else None

    footer_parts = [f"Версия {idx + 1} из {len(CHANGELOG)}"]
    if prev_ver or next_ver:
        footer_parts.append("Листай историю кнопками ниже 👇")
    text = card(
        header,
        body=summary,
        expandable=details if len(details) > 8 else None,
        footer=" · ".join(footer_parts),
    )
    if len(details) <= 8 and details:
        text = card(header, body=[summary, "", *details], footer=" · ".join(footer_parts))
    return text, idx, prev_ver, next_ver
