# 1. 파이썬 베이스 이미지 선택
FROM python:3.11-slim

# 2. 필수 패키지 및 Chromium 설치
# 라즈베리파이 환경에 맞는 chromium과 chromedriver를 설치합니다.
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    libnss3 \
    libgconf-2-4 \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# 3. 작업 디렉토리 설정
WORKDIR /app

# 4. 의존성 파일 복사 및 설치 (uv 사용 시)
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv export --format requirements-txt > requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 코드 복사
COPY . .

# 6. 환경 변수 설정 (Selenium이 Chromium을 찾을 수 있도록)
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# 7. FastAPI 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]