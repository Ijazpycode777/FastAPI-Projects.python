import { Outlet } from "react-router-dom";
import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import type { Role } from "@/lib/constants";

/**
 * Application shell: sidebar + topbar + routed outlet.
 * Layout sub-components live in `components/layout/`; this wrapper lives in
 * `layouts/` per the repository structure.
 */
export function AppLayout() {
  const { profile } = useAuth();
  const [open, setOpen] = useState(false);
  const role = profile?.user.role as Role | undefined;

  return (
    <div className="min-h-full flex bg-slate-bg">
      <Sidebar role={role} open={open} onClose={() => setOpen(false)} />
      {open && <div className="fixed inset-0 z-30 bg-navy/50 backdrop-blur-sm lg:hidden" onClick={() => setOpen(false)} />}
      <div className="flex-1 lg:pl-[280px] min-w-0">
        <Topbar onOpenMenu={() => setOpen(true)} />
        <main className="px-4 lg:px-8 py-6 max-w-[1400px] mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
