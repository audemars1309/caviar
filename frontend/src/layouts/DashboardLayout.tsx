import { Outlet } from "react-router";

import { Footer } from "@/layouts/components/Footer";
import { Header } from "@/layouts/components/Header";
import { Sidebar } from "@/layouts/components/Sidebar";

export function DashboardLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <div className="flex flex-1">
        <Sidebar />
        <main className="min-w-0 flex-1 p-6">
          <Outlet />
        </main>
      </div>
      <Footer />
    </div>
  );
}
