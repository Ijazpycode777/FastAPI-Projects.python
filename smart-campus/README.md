# Smart Campus

A complete, modern **College Management System** built as a full-stack modular monolith: a React + TypeScript frontend and a FastAPI + PostgreSQL backend in a single deployable repository.

Every advertised feature works through real application logic and persistent database operations — there are no UI-only prototypes, no mock interactions, and no hardcoded dashboard statistics.

---

## Table of contents

1. [Overview](#overview)
2. [Technology stack](#technology-stack)
3. [Architecture](#architecture)
4. [Repository structure](#repository-structure)
5. [Local installation](#local-installation)
6. [Environment setup](#environment-setup)
7. [Database configuration & migrations](#database-configuration--migrations)
8. [Running the backend](#running-the-backend)
9. [Running the frontend](#running-the-frontend)
10. [Running tests](#running-tests)
11. [Docker](#docker)
12. [Deployment (Render)](#deployment-render)
13. [Demo accounts](#demo-accounts)
14. [Known limitations](#known-limitations)
15. [Further documentation](#further-documentation)

---

## Overview

Smart Campus serves a single college that operates multiple academic programs (ICS, FSc, I.Com and other configurable programs), classes/parts, sections and academic sessions. It provides three role-specific experiences — **Administrator**, **Teacher** and **Student** — covering:

- Student & teacher management with academic history and board records
- Lecture-based student attendance with the correct percentage rule
- Teacher self-attendance (check-in / check-out, working hours, late threshold)
- Timetable management with backend-enforced conflict detection
- Examinations, marks entry, a **versioned** configurable grading system, and finalized result integrity
- Fee structures, invoices, payments and outstanding balances (money as fixed-precision `Numeric`)
- Study materials with secure uploads and authorized downloads (files outside the DB)
- Notices with audience-targeted in-app notifications
- Academic progression that preserves historical records
- Role-specific dashboards with charts driven by real database data
- Reports & exports (Excel + PDF) from authorized live records
- Argon2id password hashing, server-managed HttpOnly sessions, CSRF protection, rate limiting and audit logging

The system deliberately does **not** include an assignment/submission module and does **not** implement dark mode.

## Technology stack

**Frontend:** React 18, TypeScript, Tailwind CSS 3, Vite 6, React Router 6, TanStack Query 5, React Hook Form + Zod, Recharts, Lucide icons.

**Backend:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic, PostgreSQL, Argon2id (`argon2-cffi`), server-managed sessions, slowapi rate limiting, pytest + HTTPX.

**Infrastructure:** Docker (multi-stage), Docker Compose, GitHub, Render Web Service + Render PostgreSQL, persistent disk for uploaded materials.

## Architecture

A **modular monolith**: the React frontend and FastAPI backend live in one repository but are logically separated. The backend exposes a versioned API under `/api/v1/` and follows a layered design — **routes → services → repositories → models**. Business rules that are pure (attendance percentage, grade calculation, fee math, timetable conflict detection, notification targeting) live in dedicated `*_logic` / pure modules so they are unit-tested without a database. DB-backed services compose those rules with queries and transactions.

In production the FastAPI app **serves the built frontend and the API from the same origin**, so session cookies, CSRF and CORS stay simple and secure.

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the deployment architecture diagram.

## Repository structure

```
smart-campus/
├── frontend/                 # React + Vite + Tailwind app
│   ├── src/
│   │   ├── components/       # common, charts, forms, tables, layout
│   │   ├── features/         # authentication, dashboard, students, teachers,
│   │   │                     # attendance, examinations, results, fees,
│   │   │                     # timetable, materials, notices, reports
│   │   ├── hooks/            # useAuth, useToast, useDebounce
│   │   ├── layouts/          # AppLayout (sidebar + topbar)
│   │   ├── lib/              # api client, constants, utils
│   │   ├── types/            # shared TypeScript types
│   │   ├── App.tsx           # routes + role guards
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── backend/
│   ├── app/
│   │   ├── api/v1/           # auth, students, teachers, academic, timetable,
│   │   │                     # attendance, teacher_attendance, examinations,
│   │   │                     # grading, fees, materials, notices, dashboard,
│   │   │                     # reports, audit
│   │   ├── core/             # config, exceptions
│   │   ├── database/         # async engine/session, declarative base, mixins
│   │   ├── models/           # 32 SQLAlchemy 2.0 models
│   │   ├── schemas/          # Pydantic v2 I/O schemas
│   │   ├── repositories/     # base repository + audit helper
│   │   ├── services/         # business logic (pure + DB-backed)
│   │   ├── security/         # Argon2id, sessions, CSRF, dependencies
│   │   ├── middleware/       # CSRF, request-id, security headers
│   │   ├── utils/            # helpers (sql_in, roll numbers, filenames…)
│   │   ├── seed.py           # coherent demo data
│   │   └── main.py           # FastAPI app factory
│   ├── migrations/           # Alembic env + initial migration
│   ├── tests/                # unit/ + integration/ + conftest.py
│   ├── alembic.ini
│   ├── requirements.txt
│   └── pytest.ini
├── docs/                     # ER diagram, schema, API, auth, deployment, testing
├── Dockerfile                # multi-stage: build frontend + run backend
├── docker-compose.yml        # local PostgreSQL + app
├── render.yaml               # Render blueprint
├── .env.example
└── README.md
```

## Local installation

Prerequisites: Python 3.11+, Node 20+, PostgreSQL 16+ (or just Docker).

```bash
git clone <repo-url> smart-campus
cd smart-campus
cp .env.example .env          # then edit values (see below)
```

### Backend

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

## Environment setup

Copy `.env.example` to `.env` and set at least:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Async SQLAlchemy URL (`postgresql+asyncpg://…`) |
| `DATABASE_URL_SYNC` | Sync URL for Alembic (`postgresql+psycopg2://…`) |
| `SESSION_SECRET_KEY` | Long random string for cookie signing (`python -c "import secrets;print(secrets.token_urlsafe(64))"`) |
| `SESSION_COOKIE_SECURE` | `false` locally, `true` in production |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed origins |
| `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` | Bootstrap admin credentials |
| `SEED_RESET_ON_START` | `true` to seed demo data on startup (dev only) |

Full reference in [`.env.example`](.env.example).

## Database configuration & migrations

The schema is created entirely by Alembic. The initial migration reflects the full SQLAlchemy metadata, so `alembic upgrade head` builds every table from a fresh database — no manual table creation is ever required.

```bash
cd backend
# create the database once (if not using Docker):
createdb smartcampus

# run migrations
alembic upgrade head
```

See [docs/SCHEMA.md](docs/SCHEMA.md) for the full schema and [docs/ER_DIAGRAM.md](docs/ER_DIAGRAM.md) for the entity-relationship diagram.

## Running the backend

```bash
cd backend
. .venv/bin/activate
# run migrations then start the dev server
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Interactive API docs are available at `http://localhost:8000/docs` (OpenAPI) and `/redoc`.

## Running the frontend

```bash
cd frontend
npm run dev
```

The Vite dev server runs on `http://localhost:5173` and proxies `/api` to the backend on port 8000, so cookies and CSRF work across the two origins in development.

To build the production bundle (served by the backend in deployment):

```bash
npm run build      # outputs frontend/dist/
```

## Running tests

The backend test suite uses an in-memory SQLite database (the same models used in Postgres) so it requires no running PostgreSQL. Argon2 parameters are lowered in tests for speed; production keeps strong defaults.

```bash
cd backend
. .venv/bin/activate
pytest                         # all tests
pytest tests/unit/             # pure business logic
pytest tests/integration/      # end-to-end API workflows
pytest --cov=app               # with coverage
```

Frontend tests (Vitest + React Testing Library):

```bash
cd frontend
npm test
```

See [docs/TESTING.md](docs/TESTING.md) for details and the workflow coverage matrix.

## Docker

A single multi-stage `Dockerfile` builds the frontend and runs the backend, serving both from one origin.

```bash
docker compose up --build
# app:  http://localhost:8000
# db:   postgresql://smartcampus:smartcampus@localhost:5432/smartcampus
```

The container runs `alembic upgrade head` on start, then calls `bootstrap_admin()`
to ensure a usable administrator exists (created from `SEED_ADMIN_EMAIL` /
`SEED_ADMIN_PASSWORD` if missing; existing admin passwords are never reset).
Demo data is seeded **only** when `APP_ENV != production` **and**
`SEED_RESET_ON_START=true`; production never seeds synthetic students/teachers.

## Deployment (Render)

Deploy through one GitHub repository using the included `render.yaml` blueprint:

- **Render PostgreSQL** (`smartcampus-db`) — persistent relational database
- **Render Web Service** (`smartcampus`, Docker runtime) — FastAPI serves the API and the built frontend from the same origin
- **Render Disk** mounted at `/var/data` — persistent local storage for study materials

Render injects `DATABASE_URL` from the database; the app normalizes `postgres://` to the asyncpg driver automatically. Migrations run on every deploy via the container `CMD`. Health checks hit `/health`.

Push the repository to GitHub, create a new Blueprint deployment on Render pointing at the repo (apply from the repository root — the blueprint's `dockerContext: .` is the repo root, not a nested subdirectory). Render provisions the database, web service and disk from `render.yaml`, auto-generates `SEED_ADMIN_PASSWORD`, and on first deploy `bootstrap_admin()` creates the administrator from `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD`. To rotate the bootstrap email later, change `SEED_ADMIN_EMAIL` and redeploy — note that bootstrap never resets an existing administrator's password.

Full instructions and the architecture diagram: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Demo accounts

Synthetic demonstration data only — **never** real student information. Seeded by `backend/app/seed.py` when `SEED_RESET_ON_START=true`.

| Role | Email | Password |
| --- | --- | --- |
| Administrator | `admin@smartcampus.edu` | `ChangeMe!2025` |
| Teacher | `teacher.sarah@smartcampus.edu` | `Teacher!2025` |
| Student | `student.ali@smartcampus.edu` | `Student!2025` |
| Student | `student.fatima@smartcampus.edu` | `Student!2025` |
| Student | `student.bilal@smartcampus.edu` | `Student!2025` |

Change these in production via the environment variables.

## Known limitations

- **Render free/starter disk**: study materials use the local-storage backend on a Render Disk. For very large volumes, configure the S3 backend (`STORAGE_BACKEND=s3`) with credentials — the S3 adapter is stubbed and must be completed with real credentials in production.
- **Async lazy-loading**: relationships used in responses are eagerly loaded (`selectin`) to stay safe under async SQLAlchemy; deeply nested ad-hoc relationship traversal outside API responses is intentionally avoided.
- **Frontend tests**: the component test scaffolding (Vitest + React Testing Library) is in place; the backend carries the primary automated verification (93 unit + integration tests). End-to-end browser tests (Playwright) are configured as a next step rather than included.
- **Email delivery**: password reset issues a temporary password returned to the administrator (over a secure session). Outbound email is not wired (no SMTP provider configured) — this is a deliberate scope decision documented here.
- **Single college**: the data model is shaped for one college with multiple programs; multi-tenancy is out of scope.

## Further documentation

- [docs/ER_DIAGRAM.md](docs/ER_DIAGRAM.md) — entity-relationship diagram
- [docs/SCHEMA.md](docs/SCHEMA.md) — database schema documentation
- [docs/API.md](docs/API.md) — API endpoint reference (also see live `/docs`)
- [docs/AUTHORIZATION.md](docs/AUTHORIZATION.md) — authentication & authorization overview
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — deployment architecture & instructions
- [docs/TESTING.md](docs/TESTING.md) — testing strategy & workflow coverage

---

Built as a coherent, genuinely functional college management platform. Correctness, security and data integrity are prioritised over decorative exhaustiveness.
