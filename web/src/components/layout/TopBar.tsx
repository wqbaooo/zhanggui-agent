"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Camera, Mic, FileText, Upload } from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

export function TopBar() {
  const pathname = usePathname();
  const [showQuickCapture, setShowQuickCapture] = useState(false);

  const routeTitles: Record<string, string> = {
    "/overview": "掌柜台",
    "/overview/actions": "今日推进",
    "/overview/coach": "接店教练",
    "/capture": "资料录入",
    "/capture/history": "录入历史",
    "/dashboard": "经营总览",
    "/sales": "营业日报",
    "/profit": "保本测算",
    "/monthly": "月度账单",
    "/channels": "渠道外卖",
    "/products": "商品菜单",
    "/inventory": "库存台账",
    "/consumables": "水电耗材",
    "/calendar": "天气商圈",
    "/reports": "经营复盘",
    "/alerts": "预警中心",
    "/sop": "SOP 作业库",
    "/training": "员工训练",
    "/workflow": "店铺动线",
    "/documents": "店铺档案",
    "/settings": "店铺设置",
  };
  const pageTitle = routeTitles[pathname] ?? "掌柜台";

  return (
    <header className="sticky top-0 z-50 w-full border-b border-orange-100/50 bg-[#FAF7F2]/70 backdrop-blur-2xl">
      <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-3 px-4 py-2.5 md:px-6">
        {/* 左侧：页面标题 */}
        <div className="flex min-w-0 items-center gap-3">
          <Link href="/overview" className="lg:hidden">
            <span className="text-base font-bold text-stone-800">掌柜 Agent</span>
          </Link>
          <h1 className="hidden text-sm font-semibold text-stone-700 lg:block">{pageTitle}</h1>
          <div className="hidden items-center gap-1.5 lg:flex">
            <span className="inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400 status-pulse" />
            <span className="text-[10px] text-stone-400">经营工作区已连接</span>
          </div>
        </div>

        {/* 右侧：快速录入 + 日期 */}
        <div className="flex shrink-0 items-center gap-2">
          <span className="hidden text-[10px] text-stone-400 sm:block">
            {new Date().toLocaleDateString("zh-CN", { month: "long", day: "numeric", weekday: "short" })}
          </span>

          {/* 快速录入按钮组 */}
          <div className="relative">
            <button
              onClick={() => setShowQuickCapture(!showQuickCapture)}
              className="flex items-center gap-1.5 rounded-full bg-gradient-to-r from-orange-500 to-orange-600 px-3 py-1.5 text-[11px] font-semibold text-white shadow-md shadow-orange-200/50 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-orange-300/50"
            >
              <Upload className="h-3 w-3" />
              录入
            </button>

            <AnimatePresence>
              {showQuickCapture && (
                <>
                  <div
                    className="fixed inset-0 z-40"
                    onClick={() => setShowQuickCapture(false)}
                  />
                  <motion.div
                    initial={{ opacity: 0, scale: 0.9, y: -10 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.9, y: -10 }}
                    transition={{ duration: 0.15 }}
                    className="absolute right-0 top-full z-50 mt-2 w-44 overflow-hidden rounded-2xl border border-orange-100 bg-white shadow-xl"
                  >
                    <Link
                      href="/capture"
                      className="flex items-center gap-2.5 px-3 py-2.5 text-xs text-stone-600 transition-colors hover:bg-orange-50 hover:text-orange-700"
                      onClick={() => setShowQuickCapture(false)}
                    >
                      <Camera className="h-3.5 w-3.5 text-orange-400" />
                      拍图录入
                    </Link>
                    <Link
                      href="/overview"
                      className="flex items-center gap-2.5 px-3 py-2.5 text-xs text-stone-600 transition-colors hover:bg-orange-50 hover:text-orange-700"
                      onClick={() => setShowQuickCapture(false)}
                    >
                      <Mic className="h-3.5 w-3.5 text-rose-400" />
                      语音录入
                    </Link>
                    <Link
                      href="/overview"
                      className="flex items-center gap-2.5 px-3 py-2.5 text-xs text-stone-600 transition-colors hover:bg-orange-50 hover:text-orange-700"
                      onClick={() => setShowQuickCapture(false)}
                    >
                      <FileText className="h-3.5 w-3.5 text-blue-400" />
                      文字录入
                    </Link>
                  </motion.div>
                </>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </header>
  );
}
