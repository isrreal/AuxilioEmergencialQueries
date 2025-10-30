FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN addgroup --system appuser && \
    adduser --system --no-create-home --group appuser && \
    chown -R appuser:appuser /app

EXPOSE 8000