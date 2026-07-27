import { FeedbackProvider } from "@/components/layout/FeedbackProvider";
import { SidebarNav } from "@/components/layout/SidebarNav";
import { TopBar } from "@/components/layout/TopBar";
import { PageTransition } from "@/components/layout/PageTransition";
import { ToastProvider } from "@/components/shared";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <ToastProvider>
      <FeedbackProvider>
        <div className="flex h-screen max-w-full overflow-hidden bg-slate-50">
          <SidebarNav />
          <div className="flex min-w-0 max-w-full flex-1 flex-col overflow-hidden">
            <TopBar />
            <main className="w-full max-w-full flex-1 overflow-x-hidden overflow-y-auto bg-[#f4f7f8] p-3 md:p-4 xl:p-5">
              <PageTransition>{children}</PageTransition>
            </main>
          </div>
        </div>
      </FeedbackProvider>
    </ToastProvider>
  );
}
