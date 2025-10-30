FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && \
    apt-get install -y locales && \
    sed -i '/pt_BR.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen pt_BR.UTF-8

ENV LANG=pt_BR.UTF-8
ENV LANGUAGE=pt_BR:pt
ENV LC_ALL=pt_BR.UTF-8

COPY . .

RUN addgroup --system appuser && \
    adduser --system --no-create-home --group appuser && \
    chown -R appuser:appuser /app

EXPOSE 8000