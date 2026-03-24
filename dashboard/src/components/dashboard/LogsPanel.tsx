import { Terminal } from "lucide-react";
import type { LogEntry } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";

interface Props {
  logs: LogEntry[];
}

const LEVEL_COLORS: Record<string, string> = {
  INFO: "text-bullish",
  WARNING: "text-warning",
  ERROR: "text-bearish",
  DEBUG: "text-muted-foreground",
};

export function LogsPanel({ logs }: Props) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-center gap-2">
        <Terminal className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          System Logs
        </span>
      </div>

      <ScrollArea className="h-48">
        <div className="space-y-0.5 font-mono text-[11px]">
          {logs.map((log) => (
            <div key={log.id} className="flex gap-2 py-0.5">
              <span className="w-16 shrink-0 text-muted-foreground/60">
                {new Date(log.timestamp).toLocaleTimeString("en-US", {
                  hour12: false,
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })}
              </span>
              <span className={`w-10 shrink-0 ${LEVEL_COLORS[log.level] ?? "text-muted-foreground"}`}>
                {log.level}
              </span>
              <span className="text-foreground/80">{log.message}</span>
            </div>
          ))}
          {logs.length === 0 && (
            <p className="py-4 text-center text-muted-foreground">No logs</p>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
