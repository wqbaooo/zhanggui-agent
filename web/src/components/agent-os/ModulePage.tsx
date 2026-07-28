import Link from "next/link";
import { CircleDot, type LucideIcon } from "lucide-react";
import { storeModules, type AgentModule, type HealthTone } from "@/data/agent-store-os";

const toneClass: Record<HealthTone, string> = {
  good: "border-nori-200 bg-nori-50 text-nori-700",
  watch: "border-sauce-200 bg-sauce-50 text-sauce-700",
  risk: "border-red-200 bg-red-50 text-red-700",
  info: "border-stone-200 bg-stone-50 text-stone-600",
};

const toneLabel: Record<HealthTone, string> = {
  good: "可执行",
  watch: "待校准",
  risk: "需盯紧",
  info: "待接入",
};

export function getModule(href: string) {
  return storeModules.find((item) => item.href === href) ?? storeModules[0];
}

export function ModulePage({
  module,
  children,
  compact = false,
}: {
  module: AgentModule;
  children?: React.ReactNode;
  compact?: boolean;
}) {
  const Icon = module.icon;

  return (
    <main className="mx-auto flex w-full min-w-0 max-w-7xl flex-col gap-4 overflow-hidden pb-8">
      <section className={`glass-card min-w-0 max-w-full overflow-hidden rounded-xl ${compact ? "px-4 py-3" : "p-4 md:p-5"}`}>
        <div className="flex min-w-0 flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-octo-50 px-2.5 py-1 font-label-caps text-octo-700">
                <Icon className="h-3.5 w-3.5" />
                {module.eyebrow}
              </span>
              <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${toneClass[module.status]}`}>
                {toneLabel[module.status]}
              </span>
            </div>
            <h1 className={`${compact ? "mt-2 text-xl" : "mt-3 text-2xl md:text-3xl"} font-semibold tracking-normal text-stone-900`}>
              {module.title}
            </h1>
            <p className={`${compact ? "mt-1 text-xs" : "mt-2 text-sm"} max-w-[48rem] leading-relaxed text-stone-500`}>
              {module.description}
            </p>
          </div>

          {!compact && <div className="grid w-full min-w-0 grid-cols-2 gap-2 lg:w-auto lg:min-w-[260px]">
            <MetricTile label="核心指标" value={module.primaryMetric} />
            <MetricTile label="当前状态" value={module.secondaryMetric} />
          </div>}
        </div>
      </section>

      {children}
    </main>
  );
}

export function ModuleGrid({ currentHref }: { currentHref?: string }) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {storeModules.map((item) => {
        const Icon = item.icon;
        const active = item.href === currentHref;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`rounded-xl border p-4 transition-colors hover:border-octo-200 hover:bg-surface ${
              active ? "border-octo-300 bg-octo-50" : "border-stone-200 bg-white/60"
            }`}
          >
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-octo-50 p-2 text-octo-600">
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-stone-900">{item.title}</p>
                <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-stone-500">{item.description}</p>
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}

export function ChecklistBlock({ title, items, icon: Icon = CircleDot }: { title: string; items: string[]; icon?: LucideIcon }) {
  return (
    <section className="glass-card rounded-xl p-4">
      <p className="font-label-caps text-stone-500">{title}</p>
      <div className="mt-3 grid gap-2">
        {items.map((item) => (
          <div key={item} className="flex items-center gap-2 rounded-lg bg-stone-50 px-3 py-2 text-sm text-stone-900">
            <Icon className="h-4 w-4 shrink-0 text-octo-500" />
            {item}
          </div>
        ))}
      </div>
    </section>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-stone-200 bg-stone-50 px-3 py-2">
      <p className="font-label-caps text-stone-500">{label}</p>
      <p className="mt-1 break-all text-sm font-semibold text-stone-900">{value}</p>
    </div>
  );
}
