FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml ./
RUN uv pip install --system -r pyproject.toml

COPY . .

EXPOSE 3399

# migrations and platform defaults (idempotent) on every start, then the API with its
# background loops (e-mails, campaigns, invites, billing reminders, AI jobs)
CMD ["sh", "-c", "python manage.py migrate && python manage.py seed && uvicorn app.main:app --host 0.0.0.0 --port ${VIP_PORT:-3399} --proxy-headers --forwarded-allow-ips='*'"]
