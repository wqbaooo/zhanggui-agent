# 掌柜Agent — 前端

Editorial Bento 风格的 Agent 工作台，基于 Halo Lab 品牌设计语言。

## 设计风格

- **不是**深色科技风 SaaS dashboard
- **是**暖色调编辑排版 + 厚黑边框 + 平面色块

灵感来源：Halo Lab、Pentagram、1970s Swiss Design。

## 技术栈

- Next.js 16 (Turbopack)
- React 19
- Tailwind CSS v4
- shadcn/ui (Base UI)
- Antonio + JetBrains Mono + Noto Sans SC

## 开发

```bash
npm install
npm run dev
# http://localhost:3000
```

需要后端 API 运行在 `http://localhost:8000`：

```bash
cd .. && python3 -m uvicorn server.main:app --port 8000
```

## 色板

| Token | 色值 |
|-------|------|
| Black | `#0A0A0A` |
| Cream | `#F5EFE3` |
| Green | `#0F4C3A` |
| Red | `#D9261C` |
| Mint | `#7FE05A` |

## 字体

- **Antonio 900** — Display 标题、大数字
- **JetBrains Mono 500** — `[ TAG ]` 标签、元数据
- **Noto Sans SC 500** — 中文正文

## 布局

- 黑色画布框架 `padding: 14px, border-radius: 24px`
- 12 列 Bento Grid `row-height: 64px, gap: 10px`
- 卡片 `border-radius: 20px`
- 760px 以下折叠为 6 列

## 核心组件

```
components/workspace/
├── space-shell.tsx    # 空间外壳（黑框 + 网格 + 导航）
├── bento.tsx          # Bento 卡片系统
├── command-bar.tsx    # 底部命令栏
└── cards/
    ├── hero-card.tsx      # Hero 叙事卡（8列）
    ├── status-card.tsx    # 经营状态卡（4列）
    ├── plan-card.tsx      # 项目卡（3列）
    ├── todo-card.tsx      # 待办卡（5列）
    └── weather-card.tsx   # 天气卡（4列）
```

## 构建

```bash
npm run build
```

## 相关文档

- [主项目 README](../README.md)
- [Agent 工作规则](../AGENTS.md)
