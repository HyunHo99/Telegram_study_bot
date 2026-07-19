"""텔레그램 관련 공통 유틸리티."""

from __future__ import annotations

from datetime import date

from telegram import Chat, Update, User
from telegram.ext import ContextTypes

from . import config


def display_name(user: User) -> str:
    """사용자 표시 이름 (풀네임 우선, 없으면 @username)."""
    name = user.full_name.strip() if user.full_name else ""
    if name:
        return name
    if user.username:
        return f"@{user.username}"
    return f"user_{user.id}"


def today() -> date:
    """설정된 시간대 기준 오늘 날짜."""
    from datetime import datetime

    return datetime.now(config.TZ).date()


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """관리 명령 실행 권한 확인.

    - ADMIN_USER_IDS 가 설정되어 있으면 그 목록에 포함된 사용자만 허용.
    - 설정이 없으면 개인 채팅이거나 그룹 관리자면 허용.
    """
    user = update.effective_user
    chat = update.effective_chat
    if user is None or chat is None:
        return False

    if config.ADMIN_USER_IDS:
        return user.id in config.ADMIN_USER_IDS

    if chat.type == Chat.PRIVATE:
        return True

    try:
        member = await chat.get_member(user.id)
        return member.status in ("administrator", "creator")
    except Exception:  # noqa: BLE001
        return False


def parse_level(text: str) -> int | None:
    """'3', '레벨3', 'level 2' 등에서 레벨 숫자 추출."""
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    try:
        level = int(digits)
    except ValueError:
        return None
    return level if level in config.VALID_LEVELS else None
