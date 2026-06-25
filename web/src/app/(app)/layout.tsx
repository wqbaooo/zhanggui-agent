import { FeedbackProvider } from "@/components/layout/FeedbackProvider";
import { SidebarNav } from "@/components/layout/SidebarNav";
import { TopBar } from "@/components/layout/TopBar";
import { PageTransition } from "@/components/layout/PageTransition";
import { ToastProvider } from "@/components/shared";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <ToastProvider>
      <FeedbackProvider>
        <div className="neural-bg" id="neural-bg" />
        <div className="flex h-screen overflow-hidden">
          <SidebarNav />
          <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
            <TopBar />
            <main className="mx-auto w-full max-w-[1440px] flex-1 overflow-y-auto p-4 md:p-6">
              <PageTransition>{children}</PageTransition>
            </main>
          </div>
        </div>
      </FeedbackProvider>
    </ToastProvider>
  );
}
