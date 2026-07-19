"""주간 벌금 집계 로직.

각 사용자의 레벨 규정에 따라 지난 주 데일리/위클리 미달 횟수를 세고
벌금을 계산한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from . import config, database, weeks

# 그룹(chat)별 "스터디 시작 주"(week ordinal) 저장 키.
_START_SETTING_KEY = "program_start_ordinal"


def get_program_start_ordinal(chat_id: int) -> int:
    """해당 그룹의 스터디 시작 주 순번. 미설정 시 config 기본값."""
    raw = database.get_setting(chat_id, _START_SETTING_KEY, "")
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    return weeks.week_ordinal(config.PROGRAM_START_DATE)


def set_program_start(chat_id: int, d) -> None:
    """d 가 속한 주를 그룹의 스터디 시작 주로 저장한다."""
    database.set_setting(chat_id, _START_SETTING_KEY, str(weeks.week_ordinal(d)))


@dataclass
class UserFine:
    user_id: int
    display_name: str
    level: int
    daily_done: int
    daily_required: int
    daily_missed: int
    weekly_done: int
    weekly_required: int
    weekly_missed: int
    weekly_assessed: bool  # 이번 주가 위클리 정산 주였는지
    daily_fine: int
    weekly_fine: int

    @property
    def total_fine(self) -> int:
        return self.daily_fine + self.weekly_fine

    @property
    def has_fine(self) -> bool:
        return self.total_fine > 0


@dataclass
class WeeklyReport:
    chat_id: int
    target_date: date
    week_label: str
    fines: list[UserFine] = field(default_factory=list)

    @property
    def payers(self) -> list[UserFine]:
        return [f for f in self.fines if f.has_fine]

    @property
    def total(self) -> int:
        return sum(f.total_fine for f in self.fines)


def compute_user_fine(chat_id: int, user_id: int, display_name: str, level: int,
                      target_ordinal: int) -> UserFine:
    rule = config.get_rule(level)
    target_year, target_week = weeks.ordinal_to_iso(target_ordinal)
    anchor_ordinal = get_program_start_ordinal(chat_id)

    # 스터디 시작 주 이전은 집계하지 않는다 (전부 0원).
    if target_ordinal < anchor_ordinal:
        return UserFine(
            user_id=user_id, display_name=display_name, level=level,
            daily_done=0, daily_required=rule.daily_required, daily_missed=0,
            weekly_done=0, weekly_required=rule.weekly_required, weekly_missed=0,
            weekly_assessed=False, daily_fine=0, weekly_fine=0,
        )

    # 데일리: 대상 주 한 주 기준.
    daily_done = database.count_submissions(
        chat_id, user_id, "daily", target_year, target_week
    )
    daily_missed = max(0, rule.daily_required - daily_done)
    daily_fine = daily_missed * rule.daily_fine

    # 위클리: 주기(period) 단위. 정산 주에만 평가.
    weekly_done = 0
    weekly_required = rule.weekly_required
    weekly_missed = 0
    weekly_fine = 0
    weekly_assessed = False

    if rule.weekly_period_weeks > 0 and weeks.is_period_due(
        target_ordinal, rule.weekly_period_weeks, anchor_ordinal
    ):
        weekly_assessed = True
        period = weeks.period_weeks(
            target_ordinal, rule.weekly_period_weeks, anchor_ordinal
        )
        weekly_done = database.count_submissions_in_weeks(
            chat_id, user_id, "weekly", period
        )
        weekly_missed = max(0, rule.weekly_required - weekly_done)
        weekly_fine = weekly_missed * rule.weekly_fine

    return UserFine(
        user_id=user_id,
        display_name=display_name,
        level=level,
        daily_done=daily_done,
        daily_required=rule.daily_required,
        daily_missed=daily_missed,
        weekly_done=weekly_done,
        weekly_required=weekly_required,
        weekly_missed=weekly_missed,
        weekly_assessed=weekly_assessed,
        daily_fine=daily_fine,
        weekly_fine=weekly_fine,
    )


def compute_weekly_report(chat_id: int, target_date: date) -> WeeklyReport:
    target_ordinal = weeks.week_ordinal(target_date)
    report = WeeklyReport(
        chat_id=chat_id,
        target_date=target_date,
        week_label=weeks.week_range_label(target_date),
    )
    for user in database.list_users(chat_id):
        report.fines.append(
            compute_user_fine(
                chat_id,
                user["user_id"],
                user["display_name"],
                user["level"],
                target_ordinal,
            )
        )
    return report


def format_report(report: WeeklyReport) -> str:
    """단톡방 공지용 텍스트."""
    lines: list[str] = []
    lines.append("📢 *주간 벌금 집계*")
    lines.append(f"📅 대상 주간: {report.week_label}")
    lines.append("")

    payers = report.payers
    if not payers:
        lines.append("🎉 이번 주 벌금 대상자가 없습니다. 모두 과제 완수! 👏")
        return "\n".join(lines)

    for f in sorted(payers, key=lambda x: (-x.total_fine, x.display_name)):
        rule = config.get_rule(f.level)
        parts = []
        if f.daily_missed > 0:
            parts.append(
                f"데일리 {f.daily_done}/{f.daily_required} → 미달 {f.daily_missed}회"
                f" × {rule.daily_fine:,}원 = {f.daily_fine:,}원"
            )
        if f.weekly_assessed and f.weekly_missed > 0:
            parts.append(
                f"위클리 {f.weekly_done}/{f.weekly_required} → 미달 {f.weekly_missed}회"
                f" × {rule.weekly_fine:,}원 = {f.weekly_fine:,}원"
            )
        detail = "\n     ".join(parts)
        lines.append(f"• *{f.display_name}* ({rule.label}) — 합계 *{f.total_fine:,}원*")
        lines.append(f"     {detail}")

    lines.append("")
    lines.append(f"💰 이번 주 총 벌금: *{report.total:,}원*")
    lines.append("입금 확인 부탁드립니다 🙏")
    return "\n".join(lines)
