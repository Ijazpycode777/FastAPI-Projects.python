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
}

/** Role-aware navigation. Filtered at render time by the current user's role. */
export const NAV: NavItem[] = [
  { to: "/admin", label: "Dashboard", icon: LayoutDashboard, roles: ["admin"] },
  { to: "/teacher", label: "Dashboard", icon: LayoutDashboard, roles: ["teacher"] },
  { to: "/student", label: "Dashboard", icon: LayoutDashboard, roles: ["student"] },
  { to: "/students", label: "Students", icon: Users, roles: ["admin"] },
  { to: "/teachers", label: "Teachers", icon: GraduationCap, roles: ["admin"] },
  { to: "/attendance/mark", label: "Mark Attendance", icon: CalendarCheck, roles: ["teacher"] },
  { to: "/attendance", label: "Attendance", icon: CalendarCheck, roles: ["admin", "teacher", "student"] },
  { to: "/examinations", label: "Examinations", icon: FileText, roles: ["admin", "teacher"] },
  { to: "/results", label: "Results", icon: ClipboardList, roles: ["admin", "teacher", "student"] },
  { to: "/fees", label: "Fees", icon: Wallet, roles: ["admin"] },
  { to: "/student/fees", label: "My Fees", icon: Wallet, roles: ["student"] },
  { to: "/timetable", label: "Timetable", icon: CalendarDays, roles: ["admin", "teacher", "student"] },
  { to: "/materials", label: "Materials", icon: BookOpen, roles: ["admin", "teacher", "student"] },
  { to: "/notices", label: "Notices", icon: Megaphone, roles: ["admin", "teacher", "student"] },
  { to: "/reports", label: "Reports", icon: BarChart3, roles: ["admin", "teacher"] },
];
