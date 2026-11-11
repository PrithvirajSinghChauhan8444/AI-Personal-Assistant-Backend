import React, { useState, useMemo } from 'react';
import { ExecutionRecord } from '../types';
import { History, Search, ArrowRight, CheckCircle2, AlertOctagon, Clock, Layers } from 'lucide-react';

interface FlightRecorderViewProps {
  history: ExecutionRecord[];
  onReplay: (rec: ExecutionRecord) => void;
  onInspect: (rec: ExecutionRecord) => void;
}

export const FlightRecorderView: React.FC<FlightRecorderViewProps> = ({
  history,
  onReplay,
  onInspect,
}) => {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  const filtered = useMemo(() => {
    return history.filter((rec) => {
      if (statusFilter !== 'ALL' && rec.status !== statusFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        const matchesModule = rec.module_name?.toLowerCase().includes(q) || false;
        const matchesId = rec.id?.toLowerCase().includes(q) || false;
        const inputStr = JSON.stringify(rec.input || '').toLowerCase();
        const matchesInput = inputStr.includes(q);
        if (!matchesModule && !matchesId && !matchesInput) return false;
      }
      return true;
    });
  }, [history, statusFilter, search]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return <span className="badge badge-mint"><CheckCircle2 size={11} /> SUCCESS</span>;
      case 'ERROR':
        return <span className="badge badge-rose"><AlertOctagon size={11} /> ERROR</span>;
      case 'PANIC':
        return <span className="badge badge-rose"><AlertOctagon size={11} /> PANIC</span>;
      case 'ABORTED':
        return <span className="badge badge-amber"><Clock size={11} /> ABORTED</span>;
      default:
        return <span className="badge badge-slate">{status}</span>;
    }
  };

  return (
    <div>
      {/* Banner & Controls */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <History size={16} style={{ color: 'var(--accent-blue)' }} />
            <span>Disk Flight Recorder Archive</span>
            <span className="badge badge-sky">{filtered.length} Recorded Runs</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {['ALL', 'SUCCESS', 'ERROR', 'ABORTED'].map((st) => (
              <button
                key={st}
                className={`pill-btn ${statusFilter === st ? 'active' : ''}`}
                style={{ padding: '4px 10px', fontSize: '11.5px' }}
                onClick={() => setStatusFilter(st)}
              >
                {st}
              </button>
            ))}
          </div>
        </div>

        <div className="card-body" style={{ padding: '14px 18px' }}>
          <div style={{ position: 'relative', width: '100%' }}>
            <Search size={14} style={{ position: 'absolute', left: '12px', top: '12px', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Search past flight runs by prompt, module, or execution ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ paddingLeft: '34px' }}
            />
          </div>
        </div>
      </div>

      {/* Runs List (Natural Scroll) */}
      {filtered.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
          <History size={32} style={{ margin: '0 auto 12px', opacity: 0.4 }} />
          <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-main)', marginBottom: '4px' }}>
            No Matching Flight Records Found
          </div>
          <div style={{ fontSize: '12px' }}>
            Execute any module in the Workbench to capture live unadulterated runs.
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {filtered.map((rec) => {
            const promptPreview = rec.input?.prompt || (typeof rec.input === 'string' ? rec.input : '');

            return (
              <div key={rec.id} className="card" style={{ margin: 0, padding: '16px 20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    {getStatusBadge(rec.status)}
                    <span style={{ fontWeight: 700, fontSize: '14px', color: 'var(--text-main)' }}>
                      {rec.module_name}
                    </span>
                    <span className="badge badge-slate" style={{ fontSize: '11px' }}>
                      {rec.category}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span className="mono" style={{ fontSize: '13px', fontWeight: 600, color: 'var(--accent-blue)' }}>
                      {rec.duration_formatted}
                    </span>
                    <span className="mono" style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                      {new Date(rec.started_at).toLocaleString()}
                    </span>
                  </div>
                </div>

                {promptPreview && (
                  <div
                    style={{
                      backgroundColor: 'var(--bg-app)',
                      border: '1px solid var(--border-main)',
                      borderRadius: '6px',
                      padding: '8px 12px',
                      fontSize: '12.5px',
                      color: 'var(--text-secondary)',
                      marginBottom: '12px',
                      fontStyle: 'italic',
                    }}
                  >
                    "{promptPreview}"
                  </div>
                )}

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-muted)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <span className="mono">id: {rec.id.slice(0, 8)}...</span>
                    <span>Events: <strong>{rec.events?.length || 0}</strong></span>
                    {rec.telemetry && (
                      <span>
                        Mem Δ: <strong>{(rec.telemetry.mem_delta_bytes / 1024).toFixed(1)} KB</strong>
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      className="btn btn-default"
                      style={{ padding: '4px 10px', fontSize: '11.5px' }}
                      onClick={() => onInspect(rec)}
                    >
                      <Layers size={12} />
                      <span>Inspect Output</span>
                    </button>

                    <button
                      className="btn btn-primary"
                      style={{ padding: '4px 12px', fontSize: '11.5px' }}
                      onClick={() => onReplay(rec)}
                    >
                      <span>Replay in Runner</span>
                      <ArrowRight size={12} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
