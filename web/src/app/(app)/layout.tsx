import { FeedbackProvider } from "@/components/layout/FeedbackProvider";
import { TopBar } from "@/components/layout/TopBar";
import { Sidebar } from "@/components/layout/Sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <FeedbackProvider>
      <div className="min-h-screen bg-cream-50">
        <TopBar />
        <div className="flex">
          <Sidebar />
          <main className="flex-1 overflow-auto px-6 py-5">
            {children}
          </main>
        </div>
      </div>
    </FeedbackProvider>
  );
}
