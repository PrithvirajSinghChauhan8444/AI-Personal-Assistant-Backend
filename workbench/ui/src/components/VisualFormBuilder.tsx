import React from 'react';
import { Module } from '../types';
import { RefreshCw, User, Bot, Terminal, Globe, Send, Cpu } from 'lucide-react';

interface VisualFormBuilderProps {
  module: Module;
  values: Record<string, any>;
  onChange: (newValues: Record<string, any>) => void;
}

export const VisualFormBuilder: React.FC<VisualFormBuilderProps> = ({
  module,
  values,
  onChange,
}) => {
  const updateField = (field: string, val: any) => {
    onChange({ ...values, [field]: val });
  };

  const generateUUID = () => {
    const uuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
    updateField('session_id', uuid);
  };

  // Turn Request Form (Gateway, Orchestrator, Pipeline E2E)
  const isTurnRequest =
    module.id.includes('gateway') ||
    module.id.includes('orchestrator') ||
    module.id.includes('pipeline');

  // Gatekeeper Form
  const isGatekeeper = module.id.includes('gatekeeper');

  // Session Store Form
  const isSessionStore = module.id.includes('session_store');

  if (isTurnRequest) {
    const currentChannel = values.channel || 'CLI';
    const currentTrigger = values.trigger || 'INTERACTIVE';
    const currentAgent = values.target_agent || 'auto';

    return (
      <div style={{ padding: '16px', overflowY: 'auto', flex: 1 }}>
        {/* Prompt Input */}
        <div className="form-group">
          <div className="form-group-label">
            <span>User Prompt</span>
            <span style={{ fontSize: '10px', color: 'var(--text-dim)' }}>
              {values.prompt?.length || 0} characters
            </span>
          </div>
          <textarea
            rows={3}
            placeholder="Enter the command or prompt (e.g. '@browser search Go 1.24 release notes' or 'Delete system files')..."
            value={values.prompt || ''}
            onChange={(e) => updateField('prompt', e.target.value)}
            style={{ fontSize: '13px', lineHeight: '1.5' }}
          />
        </div>

        {/* Channel Selector */}
        <div className="form-group">
          <div className="form-group-label">Ingress Channel</div>
          <div className="pill-group">
            {[
              { id: 'CLI', label: 'CLI Terminal', icon: Terminal },
              { id: 'WEB', label: 'Web Browser', icon: Globe },
              { id: 'TELEGRAM', label: 'Telegram Bot', icon: Send },
              { id: 'INTERNAL', label: 'Internal Daemon', icon: Cpu },
            ].map((c) => {
              const Icon = c.icon;
              return (
                <button
                  key={c.id}
                  type="button"
                  className={`pill-btn ${currentChannel === c.id ? 'active' : ''}`}
                  onClick={() => updateField('channel', c.id)}
                >
                  <Icon size={12} />
                  <span>{c.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Trigger Mode */}
        <div className="form-group">
          <div className="form-group-label">Trigger Mode</div>
          <div className="pill-group">
            <button
              type="button"
              className={`pill-btn ${currentTrigger === 'INTERACTIVE' ? 'active' : ''}`}
              onClick={() => updateField('trigger', 'INTERACTIVE')}
            >
              <User size={12} />
              <span>Interactive (Human Present)</span>
            </button>
            <button
              type="button"
              className={`pill-btn ${currentTrigger === 'AUTONOMOUS' ? 'active' : ''}`}
              onClick={() => updateField('trigger', 'AUTONOMOUS')}
            >
              <Bot size={12} />
              <span>Autonomous (Background)</span>
            </button>
          </div>
          <div className="form-hint">
            In autonomous mode, high-risk tools and interactive HITL prompts are blocked.
          </div>
        </div>

        {/* Target Agent & User ID */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div className="form-group">
            <div className="form-group-label">Target Agent</div>
            <select
              value={currentAgent}
              onChange={(e) => updateField('target_agent', e.target.value)}
            >
              <option value="auto">Auto (Manager Planner)</option>
              <option value="system">System Agent (@system)</option>
              <option value="browser">Browser Agent (@browser)</option>
              <option value="research">Research Agent (@research)</option>
            </select>
          </div>

          <div className="form-group">
            <div className="form-group-label">User Identity</div>
            <input
              type="text"
              value={values.user_id || 'local:prit'}
              onChange={(e) => updateField('user_id', e.target.value)}
              placeholder="e.g. local:prit"
            />
          </div>
        </div>

        {/* Session ID */}
        <div className="form-group">
          <div className="form-group-label">
            <span>Session ID (UUID)</span>
            <button
              type="button"
              className="btn btn-default"
              style={{ padding: '2px 6px', fontSize: '10px' }}
              onClick={generateUUID}
            >
              <RefreshCw size={10} />
              <span>Generate UUID</span>
            </button>
          </div>
          <input
            type="text"
            className="mono"
            value={values.session_id || ''}
            onChange={(e) => updateField('session_id', e.target.value)}
            placeholder="Leave empty or enter session UUID..."
          />
        </div>

        {/* Allowed Capabilities */}
        <div className="form-group">
          <div className="form-group-label">
            <span>Allowed Capabilities (Comma-Separated)</span>
          </div>
          <input
            type="text"
            className="mono"
            placeholder="e.g. fs_read, system_exec, git_ops"
            value={Array.isArray(values.allowed_capabilities) ? values.allowed_capabilities.join(', ') : ''}
            onChange={(e) => {
              const raw = e.target.value;
              const list = raw
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean);
              updateField('allowed_capabilities', list);
            }}
          />
        </div>
      </div>
    );
  }

  if (isGatekeeper) {
    return (
      <div style={{ padding: '16px', overflowY: 'auto', flex: 1 }}>
        <div className="form-group">
          <div className="form-group-label">Tool Name to Evaluate</div>
          <input
            type="text"
            className="mono"
            placeholder="e.g. sys_exec, fs_read, fs_delete, git_commit"
            value={values.tool_name || ''}
            onChange={(e) => updateField('tool_name', e.target.value)}
          />
        </div>

        <div className="form-group">
          <div className="form-group-label">Trigger Mode</div>
          <div className="pill-group">
            {['INTERACTIVE', 'AUTONOMOUS'].map((t) => (
              <button
                key={t}
                type="button"
                className={`pill-btn ${values.trigger === t ? 'active' : ''}`}
                onClick={() => updateField('trigger', t)}
              >
                {t === 'INTERACTIVE' ? <User size={12} /> : <Bot size={12} />}
                <span>{t}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="form-group">
          <div className="form-group-label">Granted Capabilities</div>
          <input
            type="text"
            className="mono"
            placeholder="e.g. system_exec, fs_read"
            value={Array.isArray(values.allowed_capabilities) ? values.allowed_capabilities.join(', ') : ''}
            onChange={(e) => {
              const list = e.target.value
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean);
              updateField('allowed_capabilities', list);
            }}
          />
        </div>
      </div>
    );
  }

  if (isSessionStore) {
    return (
      <div style={{ padding: '16px', overflowY: 'auto', flex: 1 }}>
        <div className="form-group">
          <div className="form-group-label">Session ID</div>
          <input
            type="text"
            className="mono"
            value={values.session_id || ''}
            onChange={(e) => updateField('session_id', e.target.value)}
          />
        </div>

        {values.role !== undefined && (
          <div className="form-group">
            <div className="form-group-label">Message Role</div>
            <select
              value={values.role || 'user'}
              onChange={(e) => updateField('role', e.target.value)}
            >
              <option value="user">User</option>
              <option value="assistant">Assistant</option>
              <option value="system">System</option>
              <option value="tool">Tool</option>
            </select>
          </div>
        )}

        {values.content !== undefined && (
          <div className="form-group">
            <div className="form-group-label">Message Content</div>
            <textarea
              rows={3}
              value={values.content || ''}
              onChange={(e) => updateField('content', e.target.value)}
            />
          </div>
        )}

        {values.limit !== undefined && (
          <div className="form-group">
            <div className="form-group-label">History Limit</div>
            <input
              type="number"
              value={values.limit || 10}
              onChange={(e) => updateField('limit', Number(e.target.value))}
            />
          </div>
        )}
      </div>
    );
  }

  // Generic dynamic form from introspected fields
  return (
    <div style={{ padding: '16px', overflowY: 'auto', flex: 1 }}>
      {module.schema?.fields?.map((f) => (
        <div key={f.name} className="form-group">
          <div className="form-group-label">
            <span>{f.name}</span>
            <span style={{ fontSize: '10px', color: 'var(--text-dim)' }}>{f.type}</span>
          </div>
          <input
            type="text"
            value={values[f.name] !== undefined ? String(values[f.name]) : ''}
            onChange={(e) => updateField(f.name, e.target.value)}
            placeholder={f.description || f.name}
          />
        </div>
      ))}
    </div>
  );
};
