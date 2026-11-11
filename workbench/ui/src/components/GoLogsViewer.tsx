import React, { useState, useMemo } from 'react';
import { GoLogEntry } from '../types';
import { Terminal, Search, ChevronDown, ChevronRight } from 'lucide-react';

interface GoLogsViewerProps {
  logs: GoLogEntry[];
}

export const GoLogsViewer: React.FC<GoLogsViewerProps> = ({ logs }) => {
  const [levelFilter, setLevelFilter] = useState<string>('ALL');
  const [search, setSearch] = useState<string>('');
  const [expandedIndices, setExpandedIndices] = useState<Record<number, boolean>>({});

  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      if (levelFilter !== 'ALL' && log.level !== levelFilter) return false;
      if (search) {
        const query = search.toLowerCase();
        const matchesMsg = log.message.toLowerCase().includes(query);
        const matchesSrc = log.source.toLowerCase().includes(query);
        const matchesTrace = log.trace_id?.toLowerCase().includes(query) ?? false;
        if (!matchesMsg && !matchesSrc && !matchesTrace) return false;
      }
      return true;
    });
  }, [logs, levelFilter, search]);

  const toggleExpand = (idx: number) => {
    setExpandedIndices((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const getLevelBadgeClass = (level: string) => {
    switch (level) {
      case 'ERROR':
        return 'badge-rose';
      case 'WARN':
        return 'badge-amber';
      case 'INFO':
        return 'badge-sky';
      case 'DEBUG':
        return 'badge-slate';
      default:
        return 'badge-slate';
    }
  };

  return (
    <div>
      {/* Top Banner & Filters */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Terminal size={16} style={{ color: 'var(--accent-lavender)' }} />
            <span>Go Subsystem &amp; Runtime Logs</span>
            <span className="badge badge-sky">{filteredLogs.length} Entries</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {['ALL', 'INFO', 'WARN', 'ERROR', 'DEBUG'].map((lvl) => (
              <button
                key={lvl}
                className={`pill-btn ${levelFilter === lvl ? 'active' : ''}`}
                style={{ padding: '3px 9px', fontSize: '11px' }}
                onClick={() => setLevelFilter(lvl)}
              >
                {lvl}
              </button>
            ))}
          </div>
        </div>

        <div className="card-body" style={{ padding: '14px 18px' }}>
          <div style={{ position: 'relative', width: '100%' }}>
            <Search size={14} style={{ position: 'absolute', left: '12px', top: '12px', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Search Go system logs by message, source package, or trace ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ paddingLeft: '34px' }}
            />
          </div>
        </div>
      </div>

      {/* Logs Feed (Natural Scrolling) */}
      {filteredLogs.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
          <Terminal size={32} style={{ margin: '0 auto 12px', opacity: 0.4 }} />
          <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-main)', marginBottom: '4px' }}>
            No Matching Go Logs Found
          </div>
          <div style={{ fontSize: '12px' }}>
            Internal logs from Gateway, Orchestrator, Store, and Supervisor stream here live.
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {filteredLogs.map((log, idx) => {
            const isExpanded = expandedIndices[idx];
            const hasFields = log.fields && Object.keys(log.fields).length > 0;

            return (
              <div key={idx} className="card" style={{ margin: 0, padding: '12px 16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className={`badge ${getLevelBadgeClass(log.level)}`}>{log.level}</span>
                    <span className="badge badge-slate" style={{ fontSize: '11px' }}>
                      {log.source}
                    </span>
                    {log.trace_id && (
                      <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }} title={log.trace_id}>
                        trace:{log.trace_id.slice(0, 8)}...
                      </span>
                    )}
                  </div>

                  <span className="mono" style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                    {new Date(log.timestamp).toLocaleTimeString()}.{new Date(log.timestamp).getMilliseconds().toString().padStart(3, '0')}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '10px' }}>
                  <div style={{ fontSize: '13px', color: 'var(--text-main)', flex: 1, lineHeight: '1.5' }}>
                    {log.message}
                  </div>

                  {hasFields && (
                    <button
                      className="btn btn-default"
                      style={{ padding: '2px 6px', fontSize: '10.5px' }}
                      onClick={() => toggleExpand(idx)}
                    >
                      {isExpanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                      <span>fields</span>
                    </button>
                  )}
                </div>

                {isExpanded && hasFields && (
                  <pre
                    style={{
                      marginTop: '8px',
                      padding: '10px',
                      background: 'var(--bg-app)',
                      border: '1px solid var(--border-main)',
                      borderRadius: '6px',
                      fontSize: '11px',
                      color: 'var(--text-secondary)',
                      overflowX: 'auto',
                    }}
                  >
                    {JSON.stringify(log.fields, null, 2)}
                  </pre>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
