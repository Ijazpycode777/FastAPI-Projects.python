# Testing

Automated verification is layered: **unit** tests for pure business rules (no database) and **integration** tests for end-to-end API workflows against an in-memory SQLite database built from the same SQLAlchemy models used in PostgreSQL.

Run from `backend/`:

```bash
. .venv/bin/activate
pytest                       # everything (93 tests)
pytest tests/unit/           # pure logic
pytest tests/integration/    # API workflows
pytest --cov=app             # with coverage
```

The test suite uses an isolated in-memory SQLite database created fresh per test — it never touches production data. Argon2 parameters are lowered in `tests/conftest.py` for speed; production keeps strong defaults.

## Unit tests (`tests/unit/`)

Pure functions, no I/O — fast and deterministic.

| File | Covers |
| --- | --- |
| `test_grading.py` | boundary validation (gaps, overlaps, 0/100 coverage), half-open grade matching, percentage, pass/fail, version numbering |
| `test_attendance.py` | percentage rule incl. excused-excluded denominator, empty case, counts, status helpers |
| `test_exam_marks.py` | marks validation, absent-vs-zero distinction, grade/percentage, class average excluding absent |
| `test_fees.py` | paid/outstanding, status derivation (paid/partial/unpaid/overdue), totals, number generation |
| `test_timetable_conflict.py` | overlap detection, teacher/classroom/class/section conflicts, touching-vs-overlapping, different day |
| `test_notifications.py` | audience targeting (all/role/program/class/section), recipient filtering |
| `test_teacher_attendance.py` | work-start parsing, late threshold, work-minutes (incl. mixed tz), check-in/out state machine |
| `test_file_validation.py` | extension/size/content-type validation, zip-for-docx allowance |
| `test_password.py` | Argon2id hash/verify uniqueness, empty handling, strength rules, rehash detection |

## Integration tests (`tests/integration/`)

Real HTTP requests through the FastAPI app (httpx `AsyncClient` + `ASGITransport`), exercising routes → auth → services → database → transactions.

| Workflow | Tests |
| --- | --- |
| **Auth** | admin login success; wrong password / unknown user rejected; protected endpoint requires auth; logout invalidates session; admin dashboard gated by role |
| **Students** | admin creates a student (persisted); student logs in & reaches dashboard; student cannot view another student's records (403); unauthenticated cannot list; student cannot hit admin-only lists |
| **Attendance** | teacher marks attendance → percentage correct; duplicate attendance rejected (409); teacher check-in/check-out with double-check-in rejected |
| **Timetable** | teacher double-booking rejected (409); classroom double-booking rejected; non-overlapping entry accepted |
| **Examinations** | create exam → enter marks → grade/percentage/absent handling → publish → finalize; **finalized results unchanged after grading policy update**; marks exceeding max rejected |
| **Fees** | invoice → payment → outstanding/paid correct → partial status; payment exceeding balance rejected; student views own statement |

## What is verified end-to-end

- Authentication, authorization (role + resource), and session lifecycle
- Database transactions and rollback on multi-step failures (e.g. duplicate payment, conflicting timetable)
- Business calculations: attendance percentage, grade/pass-fail, outstanding balance
- Integrity constraints: duplicate attendance, duplicate marks, timetable conflicts, marks exceeding maximum
- Result integrity: historical results survive grading-policy changes
- Audit logging on important operations (recorded in `audit_logs`)

## Frontend tests

The frontend ships with a Vitest + React Testing Library setup (`frontend/vite.config.ts` `test` block, `src/test-setup.ts`). Run with `npm test` from `frontend/`. The backend carries the primary automated verification; browser-based end-to-end tests (Playwright) against the deployed public URL are the recommended next step.

## Manual smoke test (post-deploy)

Using the actual public URL and the demo accounts:

1. **Admin**: log in → dashboard shows non-zero stats and charts → create a student → create a teacher → publish a notice.
2. **Teacher**: log in → mark attendance for a lecture → enter marks for an examination → check in/out → upload a material.
3. **Student**: log in → view attendance percentage → view results → download a material → view fee statement.

Each step must succeed against the real database — no fabricated values.
