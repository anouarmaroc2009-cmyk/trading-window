"use client";

import { Card, CardHeader, CardTitle, CardContent, Badge } from "@/components/ui/index";
import { TrendingUp, TrendingDown, Wallet, Activity, BarChart3 } from "lucide-react";
import { formatCurrency, formatPercent } from "@/lib/utils";

interface Position {
  symbol: string;
  side: "long" | "short";
  quantity: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  stop_loss?: number;
  take_profit?: number;
}

interface PortfolioData {
  portfolio_value: number;
  daily_pnl: number;
  total_realized_pnl: number;
  total_trades: number;
  win_rate: number;
  open_positions: number;
  positions: Record<string, Position>;
}

export function PortfolioTracker({ data }: { data: PortfolioData | null }) {
  if (!data) {
    return (
      <Card className="h-full">
        <CardHeader className="py-2"><CardTitle>Portfolio</CardTitle></CardHeader>
        <CardContent className="p-4"><div className="text-xs text-muted-foreground">Loading...</div></CardContent>
      </Card>
    );
  }

  return (
    <Card className="h-full">
      <CardHeader className="py-2">
        <CardTitle>Live Portfolio</CardTitle>
      </CardHeader>
      <CardContent className="p-2 space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded bg-secondary/50 p-2">
            <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
              <Wallet className="h-3 w-3" /> Value
            </div>
            <div className="text-sm font-bold mt-1">{formatCurrency(data.portfolio_value)}</div>
          </div>
          <div className="rounded bg-secondary/50 p-2">
            <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
              <Activity className="h-3 w-3" /> Daily P&L
            </div>
            <div className={`text-sm font-bold mt-1 ${data.daily_pnl >= 0 ? "text-green-500" : "text-red-500"}`}>
              {formatCurrency(data.daily_pnl)}
            </div>
          </div>
          <div className="rounded bg-secondary/50 p-2">
            <div className="text-[10px] text-muted-foreground">Win Rate</div>
            <div className="text-sm font-bold mt-1">{(data.win_rate * 100).toFixed(1)}%</div>
          </div>
          <div className="rounded bg-secondary/50 p-2">
            <div className="text-[10px] text-muted-foreground">Trades</div>
            <div className="text-sm font-bold mt-1">{data.total_trades}</div>
          </div>
        </div>

        {data.open_positions > 0 && (
          <div>
            <div className="text-[10px] text-muted-foreground mb-1">Open Positions</div>
            <div className="space-y-1">
              {Object.values(data.positions).map((pos) => (
                <div key={pos.symbol} className="flex items-center justify-between rounded bg-secondary/50 p-2">
                  <div className="flex items-center gap-2">
                    {pos.side === "long" ? (
                      <TrendingUp className="h-3 w-3 text-green-500" />
                    ) : (
                      <TrendingDown className="h-3 w-3 text-red-500" />
                    )}
                    <span className="text-xs font-medium">{pos.symbol}</span>
                    <Badge variant={pos.side === "long" ? "success" : "danger"}>
                      {pos.side.toUpperCase()}
                    </Badge>
                  </div>
                  <div className="text-right">
                    <div className="text-xs">{pos.quantity} @ {pos.entry_price.toFixed(2)}</div>
                    <div className={`text-[10px] ${pos.unrealized_pnl >= 0 ? "text-green-500" : "text-red-500"}`}>
                      {formatCurrency(pos.unrealized_pnl)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {data.open_positions === 0 && (
          <div className="text-xs text-muted-foreground text-center py-4">No open positions</div>
        )}
      </CardContent>
    </Card>
  );
}
