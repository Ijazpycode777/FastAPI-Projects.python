import { useQuery } from "@tanstack/react-query";
import { http } from "@/lib/api";
import type { AcademicSession, Program, ClassLevel, Section, Subject, Department } from "@/types";

export const useSessions = () => useQuery({ queryKey: ["sessions"], queryFn: () => http.get<AcademicSession[]>("/sessions") });
export const usePrograms = () => useQuery({ queryKey: ["programs"], queryFn: () => http.get<Program[]>("/programs") });
export const useClasses = (programId?: string) => useQuery({ queryKey: ["classes", programId], queryFn: () => http.get<ClassLevel[]>("/classes", { program_id: programId }), enabled: !!programId });
export const useSections = (classId?: string) => useQuery({ queryKey: ["sections", classId], queryFn: () => http.get<Section[]>("/sections", { class_level_id: classId }), enabled: !!classId });
export const useSubjects = (programId?: string) => useQuery({ queryKey: ["subjects", programId], queryFn: () => http.get<Subject[]>("/subjects", { program_id: programId }), enabled: !!programId });
// Departments: read-only list of the five fixed, migration-seeded rows.
export const useDepartments = () => useQuery({ queryKey: ["departments"], queryFn: () => http.get<Department[]>("/departments") });
