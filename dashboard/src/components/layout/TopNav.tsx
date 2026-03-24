import { NavLink, useLocation } from "react-router-dom";
import { useSymbol } from "@/contexts/SymbolContext";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Activity, Bot, BarChart3, Clock, Wallet, Stethoscope, FlaskConical } from "lucide-react";
import type { TradingSymbol } from "@/contexts/SymbolContext";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: Activity },
  { to: "/bots", label: "Bots", icon: Bot },
  { to: "/strategy", label: "Strategy", icon: BarChart3 },
  { to: "/history", label: "History", icon: Clock },
  { to: "/backtest", label: "Backtesting", icon: FlaskConical },
  { to: "/wallet", label: "Wallet", icon: Wallet },
  { to: "/diagnostics", label: "Diagnostics", icon: Stethoscope },
];

const SYMBOL_DISPLAY: Record<string, { label: string; short: string }> = {
  BTCUSDT: { label: "BTC / USDT", short: "BTC" },
  ETHUSDT: { label: "ETH / USDT", short: "ETH" },
  SOLUSDT: { label: "SOL / USDT", short: "SOL" },
};

export function TopNav() {
  const { symbol, setSymbol, symbols } = useSymbol();
  const location = useLocation();

  return (
    <nav className="sticky top-0 z-50 border-b border-border bg-card/85 backdrop-blur-md">
      <div className="mx-auto flex h-12 max-w-7xl items-center gap-1 px-3 sm:px-4 lg:px-6">
        {/* Logo / Brand */}
        <div className="mr-4 flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10">
            <Activity className="h-4 w-4 text-primary" />
          </div>
          <span className="hidden font-mono text-sm font-bold tracking-tight text-foreground sm:block">
            TBOT
          </span>
        </div>

        {/* Nav links */}
        <div className="flex items-center gap-0.5">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => {
            const isActive =
              to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);
            return (
              <NavLink
                key={to}
                to={to}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 font-mono text-xs transition-colors ${
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{label}</span>
              </NavLink>
            );
          })}
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        <Badge variant="secondary" className="mr-2 border border-emerald-500/40 bg-emerald-500/15 font-mono text-[10px] uppercase tracking-wide text-emerald-300">
          PAPER TRADING ONLY
        </Badge>

        {/* Symbol switcher */}
        <Select value={symbol} onValueChange={(v) => setSymbol(v as TradingSymbol)}>
          <SelectTrigger className="h-8 w-[138px] border-border bg-secondary/50 font-mono text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {symbols.map((s) => (
              <SelectItem key={s} value={s} className="font-mono text-xs">
                {SYMBOL_DISPLAY[s]?.label ?? s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </nav>
  );
}
