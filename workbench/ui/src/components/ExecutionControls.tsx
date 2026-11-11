import React from 'react';
import { Play, Square, Clock } from 'lucide-react';

interface ExecutionControlsProps {
  isRunning: boolean;
  onExecute: () => void;
  onAbort: () => void;
  timeoutSeconds: number;
  setTimeoutSeconds: (sec: number) => void;
  disabled: boolean;
}

export const ExecutionControls: React.FC<ExecutionControlsProps> = ({
  isRunning,
  onExecute,
  onAbort,
  timeoutSeconds,
  setTimeoutSeconds,
  disabled,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '14px 18px',
        background: 'var(--bg-surface)',
        borderRadius: '8px',
        border: '1px solid var(--border-main)',
        flexWrap: 'wrap',
        gap: '12px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <button
          className="btn btn-primary"
          onClick={onExecute}
          disabled={isRunning || disabled}
          style={{ minWidth: '130px', padding: '10px 18px', fontSize: '13px' }}
        >
          <Play size={15} fill="currentColor" />
          <span>Run Module</span>
        </button>

        <button
          className="btn btn-danger"
          onClick={onAbort}
          disabled={!isRunning}
          style={{ minWidth: '120px', padding: '10px 16px', fontSize: '13px' }}
          title="Abort in-flight execution context to verify cancellation"
        >
          <Square size={14} fill="currentColor" />
          <span>Abort / Kill</span>
        </button>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Clock size={14} style={{ color: 'var(--text-muted)' }} />
        <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-muted)' }}>Timeout:</span>
        <select
          value={timeoutSeconds}
          onChange={(e) => setTimeoutSeconds(Number(e.target.value))}
          disabled={isRunning}
          style={{ width: 'auto', padding: '6px 10px', fontSize: '12px', background: 'var(--bg-surface-elevated)' }}
        >
          <option value={5}>5 seconds</option>
          <option value={15}>15 seconds</option>
          <option value={30}>30 seconds</option>
          <option value={60}>60 seconds</option>
          <option value={0}>Unlimited</option>
        </select>
      </div>
    </div>
  );
};
