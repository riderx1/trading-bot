import { Outlet } from "react-router-dom";
import { TopNav } from "./TopNav";

export function AppLayout() {
  return (
    <div className="min-h-screen bg-background">
      <TopNav />
      <main className="mx-auto max-w-7xl p-3 sm:p-4 lg:p-6">
        <Outlet />
      </main>
    </div>
  );
}
