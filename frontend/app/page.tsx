"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import dynamic from "next/dynamic";

// Import Highcharts dynamically to avoid SSR issues
const HighchartsReact = dynamic(() => import("highcharts-react-official"), {
  ssr: false,
});
import Highcharts from "highcharts";

interface FinalAnswer {
  summary: string;
  findings: string[];
  evidence: string[];
  confidence: number;
  validated: boolean;
  critic_notes: string | null;
  chart?: any; // Highcharts config
}

interface Message {
  id: string;
  role: "user" | "assistant" | "error";
  content: string | FinalAnswer;
}

interface SessionMeta {
  session_id: string;
  title: string;
}

type ApiResponse =
  | { needs_clarification: true; clarification_question: string }
  | { detail: string }
  | { role: string; parts: { text: string }[] }
  | Record<string, unknown>;

function parseApiResponse(data: ApiResponse): string | FinalAnswer {
  if (!data) return "No response received.";

  if ("needs_clarification" in data && data.needs_clarification) {
    return (data as { needs_clarification: true; clarification_question: string })
      .clarification_question;
  }

  if ("answer" in data) {
    const answer = (data as { answer: unknown }).answer;
    if (typeof answer === "string") return answer;
    if (answer && typeof answer === "object" && "summary" in answer) {
      return answer as FinalAnswer;
    }
  }

  if ("detail" in data && typeof (data as { detail: string }).detail === "string") {
    return (data as { detail: string }).detail;
  }

  return JSON.stringify(data, null, 2);
}

