import { createContext, useContext, useState, type ReactNode } from "react";

const SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"] as const;
export type TradingSymbol = (typeof SYMBOLS)[number];

interface SymbolContextType {
  symbol: TradingSymbol;
  setSymbol: (s: TradingSymbol) => void;
  symbols: readonly TradingSymbol[];
}

const SymbolContext = createContext<SymbolContextType | null>(null);

export function SymbolProvider({ children }: { children: ReactNode }) {
  const [symbol, setSymbol] = useState<TradingSymbol>("BTCUSDT");
  return (
    <SymbolContext.Provider value={{ symbol, setSymbol, symbols: SYMBOLS }}>
      {children}
    </SymbolContext.Provider>
  );
}

export function useSymbol() {
  const ctx = useContext(SymbolContext);
  if (!ctx) throw new Error("useSymbol must be used within SymbolProvider");
  return ctx;
}
