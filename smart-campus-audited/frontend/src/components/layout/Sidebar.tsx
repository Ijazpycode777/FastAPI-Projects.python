import { NavLink } from "react-router-dom";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV } from "./nav";
import type { Role } from "@/lib/constants";

interface SidebarProps {
  role: Role | undefined;
  open: boolean;
  onClose: () => void;
}

/** Primary navigation sidebar. Fixed on desktop, slide-in on mobile. */
export function Sidebar({ role, open, onClose }: SidebarProps) {
  const items = NAV.filter((n) => role && n.roles.includes(role));

  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-40 w-64 transform bg-navy text-white transition-transform lg:translate-x-0",
        open ? "translate-x-0" : "-translate-x-full"
      )}
    >
      <div className="flex h-16 items-center gap-2.5 px-5 border-b border-white/10">
        <div className="h-8 w-8 rounded-lg bg-indigo grid place-items-center font-bold text-sm">SC</div>
        <div className="leading-tight">
          <p className="font-bold text-sm">Smart Campus</p>
          <p className="text-[10px] text-white/60 uppercase tracking-wide">{role}</p>
        </div>
        <button className="ml-auto lg:hidden text-white/70" onClick={onClose} aria-label="Close menu">
          <X size={18} />
        </button>
      </div>
      <nav className="px-3 py-4 space-y-1 overflow-y-auto h-[calc(100%-4rem)]">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/admin" || item.to === "/teacher" || item.to === "/student"}
            onClick={onClose}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive ? "bg-indigo text-white" : "text-white/70 hover:bg-white/10 hover:text-white"
              )
            }
          >
            <item.icon size={18} />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
