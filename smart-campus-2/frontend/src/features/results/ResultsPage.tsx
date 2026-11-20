import { useQuery } from "@tanstack/react-query";
import { ClipboardList } from "lucide-react";
import { PageHeader, Card, CardHeader, Badge, EmptyState, ErrorState } from "@/components/common";
import { DataTable, type Column } from "@/components/tables/DataTable";
import { http } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { StudentMark, Examination } from "@/types";
import { formatDate } from "@/lib/utils";

export function ResultsPage() {
  const { profile } = useAuth();
  const role = profile?.user.role;

  const exams = useQuery({ queryKey: ["exams-for-results"], queryFn: () => http.get<Examination[]>("/examinations", { status: "published" }) });

  // For students, show their own marks; for staff, list published exams.
  const marks = useQuery({
    queryKey: ["my-marks", profile?.student?.id],
    queryFn: () => http.get<StudentMark[]>("/results/me").catch(() => [] as StudentMark[]),
    enabled: role === "student",
  });

  const columns: Column<StudentMark>[] = [
    { key: "subject_id", header: "Subject", render: (m) => <span className="text-slate-muted">{m.subject_id.slice(0, 8)}</span> },
    { key: "marks_obtained", header: "Marks" },
    { key: "percentage", header: "%", render: (m) => m.percentage ? `${m.percentage}%` : "—" },
    { key: "grade", header: "Grade", render: (m) => m.grade ? <Badge>{m.grade}</Badge> : "—" },
    { key: "is_pass", header: "Result", render: (m) => m.is_pass === null ? "—" : m.is_pass ? <span className="text-teal font-medium">Pass</span> : <span className="text-rose font-medium">Fail</span> },
    { key: "status", header: "Status", render: (m) => <Badge status={m.status}>{m.status}</Badge> },
  ];

  if (exams.isError) return <ErrorState message="Could not load results." onRetry={() => exams.refetch()} />;

  return (
    <div>
      <PageHeader title="Results" description={role === "student" ? "Your examination results across subjects." : "Published and finalized examination results."} />
      <Card>
        <CardHeader title={role === "student" ? "Your marks" : "Examinations"} />
        {role === "student" ? (
          <DataTable columns={columns} rows={marks.data ?? []} rowKey={(m) => m.id} loading={marks.isLoading}
            emptyState={<EmptyState icon={ClipboardList} title="No results published yet" />} />
        ) : (
          <DataTable
            columns={[
              { key: "name", header: "Examination", render: (e) => <span className="font-medium text-navy">{e.name}</span> },
              { key: "exam_type", header: "Type", render: (e) => <Badge>{e.exam_type.replace("_", " ")}</Badge> },
              { key: "exam_date", header: "Date", render: (e) => formatDate(e.exam_date) },
              { key: "status", header: "Status", render: (e) => <Badge status={e.status}>{e.status}</Badge> },
            ]}
            rows={exams.data ?? []} rowKey={(e) => e.id} loading={exams.isLoading}
            emptyState={<EmptyState icon={ClipboardList} title="No published examinations" />} />
        )}
      </Card>
    </div>
  );
}
