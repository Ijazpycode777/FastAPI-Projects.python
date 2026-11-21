import { useLocation, useNavigate } from "react-router-dom";
import { LogOut, Menu, Bell } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { initials } from "@/lib/utils";

interface TopbarProps {
  onOpenMenu: () => void;
}

/** Capitalize each path segment for a polished breadcrumb title. */
function pageTitle(pathname: string): string {
  if (pathname === "/" ) return "Dashboard";
  const segs = pathname.split("/").filter(Boolean);
  return segs.map((s) => s.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())).join("  /  ");
}

/** Sticky application header — polished, keeps breadcrumb + notifications + account. */
export function Topbar({ onOpenMenu }: TopbarProps) {
  const { profile, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-border bg-white/85 backdrop-blur-md px-4 lg:px-8">
      <button className="lg:hidden text-ink hover:text-indigo" onClick={onOpenMenu} aria-label="Open menu">
        <Menu size={22} />
      </button>
      <h2 className="text-[15px] font-semibold text-ink truncate">{pageTitle(location.pathname)}</h2>
      <div className="ml-auto flex items-center gap-3">
        <button className="relative text-slate-muted hover:text-ink transition-colors" aria-label="Notifications">
          <Bell size={20} />
          <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-rose ring-2 ring-white" />
        </button>
        <div className="flex items-center gap-2.5 pl-1">
          <div className="h-9 w-9 rounded-full grid place-items-center text-xs font-bold text-white bg-gradient-to-br from-indigo to-violet ring-2 ring-white shadow-glow">
            {profile ? initials(profile.user.full_name) : "?"}
          </div>
          <div className="hidden sm:block leading-tight">
            <p className="text-[13px] font-semibold text-ink">{profile?.user.full_name}</p>
            <p className="text-[11px] text-slate-muted truncate max-w-[180px]">{profile?.user.email}</p>
          </div>
          <button onClick={handleLogout} className="btn-ghost !px-2" aria-label="Log out" title="Log out">
            <LogOut size={18} />
          </button>
        </div>
      </div>
    </header>
  );
}
