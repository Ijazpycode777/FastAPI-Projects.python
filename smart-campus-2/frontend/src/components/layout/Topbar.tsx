import { useLocation, useNavigate } from "react-router-dom";
import { LogOut, Menu, Bell } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { initials } from "@/lib/utils";

interface TopbarProps {
  onOpenMenu: () => void;
}

/** Sticky application header with breadcrumb, notifications and account actions. */
export function Topbar({ onOpenMenu }: TopbarProps) {
  const { profile, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-border bg-white/90 backdrop-blur px-4 lg:px-8">
      <button className="lg:hidden text-navy" onClick={onOpenMenu} aria-label="Open menu">
        <Menu size={22} />
      </button>
      <div className="hidden sm:block text-sm text-slate-muted">
        {location.pathname === "/" ? "Dashboard" : location.pathname.split("/").filter(Boolean).join(" / ")}
      </div>
      <div className="ml-auto flex items-center gap-3">
        <button className="relative text-slate-muted hover:text-navy" aria-label="Notifications">
          <Bell size={20} />
          <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-rose" />
        </button>
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-full bg-indigo/10 text-indigo grid place-items-center text-xs font-bold">
            {profile ? initials(profile.user.full_name) : "?"}
          </div>
          <div className="hidden sm:block leading-tight">
            <p className="text-sm font-semibold text-navy">{profile?.user.full_name}</p>
            <p className="text-[11px] text-slate-muted">{profile?.user.email}</p>
          </div>
          <button onClick={handleLogout} className="btn-ghost !px-2" aria-label="Log out" title="Log out">
            <LogOut size={18} />
          </button>
        </div>
      </div>
    </header>
  );
}
