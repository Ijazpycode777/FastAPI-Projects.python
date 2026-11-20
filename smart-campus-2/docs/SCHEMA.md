# Database Schema

PostgreSQL via SQLAlchemy 2.0, migrations via Alembic. 32 tables. Every primary key is a UUID v4 string (`String(36)`). All entities carry `created_at` / `updated_at` (timezone-aware UTC).

## Identity & sessions

### `users`
| column | type | notes |
| --- | --- | --- |
| id | String(36) PK | UUID |
| email | String(255) | unique, lowercase |
| role | String(16) | `admin` / `teacher` / `student` (check) |
| password_hash | String(255) | Argon2id |
| full_name, phone | strings | |
| is_active, must_reset_password | bool | |
| failed_login_attempts | int | account lockout counter |
| locked_until | String(40) | ISO timestamp; null when unlocked |

### `sessions`
Server-side session rows. The cookie token is opaque; the row is the truth.
| column | type | notes |
| --- | --- | --- |
| id | String(36) PK | |
| token | String(64) | unique CSPRNG token |
| user_id | FK → users | on delete cascade |
| expires_at | timestamptz | |
| revoked | bool | server-side revocation |
| ip_address, user_agent | strings | |

## Academic structure

### `academic_sessions`
`name` (e.g. 2025-2026, unique), `start_date`, `end_date`, `is_active`.

### `programs`
`code` (unique: ICS, FSc, I.Com…), `name`, `description`.

### `class_levels`
`program_id` FK, `name` (Part 1 / Part 2), `year`. Unique `(program_id, name)`.

### `sections`
`class_level_id` FK (cascade), `name` (A / B), `capacity`. Unique `(class_level_id, name)`.

### `subjects`
`program_id` FK, `code`, `name`, `theory_marks`, `practical_marks`. Unique `(program_id, code)`.

### `classrooms`
`room_number` (unique), `building`, `capacity`, `is_active`.

## People

### `teachers`
`user_id` FK (cascade, unique), `employee_id` (unique), `full_name`, `email`, `phone`, `department`, `designation`, `joining_date`, `employment_status`.

### `guardians`
`name`, `phone`, `email`, `relationship_type`, `occupation`.

### `students`
`user_id` FK (cascade, unique), `admission_number` (unique), `full_name`, `email`, `phone`, `date_of_birth`, `gender` (check), `guardian_id` FK (set null), `admission_date`, `account_status` (check), plus current placement pointers: `current_program_id`, `current_class_id`, `current_section_id`, `current_session_id`, `current_roll_number`. These mutate on promotion; history is preserved in enrolments.

### `student_enrolments`
One row per (student, academic session). `student_id` FK, `academic_session_id`, `program_id`, `class_id`, `section_id`, `roll_number`, `is_active`. Unique `(session, section, roll_number)`. Previous enrolments are deactivated, never deleted.

### `student_academic_history`
Snapshot of placement at promotion time: `previous_class`, `previous_section`, `previous_session`, `previous_roll_number`, `action` (promoted/repeated/section_change/left), `note`.

### `board_examination_records`
External board results, separate from college exams. `student_id`, `level` (matric/inter_part1), `board`, `examination_year`, `total_marks`, `obtained_marks`, `grade`. Unique `(student, level)`.

### `teacher_assignments`
Authoritative source of a teacher's authority. `teacher_id`, `subject_id`, `class_id`, `section_id` (nullable), `academic_session_id`, `is_active`. Unique on the full tuple.

## Timetable

### `timetable_periods`
Named period template: `name`, `day_of_week`, `start_time`, `end_time`, `academic_session_id`.

### `timetable_entries`
A scheduled lecture: `day_of_week`, `start_time`, `end_time`, `subject_id`, `teacher_id`, `class_id`, `section_id`, `classroom_id`, `is_cancelled`. `end_time > start_time` check; conflicts (teacher/classroom/class/section overlap) validated transactionally in the service layer.

## Attendance

### `attendance_records`
One row per (student, scheduled lecture, date). `student_id`, `timetable_entry_id`, `subject_id`, `teacher_id`, `class_id`, `section_id`, `academic_session_id`, `attendance_date`, `status` (present/absent/late/excused), `marked_by`, `marked_at`, `is_finalized`, `note`. Unique `(student, timetable_entry, date)`.

Percentage rule: `(present + late) / (present + late + absent) × 100`. Excused is excluded from the denominator.

### `teacher_attendance`
Self-attendance: `teacher_id`, `attendance_date`, `check_in_at`, `check_out_at`, `status`, `work_minutes`, `note`. Unique `(teacher, date)`. Timestamps are server-generated.

### `holidays`, `leave_records`
Holidays: `(date, session)` unique. Leave: `teacher_id`, `start_date`, `end_date`, `reason`, `status` (pending/approved/rejected), `approved_by`.

## Examinations & grading

### `grading_policies` / `grading_boundaries`
Versioned policy: `name`, `version` (unique `(name, version)`), `is_active`, `description`. Boundaries: `grade_name`, `min_percentage`, `max_percentage`, `is_pass`, `description`. Validated contiguously over `[0, 100]` with half-open matching. Finalized results keep the `grading_policy_id` they were computed with, so changing boundaries for future exams never rewrites history.

### `examinations`
`name`, `exam_type` (monthly_test/class_test/midterm/final/quiz), academic + class + section + subject scope, `max_marks`, `passing_marks` (≤ max), `exam_date`, `status` (draft/published/finalized), `created_by`, `finalized_by`, `finalized_at`, `grading_policy_id`.

### `student_marks`
`examination_id`, `student_id`, `subject_id`, `marks_obtained`, `is_absent`, `grade`, `percentage`, `is_pass`, `status` (entered/finalized), `recorded_by`, `recorded_at`, `finalized_at`. Unique `(exam, student)`. Absent students are distinct from students who scored zero.

## Fees

### `fee_structures`
`name`, `program_id`, `class_id`, `academic_session_id`, `amount` (Numeric(12,2)), `frequency`, `due_after_days`, `is_active`.

### `fee_invoices`
`invoice_number` (unique), `student_id`, `fee_structure_id`, `academic_session_id`, `amount`, `issued_date`, `due_date`, `status` (unpaid/partial/paid/overdue/void), `issued_by`.

### `payments`
`invoice_id`, `student_id`, `amount`, `paid_at`, `method`, `reference`, `recorded_by`, `receipt_number` (unique). Outstanding balance is always `amount − sum(payments)` from authoritative rows.

## Materials, notices, notifications, audit

### `study_materials`
Metadata only — file bytes live in object/local storage. `title`, `description`, `subject_id`, `class_id`, `section_id`, `uploaded_by`, `storage_backend`, `storage_key`, `file_name`, `file_size`, `content_type`, `is_active`.

### `notices`
`title`, `content`, `published_by`, `published_at`, `target_audience` (all/admins/teachers/students/program/class/section), `program_id`, `class_id`, `section_id`, `expires_at`, `is_pinned`.

### `notifications`
Per-user in-app notification. `user_id`, `type`, `title`, `body`, `related_resource_type`, `related_resource_id`, `read_at`. Delivered only to users the audience rule matches.

### `audit_logs`
Append-only. `actor_id`, `actor_role`, `action`, `resource_type`, `resource_id`, `before` (JSON), `after` (JSON), `ip_address`, `user_agent`.
