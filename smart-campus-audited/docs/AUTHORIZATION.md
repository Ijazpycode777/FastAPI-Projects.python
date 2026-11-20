# Authentication & Authorization

Smart Campus implements server-managed browser sessions with role-based access control (RBAC) and resource-level authorization. Frontend route guards are a convenience only — **every protected backend endpoint enforces authorization independently**.

## Three roles

| Role | Scope |
| --- | --- |
| **Administrator** | Full college management: create users, students, teachers, academic structure, timetable, examinations, fees, notices, reports. |
| **Teacher** | Limited to assigned classes/sections/subjects: mark attendance, enter marks, upload materials, publish class/section notices, self-attendance. |
| **Student** | Own academic information only: profile, attendance history, results, fee statement, materials authorized for their class, notices targeted to them. |

Student self-registration is **not** provided — administrators create student and teacher accounts.

## Authentication flow

1. `POST /api/v1/auth/login` with email + password.
2. Backend validates credentials against the Argon2id hash in the database.
3. On success: retrieves the user's real role, creates a **cryptographically random** session token (`secrets.token_urlsafe(32)`, ~256 bits), persists a `sessions` row, sets an **HttpOnly** cookie (`smartcampus_session`). Issues a separate non-HttpOnly **CSRF** cookie.
4. Revokes the user's prior active sessions (one active session per user — session fixation protection).
5. Returns the profile; the frontend redirects to the role-specific dashboard.

## Session security

- **HttpOnly cookies** — JavaScript cannot read the session token (no XSS exfiltration).
- **Secure cookies** in production (`SESSION_COOKIE_SECURE=true`), **SameSite=lax**.
- **Server-side revocation** on logout (`sessions.revoked = true`) and on new login.
- **Session expiration** (`SESSION_MAX_AGE_SECONDS`, default 8h).
- **Login rate limiting** via slowapi (`LOGIN_RATE_LIMIT`, default `5/minute`).
- **Account lockout** after 5 consecutive failed attempts (`locked_until`).
- Passwords and session credentials are **never** stored in browser `localStorage`.

## CSRF protection

Double-submit cookie: a non-HttpOnly `smartcampus_csrf` cookie holds a token that must also be sent in the `X-CSRF-Token` header on every unsafe method. The session token itself never leaves the HttpOnly cookie, so an attacker cannot forge both tokens via XSS. Login, CSRF issuance and password-reset endpoints are exempt.

## Password security

- **Argon2id** (`argon2-cffi`, `Type.ID`) with configurable time/memory/parallelism.
- Never plaintext, never reversibly encrypted.
- Strength validation: min length, upper/lower/digit/symbol.
- Administrators may **reset** credentials (issuing a temporary password) but can **never view** existing passwords.
- `must_reset_password` flag forces a change after an admin reset.

## Authorization enforcement

The `get_current_user` dependency resolves the session → user on every protected request. `require_roles(*roles)` (and `require_admin` / `require_teacher` / `require_student` / `require_staff`) enforce role gates. Resource-level checks live in the services:

- **Teacher authorization** consults `teacher_assignments` — the single source of truth — for attendance marking, marks entry, material upload/download, and notice publishing. A teacher can only act on subjects/classes/sections assigned to them.
- **Student authorization** compares the resource's owner (`student_id`) against `user.student_profile.id`. Students cannot read another student's records, attendance, marks, fees or materials.
- **Finalized records** (attendance, examination results) cannot be silently changed — only an administrator may correct them, and every correction is written to the audit log.

## Defense in depth

- Pydantic input validation on every endpoint.
- SQLAlchemy 2.0 ORM query construction (parameterized) — no string-interpolated SQL.
- Strict CORS (configured origins only).
- Security headers: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Strict-Transport-Security`, `Permissions-Policy`.
- Safe error responses — internal stack traces are never exposed to clients (the global exception handler logs them server-side and returns a generic 500 envelope).
- File uploads: extension + size + real content-type validation; safe filenames; path-traversal-safe storage keys; authorized downloads only.
- Audit logging of every important state-changing operation (create/update/delete/promote/finalize/payment/password reset/attendance correction).

## Secrets

No credentials, API keys, encryption keys or database passwords are hardcoded. Everything is read from environment variables via `pydantic-settings`. `.env` is gitignored; only `.env.example` is committed.

AES-256-GCM is available for any field that genuinely needs reversible encryption (none currently do — Argon2id hashes are one-way by design).
