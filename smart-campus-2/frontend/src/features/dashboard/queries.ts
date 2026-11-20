import { useQuery } from "@tanstack/react-query";
import { http } from "@/lib/api";
import type { StatCard as StatCardType, SeriesPoint, DistributionPoint } from "@/types";

export interface AdminDashboardData {
  stats: StatCardType[];
  program_distribution: DistributionPoint[];
  class_section_distribution: DistributionPoint[];
  attendance_trend: SeriesPoint[];
  examination_performance: SeriesPoint[];
  fee_collection: StatCardType[];
  outstanding_balance: number;
  recent_notices: { id: string; title: string; published_at: string }[];
  recent_activity: { id?: string; action?: string; resource_type?: string }[];
}
export interface TeacherDashboardData {
  stats: StatCardType[];
  assigned_classes: { class_id: string; section_id?: string | null; subject_id: string }[];
  assigned_subjects: string[];
  today_timetable: { id: string; start: string; end: string; class_id: string }[];
  upcoming_examinations: { id: string; name: string; date: string }[];
  recent_notices: { id: string; title: string }[];
  workload: { weekly_lectures: number };
}
export interface StudentDashboardData {
  stats: StatCardType[];
  attendance_percentage: number;
  subject_marks: { subject_id: string; percentage: number; grade?: string | null }[];
  recent_materials: { id: string; title: string }[];
  notices: { id: string; title: string }[];
  fee_summary: { total_outstanding: number; total_paid: number; total_invoiced: number };
}

export function useAdminDashboard() {
  return useQuery({ queryKey: ["dashboard", "admin"], queryFn: () => http.get<AdminDashboardData>("/dashboard/admin") });
}
export function useTeacherDashboard() {
  return useQuery({ queryKey: ["dashboard", "teacher"], queryFn: () => http.get<TeacherDashboardData>("/dashboard/teacher") });
}
export function useStudentDashboard() {
  return useQuery({ queryKey: ["dashboard", "student"], queryFn: () => http.get<StudentDashboardData>("/dashboard/student") });
}
