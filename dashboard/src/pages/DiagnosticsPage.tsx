import { useCalibrationDiagnostics } from "@/hooks/use-trading-data";
import { CalibrationDiagnosticsPanel } from "@/components/dashboard/CalibrationDiagnosticsPanel";

export default function DiagnosticsPage() {
  const diagnostics = useCalibrationDiagnostics(120);

  return (
    <div className="space-y-4">
      <h1 className="font-mono text-lg font-bold text-foreground">Diagnostics</h1>
      <p className="font-mono text-xs text-muted-foreground">
        Calibration metrics for confidence, edge quality, and strategy signal density.
      </p>
      <CalibrationDiagnosticsPanel
        diagnostics={diagnostics.data}
        isLoading={diagnostics.isLoading}
        isError={Boolean(diagnostics.error)}
      />
    </div>
  );
}
