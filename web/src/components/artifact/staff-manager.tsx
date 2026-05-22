"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const staff = [
  { name: "张伟", role: "主厨", salary: 6000, schedule: "全职 10:00-21:00", performance: "优", attendance: "本月迟到 2 次" },
  { name: "李芳", role: "服务员", salary: 3500, schedule: "兼职 17:00-21:00", performance: "良", attendance: "全勤" },
  { name: "王磊", role: "帮厨", salary: 4000, schedule: "全职 9:00-20:00", performance: "良", attendance: "全勤" },
];

const weekSchedule = [
  { day: "周一", chef: "张伟", server: "李芳", helper: "王磊", note: "" },
  { day: "周二", chef: "张伟", server: "—", helper: "王磊", note: "李芳休息" },
  { day: "周三", chef: "张伟", server: "李芳", helper: "王磊", note: "" },
  { day: "周四", chef: "张伟", server: "李芳", helper: "王磊", note: "" },
  { day: "周五", chef: "张伟", server: "李芳", helper: "王磊", note: "晚高峰需支援" },
  { day: "周六", chef: "张伟", server: "李芳", helper: "—", note: "王磊休息" },
  { day: "周日", chef: "张伟", server: "李芳", helper: "王磊", note: "" },
];

export function StaffManager() {
  const totalPayroll = staff.reduce((s, st) => s + st.salary, 0);

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-lg font-semibold">人员管理 · 九江店</h2>

      <div className="grid grid-cols-3 gap-3">
        <Card className="p-4"><p className="text-xs text-muted-foreground">员工数</p><p className="text-2xl font-semibold mt-1">{staff.length} 人</p></Card>
        <Card className="p-4"><p className="text-xs text-muted-foreground">月薪总额</p><p className="text-2xl font-semibold mt-1">¥{totalPayroll.toLocaleString()}</p></Card>
        <Card className="p-4"><p className="text-xs text-muted-foreground">人力成本率</p><p className="text-2xl font-semibold mt-1">{(totalPayroll / 85000 * 100).toFixed(1)}%</p></Card>
      </div>

      <div>
        <h3 className="text-sm font-medium mb-3">员工列表</h3>
        <div className="space-y-2">
          {staff.map((s) => (
            <Card key={s.name} className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{s.name}</span>
                    <Badge variant="outline" className="text-xs">{s.role}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{s.schedule}</p>
                </div>
                <div className="text-right text-sm">
                  <p>¥{s.salary.toLocaleString()}/月</p>
                  <p className="text-xs text-muted-foreground">{s.attendance}</p>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium mb-3">本周排班</h3>
        <div className="space-y-1">
          {weekSchedule.map((d) => (
            <Card key={d.day} className="p-3">
              <div className="grid grid-cols-5 text-sm items-center">
                <span className="font-medium">{d.day}</span>
                <span>👨‍🍳 {d.chef}</span>
                <span>💁 {d.server}</span>
                <span>🔪 {d.helper}</span>
                <span className="text-xs text-muted-foreground">{d.note}</span>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
