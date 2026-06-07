import { useState, useEffect, useRef, useCallback } from 'react';

export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const [targets, setTargets] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const resultsRef = useRef({});

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    const apiUrl = import.meta.env.VITE_API_URL || `${protocol}//${host}:8000`;
    const wsUrl = apiUrl.replace(/^https?:/, protocol) + '/ws';

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'snapshot') {
          setTargets(data.targets || []);
          setAlerts(data.alerts || []);
        } else if (data.type === 'status_update') {
          setTargets(prev => {
            const idx = prev.findIndex(t => t.id === data.target.id);
            if (idx >= 0) {
              const newTargets = [...prev];
              newTargets[idx] = { ...newTargets[idx], ...data.target };
              return newTargets;
            }
            return [...prev, data.target];
          });
        } else if (data.type === 'alert') {
          setAlerts(prev => [data.alert, ...prev].slice(0, 100));
        } else if (data.type === 'probe_result') {
          const targetId = data.target_id;
          if (!resultsRef.current[targetId]) {
            resultsRef.current[targetId] = [];
          }
          resultsRef.current[targetId].push(data.result);
          if (resultsRef.current[targetId].length > 200) {
            resultsRef.current[targetId].shift();
          }
        }
      };

      ws.onclose = () => {
        setConnected(false);
        scheduleReconnect();
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (e) {
      scheduleReconnect();
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimerRef.current) return;
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null;
      connect();
    }, 3000);
  }, [connect]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
    };
  }, [connect]);

  const getResults = useCallback((targetId) => {
    return resultsRef.current[targetId] || [];
  }, []);

  const setTargetsData = useCallback((newTargets) => {
    setTargets(newTargets);
  }, []);

  const setAlertsData = useCallback((newAlerts) => {
    setAlerts(newAlerts);
  }, []);

  return {
    connected,
    targets,
    alerts,
    getResults,
    setTargets: setTargetsData,
    setAlerts: setAlertsData
  };
}
