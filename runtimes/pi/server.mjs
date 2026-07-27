import http from "node:http";
import { Agent } from "@earendil-works/pi-agent-core";
import { Type, createModels } from "@earendil-works/pi-ai";
import { deepseekProvider } from "@earendil-works/pi-ai/providers/deepseek";

const port = Number(process.env.PI_AGENT_PORT || 8653);
const backendBase = (process.env.ZHANGGUI_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
const projectId = process.env.ZHANGGUI_PROJECT_ID || "xinyu-hengtai-dakou";
const modelId = process.env.PI_AGENT_MODEL || "deepseek-v4-pro";
const apiKey = process.env.PI_AGENT_API_KEY || "";

const models = createModels();
models.setProvider(deepseekProvider());
const model = models.getModel("deepseek", modelId);
if (!model) throw new Error(`Pi runtime cannot find DeepSeek model: ${modelId}`);

const sessions = new Map();

async function getJson(path) {
  const response = await fetch(`${backendBase}${path}`, { signal: AbortSignal.timeout(5000) });
  if (!response.ok) throw new Error(`Store API ${response.status}`);
  return response.json();
}

function readOnlyTools(allowedCapabilities) {
  const tools = [];
  if (allowedCapabilities.includes("finance")) {
    tools.push({
      name: "get_finance_overview",
      label: "读取财务概况",
      description: "只读查询当前门店的财务概况；不能写账或修改记录。",
      parameters: Type.Object({
        start: Type.Optional(Type.String()),
        end: Type.Optional(Type.String()),
      }),
      execute: async (_id, params) => ({
        content: [{
          type: "text",
          text: JSON.stringify(await getJson(
            `/api/projects/${projectId}/finance/overview?start=${encodeURIComponent(params.start || "2026-07-01")}&end=${encodeURIComponent(params.end || "2026-07-31")}`
          )),
        }],
        details: { source: "store-finance-api", readOnly: true },
      }),
    });
  }
  if (allowedCapabilities.includes("inventory")) {
    tools.push({
      name: "get_inventory_summary",
      label: "读取库存概况",
      description: "只读查询当前门店库存概况；不能修改盘点或采购。",
      parameters: Type.Object({}),
      execute: async () => ({
        content: [{
          type: "text",
          text: JSON.stringify(await getJson(`/api/projects/${projectId}/skus/inventory-summary`)),
        }],
        details: { source: "store-inventory-api", readOnly: true },
      }),
    });
  }
  return tools;
}

function getSession(sessionId) {
  if (sessions.has(sessionId)) return sessions.get(sessionId);
  const record = { allowedToolNames: new Set(), queue: Promise.resolve() };
  const agent = new Agent({
    initialState: {
      systemPrompt: "你是掌柜Agent。只回答老板当前的问题；普通寒暄必须简短自然，不主动汇报财务。",
      model,
      thinkingLevel: "medium",
      tools: [],
      messages: [],
    },
    streamFn: models.streamSimple.bind(models),
    sessionId,
    transformContext: async (messages) => messages.slice(-12),
    beforeToolCall: async ({ toolCall }) => {
      if (!record.allowedToolNames.has(toolCall.name)) {
        return { block: true, reason: `本轮未授权工具：${toolCall.name}` };
      }
    },
  });
  record.agent = agent;
  sessions.set(sessionId, record);
  return record;
}

async function runTurn(body, sessionId) {
  const context = body.zhanggui_context || {};
  const allowed = Array.isArray(context.allowed_tools) ? context.allowed_tools : [];
  const record = getSession(sessionId);
  record.agent.state.tools = readOnlyTools(allowed);
  record.allowedToolNames = new Set(record.agent.state.tools.map((tool) => tool.name));
  record.agent.state.systemPrompt = [
    "你是新余恒太城五楼大口章鱼烧唯一对外的掌柜Agent，用户是老板。",
    "先理解当前话语再决定是否分析。寒暄不调用工具、不输出经营报告。",
    "只使用本轮提供的事实和只读工具；不知道就明确说不知道。",
    "销售收入、平台结算、银行卡到账、老板投入和个人消费必须分开。",
    "不得写账、改库存或执行外部动作。",
    `本轮意图：${context.intent || "business_question"}`,
    `本轮可信上下文：${JSON.stringify(context)}`,
  ].join("\n");
  const userMessage = [...(body.messages || [])].reverse().find((item) => item.role === "user")?.content;
  if (!userMessage) throw new Error("Missing user message");

  let text = "";
  const unsubscribe = record.agent.subscribe((event) => {
    if (event.type === "message_update" && event.assistantMessageEvent?.type === "text_delta") {
      text += event.assistantMessageEvent.delta;
    }
  });
  try {
    await record.agent.prompt(String(userMessage));
  } finally {
    unsubscribe();
  }
  if (!text.trim()) throw new Error("Pi Agent returned no text");
  return text.trim();
}

function sendJson(response, status, payload) {
  response.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  response.end(JSON.stringify(payload));
}

const server = http.createServer(async (request, response) => {
  if (request.method === "GET" && request.url === "/health") {
    return sendJson(response, 200, { status: "ok", runtime: "pi-agent-core", model: modelId });
  }
  if (request.method !== "POST" || request.url !== "/v1/chat/completions") {
    return sendJson(response, 404, { error: "not_found" });
  }
  if (apiKey && request.headers.authorization !== `Bearer ${apiKey}`) {
    return sendJson(response, 401, { error: "unauthorized" });
  }
  try {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    const body = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    const sessionId = String(request.headers["x-agent-session-id"] || "default");
    const record = getSession(sessionId);
    const task = record.queue.then(() => runTurn(body, sessionId));
    record.queue = task.catch(() => undefined);
    const text = await task;
    return sendJson(response, 200, {
      id: `pi-${Date.now()}`,
      model: modelId,
      choices: [{ message: { role: "assistant", content: text }, finish_reason: "stop" }],
    });
  } catch (error) {
    return sendJson(response, 500, { error: error instanceof Error ? error.message : "pi_runtime_failed" });
  }
});

server.listen(port, "127.0.0.1", () => {
  process.stdout.write(`Pi Agent runtime listening on http://127.0.0.1:${port}\n`);
});
