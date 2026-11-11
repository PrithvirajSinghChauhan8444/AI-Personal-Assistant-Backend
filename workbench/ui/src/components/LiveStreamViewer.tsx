import React, { useEffect, useRef } from 'react';
import { StreamEvent } from '../types';
import { Activity } from 'lucide-react';

interface LiveStreamViewerProps {
  events: StreamEvent[];
  isRunning: boolean;
}

export const LiveStreamViewer: React.FC<LiveStreamViewerProps> = ({ events, isRunning }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isRunning) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [events, isRunning]);

  const getBadgeClass = (type: string) => {
    switch (type) {
      case 'TOKEN_CHUNK':
      case 'TURN_COMPLETE':
        return 'badge-mint';
      case 'THOUGHT_CHUNK':
        return 'badge-lavender';
      case 'STATUS_UPDATE':
      case 'GATEWAY_NORMALIZED':
        return 'badge-sky';
      case 'HITL_REQUEST':
      case 'POLICY_VERDICT':
        return 'badge-amber';
      case 'TURN_ERROR':
      case 'PANIC_STACK':
        return 'badge-rose';
      default:
        return 'badge-slate';
    }
  };

  const renderPayload = (payload: any) => {
    if (typeof payload === 'string') {
      return payload;
    }
    return JSON.stringify(payload, null, 2);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      <div className="section-label" style={{ padding: '8px 16px', background: 'var(--bg-card)', borderBottom: '1px solid var(--border-dim)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Activity size={13} style={{ color: 'var(--pastel-sky)' }} />
          <span>Live Event Stream ({events.length} events)</span>
        </div>
        {isRunning && <span className="badge badge-amber">Streaming...</span>}
      </div>

      <div className="stream-list">
        {events.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '40px 0', fontSize: '12px' }}>
            Awaiting module execution. Events will stream here in real time.
          </div>
        ) : (
          events.map((ev, idx) => (
            <div key={idx} className="stream-card">
              <div className="stream-card-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span className={`badge ${getBadgeClass(ev.type)}`}>{ev.type}</span>
                  {ev.agent_name && (
                    <span className="badge badge-slate" style={{ fontSize: '10px' }}>
                      @{ev.agent_name}
                    </span>
                  )}
                </div>
                <span className="mono" style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                  #{ev.index || idx + 1} • {new Date(ev.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <div className="stream-card-body">{renderPayload(ev.payload)}</div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};
