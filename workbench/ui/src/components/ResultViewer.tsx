import React, { useState } from 'react';
import { ExecutionRecord } from '../types';
import { CheckCircle2, AlertOctagon, Copy, Check, Clock } from 'lucide-react';

interface ResultViewerProps {
  record: ExecutionRecord | null;
}

export const ResultViewer: React.FC<ResultViewerProps> = ({ record }) => {
  const [tab, setTab] = useState<'visual' | 'raw' | 'telemetry' | 'panic'>('visual');
  const [copied, setCopied] = useState(false);

  if (!record) return null;

  const handleCopyRaw = () => {
    navigator.clipboard.writeText(JSON.stringify(record, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return <span className="badge badge-mint"><CheckCircle2 size={12} /> SUCCESS</span>;
      case 'ERROR':
        return <span className="badge badge-rose"><AlertOctagon size={12} /> ERROR</span>;
      case 'PANIC':
        return <span className="badge badge-rose"><AlertOctagon size={12} /> PANIC RECOVERED</span>;
      case 'ABORTED':
        return <span className="badge badge-amber"><Clock size={12} /> ABORTED BY USER</span>;
      default:
        return <span className="badge badge-slate">{status}</span>;
    }
  };

  const normalized = record.output?.normalized_request;

  return (
    <div className="card" style={{ marginTop: '16px', overflow: 'hidden' }}>
      {/* Header Bar */}
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {getStatusBadge(record.status)}
          <span className="mono" style={{ fontSize: '13px', fontWeight: 700, color: 'var(--accent-blue)' }}>
            {record.duration_formatted}
          </span>
          <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            exec: {record.id.slice(0, 8)}...
          </span>
        </div>

        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            className={`btn btn-default ${tab === 'visual' ? 'active' : ''}`}
            style={{ padding: '4px 10px', fontSize: '11.5px', background: tab === 'visual' ? 'var(--accent-blue-bg)' : undefined, color: tab === 'visual' ? 'var(--accent-blue)' : undefined }}
            onClick={() => setTab('visual')}
          >
            Visual Summary
          </button>
          <button
            className={`btn btn-default ${tab === 'telemetry' ? 'active' : ''}`}
            style={{ padding: '4px 10px', fontSize: '11.5px', background: tab === 'telemetry' ? 'var(--accent-blue-bg)' : undefined, color: tab === 'telemetry' ? 'var(--accent-blue)' : undefined }}
            onClick={() => setTab('telemetry')}
          >
            Telemetry Stats
          </button>
          <button
            className={`btn btn-default ${tab === 'raw' ? 'active' : ''}`}
            style={{ padding: '4px 10px', fontSize: '11.5px', background: tab === 'raw' ? 'var(--accent-blue-bg)' : undefined, color: tab === 'raw' ? 'var(--accent-blue)' : undefined }}
            onClick={() => setTab('raw')}
          >
            Raw JSON
          </button>
          {record.panic && (
            <button
              className="btn btn-danger"
              style={{ padding: '4px 10px', fontSize: '11.5px' }}
              onClick={() => setTab('panic')}
            >
              Panic Stack
            </button>
          )}
          <button
            className="btn btn-default"
            style={{ padding: '4px 10px', fontSize: '11.5px' }}
            onClick={handleCopyRaw}
            title="Copy unedited record"
          >
            {copied ? <Check size={12} color="var(--accent-mint)" /> : <Copy size={12} />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>
      </div>

      {/* Content View */}
      <div className="card-body">
        {record.aborted && (
          <div style={{ marginBottom: '12px', padding: '10px 14px', background: 'var(--accent-amber-bg)', color: '#92400e', borderRadius: '8px', fontSize: '13px', border: '1px solid var(--accent-amber-border)' }}>
            <strong>Context Cancelled:</strong> Execution was interrupted via user Abort signal or timeout.
          </div>
        )}

        {record.error && !record.panic && (
          <div style={{ marginBottom: '12px', padding: '10px 14px', background: 'var(--accent-coral-bg)', color: '#9f1239', borderRadius: '8px', fontSize: '13px', border: '1px solid var(--accent-coral-border)' }}>
            <strong>Execution Error:</strong> {record.error}
          </div>
        )}

        {tab === 'panic' && record.panic ? (
          <pre style={{ color: 'var(--accent-coral)', fontSize: '12px', whiteSpace: 'pre-wrap', background: '#0f172a', padding: '14px', borderRadius: '8px' }}>
            {record.panic}
          </pre>
        ) : tab === 'raw' ? (
          <pre style={{ fontSize: '12px', color: '#f8fafc', background: '#0f172a', padding: '14px', borderRadius: '8px', whiteSpace: 'pre-wrap', overflowX: 'auto' }}>
            {JSON.stringify(record, null, 2)}
          </pre>
        ) : tab === 'telemetry' ? (
          <div>
            {record.telemetry ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', fontSize: '12px' }}>
                <div className="metric-tile">
                  <div className="metric-tile-label">Trace ID</div>
                  <div className="mono" style={{ color: 'var(--accent-blue)', fontSize: '11.5px' }}>
                    {record.telemetry.trace_id}
                  </div>
                </div>

                <div className="metric-tile">
                  <div className="metric-tile-label">Goroutine Safety</div>
                  <div className="mono" style={{ fontSize: '13px' }}>
                    Start: <strong>{record.telemetry.goroutines_start}</strong> → End: <strong>{record.telemetry.goroutines_end}</strong>{' '}
                    <span style={{ color: record.telemetry.goroutine_delta === 0 ? 'var(--accent-mint)' : 'var(--accent-amber)' }}>
                      (Δ {record.telemetry.goroutine_delta > 0 ? `+${record.telemetry.goroutine_delta}` : record.telemetry.goroutine_delta})
                    </span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    {record.telemetry.goroutine_delta === 0 ? '✓ Zero Goroutine Leaks' : 'Goroutine count shifted'}
                  </div>
                </div>

                <div className="metric-tile">
                  <div className="metric-tile-label">Memory Delta</div>
                  <div className="mono" style={{ fontSize: '13px' }}>
                    {(record.telemetry.mem_delta_bytes / 1024).toFixed(2)} KB
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    Heap Alloc: {(record.telemetry.mem_alloc_end_bytes / (1024 * 1024)).toFixed(2)} MB
                  </div>
                </div>

                <div className="metric-tile">
                  <div className="metric-tile-label">Execution Duration</div>
                  <div className="mono" style={{ fontSize: '13px', color: 'var(--accent-blue)' }}>
                    {record.duration_formatted} ({record.duration_us} µs)
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    Exact latency
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                No telemetry recorded for this execution.
              </div>
            )}
          </div>
        ) : (
          /* Visual Summary Tab */
          <div>
            {normalized ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <span className="badge badge-sky">Target: @{normalized.target_agent || 'auto'}</span>
                  <span className="badge badge-slate">Channel: {normalized.channel}</span>
                  <span className="badge badge-slate">Trigger: {normalized.trigger}</span>
                  <span className="badge badge-mint">Status: {record.status}</span>
                </div>

                <table className="kv-table" style={{ background: 'var(--bg-app)', borderRadius: '8px', overflow: 'hidden' }}>
                  <tbody>
                    <tr>
                      <td>Session UUID:</td>
                      <td className="mono">{normalized.session_id || 'Generated In-Flight'}</td>
                    </tr>
                    <tr>
                      <td>Trace ID:</td>
                      <td className="mono" style={{ color: 'var(--accent-blue)' }}>{normalized.trace_id || record.id}</td>
                    </tr>
                    <tr>
                      <td>Prompt:</td>
                      <td style={{ fontWeight: 600, color: 'var(--text-main)' }}>"{normalized.prompt}"</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : record.output ? (
              <div>
                <pre style={{ fontSize: '12px', color: '#f8fafc', background: '#0f172a', padding: '14px', borderRadius: '8px', whiteSpace: 'pre-wrap' }}>
                  {JSON.stringify(record.output, null, 2)}
                </pre>
              </div>
            ) : (
              <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                {record.error ? 'No return struct due to error.' : 'Execution finished.'}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
