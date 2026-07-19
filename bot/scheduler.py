"""주간 벌금 집계 스케줄러.

한국시간(설정된 TZ) 기준 매주 월요일 08:00 에 지난 주 벌금을 집계·공지한다.
JobQueue 의 요일 인덱스 규약에 의존하지 않도록, 다음 실행 시점을 직접 계산해
주 1회 반복(run_repeating)으로 등록한다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes

from . import config, database, fines, weeks

logger = logging.getLogger(__name__)


def next_fine_datetime(now: datetime) -> datetime:
    """now 이후 가장 가까운 '월요일 FINE_HOUR:FINE_MINUTE' 시각(aware)."""
    days_ahead = (config.FINE_WEEKDAY - now.weekday()) % 7
    candidate = now.replace(
        hour=config.FINE_HOUR, minute=config.FINE_MINUTE, second=0, microsecond=0
    ) + timedelta(days=days_ahead)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def _target_chat_ids() -> list[int]:
    if config.ANNOUNCE_CHAT_ID:
        try:
            return [int(config.ANNOUNCE_CHAT_ID)]
        except ValueError:
            logger.warning("잘못된 ANNOUNCE_CHAT_ID: %s", config.ANNOUNCE_CHAT_ID)
    return database.all_chat_ids()


async def weekly_fine_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """지난 주 벌금 집계 후 각 단톡방에 공지."""
    now = datetime.now(config.TZ)
    # 월요일에 실행 → 지난 주 일요일을 대상 주간으로 삼는다.
    target_date = now.date() - timedelta(days=now.weekday() + 1)
    target_ordinal = weeks.week_ordinal(target_date)

    chat_ids = _target_chat_ids()
    if not chat_ids:
        logger.info("벌금 집계 대상 단톡방이 없습니다.")
        return

    for chat_id in chat_ids:
        try:
            # 그룹의 스터디 시작 주 이전이면 집계·공지하지 않는다.
            if target_ordinal < fines.get_program_start_ordinal(chat_id):
                logger.info("스터디 시작 이전 주간 → 집계 건너뜀 (chat=%s, 대상 %s)",
                            chat_id, target_date)
                continue
            report = fines.compute_weekly_report(chat_id, target_date)
            text = fines.format_report(report)
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            logger.info("벌금 공지 전송 완료 (chat=%s, 총 %s원)", chat_id, report.total)
        except Exception:  # noqa: BLE001
            logger.exception("벌금 공지 전송 실패 (chat=%s)", chat_id)


def schedule_weekly_fine(app: Application) -> None:
    if app.job_queue is None:
        logger.error(
            "JobQueue 를 사용할 수 없습니다. "
            "'pip install \"python-telegram-bot[job-queue]\"' 로 설치하세요."
        )
        return

    now = datetime.now(config.TZ)
    first = next_fine_datetime(now)
    app.job_queue.run_repeating(
        weekly_fine_job,
        interval=timedelta(weeks=1),
        first=first,
        name="weekly_fine",
    )
    logger.info("주간 벌금 집계 예약: 최초 실행 %s (매주 반복)", first.isoformat())
