"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { CloudRain, Droplets, MapPin, Thermometer, Wind } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { getWeather, type WeatherForecast, type WeatherResponse } from "@/lib/api";

const ReactAnimatedWeather = dynamic(() => import("react-animated-weather"), { ssr: false });

const weatherToIcon: Record<string, string> = {
  sunny: "CLEAR_DAY", cloudy: "PARTLY_CLOUDY_DAY", overcast: "CLOUDY",
  light_rain: "RAIN", heavy_rain: "RAIN", thunderstorm: "RAIN",
  snow: "SNOW", fog: "FOG",
};

const weatherColor: Record<string, string> = {
  sunny: "#f59e0b", cloudy: "#94a3b8", overcast: "#64748b",
  light_rain: "#38bdf8", heavy_rain: "#2563eb", thunderstorm: "#6366f1",
  snow: "#e0f2fe", fog: "#cbd5e1",
};

const defaultData: WeatherResponse = {
  city: "新余", district: "渝水区", location: "恒太城",
  current: { weather: "sunny", temperature: 28, temp_high: 32, temp_low: 24, humidity: 65, wind: "2级", tips: ["数据加载中..."] },
  forecast: Array.from({ length: 7 }, (_, i) => ({
    date: "", weekday: ["周一","周二","周三","周四","周五","周六","周日"][i],
    weather: "sunny" as const, temp_high: 30, temp_low: 22,
    humidity: 60, wind: "2级", is_weekend: i >= 5, tips: [],
  })),
  events: [],
  updated_at: "",
};

export default function CalendarPage() {
  const [data, setData] = useState<WeatherResponse | null>(null);
  const [initialized, setInitialized] = useState(false);

  const fetchWeather = useCallback(async () => {
    try { const res = await getWeather(); setData(res); } catch { /* */ }
    setInitialized(true);
  }, []);

  useEffect(() => { fetchWeather(); const i = setInterval(fetchWeather, 600000); return () => clearInterval(i); }, [fetchWeather]);

  const d = data || defaultData;

  const module = getModule("/calendar");

  return (
    <ModulePage module={module}>
      <div className="space-y-4">
        {!initialized && <div className="h-0.5 w-full animate-pulse rounded-full bg-primary/30" />}

        {/* 当前天气大卡 */}
        <div className="relative overflow-hidden rounded-3xl border border-white/45 bg-gradient-to-br from-sky-100/30 via-white/40 to-amber-50/20 p-6 backdrop-blur-xl">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-4">
              <div className="flex h-24 w-24 items-center justify-center">
                <ReactAnimatedWeather
                  icon={weatherToIcon[d.current.weather] ?? "PARTLY_CLOUDY_DAY"}
                  color={weatherColor[d.current.weather] ?? "#94a3b8"}
                  size={96}
                  animate
                />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <MapPin className="h-3.5 w-3.5 text-on-surface-variant" />
                  <p className="text-xs text-on-surface-variant">{d.city}·{d.district} · {d.location}</p>
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-6xl font-bold tracking-tight text-on-background">{d.current.temperature}°</span>
                  <span className="text-sm text-on-surface-variant">{d.current.temp_high}° / {d.current.temp_low}°</span>
                </div>
                <div className="mt-2 flex items-center gap-3 text-xs text-on-surface-variant">
                  <span className="inline-flex items-center gap-1"><Droplets className="h-3 w-3" />{d.current.humidity}%</span>
                  <span className="inline-flex items-center gap-1"><Wind className="h-3 w-3" />{d.current.wind}</span>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              {d.current.tips.map((tip, i) => (
                <span key={i} className="rounded-full bg-white/60 px-3 py-1 text-xs font-medium text-on-background backdrop-blur-sm">{tip}</span>
              ))}
            </div>
          </div>
        </div>

        {/* 7日预报 */}
        <div className="grid grid-cols-7 gap-2">
          {d.forecast.map((day, i) => (
            <ForecastCell key={i} day={day} isToday={i === 0} />
          ))}
        </div>

        {/* 商圈事件 */}
        <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
          <p className="text-xs font-medium text-on-surface-variant">商圈事件</p>
          {d.events.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {d.events.map((e) => (
                <div key={e.date} className="flex items-center gap-3 rounded-xl bg-white/55 px-4 py-3 min-w-[220px]">
                  <div className="shrink-0 rounded-lg bg-amber-100 px-2 py-1 text-center">
                    <p className="text-[10px] font-semibold text-amber-800">{e.date.slice(5)}</p>
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-on-background">{e.title}</p>
                    <p className="mt-0.5 text-[10px] text-on-surface-variant">{e.type}</p>
                    <p className="mt-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] text-emerald-700 inline-block">{e.impact}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="mt-3 text-sm text-on-surface-variant">{initialized ? "暂无商圈事件" : ""}</p>}
        </div>

        {/* 客流标签 */}
        <div className="rounded-2xl border border-white/45 bg-white/42 p-4">
          <p className="text-xs font-medium text-on-surface-variant">客流影响</p>
          <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
            {[
              { label: "高温", active: d.current.temperature > 35, body: "备冷饮冷食，减少热汤" },
              { label: "降雨", active: ["light_rain","heavy_rain","thunderstorm"].includes(d.current.weather), body: "外卖上调，堂食降排班" },
              { label: "周末高峰", active: d.forecast[0]?.is_weekend ?? false, body: "全员上岗，备货上调" },
              { label: "暑假", active: new Date().getMonth() >= 6 && new Date().getMonth() <= 7, body: "工作日也有学生客流" },
            ].map((tag) => (
              <div key={tag.label} className={`rounded-2xl border p-3 transition-colors ${tag.active ? "border-amber-300 bg-amber-50" : "border-white/45 bg-white/38 opacity-60"}`}>
                <p className={`text-sm font-semibold ${tag.active ? "text-amber-800" : "text-on-surface-variant"}`}>{tag.label}{tag.active ? " ✓" : ""}</p>
                <p className="mt-1 text-[11px] leading-relaxed text-on-surface-variant">{tag.body}</p>
              </div>
            ))}
          </div>
        </div>

        {initialized && !data && (
          <div className="rounded-2xl border border-dashed border-white/60 bg-white/35 p-8 text-center">
            <CloudRain className="mx-auto h-8 w-8 text-on-surface-variant/40" />
            <p className="mt-3 text-sm font-medium text-on-background">天气数据暂不可用</p>
          </div>
        )}
      </div>
    </ModulePage>
  );
}

function ForecastCell({ day, isToday }: { day: WeatherForecast; isToday: boolean }) {
  return (
    <div className={`rounded-2xl border p-2.5 text-center transition-colors ${isToday ? "border-primary/50 bg-primary-container/45" : "border-white/45 bg-white/42"}`}>
      <p className="text-[10px] font-medium text-on-surface-variant">{isToday ? "今天" : day.weekday}</p>
      <div className="mx-auto mt-1.5 flex h-10 w-10 items-center justify-center">
        <ReactAnimatedWeather
          icon={weatherToIcon[day.weather] ?? "PARTLY_CLOUDY_DAY"}
          color={weatherColor[day.weather] ?? "#94a3b8"}
          size={40}
          animate
        />
      </div>
      <p className="mt-1 text-sm font-bold text-on-background">{day.temp_high}°</p>
      <p className="text-[10px] text-on-surface-variant">{day.temp_low}°</p>
      {day.is_weekend && <span className="mt-1 inline-block rounded-full bg-rose-50 px-1.5 py-0.5 text-[8px] font-medium text-rose-600">周末</span>}
    </div>
  );
}
