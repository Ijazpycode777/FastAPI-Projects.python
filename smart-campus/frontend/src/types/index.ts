export interface User {
  id: string;
  email: string;
  role: "admin" | "teacher" | "student";
  full_name: string;
  phone?: string | null;
  is_active: boolean;
  must_reset_password: boolean;
  last_login_at?: string | null;
}

export interface Profile {
  user: User;
  teacher?: { id: string; employee_id: string; department?: string | null } | null;
  student?: { id: string; admission_number: string } | null;
}

export interface Page<T> {
  items: T[];
  pagination: { page: number; page_size: number; total: number; total_pages: number };
}

export interface StatCard {
  label: string;
  value: number | string;
  hint?: string;
  tone?: string;
}

export interface SeriesPoint { label: string; value: number; }
export interface DistributionPoint { label: string; value: number; color?: string; }

export interface Student {
  id: string; user_id: string; admission_number: string; full_name: string; email: string;
  phone?: string | null; date_of_birth?: string | null; gender?: string | null;
  admission_date: string; account_status: string;
  current_program_id?: string | null; current_class_id?: string | null;
  current_section_id?: string | null; current_session_id?: string | null;
  current_roll_number?: number | null;
}

export interface BoardRecord {
  id: string; student_id: string; level: string; board: string; examination_year: number;
  total_marks: number; obtained_marks: number; grade?: string | null; percentage: number;
}

export interface Enrolment {
  id: string; student_id: string; academic_session_id: string; program_id: string;
  class_id: string; section_id: string; roll_number: number; is_active: boolean;
}

export interface Teacher {
  id: string; user_id: string; employee_id: string; full_name: string; email: string;
  phone?: string | null; department?: string | null; designation: string;
  joining_date: string; employment_status: string;
}

export interface AcademicSession { id: string; name: string; start_date: string; end_date: string; is_active: boolean; }
export interface Program { id: string; code: string; name: string; description?: string | null; }
export interface ClassLevel { id: string; program_id: string; name: string; year: number; }
export interface Section { id: string; class_level_id: string; name: string; capacity: number; }
export interface Subject { id: string; program_id: string; code: string; name: string; theory_marks: number; practical_marks: number; }
export interface Classroom { id: string; room_number: string; building?: string | null; capacity: number; is_active: boolean; }

export interface TimetableEntry {
  id: string; day_of_week: string; start_time: string; end_time: string;
  subject_id: string; teacher_id: string; class_id: string; section_id?: string | null;
  classroom_id?: string | null; is_cancelled: boolean;
  subject_name?: string; teacher_name?: string; classroom_number?: string;
}

export interface AttendanceRecord {
  id: string; student_id: string; status: "present" | "absent" | "late" | "excused";
  attendance_date: string; subject_id: string; class_id: string; section_id?: string | null;
  is_finalized: boolean; note?: string | null;
}
export interface AttendanceSummary {
  student_id: string; present: number; absent: number; late: number; excused: number;
  total_eligible: number; percentage: number;
}

export interface Examination {
  id: string; name: string; exam_type: string; academic_session_id: string; program_id: string;
  class_id: string; section_id?: string | null; subject_id: string; max_marks: number;
  passing_marks: number; exam_date: string; status: "draft" | "published" | "finalized";
  grading_policy_id?: string | null;
}
export interface StudentMark {
  id: string; examination_id: string; student_id: string; subject_id: string;
  marks_obtained: number; is_absent: boolean; grade?: string | null; percentage?: number | null;
  is_pass?: boolean | null; status: string;
}

export interface FeeStructure { id: string; name: string; amount: number; frequency: string; is_active: boolean; }
export interface FeeInvoice {
  id: string; invoice_number: string; student_id: string; amount: number;
  issued_date: string; due_date: string; status: string;
}
export interface InvoiceDetail extends FeeInvoice {
  paid_amount: number; outstanding: number; payments: Payment[];
}
export interface Payment {
  id: string; invoice_id: string; student_id: string; amount: number;
  paid_at: string; method: string; reference?: string | null; receipt_number: string;
}

export interface StudyMaterial {
  id: string; title: string; description?: string | null; subject_id: string; class_id: string;
  section_id?: string | null; file_name: string; file_size: number; content_type: string;
  created_at: string; is_active: boolean;
}

export interface Notice {
  id: string; title: string; content: string; published_at: string;
  target_audience: string; is_pinned: boolean; expires_at?: string | null;
}

export interface Notification {
  id: string; type: string; title: string; body?: string | null;
  read_at?: string | null; created_at: string;
}
