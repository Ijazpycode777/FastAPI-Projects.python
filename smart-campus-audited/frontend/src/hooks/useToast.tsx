import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

export type ToastTone = "success" | "error" | "info" | "warning";
export interface Toast { id: number; title: string; description?: string; tone: ToastTone; }

interface ToastContextValue {
  toasts: Toast[];
  push: (t: Omit<Toast, "id">) => void;
  dismiss: (id: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let counter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback((t: Omit<Toast, "id">) => {
    const id = ++counter;
    setToasts((prev) => [...prev, { ...t, id }]);
    setTimeout(() => dismiss(id), 4500);
  }, [dismiss]);

  return (
    <ToastContext.Provider value={{ toasts, push, dismiss }}>
      {children}
      <ToastViewport toasts={toasts} dismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return {
    success: (title: string, description?: string) => ctx.push({ title, description, tone: "success" }),
    error: (title: string, description?: string) => ctx.push({ title, description, tone: "error" }),
    info: (title: string, description?: string) => ctx.push({ title, description, tone: "info" }),
    warning: (title: string, description?: string) => ctx.push({ title, description, tone: "warning" }),
  };
}

const TONE_STYLES: Record<ToastTone, string> = {
  success: "border-teal/30 bg-white",
  error: "border-rose/30 bg-white",
  info: "border-indigo/30 bg-white",
  warning: "border-amber/30 bg-white",
};
const TONE_DOT: Record<ToastTone, string> = {
  success: "bg-teal", error: "bg-rose", info: "bg-indigo", warning: "bg-amber",
};

function ToastViewport({ toasts, dismiss }: { toasts: Toast[]; dismiss: (id: number) => void }) {
  return (
    <div className="fixed top-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          role="alert"
          className={`flex items-start gap-3 rounded-xl border ${TONE_STYLES[t.tone]} shadow-pop p-3.5 animate-slideUp`}
        >
          <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${TONE_DOT[t.tone]}`} />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-navy">{t.title}</p>
            {t.description && <p className="mt-0.5 text-xs text-slate-muted">{t.description}</p>}
          </div>
          <button onClick={() => dismiss(t.id)} className="text-slate-muted hover:text-navy text-sm" aria-label="Dismiss">
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
