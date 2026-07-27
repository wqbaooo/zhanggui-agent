"use client";

import { useState, useCallback, useEffect } from "react";
import { API_BASE, DEFAULT_PROJECT_ID } from "@/lib/api";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  toolCalls?: Array<{ name: string; status: "running" | "done"; output?: string }>;
  run?: ChatRunMetadata;
}

export interface ChatRunMetadata {
  status: "answered" | "needs_input" | "conflict" | "conversation";
  intent?: "social" | "business_question" | "business_action";
  allowed_tools?: string[];
  domains: string[];
  consulted_modules: string[];
  gaps: string[];
  conflict_count: number;
  model_provider?: string;
  model?: string;
  guardrail_applied?: boolean;
  answer_source?: string;
  requested_runtime?: string;
  runtime_fallback?: boolean;
  runtime_fallback_reason?: string | null;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: string;
  updatedAt: string;
  projectId: string;
  scope?: string;
  runtime?: string;
}

export interface AgentRuntimeStatus {
  selected: "trusted" | "hermes" | string;
  available: boolean;
  active: boolean;
  label: string;
  model?: string;
  fallback?: string | null;
}

const STORAGE_KEY = "store-agent-chat-sessions";
const ACTIVE_KEY = "store-agent-chat-active-session";

function loadSessions(): ChatSession[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as ChatSession[];
  } catch {
    return [];
  }
}

function saveSessions(sessions: ChatSession[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch {
    // ignore
  }
}

function loadActiveSessionId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACTIVE_KEY);
}

function saveActiveSessionId(id: string | null) {
  if (typeof window === "undefined") return;
  if (id) {
    localStorage.setItem(ACTIVE_KEY, id);
  } else {
    localStorage.removeItem(ACTIVE_KEY);
  }
}

function generateSessionTitle(firstMessage: string): string {
  const trimmed = firstMessage.trim();
  if (!trimmed) return "新对话";
  return trimmed.length > 20 ? trimmed.slice(0, 20) + "…" : trimmed;
}

async function fetchBackendSessions(): Promise<ChatSession[]> {
  const response = await fetch(
    `${API_BASE}/api/projects/${DEFAULT_PROJECT_ID}/agent/sessions?scope=master`,
    { cache: "no-store" }
  );
  if (!response.ok) throw new Error(`历史记录加载失败：${response.status}`);
  const payload = await response.json();
  return Array.isArray(payload.sessions) ? payload.sessions : [];
}

