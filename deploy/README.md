# 🚀 Oracle Cloud 무료 VM 배포 가이드

Oracle Cloud "Always Free" VM에 스터디 봇을 **24시간 무료로** 올리는 방법입니다.
봇은 텔레그램으로 **아웃바운드 연결(long polling)** 만 사용하므로,
방화벽/포트를 열 필요가 없어 설정이 간단하고 안전합니다.

> 소요 시간: 처음이면 약 20~30분. 한 번 올려두면 계속 켜져 있습니다.

---

## 1단계. Oracle Cloud 무료 계정 & VM 생성

1. https://www.oracle.com/kr/cloud/free/ 에서 가입 (카드 인증 필요하지만 Always Free 리소스는 **과금되지 않음**).
2. 콘솔에서 **Compute → Instances → Create Instance**.
3. 아래 설정으로 생성:
   - **Image**: `Canonical Ubuntu` (22.04 이상 권장)
   - **Shape**: `VM.Standard.A1.Flex` (Ampere ARM, Always Free) — OCPU 1, 메모리 6GB면 충분
     - A1 재고가 없다는 오류가 나면 `VM.Standard.E2.1.Micro` (x86 Always Free)로 대체 가능
   - **SSH keys**: "Generate a key pair for me" 를 선택하고 **개인키(.key)를 꼭 다운로드**
4. 생성 후 인스턴스의 **Public IP** 를 메모.

> ⚠️ 인바운드 포트는 열지 않아도 됩니다. 봇은 텔레그램 서버로 나가는 연결만 사용합니다.

---

## 2단계. VM 접속

로컬 터미널(맥/리눅스) 또는 Windows PowerShell에서:

```bash
# 다운로드한 개인키 권한 설정 (맥/리눅스)
chmod 600 ~/Downloads/ssh-key.key

# 접속 (Ubuntu 이미지는 사용자명이 ubuntu)
ssh -i ~/Downloads/ssh-key.key ubuntu@<PUBLIC_IP>
```

Oracle Linux 이미지를 골랐다면 사용자명은 `opc` 입니다.

---

## 3단계. 봇 설치

VM 안에서 순서대로 실행합니다.

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

## 4단계. 환경변수(.env) 설정

```bash
cp .env.example .env
nano .env      # 값 입력 후 Ctrl+O, Enter, Ctrl+X 로 저장
```

최소한 `TELEGRAM_BOT_TOKEN` 은 반드시 입력해야 합니다.
Notion 아카이빙을 쓰려면 `NOTION_TOKEN` 입력 + 상위 페이지에 인테그레이션 연결(메인 README 참고).

한 번 직접 실행해서 정상 동작하는지 확인:

```bash
.venv/bin/python run.py
# "스터디 봇 시작 ..." 로그가 뜨면 성공. Ctrl+C 로 중지.
```

---

## 5단계. systemd 서비스로 항상 켜두기

크래시나 VM 재부팅 후에도 자동으로 다시 켜지도록 등록합니다.

```bash
# 서비스 파일 복사
sudo cp ~/Telegram_study_bot/deploy/study-bot.service /etc/systemd/system/study-bot.service

# (Oracle Linux 이미지라면) User/경로의 ubuntu 를 opc 로 수정
# sudo nano /etc/systemd/system/study-bot.service

# 등록 및 시작
sudo systemctl daemon-reload
sudo systemctl enable study-bot      # 부팅 시 자동 시작
sudo systemctl start study-bot       # 지금 시작
```

상태/로그 확인:

```bash
sudo systemctl status study-bot          # 실행 상태
journalctl -u study-bot -f               # 실시간 로그 (Ctrl+C 로 나가기)
```

이제 봇이 항상 켜져 있습니다. 텔레그램 단톡방에 봇을 초대하고 `/help` 를 입력해 보세요.

---

## 6단계. ⚠️ 무료 VM 회수(idle reclamation) 방지 — 중요

Oracle "Always Free" 인스턴스는 **놀고 있으면 회수될 수 있습니다.** 최근 **7일간**
아래 지표가 **모두** 낮으면(95 백분위 기준) idle 로 판정합니다:

- CPU 사용률 < 20%
- 네트워크 사용률 < 20%
- 메모리 사용률 < 20% (A1 Flex 셰이프만 해당)

