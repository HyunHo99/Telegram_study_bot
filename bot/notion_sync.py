"""Notion 아카이빙.

상위 페이지 아래에 "스터디 제출 아카이브" 데이터베이스를 만들고(최초 1회),
각 제출물을 그 데이터베이스의 행(row)으로 저장한다. 날짜 속성이 있으므로
Notion 에서 캘린더 뷰로 전환하면 날짜별로 제출이 표시된다.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from . import config, database
from .weeks import week_label

logger = logging.getLogger(__name__)

_client = None  # notion_client.AsyncClient

# Notion rich_text 블록 하나의 최대 길이 제한(2000)보다 여유 있게 설정.
_MAX_BLOCK_CHARS = 1800

# 그룹(chat)별 데이터베이스 ID 를 저장할 설정 키.
_DB_SETTING_KEY = "notion_db_id"

# 속성(컬럼) 이름 — 한 곳에서 관리.
P_TITLE = "제출"
P_MEMBER = "멤버"
P_KIND = "종류"
P_LEVEL = "레벨"
P_DATE = "날짜"
P_CHARS = "분량(자)"
P_WEEK = "주차"


def _get_client():
    global _client
    if _client is None:
        from notion_client import AsyncClient  # 지연 임포트

        _client = AsyncClient(auth=config.NOTION_TOKEN)
    return _client


def _text_blocks(content: str) -> list[dict]:
    """긴 텍스트를 Notion paragraph 블록 리스트로 변환한다."""
    blocks: list[dict] = []
    for paragraph in content.split("\n"):
        chunk = paragraph
        if not chunk:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": []},
            })
            continue
        while chunk:
            piece, chunk = chunk[:_MAX_BLOCK_CHARS], chunk[_MAX_BLOCK_CHARS:]
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": piece}}]
                },
            })
    return blocks or [{
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": []},
    }]


def _database_schema() -> dict:
    """제출 아카이브 데이터베이스의 속성 정의."""
    return {
        P_TITLE: {"title": {}},
        P_MEMBER: {"rich_text": {}},
        P_KIND: {"select": {"options": [
            {"name": "데일리", "color": "blue"},
            {"name": "위클리", "color": "orange"},
        ]}},
        P_LEVEL: {"select": {"options": [
            {"name": "레벨 3", "color": "red"},
            {"name": "레벨 2", "color": "yellow"},
            {"name": "레벨 1", "color": "gray"},
        ]}},
        P_DATE: {"date": {}},
        P_CHARS: {"number": {"format": "number"}},
        P_WEEK: {"rich_text": {}},
    }


async def ensure_database(chat_id: int) -> Optional[str]:
    """그룹의 제출 아카이브 데이터베이스를 찾거나 생성하고 database_id 를 반환한다."""
    if not config.NOTION_ENABLED or not config.NOTION_PARENT_PAGE_ID:
        return None

    cached = database.get_setting(chat_id, _DB_SETTING_KEY, "")
    if cached:
        return cached

    client = _get_client()
    try:
        resp = await client.databases.create(
            parent={"type": "page_id", "page_id": config.NOTION_PARENT_PAGE_ID},
            title=[{"type": "text", "text": {"content": "스터디 제출 아카이브"}}],
            description=[{"type": "text", "text": {
                "content": "데일리/위클리 제출 기록. '날짜' 기준 캘린더 뷰를 추가하면 달력으로 볼 수 있습니다."
            }}],
            properties=_database_schema(),
        )
        db_id = resp["id"]
        database.set_setting(chat_id, _DB_SETTING_KEY, db_id)
        logger.info("Notion 제출 아카이브 DB 생성 (chat=%s, db=%s)", chat_id, db_id)
        return db_id
    except Exception:  # noqa: BLE001 - Notion 실패가 봇 전체를 막지 않도록
        logger.exception("Notion 데이터베이스 생성 실패 (chat=%s)", chat_id)
        return None


async def archive_submission(chat_id: int, kind: str, display_name: str,
                             content: str, target_date: date,
                             level: int = config.DEFAULT_LEVEL) -> Optional[str]:
    """제출물을 아카이브 데이터베이스의 행으로 추가하고 URL 을 반환한다."""
    if not config.NOTION_ENABLED or not config.NOTION_PARENT_PAGE_ID:
        return None

    db_id = await ensure_database(chat_id)
    if not db_id:
        return None

    kind_label = "데일리" if kind == "daily" else "위클리"
    level_label = f"레벨 {level}"
    title = f"{display_name} · {kind_label}"
    client = _get_client()
    try:
        resp = await client.pages.create(
            parent={"type": "database_id", "database_id": db_id},
            properties={
                P_TITLE: {"title": [{"type": "text", "text": {"content": title}}]},
                P_MEMBER: {"rich_text": [{"type": "text", "text": {"content": display_name}}]},
                P_KIND: {"select": {"name": kind_label}},
                P_LEVEL: {"select": {"name": level_label}},
                P_DATE: {"date": {"start": target_date.isoformat()}},
                P_CHARS: {"number": len(content)},
                P_WEEK: {"rich_text": [{"type": "text", "text": {"content": week_label(target_date)}}]},
            },
            children=_text_blocks(content),
        )
        return resp.get("url")
    except Exception:  # noqa: BLE001
        logger.exception("Notion 제출 아카이빙 실패 (chat=%s, %s)", chat_id, title)
        return None
