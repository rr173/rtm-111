import { useState, useEffect, useRef, useCallback } from 'react';

export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const [targets, setTargets] = useState([]);
  const [groups, setGroups] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const resultsRef = useRef({});
  const connectedRef = useRef(false);

  const loadInitialData = useCallback(async () => {
    try {
      const apiBase = import.meta.env.VITE_API_HTTP_URL || '';
      const [targetsRes, groupsRes, alertsRes] = await Promise.all([
        fetch(`${apiBase}/api/targets`),
        fetch(`${apiBase}/api/groups`),
        fetch(`${apiBase}/api/alerts?limit=50`)
      ]);
      if (targetsRes.ok && groupsRes.ok && alertsRes.ok) {
        const [targetsData, groupsData, alertsData] = await Promise.all([
          targetsRes.json(),
          groupsRes.json(),
          alertsRes.json()
        ]);
        setTargets(targetsData);
        setGroups(groupsData);
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
          setGroups(data.groups || []);
          setAlerts(prevAlerts => {
            const snapshotAlerts = data.alerts || [];
            const merged = new Map();
            for (const a of prevAlerts) {
              merged.set(a.id, a);
            }
            for (const a of snapshotAlerts) {
              merged.set(a.id, a);
            }
            return Array.from(merged.values())
              .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
              .slice(0, 100);
          });

          if (data.targets) {
            for (const target of data.targets) {
              if (target.recent_results && target.recent_results.length > 0) {
                const existing = resultsRef.current[target.id] || [];
                const merged = new Map();
                for (const r of existing) {
                  merged.set(r.timestamp, r);
                }
                for (const r of target.recent_results) {
                  merged.set(r.timestamp, r);
                }
                const sorted = Array.from(merged.values())
                  .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
                if (sorted.length > 200) {
                  resultsRef.current[target.id] = sorted.slice(-200);
                } else {
                  resultsRef.current[target.id] = sorted;
                }
              }
            }
          }
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

  const setGroupsData = useCallback((newGroups) => {
    setGroups(newGroups);
  }, []);

  const setAlertsData = useCallback((newAlerts) => {
    setAlerts(newAlerts);
  }, []);

  return {
    connected,
    targets,
    groups,
    alerts,
    getResults,
    setTargets: setTargetsData,
    setGroups: setGroupsData,
    setAlerts: setAlertsData,
    loadInitialData
  };
}
