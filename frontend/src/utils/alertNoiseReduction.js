const SEVERITY_SCORE = {
  down: 100,
  degraded: 50,
  partial: 30,
  healthy: 0
};

const DEFAULT_MERGE_RULES = [
  {
    id: 'rule-same-target',
    name: '同一目标归并',
    description: '将同一目标在时间窗口内的告警归并为一组',
    type: 'target',
    enabled: true,
    windowSeconds: 300,
    priority: 100
  },
  {
    id: 'rule-same-group',
    name: '同一分组归并',
    description: '将同一分组在时间窗口内的告警归并为一组',
    type: 'group',
    enabled: true,
    windowSeconds: 600,
    priority: 80
  },
  {
    id: 'rule-dependency-chain',
    name: '依赖链路归并',
    description: '将存在依赖关系的目标在时间窗口内的告警归并为一组',
    type: 'dependency',
    enabled: true,
    windowSeconds: 900,
    priority: 60
  }
];

const DEFAULT_SUPPRESSION_RULES = [
  {
    id: 'suppress-maintenance',
    name: '维护状态静默',
    description: '处于维护状态的目标所有告警直接静默',
    enabled: true,
    priority: 100,
    conditions: [
      { field: 'target_paused', operator: 'equals', value: true }
    ]
  },
  {
    id: 'suppress-silenced',
    name: '已静默目标告警',
    description: '已标记为静默的目标不展示告警',
    enabled: true,
    priority: 90,
    conditions: [
      { field: 'target_silenced', operator: 'equals', value: true }
    ]
  },
  {
    id: 'suppress-low-severity',
    name: '低严重度告警抑制',
    description: 'healthy 状态的恢复告警不单独展示',
    enabled: false,
    priority: 50,
    conditions: [
      { field: 'to_status', operator: 'equals', value: 'healthy' }
    ]
  }
];

const TARGET_IMPORTANCE_WEIGHTS = {
  critical: 3.0,
  high: 2.0,
  medium: 1.5,
  low: 1.0,
  default: 1.0
};

