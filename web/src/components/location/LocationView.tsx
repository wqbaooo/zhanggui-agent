"use client";

import { useMemo } from "react";
import { fmtMoney } from "@/domain/calculations";
import { calcRentPressureIndex } from "@/domain/calculations";
import { assessLocationRisks, generateScoutChecklist } from "@/domain/riskRules";
import { mockLocation, mockInvestment } from "@/data/mockProject";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { SectionHeader } from "@/components/shared/SectionHeader";
import { MetricCard } from "@/components/shared/MetricCard";
import { Tag } from "@/components/shared/DataDisplay";
import { RiskList } from "@/components/shared/RiskList";

export function LocationView() {
  const loc = mockLocation;
  const rentPressure = calcRentPressureIndex(loc.monthlyRent, mockInvestment.averageDailyOrders * mockInvestment.averageOrderValue);
  const risks = useMemo(() => assessLocationRisks(mockLocation, mockInvestment), []);
  const scoutChecklist = useMemo(() => generateScoutChecklist(), []);

  return (
    <div className="space-y-6">
      <SectionHeader title="选址评估" subtitle={`${loc.city} ${loc.district} · ${loc.businessAreaType}`} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <MetricCard label="面积" value={`${loc.areaSqm}㎡`} />
        <MetricCard label="月租金" value={fmtMoney(loc.monthlyRent)} />
        <MetricCard label="租金压力" value={`${rentPressure}%`} negative={rentPressure > 20} trend={rentPressure > 20 ? "up" : "down"} />
        <MetricCard label="500m内竞品" value={`${loc.competitorCount500m}家`} negative={loc.competitorCount500m > 8} />
        <MetricCard label="工作日人流" value={`${loc.weekdayFootTraffic}/天`} />
        <MetricCard label="门头可见度" value={`${loc.storefrontVisibility}/5`} negative={loc.storefrontVisibility <= 2} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>周边环境</CardTitle>
          <CardDescription>步行范围内设施分布</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {loc.nearCommunity && <Tag label="社区" />}
          {loc.nearOffice && <Tag label="写字楼" />}
          {loc.nearSchool && <Tag label="学校" />}
          {loc.nearMall && <Tag label="商场" />}
          {loc.nearSubway && <Tag label="地铁" />}
          {loc.nearHospital && <Tag label="医院" />}
          <Tag label={`外卖适配 ${loc.deliveryFit}/5`} />
        </CardContent>
      </Card>

      <RiskList risks={risks} title="选址风险" />

      <Card className="border-emerald-400/30 bg-emerald-50/30">
        <CardHeader>
          <CardTitle className="text-emerald-800">实地蹲点观察清单</CardTitle>
          <CardDescription>建议在以下时段实地观察并记录真实数据</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-1.5">
            {scoutChecklist.map((item, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className="flex size-5 shrink-0 items-center justify-center rounded border border-emerald-300 text-[10px] text-emerald-600 font-mono">{i + 1}</span>
                <span className="text-xs text-gray-600">{item}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
