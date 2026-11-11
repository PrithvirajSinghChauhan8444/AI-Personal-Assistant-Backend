import React from 'react';
import { ExecutionRecord } from '../types';
import { X, Clock, ArrowRight } from 'lucide-react';

interface FlightHistoryDrawerProps {
  open: boolean;
  onClose: () => void;
  history: ExecutionRecord[];
  onSelectRecord: (rec: ExecutionRecord) => void;
  onReplayInput: (rec: ExecutionRecord) => void;
}

export const FlightHistoryDrawer: React.FC<FlightHistoryDrawerProps> = ({
  open,
  onClose,
  history,
  onSelectRecord,
  onReplayInput,
}) => {
  if (!open) return null;

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
        <div
          style={{
            padding: '14px 16px',
            borderBottom: '1px solid var(--border-dim)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Clock size={16} style={{ color: 'var(--pastel-sky)' }} />
            <span style={{ fontWeight: 600, fontSize: '13px' }}>Disk Flight Recorder Logs</span>
            <span className="badge badge-slate">{history.length}</span>
          </div>
          <button className="btn btn-default" style={{ padding: '4px' }} onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
          {history.length === 0 ? (
            <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '40px 0' }}>
              No execution history recorded yet.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {history.map((rec) => {
                let badgeClass = 'badge-slate';
                if (rec.status === 'SUCCESS') badgeClass = 'badge-mint';
                else if (rec.status === 'ERROR' || rec.status === 'PANIC') badgeClass = 'badge-rose';
                else if (rec.status === 'ABORTED') badgeClass = 'badge-amber';

                return (
                  <div
                    key={rec.id}
                    className="stream-card"
                    style={{ cursor: 'pointer', transition: 'border-color 0.1s' }}
                    onClick={() => onSelectRecord(rec)}
                  >
                    <div className="stream-card-header">
                      <span className={`badge ${badgeClass}`}>{rec.status}</span>
                      <span className="mono" style={{ fontSize: '11px', color: 'var(--pastel-sky)' }}>
                        {rec.duration_formatted}
                      </span>
                    </div>

                    <div style={{ fontWeight: 500, fontSize: '12px', marginTop: '4px', color: 'var(--text-main)' }}>
                      {rec.module_name}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '8px' }}>
                      <span style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                        {new Date(rec.started_at).toLocaleString()}
                      </span>

                      <button
                        className="btn btn-default"
                        style={{ padding: '2px 8px', fontSize: '11px' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          onReplayInput(rec);
                        }}
                        title="Load this input payload into the editor"
                      >
                        <span>Replay</span>
                        <ArrowRight size={11} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
