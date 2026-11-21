import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { STATUS_TONE } from "@/lib/constants";

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("card", className)}>{children}</div>;
}

export function CardHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-slate-hairline px-5 py-4">
      <div>
        <h3 className="font-semibold text-[15px] text-ink">{title}</h3>
        {subtitle && <p className="text-xs text-slate-muted mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function Badge({ status, children }: { status?: string; children: ReactNode }) {
  const tone = status ? STATUS_TONE[status] ?? "bg-slate-border text-slate-muted" : "bg-slate-border text-slate-muted";
  return <span className={cn("badge", tone)}>{children}</span>;
}

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-6">
      <div>
        <h1 className="text-xl font-extrabold tracking-tight text-ink sm:text-2xl">{title}</h1>
        {description && <p className="text-sm text-slate-muted mt-1">{description}</p>}
      </div>
      {action && <div className="flex items-center gap-2">{action}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-xl bg-slate-border/70", className)} />;
}

export function EmptyState({ icon: Icon, title, description, action }: { icon?: LucideIcon; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-6">
      {Icon && (
        <div className="h-14 w-14 rounded-2xl grid place-items-center mb-3 bg-indigo/10 text-indigo">
          <Icon size={24} />
        </div>
      )}
      <p className="font-semibold text-ink">{title}</p>
      {description && <p className="text-sm text-slate-muted mt-1 max-w-sm">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-10 px-6">
      <p className="font-semibold text-rose">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn-secondary mt-4">Retry</button>
      )}
    </div>
  );
}

export function Pagination({ page, totalPages, onPage }: { page: number; totalPages: number; onPage: (p: number) => void }) {
  if (totalPages <= 1) return null;
  const pages = Array.from({ length: totalPages }, (_, i) => i + 1).filter(
    (p) => p === 1 || p === totalPages || Math.abs(p - page) <= 1
  );
  return (
    <div className="flex items-center justify-center gap-1 mt-4">
      <button className="btn-ghost !px-2.5" disabled={page === 1} onClick={() => onPage(page - 1)}>Prev</button>
      {pages.map((p, i) => (
        <span key={p} className="flex items-center">
          {i > 0 && p - pages[i - 1] > 1 && <span className="px-1 text-slate-muted">…</span>}
          <button
            onClick={() => onPage(p)}
            className={cn("h-8 w-8 rounded-md text-sm font-medium", p === page ? "bg-indigo text-white" : "text-slate-muted hover:bg-slate-bg")}
          >
            {p}
          </button>
        </span>
      ))}
      <button className="btn-ghost !px-2.5" disabled={page === totalPages} onClick={() => onPage(page + 1)}>Next</button>
    </div>
  );
}

export function Modal({ open, onClose, title, children, footer }: { open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-navy/50 backdrop-blur-sm animate-fadeIn" onClick={onClose} />
      <div className="relative w-full max-w-lg card animate-slideUp">
        <div className="flex items-center justify-between border-b border-slate-hairline px-5 py-3.5">
          <h3 className="font-semibold text-[15px] text-ink">{title}</h3>
          <button onClick={onClose} className="grid h-8 w-8 place-items-center rounded-lg text-slate-muted hover:bg-slate-bg hover:text-ink" aria-label="Close">✕</button>
        </div>
        <div className="px-5 py-4 max-h-[70vh] overflow-y-auto">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-slate-hairline px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}

export function StatCard({ label, value, hint, tone = "neutral", icon: Icon }: { label: string; value: number | string; hint?: string; tone?: string; icon?: LucideIcon }) {
  // Pastel icon tile per tone — the signature premium KPI styling.
  const tile: Record<string, string> = {
    primary: "bg-indigo/10 text-indigo",
    success: "bg-teal/10 text-teal",
    warning: "bg-amber/15 text-amber",
    danger: "bg-rose/10 text-rose",
    neutral: "bg-slate-bg text-slate-muted",
  };
  const trendUp = hint?.trim().startsWith("+");
  const trendDown = hint?.trim().startsWith("-");
  return (
    <div className="stat-card card-hover min-w-0">
      <div className="flex items-center gap-3">
        {Icon && (
          <div className={`h-11 w-11 rounded-xl grid place-items-center shrink-0 ${tile[tone] ?? tile.neutral}`}>
            <Icon size={20} />
          </div>
        )}
        <div className="min-w-0">
          <p className="text-xl sm:text-2xl font-extrabold leading-none tracking-tight text-ink truncate">{value}</p>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-muted mt-1.5 truncate">{label}</p>
        </div>
      </div>
      {hint && (
        <p className={`text-xs font-medium ${trendUp ? "text-teal" : trendDown ? "text-rose" : "text-slate-muted"}`}>
          {hint}
        </p>
      )}
    </div>
  );
}

/** Premium gradient welcome banner for dashboard headers. Visual only — no actions. */
export function HeroBanner({ title, subtitle, emoji, children }: { title: string; subtitle?: string; emoji?: string; children?: ReactNode }) {
  return (
    <div className="hero-gradient relative overflow-hidden rounded-2xl p-6 text-white shadow-glow animate-slideUp mb-6">
      <div className="absolute -right-10 -top-10 h-36 w-36 rounded-full bg-white/10" />
      <div className="absolute -right-4 bottom-0 h-24 w-24 rounded-full bg-white/5" />
      <div className="relative">
        {subtitle && <p className="text-sm font-medium text-white/85">{subtitle}</p>}
        <h2 className="mt-1 text-2xl font-extrabold tracking-tight sm:text-[26px]">
          {emoji && <span className="mr-1.5">{emoji}</span>}{title}
        </h2>
        {children && <div className="mt-2 text-sm text-white/90">{children}</div>}
      </div>
    </div>
  );
}
