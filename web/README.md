# 掌柜Agent — 前端

新余恒太城大口章鱼烧的 AI 单店经营 Agent 工作台。

## 设计风格

- **不是**通用餐饮 SaaS 或加盟顾问后台
- **是**掌柜总控台：对话/截图主入口、经营状态、证据、待确认草稿和今日动作

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
# http://localhost:3005
```

需要后端 API 运行在 `http://localhost:8000`：

```bash
cd .. && python3 -m uvicorn server.main:app --port 8000
```

## 当前默认对象

- 项目 ID：`xinyu-hengtai-dakou`
- 门店：新余恒太城五楼大口章鱼烧
- 后端：`http://localhost:8000`
- 前端：`http://localhost:3005/overview`

## 构建

```bash
npm run build
```

## 相关文档

- [主项目 README](../README.md)
- [Agent 工作规则](../AGENTS.md)
