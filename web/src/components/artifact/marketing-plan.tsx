"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface ChannelPlan {
  channel: string;
  icon: string;
  budget: string;
  roi: string;
  actions: { title: string; detail: string }[];
}

const marketingPlan: ChannelPlan[] = [
  {
    channel: "抖音同城",
    icon: "🎵",
    budget: "投流 ¥500-1500/月 + 达人 ¥1000/位",
    roi: "预期曝光 3-5万 / 月",
    actions: [
      { title: "短视频内容", detail: "制作过程解压视频 + 顾客好评实录，每周 3-5 条，挂 POI 定位和团购链接" },
      { title: "达人探店", detail: "同城美食达人 1-2 位/月，预算 500-1000 元/位，要求挂团购 + POI" },
      { title: "DOU+ 投流", detail: "针对 3km 内 18-35 岁女性，高峰时段（11:30/17:30）投放，ROI ＞ 1:3 时加投" },
      { title: "团购设计", detail: "招牌章鱼烧 ¥25 → 团购价 ¥19.9，双人套餐 ¥45 → ¥35，核销率目标 60%" },
    ],
  },
  {
    channel: "小红书",
    icon: "📕",
    budget: "内容制作 ¥300/月",
    roi: "自然流量 + 搜索占位",
    actions: [
      { title: "种草笔记", detail: "每周 2 篇图文笔记：'南昌最好吃的章鱼烧'、'红谷滩宝藏小吃'，带位置标签" },
      { title: "关键词占位", detail: "抢占「南昌章鱼烧」「红谷滩小吃」「南昌美食推荐」搜索排名" },
      { title: "UGC 激励", detail: "顾客发小红书带定位 → 免费加料一份，低成本撬动真实口碑" },
    ],
  },
  {
    channel: "美团团购",
    icon: "🛵",
    budget: "平台佣金 5-8%",
    roi: "新店流量扶持 30 天",
    actions: [
      { title: "新店入驻", detail: "上传专业菜品图（投入 ¥500 拍摄），转化率提升 30%+" },
      { title: "满减活动", detail: "满 30 减 5，新客立减 8 元，配合平台新店流量包" },
      { title: "评价管理", detail: "差评 24 小时内回复处理，好评引导（送小料），评分维持 4.5+" },
    ],
  },
  {
    channel: "私域运营",
    icon: "💬",
    budget: "几乎零成本",
    roi: "复购率提升 25%+",
    actions: [
      { title: "微信群", detail: "到店顾客扫码入群，每日发「今日特供」+ 限量福利，沉淀 200+ 活跃用户" },
      { title: "朋友圈", detail: "每日 1-2 条真实内容：制作花絮、顾客故事，不硬广，场景化触达" },
      { title: "集章卡", detail: "买 10 送 1，纸质集章卡，简单有效，适合低线市场的复购利器" },
      { title: "储值锁定", detail: "充 200 送 30，充 500 送 100，锁定现金流 + 提升到店频次" },
    ],
  },
];

export function MarketingPlan() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">开业营销方案 · 大口章鱼烧</h2>
        <Badge variant="secondary">4 渠道覆盖</Badge>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <Card className="p-3 text-center">
          <p className="text-xs text-muted-foreground">抖音投流</p>
          <p className="text-lg font-semibold">¥1,500</p>
          <p className="text-xs text-muted-foreground">/月</p>
        </Card>
        <Card className="p-3 text-center">
          <p className="text-xs text-muted-foreground">美团佣金</p>
          <p className="text-lg font-semibold">5-8%</p>
          <p className="text-xs text-muted-foreground">营业额</p>
        </Card>
        <Card className="p-3 text-center">
          <p className="text-xs text-muted-foreground">小红书</p>
          <p className="text-lg font-semibold">¥300</p>
          <p className="text-xs text-muted-foreground">/月</p>
        </Card>
        <Card className="p-3 text-center">
          <p className="text-xs text-muted-foreground">私域</p>
          <p className="text-lg font-semibold text-green-700">¥0</p>
          <p className="text-xs text-muted-foreground">低成本</p>
        </Card>
      </div>

      <div className="space-y-4">
        {marketingPlan.map((channel) => (
          <Card key={channel.channel} className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-lg">{channel.icon}</span>
              <span className="font-medium">{channel.channel}</span>
              <Badge variant="outline" className="text-xs">{channel.budget}</Badge>
              <span className="text-xs text-muted-foreground ml-auto">{channel.roi}</span>
            </div>
            <div className="space-y-2">
              {channel.actions.map((action) => (
                <div key={action.title} className="pl-6 border-l-2 border-muted">
                  <p className="text-sm font-medium">{action.title}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{action.detail}</p>
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>

      <Card className="p-4 bg-accent/30">
        <p className="text-sm font-medium mb-2">30 天开业活动时间线</p>
        <div className="text-sm text-muted-foreground space-y-1">
          <p>D-14 · 抖音账号装修 + 3 条预热视频储备</p>
          <p>D-7 · 美团/点评店铺入驻 + 团购上架审核</p>
          <p>D-3 · 朋友圈/微信群转发集赞活动启动</p>
          <p>D-1 · 试营业体验日（邀请亲友 + 收集反馈）</p>
          <p>D-Day · 正式开业：买一送一 + 抖音直播 + 到店扫码入群</p>
          <p>D+7 · 首周数据复盘：调整投流策略 + 优化团购价格</p>
          <p>D+15 · 达人探店视频上线 + 小红书种草笔记发布</p>
          <p>D+30 · 满月复盘：各渠道 ROI 分析 + 下月营销日历</p>
        </div>
      </Card>
    </div>
  );
}
