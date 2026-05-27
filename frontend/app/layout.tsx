import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Quant Trading Engine",
  description: "Autonomous AI-powered algorithmic trading platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  );
}
