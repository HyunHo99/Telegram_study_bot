"""ISO 주차 계산 유틸리티.

위클리 과제 주기(1주/2주)를 다루기 위해 '주 순번(week ordinal)'을 사용한다.
기준 월요일(1970-01-05)로부터 몇 번째 주인지를 정수로 표현하여
연도 경계와 무관하게 주기 계산을 단순화한다.
"""

from __future__ import annotations

from datetime import date, timedelta

# 1970-01-05 는 월요일.
_EPOCH_MONDAY = date(1970, 1, 5)


def monday_of(d: date) -> date:
    """해당 날짜가 속한 주(월~일)의 월요일."""
    return d - timedelta(days=d.weekday())


def week_ordinal(d: date) -> int:
    """기준 월요일로부터의 주 순번."""
    return (monday_of(d) - _EPOCH_MONDAY).days // 7


def ordinal_to_iso(ordinal: int) -> tuple[int, int]:
    """주 순번 -> (ISO year, ISO week)."""
    monday = _EPOCH_MONDAY + timedelta(weeks=ordinal)
    iso = monday.isocalendar()
    return iso.year, iso.week


def iso_of(d: date) -> tuple[int, int]:
    """날짜 -> (ISO year, ISO week)."""
    iso = d.isocalendar()
    return iso.year, iso.week


def week_label(d: date) -> str:
    """'2026-W30' 형식 라벨."""
    year, week = iso_of(d)
    return f"{year}-W{week:02d}"


def week_range_label(d: date) -> str:
    """'2026-07-13 ~ 2026-07-19 (2026-W29)' 형식 라벨."""
    monday = monday_of(d)
    sunday = monday + timedelta(days=6)
    year, week = iso_of(d)
    return f"{monday.isoformat()} ~ {sunday.isoformat()} ({year}-W{week:02d})"


def period_weeks(target_ordinal: int, period: int) -> list[tuple[int, int]]:
    """target 주가 속한 주기(period주)에 포함된 모든 (iso_year, iso_week).

    period<=1 이면 target 주 하나만 반환한다.
    """
    if period <= 1:
        return [ordinal_to_iso(target_ordinal)]
    start = (target_ordinal // period) * period
    return [ordinal_to_iso(start + i) for i in range(period)]


def is_period_due(target_ordinal: int, period: int) -> bool:
    """target 주가 해당 주기의 마지막 주(정산 주)인지 여부.

    period<=1 이면 항상 정산 대상.
    """
    if period <= 1:
        return True
    return target_ordinal % period == period - 1
