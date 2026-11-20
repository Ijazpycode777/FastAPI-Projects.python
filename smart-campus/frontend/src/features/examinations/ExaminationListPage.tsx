import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, FileText } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader, Badge, EmptyState, ErrorState } from "@/components/common";
import { DataTable, type Column } from "@/components/tables/DataTable";
import { http } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { Examination } from "@/types";
import { formatDate } from "@/lib/utils";

export function ExaminationListPage() {
  const navigate = useNavigate();
  const { profile } = useAuth();
  const [status] = useState<string | undefined>(undefined);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["examinations", status],
    queryFn: () => http.get<Examination[]>("/examinations", { status }),
  });

  const columns: Column<Examination>[] = [
    { key: "name", header: "Name", render: (e) => <span className="font-medium text-navy">{e.name}</span> },
    { key: "exam_type", header: "Type", render: (e) => <Badge>{e.exam_type.replace("_", " ")}</Badge> },
    { key: "exam_date", header: "Date", render: (e) => formatDate(e.exam_date) },
    { key: "max_marks", header: "Max" },
    { key: "passing_marks", header: "Pass" },
    { key: "status", header: "Status", render: (e) => <Badge status={e.status}>{e.status}</Badge> },
    { key: "_action", header: "", render: (e) => <button onClick={(ev) => { ev.stopPropagation(); navigate(`/examinations/${e.id}/marks`); }} className="text-xs text-indigo font-medium hover:underline">Marks →</button> },
  ];

  return (
    <div>
      <PageHeader title="Examinations" description="Create and manage examinations for your subjects."
        action={profile?.user.role === "admin" ? <button onClick={() => navigate("/examinations/new")} className="btn-primary"><Plus size={16} /> New Exam</button> : undefined} />
      {isError ? <ErrorState message="Could not load examinations." onRetry={() => refetch()} /> : (
        <DataTable columns={columns} rows={data ?? []} rowKey={(e) => e.id} loading={isLoading}
          onRowClick={(e) => navigate(`/examinations/${e.id}/marks`)}
          emptyState={<EmptyState icon={FileText} title="No examinations yet" description="Create an examination to enter marks." />} />
      )}
    </div>
  );
}
