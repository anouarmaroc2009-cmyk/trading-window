"use client";

import { useState } from "react";
import { Button, Input } from "@/components/ui/index";
import { Bot, Send } from "lucide-react";

export function Topbar({
  agentMode,
  onModeChange,
  onChat,
}: {
  agentMode: string;
  onModeChange: (mode: string) => void;
  onChat: (msg: string) => void;
}) {
  const [chatInput, setChatInput] = useState("");

  const handleSend = () => {
    if (chatInput.trim()) {
      onChat(chatInput.trim());
      setChatInput("");
    }
  };

  return (
    <div className="topbar flex items-center gap-3 px-4 border-b border-border bg-card">
      <div className="flex items-center gap-2 flex-1">
        <Bot className="h-4 w-4 text-primary" />
        <span className="text-xs text-muted-foreground">AI Agent:</span>
        <div className="flex gap-1">
          {["manual", "semi", "auto"].map((mode) => (
            <Button
              key={mode}
              size="sm"
              variant={agentMode === mode ? "default" : "ghost"}
              onClick={() => onModeChange(mode)}
              className="text-xs capitalize"
            >
              {mode}
            </Button>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-2 max-w-md flex-1">
        <Input
          placeholder="Chat with AI Agent..."
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          className="h-8 text-xs"
        />
        <Button size="sm" onClick={handleSend}>
          <Send className="h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}
