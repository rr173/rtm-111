import { useMemo } from 'react';

function LatencyChart({ results = [] }) {
  const width = 600;
  const height = 180;
  const padding = { top: 20, right: 20, bottom: 30, left: 50 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const { points, maxLatency, minLatency, pathD, areaD } = useMemo(() => {
    if (!results || results.length === 0) {
      return { points: [], maxLatency: 100, minLatency: 0, pathD: '', areaD: '' };
    }

    const validResults = results.filter(r => r.success && r.latency_ms != null);

    if (validResults.length === 0) {
      return { points: [], maxLatency: 100, minLatency: 0, pathD: '', areaD: '' };
    }

    const latencies = validResults.map(r => r.latency_ms);
    const maxLat = Math.max(...latencies) * 1.1;
    const minLat = Math.min(...latencies) * 0.9;
    const range = maxLat - minLat || 1;

    const n = validResults.length;
    const pts = validResults.map((r, i) => {
      const x = padding.left + (i / (n - 1 || 1)) * chartWidth;
      const y = padding.top + chartHeight - ((r.latency_ms - minLat) / range) * chartHeight;
      return { x, y, latency: r.latency_ms, time: r.timestamp };
    });

    let path = '';
    let area = '';

    if (pts.length > 0) {
      path = `M ${pts[0].x} ${pts[0].y}`;
      for (let i = 1; i < pts.length; i++) {
        const prev = pts[i - 1];
        const curr = pts[i];
        const cpx1 = prev.x + (curr.x - prev.x) / 3;
        const cpy1 = prev.y;
        const cpx2 = prev.x + 2 * (curr.x - prev.x) / 3;
        const cpy2 = curr.y;
        path += ` C ${cpx1} ${cpy1}, ${cpx2} ${cpy2}, ${curr.x} ${curr.y}`;
      }

      area = path + ` L ${pts[pts.length - 1].x} ${padding.top + chartHeight} L ${pts[0].x} ${padding.top + chartHeight} Z`;
    }

    return {
      points: pts,
      maxLatency: maxLat,
      minLatency: minLat,
      pathD: path,
      areaD: area
    };
  }, [results]);

  const yTicks = useMemo(() => {
    const ticks = [];
    const range = maxLatency - minLatency;
    for (let i = 0; i <= 4; i++) {
      const value = minLatency + (range * i) / 4;
      const y = padding.top + chartHeight - (i / 4) * chartHeight;
      ticks.push({ value: value.toFixed(0), y });
    }
    return ticks;
  }, [maxLatency, minLatency]);

  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id="latencyGradient" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.05" />
        </linearGradient>
      </defs>

      {yTicks.map((tick, i) => (
        <g key={i}>
          <line
            x1={padding.left}
            y1={tick.y}
            x2={width - padding.right}
            y2={tick.y}
            stroke="#334155"
            strokeWidth="1"
            strokeDasharray="3,3"
          />
          <text
            x={padding.left - 8}
            y={tick.y + 4}
            textAnchor="end"
            fill="#64748b"
            fontSize="11"
          >
            {tick.value}ms
          </text>
        </g>
      ))}

      {areaD && (
        <path
          d={areaD}
          fill="url(#latencyGradient)"
        />
      )}

      {pathD && (
        <path
          d={pathD}
          fill="none"
          stroke="#3b82f6"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}

      {points.filter((_, i) => i % Math.max(1, Math.floor(points.length / 10)) === 0).map((point, i) => (
        <circle
          key={i}
          cx={point.x}
          cy={point.y}
          r="3"
          fill="#3b82f6"
          stroke="#0f172a"
          strokeWidth="2"
        />
      ))}

      <line
        x1={padding.left}
        y1={padding.top + chartHeight}
        x2={width - padding.right}
        y2={padding.top + chartHeight}
        stroke="#475569"
        strokeWidth="1"
      />
    </svg>
  );
}

export default LatencyChart;
