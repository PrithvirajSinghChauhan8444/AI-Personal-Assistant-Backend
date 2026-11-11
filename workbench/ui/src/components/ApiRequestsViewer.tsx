import React, { useState } from 'react';
import { APIRequestLog } from '../types';
import { Network, Copy, Check, ChevronDown, ChevronRight, Search } from 'lucide-react';

interface ApiRequestsViewerProps {
  requests: APIRequestLog[];
}

export const ApiRequestsViewer: React.FC<ApiRequestsViewerProps> = ({ requests }) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [search, setSearch] = useState<string>('');

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const filtered = requests.filter((r) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      r.path.toLowerCase().includes(q) ||
      r.method.toLowerCase().includes(q) ||
      r.trace_id.toLowerCase().includes(q) ||
      (r.request_body && r.request_body.toLowerCase().includes(q))
    );
  });

  const getStatusBadge = (status: number) => {
    if (status >= 200 && status < 300) return <span className="badge badge-mint">{status} OK</span>;
    if (status >= 400 && status < 500) return <span className="badge badge-amber">{status}</span>;
    return <span className="badge badge-rose">{status} ERR</span>;
  };

  const getMethodBadge = (method: string) => {
    switch (method) {
      case 'POST':
        return <span className="badge badge-sky">{method}</span>;
      case 'GET':
        return <span className="badge badge-mint">{method}</span>;
      default:
        return <span className="badge badge-slate">{method}</span>;
    }
  };

  return (
    <div>
      {/* Top Banner & Search */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Network size={16} style={{ color: 'var(--accent-blue)' }} />
            <span>HTTP API Network Telemetry</span>
            <span className="badge badge-sky">{filtered.length} Requests</span>
          </div>
          <span style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
            Captured automatically via Telemetry Middleware
          </span>
        </div>

        <div className="card-body" style={{ padding: '14px 18px' }}>
          <div style={{ position: 'relative', width: '100%' }}>
            <Search size={14} style={{ position: 'absolute', left: '12px', top: '12px', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Search API calls by route (/api/execute), method, or trace ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ paddingLeft: '34px' }}
            />
          </div>
        </div>
      </div>

      {/* Requests List (Natural Scrolling) */}
      {filtered.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
          <Network size={32} style={{ margin: '0 auto 12px', opacity: 0.4 }} />
          <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-main)', marginBottom: '4px' }}>
            No HTTP API Requests Captured Yet
          </div>
          <div style={{ fontSize: '12px' }}>
            API calls will appear here in real time as actions are executed in the Workbench.
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {filtered.map((req) => {
            const isExpanded = expandedId === req.id;

            return (
              <div key={req.id} className="card" style={{ margin: 0, padding: '14px 18px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {getMethodBadge(req.method)}
                    <span className="mono" style={{ fontWeight: 700, fontSize: '13.5px', color: 'var(--text-main)' }}>
                      {req.path}
                    </span>
                    {getStatusBadge(req.status)}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span className="mono" style={{ fontSize: '12.5px', fontWeight: 600, color: 'var(--accent-blue)' }}>
                      {req.duration_formatted}
                    </span>
                    <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      {new Date(req.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-muted)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    <span>In: <strong>{req.bytes_received}B</strong></span>
                    <span>Out: <strong>{req.bytes_sent}B</strong></span>
                    {req.trace_id && (
                      <span className="mono" title={req.trace_id}>
                        trace:{req.trace_id.slice(0, 8)}...
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: '6px' }}>
                    {req.trace_id && (
                      <button
                        className="btn btn-default"
                        style={{ padding: '3px 8px', fontSize: '11px' }}
                        onClick={() => handleCopy(`trace-${req.id}`, req.trace_id)}
                      >
                        {copiedId === `trace-${req.id}` ? <Check size={11} color="var(--accent-mint)" /> : <Copy size={11} />}
                        <span>Trace</span>
                      </button>
                    )}

                    {req.request_body && (
                      <button
                        className="btn btn-default"
                        style={{ padding: '3px 8px', fontSize: '11px' }}
                        onClick={() => setExpandedId(isExpanded ? null : req.id)}
                      >
                        {isExpanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                        <span>Payload</span>
                      </button>
                    )}
                  </div>
                </div>

                {isExpanded && req.request_body && (
                  <div style={{ marginTop: '10px' }}>
                    <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>
                      Request Payload (JSON):
                    </div>
                    <pre
                      style={{
                        background: '#0f172a',
                        color: '#f8fafc',
                        padding: '12px',
                        borderRadius: '6px',
                        fontSize: '11.5px',
                        overflowX: 'auto',
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {req.request_body}
                    </pre>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
