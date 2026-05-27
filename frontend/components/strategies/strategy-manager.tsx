"use client";

import { Toggle, Card, CardHeader, CardTitle, CardContent } from "@/components/ui/index";

interface Suite {
  id: string;
  name: string;
  enabled: boolean;
}

export function StrategyManager({
  suites,
  onToggle,
}: {
  suites: Suite[];
  onToggle: (id: string) => void;
}) {
  return (
    <Card className="h-full">
      <CardHeader className="py-2">
        <CardTitle>Strategy Engine — 7 Core Pillars</CardTitle>
      </CardHeader>
      <CardContent className="p-2">
        <div className="space-y-1">
          {suites.map((suite) => (
            <div
              key={suite.id}
              className="flex items-center justify-between p-2 rounded hover:bg-secondary/50 transition-colors"
            >
              <div className="flex items-center gap-2">
                <div
                  className={`h-2 w-2 rounded-full ${
                    suite.enabled ? "bg-green-500" : "bg-muted-foreground"
                  }`}
                />
                <span className="text-xs">{suite.name}</span>
              </div>
              <Toggle
                pressed={suite.enabled}
                onPressedChange={() => onToggle(suite.id)}
                className="h-7 px-3 text-xs"
              >
                {suite.enabled ? "ON" : "OFF"}
              </Toggle>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
