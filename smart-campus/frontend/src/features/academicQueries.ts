import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { http } from "@/lib/api";
import type { AcademicSession, Program, ClassLevel, Section, Subject, Department, ClassDistribution, ClassRoster } from "@/types";

// ---------------- Reads ----------------
export const useSessions = () => useQuery({ queryKey: ["sessions"], queryFn: () => http.get<AcademicSession[]>("/sessions") });
export const usePrograms = () => useQuery({ queryKey: ["programs"], queryFn: () => http.get<Program[]>("/programs") });
export const useClasses = (programId?: string) => useQuery({ queryKey: ["classes", programId], queryFn: () => http.get<ClassLevel[]>("/classes", { program_id: programId }), enabled: !!programId });
export const useSections = (classId?: string) => useQuery({ queryKey: ["sections", classId], queryFn: () => http.get<Section[]>("/sections", { class_level_id: classId }), enabled: !!classId });
export const useSubjects = (programId?: string) => useQuery({ queryKey: ["subjects", programId], queryFn: () => http.get<Subject[]>("/subjects", { program_id: programId }), enabled: !!programId });
/** All subjects, unfiltered — for the Subjects management section. */
export const useAllSubjects = () => useQuery({ queryKey: ["subjects", "all"], queryFn: () => http.get<Subject[]>("/subjects") });
// Departments: read-only list of the five fixed, migration-seeded rows.
export const useDepartments = () => useQuery({ queryKey: ["departments"], queryFn: () => http.get<Department[]>("/departments") });

/** Aggregated classes view for the Classes Distribution admin page. */
export const useClassDistribution = () =>
  useQuery({ queryKey: ["classes", "distribution"], queryFn: () => http.get<ClassDistribution[]>("/classes/distribution") });

/** Role-aware class listing for the roster feature. Admin: all classes;
 *  teacher: only assigned classes. Same ClassDistribution shape as the admin
 *  management view, so one listing component serves both roles. */
export const useClassRosterList = () =>
  useQuery({ queryKey: ["classes", "rosters"], queryFn: () => http.get<ClassDistribution[]>("/classes/rosters") });

/**
 * Compute the refetch interval for the roster so the live status updates
 * promptly at lecture start/end without polling every second.
 *
 * The backend returns `lectures_today` (today's start/end times for the class)
 * and `server_now` (ISO in the college timezone). We find the next boundary
 * strictly after `server_now` and refetch just past it. If no more transitions
 * are due today, fall back to 60s so a long-open tab still crosses midnight and
 * picks up the next day's timetable. The interval is clamped to [3s, 60s].
 */
export function computeRosterRefetchMs(data: ClassRoster | undefined): number | false {
  if (!data?.server_now) return 30_000;
  const now = Date.parse(data.server_now);
  if (Number.isNaN(now)) return 30_000;
  // server_now is "YYYY-MM-DDTHH:MM:SS+HH:MM"; reuse its date + offset so the
  // composed lecture timestamps share the college timezone instead of the
  // browser's local zone.
  const day = data.server_now.slice(0, 10);
  const offset = data.server_now.slice(19) || "+00:00";
  let next = Infinity;
  for (const l of data.lectures_today) {
    const start = Date.parse(`${day}T${l.start_time}:00${offset}`);
    const end = Date.parse(`${day}T${l.end_time}:00${offset}`);
    if (!Number.isNaN(start) && start > now) next = Math.min(next, start - now);
    if (!Number.isNaN(end) && end > now) next = Math.min(next, end - now);
  }
  if (!Number.isFinite(next)) return 60_000;
  // +1s grace past the boundary so the server has flipped the status.
  return Math.min(60_000, Math.max(3_000, next + 1_000));
}

/** Class roster with live timetable status. Auto-refreshes at the next lecture
 *  transition (computed from lectures_today + server_now) so an open tab stays
 *  current without per-second polling. */
export function useClassRoster(classId?: string, sectionId?: string) {
  return useQuery({
    queryKey: ["classes", "roster", classId, sectionId],
    queryFn: () => http.get<ClassRoster>(`/classes/${classId}/roster`, { section_id: sectionId }),
    enabled: !!classId,
    refetchInterval: (query) => computeRosterRefetchMs(query.state.data),
    refetchOnWindowFocus: true,
  });
}

// ---------------- Mutations ----------------
// Centralizes cache invalidation: every academic write touches the caches the
// distribution view + the student-form dropdowns read from, so they all stay in
// sync. Callers handle their own toasts + read mutation.error for the message.
function useAcademicMutation<I, T>(mutationFn: (input: I) => Promise<T>) {
  const qc = useQueryClient();
  return useMutation<T, Error, I>({
    mutationFn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["classes"] });
      qc.invalidateQueries({ queryKey: ["programs"] });
      qc.invalidateQueries({ queryKey: ["sections"] });
      qc.invalidateQueries({ queryKey: ["subjects"] });
      qc.invalidateQueries({ queryKey: ["sessions"] });
    },
  });
}

// Programs
export function useCreateProgram() {
  return useAcademicMutation<{ code: string; name: string; description?: string | null }, Program>(
    (v) => http.post<Program>("/programs", v),
  );
}
export function useUpdateProgram() {
  return useAcademicMutation<{ id: string; code?: string; name?: string; description?: string | null }, Program>(
    ({ id, ...v }) => http.patch<Program>(`/programs/${id}`, v),
  );
}
export function useDeleteProgram() {
  return useAcademicMutation<string, unknown>((id) => http.del(`/programs/${id}`));
}

// Classes
export function useCreateClass() {
  return useAcademicMutation<{ program_id: string; name: string; year: number }, ClassLevel>(
    (v) => http.post<ClassLevel>("/classes", v),
  );
}
export function useUpdateClass() {
  return useAcademicMutation<{ id: string; name?: string; year?: number }, ClassLevel>(
    ({ id, ...v }) => http.patch<ClassLevel>(`/classes/${id}`, v),
  );
}
export function useDeleteClass() {
  return useAcademicMutation<string, unknown>((id) => http.del(`/classes/${id}`));
}

// Sections
export function useCreateSection() {
  return useAcademicMutation<{ class_level_id: string; name: string; capacity: number }, Section>(
    (v) => http.post<Section>("/sections", v),
  );
}
export function useUpdateSection() {
  return useAcademicMutation<{ id: string; name?: string; capacity?: number }, Section>(
    ({ id, ...v }) => http.patch<Section>(`/sections/${id}`, v),
  );
}
export function useDeleteSection() {
  return useAcademicMutation<string, unknown>((id) => http.del(`/sections/${id}`));
}

// Subjects
export function useCreateSubject() {
  return useAcademicMutation<{ program_id: string; code: string; name: string; theory_marks?: number; practical_marks?: number }, Subject>(
    (v) => http.post<Subject>("/subjects", v),
  );
}
export function useUpdateSubject() {
  return useAcademicMutation<{ id: string; code?: string; name?: string; theory_marks?: number; practical_marks?: number }, Subject>(
    ({ id, ...v }) => http.patch<Subject>(`/subjects/${id}`, v),
  );
}
export function useDeleteSubject() {
  return useAcademicMutation<string, unknown>((id) => http.del(`/subjects/${id}`));
}

// Sessions (academic years) — create only.
export function useCreateSession() {
  return useAcademicMutation<{ name: string; start_date: string; end_date: string; is_active: boolean }, AcademicSession>(
    (v) => http.post<AcademicSession>("/sessions", v),
  );
}
