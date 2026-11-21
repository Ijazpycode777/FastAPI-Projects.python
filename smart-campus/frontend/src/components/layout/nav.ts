import {
  LayoutDashboard, Users, GraduationCap, CalendarCheck, FileText, ClipboardList,
  Wallet, CalendarDays, BookOpen, Megaphone, BarChart3,
} from "lucide-react";
import type { Role } from "@/lib/constants";

export interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  roles: Role[];
  group: string;
}

/** Role-aware navigation, grouped by section. Filtered at render time by role. */
export const NAV: NavItem[] = [
  { to: "/admin", label: "Dashboard", icon: LayoutDashboard, roles: ["admin"], group: "Main" },
  { to: "/teacher", label: "Dashboard", icon: LayoutDashboard, roles: ["teacher"], group: "Main" },
  { to: "/student", label: "Dashboard", icon: LayoutDashboard, roles: ["student"], group: "Main" },
  { to: "/students", label: "Student Logs", icon: Users, roles: ["admin"], group: "People" },
  { to: "/teachers", label: "Teacher Logs", icon: GraduationCap, roles: ["admin"], group: "People" },
  { to: "/attendance/mark", label: "Mark Attendance", icon: CalendarCheck, roles: ["teacher"], group: "Academics" },
  { to: "/attendance", label: "Attendance", icon: CalendarCheck, roles: ["admin", "teacher", "student"], group: "Academics" },
  { to: "/examinations", label: "Examinations", icon: FileText, roles: ["admin", "teacher"], group: "Academics" },
  { to: "/results", label: "Results", icon: ClipboardList, roles: ["admin", "teacher", "student"], group: "Academics" },
  { to: "/timetable", label: "Timetable", icon: CalendarDays, roles: ["admin", "teacher", "student"], group: "Academics" },
  { to: "/materials", label: "Materials", icon: BookOpen, roles: ["admin", "teacher", "student"], group: "Academics" },
  { to: "/fees", label: "Fees", icon: Wallet, roles: ["admin"], group: "Finance" },
  { to: "/student/fees", label: "My Fees", icon: Wallet, roles: ["student"], group: "Finance" },
  { to: "/notices", label: "Notices", icon: Megaphone, roles: ["admin", "teacher", "student"], group: "Communication" },
  { to: "/reports", label: "Reports", icon: BarChart3, roles: ["admin", "teacher"], group: "Communication" },
];

/** Stable group ordering for sidebar rendering. */
export const NAV_GROUP_ORDER = ["Main", "People", "Academics", "Finance", "Communication"];
