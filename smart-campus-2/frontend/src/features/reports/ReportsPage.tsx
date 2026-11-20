import { BarChart3, FileSpreadsheet, FileText } from "lucide-react";
import { PageHeader, Card, CardHeader } from "@/components/common";
import { API_BASE } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";

interface ReportLink { label: string; description: string; href: string; icon: typeof FileText; tone: string; }

export function ReportsPage() {
  const { profile } = useAuth();
  const role = profile?.user.role;

  const adminReports: ReportLink[] = [
    { label: "Student enrolment (Excel)", description: "All students with program, class and status.", href: `${API_BASE}/reports/students.xlsx`, icon: FileSpreadsheet, tone: "text-teal" },
    { label: "Fee statement (PDF)", description: "Per-student fee statement with outstanding balance.", href: `${API_BASE}/reports/fees/placeholder.pdf`, icon: FileText, tone: "text-indigo" },
  ];
  const teacherReports: ReportLink[] = [
    { label: "Class attendance (Excel)", description: "Attendance percentage per student for a class.", href: `${API_BASE}/reports/attendance/class/placeholder.xlsx`, icon: FileSpreadsheet, tone: "text-teal" },
  ];

  const reports = role === "admin" ? [...adminReports, ...teacherReports] : teacherReports;

  return (
    <div>
      <PageHeader title="Reports & Exports" description="Generate Excel and PDF exports from live, authorized database records." />
      <div className="grid sm:grid-cols-2 gap-4">
        {reports.map((r) => (
          <Card key={r.label} className="p-5 flex items-start gap-4">
            <div className={`h-11 w-11 rounded-lg bg-slate-bg grid place-items-center ${r.tone}`}><r.icon size={20} /></div>
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-navy">{r.label}</p>
              <p className="text-sm text-slate-muted mt-0.5">{r.description}</p>
            </div>
            <a href={r.href} target="_blank" rel="noreferrer" className="btn-secondary !py-1.5 shrink-0">Export</a>
          </Card>
        ))}
      </div>

      <Card className="mt-4">
        <CardHeader title="About exports" />
        <div className="p-5 text-sm text-slate-muted space-y-2">
          <p className="flex items-start gap-2"><BarChart3 size={16} className="text-indigo mt-0.5 shrink-0" /> Every export is generated on demand from the live database — values shown reflect the current authorized records for your role.</p>
          <p>Receipts and result sheets are also available directly from the relevant invoice or examination page.</p>
        </div>
      </Card>
    </div>
  );
}
