FROM python:3.12-slim

# Chromium + chromedriver from Debian repos (works for amd64 and arm64)
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium chromium-driver \
        ca-certificates fonts-liberation && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data

EXPOSE 5000

CMD ["python", "app.py"]
