import { generateId } from './alertNoiseReduction';

function generateDemoTargets() {
  const now = new Date();
  return [
    {
      id: 1,
      group_id: 1,
      name: 'API网关-生产环境',
      type: 'http',
      address: 'https://api.example.com',
      status: 'down',
      paused: false,
      silenced: false,
      importance: 'critical',
      consecutive_failures: 15,
      last_check: new Date(now.getTime() - 30000).toISOString()
    },
    {
      id: 2,
      group_id: 1,
      name: '用户服务-生产环境',
      type: 'http',
      address: 'https://user.example.com',
      status: 'degraded',
      paused: false,
      silenced: false,
      importance: 'high',
      consecutive_failures: 8,
      last_check: new Date(now.getTime() - 45000).toISOString()
    },
    {
      id: 3,
      group_id: 1,
      name: '订单服务-生产环境',
      type: 'http',
      address: 'https://order.example.com',
      status: 'degraded',
      paused: false,
      silenced: false,
      importance: 'high',
      consecutive_failures: 6,
      last_check: new Date(now.getTime() - 60000).toISOString()
    },
    {
      id: 4,
      group_id: 2,
      name: '数据库主库-生产',
      type: 'tcp',
      address: 'db-master.example.com:3306',
      status: 'down',
      paused: false,
      silenced: false,
      importance: 'critical',
      consecutive_failures: 20,
      last_check: new Date(now.getTime() - 20000).toISOString()
    },
    {
      id: 5,
      group_id: 2,
      name: 'Redis缓存集群',
      type: 'tcp',
      address: 'redis.example.com:6379',
      status: 'degraded',
      paused: false,
      silenced: false,
      importance: 'medium',
      consecutive_failures: 4,
      last_check: new Date(now.getTime() - 90000).toISOString()
    },
    {
      id: 6,
      group_id: 3,
      name: '日志收集服务-测试',
      type: 'http',
      address: 'https://log-test.example.com',
      status: 'healthy',
      paused: true,
      silenced: false,
      importance: 'low',
      consecutive_failures: 0,
      last_check: new Date(now.getTime() - 120000).toISOString()
    },
    {
      id: 7,
      group_id: 3,
      name: '监控大盘-测试',
      type: 'http',
      address: 'https://grafana-test.example.com',
      status: 'degraded',
      paused: false,
      silenced: true,
      importance: 'low',
      consecutive_failures: 3,
      last_check: new Date(now.getTime() - 150000).toISOString()
    },
    {
      id: 8,
      group_id: 1,
      name: '支付服务-生产环境',
      type: 'http',
      address: 'https://pay.example.com',
      status: 'down',
      paused: false,
      silenced: false,
      importance: 'critical',
      consecutive_failures: 12,
      last_check: new Date(now.getTime() - 25000).toISOString()
    }
  ];
}

function generateDemoGroups() {
  return [
    { id: 1, name: '核心业务服务', description: '生产环境核心业务线', color: '#3b82f6' },
    { id: 2, name: '基础存储服务', description: '数据库、缓存等基础设施', color: '#8b5cf6' },
    { id: 3, name: '测试环境服务', description: '测试与预发环境', color: '#64748b' }
  ];
}

function generateDemoDependencies() {
  return [
    { id: 1, upstream_id: 4, downstream_id: 1, description: 'API网关依赖数据库' },
    { id: 2, upstream_id: 4, downstream_id: 2, description: '用户服务依赖数据库' },
    { id: 3, upstream_id: 4, downstream_id: 3, description: '订单服务依赖数据库' },
    { id: 4, upstream_id: 5, downstream_id: 1, description: 'API网关依赖Redis' },
    { id: 5, upstream_id: 5, downstream_id: 3, description: '订单服务依赖Redis' },
    { id: 6, upstream_id: 1, downstream_id: 2, description: '用户服务通过API网关访问' },
    { id: 7, upstream_id: 1, downstream_id: 3, description: '订单服务通过API网关访问' },
    { id: 8, upstream_id: 1, downstream_id: 8, description: '支付服务通过API网关访问' },
    { id: 9, upstream_id: 4, downstream_id: 8, description: '支付服务依赖数据库' }
  ];
}

