#!/usr/bin/env bash
#
# Oracle Cloud "Always Free" VM 회수(idle reclamation) 방지용 CPU keepalive.
#
# Oracle 은 최근 7일간 CPU/네트워크/메모리(95 백분위)가 모두 낮으면 인스턴스를
# idle 로 보고 회수할 수 있다. long-polling 봇은 거의 idle 이므로, 이 스크립트가
# 주기적으로 짧게 CPU 부하를 주어 CPU 95 백분위 사용률을 20% 이상으로 유지한다.
#
# systemd 타이머(study-bot-keepalive.timer)가 이 스크립트를 주기 실행한다.
# 환경변수로 세기를 조절할 수 있다:
#   KEEPALIVE_SECONDS : 1회 부하 지속 시간(초, 기본 120)
#   KEEPALIVE_WORKERS : 동시 부하 프로세스 수(기본 1)
set -euo pipefail

DURATION="${KEEPALIVE_SECONDS:-120}"
WORKERS="${KEEPALIVE_WORKERS:-1}"

end=$(( $(date +%s) + DURATION ))
pids=()
for _ in $(seq "$WORKERS"); do
    # CPU 한 코어를 바쁘게 돌리는 순수 busy-loop (외부 패키지 불필요).
    ( while [ "$(date +%s)" -lt "$end" ]; do : ; done ) &
    pids+=($!)
done
wait "${pids[@]}"
