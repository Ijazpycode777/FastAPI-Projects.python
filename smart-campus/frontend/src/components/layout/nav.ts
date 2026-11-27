import {
  LayoutDashboard, Users, GraduationCap, CalendarCheck, FileText, ClipboardList,
  Wallet, CalendarDays, BookOpen, BarChart3, Layers, ShieldCheck, KeyRound,
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
  { to: "/admins", label: "Administrators", icon: ShieldCheck, roles: ["admin"], group: "People" },
  { to: "/classes", label: "Classes Distribution", icon: Layers, roles: ["admin", "teacher"], group: "Academics" },
  { to: "/attendance/mark", label: "Mark Attendance", icon: CalendarCheck, roles: ["teacher"], group: "Academics" },
  { to: "/attendance", label: "Attendance", icon: CalendarCheck, roles: ["admin", "teacher", "student"], group: "Academics" },
  { to: "/examinations", label: "Examinations", icon: FileText, roles: ["admin", "teacher"], group: "Academics" },
  { to: "/results", label: "Results", icon: ClipboardList, roles: ["admin", "teacher", "student"], group: "Academics" },
  { to: "/timetable", label: "Timetable", icon: CalendarDays, roles: ["admin", "teacher", "student"], group: "Academics" },
  { to: "/materials", label: "Materials", icon: BookOpen, roles: ["admin", "teacher", "student"], group: "Academics" },
  { to: "/fees", label: "Fees", icon: Wallet, roles: ["admin"], group: "Finance" },
  { to: "/student/fees", label: "My Fees", icon: Wallet, roles: ["student"], group: "Finance" },
  // Notices is intentionally absent from the sidebar — it is reachable only
  // via the bell icon in the Topbar, which doubles as the unseen-notice badge.
  { to: "/reports", label: "Reports", icon: BarChart3, roles: ["admin", "teacher"], group: "Communication" },
  { to: "/change-password", label: "Change Password", icon: KeyRound, roles: ["admin", "teacher", "student"], group: "Account" },
];

/** Stable group ordering for sidebar rendering. */
export const NAV_GROUP_ORDER = ["Main", "People", "Academics", "Finance", "Communication", "Account"];
