import { useState } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

function CreateSnapshotModal({ onClose, onCreated }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [durationPreset, setDurationPreset] = useState('custom');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  const handlePresetChange = (preset) => {
    setDurationPreset(preset);
    const now = new Date();
    const end = new Date(now);
    
    let start;
    switch (preset) {
      case '5min':
        start = new Date(now.getTime() - 5 * 60 * 1000);
        break;
      case '15min':
        start = new Date(now.getTime() - 15 * 60 * 1000);
        break;
      case '30min':
        start = new Date(now.getTime() - 30 * 60 * 1000);
        break;
      case '1hour':
        start = new Date(now.getTime() - 60 * 60 * 1000);
        break;
      case '2hour':
        start = new Date(now.getTime() - 2 * 60 * 60 * 1000);
        break;
      case '6hour':
        start = new Date(now.getTime() - 6 * 60 * 60 * 1000);
        break;
      case '24hour':
        start = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        break;
      default:
        return;
    }

    setStartTime(start.toISOString().slice(0, 16));
    setEndTime(end.toISOString().slice(0, 16));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!name.trim()) {
      setError('请输入快照名称');
      return;
    }
    if (!startTime || !endTime) {
      setError('请选择开始和结束时间');
      return;
    }

    const start = new Date(startTime);
    const end = new Date(endTime);
    if (start >= end) {
      setError('开始时间必须早于结束时间');
      return;
    }

    try {
      setCreating(true);
      const res = await fetch(`${API_BASE}/api/snapshots`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
          start_time: start.toISOString(),
          end_time: end.toISOString()
        })
      });

      if (res.ok) {
        onCreated();
      } else {
        const data = await res.json();
        setError(data.detail || '创建失败，请重试');
      }
    } catch (e) {
      console.error('Failed to create snapshot:', e);
      setError('网络错误，请重试');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content create-snapshot-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>📸 创建快照</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body">
          <div className="form-group">
            <label>快照名称 *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：上线前基线、v2.0发布后"
              className="edit-input"
              required
            />
          </div>

          <div className="form-group">
            <label>备注信息</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="例如：2024.06.11 新功能上线前基准数据"
              className="edit-textarea"
              rows={2}
            />
          </div>

          <div className="form-group">
            <label>快速选择时间段</label>
            <div className="preset-buttons">
              <button
                type="button"
                className={`preset-btn ${durationPreset === '5min' ? 'active' : ''}`}
                onClick={() => handlePresetChange('5min')}
              >
                最近5分钟
              </button>
              <button
                type="button"
                className={`preset-btn ${durationPreset === '15min' ? 'active' : ''}`}
                onClick={() => handlePresetChange('15min')}
              >
                最近15分钟
              </button>
              <button
                type="button"
                className={`preset-btn ${durationPreset === '30min' ? 'active' : ''}`}
                onClick={() => handlePresetChange('30min')}
              >
                最近30分钟
              </button>
              <button
                type="button"
                className={`preset-btn ${durationPreset === '1hour' ? 'active' : ''}`}
                onClick={() => handlePresetChange('1hour')}
              >
                最近1小时
              </button>
              <button
                type="button"
                className={`preset-btn ${durationPreset === '2hour' ? 'active' : ''}`}
                onClick={() => handlePresetChange('2hour')}
              >
                最近2小时
              </button>
              <button
                type="button"
                className={`preset-btn ${durationPreset === '6hour' ? 'active' : ''}`}
                onClick={() => handlePresetChange('6hour')}
              >
                最近6小时
              </button>
              <button
                type="button"
                className={`preset-btn ${durationPreset === '24hour' ? 'active' : ''}`}
                onClick={() => handlePresetChange('24hour')}
              >
                最近24小时
              </button>
              <button
                type="button"
                className={`preset-btn ${durationPreset === 'custom' ? 'active' : ''}`}
                onClick={() => setDurationPreset('custom')}
              >
                自定义
              </button>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>开始时间 *</label>
              <input
                type="datetime-local"
                value={startTime}
                onChange={(e) => {
                  setStartTime(e.target.value);
                  setDurationPreset('custom');
                }}
                className="edit-input"
                required
              />
            </div>
            <div className="form-group">
              <label>结束时间 *</label>
              <input
                type="datetime-local"
                value={endTime}
                onChange={(e) => {
                  setEndTime(e.target.value);
                  setDurationPreset('custom');
                }}
                className="edit-input"
                required
              />
            </div>
          </div>

          {startTime && endTime && (
            <div className="time-range-info">
              <span>
                选中时间段：
                {new Date(startTime).toLocaleString('zh-CN')}
                {' ~ '}
                {new Date(endTime).toLocaleString('zh-CN')}
              </span>
              <span className="duration-badge">
                时长：{Math.round((new Date(endTime) - new Date(startTime)) / 60000)} 分钟
              </span>
            </div>
          )}

          {error && <div className="error-message">{error}</div>}

          <div className="modal-footer">
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={creating}
            >
              取消
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={creating}
            >
              {creating ? '创建中...' : '创建快照'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default CreateSnapshotModal;
