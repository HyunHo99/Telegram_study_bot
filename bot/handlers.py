"""텔레그램 명령 핸들러."""

from __future__ import annotations

import logging
from datetime import timedelta

from telegram import ForceReply, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from . import config, database, fines, keyboards, notion_sync, weeks
from .telegram_utils import display_name, is_admin, parse_level, today

logger = logging.getLogger(__name__)

WEEKLY_TOPIC_KEY = "weekly_topic"
# ForceReply 로 유도한 제출 대기 상태 저장 키 (application.bot_data)
PENDING_SUB_KEY = "pending_submissions"


# ===================== 도움말 =====================

# 주의: 명령에 밑줄(_)이 포함되어 있어 Markdown 파싱이 깨지므로 일반 텍스트로 전송한다.
HELP_TEXT = (
    "📚 스터디 봇 도움말\n\n"
    "▪ 멤버 명령\n"
    "• /register [레벨] — 스터디 멤버로 등록 (레벨 미입력 시 1)\n"
    "• /daily <내용> — 데일리 과제 제출 (내용 대신 메시지에 답장해도 됨)\n"
    "• /weekly <내용> — 위클리 과제 제출\n"
    "• /status — 이번 주 내 과제 진행 상황\n"
    "• /mylevel — 내 레벨/규정 확인\n"
    "• /members — 멤버 및 레벨 목록\n"
    "• /rules — 레벨별 과제/벌금 규정\n"
    "• /topic — 이번 주 위클리 과제 방향 확인\n\n"
    "▪ 관리자 명령\n"
    "• /setlevel <레벨> — (대상 메시지에 답장하여) 해당 멤버 레벨 설정\n"
    "• /setlevel <user_id> <레벨> — user_id 로 레벨 설정\n"
    "• /remove — (대상 메시지에 답장 또는 user_id) 멤버 삭제\n"
    "• /topic <내용> — 이번 주 위클리 과제 방향 공지/설정\n"
    "• /fine — 지난 주 벌금 지금 집계·공지\n"
    "• /fine_preview — 이번 주 현재까지 기준 벌금 미리보기\n"
    "• /reset — 집계 기준을 이번 주부터로 리셋 (제출 기록은 유지)\n\n"
    "💡 /menu 를 입력하면 버튼으로 편하게 쓸 수 있어요."
)

MENU_TEXT = "📚 *스터디 봇 메뉴*\n원하는 항목을 눌러 주세요."


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_menu(update, context)


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        MENU_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboards.main_menu()
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP_TEXT)


# ===================== 레벨 / 멤버 =====================

def _register_user(chat_id: int, user, level: int | None) -> str:
    """멤버를 등록/갱신하고 결과 메시지 텍스트를 반환한다."""
    existing = database.get_user(chat_id, user.id)
    database.upsert_user(chat_id, user.id, display_name(user), level)
    saved = database.get_user(chat_id, user.id)
    rule = config.get_rule(saved["level"])
    verb = "등록" if existing is None else "정보 갱신"
    return (
        f"✅ {display_name(user)} 님 {verb} 완료 — {rule.label}\n{_rule_line(rule)}"
    )


async def cmd_register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat

    # 레벨을 지정하지 않으면 버튼으로 물어본다.
    if not context.args:
        await update.effective_message.reply_text(
            "등록할 레벨을 선택하세요:", reply_markup=keyboards.level_menu()
        )
        return

    level = parse_level(" ".join(context.args))
    if level is None:
        await update.effective_message.reply_text(
            f"레벨은 {', '.join(map(str, config.VALID_LEVELS))} 중 하나여야 합니다."
        )
        return

    await update.effective_message.reply_text(
        _register_user(chat.id, user, level), parse_mode=ParseMode.MARKDOWN
    )


