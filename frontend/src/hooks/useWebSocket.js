import { useState, useEffect, useRef, useCallback } from 'react';

function normalizeRoundResult(raw) {
  const observerResults = raw.observer_results || raw.results || [];
  const results = observerResults.map(r => ({
    observer_id: r.observer_id,
    observer_name: r.observer_name || r.name || '',
    observer_region: r.observer_region || r.region || '',
    observer_status: r.observer_status || (r.success ? 'online' : 'online'),
    success: r.success,
    latency_ms: r.latency_ms,
    error_message: r.error_message || r.error || null
  }));
  return {
    round_id: raw.round_id,
    timestamp: raw.timestamp,
    failure_type: raw.failure_type || raw.unified_status || 'all_healthy',
    unified_status: raw.unified_status,
    success_count: raw.success_count,
    failure_count: raw.failure_count,
    offline_count: raw.offline_count || 0,
    online_count: raw.online_count,
    results
  };
}

export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const [targets, setTargets] = useState([]);
  const [groups, setGroups] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [dependencies, setDependencies] = useState([]);
  const [observers, setObservers] = useState([]);
  const [observationMatrix, setObservationMatrix] = useState(null);
  const [targetRoundResultsMap, setTargetRoundResultsMap] = useState({});
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const resultsRef = useRef({});
  const roundResultsRef = useRef({});
  const connectedRef = useRef(false);

  const loadInitialData = useCallback(async () => {
    try {
      const apiBase = import.meta.env.VITE_API_HTTP_URL || '';
      const [targetsRes, groupsRes, alertsRes, depsRes, observersRes, matrixRes] = await Promise.all([
        fetch(`${apiBase}/api/targets`),
        fetch(`${apiBase}/api/groups`),
        fetch(`${apiBase}/api/alerts?limit=50`),
        fetch(`${apiBase}/api/dependencies`),
        fetch(`${apiBase}/api/observers`),
        fetch(`${apiBase}/api/observation-matrix`)
      ]);
      if (targetsRes.ok && groupsRes.ok && alertsRes.ok && depsRes.ok) {
        const [targetsData, groupsData, alertsData, depsData] = await Promise.all([
          targetsRes.json(),
          groupsRes.json(),
          alertsRes.json(),
          depsRes.json()
        ]);
        setTargets(targetsData);
        setGroups(groupsData);
        setAlerts(alertsData.reverse());
        setDependencies(depsData);
      }
      if (observersRes.ok) {
        const observersData = await observersRes.json();
        setObservers(observersData);
      }
      if (matrixRes.ok) {
        const matrixData = await matrixRes.json();
        setObservationMatrix(matrixData);
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
          setDependencies(data.dependencies || []);
          setObservers(data.observers || []);
          if (data.observation_matrix) {
            setObservationMatrix(data.observation_matrix);
          }
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
        } else if (data.type === 'observers_update') {
          setObservers(data.observers || []);
        } else if (data.type === 'targets_snapshot') {
          setTargets(data.targets || []);
        } else if (data.type === 'dependencies_update') {
          setDependencies(data.dependencies || []);
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
          if (data.result && data.result.round_id) {
            if (!roundResultsRef.current[targetId]) {
              roundResultsRef.current[targetId] = [];
            }
            const normalized = normalizeRoundResult(data.result);
            roundResultsRef.current[targetId].unshift(normalized);
            if (roundResultsRef.current[targetId].length > 50) {
              roundResultsRef.current[targetId].pop();
            }
            setTargetRoundResultsMap(prev => ({
              ...prev,
              [targetId]: [...roundResultsRef.current[targetId]]
            }));
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

  const setDependenciesData = useCallback((newDeps) => {
    setDependencies(newDeps);
  }, []);

  const setObserversData = useCallback((newObservers) => {
    setObservers(newObservers);
  }, []);

  const setObservationMatrixData = useCallback((newMatrix) => {
    setObservationMatrix(newMatrix);
  }, []);

  const getRoundResults = useCallback((targetId) => {
    return roundResultsRef.current[targetId] || [];
  }, []);

  return {
    connected,
    targets,
    groups,
    alerts,
    dependencies,
    observers,
    observationMatrix,
    targetRoundResultsMap,
    getResults,
    getRoundResults,
    setTargets: setTargetsData,
    setGroups: setGroupsData,
    setAlerts: setAlertsData,
    setDependencies: setDependenciesData,
    setObservers: setObserversData,
    setObservationMatrix: setObservationMatrixData,
    loadInitialData
  };
}
