import type { Metadata } from "next";
import { QueryProvider } from "@/lib/query-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "掌柜Agent",
  description: "掌柜 Agent — 新余恒太城大口章鱼烧的 AI 单店经营工作台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased min-h-screen flex flex-col relative">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
