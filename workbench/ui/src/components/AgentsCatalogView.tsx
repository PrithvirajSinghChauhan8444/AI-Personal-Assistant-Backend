import React, { useState } from 'react';
import { AgentDetail } from '../types';
import { Bot, Wrench, FileText, Search, Copy, Check, ChevronDown, ChevronRight, Cpu } from 'lucide-react';

interface AgentsCatalogViewProps {
  agents: AgentDetail[];
  loading: boolean;
  onRefresh: () => void;
}

export const AgentsCatalogView: React.FC<AgentsCatalogViewProps> = ({
  agents,
  loading,
  onRefresh,
}) => {
  const [search, setSearch] = useState('');
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [expandedPrompts, setExpandedPrompts] = useState<Record<string, boolean>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const togglePrompt = (id: string) => {
    setExpandedPrompts((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const copyToClipboard = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const filteredAgents = agents.filter((ag) => {
    if (!search) return true;
    const q = search.toLowerCase();
    const matchName = ag.display_name.toLowerCase().includes(q) || ag.id.toLowerCase().includes(q);
    const matchDesc = ag.description.toLowerCase().includes(q);
    const matchTools = ag.tools.some((t) => t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q));
    return matchName || matchDesc || matchTools;
  });

  const activeAgent = selectedAgentId
    ? agents.find((a) => a.id === selectedAgentId) || agents[0]
    : agents[0] || null;

  if (loading && agents.length === 0) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
        <Bot size={32} style={{ margin: '0 auto 12px', color: 'var(--accent-blue)', animation: 'spin 2s linear infinite' }} />
        <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-main)' }}>Loading Agent Catalog...</div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Top Banner & Search */}
      <div className="card" style={{ margin: 0 }}>
        <div className="card-header">
          <div className="card-title">
            <Bot size={16} style={{ color: 'var(--accent-lavender)' }} />
            <span>Swarm Agent &amp; Tool Contracts Catalog</span>
            <span className="badge badge-lavender">{agents.length} Agents Registered</span>
          </div>
          <button className="btn btn-default" style={{ padding: '4px 10px', fontSize: '11.5px' }} onClick={onRefresh}>
            Refresh Catalog
          </button>
        </div>

        <div className="card-body" style={{ padding: '14px 18px' }}>
          <div style={{ position: 'relative', width: '100%' }}>
            <Search size={14} style={{ position: 'absolute', left: '12px', top: '12px', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Search agents, capabilities, tools, or descriptions..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ paddingLeft: '34px' }}
            />
          </div>
        </div>
      </div>

      {/* Main 2-Column Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '16px', alignItems: 'start' }}>
        {/* Left List: Agents */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {filteredAgents.map((ag) => {
            const isSelected = activeAgent?.id === ag.id;
            return (
              <div
                key={ag.id}
                onClick={() => setSelectedAgentId(ag.id)}
                className="card"
                style={{
                  margin: 0,
                  padding: '14px 16px',
                  cursor: 'pointer',
                  borderLeft: isSelected ? '4px solid var(--accent-blue)' : '1px solid var(--border-main)',
                  backgroundColor: isSelected ? 'var(--bg-surface-elevated)' : 'var(--bg-surface)',
                  boxShadow: isSelected ? 'var(--shadow-md)' : 'none',
                  transition: 'all 0.15s ease',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span style={{ fontWeight: 700, fontSize: '13.5px', color: isSelected ? 'var(--accent-blue)' : 'var(--text-main)' }}>
                    @{ag.id}
                  </span>
                  <span className="badge badge-slate" style={{ fontSize: '10.5px' }}>
                    {ag.tools.length} Tools
                  </span>
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px', lineHeight: 1.4 }}>
                  {ag.description}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Cpu size={11} style={{ color: 'var(--text-muted)' }} />
                  <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    {ag.model?.default || 'default'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Right Pane: Selected Agent Deep Trace Spec */}
        {activeAgent && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Agent Header Card */}
            <div className="card" style={{ margin: 0 }}>
              <div className="card-header">
                <div className="card-title">
                  <Bot size={16} style={{ color: 'var(--accent-blue)' }} />
                  <span>@{activeAgent.id} &mdash; {activeAgent.display_name}</span>
                </div>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <span className="badge badge-sky">
                    Model: {activeAgent.model?.default || 'gemini-2.5-flash'}
                  </span>
                  {activeAgent.model?.temperature !== undefined && (
                    <span className="badge badge-slate">
                      Temp: {activeAgent.model.temperature}
                    </span>
                  )}
                </div>
              </div>

              <div className="card-body">
                <div style={{ fontSize: '13px', color: 'var(--text-main)', marginBottom: '14px', lineHeight: 1.5 }}>
                  {activeAgent.description}
                </div>

                {activeAgent.routing_rules && activeAgent.routing_rules.length > 0 && (
                  <div style={{ background: 'var(--bg-app)', padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--border-subtle)', marginBottom: '14px' }}>
                    <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase' }}>
                      Routing Triggers:
                    </div>
                    <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                      {activeAgent.routing_rules.map((rule, idx) => (
                        <li key={idx} style={{ marginBottom: '2px' }}>{rule}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>

            {/* System Prompt Section */}
            <div className="card" style={{ margin: 0 }}>
              <div
                className="card-header"
                style={{ cursor: 'pointer' }}
                onClick={() => togglePrompt(activeAgent.id)}
              >
                <div className="card-title">
                  <FileText size={15} style={{ color: 'var(--accent-lavender)' }} />
                  <span>System Prompt &amp; Grounding Persona</span>
                  <span className="badge badge-lavender">BASE TEMPLATE</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {activeAgent.system_prompt && (
                    <button
                      className="btn btn-default"
                      style={{ padding: '3px 8px', fontSize: '11px' }}
                      onClick={(e) => {
                        e.stopPropagation();
                        copyToClipboard('prompt_' + activeAgent.id, activeAgent.system_prompt || '');
                      }}
                    >
                      {copiedId === 'prompt_' + activeAgent.id ? <Check size={11} color="var(--accent-mint)" /> : <Copy size={11} />}
                      <span>{copiedId === 'prompt_' + activeAgent.id ? 'Copied' : 'Copy Prompt'}</span>
                    </button>
                  )}
                  {expandedPrompts[activeAgent.id] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </div>
              </div>

              {expandedPrompts[activeAgent.id] && (
                <div className="card-body">
                  <pre
                    style={{
                      background: '#0f172a',
                      color: '#f8fafc',
                      padding: '14px',
                      borderRadius: '8px',
                      fontSize: '11.5px',
                      lineHeight: '1.6',
                      maxHeight: '400px',
                      overflowY: 'auto',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {activeAgent.system_prompt || '// No static prompt.md file found for this agent.'}
                  </pre>
                </div>
              )}
            </div>

            {/* Available Tools Section */}
            <div className="card" style={{ margin: 0 }}>
              <div className="card-header">
                <div className="card-title">
                  <Wrench size={15} style={{ color: 'var(--accent-coral)' }} />
                  <span>Available Tools Declared for @{activeAgent.id} ({activeAgent.tools.length})</span>
                </div>
              </div>

              <div className="card-body">
                {activeAgent.tools.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text-muted)', fontSize: '12.5px' }}>
                    No specialized tools declared. This agent operates purely through reasoning and synthesis.
                  </div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '10px' }}>
                    {activeAgent.tools.map((t) => {
                      const isHighRisk = t.risk === 'HIGH';
                      const isMedRisk = t.risk === 'MEDIUM';
                      return (
                        <div
                          key={t.name}
                          style={{
                            background: 'var(--bg-app)',
                            border: '1px solid var(--border-subtle)',
                            borderRadius: '8px',
                            padding: '12px 14px',
                            display: 'flex',
                            flexDirection: 'column',
                            justifyContent: 'space-between',
                          }}
                        >
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                              <strong style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', color: 'var(--accent-blue)' }}>
                                {t.name}
                              </strong>
                              <span
                                className={`badge ${isHighRisk ? 'badge-rose' : isMedRisk ? 'badge-amber' : 'badge-mint'}`}
                                style={{ fontSize: '10px' }}
                              >
                                {t.risk || 'LOW'}
                              </span>
                            </div>
                            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px', lineHeight: 1.4 }}>
                              {t.description}
                            </div>
                          </div>

                          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '6px', paddingTop: '6px', borderTop: '1px solid var(--border-subtle)' }}>
                            {t.execution_domain && (
                              <span className="badge badge-slate" style={{ fontSize: '10px' }}>
                                domain: {t.execution_domain}
                              </span>
                            )}
                            {t.required_capability && (
                              <span className="badge badge-sky" style={{ fontSize: '10px' }}>
                                cap: {t.required_capability}
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
