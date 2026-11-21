import { useQuery } from "@tanstack/react-query";
import { http } from "@/lib/api";
import type { CampusShift, RollNumberScheme } from "@/types";

export function useShifts() {
  return useQuery({ queryKey: ["campus", "shifts"], queryFn: () => http.get<CampusShift[]>("/campus/shifts") });
}

export function useRollSchemes(shiftId?: string) {
  return useQuery({
    queryKey: ["campus", "roll-schemes", shiftId],
    queryFn: () => http.get<RollNumberScheme[]>("/campus/roll-schemes", shiftId ? { campus_shift_id: shiftId } : undefined),
  });
}
