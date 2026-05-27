"use client";

import { useEffect, useState, useCallback } from "react";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { TradingViewChart } from "@/components/charts/tradingview-chart";
import { AICommandCenter } from "@/components/ai/command-center";
import { StrategyManager } from "@/components/strategies/strategy-manager";
import { PortfolioTracker } from "@/components/portfolio/portfolio-tracker";
import { OrderHistory } from "@/components/portfolio/order-history";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/index";
import { useWebSocket } from "@/hooks/use-websocket";

const WS_URL = "ws://localhost:8000/ws/live";
const API_URL = "http://localhost:8000";

interface Suite {
  id: string;
  name: string;
  enabled: boolean;
}

interface ReasoningEntry {
  decision: string;
  reason: string;
  timestamp: string;
  thesis?: string;
  market_context?: string;
}

export default function Dashboard() {
  const [activeView, setActiveView] = useState("dashboard");
  const [agentMode, setAgentMode] = useState("manual");
  const [suites, setSuites] = useState<Suite[]>([]);
  const [portfolio, setPortfolio] = useState<any>(null);
  const [orders, setOrders] = useState<any[]>([]);
  const [reasoning, setReasoning] = useState<ReasoningEntry[]>([]);
  const [symbol, setSymbol] = useState("BTCUSD");
  const [tickPrice, setTickPrice] = useState<number | null>(null);

  const { connected, subscribe, send } = useWebSocket(WS_URL);

  useEffect(() => {
    if (!connected) return;
    const unsub1 = subscribe("agent:reasoning", (data: ReasoningEntry) => {
      setReasoning((prev) => [...prev.slice(-99), data]);
    });
    const unsub2 = subscribe("portfolio:snapshot", (data: any) => {
      setPortfolio(data);
    });
    const unsub3 = subscribe("execution:orders", (data: any) => {
      setOrders((prev) => [data, ...prev].slice(0, 50));
    });
    const unsub4 = subscribe("live:ticks", (data: any) => {
      if (data?.payload?.symbol === symbol) {
        setTickPrice(data.payload.price);
      }
    });
    return () => {
      unsub1(); unsub2(); unsub3(); unsub4();
    };
  }, [connected, subscribe, symbol]);

  useEffect(() => {
    fetch(`${API_URL}/api/v1/suites`)
      .then((r) => r.json())
      .then((d) => setSuites(d.suites))
      .catch(() => {});
    fetch(`${API_URL}/api/v1/orders`)
      .then((r) => r.json())
      .then((d) => setOrders(d.slice(0, 50)))
      .catch(() => {});
    fetch(`${API_URL}/api/v1/portfolio`)
      .then((r) => r.json())
      .then(setPortfolio)
      .catch(() => {});
  }, []);

  const handleModeChange = useCallback(
    (mode: string) => {
      setAgentMode(mode);
      send({ type: "set_mode", mode });
      fetch(`${API_URL}/api/v1/agent/mode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      }).catch(() => {});
    },
    [send]
  );

  const handleChat = useCallback(
    (message: string) => {
      send({ type: "chat", symbol, message });
    },
    [send, symbol]
  );

  const handleSuiteToggle = useCallback(
    (id: string) => {
      fetch(`${API_URL}/api/v1/suites/${id}/toggle`, { method: "POST" })
        .then((r) => r.json())
        .then((d) => {
          setSuites((prev) =>
            prev.map((s) => (s.id === id ? { ...s, enabled: d.enabled } : s))
          );
        })
        .catch(() => {});
    },
    []
  );

  const renderView = () => {
    switch (activeView) {
      case "dashboard":
        return (
          <div className="grid grid-cols-2 gap-1 p-1 h-full">
            <div className="col-span-2">
              <TradingViewChart symbol={symbol} />
            </div>
            <div className="flex flex-col gap-1">
              <AICommandCenter entries={reasoning} onChat={handleChat} />
            </div>
            <div className="flex flex-col gap-1">
              <PortfolioTracker data={portfolio} />
              <OrderHistory orders={orders} />
            </div>
          </div>
        );
      case "charts":
        return (
          <div className="p-2 h-full">
            <TradingViewChart symbol={symbol} />
          </div>
        );
      case "ai":
        return (
          <div className="p-2 h-full">
            <AICommandCenter entries={reasoning} onChat={handleChat} />
          </div>
        );
      case "strategies":
        return (
          <div className="p-2 h-full">
            <StrategyManager suites={suites} onToggle={handleSuiteToggle} />
          </div>
        );
      case "portfolio":
        return (
          <div className="p-2 h-full flex flex-col gap-2">
            <PortfolioTracker data={portfolio} />
            <OrderHistory orders={orders} />
          </div>
        );
      case "orders":
        return (
          <div className="p-2 h-full">
            <OrderHistory orders={orders} />
          </div>
        );
      case "scripts":
        return (
          <div className="p-2 h-full">
            <Card className="h-full">
              <CardHeader className="py-2">
                <CardTitle>Custom Scripts</CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <div className="rounded border border-border bg-secondary/30 p-4 text-center">
                  <p className="text-sm text-muted-foreground mb-2">
                    Upload or write custom Pine Script / Python strategies
                  </p>
                  <div className="flex items-center justify-center gap-2">
                    <span className="text-xs bg-secondary px-3 py-1.5 rounded cursor-pointer hover:bg-secondary/80">
                      📄 Upload Script
                    </span>
                    <span className="text-xs bg-secondary px-3 py-1.5 rounded cursor-pointer hover:bg-secondary/80">
                      ✏️ New Script
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="trading-grid">
      <Sidebar activeView={activeView} onViewChange={setActiveView} />

      <Topbar agentMode={agentMode} onModeChange={handleModeChange} onChat={handleChat} />

      <div className="main-content overflow-hidden">
        {/* Status bar */}
        <div className="flex items-center gap-4 px-3 py-1 bg-card border-b border-border text-[10px] text-muted-foreground">
          <div className="flex items-center gap-1">
            <div className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`} />
            <span>{connected ? "Live" : "Disconnected"}</span>
          </div>
          <span>|</span>
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="bg-transparent text-[10px] text-muted-foreground outline-none"
          >
            {["BTCUSD", "ETHUSD", "EURUSD", "GBPUSD", "SP500"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          {tickPrice && (
            <>
              <span>|</span>
              <span className="font-mono text-foreground">{tickPrice.toFixed(2)}</span>
            </>
          )}
          <span className="ml-auto">
            Mode: <span className="text-primary font-medium uppercase">{agentMode}</span>
          </span>
        </div>

        {/* Main content area */}
        <div className="overflow-hidden h-full">{renderView()}</div>
      </div>
    </div>
  );
}
