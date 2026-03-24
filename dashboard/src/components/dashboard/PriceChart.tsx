import { useQuery } from "@tanstack/react-query";
import { useSymbol } from "@/contexts/SymbolContext";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

interface Kline {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

function usePriceData() {
  const { symbol } = useSymbol();
  return useQuery({
    queryKey: ["price-chart", symbol],
    queryFn: async (): Promise<Kline[]> => {
      // Binance public klines API — no key needed
      const res = await fetch(
        `https://api.binance.com/api/v3/klines?symbol=${symbol}&interval=1h&limit=48`
      );
      if (!res.ok) throw new Error("Binance API error");
      const data = await res.json();
      return data.map((k: any[]) => ({
        time: new Date(k[0]).toLocaleTimeString("en-US", {
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        }),
        open: parseFloat(k[1]),
        high: parseFloat(k[2]),
        low: parseFloat(k[3]),
        close: parseFloat(k[4]),
      }));
    },
    refetchInterval: 60000,
    retry: 2,
  });
}

export function PriceChart() {
  const { symbol } = useSymbol();
  const { data, isLoading } = usePriceData();

  const prices = data ?? [];
  const latest = prices[prices.length - 1];
  const first = prices[0];
  const isUp = latest && first ? latest.close >= first.close : true;

  const formatPrice = (v: number) => {
    if (v >= 10000) return v.toFixed(0);
    if (v >= 100) return v.toFixed(1);
    return v.toFixed(2);
  };

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            {symbol.replace("USDT", " / USDT")}
          </span>
          {latest && (
            <span className="font-mono text-lg font-bold text-foreground">
              ${formatPrice(latest.close)}
            </span>
          )}
          {latest && first && (
            <span
              className={`font-mono text-xs ${isUp ? "text-bullish" : "text-bearish"}`}
            >
              {isUp ? "+" : ""}
              {((latest.close - first.close) / first.close * 100).toFixed(2)}%
            </span>
          )}
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">48h · 1h candles</span>
      </div>

      <div className="h-40">
        {isLoading ? (
          <div className="flex h-full items-center justify-center">
            <span className="font-mono text-xs text-muted-foreground animate-pulse">Loading chart...</span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={prices} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="0%"
                    stopColor={isUp ? "hsl(142, 60%, 45%)" : "hsl(0, 72%, 55%)"}
                    stopOpacity={0.2}
                  />
                  <stop
                    offset="100%"
                    stopColor={isUp ? "hsl(142, 60%, 45%)" : "hsl(0, 72%, 55%)"}
                    stopOpacity={0}
                  />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(220, 14%, 14%)"
                vertical={false}
              />
              <XAxis
                dataKey="time"
                axisLine={false}
                tickLine={false}
                tick={{ fill: "hsl(215, 12%, 50%)", fontSize: 10, fontFamily: "JetBrains Mono" }}
                interval="preserveStartEnd"
                minTickGap={40}
              />
              <YAxis
                domain={["dataMin", "dataMax"]}
                axisLine={false}
                tickLine={false}
                tick={{ fill: "hsl(215, 12%, 50%)", fontSize: 10, fontFamily: "JetBrains Mono" }}
                tickFormatter={formatPrice}
                width={55}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(220, 18%, 7%)",
                  border: "1px solid hsl(220, 14%, 14%)",
                  borderRadius: "0.375rem",
                  fontFamily: "JetBrains Mono",
                  fontSize: "11px",
                  color: "hsl(210, 20%, 90%)",
                }}
                labelStyle={{ color: "hsl(215, 12%, 50%)" }}
                formatter={(value: number) => [`$${formatPrice(value)}`, "Price"]}
              />
              <Area
                type="monotone"
                dataKey="close"
                stroke={isUp ? "hsl(142, 60%, 45%)" : "hsl(0, 72%, 55%)"}
                strokeWidth={1.5}
                fill="url(#priceGrad)"
                dot={false}
                activeDot={{ r: 3, strokeWidth: 0 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
