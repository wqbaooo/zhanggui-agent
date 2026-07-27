"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  CloudRain,
  Droplets,
  MapPin,
  RefreshCw,
  Satellite,
  Wind,
} from "lucide-react";
import { getWeather, type WeatherForecast, type WeatherResponse } from "@/lib/api";

const ReactAnimatedWeather = dynamic(() => import("react-animated-weather"), { ssr: false });

const weatherToIcon: Record<string, string> = {
  sunny: "CLEAR_DAY",
  cloudy: "PARTLY_CLOUDY_DAY",
  overcast: "CLOUDY",
  light_rain: "RAIN",
  heavy_rain: "RAIN",
  thunderstorm: "RAIN",
  snow: "SNOW",
  fog: "FOG",
};

const weatherColor: Record<string, string> = {
  sunny: "#d97706",
  cloudy: "#64748b",
  overcast: "#475569",
  light_rain: "#0284c7",
  heavy_rain: "#1d4ed8",
  thunderstorm: "#4f46e5",
  snow: "#0369a1",
  fog: "#64748b",
};

const sourceLabels: Record<string, string> = {
  amap: "高德天气",
  "weather.com.cn": "中国天气网",
  "open-meteo": "Open-Meteo",
};

function sourceLabel(source: string | null) {
  if (!source) return "暂无可用来源";
  return source
    .split("+")
    .map((item) => sourceLabels[item] || item)
    .join(" + ");
}

function degree(value: number | null) {
  return value == null ? "—" : `${value}°`;
}