function generateDemoAlerts() {
  const now = new Date();
  const alerts = [];
  let alertId = 1;

  const scenarios = [
    {
      targetId: 4,
      targetName: '数据库主库-生产',
      events: [
        { offset: -7200, from: 'healthy', to: 'degraded' },
        { offset: -6900, from: 'degraded', to: 'down' },
        { offset: -6600, from: 'down', to: 'degraded' },
        { offset: -6300, from: 'degraded', to: 'down' },
        { offset: -6000, from: 'down', to: 'degraded' },
        { offset: -5700, from: 'degraded', to: 'down' },
        { offset: -5400, from: 'down', to: 'degraded' },
        { offset: -5100, from: 'degraded', to: 'down' }
      ]
    },
    {
      targetId: 1,
      targetName: 'API网关-生产环境',
      events: [
        { offset: -7000, from: 'healthy', to: 'degraded' },
        { offset: -6800, from: 'degraded', to: 'down' },
        { offset: -6500, from: 'down', to: 'degraded' },
        { offset: -6200, from: 'degraded', to: 'down' },
        { offset: -5900, from: 'down', to: 'degraded' },
        { offset: -5600, from: 'degraded', to: 'down' },
        { offset: -5300, from: 'down', to: 'degraded' },
        { offset: -5000, from: 'degraded', to: 'down' }
      ]
    },
    {
      targetId: 2,
      targetName: '用户服务-生产环境',
      events: [
        { offset: -6900, from: 'healthy', to: 'degraded' },
        { offset: -6400, from: 'degraded', to: 'down' },
        { offset: -5800, from: 'down', to: 'degraded' },
        { offset: -5200, from: 'degraded', to: 'down' },
        { offset: -4600, from: 'down', to: 'degraded' },
        { offset: -4000, from: 'degraded', to: 'down' }
      ]
    },
    {
      targetId: 3,
      targetName: '订单服务-生产环境',
      events: [
        { offset: -6850, from: 'healthy', to: 'degraded' },
        { offset: -6250, from: 'degraded', to: 'down' },
        { offset: -5650, from: 'down', to: 'degraded' },
        { offset: -5050, from: 'degraded', to: 'down' },
        { offset: -4450, from: 'down', to: 'degraded' }
      ]
    },
    {
      targetId: 8,
      targetName: '支付服务-生产环境',
      events: [
        { offset: -6950, from: 'healthy', to: 'degraded' },
        { offset: -6350, from: 'degraded', to: 'down' },
        { offset: -5750, from: 'down', to: 'degraded' },
        { offset: -5150, from: 'degraded', to: 'down' },
        { offset: -4550, from: 'down', to: 'degraded' },
        { offset: -3950, from: 'degraded', to: 'down' }
      ]
    },
    {
      targetId: 5,
      targetName: 'Redis缓存集群',
      events: [
        { offset: -3600, from: 'healthy', to: 'degraded' },
        { offset: -3300, from: 'degraded', to: 'partial' },
        { offset: -3000, from: 'partial', to: 'degraded' },
        { offset: -2700, from: 'degraded', to: 'partial' },
        { offset: -2400, from: 'partial', to: 'degraded' }
      ]
    },
    {
      targetId: 6,
      targetName: '日志收集服务-测试',
      events: [
        { offset: -1800, from: 'healthy', to: 'degraded' },
        { offset: -1500, from: 'degraded', to: 'down' },
        { offset: -1200, from: 'down', to: 'degraded' }
      ]
    },
    {
      targetId: 7,
      targetName: '监控大盘-测试',
      events: [
        { offset: -900, from: 'healthy', to: 'degraded' },
        { offset: -600, from: 'degraded', to: 'down' },
        { offset: -300, from: 'down', to: 'degraded' }
      ]
    }
  ];

  scenarios.forEach(scenario => {
    scenario.events.forEach(event => {
      alerts.push({
        id: alertId++,
        target_id: scenario.targetId,
        target_name: scenario.targetName,
        timestamp: new Date(now.getTime() + event.offset * 1000).toISOString(),
        from_status: event.from,
        to_status: event.to,
        acknowledged: false,
        acknowledged_at: null
      });
    });
  });

  const earlierAlerts = [
    { targetId: 4, targetName: '数据库主库-生产', count: 8, spreadHours: 20, minOffset: 3 },
    { targetId: 1, targetName: 'API网关-生产环境', count: 6, spreadHours: 18, minOffset: 4 },
    { targetId: 2, targetName: '用户服务-生产环境', count: 5, spreadHours: 15, minOffset: 5 },
    { targetId: 5, targetName: 'Redis缓存集群', count: 4, spreadHours: 12, minOffset: 6 },
    { targetId: 3, targetName: '订单服务-生产环境', count: 3, spreadHours: 10, minOffset: 7 }
  ];

  earlierAlerts.forEach(scenario => {
    for (let i = 0; i < scenario.count; i++) {
      const hoursAgo = scenario.minOffset + (i / scenario.count) * scenario.spreadHours;
      const fromStates = ['healthy', 'degraded', 'partial', 'healthy'];
      const toStates = ['degraded', 'down', 'degraded', 'healthy'];
      const stateIdx = i % 4;
      
      alerts.push({
        id: alertId++,
        target_id: scenario.targetId,
        target_name: scenario.targetName,
        timestamp: new Date(now.getTime() - hoursAgo * 3600 * 1000).toISOString(),
        from_status: fromStates[stateIdx],
        to_status: toStates[stateIdx],
        acknowledged: i < scenario.count - 2,
        acknowledged_at: i < scenario.count - 2 
          ? new Date(now.getTime() - (hoursAgo - 0.1) * 3600 * 1000).toISOString() 
          : null
      });
    }
  });

  return alerts.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
}

export {
  generateDemoTargets,
  generateDemoGroups,
  generateDemoDependencies,
  generateDemoAlerts
};
