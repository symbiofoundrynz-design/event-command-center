FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/ecc
COPY requirements.txt ./
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt \
    && groupadd -r -g 10001 ecc \
    && useradd -r -u 10001 -g ecc -d /opt/ecc ecc \
    && mkdir -p /data/photos /opt/ecc \
    && chown -R ecc:ecc /data/photos /opt/ecc
COPY --chown=ecc:ecc app/ ./app/
USER ecc
WORKDIR /opt/ecc/app
EXPOSE 8082
CMD ["gunicorn", "--preload", "--workers", "2", "--threads", "2", "--timeout", "120", "--bind", "0.0.0.0:8082", "app:app"]
