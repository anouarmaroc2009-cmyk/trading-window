"use client";

import { Card, CardHeader, CardTitle, CardContent, Badge } from "@/components/ui/index";
import { formatCurrency } from "@/lib/utils";

interface Order {
  order_id: string;
  symbol: string;
  side: "buy" | "sell";
  quantity: number;
  price: number;
  order_type: string;
  status: string;
  avg_fill_price?: number;
  created_at: string;
}

export function OrderHistory({ orders }: { orders: Order[] }) {
  return (
    <Card className="h-full">
      <CardHeader className="py-2">
        <CardTitle>Order History</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-y-auto max-h-[300px]">
          <table className="w-full text-xs">
            <thead className="text-muted-foreground border-b border-border">
              <tr>
                <th className="text-left p-2 font-medium">ID</th>
                <th className="text-left p-2 font-medium">Symbol</th>
                <th className="text-left p-2 font-medium">Side</th>
                <th className="text-right p-2 font-medium">Qty</th>
                <th className="text-right p-2 font-medium">Price</th>
                <th className="text-left p-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {orders.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-center p-4 text-muted-foreground">
                    No orders yet
                  </td>
                </tr>
              )}
              {orders.map((order) => (
                <tr key={order.order_id} className="border-b border-border/50 hover:bg-secondary/30">
                  <td className="p-2 font-mono text-[10px]">{order.order_id.slice(0, 8)}</td>
                  <td className="p-2 font-medium">{order.symbol}</td>
                  <td className="p-2">
                    <Badge variant={order.side === "buy" ? "success" : "danger"}>
                      {order.side.toUpperCase()}
                    </Badge>
                  </td>
                  <td className="p-2 text-right">{order.quantity}</td>
                  <td className="p-2 text-right font-mono">
                    {formatCurrency(order.avg_fill_price || order.price || 0, 2)}
                  </td>
                  <td className="p-2">
                    <Badge
                      variant={
                        order.status === "filled"
                          ? "success"
                          : order.status === "rejected"
                          ? "danger"
                          : "warning"
                      }
                    >
                      {order.status}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
