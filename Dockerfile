FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --no-compile -r requirements.txt \
    && useradd --create-home --uid 10001 vanguard
COPY app ./app
COPY web ./web
COPY data ./data
RUN mkdir -p /app/data && chown -R vanguard:vanguard /app
USER vanguard
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
