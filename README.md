# Argus Service Desk Python API

Production-grade Django + DRF backend for the React `argus-servicedesk` app.

## Goals

- Replace Node backend with Python backend.
- Keep Argus-style domain modules and endpoint surface under `/api/v1`.
- Support multi-tenant org context with `X-Organization-Id`.
- Keep secrets in environment variables only.

## Stack

- Django 5
- Django REST Framework
- Simple JWT
- PostgreSQL (default)
- Redis + Celery
- drf-spectacular (OpenAPI)

## Quick Start

```bash
cd Argus-Backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

API base: `http://localhost:8000/api/v1`

Health: `GET /health/`

## Vault / Secrets

Argus reads secrets only from environment variables or an optional env file rendered by Vault Agent.

For local development:

```bash
copy .env.example .env
```

For Kubernetes production, keep real values in Vault and inject them as env vars, or render them to a file and set:

```env
ARGUS_SECRETS_FILE=/vault/secrets/argus-backend.env
```

Required production secrets include:

```text
DJANGO_SECRET_KEY
JWT_SIGNING_KEY
DATABASE_URL or DB_PASSWORD
REDIS_URL
KEYCLOAK_ISSUER
ARGUS_WEBHOOK_API_TOKEN when ARGUS_WEBHOOK_REQUIRE_TOKEN=true
```

Never commit real `.env` files, tokens, passwords, or private keys.

