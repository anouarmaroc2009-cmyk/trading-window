"use client";

import { useEffect, useRef } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/index";

declare global {
  interface Window {
    TradingView: any;
  }
}

export function TradingViewChart({ symbol = "BTCUSD" }: { symbol?: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const scriptLoaded = useRef(false);

  useEffect(() => {
    if (scriptLoaded.current) return;
    scriptLoaded.current = true;

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/tv.js";
    script.async = true;
    script.onload = () => {
      if (containerRef.current && window.TradingView) {
        new window.TradingView.widget({
          container_id: containerRef.current.id,
          symbol: symbol.includes("USD") ? `FX:${symbol}` : symbol,
          interval: "5",
          timezone: "America/New_York",
          theme: "dark",
          style: "1",
          locale: "en",
          toolbar_bg: "#1a1d29",
          enable_publishing: false,
          hide_side_toolbar: false,
          allow_symbol_change: true,
          width: "100%",
          height: "100%",
          save_image: false,
          studies: [
            "RSI@tv-basicstudies",
            "Volume@tv-basicstudies",
            "MACD@tv-basicstudies",
            "EMA@tv-basicstudies",
          ],
        });
      }
    };
    document.head.appendChild(script);

    return () => {
      scriptLoaded.current = false;
    };
  }, [symbol]);

  return (
    <Card className="h-full">
      <CardHeader className="py-2">
        <CardTitle>{symbol} — Live Chart</CardTitle>
      </CardHeader>
      <CardContent className="p-0 h-[calc(100%-36px)]">
        <div
          id="tv-chart"
          ref={containerRef}
          className="w-full h-full"
        />
      </CardContent>
    </Card>
  );
}
