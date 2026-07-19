"""봇 진입점."""

from __future__ import annotations

import logging
import sys

from telegram.ext import Application, CommandHandler

from . import config, database, handlers, scheduler

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("study_bot")


def build_application() -> Application:
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN 이 설정되지 않았습니다. .env 를 확인하세요.")
        sys.exit(1)

    database.init_db()

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # 명령 핸들러 등록
    app.add_handler(CommandHandler("start", handlers.cmd_start))
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

    scheduler.schedule_weekly_fine(app)

    logger.info("스터디 봇 시작 (TZ=%s, Notion=%s)",
                config.TIMEZONE_NAME, "ON" if config.NOTION_ENABLED else "OFF")
    return app


def main() -> None:
    app = build_application()
    app.run_polling(allowed_updates=None)


if __name__ == "__main__":
    main()
