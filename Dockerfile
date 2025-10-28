FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN addgroup --system appuser && \
    adduser --system --no-create-home --group appuser && \
    chown -R appuser:appuser /app

EXPOSE 8000