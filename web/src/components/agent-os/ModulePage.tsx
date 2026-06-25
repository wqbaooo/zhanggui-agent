import Link from "next/link";
import { ArrowRight, CheckCircle2, CircleDot, FileSearch, type LucideIcon } from "lucide-react";
import { storeModules, type AgentModule, type HealthTone } from "@/data/agent-store-os";

const toneClass: Record<HealthTone, string> = {
  good: "border-emerald-200 bg-emerald-50 text-emerald-800",
  watch: "border-amber-200 bg-amber-50 text-amber-800",
  risk: "border-red-200 bg-red-50 text-red-800",
  info: "border-sky-200 bg-sky-50 text-sky-800",
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
}: {
  module: AgentModule;
  children?: React.ReactNode;
}) {
  const Icon = module.icon;

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-4 pb-8">
      <section className="rounded-xl border border-muted-border/35 bg-surface/95 p-4 shadow-sm md:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-primary-container px-2.5 py-1 font-label-caps text-primary-fixed">
                <Icon className="h-3.5 w-3.5" />
                {module.eyebrow}
              </span>
              <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${toneClass[module.status]}`}>
                {toneLabel[module.status]}
              </span>
            </div>
            <h1 className="mt-3 text-2xl font-semibold tracking-normal text-on-background md:text-3xl">
              {module.title}
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-on-surface-variant">
              {module.description}
            </p>
          </div>

          <div className="grid min-w-[260px] grid-cols-2 gap-2">
            <MetricTile label="核心指标" value={module.primaryMetric} />
            <MetricTile label="当前状态" value={module.secondaryMetric} />
          </div>
        </div>
      </section>

      {children}

      <section className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-xl border border-muted-border/35 bg-surface/95 p-4 shadow-sm">
          <p className="font-label-caps text-on-surface-variant">输出</p>
          <div className="mt-3 grid gap-2">
            {module.tasks.map((task) => (
              <div key={task} className="flex items-center gap-2 rounded-lg bg-surface-container-lowest px-3 py-2 text-sm text-on-background">
                <CheckCircle2 className="h-4 w-4 shrink-0 text-primary-fixed" />
                {task}
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-muted-border/35 bg-surface/95 p-4 shadow-sm">
          <p className="font-label-caps text-on-surface-variant">证据</p>
          <div className="mt-3 space-y-2">
            {module.evidence.map((item) => (
              <div key={item} className="flex items-center gap-2 text-sm text-on-surface-variant">
                <FileSearch className="h-4 w-4 shrink-0 text-primary-fixed" />
                {item}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-muted-border/35 bg-surface/95 p-4 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="font-label-caps text-on-surface-variant">入口</p>
            <h2 className="mt-1 text-lg font-semibold text-on-background">工作台对话 / 资料入库</h2>
          </div>
          <Link
            href="/overview"
            className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-on-primary hover:bg-primary-fixed"
          >
            回工作台
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>
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
            className={`rounded-xl border p-4 transition-colors hover:border-primary/40 hover:bg-surface ${
              active ? "border-primary/45 bg-primary-container/25" : "border-muted-border/35 bg-surface/90"
            }`}
          >
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-primary-container p-2 text-primary-fixed">
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-on-background">{item.title}</p>
                <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-on-surface-variant">{item.description}</p>
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
    <section className="rounded-xl border border-muted-border/35 bg-surface/95 p-4 shadow-sm">
      <p className="font-label-caps text-on-surface-variant">{title}</p>
      <div className="mt-3 grid gap-2">
        {items.map((item) => (
          <div key={item} className="flex items-center gap-2 rounded-lg bg-surface-container-lowest px-3 py-2 text-sm text-on-background">
            <Icon className="h-4 w-4 shrink-0 text-primary-fixed" />
            {item}
          </div>
        ))}
      </div>
    </section>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-muted-border/35 bg-surface-container-lowest px-3 py-2">
      <p className="font-label-caps text-on-surface-variant">{label}</p>
      <p className="mt-1 text-sm font-semibold text-on-background">{value}</p>
    </div>
  );
}
