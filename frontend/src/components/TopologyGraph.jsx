import { useState, useEffect, useRef, useMemo, useCallback } from 'react';

const NODE_WIDTH = 160;
const NODE_HEIGHT = 60;
const HORIZONTAL_GAP = 80;
const VERTICAL_GAP = 30;

function getStatusColor(status, cascadeAffected = false, isSimulated = false) {
  if (isSimulated) {
    return '#f97316';
  }
  if (cascadeAffected) {
    return '#a855f7';
  }
  switch (status) {
    case 'healthy':
      return '#22c55e';
    case 'degraded':
      return '#eab308';
    case 'down':
      return '#ef4444';
    default:
      return '#64748b';
  }
}

function getStatusBgColor(status, cascadeAffected = false, isSimulated = false) {
  if (isSimulated) {
    return 'rgba(249, 115, 22, 0.15)';
  }
  if (cascadeAffected) {
    return 'rgba(168, 85, 247, 0.15)';
  }
  switch (status) {
    case 'healthy':
      return 'rgba(34, 197, 94, 0.1)';
    case 'degraded':
      return 'rgba(234, 179, 8, 0.1)';
    case 'down':
      return 'rgba(239, 68, 68, 0.1)';
    default:
      return 'rgba(100, 116, 139, 0.1)';
  }
}

function getStatusLabel(status, cascadeAffected = false) {
  if (cascadeAffected) return '级联受损';
  switch (status) {
    case 'healthy': return '健康';
    case 'degraded': return '降级';
    case 'down': return '故障';
    default: return '未知';
  }
}

function calculateLayout(targets, dependencies) {
  if (targets.length === 0) return { nodes: [], layers: [] };

  const targetMap = new Map(targets.map(t => [t.id, t]));
  const inDegree = new Map();
  const outEdges = new Map();

  targets.forEach(t => {
    inDegree.set(t.id, 0);
    outEdges.set(t.id, []);
  });

  dependencies.forEach(dep => {
    if (targetMap.has(dep.upstream_id) && targetMap.has(dep.downstream_id)) {
      inDegree.set(dep.downstream_id, (inDegree.get(dep.downstream_id) || 0) + 1);
      outEdges.get(dep.upstream_id).push(dep.downstream_id);
    }
  });

  const layers = [];
  const visited = new Set();
  const currentLayer = [];

  inDegree.forEach((degree, id) => {
    if (degree === 0) {
      currentLayer.push(id);
      visited.add(id);
    }
  });

  while (currentLayer.length > 0) {
    layers.push([...currentLayer]);
    const nextLayer = [];

    currentLayer.forEach(nodeId => {
      outEdges.get(nodeId)?.forEach(neighborId => {
        if (!visited.has(neighborId)) {
          inDegree.set(neighborId, inDegree.get(neighborId) - 1);
          if (inDegree.get(neighborId) === 0) {
            nextLayer.push(neighborId);
            visited.add(neighborId);
          }
        }
      });
    });

    currentLayer.length = 0;
    currentLayer.push(...nextLayer);
  }

  targets.forEach(t => {
    if (!visited.has(t.id)) {
      if (layers.length === 0) {
        layers.push([t.id]);
      } else {
        layers[layers.length - 1].push(t.id);
      }
      visited.add(t.id);
    }
  });

  const nodes = [];
  const layerHeights = layers.map(layer =>
    layer.length * NODE_HEIGHT + (layer.length - 1) * VERTICAL_GAP
  );

  const totalWidth = layers.length * NODE_WIDTH + (layers.length - 1) * HORIZONTAL_GAP;
  const maxHeight = Math.max(...layerHeights, NODE_HEIGHT);

  layers.forEach((layer, layerIndex) => {
    const layerHeight = layerHeights[layerIndex];
    const startY = (maxHeight - layerHeight) / 2;

    layer.forEach((nodeId, nodeIndex) => {
      const target = targetMap.get(nodeId);
      if (target) {
        nodes.push({
          ...target,
          x: layerIndex * (NODE_WIDTH + HORIZONTAL_GAP),
          y: startY + nodeIndex * (NODE_HEIGHT + VERTICAL_GAP),
          layerIndex
        });
      }
    });
  });

  return { nodes, layers, totalWidth, totalHeight: maxHeight };
}

