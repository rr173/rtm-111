import { useState, useEffect, useRef, useCallback } from 'react';

export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const [targets, setTargets] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const resultsRef = useRef({});
  const connectedRef = useRef(false);

  const loadInitialData = useCallback(async () => {
    try {
      const apiBase = import.meta.env.VITE_API_HTTP_URL || '';
      const [targetsRes, alertsRes] = await Promise.all([
        fetch(`${apiBase}/api/targets`),
        fetch(`${apiBase}/api/alerts?limit=50`)
      ]);
      if (targetsRes.ok && alertsRes.ok) {
        const [targetsData, alertsData] = await Promise.all([
          targetsRes.json(),
          alertsRes.json()
        ]);
        setTargets(targetsData);
        setAlerts(alertsData.reverse());
      }
    } catch (e) {
      console.error('Failed to load initial data:', e);
    }
  }, []);

  const connect = useCallback(() => {
    const apiBase = import.meta.env.VITE_API_URL || '';
    let wsUrl;

    if (apiBase) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      wsUrl = apiBase.replace(/^https?:/, protocol).replace(/^ws:/, protocol).replace(/^wss:/, protocol);
      if (!wsUrl.endsWith('/api/ws')) {
        wsUrl = wsUrl.replace(/\/$/, '') + '/api/ws';
      }
    } else {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      wsUrl = `${protocol}//${window.location.host}/api/ws`;
    }

    console.log('Connecting WebSocket:', wsUrl);

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected');
        setConnected(true);
        connectedRef.current = true;
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
        console.log('WebSocket disconnected');
        setConnected(false);
        connectedRef.current = false;
        scheduleReconnect();
      };

      ws.onerror = (e) => {
        console.error('WebSocket error');
      };
    } catch (e) {
      console.error('Failed to create WebSocket:', e);
      scheduleReconnect();
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimerRef.current) return;
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null;
      if (!connectedRef.current) {
        connect();
      }
    }, 3000);
  }, [connect]);

  useEffect(() => {
    loadInitialData();
    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
    };
  }, [connect, loadInitialData]);

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
    setAlerts: setAlertsData,
    loadInitialData
  };
}
