# API Reference

All endpoints are versioned under `/api/v1/`. The live, interactive OpenAPI documentation is served at `/docs` (Swagger) and `/redoc` (ReDoc) once the backend is running — that is the canonical reference. This document summarises the surface area.

## Conventions

- **Auth:** server-managed session cookie (`smartcampus_session`, HttpOnly). Credentials are sent automatically by the browser; the frontend API client uses `credentials: "include"`.
- **CSRF:** every unsafe method (`POST`/`PUT`/`PATCH`/`DELETE`) requires a matching `X-CSRF-Token` header against the `smartcampus_csrf` cookie. Acquire a token with `POST /auth/csrf`.
- **Errors:** a consistent envelope —
  ```json
  { "error": { "code": "VALIDATION_ERROR", "message": "...", "details": [{"field":"email","message":"..."}], "request_id": "..." } }
  ```
  Codes: `BAD_REQUEST`, `UNAUTHENTICATED`, `FORBIDDEN`, `NOT_FOUND`, `METHOD_NOT_ALLOWED`, `CONFLICT`, `VALIDATION_ERROR`, `TOO_MANY_REQUESTS`, `INTERNAL_ERROR`, `SERVICE_UNAVAILABLE`.
- **Pagination:** list endpoints return `{ "items": [...], "pagination": { "page", "page_size", "total", "total_pages" } }`.

## Authentication

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| POST | `/auth/csrf` | public | issue CSRF token cookie |
| POST | `/auth/login` | public | email + password → session + profile |
| POST | `/auth/logout` | any | revoke session, clear cookies |
| GET | `/auth/me` | any | current profile |
| POST | `/auth/password` | any | change own password |
| POST | `/auth/reset/{user_id}` | admin | issue temporary password (admin never sees existing) |

## Academic structure

| Method | Path | Role |
| --- | --- | --- |
| GET/POST | `/sessions` | get: any · post: admin |
| GET/POST | `/programs` | get: any · post: admin |
| GET/POST | `/classes` | get: any · post: admin |
| GET/POST | `/sections` | get: any · post: admin |
| GET/POST | `/subjects` | get: any · post: admin |
| GET/POST | `/classrooms` | get: any · post: admin |
| GET/POST | `/assignments` | get: any · post: admin |

## Students

| Method | Path | Role |
| --- | --- | --- |
| GET | `/students` | admin (search/filter/paginate) |
| POST | `/students` | admin |
| GET | `/students/{id}` | admin or self |
| PATCH | `/students/{id}` | admin |
| POST | `/students/{id}/activate` `/deactivate` | admin |
| POST | `/students/promote` | admin |
| GET/POST | `/students/{id}/board-records` | admin (get: admin or self) |
| GET | `/students/me/attendance` | student |

## Teachers

| Method | Path | Role |
| --- | --- | --- |
| GET | `/teachers` | admin |
| POST | `/teachers` | admin |
| GET | `/teachers/{id}` | admin |
| PATCH | `/teachers/{id}` | admin |
| POST | `/teachers/{id}/activate` `/deactivate` | admin |

## Timetable

| Method | Path | Role |
| --- | --- | --- |
| GET/POST | `/timetable/periods` | get: any · post: admin |
| GET/POST | `/timetable/entries` | get: any · post: admin/teacher |
| POST | `/timetable/entries/{id}/cancel` | admin |
| GET | `/timetable/me` | teacher (own) / student (class) |

## Attendance

| Method | Path | Role |
| --- | --- | --- |
| POST | `/attendance/mark` | teacher |
| PATCH | `/attendance/{record_id}` | teacher (own) / admin (finalized correction) |
| GET | `/attendance/student/{student_id}` | admin/teacher or self |
| GET | `/attendance/class/{class_id}` | admin/teacher |
| GET | `/attendance/records` | scoped by role |

## Teacher self-attendance

| Method | Path | Role |
| --- | --- | --- |
| POST | `/teacher-attendance/check-in` | teacher |
| POST | `/teacher-attendance/check-out` | teacher |
| GET | `/teacher-attendance/today` | teacher |
| GET | `/teacher-attendance/history` | teacher |
| GET | `/teacher-attendance/summary` | teacher |

## Examinations & grading

| Method | Path | Role |
| --- | --- | --- |
| GET/POST | `/examinations` | admin/teacher |
| GET | `/examinations/{id}` | any authed |
| POST | `/examinations/{id}/marks` | admin/teacher (authorized) |
| GET | `/examinations/{id}/marks` | any authed |
| POST | `/examinations/{id}/publish` `/finalize` | admin/teacher |
| GET/POST | `/grading` | get: any · post: admin |
| GET | `/grading/active` | any |
| POST | `/grading/{id}/activate` | admin |

## Fees

| Method | Path | Role |
| --- | --- | --- |
| GET/POST | `/fees/structures` | get: any · post: admin |
| GET/POST | `/fees/invoices` | admin |
| GET | `/fees/invoices/{id}` | admin or owner |
| POST | `/fees/payments` | admin |
| GET | `/fees/statement/me` | student |
| GET | `/fees/statement/{student_id}` | admin or owner |

## Materials, notices, notifications

| Method | Path | Role |
| --- | --- | --- |
| GET/POST | `/materials` | get: scoped · post: admin/teacher |
| GET | `/materials/{id}/download` | authorized only |
| DELETE | `/materials/{id}` | admin/teacher |
| GET/POST | `/notices` | get: scoped · post: admin/teacher |
| DELETE | `/notices/{id}` | admin or publisher |
| GET | `/notifications` | any (own) |
| POST | `/notifications/{id}/read` `/read-all` | any (own) |

## Dashboard & reports

| Method | Path | Role |
| --- | --- | --- |
| GET | `/dashboard/admin` | admin |
| GET | `/dashboard/teacher` | teacher |
| GET | `/dashboard/student` | student |
| GET | `/dashboard/me` | any (dispatches by role) |
| GET | `/reports/students.xlsx` | admin |
| GET | `/reports/attendance/class/{class_id}.xlsx` | admin/teacher |
| GET | `/reports/fees/{student_id}.pdf` | admin |
| GET | `/reports/payments/{payment_id}/receipt.pdf` | admin |
| GET | `/reports/examinations/{exam_id}/result-sheet.pdf` | admin/teacher |

## Audit

| Method | Path | Role |
| --- | --- | --- |
| GET | `/audit` | admin (filter by action/resource/actor, paginated) |
