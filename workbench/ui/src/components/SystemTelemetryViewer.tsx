import React from 'react';
import { SystemStats } from '../types';
import { Cpu, RefreshCw, Activity, ShieldCheck, HardDrive, Zap } from 'lucide-react';

interface SystemTelemetryViewerProps {
  system: SystemStats | null;
  onRefresh: () => void;
  loading: boolean;
}

export const SystemTelemetryViewer: React.FC<SystemTelemetryViewerProps> = ({
  system,
  onRefresh,
  loading,
}) => {
  if (!system) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
        Loading Go runtime telemetry...
      </div>
    );
  }

  return (
    <div>
      {/* Top Banner */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Cpu size={16} style={{ color: 'var(--accent-blue)' }} />
            <span>Go Runtime &amp; System Health Telemetry</span>
          </div>

          <button className="btn btn-default" onClick={onRefresh} disabled={loading}>
            <RefreshCw size={13} className={loading ? 'spin' : ''} />
            <span>Refresh Stats</span>
          </button>
        </div>

        <div className="card-body">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
            {/* Tile 1: Goroutines */}
            <div className="metric-tile" style={{ padding: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span className="metric-tile-label">Active Goroutines</span>
                <Activity size={16} style={{ color: 'var(--accent-mint)' }} />
              </div>
              <div className="metric-tile-val" style={{ fontSize: '26px', color: 'var(--accent-mint)' }}>
                {system.goroutines}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                Lightweight green threads active
              </div>
            </div>

            {/* Tile 2: Heap Memory Allocated */}
            <div className="metric-tile" style={{ padding: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span className="metric-tile-label">Heap Memory in Use</span>
                <HardDrive size={16} style={{ color: 'var(--accent-blue)' }} />
              </div>
              <div className="metric-tile-val" style={{ fontSize: '26px', color: 'var(--accent-blue)' }}>
                {system.mem_alloc_mb.toFixed(2)} <span style={{ fontSize: '15px' }}>MB</span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                Live active heap objects
              </div>
            </div>

            {/* Tile 3: OS Reserved Memory */}
            <div className="metric-tile" style={{ padding: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span className="metric-tile-label">Total OS Reserved</span>
                <Zap size={16} style={{ color: 'var(--accent-lavender)' }} />
              </div>
              <div className="metric-tile-val" style={{ fontSize: '26px', color: 'var(--accent-lavender)' }}>
                {system.mem_sys_mb.toFixed(2)} <span style={{ fontSize: '15px' }}>MB</span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                Memory mapped from Linux kernel
              </div>
            </div>

            {/* Tile 4: GC & CPUs */}
            <div className="metric-tile" style={{ padding: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span className="metric-tile-label">Garbage Collections</span>
                <ShieldCheck size={16} style={{ color: 'var(--accent-amber)' }} />
              </div>
              <div className="metric-tile-val" style={{ fontSize: '26px', color: 'var(--accent-amber)' }}>
                {system.num_gc} <span style={{ fontSize: '15px', color: 'var(--text-muted)' }}>runs</span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                Across {system.num_cpu} logical CPU cores
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Observability Details Card */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Activity size={16} style={{ color: 'var(--accent-mint)' }} />
            <span>Memory &amp; Concurrency Invariants</span>
          </div>
        </div>

        <div className="card-body">
          <table className="kv-table">
            <tbody>
              <tr>
                <td>Cumulative Memory Allocated:</td>
                <td><strong className="mono">{system.mem_total_mb.toFixed(2)} MB</strong></td>
              </tr>
              <tr>
                <td>Goroutine Concurrency Safety:</td>
                <td>
                  <span className="badge badge-mint">ACTIVE LEAK DETECTION</span>
                  <span style={{ marginLeft: '10px', color: 'var(--text-secondary)' }}>
                    Each turn execution monitors the exact delta between goroutine start and finish.
                  </span>
                </td>
              </tr>
              <tr>
                <td>Telemetry Sampling:</td>
                <td>Captured via Go's native standard library <code>runtime.ReadMemStats</code> and <code>runtime.NumGoroutine</code> with zero overhead.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
