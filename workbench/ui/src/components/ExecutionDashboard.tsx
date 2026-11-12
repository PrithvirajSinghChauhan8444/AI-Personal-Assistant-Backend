import React, { useState, useMemo } from 'react';
import { StreamEvent, ExecutionRecord } from '../types';
import {
  Brain,
  ShieldCheck,
  Zap,
  Terminal,
  Activity,
  ChevronDown,
  ChevronRight,
  Clock,
  Copy,
  Check,
  Wrench,
  Bot,
  AlertTriangle,
} from 'lucide-react';

interface ExecutionDashboardProps {
  events: StreamEvent[];
  record: ExecutionRecord | null;
  isRunning: boolean;
}

export const ExecutionDashboard: React.FC<ExecutionDashboardProps> = ({
  events,
  record,
  isRunning,
}) => {
  const [showRaw, setShowRaw] = useState<Record<string, boolean>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const toggleRaw = (stepId: string) => {
    setShowRaw((prev) => ({ ...prev, [stepId]: !prev[stepId] }));
  };

  const copyToClipboard = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  // 1. Ingestion / Normalization Step
  const normalizationEvent = useMemo(() => {
    return (
      events.find((e) => e.type === 'GATEWAY_NORMALIZED') ||
      (record?.output?.normalized_request
        ? { payload: record.output.normalized_request }
        : null)
    );
  }, [events, record]);

  // 2. Safety / Gatekeeper Step
  const safetyEvent = useMemo(() => {
    return (
      events.find((e) => e.type === 'POLICY_VERDICT') ||
      (record?.module_id?.includes('gatekeeper') && record?.output
        ? { payload: record.output }
        : null)
    );
  }, [events, record]);

  // 3. Status Updates
  const statusUpdates = useMemo(() => {
    return events.filter((e) => e.type === 'STATUS_UPDATE');
  }, [events]);

  // 4. Reasoning / Thoughts (aggregated)
  const thoughts = useMemo(() => {
    return events
      .filter((e) => e.type === 'THOUGHT_CHUNK' || e.type === 'AGENT_THOUGHT')
      .map((e) => (typeof e.payload === 'string' ? e.payload : JSON.stringify(e.payload)))
      .join(' ');
  }, [events]);

  // 5. Tokens / Output (aggregated stream)
  const streamedTokens = useMemo(() => {
    return events
      .filter((e) => e.type === 'TOKEN_CHUNK' || e.type === 'AGENT_TOKEN')
      .map((e) => (typeof e.payload === 'string' ? e.payload : JSON.stringify(e.payload)))
      .join('\n');
  }, [events]);

  // 6. Layer 3 Tool Events
  const toolStarted = useMemo(() => events.find((e) => e.type === 'TOOL_STARTED'), [events]);
  const toolStdout = useMemo(() => events.find((e) => e.type === 'TOOL_STDOUT'), [events]);
  const toolStderr = useMemo(() => events.find((e) => e.type === 'TOOL_STDERR'), [events]);
  const toolFinished = useMemo(() => events.find((e) => e.type === 'TOOL_FINISHED'), [events]);
  const toolSpillover = useMemo(() => events.find((e) => e.type === 'TOOL_SPILLOVER'), [events]);

  // 7. Layer 6 Specialised Agent Events
  const agentInit = useMemo(() => events.find((e) => e.type === 'AGENT_INIT'), [events]);
  const toolIntents = useMemo(() => events.filter((e) => e.type === 'TOOL_INTENT'), [events]);
  const agentResponse = useMemo(() => events.find((e) => e.type === 'AGENT_RESPONSE'), [events]);

  // 8. Turn Complete / Metrics
  const turnCompleteEvent = useMemo(() => {
    return events.find((e) => e.type === 'TURN_COMPLETE');
  }, [events]);

  const metrics = useMemo(() => {
    if (turnCompleteEvent?.payload && typeof turnCompleteEvent.payload === 'object') {
      return turnCompleteEvent.payload;
    }
    return null;
  }, [turnCompleteEvent]);

  if (events.length === 0 && !record && !isRunning) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
        <Terminal size={32} style={{ margin: '0 auto 12px', color: 'var(--accent-blue)', opacity: 0.5 }} />
        <div style={{ fontWeight: 700, fontSize: '15px', color: 'var(--text-main)', marginBottom: '4px' }}>
          Workbench Ready for Execution
        </div>
        <div style={{ fontSize: '12.5px' }}>
          Configure parameters on the left and click <strong>Run Module</strong> to begin live streaming.
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Stepper Progress Bar */}
      <div className="card" style={{ margin: 0, padding: 0 }}>
        <div className="stepper-nav">
          <div className={`step-pill ${normalizationEvent ? 'completed' : isRunning ? 'active' : ''}`}>
            <Terminal size={13} />
            <span>1. Ingress &amp; Normalization</span>
          </div>

          <div className={`step-pill ${safetyEvent ? 'completed' : ''}`}>
            <ShieldCheck size={13} />
            <span>2. Safety Gate</span>
          </div>

          <div className={`step-pill ${thoughts ? 'completed' : ''}`}>
            <Brain size={13} />
            <span>3. Planner Reasoning</span>
          </div>

          <div className={`step-pill ${streamedTokens ? 'completed' : isRunning ? 'active' : ''}`}>
            <Zap size={13} />
            <span>4. Token Stream</span>
          </div>

          <div className={`step-pill ${record ? (record.status === 'SUCCESS' ? 'completed' : 'active') : ''}`}>
            <Activity size={13} />
            <span>5. Telemetry &amp; Metrics</span>
          </div>
        </div>
      </div>

      {/* Step 1: Ingress & Normalization Card */}
      {normalizationEvent && (
        <div className="card" style={{ margin: 0 }}>
          <div className="card-header">
            <div className="card-title">
              <Terminal size={15} style={{ color: 'var(--accent-blue)' }} />
              <span>Step 1: Gateway Inbound Normalization</span>
              <span className="badge badge-mint">NORMALIZED</span>
            </div>
            <button
              className="btn btn-default"
              style={{ padding: '3px 8px', fontSize: '11px' }}
              onClick={() => toggleRaw('norm')}
            >
              {showRaw['norm'] ? 'Hide Raw' : 'Raw JSON'}
            </button>
          </div>

          <div className="card-body">
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
              <span className="badge badge-sky">
                Target: @{normalizationEvent.payload?.target_agent || 'auto'}
              </span>
              <span className="badge badge-slate">
                Channel: {normalizationEvent.payload?.channel || 'CLI'}
              </span>
              <span className="badge badge-slate">
                Trigger: {normalizationEvent.payload?.trigger || 'INTERACTIVE'}
              </span>
              {normalizationEvent.payload?.session_id && (
                <span className="badge badge-slate mono" title={normalizationEvent.payload.session_id}>
                  Session: {normalizationEvent.payload.session_id.slice(0, 8)}...
                </span>
              )}
            </div>

            <div style={{ background: 'var(--bg-app)', padding: '12px 14px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>
                Cleaned Inbound Prompt:
              </div>
              <div style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-main)', lineHeight: '1.5' }}>
                "{normalizationEvent.payload?.prompt || ''}"
              </div>
            </div>

            {showRaw['norm'] && (
              <pre style={{ marginTop: '12px', padding: '12px', background: '#0f172a', color: '#f8fafc', borderRadius: '6px', fontSize: '11.5px', overflowX: 'auto' }}>
                {JSON.stringify(normalizationEvent.payload, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}

      {/* Step 2: Safety & Policy Gatekeeper */}
      {safetyEvent && (
        <div className="card" style={{ margin: 0 }}>
          <div className="card-header">
            <div className="card-title">
              <ShieldCheck size={15} style={{ color: 'var(--accent-amber)' }} />
              <span>Step 2: Safety Gatekeeper Verification</span>
              <span className={`badge ${safetyEvent.payload?.verdict === 'DENIED' || !safetyEvent.payload?.allowed ? 'badge-rose' : safetyEvent.payload?.requires_hitl ? 'badge-amber' : 'badge-mint'}`}>
                {safetyEvent.payload?.verdict || (safetyEvent.payload?.allowed ? 'ALLOWED' : 'DENIED')}
              </span>
            </div>
            <button
              className="btn btn-default"
              style={{ padding: '3px 8px', fontSize: '11px' }}
              onClick={() => toggleRaw('safety')}
            >
              {showRaw['safety'] ? 'Hide Raw' : 'Raw JSON'}
            </button>
          </div>

          <div className="card-body">
            <div className="metric-grid" style={{ marginBottom: '12px' }}>
              <div className="metric-tile">
                <div className="metric-tile-label">Risk Classification</div>
                <div className="metric-tile-val" style={{ fontSize: '14px', color: safetyEvent.payload?.risk === 'HIGH' ? 'var(--accent-coral)' : 'var(--accent-mint)' }}>
                  {safetyEvent.payload?.risk || 'LOW'}
                </div>
              </div>

              <div className="metric-tile">
                <div className="metric-tile-label">HITL Requirement</div>
                <div className="metric-tile-val" style={{ fontSize: '14px', color: safetyEvent.payload?.requires_hitl ? 'var(--accent-amber)' : 'var(--text-muted)' }}>
                  {safetyEvent.payload?.requires_hitl ? 'Approval Required' : 'None'}
                </div>
              </div>

              <div className="metric-tile">
                <div className="metric-tile-label">Action Permission</div>
                <div className="metric-tile-val" style={{ fontSize: '14px', color: safetyEvent.payload?.allowed !== false ? 'var(--accent-mint)' : 'var(--accent-coral)' }}>
                  {safetyEvent.payload?.allowed !== false ? 'Permitted' : 'Blocked'}
                </div>
              </div>
            </div>

            {safetyEvent.payload?.reason && (
              <div style={{ background: 'var(--bg-app)', padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--border-subtle)', fontSize: '12.5px' }}>
                <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Policy Explanation: </span>
                <span style={{ color: 'var(--text-main)' }}>{safetyEvent.payload.reason}</span>
              </div>
            )}

            {showRaw['safety'] && (
              <pre style={{ marginTop: '12px', padding: '12px', background: '#0f172a', color: '#f8fafc', borderRadius: '6px', fontSize: '11.5px', overflowX: 'auto' }}>
                {JSON.stringify(safetyEvent.payload, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}

      {/* Step 3: Planner Reasoning / Thoughts */}
      {thoughts && (
        <div className="card" style={{ margin: 0 }}>
          <div className="card-header">
            <div className="card-title">
              <Brain size={15} style={{ color: 'var(--accent-lavender)' }} />
              <span>Step 3: Planner Reasoning Process</span>
              <span className="badge badge-lavender">INTERNAL MONOLOGUE</span>
            </div>
            <button
              className="btn btn-default"
              style={{ padding: '3px 8px', fontSize: '11px' }}
              onClick={() => copyToClipboard('thoughts', thoughts)}
            >
              {copiedId === 'thoughts' ? <Check size={11} color="var(--accent-mint)" /> : <Copy size={11} />}
              <span>{copiedId === 'thoughts' ? 'Copied' : 'Copy'}</span>
            </button>
          </div>

          <div className="card-body">
            <div className="thought-box">
              {thoughts}
            </div>
          </div>
        </div>
      )}

      {/* Step 4: Streamed Tokens / Assistant Response */}
      {(streamedTokens || (isRunning && !thoughts)) && (
        <div className="card" style={{ margin: 0 }}>
          <div className="card-header">
            <div className="card-title">
              <Zap size={15} style={{ color: 'var(--accent-mint)' }} />
              <span>Step 4: Live Token Stream (Assistant)</span>
              {isRunning && <span className="badge badge-amber">STREAMING ACTIVE</span>}
            </div>
            <button
              className="btn btn-default"
              style={{ padding: '3px 8px', fontSize: '11px' }}
              onClick={() => copyToClipboard('tokens', streamedTokens)}
            >
              {copiedId === 'tokens' ? <Check size={11} color="var(--accent-mint)" /> : <Copy size={11} />}
              <span>{copiedId === 'tokens' ? 'Copied' : 'Copy'}</span>
            </button>
          </div>

          <div className="card-body">
            <div className="token-stream-container">
              {streamedTokens}
              {isRunning && <span className="blinking-cursor" />}
            </div>
          </div>
        </div>
      )}

      {/* Layer 3: Tool Execution Panel */}
      {(toolStarted || toolStdout || toolFinished) && (
        <div className="card" style={{ margin: 0, borderLeft: '4px solid var(--accent-coral)' }}>
          <div className="card-header">
            <div className="card-title">
              <Wrench size={15} style={{ color: 'var(--accent-coral)' }} />
              <span>Layer 3: Native Tool Execution Ground Truth</span>
              {toolStarted?.payload?.tool_name && (
                <span className="badge badge-sky">{toolStarted.payload.tool_name}</span>
              )}
              {toolStarted?.payload?.risk_level && (
                <span
                  className={`badge ${
                    toolStarted.payload.risk_level === 'HIGH'
                      ? 'badge-coral'
                      : toolStarted.payload.risk_level === 'MEDIUM'
                      ? 'badge-amber'
                      : 'badge-mint'
                  }`}
                >
                  RISK: {toolStarted.payload.risk_level}
                </span>
              )}
            </div>
          </div>

          <div className="card-body">
            {toolStarted?.payload?.args && (
              <div style={{ marginBottom: '10px' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Arguments:
                </span>
                <pre style={{ background: 'var(--bg-app)', padding: '8px 12px', borderRadius: '6px', fontSize: '12px', marginTop: '4px', border: '1px solid var(--border-subtle)' }}>
                  {typeof toolStarted.payload.args === 'string' ? toolStarted.payload.args : JSON.stringify(toolStarted.payload.args, null, 2)}
                </pre>
              </div>
            )}

            {toolStdout && (
              <div style={{ marginBottom: '10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    Stdout Stream:
                  </span>
                  <button
                    className="btn btn-default"
                    style={{ padding: '2px 6px', fontSize: '11px' }}
                    onClick={() => copyToClipboard('stdout', String(toolStdout.payload))}
                  >
                    {copiedId === 'stdout' ? <Check size={11} color="var(--accent-mint)" /> : <Copy size={11} />}
                    <span>{copiedId === 'stdout' ? 'Copied' : 'Copy'}</span>
                  </button>
                </div>
                <pre style={{ background: '#0f172a', color: '#38bdf8', padding: '12px', borderRadius: '6px', fontSize: '12px', overflowX: 'auto', maxHeight: '300px' }}>
                  {String(toolStdout.payload)}
                </pre>
              </div>
            )}

            {toolStderr && (
              <div style={{ marginBottom: '10px' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--accent-coral)', textTransform: 'uppercase' }}>
                  Stderr Stream:
                </span>
                <pre style={{ background: 'rgba(239, 68, 68, 0.1)', color: 'var(--accent-coral)', padding: '10px', borderRadius: '6px', fontSize: '12px', marginTop: '4px', border: '1px solid var(--accent-coral)' }}>
                  {String(toolStderr.payload)}
                </pre>
              </div>
            )}

            {toolSpillover && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'var(--accent-amber-bg)', padding: '8px 12px', borderRadius: '6px', fontSize: '12px', color: 'var(--accent-amber)', marginBottom: '10px' }}>
                <AlertTriangle size={14} />
                <span>{String(toolSpillover.payload)}</span>
              </div>
            )}

            {toolFinished && (
              <div style={{ display: 'flex', gap: '16px', fontSize: '12px', paddingTop: '8px', borderTop: '1px solid var(--border-subtle)' }}>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Exit Code: </span>
                  <strong style={{ color: toolFinished.payload?.exit_code === 0 ? 'var(--accent-mint)' : 'var(--accent-coral)' }}>
                    {toolFinished.payload?.exit_code ?? 0}
                  </strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Duration: </span>
                  <strong>{toolFinished.payload?.duration_ms ?? 0}ms</strong>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Layer 6: Specialised Agent Cognitive ReAct Panel */}
      {(agentInit || toolIntents.length > 0 || agentResponse) && (
        <div className="card" style={{ margin: 0, borderLeft: '4px solid var(--accent-amber)' }}>
          <div className="card-header">
            <div className="card-title">
              <Bot size={15} style={{ color: 'var(--accent-amber)' }} />
              <span>Layer 6: Specialised Worker Agent ReAct Loop</span>
              {agentInit?.payload?.agent && (
                <span className="badge badge-amber">@{agentInit.payload.agent}</span>
              )}
              {agentInit?.payload?.model_mode && (
                <span className="badge badge-lavender">Mode: {agentInit.payload.model_mode}</span>
              )}
            </div>
          </div>

          <div className="card-body">
            {toolIntents.length > 0 && (
              <div style={{ marginBottom: '12px' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Tool Invocations Proposed by Agent:
                </span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
                  {toolIntents.map((ti, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: 'var(--bg-app)',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-subtle)',
                        fontSize: '12px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                        <Wrench size={12} style={{ color: 'var(--accent-blue)' }} />
                        <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-blue)' }}>
                          {ti.agent_name || 'tool'}
                        </strong>
                      </div>
                      <pre style={{ margin: 0, fontSize: '11.5px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                        {typeof ti.payload === 'string' ? ti.payload : JSON.stringify(ti.payload, null, 2)}
                      </pre>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {agentResponse && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    Final Agent Response:
                  </span>
                  <button
                    className="btn btn-default"
                    style={{ padding: '2px 6px', fontSize: '11px' }}
                    onClick={() => copyToClipboard('agent_resp', String(agentResponse.payload))}
                  >
                    {copiedId === 'agent_resp' ? <Check size={11} color="var(--accent-mint)" /> : <Copy size={11} />}
                    <span>{copiedId === 'agent_resp' ? 'Copied' : 'Copy'}</span>
                  </button>
                </div>
                <div style={{ background: '#ffffff', border: '1px solid var(--border-subtle)', borderRadius: '8px', padding: '12px 14px', fontSize: '13px', lineHeight: 1.5, color: 'var(--text-main)' }}>
                  {String(agentResponse.payload)}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Step 5: Completion & Metrics Dashboard */}
      {metrics && (
        <div className="card" style={{ margin: 0 }}>
          <div className="card-header">
            <div className="card-title">
              <Activity size={15} style={{ color: 'var(--accent-blue)' }} />
              <span>Step 5: Turn Metrics &amp; Telemetry Ground Truth</span>
              <span className="badge badge-mint">{metrics.model_name || 'Completed'}</span>
            </div>
            <button
              className="btn btn-default"
              style={{ padding: '3px 8px', fontSize: '11px' }}
              onClick={() => toggleRaw('metrics')}
            >
              {showRaw['metrics'] ? 'Hide Raw' : 'Raw JSON'}
            </button>
          </div>

          <div className="card-body">
            <div className="metric-grid">
              <div className="metric-tile">
                <div className="metric-tile-label">Prompt Tokens</div>
                <div className="metric-tile-val" style={{ color: 'var(--accent-blue)' }}>
                  {metrics.prompt_tokens ?? '-'}
                </div>
              </div>

              <div className="metric-tile">
                <div className="metric-tile-label">Completion Tokens</div>
                <div className="metric-tile-val" style={{ color: 'var(--accent-mint)' }}>
                  {metrics.completion_tokens ?? '-'}
                </div>
              </div>

              <div className="metric-tile">
                <div className="metric-tile-label">Cached Tokens</div>
                <div className="metric-tile-val" style={{ color: 'var(--accent-lavender)' }}>
                  {metrics.cached_tokens ?? 0}
                </div>
              </div>

              <div className="metric-tile">
                <div className="metric-tile-label">TTFT Latency</div>
                <div className="metric-tile-val" style={{ color: 'var(--accent-amber)' }}>
                  {metrics.ttft_ms ? `${metrics.ttft_ms}ms` : '-'}
                </div>
              </div>
            </div>

            {/* Token Distribution Bar */}
            {metrics.prompt_tokens && metrics.completion_tokens && (
              <div style={{ marginBottom: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11.5px', color: 'var(--text-muted)', marginBottom: '5px' }}>
                  <span>Token Distribution: {metrics.prompt_tokens} prompt / {metrics.completion_tokens} completion</span>
                  <span>{metrics.prompt_tokens + metrics.completion_tokens} Total Tokens</span>
                </div>
                <div style={{ height: '7px', background: 'var(--border-main)', borderRadius: '4px', overflow: 'hidden', display: 'flex' }}>
                  <div
                    style={{
                      width: `${(metrics.prompt_tokens / (metrics.prompt_tokens + metrics.completion_tokens)) * 100}%`,
                      background: 'var(--accent-blue)',
                    }}
                  />
                  <div
                    style={{
                      width: `${(metrics.completion_tokens / (metrics.prompt_tokens + metrics.completion_tokens)) * 100}%`,
                      background: 'var(--accent-mint)',
                    }}
                  />
                </div>
              </div>
            )}

            {showRaw['metrics'] && (
              <pre style={{ marginTop: '12px', padding: '12px', background: '#0f172a', color: '#f8fafc', borderRadius: '6px', fontSize: '11.5px', overflowX: 'auto' }}>
                {JSON.stringify(metrics, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}

      {/* Operational Status Trail (Accordion) */}
      {statusUpdates.length > 0 && (
        <div className="card" style={{ margin: 0 }}>
          <div
            className="card-header"
            style={{ cursor: 'pointer' }}
            onClick={() => toggleRaw('status_feed')}
          >
            <div className="card-title">
              <Clock size={15} style={{ color: 'var(--text-muted)' }} />
              <span>Operational Status Trail ({statusUpdates.length} steps)</span>
            </div>
            {showRaw['status_feed'] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </div>

          {showRaw['status_feed'] && (
            <div className="card-body" style={{ padding: '12px 18px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {statusUpdates.map((st, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '12px' }}>
                    <span className="mono" style={{ color: 'var(--text-muted)', width: '70px' }}>
                      {new Date(st.timestamp).toLocaleTimeString()}
                    </span>
                    <span className="badge badge-slate" style={{ fontSize: '11px' }}>
                      @{st.agent_name || 'System'}
                    </span>
                    <span style={{ color: 'var(--text-main)' }}>
                      {typeof st.payload === 'string' ? st.payload : JSON.stringify(st.payload)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
