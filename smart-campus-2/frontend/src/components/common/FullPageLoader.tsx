export function FullPageLoader() {
  return (
    <div className="min-h-full grid place-items-center bg-slate-bg">
      <div className="flex flex-col items-center gap-3">
        <div className="h-10 w-10 rounded-lg bg-indigo grid place-items-center font-bold text-white animate-pulse">SC</div>
        <div className="h-1.5 w-32 overflow-hidden rounded-full bg-slate-border">
          <div className="h-full w-1/2 bg-indigo animate-[fadeIn_1s_ease-in-out_infinite]" />
        </div>
        <p className="text-xs text-slate-muted">Loading…</p>
      </div>
    </div>
  );
}
