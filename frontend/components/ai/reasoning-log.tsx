"use client";

import { useEffect, useRef } from "react";
import { Card, CardHeader, CardTitle, CardContent, Badge } from "@/components/ui/index";

interface ReasoningEntry {
  decision: string;
  reason: string;
  timestamp: string;
  thesis?: string;
  market_context?: string;
}

export function ReasoningLog({ entries }: { entries: ReasoningEntry[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries]);

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="py-2">
        <CardTitle>AI Chain of Thought</CardTitle>
      </CardHeader>
      <CardContent className="p-2 flex-1 overflow-hidden">
        <div ref={scrollRef} className="h-full overflow-y-auto space-y-1 terminal-scroll pr-1">
          {entries.length === 0 && (
            <div className="text-xs text-muted-foreground p-2">Waiting for signals...</div>
          )}
          {entries.map((entry, i) => (
            <div
              key={i}
              className="rounded bg-secondary/50 p-2 text-xs font-mono leading-relaxed"
            >
              <div className="flex items-center gap-2 mb-1">
                <Badge
                  variant={
                    entry.decision === "EXECUTED"
                      ? "success"
                      : entry.decision === "RECOMMEND"
                      ? "warning"
                      : "default"
                  }
                >
                  {entry.decision}
                </Badge>
                <span className="text-muted-foreground text-[10px]">
                  {entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : ""}
                </span>
              </div>
              {entry.thesis && (
                <div className="text-[11px] text-primary mb-1">{entry.thesis}</div>
              )}
              <div className="text-muted-foreground">{entry.reason}</div>
              {entry.market_context && (
                <details className="mt-1">
                  <summary className="text-[10px] text-muted-foreground cursor-pointer">
                    Market Context
                  </summary>
                  <pre className="text-[10px] text-muted-foreground mt-1 whitespace-pre-wrap">
                    {entry.market_context}
                  </pre>
                </details>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
