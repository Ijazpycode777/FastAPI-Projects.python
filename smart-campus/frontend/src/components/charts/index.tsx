import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  BarChart, Bar, PieChart, Pie, Cell, AreaChart, Area,
} from "recharts";

// Premium ERP palette — navy→deep-purple primary with refined SaaS accents,
// aligned to the Smart Campus design tokens.
export const CHART_COLORS = ["#6041C8", "#18A879", "#E8A23A", "#E05262", "#301078", "#3999D6"];

// Attendance donut segment colours — present=green, absent=red, leave=grey.
export const ATTENDANCE_COLORS = {
  present: "#18A879", // green
  absent: "#E05262",  // red
  leave: "#9CA0B5",   // grey
} as const;

const axisStyle = { fontSize: 11, fill: "#73758A" };
const gridStroke = "#EEF0F7";
const tooltipStyle = { borderRadius: 12, border: `1px solid #E8E8F0`, fontSize: 12, boxShadow: "0 8px 24px rgba(33,20,91,0.10)" };

interface SeriesProps { data: { label: string; value: number }[]; color?: string; height?: number; }

export function TrendLineChart({ data, color = "#6041C8", height = 240 }: SeriesProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
        <XAxis dataKey="label" tick={axisStyle} tickLine={false} axisLine={false} />
        <YAxis tick={axisStyle} tickLine={false} axisLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 5 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function CategoryBarChart({ data, height = 240 }: SeriesProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
        <XAxis dataKey="label" tick={axisStyle} tickLine={false} axisLine={false} />
        <YAxis tick={axisStyle} tickLine={false} axisLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Bar dataKey="value" radius={[6, 6, 0, 0]}>
          {data.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// Horizontal bars — for long class/section labels (admin class comparison,
// teacher class distribution).
export function HorizontalBarChart({ data, height = 240, color = "#6041C8" }: SeriesProps & { color?: string }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart layout="vertical" data={data} margin={{ top: 4, right: 16, bottom: 4, left: 24 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} horizontal={false} />
        <XAxis type="number" tick={axisStyle} tickLine={false} axisLine={false} />
        <YAxis type="category" dataKey="label" tick={axisStyle} tickLine={false} axisLine={false} width={120} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#F6F7FC" }} />
        <Bar dataKey="value" radius={[0, 6, 6, 0]} fill={color} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function DistributionDonut({ data, height = 240 }: { data: { label: string; value: number }[]; height?: number }) {
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="label" innerRadius={55} outerRadius={85} paddingAngle={2} stroke="none">
          {data.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
        </Pie>
        <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => `${v} (${Math.round((v / total) * 100)}%)`} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function TrendAreaChart({ data, color = "#18A879", height = 240 }: SeriesProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
        <defs>
          <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.25} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
        <XAxis dataKey="label" tick={axisStyle} tickLine={false} axisLine={false} />
        <YAxis tick={axisStyle} tickLine={false} axisLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Area type="monotone" dataKey="value" stroke={color} strokeWidth={2.5} fill="url(#areaFill)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ---------------- Circular progress ring (Part 8.2) ----------------
// For fee-status / collection-rate visualizations. Ring thickness ~10% of
// diameter, rounded stroke ends, muted background track, smooth animated arc.
// Pure SVG (no recharts) for precise geometry + lightweight rendering.
interface ProgressRingProps {
  value: number;          // 0..100
  size?: number;          // px (desktop ~180, mobile ~140)
  stroke?: number;        // ring thickness (defaults to ~10% of size)
  color?: string;         // arc colour (defaults to accent)
  track?: string;         // background track colour
  label?: string;         // small caption under the centred value
  centerValue?: string;   // override the centred text (e.g. currency)
}

export function ProgressRing({
  value, size = 180, stroke, color = "#6041C8", track = "#EEF0F7", label, centerValue,
}: ProgressRingProps) {
  const r = size / 2;
  const thickness = stroke ?? Math.max(10, Math.round(size * 0.1));
  const radius = r - thickness / 2;
  const circ = 2 * Math.PI * radius;
  const pct = Math.max(0, Math.min(100, value));
  const offset = circ - (pct / 100) * circ;
  return (
    <div className="flex flex-col items-center" role="img" aria-label={`${label ?? "Progress"} ${Math.round(pct)}%`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="max-w-full">
        <circle cx={r} cy={r} r={radius} fill="none" stroke={track} strokeWidth={thickness} />
        <circle
          cx={r} cy={r} r={radius} fill="none" stroke={color} strokeWidth={thickness}
          strokeLinecap="round"
          strokeDasharray={circ} strokeDashoffset={offset}
          transform={`rotate(-90 ${r} ${r})`}
          style={{ transition: "stroke-dashoffset 600ms ease-out" }}
        />
        <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central"
              style={{ fontSize: size * 0.22, fontWeight: 700, fill: "#202033" }}>
          {centerValue ?? `${Math.round(pct)}%`}
        </text>
      </svg>
      {label && <p className="mt-2 text-xs text-slate-muted">{label}</p>}
    </div>
  );
}

// ---------------- Attendance donut (Part 8.2 — exact colours, perfect circle) ----------------
type AttStatus = "present" | "absent" | "leave";

interface AttendanceDonutProps {
  present: number;
  absent: number;
  leave: number;
  percentage?: number;
  onSegmentClick?: (status: AttStatus) => void;
  onCentreClick?: () => void;
  size?: number; // square px (desktop ~260, tablet ~230, mobile ~200)
  loading?: boolean;
}

export function AttendanceDonut({
  present, absent, leave, percentage, onSegmentClick, onCentreClick, size = 260, loading,
}: AttendanceDonutProps) {
  const total = present + absent + leave;
  const pct = percentage ?? (total ? Math.round((present / total) * 1000) / 10 : 0);
  const ariaLabel = `Attendance ${pct}%. Present ${present}, absent ${absent}, leave ${leave}, total ${total} scheduled sessions.`;

  if (loading) {
    return <div className="animate-pulse rounded-full bg-slate-border/60" style={{ width: size, height: size }} />;
  }

  // Empty state: a neutral grey ring — never a fabricated 0% donut.
  if (total === 0) {
    return (
      <div className="flex flex-col items-center" role="img" aria-label="No attendance records yet">
        <svg width={size} height={size} viewBox="0 0 100 100" className="text-neutral">
          <circle cx="50" cy="50" r="40" fill="none" stroke="currentColor" strokeWidth="12" opacity="0.35" />
        </svg>
        <p className="mt-2 text-sm text-slate-muted">No attendance records yet</p>
      </div>
    );
  }

  const data = ([
    { label: "Present", value: present, status: "present" as const },
    { label: "Absent", value: absent, status: "absent" as const },
    { label: "Leave", value: leave, status: "leave" as const },
  ]).filter((d) => d.value > 0);

  const legend: { status: AttStatus; label: string; count: number }[] = [
    { status: "present", label: "Present", count: present },
    { status: "absent", label: "Absent", count: absent },
    { status: "leave", label: "Leave", count: leave },
  ];

  return (
    <div className="flex flex-col items-center" role="img" aria-label={ariaLabel}>
      <div className="relative mx-auto" style={{ width: size, height: size, maxWidth: "100%" }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data} dataKey="value" nameKey="label"
              innerRadius="45%" outerRadius="72%" paddingAngle={1} stroke="none"
              cursor={onSegmentClick ? "pointer" : undefined}
              onClick={(d: { status?: AttStatus }) => d?.status && onSegmentClick?.(d.status)}
            >
              {data.map((d) => <Cell key={d.status} fill={ATTENDANCE_COLORS[d.status]} />)}
            </Pie>
            <Tooltip
              contentStyle={tooltipStyle}
              formatter={(v: number, name: string) => [`${v} — ${Math.round((v / total) * 1000) / 10}%`, name]}
            />
          </PieChart>
        </ResponsiveContainer>
        <button
          type="button"
          onClick={onCentreClick}
          disabled={!onCentreClick}
          className="absolute inset-0 flex flex-col items-center justify-center rounded-full cursor-pointer transition-transform hover:scale-[1.02] disabled:cursor-default disabled:hover:scale-100"
          aria-label="Open full attendance history"
        >
          <span className="text-3xl font-bold text-ink leading-none">{pct}%</span>
          <span className="mt-1 text-xs text-slate-muted">Attendance</span>
        </button>
      </div>
      <ul className="mt-3 grid w-full grid-cols-3 gap-2 text-center text-xs">
        {legend.map((l) => (
          <li key={l.status} className="flex flex-col items-center gap-0.5">
            <button
              type="button"
              onClick={() => onSegmentClick?.(l.status)}
              disabled={!onSegmentClick}
              className="flex items-center gap-1.5 disabled:cursor-default"
            >
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: ATTENDANCE_COLORS[l.status] }} />
              <span className="text-slate-muted">{l.label}</span>
            </button>
            <span className="font-semibold text-ink">{l.count}</span>
            <span className="text-slate-muted">{total ? Math.round((l.count / total) * 1000) / 10 : 0}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
