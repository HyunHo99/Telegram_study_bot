# 🚀 Google Cloud 무료 VM 배포 가이드

Google Cloud "Always Free" e2-micro VM에 스터디 봇을 **24시간 무료로** 올리는 방법입니다.
봇은 텔레그램으로 **아웃바운드 연결(long polling)** 만 사용하므로 방화벽/포트를 열 필요가
없고, **Oracle 과 달리 idle 회수(reclamation)가 없어** keepalive 같은 꼼수도 불필요합니다.

> 소요 시간: 처음이면 약 15~25분. 한 번 올려두면 계속 켜져 있습니다.

---

## ⚠️ 무료(Always Free) 조건 — 반드시 지킬 것

아래를 벗어나면 과금될 수 있습니다. 이 조건만 지키면 요금은 $0 입니다.

- **머신 타입**: `e2-micro` (반드시 이것)
- **리전**: `us-west1`(오리건) / `us-central1`(아이오와) / `us-east1`(사우스캐롤라이나) **중 하나**
  - ⚠️ 서울(asia-northeast3) 등 다른 리전은 무료 대상이 아닙니다.
- **부팅 디스크**: **표준 영구 디스크(Standard persistent disk) 30GB 이하**
  - ⚠️ 기본값인 "균형 있는(Balanced/SSD)" 디스크는 무료가 아닙니다. **Standard 로 변경**하세요.
- 아웃바운드 트래픽: 북미발 월 1GB 무료 (봇 polling 은 트래픽 극소량이라 문제없음)

---

## 1단계. 프로젝트 & 결제 설정

1. https://console.cloud.google.com 접속 (구글 계정으로 로그인).
2. 상단에서 **프로젝트 생성** (예: `study-bot`).
3. **결제 계정 연결**: 좌측 메뉴 **결제(Billing)** → 카드 등록.
   - 무료 한도 내에서는 청구되지 않습니다. 처음이면 $300 크레딧도 함께 제공됩니다.
4. (권장) **과금 방지 알림**: 결제 → **예산 및 알림(Budgets & alerts)** → 예산 생성
   → 금액을 낮게(예: ₩1,000) 두고 임계값 알림 설정.

---

## 2단계. VM 인스턴스 생성

1. 좌측 메뉴 **Compute Engine → VM 인스턴스**. (처음이면 Compute Engine API 활성화 클릭)
2. **인스턴스 만들기** 클릭 후 아래대로 설정:
   - **이름**: `study-bot`
   - **리전**: `us-central1 (아이오와)` — (또는 us-west1 / us-east1)
   - **머신 구성**: 시리즈 `E2` → 머신 타입 **`e2-micro`**
   - **부팅 디스크** → **변경** 클릭:
     - 운영체제: **Ubuntu**, 버전: **Ubuntu 22.04 LTS (x86/amd64)**
     - 디스크 종류: **표준 영구 디스크(Standard persistent disk)**
     - 크기: **30 GB**
   - **방화벽**: HTTP/HTTPS 트래픽 허용 **체크 안 함** (아웃바운드만 쓰므로 불필요)
3. **만들기** 클릭. 잠시 후 목록에 인스턴스가 뜹니다.

> 💡 별도 SSH 키를 만들 필요가 없습니다. 다음 단계에서 브라우저로 바로 접속합니다.

---

## 3단계. VM 접속 (브라우저 SSH)

VM 인스턴스 목록에서 우리 인스턴스 행의 **`SSH`** 버튼 클릭 → 브라우저에 터미널 창이 열립니다.
(로컬 터미널이나 키 관리가 전혀 필요 없습니다.)

---

## 4단계. 봇 설치

열린 SSH 터미널에서 순서대로 실행합니다.

```bash
# 필수 패키지
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git

# 코드 받기
cd ~
git clone https://github.com/HyunHo99/Telegram_study_bot.git
cd Telegram_study_bot
git checkout claude/telegram-study-bot-omo3d4   # 배포 브랜치 (병합 후에는 main/기본 브랜치)

# 가상환경 + 의존성
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

---

## 5단계. 환경변수(.env) 설정

```bash
cp .env.example .env
nano .env      # 값 입력 후 Ctrl+O, Enter, Ctrl+X 로 저장
```

최소한 `TELEGRAM_BOT_TOKEN` 은 반드시 입력해야 합니다.
Notion 아카이빙을 쓰려면 `NOTION_TOKEN` 입력 + 상위 페이지에 인테그레이션 연결(메인 README 참고).

한 번 직접 실행해서 정상 동작하는지 확인:

```bash
.venv/bin/python run.py
# "스터디 봇 시작 ..." / "Application started" 로그가 뜨면 성공. Ctrl+C 로 중지.
```

---

## 6단계. systemd 서비스로 항상 켜두기

크래시나 VM 재부팅 후에도 자동으로 다시 켜지도록 등록합니다.
아래 명령은 **현재 사용자/경로를 자동으로 채워** 서비스 파일을 만들기 때문에,
GCP 의 사용자명(구글 계정 기반)이 무엇이든 그대로 동작합니다.

```bash
sudo tee /etc/systemd/system/study-bot.service > /dev/null <<EOF
[Unit]
Description=Telegram Study Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/Telegram_study_bot
ExecStart=$HOME/Telegram_study_bot/.venv/bin/python run.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 등록 및 시작
sudo systemctl daemon-reload
sudo systemctl enable study-bot      # 부팅 시 자동 시작
sudo systemctl start study-bot       # 지금 시작
```

상태/로그 확인:

```bash
sudo systemctl status study-bot          # 실행 상태 (active (running) 확인)
journalctl -u study-bot -f               # 실시간 로그 (Ctrl+C 로 나가기)
```

이제 봇이 항상 켜져 있습니다. 텔레그램 단톡방에 봇을 초대하고 `/menu` 를 입력해 보세요.

> ✅ Google Cloud 는 Oracle 과 달리 idle 인스턴스를 회수하지 않으므로,
> 별도의 keepalive 설정은 필요 없습니다.

---

## 코드 업데이트 방법

봇 코드를 수정/업데이트한 뒤:

```bash
cd ~/Telegram_study_bot
git pull
.venv/bin/pip install -r requirements.txt   # 의존성 변경 시에만
sudo systemctl restart study-bot
```

---

## 자주 겪는 문제

| 증상 | 해결 |
|---|---|
| `systemctl status` 가 `failed` | `journalctl -u study-bot -n 50` 로 로그 확인. 대개 `.env` 토큰 누락 |
| 봇이 그룹에서 응답 없음 | BotFather → `/setprivacy` → 봇 선택 → **Disable** (그룹 메시지 수신 허용) |
| `Conflict: terminated by other getUpdates` | 같은 토큰으로 봇이 두 군데서 실행 중. 로컬 등 다른 인스턴스를 끄세요 |
| 요금이 청구될까 걱정 | 머신 `e2-micro` + 무료 리전 + 표준 디스크 30GB 조건이면 $0. 예산 알림으로 이중 확인 |
| DB가 사라짐 | VM 로컬 디스크는 재부팅에도 유지됩니다. VM 자체를 삭제하지 않는 한 안전 |

---

## (선택) Docker로 실행하고 싶다면

VM에 Docker가 설치돼 있다면 systemd 대신 컨테이너로도 실행할 수 있습니다.

```bash
sudo apt install -y docker.io
cd ~/Telegram_study_bot
sudo docker build -t study-bot .
sudo docker run -d --name study-bot --restart always \
  --env-file .env -v $(pwd)/data:/app/data study-bot
```