function ArrowMarker() {
  return (
    <defs>
      <marker
        id="arrowhead"
        markerWidth="10"
        markerHeight="7"
        refX="9"
        refY="3.5"
        orient="auto"
      >
        <polygon points="0 0, 10 3.5, 0 7" fill="#475569" />
      </marker>
      <marker
        id="arrowhead-simulated"
        markerWidth="10"
        markerHeight="7"
        refX="9"
        refY="3.5"
        orient="auto"
      >
        <polygon points="0 0, 10 3.5, 0 7" fill="#f97316" />
      </marker>
      <marker
        id="arrowhead-cascade"
        markerWidth="10"
        markerHeight="7"
        refX="9"
        refY="3.5"
        orient="auto"
      >
        <polygon points="0 0, 10 3.5, 0 7" fill="#a855f7" />
      </marker>
    </defs>
  );
}

export default function TopologyGraph({
  targets,
  dependencies,
  simulationTargetId,
  simulatedAffectedIds = [],
  onNodeClick,
  onNodeDoubleClick,
  onAddDependency
}) {
  const svgRef = useRef(null);
  const [pan, setPan] = useState({ x: 20, y: 20 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [selectedNode, setSelectedNode] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);

  const layout = useMemo(() =>
    calculateLayout(targets, dependencies),
    [targets, dependencies]
  );

  const nodeMap = useMemo(() => {
    const map = new Map();
    layout.nodes.forEach(n => map.set(n.id, n));
    return map;
  }, [layout.nodes]);

  const simulatedSet = useMemo(() => new Set(simulatedAffectedIds), [simulatedAffectedIds]);

  const getEdgePath = useCallback((fromNode, toNode) => {
    const startX = fromNode.x + NODE_WIDTH;
    const startY = fromNode.y + NODE_HEIGHT / 2;
    const endX = toNode.x;
    const endY = toNode.y + NODE_HEIGHT / 2;

    const midX = (startX + endX) / 2;

    return `M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX - 10} ${endY}`;
  }, []);

  const handleMouseDown = (e) => {
    if (e.target.tagName === 'svg' || e.target.classList.contains('graph-bg')) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e) => {
    if (isDragging) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleNodeClick = (node) => {
    setSelectedNode(node.id === selectedNode ? null : node.id);
    if (onNodeClick) {
      onNodeClick(node);
    }
  };

  const isEdgeSimulated = (dep) => {
    return simulationTargetId && (
      dep.upstream_id === simulationTargetId ||
      simulatedSet.has(dep.upstream_id)
    ) && simulatedSet.has(dep.downstream_id);
  };

  const isEdgeCascade = (dep) => {
    const upstream = nodeMap.get(dep.upstream_id);
    const downstream = nodeMap.get(dep.downstream_id);
    return downstream?.cascade_affected && upstream?.status !== 'healthy';
  };

  const svgWidth = Math.max(layout.totalWidth + 100, 600);
  const svgHeight = Math.max(layout.totalHeight + 100, 400);

  return (
    <div className="topology-graph-container">
      <div className="topology-legend">
        <div className="legend-item">
          <span className="legend-dot" style={{ backgroundColor: '#22c55e' }}></span>
          <span>健康</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot" style={{ backgroundColor: '#eab308' }}></span>
          <span>降级</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot" style={{ backgroundColor: '#ef4444' }}></span>
          <span>故障</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot" style={{ backgroundColor: '#a855f7' }}></span>
          <span>级联受损</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot" style={{ backgroundColor: '#f97316' }}></span>
          <span>模拟故障影响</span>
        </div>
      </div>

      <svg
        ref={svgRef}
        className="topology-svg"
        width="100%"
        height="500"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <ArrowMarker />
        <rect className="graph-bg" width="100%" height="100%" fill="transparent" />

        <g transform={`translate(${pan.x}, ${pan.y})`}>
          <g className="edges">
            {dependencies.map(dep => {
              const fromNode = nodeMap.get(dep.upstream_id);
              const toNode = nodeMap.get(dep.downstream_id);
              if (!fromNode || !toNode) return null;

              const isSimulated = isEdgeSimulated(dep);
              const isCascade = isEdgeCascade(dep);

              let markerEnd = 'url(#arrowhead)';
              let strokeColor = '#475569';
              let strokeWidth = 1.5;
              let opacity = 0.6;

              if (isSimulated) {
                markerEnd = 'url(#arrowhead-simulated)';
                strokeColor = '#f97316';
                strokeWidth = 2.5;
                opacity = 1;
              } else if (isCascade) {
                markerEnd = 'url(#arrowhead-cascade)';
                strokeColor = '#a855f7';
                strokeWidth = 2;
                opacity = 0.8;
              }

              return (
                <path
                  key={dep.id}
                  d={getEdgePath(fromNode, toNode)}
                  fill="none"
                  stroke={strokeColor}
                  strokeWidth={strokeWidth}
                  opacity={opacity}
                  markerEnd={markerEnd}
                />
              );
            })}
          </g>

          <g className="nodes">
            {layout.nodes.map(node => {
              const isSimulated = simulatedSet.has(node.id) || node.id === simulationTargetId;
              const isSource = node.id === simulationTargetId;
              const isSelected = selectedNode === node.id;
              const isHovered = hoveredNode === node.id;

              const color = getStatusColor(node.status, node.cascade_affected, isSimulated && !isSource);
              const bgColor = getStatusBgColor(node.status, node.cascade_affected, isSimulated && !isSource);

              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x}, ${node.y})`}
                  className={`topology-node ${isSelected ? 'selected' : ''} ${isHovered ? 'hovered' : ''}`}
                  onClick={() => handleNodeClick(node)}
                  onDoubleClick={() => onNodeDoubleClick?.(node)}
                  onMouseEnter={() => setHoveredNode(node.id)}
                  onMouseLeave={() => setHoveredNode(null)}
                  style={{ cursor: 'pointer' }}
                >
                  <rect
                    width={NODE_WIDTH}
                    height={NODE_HEIGHT}
                    rx="8"
                    fill={bgColor}
                    stroke={color}
                    strokeWidth={isSelected || isSource ? 3 : 2}
                    style={{
                      filter: isSource ? 'drop-shadow(0 0 8px rgba(249, 115, 22, 0.5))' : 'none'
                    }}
                  />

                  {isSource && (
                    <rect
                      x="-4"
                      y="-4"
                      width={NODE_WIDTH + 8}
                      height={NODE_HEIGHT + 8}
                      rx="10"
                      fill="none"
                      stroke="#f97316"
                      strokeWidth="2"
                      strokeDasharray="4 2"
                    />
                  )}

                  <text
                    x={NODE_WIDTH / 2}
                    y="24"
                    textAnchor="middle"
                    fontSize="13"
                    fontWeight="600"
                    fill="#f1f5f9"
                  >
                    {node.name.length > 14 ? node.name.slice(0, 14) + '...' : node.name}
                  </text>

                  <text
                    x={NODE_WIDTH / 2}
                    y="44"
                    textAnchor="middle"
                    fontSize="11"
                    fill={color}
                    fontWeight="500"
                  >
                    {isSource ? '模拟故障源' : getStatusLabel(node.status, node.cascade_affected)}
                  </text>

                  {node.paused && !node.cascade_affected && (
                    <circle cx={NODE_WIDTH - 12} cy="12" r="6" fill="#64748b" />
                  )}

                  {node.cascade_affected && (
                    <circle cx={NODE_WIDTH - 12} cy="12" r="6" fill="#a855f7" />
                  )}
                </g>
              );
            })}
          </g>
        </g>
      </svg>

      {hoveredNode && nodeMap.get(hoveredNode) && (
        <div className="node-tooltip">
          <div className="tooltip-name">{nodeMap.get(hoveredNode).name}</div>
          <div className="tooltip-status">
            状态: {getStatusLabel(
              nodeMap.get(hoveredNode).status,
              nodeMap.get(hoveredNode).cascade_affected
            )}
          </div>
          {nodeMap.get(hoveredNode).cascade_affected && (
            <div className="tooltip-cascade">
              级联源: {nodeMap.get(hoveredNode).cascade_source_name || '未知'}
            </div>
          )}
          <div className="tooltip-address">
            地址: {nodeMap.get(hoveredNode).address}
          </div>
        </div>
      )}
    </div>
  );
}