async def cmd_setlevel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update, context):
        await update.effective_message.reply_text("⛔ 관리자만 사용할 수 있는 명령입니다.")
        return

    chat = update.effective_chat
    msg = update.effective_message
    reply = msg.reply_to_message

    target_id: int | None = None
    target_name = ""
    level: int | None = None

    if reply is not None and reply.from_user is not None:
        # 대상 메시지에 답장 + /setlevel <레벨>
        target_id = reply.from_user.id
        target_name = display_name(reply.from_user)
        level = parse_level(" ".join(context.args)) if context.args else None
    elif len(context.args) >= 2:
        # /setlevel <user_id> <레벨>
        try:
            target_id = int(context.args[0])
        except ValueError:
            target_id = None
        level = parse_level(context.args[1])

    if target_id is None or level is None:
        await msg.reply_text(
            "사용법:\n"
            "• 대상 메시지에 답장 후 `/setlevel 3`\n"
            "• 또는 `/setlevel <user_id> <레벨>`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    existing = database.get_user(chat.id, target_id)
    if target_name == "" and existing is not None:
        target_name = existing["display_name"]
    database.set_level(chat.id, target_id, level, target_name)
    rule = config.get_rule(level)
    await msg.reply_text(
        f"✅ {target_name or target_id} 님 레벨을 *{rule.label}* 로 설정했습니다.\n{_rule_line(rule)}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """멤버를 삭제한다 (관리자). 대상 메시지에 답장하거나 user_id 로 지정."""
    if not await is_admin(update, context):
        await update.effective_message.reply_text("⛔ 관리자만 사용할 수 있는 명령입니다.")
        return

    chat = update.effective_chat
    msg = update.effective_message
    reply = msg.reply_to_message

    target_id: int | None = None
    target_name = ""
    if reply is not None and reply.from_user is not None:
        target_id = reply.from_user.id
        target_name = display_name(reply.from_user)
    elif context.args:
        try:
            target_id = int(context.args[0])
        except ValueError:
            target_id = None

    if target_id is None:
        await msg.reply_text(
            "사용법:\n"
            "• 대상 메시지에 답장 후 `/remove`\n"
            "• 또는 `/remove <user_id>`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    existing = database.get_user(chat.id, target_id)
    if existing is None:
        await msg.reply_text("해당 멤버는 등록되어 있지 않습니다.")
        return

    name = target_name or existing["display_name"]
    database.delete_user(chat.id, target_id)
    await msg.reply_text(
        f"🗑 *{name}* 님을 멤버에서 삭제했습니다.\n"
        f"(제출 기록은 보관됩니다. 다시 참여하려면 `/register` 하면 됩니다.)",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_mylevel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    row = database.get_user(chat.id, user.id)
    if row is None:
        await update.effective_message.reply_text(
            "아직 등록되지 않았습니다. `/register` 로 먼저 등록해 주세요.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    rule = config.get_rule(row["level"])
    await update.effective_message.reply_text(
        f"👤 {row['display_name']} — *{rule.label}*\n{_rule_line(rule)}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    members = database.list_users(chat.id)
    if not members:
        await update.effective_message.reply_text("아직 등록된 멤버가 없습니다.")
        return
    lines = ["👥 *멤버 목록*"]
    for m in members:
        rule = config.get_rule(m["level"])
        lines.append(f"• {m['display_name']} — {rule.label}")
    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.MARKDOWN
    )


async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = ["📋 *레벨별 과제/벌금 규정*", ""]
    for level in sorted(config.VALID_LEVELS, reverse=True):
        rule = config.get_rule(level)
        lines.append(f"*{rule.label}*")
        lines.append(_rule_line(rule))
        lines.append("")
    lines.append("📍 정기과제/위클리: 증권사 리포트를 읽고 내용요약·느낀점 작성")
    lines.append(f"   (권장 최소 분량 {config.RECOMMENDED_MIN_CHARS}자)")
    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.MARKDOWN
    )


def _rule_line(rule: config.LevelRule) -> str:
    weekly = (
        f"위클리 {rule.weekly_period_weeks}주 1회" if rule.weekly_period_weeks > 0
        else "위클리 없음"
    )
    fine = f"데일리 {rule.daily_fine:,}원"
    if rule.weekly_fine > 0:
        fine += f" · 위클리 {rule.weekly_fine:,}원"
    return f"  · 과제: 데일리 {rule.daily_required}회 / {weekly}\n  · 벌금: {fine}"


# ===================== 과제 방향(위클리 topic) =====================

async def cmd_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg = update.effective_message
    if context.args:
        if not await is_admin(update, context):
            await msg.reply_text("⛔ 과제 방향 설정은 관리자만 가능합니다.")
            return
        topic = " ".join(context.args)
        database.set_setting(chat.id, WEEKLY_TOPIC_KEY, topic)
        await msg.reply_text(
            f"📌 *이번 주 위클리 과제 방향이 설정되었습니다.*\n\n{topic}",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    topic = database.get_setting(chat.id, WEEKLY_TOPIC_KEY, "")
    if topic:
        await msg.reply_text(
            f"📌 *이번 주 위클리 과제 방향*\n\n{topic}", parse_mode=ParseMode.MARKDOWN
        )
    else:
        await msg.reply_text(
            "아직 설정된 위클리 과제 방향이 없습니다.\n관리자가 `/topic <내용>` 으로 설정할 수 있습니다.",
            parse_mode=ParseMode.MARKDOWN,
        )


# ===================== 제출 (데일리 / 위클리) =====================

def _extract_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """명령 인자 또는 답장 대상 메시지에서 제출 내용을 추출한다."""
    if context.args:
        return " ".join(context.args).strip()
    reply = update.effective_message.reply_to_message
    if reply is not None:
        return (reply.text or reply.caption or "").strip()
    return ""


async def _prompt_submission(target_msg, user, context: ContextTypes.DEFAULT_TYPE,
                             kind: str) -> None:
    """제출 내용을 답장(ForceReply)으로 받도록 유도한다."""
    kind_label = "데일리" if kind == "daily" else "위클리"
    mention = f"[{display_name(user)}](tg://user?id={user.id})"
    prompt = await target_msg.reply_text(
        f"📝 {mention} 님, 이 메시지에 *답장(Reply)* 으로 {kind_label} 과제 내용을 "
        f"보내주세요.\n(권장 {config.RECOMMENDED_MIN_CHARS}자 이상)",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ForceReply(
            selective=True,
            input_field_placeholder=f"{kind_label} 과제 내용을 입력하세요",
        ),
    )
    pending = context.application.bot_data.setdefault(PENDING_SUB_KEY, {})
    pending[(target_msg.chat_id, prompt.message_id)] = {
        "user_id": user.id, "kind": kind,
    }


async def _process_submission(chat, user, reply_msg, context: ContextTypes.DEFAULT_TYPE,
                              kind: str, content: str) -> None:
    """제출 내용을 저장·아카이빙하고 결과를 응답한다."""
    kind_label = "데일리" if kind == "daily" else "위클리"

    # 미등록 사용자는 자동 등록(기본 레벨).
    if database.get_user(chat.id, user.id) is None:
        database.upsert_user(chat.id, user.id, display_name(user))

    d = today()

    # 데일리는 하루 1회만 제출 가능.
    if kind == "daily" and database.count_submissions_on_date(
        chat.id, user.id, "daily", d.isoformat()
    ) > 0:
        await reply_msg.reply_text(
            "⚠️ 오늘은 이미 데일리 과제를 제출했어요. 데일리는 하루 1회만 제출할 수 있습니다."
        )
        return

    year, week = weeks.iso_of(d)
    sub_id = database.add_submission(chat.id, user.id, kind, content, year, week)

    level = database.get_user(chat.id, user.id)["level"]

    # Notion 아카이빙 (실패해도 제출은 유효).
    notion_url = await notion_sync.archive_submission(
        chat.id, kind, display_name(user), content, d, level=level
    )
    if notion_url:
        database.set_submission_notion_url(sub_id, notion_url)

    rule = config.get_rule(level)
    char_count = len(content)

    if kind == "daily":
        done = database.count_submissions(chat.id, user.id, "daily", year, week)
        progress = f"이번 주 데일리 {done}/{rule.daily_required}회"
    else:
        done = database.count_submissions(chat.id, user.id, "weekly", year, week)
        progress = f"이번 주 위클리 {done}회 제출"

    reply = (
        f"✅ {kind_label} 과제 제출 완료! ({char_count}자)\n"
        f"📊 {progress}"
    )
    if notion_url:
        reply += f"\n🗂 Notion 아카이빙: {notion_url}"
    await reply_msg.reply_text(reply, disable_web_page_preview=True)


async def _handle_submission(update: Update, context: ContextTypes.DEFAULT_TYPE,
                             kind: str) -> None:
    content = _extract_content(update, context)
    if not content:
        # 내용 없이 명령만 온 경우: 답장으로 내용 받기.
        await _prompt_submission(
            update.effective_message, update.effective_user, context, kind
        )
        return
    await _process_submission(
        update.effective_chat, update.effective_user,
        update.effective_message, context, kind, content,
    )


async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_submission(update, context, "daily")


async def cmd_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_submission(update, context, "weekly")


# ===================== 답장 기반 제출 수신 =====================

async def on_reply_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """봇의 제출 유도(ForceReply) 메시지에 대한 답장을 처리한다."""
    msg = update.effective_message
    reply = msg.reply_to_message
    if reply is None:
        return
    pending = context.application.bot_data.get(PENDING_SUB_KEY, {})
    key = (msg.chat_id, reply.message_id)
    info = pending.get(key)
    if info is None:
        return  # 우리가 유도한 답장이 아님 → 무시
    if info["user_id"] != update.effective_user.id:
        return  # 다른 사람이 답장한 경우 무시
    pending.pop(key, None)

    content = (msg.text or msg.caption or "").strip()
    if not content:
        await msg.reply_text("내용이 비어 있어요. 다시 제출해 주세요.")
        return
    await _process_submission(
        update.effective_chat, update.effective_user, msg, context,
        info["kind"], content,
    )


# ===================== 그룹→슈퍼그룹 전환 처리 =====================

async def on_chat_migration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """그룹이 슈퍼그룹으로 전환되면 데이터를 새 chat_id 로 자동 이전한다."""
    msg = update.effective_message
    if msg is None:
        return
    if msg.migrate_to_chat_id is not None:
        old_id, new_id = update.effective_chat.id, msg.migrate_to_chat_id
    elif msg.migrate_from_chat_id is not None:
        old_id, new_id = msg.migrate_from_chat_id, update.effective_chat.id
    else:
        return

    database.migrate_chat(old_id, new_id)
    logger.info("그룹 마이그레이션: chat_id %s → %s", old_id, new_id)
    try:
        await context.bot.send_message(
            new_id,
            "ℹ️ 그룹이 슈퍼그룹으로 전환되어 스터디 데이터를 새 그룹으로 자동 이전했습니다.",
        )
    except Exception:  # noqa: BLE001
        pass


# ===================== 버튼(콜백) 처리 =====================

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """인라인 버튼 클릭 처리."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if data == "m:menu":
        await query.edit_message_text(
            MENU_TEXT, parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.main_menu(),
        )
        return

    if data == "m:help":
        await query.message.reply_text(HELP_TEXT)
        return

    if data == "m:status":
        await cmd_status(update, context)
        return
    if data == "m:rules":
        await cmd_rules(update, context)
        return
    if data == "m:mylevel":
        await cmd_mylevel(update, context)
        return
    if data == "m:members":
        await cmd_members(update, context)
        return
    if data == "m:topic":
        await cmd_topic(update, context)
        return

    if data == "m:register":
        await query.message.reply_text(
            "등록할 레벨을 선택하세요:", reply_markup=keyboards.level_menu()
        )
        return
    if data.startswith("reg:"):
        try:
            level = int(data.split(":", 1)[1])
        except ValueError:
            level = None
        text = _register_user(query.message.chat_id, update.effective_user, level)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
        return

    if data == "m:daily":
        await _prompt_submission(query.message, update.effective_user, context, "daily")
        return
    if data == "m:weekly":
        await _prompt_submission(query.message, update.effective_user, context, "weekly")
        return


# ===================== 진행 상황 / 벌금 =====================

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    row = database.get_user(chat.id, user.id)
    if row is None:
        await update.effective_message.reply_text(
            "아직 등록되지 않았습니다. `/register` 로 먼저 등록해 주세요.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    d = today()
    ordinal = weeks.week_ordinal(d)
    fine = fines.compute_user_fine(
        chat.id, user.id, row["display_name"], row["level"], ordinal
    )
    rule = config.get_rule(row["level"])

    lines = [f"📊 *{row['display_name']} — {rule.label}*",
             f"📅 {weeks.week_range_label(d)}", ""]
    daily_mark = "✅" if fine.daily_missed == 0 else "⚠️"
    lines.append(f"{daily_mark} 데일리: {fine.daily_done}/{fine.daily_required}회")
    if rule.weekly_period_weeks > 0:
        if fine.weekly_assessed:
            weekly_mark = "✅" if fine.weekly_missed == 0 else "⚠️"
            lines.append(
                f"{weekly_mark} 위클리: {fine.weekly_done}/{fine.weekly_required}회"
                f" (이번 주 정산)"
            )
        else:
            done = database.count_submissions(
                chat.id, user.id, "weekly", *weeks.iso_of(d)
            )
            lines.append(f"🔸 위클리: {done}회 (정산 주 아님)")
    else:
        lines.append("— 위클리 과제 없음")

    start_ordinal = fines.get_program_start_ordinal(chat.id)
    if ordinal < start_ordinal:
        start_monday = weeks.monday_of(d) + timedelta(weeks=start_ordinal - ordinal)
        lines.append("")
        lines.append(f"🗓 벌금 집계는 *{start_monday.isoformat()}* 주부터 시작돼요. "
                     "이번 주는 집계 대상이 아닙니다.")
    elif fine.has_fine:
        lines.append("")
        lines.append(f"💸 현재 기준 예상 벌금: *{fine.total_fine:,}원*")
        lines.append("아직 이번 주가 끝나지 않았으니 만회 가능합니다! 💪")
    else:
        lines.append("")
        lines.append("👍 현재 기준 벌금 없음. 좋아요!")

    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.MARKDOWN
    )


async def cmd_fine_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """이번 주(진행 중) 기준 벌금 미리보기."""
    chat = update.effective_chat
    report = fines.compute_weekly_report(chat.id, today())
    text = "🔎 *이번 주 진행 중 기준 미리보기*\n\n" + fines.format_report(report)
    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
    )


async def cmd_fine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """지난 주 벌금을 지금 집계하여 공지한다 (관리자)."""
    if not await is_admin(update, context):
        await update.effective_message.reply_text("⛔ 관리자만 사용할 수 있는 명령입니다.")
        return

    chat = update.effective_chat
    target = today() - timedelta(days=today().weekday() + 1)  # 지난 주 일요일
    report = fines.compute_weekly_report(chat.id, target)
    await update.effective_message.reply_text(
        fines.format_report(report),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """스터디 집계 기준을 이번 주로 리셋한다 (관리자). 제출 기록은 유지."""
    if not await is_admin(update, context):
        await update.effective_message.reply_text("⛔ 관리자만 사용할 수 있는 명령입니다.")
        return

    chat = update.effective_chat
    d = today()
    fines.set_program_start(chat.id, d)
    monday = weeks.monday_of(d)
    await update.effective_message.reply_text(
        f"🔄 *스터디 집계를 이번 주부터 다시 시작합니다.*\n\n"
        f"• 기준 주: *{monday.isoformat()}* 주 (이번 주)\n"
        f"• 이 주부터 데일리/위클리 벌금이 집계됩니다.\n"
        f"• 위클리 2주 주기도 이 주를 1주차로 다시 계산합니다.\n"
        f"• 기존 제출 기록은 그대로 유지됩니다.",
        parse_mode=ParseMode.MARKDOWN,
    )
