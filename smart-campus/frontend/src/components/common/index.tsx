import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { STATUS_TONE } from "@/lib/constants";

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("card", className)}>{children}</div>;
}

export function CardHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-slate-border px-5 py-4">
      <div>
        <h3 className="font-semibold text-navy">{title}</h3>
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
        <h1 className="text-xl font-bold text-navy sm:text-2xl">{title}</h1>
        {description && <p className="text-sm text-slate-muted mt-1">{description}</p>}
      </div>
      {action && <div className="flex items-center gap-2">{action}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-slate-border/70", className)} />;
}

export function EmptyState({ icon: Icon, title, description, action }: { icon?: LucideIcon; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-6">
      {Icon && (
        <div className="h-12 w-12 rounded-xl bg-slate-bg grid place-items-center text-slate-muted mb-3">
          <Icon size={22} />
        </div>
      )}
      <p className="font-semibold text-navy">{title}</p>
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
      <div className="absolute inset-0 bg-navy/40" onClick={onClose} />
      <div className="relative w-full max-w-lg card animate-slideUp">
        <div className="flex items-center justify-between border-b border-slate-border px-5 py-3.5">
          <h3 className="font-semibold text-navy">{title}</h3>
          <button onClick={onClose} className="text-slate-muted hover:text-navy" aria-label="Close">✕</button>
        </div>
        <div className="px-5 py-4 max-h-[70vh] overflow-y-auto">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-slate-border px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}

export function StatCard({ label, value, hint, tone = "neutral", icon: Icon }: { label: string; value: number | string; hint?: string; tone?: string; icon?: LucideIcon }) {
  const toneText: Record<string, string> = { primary: "text-indigo", success: "text-teal", warning: "text-amber", danger: "text-rose", neutral: "text-navy" };
  const toneBg: Record<string, string> = { primary: "bg-indigo/10", success: "bg-teal/10", warning: "bg-amber/10", danger: "bg-rose/10", neutral: "bg-slate-bg" };
  return (
    <div className="stat-card">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-slate-muted uppercase tracking-wide">{label}</p>
        {Icon && <div className={`h-8 w-8 rounded-lg grid place-items-center ${toneBg[tone] ?? toneBg.neutral} ${toneText[tone] ?? toneText.neutral}`}><Icon size={16} /></div>}
      </div>
      <p className={`text-2xl font-bold ${toneText[tone] ?? toneText.neutral}`}>{value}</p>
      {hint && <p className="text-xs text-slate-muted">{hint}</p>}
    </div>
  );
}
