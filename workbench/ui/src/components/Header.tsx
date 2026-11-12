import React from 'react';
import { Layers, Rocket, History, Cpu, Network, Terminal, Circle, FileCode2 } from 'lucide-react';

export type WorkbenchMode = 'runner' | 'ast' | 'history' | 'telemetry' | 'apireqs' | 'gologs';

interface HeaderProps {
  currentMode: WorkbenchMode;
  onSelectMode: (mode: WorkbenchMode) => void;
  isRunning: boolean;
  historyCount: number;
  apiCount: number;
  logCount: number;
  astMethodCount?: number;
}

export const Header: React.FC<HeaderProps> = ({
  currentMode,
  onSelectMode,
  isRunning,
  historyCount,
  apiCount,
  logCount,
  astMethodCount = 0,
}) => {
  return (
    <header className="app-header">
      {/* Brand & Logo */}
      <div className="header-brand">
        <div className="header-logo-icon">
          <Layers size={18} />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="header-title">Module Workbench</span>
            <span className="header-badge">v1.3 AST Autodiscovery</span>
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Visual Testbed &amp; Telemetry Flight Recorder
          </div>
        </div>
      </div>

      {/* Mode Navigation Tabs */}
      <nav className="nav-tabs">
        <button
          className={`nav-tab-btn ${currentMode === 'runner' ? 'active' : ''}`}
          onClick={() => onSelectMode('runner')}
        >
          <Rocket size={14} />
          <span>Runner &amp; Workbench</span>
        </button>

        <button
          className={`nav-tab-btn ${currentMode === 'ast' ? 'active' : ''}`}
          onClick={() => onSelectMode('ast')}
        >
          <FileCode2 size={14} />
          <span>AST Codebase Scanner</span>
          {astMethodCount > 0 && <span className="tab-badge" style={{ background: 'var(--accent-purple-bg)', color: 'var(--accent-purple)', borderColor: 'var(--accent-purple-border)' }}>{astMethodCount}</span>}
        </button>

        <button
          className={`nav-tab-btn ${currentMode === 'history' ? 'active' : ''}`}
          onClick={() => onSelectMode('history')}
        >
          <History size={14} />
          <span>Flight Recorder</span>
          <span className="tab-badge">{historyCount}</span>
        </button>

        <button
          className={`nav-tab-btn ${currentMode === 'telemetry' ? 'active' : ''}`}
          onClick={() => onSelectMode('telemetry')}
        >
          <Cpu size={14} />
          <span>System Telemetry</span>
        </button>

        <button
          className={`nav-tab-btn ${currentMode === 'apireqs' ? 'active' : ''}`}
          onClick={() => onSelectMode('apireqs')}
        >
          <Network size={14} />
          <span>API Network</span>
          <span className="tab-badge">{apiCount}</span>
        </button>

        <button
          className={`nav-tab-btn ${currentMode === 'gologs' ? 'active' : ''}`}
          onClick={() => onSelectMode('gologs')}
        >
          <Terminal size={14} />
          <span>Go Logs</span>
          <span className="tab-badge">{logCount}</span>
        </button>
      </nav>

      {/* Runtime Status Pill */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '11.5px',
            fontWeight: 600,
            padding: '5px 12px',
            borderRadius: '20px',
            backgroundColor: isRunning ? 'var(--accent-amber-bg)' : 'var(--accent-mint-bg)',
            color: isRunning ? 'var(--accent-amber)' : 'var(--accent-mint)',
            border: `1px solid ${isRunning ? 'var(--accent-amber-border)' : 'var(--accent-mint-border)'}`,
          }}
        >
          <Circle
            size={8}
            fill={isRunning ? 'var(--accent-amber)' : 'var(--accent-mint)'}
            color={isRunning ? 'var(--accent-amber)' : 'var(--accent-mint)'}
          />
          <span>{isRunning ? 'Processing Turn...' : 'Backend Ready'}</span>
        </div>
      </div>
    </header>
  );
};
