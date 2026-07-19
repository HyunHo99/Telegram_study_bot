"""SQLite 저장소 계층.

python-telegram-bot 핸들러는 단일 이벤트 루프 스레드에서 실행되므로
간단한 동기 sqlite3 사용으로 충분하다.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Optional

from . import config

_conn: Optional[sqlite3.Connection] = None


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL;")
        _conn.execute("PRAGMA foreign_keys=ON;")
    return _conn


def init_db() -> None:
    conn = _connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            chat_id       INTEGER NOT NULL,
            user_id       INTEGER NOT NULL,
            display_name  TEXT NOT NULL DEFAULT '',
            level         INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT NOT NULL,
            updated_at    TEXT NOT NULL,
            PRIMARY KEY (chat_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS submissions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id     INTEGER NOT NULL,
            user_id     INTEGER NOT NULL,
            kind        TEXT NOT NULL CHECK (kind IN ('daily','weekly')),
            content     TEXT NOT NULL DEFAULT '',
            char_count  INTEGER NOT NULL DEFAULT 0,
            iso_year    INTEGER NOT NULL,
            iso_week    INTEGER NOT NULL,
            created_at  TEXT NOT NULL,
            notion_url  TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_sub_lookup
            ON submissions (chat_id, user_id, kind, iso_year, iso_week);

        CREATE TABLE IF NOT EXISTS settings (
            chat_id INTEGER NOT NULL,
            key     TEXT NOT NULL,
            value   TEXT NOT NULL,
            PRIMARY KEY (chat_id, key)
        );

        CREATE TABLE IF NOT EXISTS notion_week_pages (
            chat_id   INTEGER NOT NULL,
            iso_year  INTEGER NOT NULL,
            iso_week  INTEGER NOT NULL,
            page_id   TEXT NOT NULL,
            PRIMARY KEY (chat_id, iso_year, iso_week)
        );
        """
    )
    conn.commit()


def _now() -> str:
    return datetime.now(config.TZ).isoformat(timespec="seconds")


# ===== 사용자 / 레벨 =====

def upsert_user(chat_id: int, user_id: int, display_name: str,
                level: Optional[int] = None) -> None:
    """사용자를 등록하거나 표시 이름/레벨을 갱신한다.

    level 이 None 이면 기존 레벨을 유지하고, 신규 사용자는 기본 레벨로 등록한다.
    """
    conn = _connect()
    now = _now()
    existing = get_user(chat_id, user_id)
    if existing is None:
        conn.execute(
            "INSERT INTO users (chat_id, user_id, display_name, level, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (chat_id, user_id, display_name,
             level if level is not None else config.DEFAULT_LEVEL, now, now),
        )
    else:
        new_level = level if level is not None else existing["level"]
        conn.execute(
            "UPDATE users SET display_name = ?, level = ?, updated_at = ?"
            " WHERE chat_id = ? AND user_id = ?",
            (display_name or existing["display_name"], new_level, now, chat_id, user_id),
        )
    conn.commit()


def set_level(chat_id: int, user_id: int, level: int, display_name: str = "") -> None:
    upsert_user(chat_id, user_id, display_name, level)


def get_user(chat_id: int, user_id: int) -> Optional[sqlite3.Row]:
    conn = _connect()
    cur = conn.execute(
        "SELECT * FROM users WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)
    )
    return cur.fetchone()


def list_users(chat_id: int) -> list[sqlite3.Row]:
    conn = _connect()
    cur = conn.execute(
        "SELECT * FROM users WHERE chat_id = ? ORDER BY level DESC, display_name",
        (chat_id,),
    )
    return list(cur.fetchall())


def migrate_chat(old_chat_id: int, new_chat_id: int) -> None:
    """그룹이 슈퍼그룹으로 전환되어 chat_id 가 바뀐 경우 모든 데이터를 새 id 로 이전한다.

    chat_id 가 기본키 일부인 테이블은 충돌 시 기존(옛 그룹) 데이터를 우선한다(REPLACE).
    """
    conn = _connect()
    conn.execute("UPDATE OR REPLACE users SET chat_id = ? WHERE chat_id = ?",
                 (new_chat_id, old_chat_id))
    conn.execute("UPDATE submissions SET chat_id = ? WHERE chat_id = ?",
                 (new_chat_id, old_chat_id))
    conn.execute("UPDATE OR REPLACE settings SET chat_id = ? WHERE chat_id = ?",
                 (new_chat_id, old_chat_id))
    conn.execute("UPDATE OR REPLACE notion_week_pages SET chat_id = ? WHERE chat_id = ?",
                 (new_chat_id, old_chat_id))
    conn.commit()


