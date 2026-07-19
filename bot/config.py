"""환경설정 및 스터디 레벨/과제/벌금 규정 정의."""

from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int_list(name: str) -> set[int]:
    raw = os.getenv(name, "")
    result: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part:
            try:
                result.add(int(part))
            except ValueError:
                continue
    return result


# ===== Telegram =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANNOUNCE_CHAT_ID = os.getenv("ANNOUNCE_CHAT_ID", "").strip() or None
ADMIN_USER_IDS = _get_int_list("ADMIN_USER_IDS")

# ===== Notion =====
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_PARENT_PAGE_ID = os.getenv("NOTION_PARENT_PAGE_ID", "").strip()
NOTION_ENABLED = _get_bool("NOTION_ENABLED", True) and bool(NOTION_TOKEN)

# ===== 시간대 / 저장소 =====
TIMEZONE_NAME = os.getenv("TIMEZONE", "Asia/Seoul")
TZ = ZoneInfo(TIMEZONE_NAME)
DB_PATH = os.getenv("DB_PATH", "data/study_bot.db")

# 벌금 집계 스케줄 (한국시간 기준). 매주 월요일 08:00.
FINE_WEEKDAY = 0  # Monday (Python: Monday=0)
FINE_HOUR = 8
FINE_MINUTE = 0

# 권장 최소 분량(자). 검증/거부는 하지 않고 안내 표시용으로만 사용.
RECOMMENDED_MIN_CHARS = 300


@dataclass(frozen=True)
class LevelRule:
    """레벨별 과제 요구량 및 벌금 규정.

    daily_required      : 한 주(월~일) 데일리 제출 요구 횟수
    weekly_required     : 한 주기 위클리 제출 요구 횟수
    weekly_period_weeks : 위클리 과제 주기(주 단위). 0이면 위클리 없음.
    daily_fine          : 데일리 1회 미달당 벌금(원)
    weekly_fine         : 위클리 1회 미달당 벌금(원)
    """

    level: int
    label: str
    daily_required: int
    weekly_required: int
    weekly_period_weeks: int
    daily_fine: int
    weekly_fine: int


# 요구사항에 명시된 규정.
#   레벨3: 데일리 3회 / 위클리 1주 1회  / 벌금 데일리 1,000 위클리 3,000
#   레벨2: 데일리 3회 / 위클리 2주 1회  / 벌금 데일리 1,000 위클리 5,000
#   레벨1: 데일리 3회 / 위클리 없음     / 벌금 데일리 2,000
LEVEL_RULES: dict[int, LevelRule] = {
    3: LevelRule(3, "레벨3️⃣", daily_required=3, weekly_required=1, weekly_period_weeks=1,
                 daily_fine=1000, weekly_fine=3000),
    2: LevelRule(2, "레벨2️⃣", daily_required=3, weekly_required=1, weekly_period_weeks=2,
                 daily_fine=1000, weekly_fine=5000),
    1: LevelRule(1, "레벨1️⃣", daily_required=3, weekly_required=0, weekly_period_weeks=0,
                 daily_fine=2000, weekly_fine=0),
}

DEFAULT_LEVEL = 1
VALID_LEVELS = tuple(sorted(LEVEL_RULES.keys()))


def get_rule(level: int) -> LevelRule:
    return LEVEL_RULES.get(level, LEVEL_RULES[DEFAULT_LEVEL])
