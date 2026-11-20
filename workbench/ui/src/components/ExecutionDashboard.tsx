import React, { useState, useMemo } from 'react';
import { StreamEvent, ExecutionRecord, AgentDetail } from '../types';
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
  FileText,
  GitBranch,
} from 'lucide-react';

interface ExecutionDashboardProps {
  events: StreamEvent[];
  record: ExecutionRecord | null;
  isRunning: boolean;
  agents?: AgentDetail[];
}

export const ExecutionDashboard: React.FC<ExecutionDashboardProps> = ({
  events,
  record,
  isRunning,
  agents = [],
}) => {
  const [showRaw, setShowRaw] = useState<Record<string, boolean>>({});
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    prompt: true,
    tools: false,
    system_prompt: false,
    plan: true,
    tool_results: true,
    thoughts: true,
    tokens: true,
  });
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const toggleRaw = (stepId: string) => {
    setShowRaw((prev) => ({ ...prev, [stepId]: !prev[stepId] }));
  };

  const toggleSection = (secId: string) => {
    setExpandedSections((prev) => ({ ...prev, [secId]: !prev[secId] }));
  };

  const copyToClipboard = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  // 1. Ingestion / Inbound User Request
  const normalizationEvent = useMemo(() => {
    return (
      events.find((e) => e.type === 'GATEWAY_NORMALIZED') ||
      (record?.output?.normalized_request
        ? { payload: record.output.normalized_request }
        : null)
    );
  }, [events, record]);

  const userRequest = useMemo(() => {
    const fromNorm = normalizationEvent?.payload;
    if (fromNorm?.prompt) return fromNorm;
    if (record?.input?.prompt) {
      return {
        prompt: record.input.prompt,
        target_agent: record.input.target_agent || record.input.agent_type || 'auto',
        channel: record.input.channel || 'CLI',
        trigger: record.input.trigger || 'INTERACTIVE',
        session_id: record.input.session_id || 'manual_session',
        user_id: record.input.user_id || 'local:prit',
        trace_id: record.telemetry?.trace_id || '',
        span_id: record.telemetry?.span_id || '',
        allowed_capabilities: record.input.allowed_capabilities || record.input.allowed_caps || [],
      };
    }
    return null;
  }, [normalizationEvent, record]);

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

  // 4. DAG Plan Events
  const planEvent = useMemo(() => {
    return events.find((e) => e.type === 'PLAN_CREATED' || e.type === 'EventPlanCreated');
  }, [events]);

  // 5. Subtasks Progression Events ("What happened next")
  const subtaskEvents = useMemo(() => {
    const list = events.filter((e) =>
      e.type === 'SUBTASK_START' ||
      e.type === 'SUBTASK_COMPLETE' ||
      e.type === 'SUBTASK_FAILED' ||
      e.type === 'SUBTASK_PROGRESS'
    );
    // Group by subtask ID
    const byId: Record<string, { start?: any; complete?: any; status: string; worker: string; desc: string; output?: string; duration?: number; input_prompt?: string; error?: string }> = {};
    for (const ev of list) {
      const payload = ev.payload;
      if (!payload || !payload.subtask_id) continue;
      const id = payload.subtask_id;
      if (!byId[id]) {
        byId[id] = {
          status: payload.status || 'PENDING',
          worker: payload.worker || ev.agent_name || 'worker',
          desc: payload.description || '',
          input_prompt: payload.input_prompt,
        };
      }
      if (ev.type === 'SUBTASK_START') {
        byId[id].start = payload;
        byId[id].status = 'IN_PROGRESS';
        if (payload.worker) byId[id].worker = payload.worker;
        if (payload.input_prompt) byId[id].input_prompt = payload.input_prompt;
      } else if (ev.type === 'SUBTASK_COMPLETE') {
        byId[id].complete = payload;
        byId[id].status = 'COMPLETED';
        byId[id].output = payload.output;
        byId[id].duration = payload.duration_ms;
      } else if (ev.type === 'SUBTASK_FAILED') {
        byId[id].status = 'FAILED';
        byId[id].error = payload.error;
        byId[id].duration = payload.duration_ms;
      }
    }
    return Object.entries(byId).map(([id, info]) => ({ id, ...info }));
  }, [events]);

  // 6. Reasoning / Thoughts (aggregated)
  const thoughts = useMemo(() => {
    return events
      .filter((e) => e.type === 'THOUGHT_CHUNK' || e.type === 'AGENT_THOUGHT')
      .map((e) => (typeof e.payload === 'string' ? e.payload : JSON.stringify(e.payload)))
      .join(' ');
  }, [events]);

  // 7. Tokens / Output (aggregated stream)
  const streamedTokens = useMemo(() => {
    return events
      .filter((e) => e.type === 'TOKEN_CHUNK' || e.type === 'AGENT_TOKEN')
      .map((e) => (typeof e.payload === 'string' ? e.payload : JSON.stringify(e.payload)))
      .join('\n');
  }, [events]);

  // 8. Tool Call Logs & What It Returned (Unified Ground Truth)
  const unifiedToolRuns = useMemo(() => {
    const runs: Array<{
      call_id: string;
      tool_name: string;
      agent_name: string;
      args: any;
      output?: string;
      exit_code?: number;
      duration_ms?: number;
      is_error?: boolean;
      timestamp?: string;
    }> = [];

    // Map of call_id to run
    const byCallId: Record<string, number> = {};

    for (const ev of events) {
      if (ev.type === 'TOOL_CALL' && ev.payload) {
        const tc = ev.payload;
        const callId = tc.call_id || `call_${runs.length + 1}`;
        const run = {
          call_id: callId,
          tool_name: tc.tool_name || 'unknown_tool',
          agent_name: ev.agent_name || 'agent',
          args: tc.arguments || tc.args_json || {},
          timestamp: ev.timestamp,
        };
        byCallId[callId] = runs.length;
        runs.push(run);
      } else if (ev.type === 'TOOL_RESULT' && ev.payload) {
        const tr = ev.payload;
        const callId = tr.call_id;
        if (callId && byCallId[callId] !== undefined) {
          const run = runs[byCallId[callId]];
          run.output = tr.output;
          run.exit_code = tr.exit_code ?? 0;
          run.duration_ms = tr.duration_ms;
          run.is_error = tr.is_error;
        } else {
          runs.push({
            call_id: callId || `call_${runs.length + 1}`,
            tool_name: tr.tool_name || ev.agent_name || 'tool',
            agent_name: ev.agent_name || 'tool',
            args: {},
            output: tr.output,
            exit_code: tr.exit_code ?? 0,
            duration_ms: tr.duration_ms,
            is_error: tr.is_error,
            timestamp: ev.timestamp,
          });
        }
      } else if (ev.type === 'TOOL_STARTED' && ev.payload) {
        const p = ev.payload;
        const callId = `l3_tool_${runs.length + 1}`;
        byCallId[callId] = runs.length;
        runs.push({
          call_id: callId,
          tool_name: p.tool_name || 'tool',
          agent_name: 'Layer3Tools',
          args: p.args,
          timestamp: ev.timestamp,
        });
      } else if (ev.type === 'TOOL_FINISHED' && ev.payload) {
        const p = ev.payload;
        if (runs.length > 0) {
          const last = runs[runs.length - 1];
          last.exit_code = p.exit_code;
          last.duration_ms = p.duration_ms;
        }
      } else if (ev.type === 'TOOL_STDOUT' && ev.payload && runs.length > 0) {
        runs[runs.length - 1].output = String(ev.payload);
      } else if (ev.type === 'TOOL_INTENT' && ev.payload) {
        const toolName = ev.agent_name || 'tool';
        let parsedArgs: any = ev.payload;
        try {
          if (typeof ev.payload === 'string') parsedArgs = JSON.parse(ev.payload);
        } catch {
          parsedArgs = ev.payload;
        }
        runs.push({
          call_id: `intent_${runs.length + 1}`,
          tool_name: toolName,
          agent_name: ev.agent_name || 'agent',
          args: parsedArgs,
          timestamp: ev.timestamp,
        });
      }
    }

    return runs;
  }, [events]);

  // 9. Active Agent Persona & System Prompt Resolution
  const agentInit = useMemo(() => events.find((e) => e.type === 'AGENT_INIT'), [events]);
  const activeAgentId = useMemo(() => {
    if (agentInit?.payload?.agent) return agentInit.payload.agent;
    if (userRequest?.target_agent && userRequest.target_agent !== 'auto') return userRequest.target_agent.replace(/^@/, '');
    if (record?.input?.agent_type) return record.input.agent_type;
    return 'system';
  }, [agentInit, userRequest, record]);

  const activeAgentDetail = useMemo(() => {
    return agents.find((a) => a.id === activeAgentId) || null;
  }, [agents, activeAgentId]);

  const systemPromptResolved = useMemo(() => {
    if (agentInit?.payload?.system_prompt) return agentInit.payload.system_prompt;
    if (activeAgentDetail?.system_prompt) return activeAgentDetail.system_prompt;
    return null;
  }, [agentInit, activeAgentDetail]);

  const availableToolsResolved = useMemo(() => {
    if (agentInit?.payload?.available_tools) return agentInit.payload.available_tools;
    if (activeAgentDetail?.tools) return activeAgentDetail.tools;
    return [];
  }, [agentInit, activeAgentDetail]);

  // 10. Turn Complete / Metrics
  const turnCompleteEvent = useMemo(() => {
    return events.find((e) => e.type === 'TURN_COMPLETE');
  }, [events]);

  const metrics = useMemo(() => {
    if (turnCompleteEvent?.payload && typeof turnCompleteEvent.payload === 'object') {
      return turnCompleteEvent.payload;
    }
    if (record?.output?.metrics) {
      return record.output.metrics;
    }
    return null;
  }, [turnCompleteEvent, record]);

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
      {/* 7-Step Navigation Progress Header */}
      <div className="card" style={{ margin: 0, padding: 0 }}>
        <div className="stepper-nav" style={{ flexWrap: 'wrap' }}>
          <div className={`step-pill ${userRequest ? 'completed' : isRunning ? 'active' : ''}`}>
            <Terminal size={12} />
            <span>1. User Request</span>
          </div>

          <div className={`step-pill ${safetyEvent ? 'completed' : ''}`}>
            <ShieldCheck size={12} />
            <span>2. Safety Gate</span>
          </div>

          <div className={`step-pill ${availableToolsResolved.length > 0 || systemPromptResolved ? 'completed' : ''}`}>
            <Bot size={12} />
            <span>3. Agent &amp; Tools</span>
          </div>

          <div className={`step-pill ${planEvent || subtaskEvents.length > 0 ? 'completed' : ''}`}>
            <GitBranch size={12} />
            <span>4. Trajectory (DAG)</span>
          </div>

          <div className={`step-pill ${unifiedToolRuns.length > 0 ? 'completed' : ''}`}>
            <Wrench size={12} />
            <span>5. Tool Ground Truth</span>
          </div>

          <div className={`step-pill ${thoughts || streamedTokens ? 'completed' : isRunning ? 'active' : ''}`}>
            <Brain size={12} />
            <span>6. Reasoning &amp; Stream</span>
          </div>

          <div className={`step-pill ${metrics || record ? 'completed' : ''}`}>
            <Activity size={12} />
            <span>7. Latency &amp; Tokens</span>
          </div>
        </div>
      </div>

      {/* STEP 1: What was the User Request */}
      {userRequest && (
        <div className="card" style={{ margin: 0 }}>
          <div className="card-header">
            <div className="card-title">
              <Terminal size={15} style={{ color: 'var(--accent-blue)' }} />
              <span>Step 1: User Request &amp; Inbound Scope</span>
              <span className="badge badge-mint">CAPTURED</span>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                className="btn btn-default"
                style={{ padding: '3px 8px', fontSize: '11px' }}
                onClick={() => copyToClipboard('user_prompt', userRequest.prompt || '')}
              >
                {copiedId === 'user_prompt' ? <Check size={11} color="var(--accent-mint)" /> : <Copy size={11} />}
                <span>{copiedId === 'user_prompt' ? 'Copied' : 'Copy'}</span>
              </button>
              <button
                className="btn btn-default"
                style={{ padding: '3px 8px', fontSize: '11px' }}
                onClick={() => toggleRaw('norm')}
              >
                {showRaw['norm'] ? 'Hide Raw' : 'Raw JSON'}
              </button>
            </div>
          </div>

          <div className="card-body">
            {/* User Prompt Box */}
            <div style={{ background: 'var(--bg-app)', padding: '14px 16px', borderRadius: '8px', border: '1px solid var(--border-subtle)', marginBottom: '12px' }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px', textTransform: 'uppercase' }}>
                Prompt Input:
              </div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-main)', lineHeight: '1.5' }}>
                "{userRequest.prompt}"
              </div>
            </div>

            {/* Inbound Metadata Badges */}
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
              <span className="badge badge-sky">
                Target: @{userRequest.target_agent || 'auto'}
              </span>
              <span className="badge badge-slate">
                Channel: {userRequest.channel || 'CLI'}
              </span>
              <span className="badge badge-slate">
                Trigger: {userRequest.trigger || 'INTERACTIVE'}
              </span>
              {userRequest.session_id && (
                <span className="badge badge-slate mono" title={userRequest.session_id}>
                  Session: {userRequest.session_id.slice(0, 12)}...
                </span>
              )}
              {userRequest.trace_id && (
                <span className="badge badge-lavender mono" title={`W3C TraceID: ${userRequest.trace_id}`}>
                  TraceID: {userRequest.trace_id.slice(0, 10)}...
                </span>
              )}
            </div>

            {/* Whitelist Capabilities */}
            {userRequest.allowed_capabilities && userRequest.allowed_capabilities.length > 0 && (
              <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>Capability Whitelist:</span>
                {userRequest.allowed_capabilities.map((c: string) => (
                  <span key={c} className="badge badge-mint" style={{ fontSize: '10.5px' }}>
                    {c}
                  </span>
                ))}
              </div>
            )}

            {showRaw['norm'] && (
              <pre style={{ marginTop: '12px', padding: '12px', background: '#0f172a', color: '#f8fafc', borderRadius: '6px', fontSize: '11.5px', overflowX: 'auto' }}>
                {JSON.stringify(userRequest, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}

      {/* STEP 2: Safety & Gatekeeper Verification */}
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

      {/* STEP 3: Available Tools & Agent System Prompt */}
      {(availableToolsResolved.length > 0 || systemPromptResolved || activeAgentDetail) && (
        <div className="card" style={{ margin: 0, borderLeft: '4px solid var(--accent-lavender)' }}>
          <div className="card-header">
            <div className="card-title">
              <Bot size={15} style={{ color: 'var(--accent-lavender)' }} />
              <span>Step 3: Agent Persona &amp; Available Toolset</span>
              <span className="badge badge-lavender">@{activeAgentId}</span>
              {activeAgentDetail?.model?.default && (
                <span className="badge badge-sky">Model: {activeAgentDetail.model.default}</span>
              )}
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                className="btn btn-default"
                style={{ padding: '3px 8px', fontSize: '11px' }}
                onClick={() => toggleSection('system_prompt')}
              >
                <FileText size={11} />
                <span>{expandedSections['system_prompt'] ? 'Hide System Prompt' : 'View System Prompt'}</span>
              </button>
              <button
                className="btn btn-default"
                style={{ padding: '3px 8px', fontSize: '11px' }}
                onClick={() => toggleSection('tools')}
              >
                <Wrench size={11} />
                <span>{expandedSections['tools'] ? 'Hide Tools' : `Tools (${availableToolsResolved.length})`}</span>
              </button>
            </div>
          </div>

          <div className="card-body">
            {/* System Prompt Collapsible Viewer */}
            {expandedSections['system_prompt'] && systemPromptResolved && (
              <div style={{ marginBottom: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    Active Grounding System Prompt:
                  </span>
                  <button
                    className="btn btn-default"
                    style={{ padding: '2px 6px', fontSize: '11px' }}
                    onClick={() => copyToClipboard('sys_prompt', systemPromptResolved)}
                  >
                    {copiedId === 'sys_prompt' ? <Check size={11} color="var(--accent-mint)" /> : <Copy size={11} />}
                    <span>{copiedId === 'sys_prompt' ? 'Copied' : 'Copy Prompt'}</span>
                  </button>
                </div>
                <pre
                  style={{
                    background: '#0f172a',
                    color: '#f8fafc',
                    padding: '12px 14px',
                    borderRadius: '8px',
                    fontSize: '11.5px',
                    lineHeight: '1.6',
                    maxHeight: '260px',
                    overflowY: 'auto',
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  {systemPromptResolved}
                </pre>
              </div>
            )}

            {/* Available Tools Grid */}
            {expandedSections['tools'] && (
              <div>
                <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase' }}>
                  Available Tools Registered for @{activeAgentId}:
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '8px' }}>
                  {availableToolsResolved.map((t: any) => (
                    <div
                      key={t.name}
                      style={{
                        background: 'var(--bg-app)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: '6px',
                        padding: '10px 12px',
                        fontSize: '12px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                        <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-blue)' }}>{t.name}</strong>
                        <span className={`badge ${t.risk === 'HIGH' ? 'badge-rose' : t.risk === 'MEDIUM' ? 'badge-amber' : 'badge-mint'}`} style={{ fontSize: '10px' }}>
                          {t.risk || 'LOW'}
                        </span>
                      </div>
                      <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)', lineHeight: 1.3 }}>{t.description}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {!expandedSections['system_prompt'] && !expandedSections['tools'] && (
              <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)' }}>
                Target worker <strong>@{activeAgentId}</strong> initialized with <strong>{availableToolsResolved.length} tools</strong> and grounded persona template.
              </div>
            )}
          </div>
        </div>
      )}

      {/* STEP 4: What happened next (DAG Plan & Subtask Progression) */}
      {(planEvent || subtaskEvents.length > 0) && (
        <div className="card" style={{ margin: 0 }}>
          <div className="card-header">
            <div className="card-title">
              <GitBranch size={15} style={{ color: 'var(--accent-blue)' }} />
              <span>Step 4: Topological Execution Trajectory &amp; DAG Subtasks</span>
              <span className="badge badge-sky">{subtaskEvents.length} Tasks Scheduled</span>
            </div>
            <button
              className="btn btn-default"
              style={{ padding: '3px 8px', fontSize: '11px' }}
              onClick={() => toggleRaw('plan')}
            >
              {showRaw['plan'] ? 'Hide Raw' : 'Raw JSON'}
            </button>
          </div>

          <div className="card-body">
            {planEvent?.payload?.primary_goal && (
              <div style={{ background: 'var(--bg-app)', padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--border-subtle)', marginBottom: '14px', fontSize: '13px' }}>
                <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Primary Plan Goal: </span>
                <span style={{ color: 'var(--text-main)', fontWeight: 500 }}>{planEvent.payload.primary_goal}</span>
              </div>
            )}

            {/* Subtasks Sequence Timeline */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {subtaskEvents.map((st) => {
                const isComplete = st.status === 'COMPLETED';
                const isFailed = st.status === 'FAILED';
                const inProgress = st.status === 'IN_PROGRESS';
                return (
                  <div
                    key={st.id}
                    style={{
                      background: 'var(--bg-surface-elevated)',
                      border: '1px solid var(--border-main)',
                      borderLeft: `4px solid ${isComplete ? 'var(--accent-mint)' : isFailed ? 'var(--accent-coral)' : inProgress ? 'var(--accent-amber)' : 'var(--border-main)'}`,
                      borderRadius: '8px',
                      padding: '12px 16px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span className="mono" style={{ fontWeight: 700, fontSize: '13px', color: 'var(--accent-blue)' }}>
                          {st.id}
                        </span>
                        <span className="badge badge-lavender" style={{ fontSize: '11px' }}>
                          @{st.worker}
                        </span>
                        <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)' }}>
                          {st.desc}
                        </span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {st.duration !== undefined && (
                          <span className="mono" style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                            {st.duration}ms
                          </span>
                        )}
                        <span className={`badge ${isComplete ? 'badge-mint' : isFailed ? 'badge-rose' : 'badge-amber'}`}>
                          {st.status}
                        </span>
                      </div>
                    </div>

                    {/* Inputs passed to this subtask from prior tasks */}
                    {st.input_prompt && (
                      <div style={{ background: 'var(--bg-app)', padding: '8px 12px', borderRadius: '6px', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                        <span style={{ fontWeight: 600, color: 'var(--text-muted)' }}>Injected Input Prompt: </span>
                        <span>{st.input_prompt}</span>
                      </div>
                    )}

                    {/* What this subtask returned */}
                    {st.output && (
                      <div style={{ background: '#0f172a', color: '#38bdf8', padding: '10px 12px', borderRadius: '6px', fontSize: '12px', overflowX: 'auto', maxHeight: '180px' }}>
                        <div style={{ fontSize: '10.5px', color: '#94a3b8', marginBottom: '4px', textTransform: 'uppercase' }}>Subtask Output:</div>
                        <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{st.output}</pre>
                      </div>
                    )}

                    {st.error && (
                      <div style={{ background: 'var(--accent-coral-bg)', color: 'var(--accent-coral)', padding: '8px 12px', borderRadius: '6px', fontSize: '12px', marginTop: '6px' }}>
                        <strong>Error: </strong> {st.error}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {showRaw['plan'] && (
              <pre style={{ marginTop: '12px', padding: '12px', background: '#0f172a', color: '#f8fafc', borderRadius: '6px', fontSize: '11.5px', overflowX: 'auto' }}>
                {JSON.stringify(planEvent?.payload || subtaskEvents, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}

      {/* STEP 5: Tool Call Logs & What It Returned (Ground Truth) */}
      {unifiedToolRuns.length > 0 && (
        <div className="card" style={{ margin: 0, borderLeft: '4px solid var(--accent-coral)' }}>
          <div className="card-header">
            <div className="card-title">
              <Wrench size={15} style={{ color: 'var(--accent-coral)' }} />
              <span>Step 5: Tool Execution Ground Truth &amp; Return Logs ({unifiedToolRuns.length})</span>
            </div>
            <button
              className="btn btn-default"
              style={{ padding: '3px 8px', fontSize: '11px' }}
              onClick={() => toggleRaw('all_tools')}
            >
              {showRaw['all_tools'] ? 'Hide Raw' : 'Raw JSON'}
            </button>
          </div>

          <div className="card-body">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {unifiedToolRuns.map((tool, idx) => {
                const hasError = tool.is_error || (tool.exit_code !== undefined && tool.exit_code !== 0);
                const hasReturn = tool.output !== undefined && tool.output !== '';

                return (
                  <div
                    key={idx}
                    style={{
                      background: 'var(--bg-app)',
                      border: '1px solid var(--border-main)',
                      borderRadius: '8px',
                      padding: '14px 16px',
                    }}
                  >
                    {/* Tool Call Header */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Wrench size={13} style={{ color: 'var(--accent-coral)' }} />
                        <strong style={{ fontFamily: 'var(--font-mono)', fontSize: '13.5px', color: 'var(--accent-blue)' }}>
                          {tool.tool_name}
                        </strong>
                        <span className="badge badge-slate mono" style={{ fontSize: '10.5px' }}>
                          {tool.call_id}
                        </span>
                        {tool.agent_name && (
                          <span className="badge badge-lavender" style={{ fontSize: '10.5px' }}>
                            @{tool.agent_name}
                          </span>
                        )}
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {tool.duration_ms !== undefined && (
                          <span className="mono" style={{ fontSize: '12px', fontWeight: 600, color: 'var(--accent-amber)' }}>
                            {tool.duration_ms}ms
                          </span>
                        )}
                        <span className={`badge ${hasError ? 'badge-rose' : 'badge-mint'}`}>
                          {hasError ? 'ERROR' : 'SUCCESS'} (exit: {tool.exit_code ?? 0})
                        </span>
                      </div>
                    </div>

                    {/* Tool Input Arguments */}
                    <div style={{ marginBottom: '10px' }}>
                      <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        Input Arguments:
                      </span>
                      <pre style={{ background: '#ffffff', border: '1px solid var(--border-subtle)', padding: '8px 12px', borderRadius: '6px', fontSize: '12px', marginTop: '4px', overflowX: 'auto', margin: '4px 0 0' }}>
                        {typeof tool.args === 'string' ? tool.args : JSON.stringify(tool.args, null, 2)}
                      </pre>
                    </div>

                    {/* Tool What It Returned */}
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                        <span style={{ fontSize: '11px', fontWeight: 600, color: hasError ? 'var(--accent-coral)' : 'var(--accent-mint)', textTransform: 'uppercase' }}>
                          What It Returned:
                        </span>
                        {hasReturn && (
                          <button
                            className="btn btn-default"
                            style={{ padding: '2px 6px', fontSize: '10.5px' }}
                            onClick={() => copyToClipboard(`tool_ret_${idx}`, tool.output || '')}
                          >
                            {copiedId === `tool_ret_${idx}` ? <Check size={10} color="var(--accent-mint)" /> : <Copy size={10} />}
                            <span>{copiedId === `tool_ret_${idx}` ? 'Copied' : 'Copy Return'}</span>
                          </button>
                        )}
                      </div>

                      <pre
                        style={{
                          background: '#0f172a',
                          color: hasError ? '#fca5a5' : '#38bdf8',
                          padding: '12px',
                          borderRadius: '6px',
                          fontSize: '12px',
                          lineHeight: '1.5',
                          overflowX: 'auto',
                          maxHeight: '260px',
                          margin: 0,
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                        }}
                      >
                        {tool.output || '// Execution in progress or no stdout output returned.'}
                      </pre>
                    </div>
                  </div>
                );
              })}
            </div>

            {showRaw['all_tools'] && (
              <pre style={{ marginTop: '12px', padding: '12px', background: '#0f172a', color: '#f8fafc', borderRadius: '6px', fontSize: '11.5px', overflowX: 'auto' }}>
                {JSON.stringify(unifiedToolRuns, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}

      {/* STEP 6: Planner Reasoning & Thoughts */}
      {thoughts && (
        <div className="card" style={{ margin: 0 }}>
          <div className="card-header">
            <div className="card-title">
              <Brain size={15} style={{ color: 'var(--accent-lavender)' }} />
              <span>Step 6: Reasoning &amp; Internal Monologue (Why the agent chose actions)</span>
              <span className="badge badge-lavender">THOUGHT STREAM</span>
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

      {/* Streamed Tokens / Assistant Response */}
      {(streamedTokens || (isRunning && !thoughts)) && (
        <div className="card" style={{ margin: 0 }}>
          <div className="card-header">
            <div className="card-title">
              <Zap size={15} style={{ color: 'var(--accent-mint)' }} />
              <span>Live Assistant Response Stream</span>
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

      {/* STEP 7: Time Taken & Tokens Used (Telemetry Ground Truth) */}
      {(metrics || record) && (
        <div className="card" style={{ margin: 0 }}>
          <div className="card-header">
            <div className="card-title">
              <Activity size={15} style={{ color: 'var(--accent-blue)' }} />
              <span>Step 7: Time Taken &amp; Tokens Used Ground Truth</span>
              <span className="badge badge-mint">{metrics?.model_name || 'Completed'}</span>
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
            <div className="metric-grid" style={{ marginBottom: '14px' }}>
              <div className="metric-tile">
                <div className="metric-tile-label">Total Execution Time</div>
                <div className="metric-tile-val" style={{ color: 'var(--accent-coral)' }}>
                  {record?.duration_formatted || (metrics?.total_duration_ms ? `${metrics.total_duration_ms}ms` : '-')}
                </div>
              </div>

              <div className="metric-tile">
                <div className="metric-tile-label">Time to First Token (TTFT)</div>
                <div className="metric-tile-val" style={{ color: 'var(--accent-amber)' }}>
                  {metrics?.ttft_ms ? `${metrics.ttft_ms}ms` : '-'}
                </div>
              </div>

              <div className="metric-tile">
                <div className="metric-tile-label">Prompt Tokens (Input)</div>
                <div className="metric-tile-val" style={{ color: 'var(--accent-blue)' }}>
                  {metrics?.prompt_tokens ?? '-'}
                </div>
              </div>

              <div className="metric-tile">
                <div className="metric-tile-label">Completion Tokens (Output)</div>
                <div className="metric-tile-val" style={{ color: 'var(--accent-mint)' }}>
                  {metrics?.completion_tokens ?? '-'}
                </div>
              </div>

              <div className="metric-tile">
                <div className="metric-tile-label">Cached Tokens (KV Hit)</div>
                <div className="metric-tile-val" style={{ color: 'var(--accent-lavender)' }}>
                  {metrics?.cached_tokens ?? 0}
                </div>
              </div>

              <div className="metric-tile">
                <div className="metric-tile-label">Total Tokens</div>
                <div className="metric-tile-val" style={{ color: 'var(--text-main)' }}>
                  {metrics?.prompt_tokens && metrics?.completion_tokens
                    ? metrics.prompt_tokens + metrics.completion_tokens
                    : '-'}
                </div>
              </div>
            </div>

            {/* Token Distribution Visualization */}
            {metrics?.prompt_tokens && metrics?.completion_tokens && (
              <div style={{ marginBottom: '10px' }}>
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
                    title={`Prompt: ${metrics.prompt_tokens}`}
                  />
                  <div
                    style={{
                      width: `${(metrics.completion_tokens / (metrics.prompt_tokens + metrics.completion_tokens)) * 100}%`,
                      background: 'var(--accent-mint)',
                    }}
                    title={`Completion: ${metrics.completion_tokens}`}
                  />
                </div>
              </div>
            )}

            {showRaw['metrics'] && (
              <pre style={{ marginTop: '12px', padding: '12px', background: '#0f172a', color: '#f8fafc', borderRadius: '6px', fontSize: '11.5px', overflowX: 'auto' }}>
                {JSON.stringify(metrics || record?.telemetry, null, 2)}
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