const SUGGESTIONS = [
  "Why did revenue drop last week?",
  "Compare conversion rate this month vs last month",
  "What are the top product categories by revenue?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessions, setSessions] = useState<SessionMeta[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>(() => crypto.randomUUID());
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const activeSessionRef = useRef(currentSessionId);

  // Auto-scroll to bottom whenever messages or loading state changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Auto-resize textarea
  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 140) + "px";
  }, []);

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch("/api/sessions");
      const data = await res.json();
      setSessions(data.sessions || []);
    } catch {}
  }, []);

  // Fetch sessions on mount
  useEffect(() => {
    fetchSessions();
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    resizeTextarea();
  };

  const handleNewChat = () => {
    const newId = crypto.randomUUID();
    activeSessionRef.current = newId;
    setCurrentSessionId(newId);
    setMessages([]);
    textareaRef.current?.focus();
  };

  const handleSelectSession = async (id: string) => {
    activeSessionRef.current = id;
    setCurrentSessionId(id);
    setMessages([]);
    setLoading(true);
    try {
      const res = await fetch(`/api/sessions/${id}`);
      const data = await res.json();
      const msgs: Message[] = (data.messages || []).map((m: { role: string; content: string }) => {
        let content: string | FinalAnswer = m.content;
        if (m.role !== "user") {
          try {
            const parsed = JSON.parse(m.content);
            if (parsed && typeof parsed === "object" && "summary" in parsed) {
              content = parsed as FinalAnswer;
            }
          } catch { /* plain text — use as-is */ }
        }
        return {
          id: crypto.randomUUID(),
          role: m.role === "user" ? "user" : ("assistant" as const),
          content,
        };
      });
      // Only apply if this session is still the active one
      if (activeSessionRef.current === id) {
        setMessages(msgs);
      }
    } catch {
      if (activeSessionRef.current === id) setMessages([]);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSession = async (id: string) => {
    const res = await fetch(`/api/sessions/${id}`, { method: "DELETE" });
    if (res.ok) {
      if (id === currentSessionId) handleNewChat();
      setSessions((prev) => prev.filter((s) => s.session_id !== id));
    } else {
      // Refresh from server so UI matches actual DB state
      fetchSessions();
    }
  };

  const handleRenameSession = async (id: string, title: string) => {
    const res = await fetch(`/api/sessions/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    if (res.ok) {
      setSessions((prev) =>
        prev.map((s) => (s.session_id === id ? { ...s, title } : s))
      );
    } else {
      fetchSessions();
    }
  };

  const submitMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading) return;

      const userMessage: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: trimmed,
      };

      setMessages((prev) => [...prev, userMessage]);
      setInput("");
      setLoading(true);

      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }

      const sessionIdAtSubmit = currentSessionId;
      try {
        const res = await fetch("/api/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: trimmed, session_id: sessionIdAtSubmit }),
        });

        const data: ApiResponse = await res.json();
        const content = parseApiResponse(data);
        const isError = res.status >= 400 || "detail" in data;

        const assistantMessage: Message = {
          id: crypto.randomUUID(),
          role: isError ? "error" : "assistant",
          content,
        };

        // Only update messages if the user hasn't switched to a different session
        if (activeSessionRef.current === sessionIdAtSubmit) {
          setMessages((prev) => [...prev, assistantMessage]);
        }
        fetchSessions();
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "error",
            content: "An unexpected error occurred. Please try again.",
          },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [loading, currentSessionId, fetchSessions]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitMessage(input);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    submitMessage(input);
  };

  const handleSuggestion = (suggestion: string) => {
    setInput(suggestion);
    textareaRef.current?.focus();
    setTimeout(resizeTextarea, 0);
  };

  return (
    <div className="flex h-full bg-[#111111]">
      {/* Sidebar toggle button — visible when sidebar closed */}
      {!sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(true)}
          className="absolute top-4 left-4 z-10 p-2 text-[#6B7280] hover:text-[#E5E7EB] transition-colors"
        >
          ☰
        </button>
      )}

      {/* Sidebar */}
      {sidebarOpen && (
        <div className="relative flex-shrink-0">
          <Sidebar
            sessions={sessions}
            currentSessionId={currentSessionId}
            onNewChat={handleNewChat}
            onSelectSession={handleSelectSession}
            onDeleteSession={handleDeleteSession}
            onRenameSession={handleRenameSession}
          />
          {/* Collapse button */}
          <button
            onClick={() => setSidebarOpen(false)}
            className="absolute top-3 right-3 text-[#6B7280] hover:text-[#E5E7EB] text-xs transition-colors"
            title="Collapse sidebar"
          >
            ←
          </button>
        </div>
      )}

      {/* Main chat area */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Header */}
        <header className="flex items-center justify-between px-8 py-4 bg-[#111111] border-b border-[#1E1E1E] flex-shrink-0">
          <div>
            <p className="text-xs tracking-widest uppercase text-[#6B7280] font-medium">
              Allinsoft ware
            </p>
            <h1 className="text-base font-semibold text-[#E5E7EB] mt-0.5">
              AI Data Analyst
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#1A56DB] opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#1A56DB]" />
            </span>
            <span className="text-xs tracking-widest uppercase text-[#6B7280] font-medium">
              Live
            </span>
          </div>
        </header>

        {/* Messages area */}
        <main className="flex-1 overflow-y-auto bg-[#0D0D0D] px-6 py-8">
          {messages.length === 0 && !loading ? (
            /* Empty state */
            <div className="flex flex-col items-center justify-center h-full text-center">
              <p className="text-xs tracking-widest uppercase text-[#6B7280] font-medium mb-4">
                AI Data Analyst
              </p>
              <h2 className="text-2xl font-semibold text-[#E5E7EB] mb-3">
                What do you want to know?
              </h2>
              <p className="text-sm text-[#6B7280] mb-10 max-w-sm">
                Ask a question about your business data. The analyst will query
                your data warehouse and return insights.
              </p>
              <div className="flex flex-col gap-2 w-full max-w-md">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => handleSuggestion(suggestion)}
                    className="text-left text-sm text-[#E5E7EB] bg-[#161616] border border-[#1E1E1E] px-4 py-3 rounded-sm hover:border-[#2A2A2A] hover:bg-[#1a1a1a] transition-colors duration-150"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* Message list */
            <div className="flex flex-col gap-6 max-w-4xl mx-auto">
              {messages.map((message) => {
                if (message.role === "user") {
                  return (
                    <div key={message.id} className="flex justify-end">
                      <div className="max-w-[72%] bg-[#1A56DB] text-white px-4 py-3 rounded-sm text-sm leading-relaxed">
                        {message.content}
                      </div>
                    </div>
                  );
                }

                if (message.role === "error") {
                  return (
                    <div key={message.id} className="flex items-start gap-3">
                      <div className="flex-shrink-0 w-6 h-6 bg-[#1A56DB] flex items-center justify-center text-white text-xs font-semibold rounded-sm mt-5">
                        A
                      </div>
                      <div className="flex flex-col gap-1 max-w-[78%]">
                        <span className="text-xs tracking-widest uppercase text-[#6B7280] font-medium pl-1">
                          Error
                        </span>
                        <div className="bg-[#1C1010] border border-[#3D1515] px-4 py-3 rounded-sm text-sm text-[#FCA5A5] leading-relaxed whitespace-pre-wrap">
                          {message.content}
                        </div>
                      </div>
                    </div>
                  );
                }

                // assistant
                const isStructured = typeof message.content === "object" && message.content !== null && "summary" in message.content;
                const fa = isStructured ? (message.content as FinalAnswer) : null;
                return (
                  <div key={message.id} className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-6 h-6 bg-[#1A56DB] flex items-center justify-center text-white text-xs font-semibold rounded-sm mt-5">
                      A
                    </div>
                    <div className="flex flex-col gap-1 max-w-[78%]">
                      <span className="text-xs tracking-widest uppercase text-[#6B7280] font-medium pl-1">
                        Analyst
                      </span>
                      {fa ? (
                        <div className="bg-[#161616] border border-[#1E1E1E] rounded-sm text-sm text-[#E5E7EB] overflow-hidden">
                          <div className="px-4 py-3 border-b border-[#1E1E1E]">
                            <p className="font-medium leading-relaxed">{fa.summary}</p>
                          </div>
                          {fa.findings?.length > 0 && (
                            <div className="px-4 py-3 border-b border-[#1E1E1E]">
                              <p className="text-[10px] tracking-widest uppercase text-[#6B7280] font-medium mb-2">Findings</p>
                              <ul className="space-y-1">
                                {fa.findings.map((f, i) => <li key={i} className="text-[#9CA3AF] leading-relaxed">• {f}</li>)}
                              </ul>
                            </div>
                          )}
                          {fa.chart && (
                            <div className="px-4 py-4 border-b border-[#1E1E1E] bg-[#0D0D0D]">
                              <HighchartsReact highcharts={Highcharts} options={fa.chart} />
                            </div>
                          )}
                          {fa.evidence?.length > 0 && (
                            <div className="px-4 py-3 border-b border-[#1E1E1E]">
                              <p className="text-[10px] tracking-widest uppercase text-[#6B7280] font-medium mb-2">Evidence</p>
                              <ul className="space-y-1">
                                {fa.evidence.map((e, i) => <li key={i} className="text-[#6B7280] text-xs leading-relaxed">• {e}</li>)}
                              </ul>
                            </div>
                          )}
                          <div className="px-4 py-2 flex items-center gap-4">
                            <span className="text-[10px] tracking-widest uppercase text-[#374151]">
                              Confidence {Math.round(fa.confidence * 100)}%
                            </span>
                            {fa.validated && (
                              <span className="text-[10px] tracking-widest uppercase text-[#374151]">Validated</span>
                            )}
                            {fa.critic_notes && (
                              <span className="text-[10px] text-[#6B7280]">{fa.critic_notes}</span>
                            )}
                          </div>
                        </div>
                      ) : (
                        <div className="bg-[#161616] border border-[#1E1E1E] px-4 py-3 rounded-sm text-sm text-[#E5E7EB] leading-relaxed whitespace-pre-wrap">
                          {message.content as string}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* Loading state */}
              {loading && (
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-6 h-6 bg-[#1A56DB] flex items-center justify-center text-white text-xs font-semibold rounded-sm mt-5">
                    A
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-xs tracking-widest uppercase text-[#6B7280] font-medium pl-1">
                      Analyst
                    </span>
                    <div className="bg-[#161616] border border-[#1E1E1E] px-4 py-3 rounded-sm">
                      <div className="flex items-center gap-1.5">
                        <span
                          className="w-1.5 h-1.5 rounded-full bg-[#1A56DB] animate-bounce"
                          style={{ animationDelay: "0ms" }}
                        />
                        <span
                          className="w-1.5 h-1.5 rounded-full bg-[#1A56DB] animate-bounce"
                          style={{ animationDelay: "150ms" }}
                        />
                        <span
                          className="w-1.5 h-1.5 rounded-full bg-[#1A56DB] animate-bounce"
                          style={{ animationDelay: "300ms" }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          )}
        </main>

        {/* Input area */}
        <div className="bg-[#0D0D0D] border-t border-[#1E1E1E] px-6 pb-6 pt-4 flex-shrink-0">
          <form
            onSubmit={handleSubmit}
            className="flex gap-3 items-end max-w-4xl mx-auto"
          >
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question about your data..."
              rows={1}
              disabled={loading}
              className="flex-1 bg-[#111111] border border-[#1E1E1E] text-[#E5E7EB] placeholder-[#4B5563] px-4 py-3 rounded-sm resize-none text-sm leading-relaxed focus:outline-none focus:border-[#1A56DB] transition-colors duration-150 disabled:opacity-50"
              style={{ minHeight: "48px", maxHeight: "140px" }}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="flex-shrink-0 bg-[#1A56DB] hover:bg-[#1d4ed8] text-white px-5 py-3 rounded-sm text-sm font-medium transition-colors duration-150 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Send
            </button>
          </form>
          <p className="text-center text-[10px] tracking-widest uppercase text-[#374151] mt-3 max-w-4xl mx-auto">
            Allinsoft ware &middot; AI Analytics &middot; Powered by Google ADK
          </p>
        </div>
      </div>
    </div>
  );
}
