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

