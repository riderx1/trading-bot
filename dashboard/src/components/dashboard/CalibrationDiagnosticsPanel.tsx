interface CalibrationDiagnostics {
  confidence_distribution: Record<string, number>;
  edge_distribution: Record<string, number>;
  signal_density: {
    window_minutes: number;
    total_signals: number;
    by_strategy: Record<string, number>;
  };
}

interface Props {
  diagnostics: CalibrationDiagnostics | undefined;
  isLoading: boolean;
  isError: boolean;
}

function maxValue(values: number[]): number {
  if (values.length === 0) return 1;
  return Math.max(1, ...values);
}

function prettyLabel(label: string): string {
  return label.replaceAll("_", " ");
}

export function CalibrationDiagnosticsPanel({ diagnostics, isLoading, isError }: Props) {
  const confidenceRows = Object.entries(diagnostics?.confidence_distribution ?? {});
  const edgeRows = Object.entries(diagnostics?.edge_distribution ?? {});
  const densityRows = Object.entries(diagnostics?.signal_density?.by_strategy ?? {}).sort((a, b) => b[1] - a[1]);

  const confidenceMax = maxValue(confidenceRows.map(([, count]) => count));
  const edgeMax = maxValue(edgeRows.map(([, count]) => count));
  const densityMax = maxValue(densityRows.map(([, count]) => count));

  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-[0_10px_30px_rgba(0,0,0,0.15)]">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-muted-foreground">Calibration Diagnostics</p>
          <h2 className="mt-1 text-lg font-semibold text-foreground">Signal Quality Snapshot</h2>
        </div>
        <div className="text-right">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Window</p>
          <p className="font-mono text-xs text-foreground">{diagnostics?.signal_density?.window_minutes ?? 120}m</p>
        </div>
      </div>

      {isLoading ? <p className="py-10 text-center font-mono text-xs text-muted-foreground">Loading diagnostics...</p> : null}
      {isError ? <p className="py-10 text-center font-mono text-xs text-bearish">Could not load diagnostics data.</p> : null}

      {!isLoading && !isError ? (
        <div className="grid gap-4 xl:grid-cols-3">
          <MetricGroup title="Confidence Distribution" rows={confidenceRows} max={confidenceMax} colorClass="bg-primary" suffix="signals" />
          <MetricGroup title="Edge Distribution" rows={edgeRows} max={edgeMax} colorClass="bg-accent" suffix="setups" />
          <MetricGroup title="Signal Density by Strategy" rows={densityRows} max={densityMax} colorClass="bg-warning" suffix="signals" />
        </div>
      ) : null}

      {!isLoading && !isError ? (
        <div className="mt-4 rounded-lg border border-border bg-secondary/25 px-4 py-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Summary</p>
          <p className="mt-2 font-mono text-sm text-foreground">
            Total signals in window: {diagnostics?.signal_density?.total_signals ?? 0}
          </p>
        </div>
      ) : null}
    </section>
  );
}

function MetricGroup({
  title,
  rows,
  max,
  colorClass,
  suffix,
}: {
  title: string;
  rows: Array<[string, number]>;
  max: number;
  colorClass: string;
  suffix: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-secondary/20 p-4">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{title}</p>
      <div className="mt-3 space-y-2">
        {rows.map(([label, count]) => (
          <div key={label}>
            <div className="mb-1 flex items-center justify-between">
              <span className="font-mono text-xs text-foreground">{prettyLabel(label)}</span>
              <span className="font-mono text-[10px] text-muted-foreground">{count} {suffix}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div className={`h-full ${colorClass}`} style={{ width: `${Math.max(2, Math.min(100, (count / max) * 100))}%` }} />
            </div>
          </div>
        ))}
        {rows.length === 0 ? <p className="py-6 text-center font-mono text-xs text-muted-foreground">No data in selected window</p> : null}
      </div>
    </div>
  );
}
