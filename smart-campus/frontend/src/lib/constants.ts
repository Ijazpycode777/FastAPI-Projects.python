export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string) || "/api/v1";

export const PAGE_SIZE = 20;

export const ROLE = {
  ADMIN: "admin",
  TEACHER: "teacher",
  STUDENT: "student",
} as const;

export type Role = (typeof ROLE)[keyof typeof ROLE];

export const ATTENDANCE_STATUS = {
  PRESENT: "present",
  ABSENT: "absent",
  LATE: "late",
  EXCUSED: "excused",
} as const;

export const STATUS_TONE: Record<string, string> = {
  present: "bg-teal/10 text-teal",
  late: "bg-amber/15 text-amber",
  absent: "bg-rose/10 text-rose",
  excused: "bg-indigo/10 text-indigo",
  active: "bg-teal/10 text-teal",
  inactive: "bg-slate-border text-slate-muted",
  paid: "bg-teal/10 text-teal",
  partial: "bg-amber/15 text-amber",
  unpaid: "bg-slate-border text-slate-muted",
  overdue: "bg-rose/10 text-rose",
  draft: "bg-slate-border text-slate-muted",
  published: "bg-indigo/10 text-indigo",
  finalized: "bg-teal/10 text-teal",
};

export const TONE_TEXT: Record<string, string> = {
  primary: "text-indigo",
  success: "text-teal",
  warning: "text-amber",
  danger: "text-rose",
  neutral: "text-navy",
};