function generateId() {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

function evaluateCondition(alert, condition, targets = []) {
  const target = targets.find(t => t.id === alert.target_id);
  
  let fieldValue;
  switch (condition.field) {
    case 'target_paused':
      fieldValue = target?.paused || false;
      break;
    case 'target_silenced':
      fieldValue = target?.silenced || false;
      break;
    case 'target_group_id':
      fieldValue = target?.group_id;
      break;
    case 'target_id':
      fieldValue = alert.target_id;
      break;
    case 'to_status':
    case 'from_status':
      fieldValue = alert[condition.field];
      break;
    default:
      fieldValue = alert[condition.field];
  }

  switch (condition.operator) {
    case 'equals':
      return fieldValue === condition.value;
    case 'not_equals':
      return fieldValue !== condition.value;
    case 'in':
      return Array.isArray(condition.value) && condition.value.includes(fieldValue);
    case 'contains':
      return typeof fieldValue === 'string' && fieldValue.includes(condition.value);
    case 'greater_than':
      return typeof fieldValue === 'number' && fieldValue > condition.value;
    case 'less_than':
      return typeof fieldValue === 'number' && fieldValue < condition.value;
    default:
      return false;
  }
}

function checkSuppression(alert, suppressionRules, targets = []) {
  const sortedRules = [...suppressionRules]
    .filter(r => r.enabled)
    .sort((a, b) => b.priority - a.priority);

  for (const rule of sortedRules) {
    const allConditionsMet = rule.conditions.every(cond => 
      evaluateCondition(alert, cond, targets)
    );
    if (allConditionsMet) {
      return { suppressed: true, rule };
    }
  }
  return { suppressed: false, rule: null };
}

function findTargetDependencies(targetId, dependencies = []) {
  const relatedIds = new Set([targetId]);
  
  dependencies.forEach(dep => {
    if (dep.upstream_id === targetId) {
      relatedIds.add(dep.downstream_id);
    }
    if (dep.downstream_id === targetId) {
      relatedIds.add(dep.upstream_id);
    }
  });
  
  return Array.from(relatedIds);
}

function shouldMergeAlerts(alert1, alert2, rule, targets = [], dependencies = []) {
  const now = Date.now();
  const t1 = new Date(alert1.timestamp).getTime();
  const t2 = new Date(alert2.timestamp).getTime();
  
  if (Math.abs(t1 - t2) > rule.windowSeconds * 1000) {
    return false;
  }

  const target1 = targets.find(t => t.id === alert1.target_id);
  const target2 = targets.find(t => t.id === alert2.target_id);

  switch (rule.type) {
    case 'target':
      return alert1.target_id === alert2.target_id;
    
    case 'group':
      return target1?.group_id && target2?.group_id && 
             target1.group_id === target2.group_id;
    
    case 'dependency': {
      const relatedIds = findTargetDependencies(alert1.target_id, dependencies);
      return relatedIds.includes(alert2.target_id);
    }
    
    case 'custom':
      return rule.customMatch ? rule.customMatch(alert1, alert2, targets, dependencies) : false;
    
    default:
      return false;
  }
}

function calculateSeverityScore(group, targets = []) {
  if (!group.alerts || group.alerts.length === 0) return 0;

  let baseScore = 0;
  let totalWeight = 0;

  group.alerts.forEach(alert => {
    const target = targets.find(t => t.id === alert.target_id);
    const importance = target?.importance || 'default';
    const weight = TARGET_IMPORTANCE_WEIGHTS[importance] || TARGET_IMPORTANCE_WEIGHTS.default;
    
    const alertSeverity = SEVERITY_SCORE[alert.to_status] || 0;
    baseScore += alertSeverity * weight;
    totalWeight += weight;
  });

  const avgSeverity = totalWeight > 0 ? baseScore / totalWeight : 0;

  const alertCount = group.alerts.length;
  const countMultiplier = Math.min(1 + (alertCount - 1) * 0.2, 3.0);

  const firstAlertTime = new Date(group.started_at).getTime();
  const lastAlertTime = new Date(group.last_updated_at).getTime();
  const durationHours = Math.max((lastAlertTime - firstAlertTime) / (1000 * 60 * 60), 0.01);
  const durationMultiplier = Math.min(1 + Math.log2(durationHours + 1) * 0.5, 2.5);

  const finalScore = Math.round(avgSeverity * countMultiplier * durationMultiplier);

  return Math.min(finalScore, 1000);
}

function getSeverityLevel(score) {
  if (score >= 400) return { level: 'critical', label: '严重', color: '#ef4444' };
  if (score >= 200) return { level: 'high', label: '高危', color: '#f97316' };
  if (score >= 100) return { level: 'medium', label: '中等', color: '#eab308' };
  if (score >= 50) return { level: 'low', label: '低危', color: '#3b82f6' };
  return { level: 'info', label: '提示', color: '#64748b' };
}

function mergeAlertsIntoGroups(alerts, mergeRules, targets = [], dependencies = []) {
  const activeRules = [...mergeRules]
    .filter(r => r.enabled)
    .sort((a, b) => b.priority - a.priority);

  const sortedAlerts = [...alerts].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  const groups = [];

  sortedAlerts.forEach(alert => {
    let merged = false;

    for (const rule of activeRules) {
      if (merged) break;

      for (const group of groups) {
        if (merged) break;

        const lastAlertInGroup = group.alerts[group.alerts.length - 1];
        if (shouldMergeAlerts(alert, lastAlertInGroup, rule, targets, dependencies)) {
          group.alerts.push(alert);
          group.last_updated_at = alert.timestamp;
          group.rule_ids = group.rule_ids || [];
          if (!group.rule_ids.includes(rule.id)) {
            group.rule_ids.push(rule.id);
          }
          group.affected_target_ids = new Set([...group.affected_target_ids, alert.target_id]);
          merged = true;
        }
      }
    }

    if (!merged) {
      groups.push({
        id: generateId(),
        alerts: [alert],
        started_at: alert.timestamp,
        last_updated_at: alert.timestamp,
        rule_ids: [],
        affected_target_ids: new Set([alert.target_id]),
        acknowledged: false
      });
    }
  });

  return groups.map(group => {
    const targetIds = Array.from(group.affected_target_ids);
    const affectedTargets = targetIds.map(tid => targets.find(t => t.id === tid)).filter(Boolean);
    const groupName = generateGroupName(group, affectedTargets);
    
    return {
      ...group,
      affected_target_ids: targetIds,
      affected_targets: affectedTargets,
      name: groupName,
      severity_score: calculateSeverityScore(group, targets),
      alert_count: group.alerts.length,
      target_count: targetIds.length
    };
  }).sort((a, b) => b.severity_score - a.severity_score);
}

function generateGroupName(group, targets) {
  if (targets.length === 0) {
    return `告警组 (${group.alerts.length} 条告警)`;
  }

  if (targets.length === 1) {
    return `${targets[0].name} 相关告警`;
  }

  const mainTarget = targets[0];
  return `${mainTarget.name} 等 ${targets.length} 个目标关联告警`;
}

function processAlerts(rawAlerts, options = {}) {
  const {
    mergeRules = DEFAULT_MERGE_RULES,
    suppressionRules = DEFAULT_SUPPRESSION_RULES,
    targets = [],
    dependencies = [],
    now = Date.now()
  } = options;

  const suppressedAlerts = [];
  const passThroughAlerts = [];

  rawAlerts.forEach(alert => {
    const result = checkSuppression(alert, suppressionRules, targets);
    if (result.suppressed) {
      suppressedAlerts.push({
        ...alert,
        suppressed_by: result.rule,
        suppressed_at: new Date(now).toISOString()
      });
    } else {
      passThroughAlerts.push(alert);
    }
  });

  const groups = mergeAlertsIntoGroups(passThroughAlerts, mergeRules, targets, dependencies);

  return {
    groups,
    suppressed_alerts: suppressedAlerts,
    raw_alerts: rawAlerts,
    stats: {
      total_raw: rawAlerts.length,
      total_groups: groups.length,
      total_suppressed: suppressedAlerts.length,
      total_displayed: passThroughAlerts.length,
      noise_reduction_ratio: rawAlerts.length > 0 
        ? Math.round((1 - groups.length / rawAlerts.length) * 10000) / 100 
        : 0
    }
  };
}

function generateHourlyStats(processedData, hours = 24) {
  const hourly = [];
  const now = new Date();
  
  for (let i = hours - 1; i >= 0; i--) {
    const hourStart = new Date(now);
    hourStart.setHours(now.getHours() - i, 0, 0, 0);
    const hourEnd = new Date(hourStart);
    hourEnd.setHours(hourStart.getHours() + 1);

    const inRange = (ts) => {
      const t = new Date(ts).getTime();
      return t >= hourStart.getTime() && t < hourEnd.getTime();
    };

    const rawInHour = processedData.raw_alerts.filter(a => inRange(a.timestamp));
    const suppressedInHour = processedData.suppressed_alerts.filter(a => inRange(a.timestamp));
    
    const passThrough = rawInHour.filter(a => 
      !suppressedInHour.find(s => s.id === a.id)
    );

    let groupsInHour = 0;
    processedData.groups.forEach(g => {
      if (inRange(g.started_at) || inRange(g.last_updated_at)) {
        groupsInHour++;
      }
    });

    hourly.push({
      hour: hourStart.getHours(),
      label: `${hourStart.getHours().toString().padStart(2, '0')}:00`,
      raw_count: rawInHour.length,
      group_count: groupsInHour,
      suppressed_count: suppressedInHour.length,
      displayed_count: passThrough.length,
      noise_reduction_ratio: rawInHour.length > 0
        ? Math.round((1 - groupsInHour / Math.max(rawInHour.length, 1)) * 10000) / 100
        : 0
    });
  }

  return hourly;
}

export {
  DEFAULT_MERGE_RULES,
  DEFAULT_SUPPRESSION_RULES,
  TARGET_IMPORTANCE_WEIGHTS,
  SEVERITY_SCORE,
  generateId,
  evaluateCondition,
  checkSuppression,
  findTargetDependencies,
  shouldMergeAlerts,
  calculateSeverityScore,
  getSeverityLevel,
  mergeAlertsIntoGroups,
  processAlerts,
  generateHourlyStats
};