def all_chat_ids() -> list[int]:
    conn = _connect()
    cur = conn.execute("SELECT DISTINCT chat_id FROM users")
    return [r["chat_id"] for r in cur.fetchall()]


# ===== 제출 =====

def add_submission(chat_id: int, user_id: int, kind: str, content: str,
                   iso_year: int, iso_week: int,
                   notion_url: Optional[str] = None) -> int:
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO submissions"
        " (chat_id, user_id, kind, content, char_count, iso_year, iso_week, created_at, notion_url)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (chat_id, user_id, kind, content, len(content), iso_year, iso_week, _now(), notion_url),
    )
    conn.commit()
    return cur.lastrowid


def set_submission_notion_url(submission_id: int, url: str) -> None:
    conn = _connect()
    conn.execute("UPDATE submissions SET notion_url = ? WHERE id = ?", (url, submission_id))
    conn.commit()


def count_submissions(chat_id: int, user_id: int, kind: str,
                      iso_year: int, iso_week: int) -> int:
    conn = _connect()
    cur = conn.execute(
        "SELECT COUNT(*) AS c FROM submissions"
        " WHERE chat_id = ? AND user_id = ? AND kind = ? AND iso_year = ? AND iso_week = ?",
        (chat_id, user_id, kind, iso_year, iso_week),
    )
    return cur.fetchone()["c"]


def count_submissions_on_date(chat_id: int, user_id: int, kind: str,
                              date_iso: str) -> int:
    """특정 날짜(YYYY-MM-DD)에 해당 종류의 제출 수. created_at 앞 10자 기준."""
    conn = _connect()
    cur = conn.execute(
        "SELECT COUNT(*) AS c FROM submissions"
        " WHERE chat_id = ? AND user_id = ? AND kind = ? AND substr(created_at, 1, 10) = ?",
        (chat_id, user_id, kind, date_iso),
    )
    return cur.fetchone()["c"]


def count_submissions_in_weeks(chat_id: int, user_id: int, kind: str,
                               weeks: list[tuple[int, int]]) -> int:
    """여러 (iso_year, iso_week) 주에 걸친 제출 수 합계 (위클리 주기 계산용)."""
    if not weeks:
        return 0
    conn = _connect()
    placeholders = " OR ".join(["(iso_year = ? AND iso_week = ?)"] * len(weeks))
    params: list[int] = [chat_id, user_id, kind]
    for y, w in weeks:
        params.extend([y, w])
    cur = conn.execute(
        f"SELECT COUNT(*) AS c FROM submissions"
        f" WHERE chat_id = ? AND user_id = ? AND kind = ? AND ({placeholders})",
        params,
    )
    return cur.fetchone()["c"]


# ===== 설정 (그룹별) =====

def set_setting(chat_id: int, key: str, value: str) -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO settings (chat_id, key, value) VALUES (?, ?, ?)"
        " ON CONFLICT(chat_id, key) DO UPDATE SET value = excluded.value",
        (chat_id, key, value),
    )
    conn.commit()


def get_setting(chat_id: int, key: str, default: str = "") -> str:
    conn = _connect()
    cur = conn.execute(
        "SELECT value FROM settings WHERE chat_id = ? AND key = ?", (chat_id, key)
    )
    row = cur.fetchone()
    return row["value"] if row else default


# ===== Notion 주차 페이지 캐시 =====

def get_notion_week_page(chat_id: int, iso_year: int, iso_week: int) -> Optional[str]:
    conn = _connect()
    cur = conn.execute(
        "SELECT page_id FROM notion_week_pages"
        " WHERE chat_id = ? AND iso_year = ? AND iso_week = ?",
        (chat_id, iso_year, iso_week),
    )
    row = cur.fetchone()
    return row["page_id"] if row else None


def set_notion_week_page(chat_id: int, iso_year: int, iso_week: int, page_id: str) -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO notion_week_pages (chat_id, iso_year, iso_week, page_id)"
        " VALUES (?, ?, ?, ?)"
        " ON CONFLICT(chat_id, iso_year, iso_week) DO UPDATE SET page_id = excluded.page_id",
        (chat_id, iso_year, iso_week, page_id),
    )
    conn.commit()
