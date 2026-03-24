import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SymbolProvider } from "@/contexts/SymbolContext";
import { AppLayout } from "@/components/layout/AppLayout";
import Index from "./pages/Index";
import BotsPage from "./pages/BotsPage";
import StrategyPage from "./pages/StrategyPage";
import HistoryPage from "./pages/HistoryPage";
import WalletPage from "./pages/WalletPage";
import DiagnosticsPage from "./pages/DiagnosticsPage";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

class AppErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("Dashboard render failed", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen bg-background px-4 py-10 text-foreground">
          <div className="mx-auto max-w-3xl rounded-xl border border-border bg-card p-6 shadow-[0_12px_32px_rgba(0,0,0,0.18)]">
            <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-warning">
              Dashboard Error
            </p>
            <h1 className="mt-2 text-2xl font-semibold">The dashboard hit a client-side error.</h1>
            <p className="mt-3 text-sm text-muted-foreground">
              Reload the page. If the problem persists, use the details below to identify the failing component.
            </p>
            <pre className="mt-5 overflow-auto rounded-lg border border-border bg-secondary/25 p-4 font-mono text-xs text-foreground/90">
              {this.state.error.stack || this.state.error.message}
            </pre>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <SymbolProvider>
        <AppErrorBoundary>
          <BrowserRouter>
            <Routes>
              <Route element={<AppLayout />}>
                <Route path="/" element={<Index />} />
                <Route path="/bots" element={<BotsPage />} />
                <Route path="/strategy" element={<StrategyPage />} />
                <Route path="/history" element={<HistoryPage />} />
                <Route path="/wallet" element={<WalletPage />} />
                <Route path="/diagnostics" element={<DiagnosticsPage />} />
              </Route>
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </AppErrorBoundary>
      </SymbolProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
