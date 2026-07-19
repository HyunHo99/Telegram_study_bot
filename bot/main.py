"""봇 진입점."""

from __future__ import annotations

import logging
import sys

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from . import config, database, handlers, scheduler

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("study_bot")


# 봇 프로필/온보딩 문구 (BotFather 의 setdescription / setabouttext 와 동일 효과)
BOT_DESCRIPTION = (
    "📚 증권사 리포트 스터디 봇입니다.\n\n"
    "레벨별 데일리/위클리 과제 제출을 관리하고, Notion 에 자동 아카이빙하며, "
    "매주 월요일 아침 벌금을 자동 집계·공지합니다.\n\n"
    "아래 [시작] 을 누른 뒤 /menu 로 버튼을 사용하세요."
)  # 빈 채팅 화면에 표시 (최대 512자)

BOT_SHORT_DESCRIPTION = (
    "증권사 리포트 스터디 과제·벌금 관리 봇. /menu 로 시작하세요."
)  # 프로필에 표시 (최대 120자)


async def _on_error(update: object, context) -> None:
    """처리되지 않은 예외를 로깅한다 (한 명령의 오류가 봇을 멈추지 않도록)."""
    logger.error("핸들러 처리 중 예외 발생", exc_info=context.error)


async def _post_init(app: Application) -> None:
    """텔레그램 명령 목록 및 봇 소개 문구를 등록한다."""
    await app.bot.set_my_commands([
        BotCommand("menu", "버튼 메뉴 열기"),
        BotCommand("status", "내 이번 주 진행상황"),
        BotCommand("daily", "데일리 과제 제출"),
        BotCommand("weekly", "위클리 과제 제출"),
        BotCommand("rules", "레벨별 규정"),
        BotCommand("mylevel", "내 레벨 확인"),
        BotCommand("members", "멤버 목록"),
        BotCommand("topic", "이번 주 위클리 주제"),
        BotCommand("register", "멤버 등록"),
        BotCommand("help", "도움말"),
    ])
    await app.bot.set_my_description(BOT_DESCRIPTION)
    await app.bot.set_my_short_description(BOT_SHORT_DESCRIPTION)


def build_application() -> Application:
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN 이 설정되지 않았습니다. .env 를 확인하세요.")
        sys.exit(1)

    database.init_db()

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).post_init(_post_init).build()

    # 그룹→슈퍼그룹 전환 시 데이터 자동 이전 (다른 핸들러보다 먼저)
    app.add_handler(MessageHandler(
        filters.StatusUpdate.MIGRATE, handlers.on_chat_migration
    ))

    # 명령 핸들러 등록
    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("menu", handlers.cmd_menu))
    app.add_handler(CommandHandler("help", handlers.cmd_help))

    app.add_handler(CommandHandler("register", handlers.cmd_register))
    app.add_handler(CommandHandler("setlevel", handlers.cmd_setlevel))
    app.add_handler(CommandHandler("mylevel", handlers.cmd_mylevel))
    app.add_handler(CommandHandler("members", handlers.cmd_members))
    app.add_handler(CommandHandler("rules", handlers.cmd_rules))

    app.add_handler(CommandHandler("topic", handlers.cmd_topic))

    app.add_handler(CommandHandler("daily", handlers.cmd_daily))
    app.add_handler(CommandHandler("weekly", handlers.cmd_weekly))

    app.add_handler(CommandHandler("status", handlers.cmd_status))
    app.add_handler(CommandHandler("fine", handlers.cmd_fine))
    app.add_handler(CommandHandler("fine_preview", handlers.cmd_fine_preview))
    app.add_handler(CommandHandler("reset", handlers.cmd_reset))

    # 버튼(콜백) 처리
    app.add_handler(CallbackQueryHandler(handlers.on_callback))
    # 제출 유도(ForceReply) 메시지에 대한 답장 수신
    app.add_handler(MessageHandler(
        filters.REPLY & filters.TEXT & ~filters.COMMAND,
        handlers.on_reply_submission,
    ))

    app.add_error_handler(_on_error)

    scheduler.schedule_weekly_fine(app)

    logger.info("스터디 봇 시작 (TZ=%s, Notion=%s)",
                config.TIMEZONE_NAME, "ON" if config.NOTION_ENABLED else "OFF")
    return app


def main() -> None:
    app = build_application()
    app.run_polling(allowed_updates=None)


if __name__ == "__main__":
    main()
