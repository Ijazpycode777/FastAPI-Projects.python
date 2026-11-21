import { NavLink } from "react-router-dom";
import { GraduationCap, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV, NAV_GROUP_ORDER } from "./nav";
import type { Role } from "@/lib/constants";

interface SidebarProps {
  role: Role | undefined;
  open: boolean;
  onClose: () => void;
}

/** Primary navigation sidebar — premium dark navy, inset & rounded on desktop. */
export function Sidebar({ role, open, onClose }: SidebarProps) {
  const items = NAV.filter((n) => role && n.roles.includes(role));
  const grouped = NAV_GROUP_ORDER.map((g) => ({ group: g, items: items.filter((i) => i.group === g) })).filter((g) => g.items.length);

  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-40 w-64 transform text-white transition-transform lg:translate-x-0",
        // Desktop: inset + rounded for the premium "floating panel" look.
        "lg:top-3 lg:bottom-3 lg:left-3 lg:rounded-2xl lg:shadow-pop lg:border lg:border-white/5",
        "bg-navy-gradient",
        open ? "translate-x-0" : "-translate-x-full"
      )}
      aria-label="Primary navigation"
    >
      <div className="flex h-16 items-center gap-2.5 px-5 border-b border-white/10">
        <div className="h-9 w-9 rounded-xl grid place-items-center shadow-glow bg-gradient-to-br from-indigo to-violet">
          <GraduationCap size={20} className="text-white" />
        </div>
        <div className="leading-tight">
          <p className="font-bold text-[15px] tracking-tight">Smart Campus</p>
          <p className="text-[10px] text-white/45 uppercase tracking-wider">{role} workspace</p>
        </div>
        <button className="ml-auto lg:hidden text-white/70 hover:text-white" onClick={onClose} aria-label="Close menu">
          <X size={18} />
        </button>
      </div>
      <nav className="px-3 py-4 overflow-y-auto h-[calc(100%-9rem)]">
        {grouped.map(({ group, items: gitems }) => (
          <div key={group} className="mb-4">
            <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-white/30">{group}</p>
            <div className="space-y-0.5">
              {gitems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/admin" || item.to === "/teacher" || item.to === "/student"}
                  onClick={onClose}
                  className={({ isActive }) =>
                    cn(
                      "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-all",
                      isActive
                        ? "bg-gradient-to-r from-indigo to-violet text-white shadow-glow"
                        : "text-white/55 hover:bg-white/5 hover:text-white"
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      <item.icon size={18} className={cn("shrink-0 transition-colors", isActive ? "text-white" : "text-white/45 group-hover:text-white")} />
                      <span className="truncate">{item.label}</span>
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>
      {/* Subtle footer marking — no actions, purely informational. */}
      <div className="absolute inset-x-3 bottom-3 rounded-xl border border-white/10 bg-white/5 px-4 py-3">
        <p className="text-[13px] font-semibold text-white">🎓 Smart Campus</p>
        <p className="text-[11px] text-white/45 mt-0.5">Education Suite · v1.0</p>
      </div>
    </aside>
  );
}
