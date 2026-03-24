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

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <SymbolProvider>
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
      </SymbolProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