async function persistSession(session: ChatSession, includeMessages = false) {
  const response = await fetch(
    `${API_BASE}/api/projects/${DEFAULT_PROJECT_ID}/agent/sessions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: session.id,
        title: session.title,
        scope: "master",
        messages: includeMessages ? session.messages : [],
      }),
    }
  );
  if (!response.ok) throw new Error(`对话保存失败：${response.status}`);
}

export function useAIChat() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<AgentRuntimeStatus | null>(null);

  useEffect(() => {
    const loaded = loadSessions();
    setSessions(loaded);
    const activeId = loadActiveSessionId();
    if (activeId && loaded.some((s) => s.id === activeId)) {
      setActiveSessionId(activeId);
    } else if (loaded.length > 0) {
      setActiveSessionId(loaded[0].id);
    }

    let cancelled = false;
    void (async () => {
      try {
        const runtimeResponse = await fetch(`${API_BASE}/api/agent/runtime`, { cache: "no-store" });
        if (runtimeResponse.ok && !cancelled) {
          setRuntimeStatus(await runtimeResponse.json());
        }
        let backendSessions = await fetchBackendSessions();
        if (backendSessions.length === 0 && loaded.length > 0) {
          await Promise.all(loaded.map((session) => persistSession(session, true)));
          backendSessions = await fetchBackendSessions();
        }
        if (cancelled || backendSessions.length === 0) return;
        setSessions(backendSessions);
        saveSessions(backendSessions);
        const currentId = loadActiveSessionId();
        const nextId = currentId && backendSessions.some((session) => session.id === currentId)
          ? currentId
          : backendSessions[0].id;
        setActiveSessionId(nextId);
        saveActiveSessionId(nextId);
      } catch {
        // Keep local history available while the backend is offline.
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const activeSession = sessions.find((s) => s.id === activeSessionId) || null;
  const messages = activeSession?.messages || [];

  const persistSessions = useCallback((updated: ChatSession[]) => {
    setSessions(updated);
    saveSessions(updated);
  }, []);

  const setActiveSession = useCallback((id: string | null) => {
    setActiveSessionId(id);
    saveActiveSessionId(id);
  }, []);

  const createNewSession = useCallback(() => {
    const newSession: ChatSession = {
      id: `sess_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      title: "新对话",
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      projectId: DEFAULT_PROJECT_ID,
    };
    const updated = [newSession, ...sessions];
    persistSessions(updated);
    setActiveSession(newSession.id);
    setError(null);
    void persistSession(newSession).catch(() => {
      // The send endpoint will create it later if the backend is temporarily offline.
    });
    return newSession;
  }, [sessions, persistSessions, setActiveSession]);

  const deleteSession = useCallback((id: string) => {
    const updated = sessions.filter((s) => s.id !== id);
    persistSessions(updated);
    if (activeSessionId === id) {
      if (updated.length > 0) {
        setActiveSession(updated[0].id);
      } else {
        setActiveSession(null);
      }
    }
    void fetch(`${API_BASE}/api/projects/${DEFAULT_PROJECT_ID}/agent/sessions/${id}`, {
      method: "DELETE",
    }).catch(() => undefined);
  }, [sessions, activeSessionId, persistSessions, setActiveSession]);

  const updateSessionMessages = useCallback((sessionId: string, updater: (prev: ChatMessage[]) => ChatMessage[], titleUpdate?: string) => {
    const updated = sessions.map((s) => {
      if (s.id !== sessionId) return s;
      const newMessages = updater(s.messages);
      return {
        ...s,
        messages: newMessages,
        title: titleUpdate || s.title,
        updatedAt: new Date().toISOString(),
      };
    });
    persistSessions(updated);
  }, [sessions, persistSessions]);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isStreaming) return;

    let sessionId = activeSessionId;
    let workingSessions = sessions;
    const isNewSession = !sessionId || messages.length === 0;

    if (isNewSession) {
      const newSession: ChatSession = {
        id: `sess_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        title: generateSessionTitle(content),
        messages: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        projectId: DEFAULT_PROJECT_ID,
      };
      sessionId = newSession.id;
      workingSessions = [newSession, ...sessions];
      setActiveSession(sessionId);
    }

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: content.trim(),
      timestamp: new Date().toISOString(),
    };

    const assistantMsg: ChatMessage = {
      id: `assistant-${Date.now()}`,
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
      toolCalls: [],
    };

    const appendMessages = (prev: ChatSession[]): ChatSession[] =>
      prev.map((s) => {
        if (s.id !== sessionId) return s;
        return {
          ...s,
          messages: [...s.messages, userMsg, assistantMsg],
          title: isNewSession ? generateSessionTitle(content) : s.title,
          updatedAt: new Date().toISOString(),
        };
      });

    workingSessions = appendMessages(workingSessions);
    persistSessions(workingSessions);

    setIsStreaming(true);
    setError(null);
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 60_000);

    try {
      const res = await fetch(`${API_BASE}/api/chat/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: content.trim(),
          project_id: DEFAULT_PROJECT_ID,
          session_id: sessionId,
          scope: "master",
          client_message_id: userMsg.id,
        }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => null);
        throw new Error(payload?.detail || `服务返回 ${res.status}`);
      }
      const data = await res.json();
      const response = String(data.response || "").trim();
      if (!response) throw new Error("Agent 没有返回内容");

      const updateAssistant = (prev: ChatSession[]): ChatSession[] =>
        prev.map((s) => {
          if (s.id !== sessionId) return s;
          return {
            ...s,
            messages: s.messages.map((m) =>
              m.id === assistantMsg.id
                ? { ...m, content: response, run: data.meta as ChatRunMetadata | undefined }
                : m
            ),
            updatedAt: new Date().toISOString(),
          };
        });

      persistSessions(updateAssistant(workingSessions));
    } catch (err) {
      const errorMsg = err instanceof DOMException && err.name === "AbortError"
        ? "处理超过 60 秒，已停止等待。你可以重新发送，已输入的内容不会丢失。"
        : err instanceof Error ? err.message : "请求失败";
      setError(errorMsg);

      const updateError = (prev: ChatSession[]): ChatSession[] =>
        prev.map((s) => {
          if (s.id !== sessionId) return s;
          return {
            ...s,
            messages: s.messages.map((m) =>
              m.id === assistantMsg.id
                ? { ...m, content: `这次没有处理完成：${errorMsg}` }
                : m
            ),
            updatedAt: new Date().toISOString(),
          };
        });

      persistSessions(updateError(workingSessions));
    } finally {
      window.clearTimeout(timeout);
      setIsStreaming(false);
      void fetch(`${API_BASE}/api/agent/runtime`, { cache: "no-store" })
        .then(async (response) => {
          if (response.ok) setRuntimeStatus(await response.json());
        })
        .catch(() => undefined);
    }
  }, [isStreaming, activeSessionId, sessions, messages.length, persistSessions, setActiveSession]);

  const clearMessages = useCallback(() => {
    if (!activeSessionId) return;
    updateSessionMessages(activeSessionId, () => [], "新对话");
    setError(null);
  }, [activeSessionId, updateSessionMessages]);

  return {
    messages,
    isStreaming,
    error,
    sendMessage,
    clearMessages,
    sessions,
    activeSessionId,
    setActiveSession,
    createNewSession,
    deleteSession,
    activeSession,
    runtimeStatus,
  };
}
