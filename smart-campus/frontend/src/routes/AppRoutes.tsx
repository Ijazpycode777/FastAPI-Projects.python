/**
 * Route table, lazy page imports and access guards.
 *
 * - `Protected` enforces authentication and (optionally) role membership.
 * - Every protected route is wrapped, so role guards run on every navigation,
 *   not only on initial load. Backend authorization is enforced independently
 *   on every endpoint regardless of these client-side guards.
 */
import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { AppLayout } from "@/layouts/AppLayout";
import { FullPageLoader } from "@/components/common/FullPageLoader";
import { NotFound } from "@/components/common/NotFound";
import { ForbiddenPage } from "@/components/common/ForbiddenPage";
import type { Role } from "@/lib/constants";

const LoginPage = lazy(() => import("@/features/authentication/LoginPage").then((m) => ({ default: m.LoginPage })));
const AdminDashboard = lazy(() => import("@/features/dashboard/AdminDashboard").then((m) => ({ default: m.AdminDashboard })));
const TeacherDashboard = lazy(() => import("@/features/dashboard/TeacherDashboard").then((m) => ({ default: m.TeacherDashboard })));
const StudentDashboard = lazy(() => import("@/features/dashboard/StudentDashboard").then((m) => ({ default: m.StudentDashboard })));
const StudentListPage = lazy(() => import("@/features/students/StudentListPage").then((m) => ({ default: m.StudentListPage })));
const StudentDetailPage = lazy(() => import("@/features/students/StudentDetailPage").then((m) => ({ default: m.StudentDetailPage })));
const StudentFormPage = lazy(() => import("@/features/students/StudentFormPage").then((m) => ({ default: m.StudentFormPage })));
const TeacherListPage = lazy(() => import("@/features/teachers/TeacherListPage").then((m) => ({ default: m.TeacherListPage })));
const TeacherDetailPage = lazy(() => import("@/features/teachers/TeacherDetailPage").then((m) => ({ default: m.TeacherDetailPage })));
const TeacherFormPage = lazy(() => import("@/features/teachers/TeacherFormPage").then((m) => ({ default: m.TeacherFormPage })));
const AttendanceMarkingPage = lazy(() => import("@/features/attendance/AttendanceMarkingPage").then((m) => ({ default: m.AttendanceMarkingPage })));
const AttendanceHistoryPage = lazy(() => import("@/features/attendance/AttendanceHistoryPage").then((m) => ({ default: m.AttendanceHistoryPage })));
const ExaminationListPage = lazy(() => import("@/features/examinations/ExaminationListPage").then((m) => ({ default: m.ExaminationListPage })));
const MarksEntryPage = lazy(() => import("@/features/examinations/MarksEntryPage").then((m) => ({ default: m.MarksEntryPage })));
const ResultsPage = lazy(() => import("@/features/results/ResultsPage").then((m) => ({ default: m.ResultsPage })));
const FeeListPage = lazy(() => import("@/features/fees/FeeListPage").then((m) => ({ default: m.FeeListPage })));
const InvoiceDetailPage = lazy(() => import("@/features/fees/InvoiceDetailPage").then((m) => ({ default: m.InvoiceDetailPage })));
const TimetablePage = lazy(() => import("@/features/timetable/TimetablePage").then((m) => ({ default: m.TimetablePage })));
const MaterialsPage = lazy(() => import("@/features/materials/MaterialsPage").then((m) => ({ default: m.MaterialsPage })));
const NoticesPage = lazy(() => import("@/features/notices/NoticesPage").then((m) => ({ default: m.NoticesPage })));
const ReportsPage = lazy(() => import("@/features/reports/ReportsPage").then((m) => ({ default: m.ReportsPage })));

function HomeRedirect() {
  const { profile, loading } = useAuth();
  if (loading) return <FullPageLoader />;
  if (!profile) return <Navigate to="/login" replace />;
  const role = profile.user.role;
  if (role === "admin") return <Navigate to="/admin" replace />;
  if (role === "teacher") return <Navigate to="/teacher" replace />;
  return <Navigate to="/student" replace />;
}

function Protected({ roles, children }: { roles?: Role[]; children: React.ReactNode }) {
  const { profile, loading } = useAuth();
  if (loading) return <FullPageLoader />;
  if (!profile) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(profile.user.role as Role)) return <ForbiddenPage />;
  return <>{children}</>;
}

export function AppRoutes() {
  return (
    <Suspense fallback={<FullPageLoader />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route path="/" element={<Protected><AppLayout /></Protected>}>
          <Route index element={<HomeRedirect />} />

          <Route path="admin" element={<Protected roles={["admin"]}><AdminDashboard /></Protected>} />
          <Route path="teacher" element={<Protected roles={["teacher"]}><TeacherDashboard /></Protected>} />
          <Route path="student" element={<Protected roles={["student"]}><StudentDashboard /></Protected>} />

          {/* Students */}
          <Route path="students" element={<Protected roles={["admin"]}><StudentListPage /></Protected>} />
          <Route path="students/new" element={<Protected roles={["admin"]}><StudentFormPage /></Protected>} />
          <Route path="students/:id" element={<Protected roles={["admin"]}><StudentDetailPage /></Protected>} />
          <Route path="students/:id/edit" element={<Protected roles={["admin"]}><StudentFormPage /></Protected>} />

          {/* Teachers */}
          <Route path="teachers" element={<Protected roles={["admin"]}><TeacherListPage /></Protected>} />
          <Route path="teachers/new" element={<Protected roles={["admin"]}><TeacherFormPage /></Protected>} />
          <Route path="teachers/:id" element={<Protected roles={["admin"]}><TeacherDetailPage /></Protected>} />

          {/* Attendance */}
          <Route path="attendance/mark" element={<Protected roles={["teacher"]}><AttendanceMarkingPage /></Protected>} />
          <Route path="attendance" element={<Protected><AttendanceHistoryPage /></Protected>} />

          {/* Examinations & results */}
          <Route path="examinations" element={<Protected roles={["admin", "teacher"]}><ExaminationListPage /></Protected>} />
          <Route path="examinations/:id/marks" element={<Protected roles={["admin", "teacher"]}><MarksEntryPage /></Protected>} />
          <Route path="results" element={<Protected><ResultsPage /></Protected>} />

          {/* Fees */}
          <Route path="fees" element={<Protected roles={["admin"]}><FeeListPage /></Protected>} />
          <Route path="fees/:id" element={<Protected><InvoiceDetailPage /></Protected>} />
          <Route path="student/fees" element={<Protected roles={["student"]}><InvoiceDetailPage /></Protected>} />

          {/* Timetable, materials, notices, reports */}
          <Route path="timetable" element={<Protected><TimetablePage /></Protected>} />
          <Route path="materials" element={<Protected><MaterialsPage /></Protected>} />
          <Route path="notices" element={<Protected><NoticesPage /></Protected>} />
          <Route path="reports" element={<Protected roles={["admin", "teacher"]}><ReportsPage /></Protected>} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
