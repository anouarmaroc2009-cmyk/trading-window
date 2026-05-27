"use client";

import { useEffect, useRef, useCallback, useState } from "react";

type MessageHandler = (data: any) => void;

export function useWebSocket(url: string) {
  const ws = useRef<WebSocket | null>(null);
  const handlers = useRef<Map<string, MessageHandler[]>>(new Map());
  const [connected, setConnected] = useState(false);
  const reconnectTimeout = useRef<NodeJS.Timeout>();

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return;
    try {
      const socket = new WebSocket(url);
      socket.onopen = () => {
        setConnected(true);
        console.log("WS connected");
      };
      socket.onclose = () => {
        setConnected(false);
        reconnectTimeout.current = setTimeout(connect, 3000);
      };
      socket.onerror = () => socket.close();
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handlers.current.forEach((hs, key) => {
            hs.forEach((h) => h(data));
          });
        } catch {
          // ignore parse errors on individual messages
        }
      };
      ws.current = socket;
    } catch {
      reconnectTimeout.current = setTimeout(connect, 3000);
    }
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimeout.current);
      ws.current?.close();
    };
  }, [connect]);

  const subscribe = useCallback((event: string, handler: MessageHandler) => {
    if (!handlers.current.has(event)) handlers.current.set(event, []);
    handlers.current.get(event)!.push(handler);
    return () => {
      const hs = handlers.current.get(event);
      if (hs) handlers.current.set(event, hs.filter((h) => h !== handler));
    };
  }, []);

  const send = useCallback((data: object) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(data));
    }
  }, []);

  return { connected, subscribe, send };
}
