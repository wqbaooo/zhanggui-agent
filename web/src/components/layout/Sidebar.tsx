"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, TrendingUp, AlertTriangle, MessageSquare, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "工作台", icon: Home },
  { href: "/operations", label: "运营", icon: TrendingUp },
  { href: "/investment", label: "投资", icon: TrendingUp },
  { href: "/risks", label: "风险", icon: AlertTriangle },
  { href: "/feedback", label: "反馈", icon: MessageSquare },
  { href: "/settings", label: "设置", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 h-screen bg-surface border-r border-muted-border/20 flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-muted-border/20">
        <h1 className="text-lg font-semibold text-on-background">掌柜Agent</h1>
        <p className="mt-1 text-[11px] text-on-surface-variant">餐饮经营教练</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item, idx) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-300",
                "hover:scale-[1.02] hover:shadow-sm",
                isActive
                  ? "bg-primary/10 text-primary border border-primary/20"
                  : "text-on-surface-variant hover:bg-surface-container-high/50 hover:text-on-background"
              )}
              style={{
                animation: `fade-in-scale 0.4s ease-out ${idx * 50}ms both`,
              }}
            >
              <Icon className={cn("w-5 h-5", isActive && "animate-glow-pulse")} />
              <span>{item.label}</span>
              {isActive && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-muted-border/20">
        <div className="glass-card rounded-lg p-3">
          <p className="text-xs text-on-surface-variant">经营教练模式</p>
          <p className="text-[10px] text-on-surface-variant/60 mt-1">
            持续学习你的经营数据
          </p>
        </div>
      </div>
    </aside>
  );
}
