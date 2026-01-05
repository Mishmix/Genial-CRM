import { useEffect, useRef, useCallback } from 'react';

type MessageHandler = (data: any) => void;

interface WebSocketMessage {
  type: string;
  data: any;
}

// In dev mode, connect to backend directly; in prod, use env var or same host
const getWsUrl = () => {
  // Check if we're in development (Vite dev server)
  if (import.meta.env.DEV) {
    return 'ws://localhost:8000/ws';
  }
  // In production, use VITE_WS_URL or construct from API URL
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }
  // Fallback: construct from API URL
  if (import.meta.env.VITE_API_URL) {
    const apiUrl = import.meta.env.VITE_API_URL;
    return apiUrl.replace('https://', 'wss://').replace('http://', 'ws://').replace('/api', '/ws');
  }
  return `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;
};

const WS_URL = getWsUrl();

// Global WebSocket instance
let globalWs: WebSocket | null = null;
let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
const handlers = new Map<string, Set<MessageHandler>>();

function connect() {
  if (globalWs?.readyState === WebSocket.OPEN || globalWs?.readyState === WebSocket.CONNECTING) {
    return;
  }

  try {
    globalWs = new WebSocket(WS_URL);

    globalWs.onopen = () => {
      console.log('[WS] Connected');
    };

    globalWs.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        console.log('[WS] Received message:', message.type, message.data);
        
        // Handle ping
        if (message.type === 'ping') {
          globalWs?.send('pong');
          return;
        }

        // Dispatch to handlers
        const typeHandlers = handlers.get(message.type);
        console.log('[WS] Handlers for', message.type, ':', typeHandlers?.size || 0);
        if (typeHandlers) {
          typeHandlers.forEach(handler => {
            try {
              handler(message.data);
            } catch (e) {
              console.error('[WS] Handler error:', e);
            }
          });
        }

        // Also dispatch to 'all' handlers
        const allHandlers = handlers.get('*');
        if (allHandlers) {
          allHandlers.forEach(handler => {
            try {
              handler(message);
            } catch (e) {
              console.error('[WS] Handler error:', e);
            }
          });
        }
      } catch (e) {
        console.error('[WS] Parse error:', e);
      }
    };

    globalWs.onclose = () => {
      console.log('[WS] Disconnected, reconnecting in 3s...');
      globalWs = null;
      reconnectTimeout = setTimeout(connect, 3000);
    };

    globalWs.onerror = (error) => {
      console.error('[WS] Error:', error);
    };
  } catch (e) {
    console.error('[WS] Connection error:', e);
    reconnectTimeout = setTimeout(connect, 3000);
  }
}

// Start connection
connect();

export function useWebSocket(eventType: string, handler: MessageHandler) {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    const wrappedHandler: MessageHandler = (data) => {
      handlerRef.current(data);
    };

    // Add handler
    if (!handlers.has(eventType)) {
      handlers.set(eventType, new Set());
    }
    handlers.get(eventType)!.add(wrappedHandler);

    // Ensure connection
    connect();

    return () => {
      handlers.get(eventType)?.delete(wrappedHandler);
    };
  }, [eventType]);
}

export function useWebSocketAll(handler: (message: WebSocketMessage) => void) {
  useWebSocket('*', handler);
}
