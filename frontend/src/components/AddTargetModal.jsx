import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_HTTP_URL || '';

function AddTargetModal({ onClose, onSubmit, groups = [], rules = [] }) {
  const [formData, setFormData] = useState({
    name: '',
    type: 'http',
    address: '',
    group_id: '',
    rule_id: '',
    interval: 30,
    timeout: 5,
    expected_status: '200',
    adaptive_enabled: false,
    slow_interval: 60,
    fast_interval: 5,
    silent_start: '',
    silent_end: ''
  });

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    let parsedValue = value;
    if (type === 'checkbox') {
      parsedValue = checked;
    } else if (name === 'interval' || name === 'timeout' || name === 'slow_interval' || name === 'fast_interval') {
      parsedValue = Number(value);
    } else if (name === 'group_id' || name === 'rule_id') {
      parsedValue = value === '' ? null : Number(value);
    }
    setFormData(prev => ({
      ...prev,
      [name]: parsedValue
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.name || !formData.address) return;

    const data = { ...formData };
    if (formData.type === 'tcp') {
      delete data.expected_status;
    }
    if (data.group_id === null) {
      delete data.group_id;
    }
    if (data.rule_id === null) {
      delete data.rule_id;
    }
    if (!data.silent_start || !data.silent_end) {
      delete data.silent_start;
      delete data.silent_end;
    }
    if (!data.adaptive_enabled) {
      delete data.slow_interval;
      delete data.fast_interval;
    }
    onSubmit(data);
  };

  const hasRule = !!formData.rule_id;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h2>添加探测目标</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>目标名称</label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              placeholder="例如：网站首页"
              required
            />
          </div>

          {groups.length > 0 && (
            <div className="form-group">
              <label>所属分组</label>
              <select
                name="group_id"
                value={formData.group_id === null ? '' : formData.group_id}
                onChange={handleChange}
              >
                <option value="">未分组</option>
                {groups.map(group => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {rules.length > 0 && (
            <div className="form-group">
              <label>绑定探测规则（可选，使用规则编排引擎）</label>
              <select
                name="rule_id"
                value={formData.rule_id === null ? '' : formData.rule_id}
                onChange={handleChange}
              >
                <option value="">不使用规则（使用传统简单探测）</option>
                {rules.map(rule => (
                  <option key={rule.id} value={rule.id}>
                    {rule.name} (v{rule.current_version || 1})
                  </option>
                ))}
              </select>
              <span className="form-hint">
                {hasRule
                  ? `✅ 将使用规则编排引擎执行多步骤探测`
                  : '不绑定规则则使用传统的简单 HTTP/TCP 探测方式'}
              </span>
            </div>
          )}

          {!hasRule && (
            <>
              <div className="form-row">
                <div className="form-group">
                  <label>类型</label>
                  <select
                    name="type"
                    value={formData.type}
                    onChange={handleChange}
                  >
                    <option value="http">HTTP</option>
                    <option value="tcp">TCP</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>超时时间 (秒)</label>
                  <input
                    type="number"
                    name="timeout"
                    min="1"
                    max="60"
                    value={formData.timeout}
                    onChange={handleChange}
                  />
                </div>
              </div>

              <div className="form-group">
                <label>{formData.type === 'http' ? 'URL 地址' : '地址 (host:port)'}</label>
                <input
                  type="text"
                  name="address"
                  value={formData.address}
                  placeholder={formData.type === 'http' ? 'https://example.com' : 'example.com:80'}
                  required
                />
              </div>

              {formData.type === 'http' && (
                <div className="form-group">
                  <label>期望状态码</label>
                  <input
                    type="text"
                    name="expected_status"
                    value={formData.expected_status}
                    onChange={handleChange}
                    placeholder="200,201 或 200-399"
                  />
                </div>
              )}
            </>
          )}

          {hasRule && (
            <div className="form-row">
              <div className="form-group">
                <label>类型（规则探测时仅作为标识）</label>
                <select
                  name="type"
                  value={formData.type}
                  onChange={handleChange}
                >
                  <option value="http">HTTP</option>
                  <option value="tcp">TCP</option>
                </select>
              </div>
              <div className="form-group">
                <label>地址（规则探测时仅作为标识）</label>
                <input
                  type="text"
                  name="address"
                  value={formData.address}
                  onChange={handleChange}
                  placeholder="规则探测时填入任意地址作为描述"
                  required
                />
              </div>
            </div>
          )}

          <div className="form-group">
            <label>基准探测间隔 (秒)</label>
            <input
              type="range"
              name="interval"
              min="5"
              max="300"
              value={formData.interval}
              onChange={handleChange}
              style={{ width: '100%' }}
            />
            <div style={{ fontSize: '12px', color: '#64748b', textAlign: 'center' }}>
              {formData.interval} 秒
            </div>
          </div>

          <div className="form-group">
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                name="adaptive_enabled"
                checked={formData.adaptive_enabled}
                onChange={handleChange}
                style={{ width: 'auto' }}
              />
              启用自适应探测间隔
            </label>
            <span className="form-hint">健康时慢速探测节省资源，异常时快速探测确认故障</span>
          </div>

          {formData.adaptive_enabled && (
            <div className="form-row">
              <div className="form-group">
                <label>慢速间隔 (秒)</label>
                <input
                  type="number"
                  name="slow_interval"
                  min="5"
                  max="600"
                  value={formData.slow_interval}
                  onChange={handleChange}
                />
                <span className="form-hint">健康/故障确认后使用</span>
              </div>
              <div className="form-group">
                <label>快速间隔 (秒)</label>
                <input
                  type="number"
                  name="fast_interval"
                  min="1"
                  max="120"
                  value={formData.fast_interval}
                  onChange={handleChange}
                />
                <span className="form-hint">异常检测时使用</span>
              </div>
            </div>
          )}

          <div className="form-group">
            <label>静默时段</label>
            <div className="form-row">
              <div className="form-group" style={{ marginBottom: 0 }}>
                <input
                  type="time"
                  name="silent_start"
                  value={formData.silent_start}
                  onChange={handleChange}
                />
                <span className="form-hint">开始时间 (UTC)</span>
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <input
                  type="time"
                  name="silent_end"
                  value={formData.silent_end}
                  onChange={handleChange}
                />
                <span className="form-hint">结束时间 (UTC)</span>
              </div>
            </div>
            <span className="form-hint">静默时段内暂停探测且不产生告警</span>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              取消
            </button>
            <button type="submit" className="btn btn-primary">
              添加
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default AddTargetModal;
