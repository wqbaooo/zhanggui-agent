"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CalendarCheck, DollarSign, GraduationCap, Plus, ShieldAlert, User, Users } from "lucide-react";
import { ModulePage, getModule } from "@/components/agent-os/ModulePage";
import { DEFAULT_PROJECT_ID, getStaff, createStaff, createWorkRecord, getWorkRecords, getWageSummary, type StaffMember, type WorkRecord, type WageDetail } from "@/lib/api";

const today = new Date().toISOString().slice(0, 7);

export default function TrainingPage() {
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [alerts, setAlerts] = useState<{ staff_id: string; name: string; expiry_date: string; days_remaining: number }[]>([]);
  const [records, setRecords] = useState<WorkRecord[]>([]);
  const [wages, setWages] = useState<WageDetail[]>([]);
  const [totalWage, setTotalWage] = useState(0);
  const [tab, setTab] = useState<"staff" | "attendance" | "wages">("staff");
  const [selectedStaff, setSelectedStaff] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [newName, setNewName] = useState("");
  const [newRole, setNewRole] = useState("员工");
  const [newWage, setNewWage] = useState("");
  const [yearMonth, setYearMonth] = useState(today);
  const [initialized, setInitialized] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const staffRes = await getStaff(DEFAULT_PROJECT_ID);
      setStaff(staffRes.staff);
      setAlerts(staffRes.health_cert_alerts);

      if (staffRes.staff.length > 0) {
        const firstId = selectedStaff || staffRes.staff[0].id;
        if (!selectedStaff) setSelectedStaff(firstId);
        const recRes = await getWorkRecords(DEFAULT_PROJECT_ID, { staff_id: firstId, limit: 30 });
        setRecords(recRes.records);
      }

      const wageRes = await getWageSummary(DEFAULT_PROJECT_ID, yearMonth);
      setWages(wageRes.breakdown);
      setTotalWage(wageRes.total_wage);
    } catch { /* offline */ }
    setInitialized(true);
  }, [selectedStaff, yearMonth]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleAddStaff = useCallback(async () => {
    if (!newName.trim()) return;
    await createStaff({ name: newName.trim(), role: newRole, hourly_wage: Number(newWage) || 0 }, DEFAULT_PROJECT_ID);
    setNewName(""); setNewWage(""); setShowAdd(false);
    fetchData();
  }, [newName, newRole, newWage, fetchData]);

  const handleSelectStaff = useCallback(async (staffId: string) => {
    setSelectedStaff(staffId);
    try {
      const recRes = await getWorkRecords(DEFAULT_PROJECT_ID, { staff_id: staffId, limit: 30 });
      setRecords(recRes.records);
    } catch { /* */ }
  }, []);

  const activeStaff = staff.find((s) => s.id === selectedStaff);

  return (
    <ModulePage module={getModule("/training")}>
        <div className="space-y-4">
          {!initialized && <div className="h-0.5 w-full animate-pulse rounded-full bg-primary/30" />}
          {/* Health cert alerts */}
          {alerts.length > 0 && (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-3">
              <div className="flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-red-600" />
                <p className="text-sm font-semibold text-red-800">健康证即将到期</p>
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {alerts.map((a) => (
                  <span key={a.staff_id} className="rounded-full bg-red-100 px-3 py-1 text-xs font-medium text-red-700">{a.name}: {a.expiry_date}（剩 {a.days_remaining} 天）</span>
                ))}
              </div>
            </div>
          )}

          {/* Tabs */}
          <div className="flex gap-1 rounded-2xl bg-white/55 p-1">
            {(["staff", "attendance", "wages"] as const).map((t) => (
              <button key={t} type="button" onClick={() => setTab(t)} className={`flex-1 rounded-xl px-3 py-2 text-sm font-medium transition-colors ${tab === t ? "bg-on-background text-inverse-on-surface" : "text-on-surface-variant hover:text-on-background"}`}>{t === "staff" ? "员工" : t === "attendance" ? "考勤" : "工资"}</button>
            ))}
          </div>

          {tab === "staff" && (
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-on-surface-variant">{staff.length} 人在岗</p>
                <button type="button" onClick={() => setShowAdd(!showAdd)} className="inline-flex items-center gap-1 rounded-full bg-primary px-3 py-1 text-xs font-medium text-on-primary"><Plus className="h-3 w-3" /> 加员工</button>
              </div>

              {showAdd && (
                <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-white/45 bg-white/55 p-3">
                  <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="姓名" className="min-w-0 flex-1 rounded-xl border border-white/50 bg-white/70 px-3 py-1.5 text-sm outline-none focus:border-primary/50" />
                  <select value={newRole} onChange={(e) => setNewRole(e.target.value)} className="rounded-xl border border-white/50 bg-white/70 px-2 py-1.5 text-sm outline-none">
                    {["员工", "店长", "兼职"].map((r) => (<option key={r}>{r}</option>))}
                  </select>
                  <input value={newWage} onChange={(e) => setNewWage(e.target.value)} placeholder="时薪(元)" type="number" className="w-24 rounded-xl border border-white/50 bg-white/70 px-3 py-1.5 text-sm outline-none" />
                  <button type="button" onClick={handleAddStaff} disabled={!newName.trim()} className="rounded-xl bg-primary px-3 py-1.5 text-sm font-semibold text-on-primary disabled:opacity-50">确认</button>
                </div>
              )}

              {initialized && staff.length === 0 ? (
                <p className="rounded-2xl bg-white/45 p-4 text-sm text-on-surface-variant">还没有员工档案。先添加老板自己和员工的信息。</p>
              ) : staff.length > 0 ? (
                <div className="grid gap-2 md:grid-cols-2">
                  {staff.map((s) => (
                    <button key={s.id} type="button" onClick={() => handleSelectStaff(s.id)} className={`rounded-2xl border p-4 text-left transition-colors ${selectedStaff === s.id ? "border-primary/50 bg-primary-container/45" : "border-white/45 bg-white/55 hover:bg-white/80"}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-on-background">{s.name}</p>
                          <p className="mt-0.5 text-xs text-on-surface-variant">{s.role}{s.hire_date ? ` · ${s.hire_date}入职` : ""}</p>
                        </div>
                        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${s.status === "在岗" ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-700"}`}>{s.status}</span>
                      </div>
                      {(s.hourly_wage > 0 || s.monthly_base > 0) && (
                        <p className="mt-2 text-xs text-on-surface-variant">
                          时薪 ¥{s.hourly_wage}{s.monthly_base > 0 ? ` / 底薪 ¥${s.monthly_base}` : ""}
                        </p>
                      )}
                      {s.skills.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {s.skills.map((skill) => (<span key={skill} className="rounded-full bg-white/70 px-2 py-0.5 text-[10px] text-on-surface-variant">{skill}</span>))}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          )}

          {tab === "attendance" && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <p className="text-xs text-on-surface-variant">员工考勤</p>
                {staff.filter((s) => s.status === "在岗").map((s) => (
                  <button key={s.id} type="button" onClick={() => handleSelectStaff(s.id)} className={`rounded-full px-3 py-1 text-xs transition-colors ${selectedStaff === s.id ? "bg-on-background text-inverse-on-surface" : "border border-white/45 bg-white/55 text-on-surface-variant"}`}>{s.name}</button>
                ))}
              </div>

              {initialized && records.length === 0 ? (
                <p className="rounded-2xl bg-white/45 p-4 text-sm text-on-surface-variant">{activeStaff ? `${activeStaff.name} 还没有考勤记录。` : "先选一位员工。"}</p>
              ) : records.length > 0 ? (
                <div className="space-y-2">
                  {records.slice(0, 14).map((r) => (
                    <div key={r.id} className="flex items-center justify-between gap-3 rounded-2xl border border-white/45 bg-white/55 px-4 py-3">
                      <div>
                        <p className="text-sm font-semibold text-on-background">{r.date}</p>
                        <p className="mt-0.5 text-xs text-on-surface-variant">{r.shift}</p>
                      </div>
                      <div className="text-right text-xs text-on-surface-variant">
                        <span>{r.hours}h</span>
                        {r.overtime_hours > 0 && <span className="ml-2 text-amber-600">+{r.overtime_hours}h 加班</span>}
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          )}

          {tab === "wages" && (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <input type="month" value={yearMonth} onChange={(e) => setYearMonth(e.target.value)} className="rounded-xl border border-white/50 bg-white/70 px-3 py-1.5 text-sm outline-none" />
                <span className="text-lg font-semibold text-on-background">合计 ¥{totalWage.toLocaleString()}</span>
              </div>

              {initialized && wages.length === 0 ? (
                <p className="rounded-2xl bg-white/45 p-4 text-sm text-on-surface-variant">该月还没有考勤数据。</p>
              ) : wages.length > 0 ? (
                <div className="grid gap-3 md:grid-cols-2">
                  {wages.map((w) => (
                    <div key={w.staff_id} className="rounded-2xl border border-white/45 bg-white/55 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-on-background">{w.staff_name}</p>
                        <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary">¥{w.total_wage.toLocaleString()}</span>
                      </div>
                      <div className="mt-2 grid grid-cols-3 gap-2 text-center">
                        <div className="rounded-xl bg-white/60 px-2 py-1.5">
                          <p className="text-[10px] text-on-surface-variant">出勤</p>
                          <p className="text-sm font-semibold text-on-background">{w.work_days}天</p>
                        </div>
                        <div className="rounded-xl bg-white/60 px-2 py-1.5">
                          <p className="text-[10px] text-on-surface-variant">工时</p>
                          <p className="text-sm font-semibold text-on-background">{w.total_hours}h</p>
                        </div>
                        <div className="rounded-xl bg-white/60 px-2 py-1.5">
                          <p className="text-[10px] text-on-surface-variant">加班</p>
                          <p className="text-sm font-semibold text-on-background">{w.total_overtime}h</p>
                        </div>
                      </div>
                      {w.hourly_wage > 0 && <p className="mt-2 text-xs text-on-surface-variant">时薪 ¥{w.hourly_wage}{w.monthly_base > 0 ? ` + 底薪 ¥${w.monthly_base}` : ""}</p>}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          )}
        </div>
    </ModulePage>
  );
}
