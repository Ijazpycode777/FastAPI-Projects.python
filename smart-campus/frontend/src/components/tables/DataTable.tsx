import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/common";
import { ChevronDown, ChevronUp } from "lucide-react";

export interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
  sortable?: boolean;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  loading?: boolean;
  onRowClick?: (row: T) => void;
  emptyState?: ReactNode;
  sortKey?: string;
  sortDir?: "asc" | "desc";
  onSort?: (key: string) => void;
}

export function DataTable<T>({
  columns, rows, rowKey, loading, onRowClick, emptyState, sortKey, sortDir, onSort,
}: DataTableProps<T>) {
  if (loading) {
    return (
      <div className="card overflow-hidden">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex gap-4 px-4 py-3 border-b border-slate-border last:border-0">
            {columns.map((c) => <Skeleton key={c.key} className="h-4 flex-1" />)}
          </div>
        ))}
      </div>
    );
  }

  if (rows.length === 0) {
    return <div className="card">{emptyState ?? <p className="px-4 py-10 text-center text-sm text-slate-muted">No records found.</p>}</div>;
  }

  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-border bg-slate-bg/60">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn("px-4 py-3 text-left font-semibold text-navy whitespace-nowrap", col.className)}
                >
                  {col.sortable && onSort ? (
                    <button onClick={() => onSort(col.key)} className="inline-flex items-center gap-1 hover:text-indigo">
                      {col.header}
                      {sortKey === col.key && (sortDir === "asc" ? <ChevronUp size={14} /> : <ChevronDown size={14} />)}
                    </button>
                  ) : (
                    col.header
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={rowKey(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={cn("border-b border-slate-border last:border-0 transition-colors", onRowClick && "cursor-pointer hover:bg-slate-bg/60")}
              >
                {columns.map((col) => (
                  <td key={col.key} className={cn("px-4 py-3 text-navy align-middle", col.className)}>
                    {col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key] ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
