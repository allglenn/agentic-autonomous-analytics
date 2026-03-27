"use client";

import { useState, useRef, useEffect } from "react";

interface SessionMeta {
  session_id: string;
  title: string;
}

interface SidebarProps {
  sessions: SessionMeta[];
  currentSessionId: string;
  onNewChat: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
  onRenameSession: (id: string, title: string) => void;
}

export default function Sidebar({
  sessions,
  currentSessionId,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  onRenameSession,
}: SidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingId && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingId]);

  const startRename = (session: SessionMeta, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(session.session_id);
    setEditValue(session.title);
  };

  const commitRename = () => {
    if (editingId && editValue.trim()) {
      onRenameSession(editingId, editValue.trim());
    }
    setEditingId(null);
  };

  const handleRenameKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      commitRename();
    } else if (e.key === "Escape") {
      setEditingId(null);
    }
  };

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm("Delete this conversation?")) {
      onDeleteSession(id);
    }
  };

  return (
    <div className="w-64 flex-shrink-0 flex flex-col bg-[#111111] border-r border-[#1E1E1E] h-full">
      {/* Top section */}
      <div className="px-4 pt-4 pb-3 border-b border-[#1E1E1E]">
        <p className="text-[10px] tracking-widest uppercase text-[#6B7280] font-medium mb-3">
          Chat History
        </p>
        <button
          onClick={onNewChat}
          className="flex items-center gap-2 w-full text-left px-3 py-2 text-sm text-[#E5E7EB] bg-[#161616] border border-[#1E1E1E] hover:border-[#1A56DB] transition-colors rounded-sm"
        >
          <span className="text-[#1A56DB] font-semibold">+</span>
          New chat
        </button>
      </div>

      {/* Sessions list */}
      <div className="flex-1 overflow-y-auto py-2">
        {sessions.length === 0 && (
          <p className="text-xs text-[#374151] text-center px-4 py-6">
            No conversations yet
          </p>
        )}
        {sessions.map((session) => {
          const isActive = session.session_id === currentSessionId;
          const isEditing = editingId === session.session_id;

          return (
            <div
              key={session.session_id}
              onClick={() => !isEditing && onSelectSession(session.session_id)}
              className={`group relative flex items-center gap-2 px-4 py-2.5 cursor-pointer transition-colors border-l-2 ${
                isActive
                  ? "bg-[#161616] border-l-[#1A56DB]"
                  : "border-l-transparent hover:bg-[#0f0f0f]"
              }`}
            >
              {isEditing ? (
                <input
                  ref={inputRef}
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onBlur={commitRename}
                  onKeyDown={handleRenameKeyDown}
                  onClick={(e) => e.stopPropagation()}
                  className="flex-1 bg-[#0D0D0D] border border-[#1A56DB] text-[#E5E7EB] text-sm px-1 py-0.5 rounded-sm outline-none min-w-0"
                />
              ) : (
                <span
                  onDoubleClick={(e) => startRename(session, e)}
                  className={`text-sm truncate flex-1 select-none ${
                    isActive ? "text-[#E5E7EB]" : "text-[#9CA3AF]"
                  }`}
                >
                  {session.title}
                </span>
              )}

              {/* Action buttons — always visible, brighter on hover */}
              {!isEditing && (
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button
                    onClick={(e) => startRename(session, e)}
                    className="text-[#4B5563] hover:text-[#E5E7EB] transition-colors p-1 rounded-sm hover:bg-[#1E1E1E]"
                    title="Rename"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                    </svg>
                  </button>
                  <button
                    onClick={(e) => handleDelete(session.session_id, e)}
                    className="text-[#4B5563] hover:text-[#EF4444] transition-colors p-1 rounded-sm hover:bg-[#1E1E1E]"
                    title="Delete"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="3 6 5 6 21 6"/>
                      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                      <path d="M10 11v6M14 11v6"/>
                      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                    </svg>
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-[#1E1E1E]">
        <p className="text-[10px] tracking-widest uppercase text-[#374151]">
          Allinsoft Ware
        </p>
      </div>
    </div>
  );
}
