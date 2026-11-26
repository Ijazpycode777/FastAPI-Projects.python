import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { http } from "@/lib/api";
import type { AcademicSession, Program, ClassLevel, Section, Subject, Department, ClassDistribution } from "@/types";

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
