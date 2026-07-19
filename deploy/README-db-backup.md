# 💾 DB 를 GitHub 에 매일 백업하기

SQLite DB(`data/study_bot.db`)를 **별도 private GitHub 저장소**에 하루 1회 백업(push)하고,
VM 을 새로 만들었을 때 복원(pull)하는 방법입니다.

## 설계 요약 (중요)

- **push(백업)** → 하루 1회. WAL 안전한 일관 스냅샷을 떠서 커밋·푸시.
- **pull(복원)** → **로컬 DB 가 없을 때만.** VM 이 하나면 로컬 DB 가 항상 최신이므로,
  매일 pull 로 덮어쓰면 그날 제출이 사라집니다. 그래서 복원은 "신규 VM 복구용"으로만 동작합니다.

## ⚠️ 저장소는 반드시 Private

DB 에는 제출 내용(리포트 본문)과 멤버 이름이 들어있습니다.
**공개(public) 저장소에 넣지 마세요.** 아래는 전용 **private** 저장소를 만드는 전제입니다.

---

## 1단계. 백업용 private 저장소 생성

GitHub 에서 새 저장소를 만듭니다 (예: `study-bot-data`) — **반드시 Private**.
비워둔 채로 생성하면 됩니다(README 없이도 OK).

---

## 2단계. VM 에서 쓰기용 배포 키(deploy key) 만들기

VM 은 headless 라 비밀번호 입력이 안 되므로 SSH 배포 키를 사용합니다.
아래는 **VM 안에서** 실행합니다.

```bash
# 백업 저장소 전용 SSH 키 생성 (암호 없이)
ssh-keygen -t ed25519 -C "study-bot-backup" -f ~/.ssh/backup_key -N ""

# 공개키 출력 → 복사
cat ~/.ssh/backup_key.pub
```

출력된 공개키를 GitHub 에 등록:
**백업 저장소 → Settings → Deploy keys → Add deploy key**
→ 키 붙여넣기 → **"Allow write access" 체크** → 저장.

다른 GitHub 인증과 충돌하지 않도록 SSH 별칭을 만듭니다:

```bash
cat >> ~/.ssh/config <<'EOF'

Host github-backup
  HostName github.com
  User git
  IdentityFile ~/.ssh/backup_key
  IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config
```

---

## 3단계. 백업 저장소 clone

`YOUR_GH` 를 본인 GitHub 사용자명으로 바꾸세요.

```bash
git clone git@github-backup:YOUR_GH/study-bot-data.git ~/study-bot-data
```

---

## 4단계. 수동으로 한 번 백업 테스트

```bash
cd ~/Telegram_study_bot
chmod +x deploy/db-sync.sh deploy/db-restore.sh
./deploy/db-sync.sh
```

`백업 완료: ...` 가 뜨고, GitHub 백업 저장소에 `study_bot.db` 가 올라가면 성공입니다.
(아직 제출 기록이 없어 DB 파일이 없으면 "DB 파일이 없습니다" 가 정상입니다.)

---

## 5단계. 매일 자동 백업 (systemd 타이머)

아래 명령은 현재 사용자/경로를 자동으로 채웁니다.

```bash
sudo tee /etc/systemd/system/study-bot-dbsync.service >/dev/null <<EOF
[Unit]
Description=Study Bot DB backup to GitHub
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$USER
Environment=HOME=$HOME
WorkingDirectory=$HOME/Telegram_study_bot
ExecStart=$HOME/Telegram_study_bot/deploy/db-sync.sh
EOF

sudo tee /etc/systemd/system/study-bot-dbsync.timer >/dev/null <<EOF
[Unit]
Description=Daily Study Bot DB backup

[Timer]
# 매일 03:00 KST (=18:00 UTC). 놓친 실행은 부팅 후 보충.
OnCalendar=*-*-* 18:00:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now study-bot-dbsync.timer
```

확인:

```bash
systemctl list-timers study-bot-dbsync.timer     # 다음 실행 시각
sudo systemctl start study-bot-dbsync.service     # 지금 1회 강제 실행
journalctl -u study-bot-dbsync -n 20              # 로그
```

---

## VM 을 새로 만들었을 때 복원

새 VM 에서 봇 코드를 clone 하고 위 2~3단계(배포 키 + 백업 저장소 clone)를 다시 한 뒤:

```bash
cd ~/Telegram_study_bot
./deploy/db-restore.sh      # 로컬 DB 가 없으면 백업본을 복원
```

그 다음 봇을 시작하면 이전 제출 기록이 그대로 이어집니다.
(로컬 DB 가 이미 있으면 복원은 자동으로 건너뜁니다 — 데이터 유실 방지.)

> 💡 봇 서비스가 뜨기 전에 자동 복원되게 하려면, `study-bot.service` 의 `[Service]` 에
> `ExecStartPre=$HOME/Telegram_study_bot/deploy/db-restore.sh` 한 줄을 추가해도 됩니다.

---

## 요약

| 스크립트 | 역할 | 실행 |
|---|---|---|
| `deploy/db-sync.sh` | 일관 스냅샷 → 커밋 → push | systemd 타이머(매일) |
| `deploy/db-restore.sh` | 로컬 DB 없을 때만 백업본 복원 | 신규 VM 셋업 시 1회 |
