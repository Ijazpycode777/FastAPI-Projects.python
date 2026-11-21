import { useQuery } from "@tanstack/react-query";
import { http } from "@/lib/api";
import type { Page, Student } from "@/types";

export function useStudents(params: {
  q?: string; program_id?: string; class_id?: string; section_id?: string;
  session_id?: string; status?: string;
  sort?: string; order?: "asc" | "desc"; page?: number; page_size?: number;
}) {
  return useQuery({
    queryKey: ["students", params],
    queryFn: () => http.get<Page<Student>>("/students", params as Record<string, string | number | undefined>),
    placeholderData: (prev) => prev,
  });
}

export function useStudent(id: string | undefined) {
  return useQuery({ queryKey: ["student", id], queryFn: () => http.get<Student>(`/students/${id}`), enabled: !!id });
}
