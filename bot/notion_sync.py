"""Notion 아카이빙.

상위 페이지 아래에 주차별 페이지(예: 2026-W30)를 만들고,
각 제출물을 그 주차 페이지의 하위 페이지로 아카이빙한다.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from . import config, database, weeks

logger = logging.getLogger(__name__)

_client = None  # notion_client.AsyncClient

# Notion rich_text 블록 하나의 최대 길이 제한(2000)보다 여유 있게 설정.
_MAX_BLOCK_CHARS = 1800


def _get_client():
    global _client
    if _client is None:
        from notion_client import AsyncClient  # 지연 임포트

        _client = AsyncClient(auth=config.NOTION_TOKEN)
    return _client


def _text_blocks(content: str) -> list[dict]:
    """긴 텍스트를 Notion paragraph 블록 리스트로 변환한다."""
    blocks: list[dict] = []
    # 문단(빈 줄 기준) 단위로 나눈 뒤, 길이 제한에 맞춰 다시 쪼갠다.
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


def _title_prop(title: str) -> dict:
    return {"title": {"title": [{"type": "text", "text": {"content": title}}]}}


async def ensure_week_page(chat_id: int, target_date: date) -> Optional[str]:
    """주차 페이지를 찾거나 생성하고 page_id 를 반환한다."""
    if not config.NOTION_ENABLED or not config.NOTION_PARENT_PAGE_ID:
        return None

    year, week = weeks.iso_of(target_date)
    cached = database.get_notion_week_page(chat_id, year, week)
    if cached:
        return cached

    client = _get_client()
    label = weeks.week_label(target_date)
    try:
        resp = await client.pages.create(
            parent={"page_id": config.NOTION_PARENT_PAGE_ID},
            properties=_title_prop(f"{label} 스터디 아카이브"),
        )
        page_id = resp["id"]
        database.set_notion_week_page(chat_id, year, week, page_id)
        return page_id
    except Exception:  # noqa: BLE001 - Notion 실패가 봇 전체를 막지 않도록
        logger.exception("Notion 주차 페이지 생성 실패 (chat=%s, %s)", chat_id, label)
        return None


async def archive_submission(chat_id: int, kind: str, display_name: str,
                             content: str, target_date: date) -> Optional[str]:
    """제출물을 주차 페이지의 하위 페이지로 만들고 URL 을 반환한다."""
    if not config.NOTION_ENABLED or not config.NOTION_PARENT_PAGE_ID:
        return None

    week_page_id = await ensure_week_page(chat_id, target_date)
    if not week_page_id:
        return None

    kind_label = "데일리" if kind == "daily" else "위클리"
    title = f"[{kind_label}] {display_name} · {target_date.isoformat()}"
    client = _get_client()
    try:
        resp = await client.pages.create(
            parent={"page_id": week_page_id},
            properties=_title_prop(title),
            children=_text_blocks(content),
        )
        return resp.get("url")
    except Exception:  # noqa: BLE001
        logger.exception("Notion 제출 아카이빙 실패 (chat=%s, %s)", chat_id, title)
        return None
