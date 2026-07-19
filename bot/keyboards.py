"""인라인 버튼(키보드) 정의."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from . import config


def main_menu() -> InlineKeyboardMarkup:
    """메인 메뉴 버튼판."""
    rows = [
        [
            InlineKeyboardButton("📊 내 진행상황", callback_data="m:status"),
            InlineKeyboardButton("📋 규정", callback_data="m:rules"),
        ],
        [
            InlineKeyboardButton("👤 내 레벨", callback_data="m:mylevel"),
            InlineKeyboardButton("👥 멤버", callback_data="m:members"),
        ],
        [
            InlineKeyboardButton("📌 이번주 주제", callback_data="m:topic"),
            InlineKeyboardButton("🆕 멤버 등록", callback_data="m:register"),
        ],
        [
            InlineKeyboardButton("✍️ 데일리 제출", callback_data="m:daily"),
            InlineKeyboardButton("📝 위클리 제출", callback_data="m:weekly"),
        ],
        [
            InlineKeyboardButton("❓ 도움말", callback_data="m:help"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def level_menu() -> InlineKeyboardMarkup:
    """레벨 선택 버튼판 (등록용)."""
    rows = [[
        InlineKeyboardButton(f"레벨 {level}", callback_data=f"reg:{level}")
        for level in sorted(config.VALID_LEVELS)
    ]]
    rows.append([InlineKeyboardButton("⬅️ 메뉴로", callback_data="m:menu")])
    return InlineKeyboardMarkup(rows)


def back_to_menu() -> InlineKeyboardMarkup:
    """단독 '메뉴로' 버튼."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ 메뉴로", callback_data="m:menu")]]
    )
