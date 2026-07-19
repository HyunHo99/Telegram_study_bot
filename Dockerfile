# 스터디 봇 컨테이너 이미지 (amd64/arm64 모두 지원).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 의존성 먼저 설치 (레이어 캐시 활용)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# 앱 코드 복사
COPY . .

# SQLite 데이터 디렉터리 (볼륨으로 마운트 권장: -v $(pwd)/data:/app/data)
RUN mkdir -p /app/data
VOLUME ["/app/data"]

CMD ["python", "run.py"]
