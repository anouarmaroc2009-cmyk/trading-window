"use client";

import { cn } from "@/lib/utils";
import {
  BarChart3, Bot, Brain, LineChart, LayoutDashboard,
  Settings, TrendingUp, Wallet, FileCode, FlaskConical,
} from "lucide-react";

const navItems = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "charts", label: "Live Charts", icon: LineChart },
  { id: "ai", label: "AI Command Center", icon: Brain },
  { id: "strategies", label: "Strategy Engine", icon: FlaskConical },
  { id: "portfolio", label: "Portfolio", icon: Wallet },
  { id: "orders", label: "Order History", icon: TrendingUp },
  { id: "scripts", label: "Custom Scripts", icon: FileCode },
];

export function Sidebar({
  activeView,
  onViewChange,
}: {
  activeView: string;
  onViewChange: (view: string) => void;
}) {
  return (
    <div className="sidebar flex flex-col border-r border-border bg-card">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
        <Bot className="h-5 w-5 text-primary" />
        <span className="font-bold text-sm">Quant Engine</span>
      </div>
      <nav className="flex-1 p-2 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                activeView === item.id
                  ? "bg-primary/15 text-primary font-medium"
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </button>
          );
        })}
      </nav>
      <div className="p-3 border-t border-border">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <div className={cn("h-2 w-2 rounded-full", "bg-green-500")} />
          <span>System Online</span>
        </div>
      </div>
    </div>
  );
}