export default function CalendarPage() {
  const [data, setData] = useState<WeatherResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const reduceMotion = Boolean(useReducedMotion());

  const fetchWeather = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getWeather());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "天气服务连接失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchWeather();
    const interval = setInterval(() => void fetchWeather(), 600000);
    return () => clearInterval(interval);
  }, [fetchWeather]);

  if (!data && loading) {
    return (
      <WeatherPageFrame>
        <div className="space-y-4" aria-label="天气数据加载中">
          <div className="h-44 animate-pulse rounded-2xl border border-slate-200 bg-white/70" />
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-7">
            {Array.from({ length: 7 }, (_, index) => (
              <div key={index} className="h-36 animate-pulse rounded-2xl border border-slate-200 bg-white/60" />
            ))}
          </div>
        </div>
      </WeatherPageFrame>
    );
  }

  if (!data) {
    return (
      <WeatherPageFrame>
        <motion.div
          initial={reduceMotion ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-red-200 bg-red-50 p-6 text-center"
        >
          <CloudRain className="mx-auto h-8 w-8 text-red-500" />
          <p className="mt-3 text-sm font-semibold text-red-900">天气数据暂时无法连接</p>
          <p className="mt-1 text-xs text-red-700">{error || "请检查后端服务后重试"}</p>
          <button
            type="button"
            onClick={() => void fetchWeather()}
            className="mt-4 inline-flex min-h-10 items-center gap-2 rounded-xl border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-800 transition-colors hover:bg-red-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
          >
            <RefreshCw className="h-4 w-4" />
            重新获取
          </button>
        </motion.div>
      </WeatherPageFrame>
    );
  }

  const statusMeta = data.status === "live"
    ? { label: "实时可用", icon: CheckCircle2, className: "border-emerald-200 bg-emerald-50 text-emerald-800" }
    : data.status === "partial"
      ? { label: "部分可用", icon: AlertTriangle, className: "border-amber-200 bg-amber-50 text-amber-800" }
      : { label: "来源不可用", icon: AlertTriangle, className: "border-red-200 bg-red-50 text-red-800" };
  const StatusIcon = statusMeta.icon;
  const hasRainRisk = data.forecast.some((day) => ["heavy_rain", "thunderstorm"].includes(day.weather));
  const hasHeatRisk = data.forecast.some((day) => day.temp_high != null && day.temp_high > 35);
  const currentIsWeekend = data.forecast[0]?.is_weekend ?? false;

  return (
    <WeatherPageFrame>
      <motion.div
        key={data.updated_at}
        initial={reduceMotion ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28, ease: "easeOut" }}
        className="space-y-4"
      >
        <motion.section
          layout={!reduceMotion}
          className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
        >
          <div className="flex flex-col gap-4 border-b border-slate-100 px-4 py-4 sm:px-5 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${statusMeta.className}`}>
                  <StatusIcon className="h-3.5 w-3.5" />
                  {statusMeta.label}
                </span>
                {data.is_stale && (
                  <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800">
                    数据已过期
                  </span>
                )}
              </div>
              <div className="mt-3 flex min-w-0 items-start gap-2">
                <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-slate-950">{data.city} · {data.district} · {data.location}</p>
                  <p className="mt-0.5 break-words text-xs text-slate-500">{data.address}</p>
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => void fetchWeather()}
              disabled={loading}
              aria-label="刷新天气数据"
              className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:cursor-wait disabled:opacity-60"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              {loading ? "更新中" : "刷新"}
            </button>
          </div>

          <div className="grid gap-5 px-4 py-5 sm:px-5 lg:grid-cols-[minmax(0,1fr)_minmax(280px,0.75fr)] lg:items-center">
            <div className="flex min-w-0 items-center gap-4 sm:gap-6">
              <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl bg-sky-50 sm:h-24 sm:w-24">
                {data.current.weather === "unknown" ? (
                  <CloudRain className="h-10 w-10 text-slate-400" />
                ) : (
                  <ReactAnimatedWeather
                    icon={weatherToIcon[data.current.weather] ?? "CLOUDY"}
                    color={weatherColor[data.current.weather] ?? "#64748b"}
                    size={82}
                    animate
                  />
                )}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-600">{data.current.weather_text || "天气暂不可用"}</p>
                <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span className="text-5xl font-semibold tracking-tight text-slate-950 sm:text-6xl">
                    {degree(data.current.temperature)}
                  </span>
                  <span className="text-sm text-slate-500">
                    今日最高 {degree(data.current.temp_high)} · 最低 {degree(data.current.temp_low)}
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-600">
                  <span className="inline-flex items-center gap-1.5">
                    <Droplets className="h-3.5 w-3.5" />
                    湿度 {data.current.humidity == null ? "—" : `${data.current.humidity}%`}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <Wind className="h-3.5 w-3.5" />
                    {data.current.wind || "风力暂缺"}
                  </span>
                </div>
              </div>
            </div>

            <div className="min-w-0 rounded-2xl bg-slate-50 p-4">
              <p className="text-xs font-semibold text-slate-700">今日经营提醒</p>
              <div className="mt-2 space-y-2">
                {data.current.tips.map((tip) => (
                  <p key={tip} className="flex gap-2 text-sm leading-6 text-slate-700">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-500" />
                    <span>{tip}</span>
                  </p>
                ))}
              </div>
              <div className="mt-3 border-t border-slate-200 pt-3 text-[11px] leading-5 text-slate-500">
                <p>实况：{sourceLabel(data.current_source)} · {data.observed_at || "更新时间未知"}</p>
                <p>预报：{sourceLabel(data.forecast_source)} · {data.forecast_updated_at || "更新时间未知"}</p>
              </div>
            </div>
          </div>
        </motion.section>

        <AnimatePresence initial={false}>
          {data.warnings.length > 0 && (
            <motion.section
              initial={reduceMotion ? false : { opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={reduceMotion ? undefined : { opacity: 0, height: 0 }}
              className="overflow-hidden rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3"
              aria-label="天气数据提醒"
            >
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" />
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-amber-900">数据提醒</p>
                  <p className="mt-1 text-xs leading-5 text-amber-800">{data.warnings.join("；")}</p>
                </div>
              </div>
            </motion.section>
          )}
        </AnimatePresence>

        <motion.section
          initial={reduceMotion ? false : { opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: reduceMotion ? 0 : 0.08, duration: 0.25 }}
          className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5"
        >
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <p className="text-sm font-semibold text-slate-950">未来一周</p>
              <p className="mt-1 text-xs text-slate-500">北京时间连续 7 天，不使用本地模拟天气</p>
            </div>
            <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
              <Satellite className="h-3.5 w-3.5" />
              {sourceLabel(data.forecast_source)}
            </span>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-7">
            {data.forecast.map((day, index) => (
              <ForecastCell key={day.date} day={day} isToday={index === 0} index={index} reduceMotion={reduceMotion} />
            ))}
          </div>
        </motion.section>

        <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
          <p className="text-sm font-semibold text-slate-950">未来 7 天经营风险</p>
          <p className="mt-1 text-xs text-slate-500">只呈现天气事实触发的作业提醒，不直接虚构收入或备货涨跌幅。</p>
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[
              { label: "强降雨", attention: hasRainRisk, body: hasRainRisk ? "检查外卖防漏、骑手取餐区和商场到店客流" : "未来一周未发现强降雨信号" },
              { label: "高温", attention: hasHeatRisk, body: hasHeatRisk ? "检查食材冷藏、成品等待和员工补水" : "未来一周未发现 35°C 以上高温" },
              { label: "今日节奏", attention: false, body: currentIsWeekend ? "今天是周末，结合实时订单观察高峰" : "今天是工作日，按现场客流滚动调整" },
              { label: "数据链路", attention: data.status !== "live" || data.is_stale, body: data.status === "live" && !data.is_stale ? "定位、实况和 7 日预报均已取得" : "存在缺失或过期数据，请先查看上方提醒" },
            ].map((item) => (
              <div
                key={item.label}
                className={`rounded-xl border p-3 ${item.attention ? "border-amber-200 bg-amber-50" : "border-emerald-200 bg-emerald-50"}`}
              >
                <p className={`text-sm font-semibold ${item.attention ? "text-amber-900" : "text-emerald-900"}`}>
                  {item.label} · {item.attention ? "需关注" : "正常"}
                </p>
                <p className="mt-1 text-xs leading-5 text-slate-600">{item.body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
          <p className="text-sm font-semibold text-slate-950">已核验商圈事件</p>
          {data.events.length > 0 ? (
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {data.events.map((event) => (
                <div key={`${event.date}-${event.title}`} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-medium text-slate-500">{event.date} · {event.type}</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">{event.title}</p>
                  <p className="mt-1 text-xs text-slate-600">{event.impact}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-500">暂无带可核验来源的商圈活动，不以推测补充。</p>
          )}
        </section>
      </motion.div>
    </WeatherPageFrame>
  );
}

function WeatherPageFrame({ children }: { children: React.ReactNode }) {
  return <div className="mx-auto w-full max-w-7xl pb-8">{children}</div>;
}

function ForecastCell({
  day,
  isToday,
  index,
  reduceMotion,
}: {
  day: WeatherForecast;
  isToday: boolean;
  index: number;
  reduceMotion: boolean;
}) {
  const unavailable = day.weather === "unknown";
  return (
    <motion.article
      initial={reduceMotion ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: reduceMotion ? 0 : 0.12 + index * 0.045, duration: 0.22 }}
      whileHover={reduceMotion ? undefined : { y: -2 }}
      className={`min-w-0 rounded-2xl border p-3 ${
        isToday ? "border-sky-300 bg-sky-50" : unavailable ? "border-dashed border-slate-300 bg-slate-50" : "border-slate-200 bg-white"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-slate-900">{isToday ? "今天" : day.weekday}</p>
          <p className="mt-0.5 text-[10px] text-slate-500">{day.date.slice(5).replace("-", "/")}</p>
        </div>
        {day.is_weekend && (
          <span className="rounded-full bg-rose-50 px-1.5 py-0.5 text-[9px] font-medium text-rose-700">周末</span>
        )}
      </div>
      <div className="mt-3 flex h-10 items-center">
        {unavailable ? (
          <CloudRain className="h-7 w-7 text-slate-400" />
        ) : (
          <ReactAnimatedWeather
            icon={weatherToIcon[day.weather] ?? "CLOUDY"}
            color={weatherColor[day.weather] ?? "#64748b"}
            size={38}
            animate
          />
        )}
      </div>
      <p className="mt-2 truncate text-sm font-medium text-slate-800" title={day.weather_text}>{day.weather_text || "暂不可用"}</p>
      <p className="mt-1 text-sm font-semibold text-slate-950">
        {degree(day.temp_high)} <span className="font-normal text-slate-400">/</span> {degree(day.temp_low)}
      </p>
      <p className="mt-2 min-h-8 break-words text-[10px] leading-4 text-slate-500">{day.wind || "风力暂缺"}</p>
    </motion.article>
  );
}
