import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

export default function DependencyModal({
  isOpen,
  onClose,
  targets,
  dependencies,
  onDependenciesChange
}) {
  const [upstreamId, setUpstreamId] = useState('');
  const [downstreamId, setDownstreamId] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen) {
      setUpstreamId('');
      setDownstreamId('');
      setDescription('');
      setError('');
    }
  }, [isOpen]);

  const handleAddDependency = async () => {
    setError('');

    if (!upstreamId || !downstreamId) {
      setError('请选择上游和下游目标');
      return;
    }

    if (parseInt(upstreamId) === parseInt(downstreamId)) {
      setError('上游和下游不能是同一个目标');
      return;
    }

    const exists = dependencies.some(
      d => d.upstream_id === parseInt(upstreamId) && d.downstream_id === parseInt(downstreamId)
    );
    if (exists) {
      setError('该依赖关系已存在');
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/dependencies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          upstream_id: parseInt(upstreamId),
          downstream_id: parseInt(downstreamId),
          description
        })
      });

      if (res.ok) {
        const newDep = await res.json();
        if (onDependenciesChange) {
          const updatedDeps = await fetch(`${API_BASE}/api/dependencies`).then(r => r.json());
          onDependenciesChange(updatedDeps);
        }
        setUpstreamId('');
        setDownstreamId('');
        setDescription('');
      } else {
        const data = await res.json();
        setError(data.detail || '添加失败');
      }
    } catch (e) {
      setError('网络错误，请重试');
    }
  };

  const handleDeleteDependency = async (depId) => {
    if (!confirm('确定要删除这条依赖关系吗？')) return;

    try {
      const res = await fetch(`${API_BASE}/api/dependencies/${depId}`, {
        method: 'DELETE'
      });

      if (res.ok) {
        if (onDependenciesChange) {
          const updatedDeps = await fetch(`${API_BASE}/api/dependencies`).then(r => r.json());
          onDependenciesChange(updatedDeps);
        }
      }
    } catch (e) {
      console.error('Failed to delete dependency:', e);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal dependency-modal" onClick={e => e.stopPropagation()}>
        <h2>🔗 依赖关系管理</h2>

        <div className="dependency-add-section">
          <h3>添加依赖关系</h3>
          <p className="form-hint">选择上游目标和下游目标，表示上游故障会影响下游</p>

          <div className="form-row">
            <div className="form-group">
              <label>上游目标 (被依赖)</label>
              <select
                value={upstreamId}
                onChange={e => setUpstreamId(e.target.value)}
              >
                <option value="">请选择...</option>
                {targets.map(t => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>下游目标 (依赖)</label>
              <select
                value={downstreamId}
                onChange={e => setDownstreamId(e.target.value)}
              >
                <option value="">请选择...</option>
                {targets.map(t => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-group">
            <label>依赖描述（可选）</label>
            <input
              type="text"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="例如：API网关依赖数据库"
            />
          </div>

          {error && <div className="form-error">{error}</div>}

          <button className="btn btn-primary" onClick={handleAddDependency}>
            + 添加依赖
          </button>
        </div>

        <div className="dependency-list-section">
          <h3>已有依赖关系 ({dependencies.length})</h3>
          {dependencies.length === 0 ? (
            <p className="empty-text">暂无依赖关系</p>
          ) : (
            <div className="dependency-list">
              {dependencies.map(dep => (
                <div key={dep.id} className="dependency-item">
                  <div className="dependency-info">
                    <span className="dep-name dep-upstream">{dep.upstream_name}</span>
                    <span className="dep-arrow">→</span>
                    <span className="dep-name dep-downstream">{dep.downstream_name}</span>
                  </div>
                  {dep.description && (
                    <div className="dependency-desc">{dep.description}</div>
                  )}
                  <button
                    className="btn btn-secondary danger"
                    onClick={() => handleDeleteDependency(dep.id)}
                  >
                    删除
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}
