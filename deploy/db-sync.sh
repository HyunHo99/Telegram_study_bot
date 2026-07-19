#!/usr/bin/env bash
#
# SQLite DB 를 별도 GitHub(private) 저장소로 백업(push)한다.
# WAL 모드에서도 일관된 스냅샷을 뜨기 위해 VACUUM INTO 를 사용한다.
# systemd 타이머(study-bot-dbsync.timer)가 하루 1회 호출한다.
#
# 경로는 환경변수로 덮어쓸 수 있다:
#   APP_DIR     : 봇 코드 경로 (기본 $HOME/Telegram_study_bot)
#   BACKUP_DIR  : 백업 저장소 clone 경로 (기본 $HOME/study-bot-data)
#   DB_PATH     : DB 파일 경로 (기본 $APP_DIR/data/study_bot.db)
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/Telegram_study_bot}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/study-bot-data}"
DB="${DB_PATH:-$APP_DIR/data/study_bot.db}"
DEST="$BACKUP_DIR/study_bot.db"

if [ ! -f "$DB" ]; then
    echo "DB 파일이 없습니다: $DB (아직 제출 기록이 없을 수 있음) — 종료"
    exit 0
fi
if [ ! -d "$BACKUP_DIR/.git" ]; then
    echo "백업 저장소가 없습니다: $BACKUP_DIR — 먼저 git clone 하세요." >&2
    exit 1
fi

# VACUUM INTO 는 대상 파일이 이미 있으면 실패하므로 먼저 제거.
rm -f "$DEST"

# WAL 안전한 일관 스냅샷 생성 (별도 파이썬 불필요 — 표준 sqlite3 모듈).
python3 - "$DB" "$DEST" <<'PY'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
con = sqlite3.connect(src)
try:
    con.execute("VACUUM INTO ?", (dst,))
finally:
    con.close()
PY

cd "$BACKUP_DIR"
git add study_bot.db
if git diff --cached --quiet; then
    echo "변경 없음 — 커밋 생략"
    exit 0
fi
git -c user.name="study-bot" -c user.email="bot@localhost" \
    commit -q -m "DB 백업 $(date +%F_%T)"
git push -q origin HEAD
echo "백업 완료: $(date +%F_%T)"
