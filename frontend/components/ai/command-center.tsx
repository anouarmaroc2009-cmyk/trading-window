"use client";

import { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent, Button, Input } from "@/components/ui/index";
import { ReasoningLog } from "./reasoning-log";
import { Send } from "lucide-react";

interface ReasoningEntry {
  decision: string;
  reason: string;
  timestamp: string;
  thesis?: string;
  market_context?: string;
}

export function AICommandCenter({
  entries,
  onChat,
}: {
  entries: ReasoningEntry[];
  onChat: (msg: string) => void;
}) {
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (input.trim()) {
      onChat(input.trim());
      setInput("");
    }
  };

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="py-2 flex-row items-center justify-between">
        <CardTitle>AI Command Center</CardTitle>
        <span className="text-[10px] text-muted-foreground">
          {entries.length} signals processed
        </span>
      </CardHeader>
      <CardContent className="p-2 flex-1 flex flex-col gap-2">
        <div className="flex-1 min-h-0">
          <ReasoningLog entries={entries} />
        </div>
        <div className="flex gap-2">
          <Input
            placeholder="Ask the AI agent..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            className="flex-1 h-9 text-xs"
          />
          <Button size="sm" onClick={handleSend}>
            <Send className="h-3 w-3" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