우리 봇은 long-polling 만 하므로 세 지표가 거의 0 → **그냥 두면 회수 위험**이 있습니다.
아래 둘 중 하나(가능하면 둘 다)를 적용하세요.

### 방법 A. Pay As You Go 로 업그레이드 (가장 확실, 권장)

**PAYG(종량제) 계정의 인스턴스는 idle 회수 대상에서 제외됩니다.**
결제수단만 등록할 뿐, **Always Free 한도 안에서 쓰면 요금은 계속 $0** 입니다.

1. OCI 콘솔 우측 상단 프로필 → **Upgrade to Paid** (또는 Billing → Upgrade).
2. 결제수단 등록. 리소스는 그대로 Always Free 로 유지됨.
3. **예상치 못한 과금 방지**를 위해 예산 알림을 걸어 두세요:
   **Billing → Budgets → Create Budget** 에서 월 예산(예: 1)과 알림 임계값(예: 80%) 설정.
4. Always Free 대상 셰이프(A1 1~4 OCPU/24GB 이내, E2.1.Micro 등)를 벗어나지 않으면
   과금되지 않습니다.

> 💡 "무료인데 카드 등록?" 이 꺼려질 수 있지만, 회수 없이 안정적으로 24시간 돌리는
> 가장 확실한 방법입니다. 예산 알림까지 걸면 실수로 과금될 일도 사실상 없습니다.

### 방법 B. keepalive 타이머 (Free Tier 유지 시)

계정을 Free Tier 로 두겠다면, 주기적으로 CPU 를 살짝 태워 idle 판정을 피합니다.
저장소에 포함된 타이머를 등록하세요 (별도 패키지 불필요):

```bash
cd ~/Telegram_study_bot
chmod +x deploy/keepalive.sh

sudo cp deploy/study-bot-keepalive.service /etc/systemd/system/
sudo cp deploy/study-bot-keepalive.timer   /etc/systemd/system/
# (Oracle Linux 이미지면 두 파일의 User=ubuntu / 경로를 opc 로 수정)

sudo systemctl daemon-reload
sudo systemctl enable --now study-bot-keepalive.timer
```

동작 확인:

```bash
systemctl list-timers study-bot-keepalive.timer   # 다음 실행 시각 확인
sudo systemctl start study-bot-keepalive.service   # 지금 1회 강제 실행 테스트
journalctl -u study-bot-keepalive -n 20            # 로그 확인
```

기본값은 **15분마다 120초 부하**(약 13% 듀티)로, CPU 95 백분위를 20% 이상으로
유지합니다. 세기를 바꾸려면 `study-bot-keepalive.service` 의 `KEEPALIVE_SECONDS` /
`KEEPALIVE_WORKERS` 값을 수정하고 `sudo systemctl daemon-reload` 하세요.

> ⚠️ keepalive 는 CPU 통계상 idle 을 면하게 해줄 뿐이며, Oracle 정책 변경 시
> 100% 보장되지는 않습니다. 확실히 하려면 **방법 A(PAYG)** 를 권장합니다.

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
| 봇이 응답 없음 | 토큰이 맞는지, 그룹에서 봇의 개인정보 모드(Privacy)를 BotFather에서 끄기 (`/setprivacy` → Disable) |
| A1 인스턴스 생성 실패 | 리전 재고 문제. 잠시 후 재시도하거나 E2.1.Micro 사용 |
| DB가 사라짐 | VM 로컬 디스크는 재부팅에도 유지됩니다. VM 자체를 재생성하지 않는 한 안전 |

> 💡 그룹에서 명령이 안 먹히면 BotFather에서 `/setprivacy` → 봇 선택 → **Disable** 로 설정해야
> 봇이 그룹 메시지를 볼 수 있습니다.

---

## (선택) Docker로 실행하고 싶다면

VM에 Docker가 설치돼 있다면 systemd 대신 컨테이너로도 실행할 수 있습니다.
저장소 루트의 `Dockerfile` 을 사용하세요.

```bash
sudo apt install -y docker.io
sudo docker build -t study-bot .
sudo docker run -d --name study-bot --restart always \
  --env-file .env -v $(pwd)/data:/app/data study-bot
```
