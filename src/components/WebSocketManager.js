import React, { useEffect, useRef, forwardRef, useImperativeHandle } from 'react';
import { io } from 'socket.io-client';

const WebSocketManager = forwardRef(({ url, onMessage, onConnectionChange }, ref) => {
  const socketRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const onMessageRef = useRef(onMessage);
  const onConnectionChangeRef = useRef(onConnectionChange);

  // Keep refs up to date
  useEffect(() => {
    onMessageRef.current = onMessage;
    onConnectionChangeRef.current = onConnectionChange;
  }, [onMessage, onConnectionChange]);

  useImperativeHandle(ref, () => ({
    disconnect: () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }
    },
    reconnect: () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
      connect();
    },
  }));

  function connect() {
    if (socketRef.current) {
      socketRef.current.disconnect();
    }

    const socket = io(url, {
      transports: ['websocket'],
      reconnection: false,
      timeout: 5000,
    });

    socket.on('connect', () => {
      console.log('WebSocket connected');
      onConnectionChangeRef.current?.(true);
    });

    socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      onConnectionChangeRef.current?.(false);
      // Auto-reconnect after 3s
      reconnectTimerRef.current = setTimeout(() => {
        connect();
      }, 3000);
    });

    socket.on('connect_error', (err) => {
      console.warn('WebSocket connection error:', err.message);
      onConnectionChangeRef.current?.(false);
      reconnectTimerRef.current = setTimeout(() => {
        connect();
      }, 3000);
    });

    socket.on('photo_update', (data) => {
      onMessageRef.current?.(data);
    });

    socket.on('pipeline_progress', (data) => {
      onMessageRef.current?.(data);
    });

    socket.on('pipeline_complete', (data) => {
      onMessageRef.current?.(data);
    });

    socket.on('pipeline_error', (data) => {
      onMessageRef.current?.(data);
    });

    socketRef.current = socket;
  }

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  return null; // This component renders nothing
});

WebSocketManager.displayName = 'WebSocketManager';

export default WebSocketManager;
