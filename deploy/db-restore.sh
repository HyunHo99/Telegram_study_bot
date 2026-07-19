#!/usr/bin/env bash
#
# GitHub 백업 저장소에서 DB 를 복원한다.
# 안전을 위해 "로컬 DB 가 없을 때만" 복원한다 (VM 을 새로 만든 경우 복구용).
# 로컬 DB 가 있으면 그것이 최신이므로 절대 덮어쓰지 않는다.
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/Telegram_study_bot}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/study-bot-data}"
DB="${DB_PATH:-$APP_DIR/data/study_bot.db}"
SRC="$BACKUP_DIR/study_bot.db"

if [ ! -d "$BACKUP_DIR/.git" ]; then
    echo "백업 저장소가 없습니다: $BACKUP_DIR — 먼저 git clone 하세요." >&2
    exit 1
fi

# 최신 백업 받기 (충돌 없이 fast-forward 만).
cd "$BACKUP_DIR" && git pull -q --ff-only || true

if [ -f "$DB" ]; then
    echo "로컬 DB 가 이미 존재 → 복원 생략 (로컬이 최신)."
    exit 0
fi
if [ ! -f "$SRC" ]; then
    echo "백업본이 없습니다 → 복원할 것 없음 (신규 시작)."
    exit 0
fi

mkdir -p "$(dirname "$DB")"
cp "$SRC" "$DB"
echo "GitHub 백업에서 DB 복원 완료: $DB"
