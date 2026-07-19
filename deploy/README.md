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
