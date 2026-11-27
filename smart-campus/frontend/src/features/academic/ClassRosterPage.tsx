import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Users, CalendarClock, Clock, Info } from "lucide-react";
import {
  PageHeader, Card, CardHeader, Badge, EmptyState, ErrorState, Skeleton,
} from "@/components/common";
import { DataTable } from "@/components/tables/DataTable";
import type { Column } from "@/components/tables/DataTable";
import { useClassRoster, useSections } from "@/features/academicQueries";
import { useAuth } from "@/hooks/useAuth";
import type { ClassRosterStudent, LiveStatus } from "@/types";

/** Visual distinction for the live timetable status. "Present" pulses to signal
 *  it is a live indicator (the class is in a scheduled lecture right now); "Off
 *  right now" is a calm neutral. Neither is attendance. */
function StatusBadge({ status }: { status: LiveStatus }) {
  if (status === "present") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-teal/10 px-2.5 py-1 text-xs font-medium text-teal">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal opacity-60" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-teal" />
        </span>
        Present
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-bg px-2.5 py-1 text-xs font-medium text-slate-muted">
      <span className="h-2 w-2 rounded-full bg-slate-muted" />
      Off right now
    </span>
  );
}

/**
 * Class roster with a live, timetable-based status indicator.
 *
 * Lists only students currently enrolled in the class (active enrolment —
 * promoted/transferred students are excluded server-side). Each student's
 * status is "Present" while their class/section is in a scheduled lecture right
 * now (server time, college timezone, holidays respected), else "Off right
 * now". The status is a live availability indicator, NOT attendance.
 *
 * The roster auto-refreshes: `useClassRoster` schedules a refetch at the next
 * lecture start/end boundary (computed from `lectures_today` + `server_now`) so
 * transitions are reflected promptly without polling every second, and falls
 * back to 60s when no transition is imminent so a long-open tab stays current.
 *
 * Backend enforces that a teacher can only open rosters for classes they are
 * assigned to (403 otherwise) — not merely hidden here.
 */
export function ClassRosterPage() {
  const { classId } = useParams<{ classId: string }>();
  const navigate = useNavigate();
  const { profile } = useAuth();
  const role = profile?.user.role;

  const [sectionId, setSectionId] = useState<string>("");
  const { data: sections } = useSections(classId);
  const { data: roster, isLoading, isError, refetch } = useClassRoster(classId, sectionId || undefined);

  const columns: Column<ClassRosterStudent>[] = useMemo(() => [
    { key: "roll_number", header: "Roll #", className: "whitespace-nowrap font-medium" },
    { key: "full_name", header: "Student", render: (s) => (
      <div className="min-w-0">
        <p className="font-medium text-ink truncate">{s.full_name}</p>
        <p className="text-xs text-slate-muted">{s.admission_number}</p>
      </div>
    ) },
    { key: "section_name", header: "Section", render: (s) => s.section_name ? <Badge>{s.section_name}</Badge> : <span className="text-slate-muted">—</span> },
    { key: "session_name", header: "Session", render: (s) => <span className="text-slate-muted">{s.session_name ?? "—"}</span> },
    { key: "live_status", header: "Status", render: (s) => <StatusBadge status={s.live_status} />, className: "whitespace-nowrap" },
  ], []);

  const presentCount = roster?.students.filter((s) => s.live_status === "present").length ?? 0;

  return (
    <div className="max-w-5xl">
      <PageHeader
        title={roster ? `${roster.class_name}` : "Class roster"}
        description={roster
          ? `${roster.program_name ?? "—"} · Year ${roster.year}${role === "teacher" ? " · one of your assigned classes" : ""}`
          : "Students currently enrolled in this class."}
        action={
          <button onClick={() => navigate("/classes")} className="btn-secondary">
            <ArrowLeft size={16} /> Back to classes
          </button>
        }
      />

      {/* Live status legend — explains the indicator is timetable-based, not attendance. */}
      <Card className="mb-4">
        <div className="flex items-start gap-3 p-4">
          <Info size={18} className="text-indigo mt-0.5 shrink-0" />
          <div className="text-sm text-slate-muted">
            <p className="text-ink font-medium">Live timetable status</p>
            <p className="mt-0.5">
              <span className="font-medium text-teal">Present</span> = the student's class/section is in a scheduled lecture right now.
              <span className="font-medium text-slate-muted"> Off right now</span> = no active lecture (before/after/between lectures, holidays, or no lecture that day).
              This is an availability indicator, not attendance — it never marks a student present in the attendance system.
            </p>
          </div>
        </div>
      </Card>

      {/* Section filter (only when the class has sections). */}
      {sections && sections.length > 0 && (
        <div className="mb-4 flex items-center gap-3 flex-wrap">
          <label className="text-sm text-slate-muted">Section:</label>
          <select
            value={sectionId} onChange={(e) => setSectionId(e.target.value)}
            className="input !w-auto"
          >
            <option value="">All sections</option>
            {sections.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          {roster && (
            <span className="text-xs text-slate-muted">
              {roster.students.length} student{roster.students.length === 1 ? "" : "s"} · {presentCount} present now
            </span>
          )}
        </div>
      )}

      {/* Roster table. */}
      {isError ? (
        <ErrorState
          message="Could not load the class roster."
          onRetry={() => refetch()}
        />
      ) : isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-10" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      ) : !roster || roster.students.length === 0 ? (
        <Card>
          <EmptyState
            icon={Users}
            title="No students enrolled"
            description="There are no currently-enrolled students in this class for the active academic session. Students who were promoted or transferred are not shown."
          />
        </Card>
      ) : (
        <DataTable
          columns={columns}
          rows={roster.students}
          rowKey={(s) => s.id}
        />
      )}

      {/* Today's lectures — schedule context for the live status. */}
      {!isError && roster && roster.lectures_today.length > 0 && (
        <Card className="mt-4">
          <CardHeader title="Today's lectures" subtitle="Scheduled for this class today — the source of the live status." />
          <div className="p-5">
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {roster.lectures_today.map((l, i) => (
                <div key={i} className="flex items-center gap-3 rounded-lg border border-slate-hairline px-3 py-2">
                  <Clock size={16} className="text-indigo shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-ink truncate">
                      {l.start_time}–{l.end_time}
                    </p>
                    <p className="text-xs text-slate-muted truncate">
                      {l.subject_name ?? "—"}{l.section_name ? ` · Sec ${l.section_name}` : " · all sections"}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Card>
      )}

      {!isError && roster && roster.lectures_today.length === 0 && (
        <Card className="mt-4">
          <div className="flex items-center gap-3 p-4">
            <CalendarClock size={18} className="text-slate-muted shrink-0" />
            <p className="text-sm text-slate-muted">
              No lectures scheduled for this class today — every student is <span className="font-medium text-slate-muted">Off right now</span>.
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}
