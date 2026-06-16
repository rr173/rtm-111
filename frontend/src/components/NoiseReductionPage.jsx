import { useState, useMemo, useEffect } from 'react';
import { 
  processAlerts, 
  generateHourlyStats,
  DEFAULT_MERGE_RULES,
  DEFAULT_SUPPRESSION_RULES
} from '../utils/alertNoiseReduction';
import { 
  generateDemoTargets, 
  generateDemoGroups, 
  generateDemoDependencies, 
  generateDemoAlerts 
} from '../utils/demoDataGenerator';
import NoiseReductionDashboard from './NoiseReductionDashboard';
import AlertGroupList from './AlertGroupList';
import NoiseReductionRules from './NoiseReductionRules';

const LS_MERGE_RULES = 'nr_merge_rules';
const LS_SUPPRESSION_RULES = 'nr_suppression_rules';

function loadMergeRules() {
  try {
    const saved = localStorage.getItem(LS_MERGE_RULES);
    if (saved) {
      const parsed = JSON.parse(saved);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch (_) {}
  return DEFAULT_MERGE_RULES;
}

function loadSuppressionRules() {
  try {
    const saved = localStorage.getItem(LS_SUPPRESSION_RULES);
    if (saved) {
      const parsed = JSON.parse(saved);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch (_) {}
  return DEFAULT_SUPPRESSION_RULES;
}

function NoiseReductionPage({ realAlerts, realTargets, realDependencies, realGroups }) {
  const [activeView, setActiveView] = useState('dashboard');
  
  const useDemo = realAlerts.length === 0 || realTargets.length === 0;
  
  const demoTargets = useMemo(() => generateDemoTargets(), []);
  const demoGroups = useMemo(() => generateDemoGroups(), []);
  const demoDependencies = useMemo(() => generateDemoDependencies(), []);
  const demoAlerts = useMemo(() => generateDemoAlerts(), []);

  const targets = useDemo ? demoTargets : realTargets;
  const dependencies = useDemo ? demoDependencies : realDependencies;
  const groupsInfo = useDemo ? demoGroups : realGroups;
  const rawAlerts = useDemo ? demoAlerts : realAlerts;

  const [mergeRules, setMergeRulesState] = useState(loadMergeRules);
  const [suppressionRules, setSuppressionRulesState] = useState(loadSuppressionRules);
  const [alertGroups, setAlertGroups] = useState([]);
  const [rulesVersion, setRulesVersion] = useState(0);

  const setMergeRules = (next) => {
    const nextArr = Array.isArray(next) ? next : [...next];
    setMergeRulesState(nextArr);
    setRulesVersion(v => v + 1);
    try { localStorage.setItem(LS_MERGE_RULES, JSON.stringify(nextArr)); } catch (_) {}
  };

  const setSuppressionRules = (next) => {
    const nextArr = Array.isArray(next) ? next : [...next];
    setSuppressionRulesState(nextArr);
    setRulesVersion(v => v + 1);
    try { localStorage.setItem(LS_SUPPRESSION_RULES, JSON.stringify(nextArr)); } catch (_) {}
  };

  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === LS_MERGE_RULES) {
        try { 
          setMergeRulesState(JSON.parse(e.newValue)); 
          setRulesVersion(v => v + 1);
        } catch (_) {}
      }
      if (e.key === LS_SUPPRESSION_RULES) {
        try { 
          setSuppressionRulesState(JSON.parse(e.newValue)); 
          setRulesVersion(v => v + 1);
        } catch (_) {}
      }
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const processedData = useMemo(() => {
    const result = processAlerts(rawAlerts, {
      mergeRules,
      suppressionRules,
      targets,
      dependencies
    });
    return result;
  }, [rawAlerts, mergeRules, suppressionRules, targets, dependencies, rulesVersion]);

  const groupsWithAck = useMemo(() => {
    return processedData.groups.map(g => ({
      ...g,
      acknowledged: alertGroups.find(ag => ag.id === g.id)?.acknowledged || false
    }));
  }, [processedData.groups, alertGroups]);

  const hourlyStats = useMemo(() => {
    return generateHourlyStats(processedData, 24);
  }, [processedData]);

  const handleAcknowledgeGroup = (groupId, acknowledged) => {
    setAlertGroups(prev => {
      const existing = prev.find(g => g.id === groupId);
      if (existing) {
        return prev.map(g => g.id === groupId ? { ...g, acknowledged } : g);
      }
      return [...prev, { id: groupId, acknowledged }];
    });
  };

  return (
    <div className="noise-reduction-page">
      <div className="nr-page-header">
        <div className="nr-page-title">
          <h1>🔕 告警疲劳治理与智能降噪</h1>
          <p className="nr-page-subtitle">
            自动归并关联告警、抑制噪声告警，让值班人员聚焦真正重要的故障
          </p>
          {useDemo && (
            <span className="demo-badge">
              📋 演示模式 - 无实时数据时展示预置示例
            </span>
          )}
        </div>
        <div className="nr-view-tabs">
          <button
            className={`nr-view-tab ${activeView === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveView('dashboard')}
          >
            📊 降噪仪表盘
          </button>
          <button
            className={`nr-view-tab ${activeView === 'groups' ? 'active' : ''}`}
            onClick={() => setActiveView('groups')}
          >
            🚨 告警组 ({groupsWithAck.length})
          </button>
          <button
            className={`nr-view-tab ${activeView === 'rules' ? 'active' : ''}`}
            onClick={() => setActiveView('rules')}
          >
            ⚙️ 规则配置
          </button>
        </div>
      </div>

      <div className="nr-page-content">
        {activeView === 'dashboard' && (
          <NoiseReductionDashboard
            stats={processedData.stats}
            hourlyStats={hourlyStats}
            groups={groupsWithAck}
            suppressedAlerts={processedData.suppressed_alerts}
          />
        )}

        {activeView === 'groups' && (
          <AlertGroupList
            groups={groupsWithAck}
            targets={targets}
            dependencies={dependencies}
            onAcknowledgeGroup={handleAcknowledgeGroup}
          />
        )}

        {activeView === 'rules' && (
          <NoiseReductionRules
            mergeRules={mergeRules}
            suppressionRules={suppressionRules}
            onUpdateMergeRules={setMergeRules}
            onUpdateSuppressionRules={setSuppressionRules}
          />
        )}
      </div>
    </div>
  );
}

export default NoiseReductionPage;
