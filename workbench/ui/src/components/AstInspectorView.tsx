import React, { useState, useMemo } from 'react';
import type {
  ASTScanResult,
  ASTMethod,
  Module,
} from '../types';
import {
  RefreshCw,
  Search,
  Package,
  Layers,
  CheckCircle2,
  Play,
  FileCode2,
  ChevronDown,
  ChevronUp,
  Activity,
  Code2,
} from 'lucide-react';

interface AstInspectorViewProps {
  scanResult: ASTScanResult | null;
  loading: boolean;
  onRescan: () => void;
  onOpenInRunner: (method: ASTMethod) => void;
  modules: Module[];
}

export const AstInspectorView: React.FC<AstInspectorViewProps> = ({
  scanResult,
  loading,
  onRescan,
  onOpenInRunner,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPkg, setSelectedPkg] = useState<string>('all');
  const [selectedLayer, setSelectedLayer] = useState<string>('all');
  const [selectedLang, setSelectedLang] = useState<'all' | 'go' | 'python'>('all');
  const [viewTab, setViewTab] = useState<'methods' | 'types'>('methods');
  const [filterCallableOnly, setFilterCallableOnly] = useState(false);
  const [filterIntegratedOnly, setFilterIntegratedOnly] = useState(false);
  const [expandedItems, setExpandedItems] = useState<Record<string, boolean>>({});

  const toggleExpand = (id: string) => {
    setExpandedItems((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const packageNames = useMemo(() => {
    if (!scanResult) return [];
    return Array.from(new Set(scanResult.packages.map((p) => p.name))).sort();
  }, [scanResult]);

  const layerNames = useMemo(() => {
    if (!scanResult) return [];
    const layers = new Set<string>();
    scanResult.packages.forEach((p) => {
      if (p.layer) layers.add(p.layer);
    });
    return Array.from(layers).sort();
  }, [scanResult]);

  const filteredMethods = useMemo(() => {
    if (!scanResult) return [];
    return scanResult.all_methods.filter((m) => {
      if (selectedPkg !== 'all' && m.package !== selectedPkg) return false;
      if (selectedLayer !== 'all' && m.layer !== selectedLayer) return false;
      if (selectedLang !== 'all' && m.language !== selectedLang) return false;
      if (filterCallableOnly && !m.is_callable) return false;
      if (filterIntegratedOnly && !m.has_registered_runner) return false;
      if (!searchQuery) return true;
      const q = searchQuery.toLowerCase();
      return (
        m.name.toLowerCase().includes(q) ||
        m.signature.toLowerCase().includes(q) ||
        (m.receiver && m.receiver.toLowerCase().includes(q)) ||
        m.package.toLowerCase().includes(q) ||
        (m.layer && m.layer.toLowerCase().includes(q)) ||
        m.doc.toLowerCase().includes(q)
      );
    });
  }, [scanResult, selectedPkg, selectedLayer, selectedLang, filterCallableOnly, filterIntegratedOnly, searchQuery]);

  const filteredTypes = useMemo(() => {
    if (!scanResult) return [];
    return scanResult.all_types.filter((t) => {
      if (selectedPkg !== 'all' && t.package !== selectedPkg) return false;
      if (selectedLayer !== 'all' && t.layer !== selectedLayer) return false;
      if (selectedLang !== 'all' && t.language !== selectedLang) return false;
      if (!searchQuery) return true;
      const q = searchQuery.toLowerCase();
      return (
        t.name.toLowerCase().includes(q) ||
        t.package.toLowerCase().includes(q) ||
        (t.layer && t.layer.toLowerCase().includes(q)) ||
        t.kind.toLowerCase().includes(q) ||
        t.doc.toLowerCase().includes(q)
      );
    });
  }, [scanResult, selectedPkg, selectedLayer, selectedLang, searchQuery]);

  if (!scanResult && loading) {
    return (
      <div className="card" style={{ padding: '60px', textAlign: 'center' }}>
        <RefreshCw className="animate-spin" size={32} style={{ color: 'var(--accent-blue)', margin: '0 auto 16px' }} />
        <h3 style={{ fontSize: '16px', fontWeight: 600 }}>Analyzing Codebase AST...</h3>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
          Scanning Go &amp; Python packages, exported structs, classes, and methods...
        </p>
      </div>
    );
  }

  if (!scanResult) {
    return (
      <div className="card" style={{ padding: '40px', textAlign: 'center' }}>
        <p>No AST scan data available.</p>
        <button className="btn btn-primary" onClick={onRescan} style={{ marginTop: '12px' }}>
          <RefreshCw size={14} /> Scan Codebase Now
        </button>
      </div>
    );
  }

  const { summary } = scanResult;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Banner & Hot Detection Status */}
      <div
        className="card"
        style={{
          padding: '20px 24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px',
          background: 'linear-gradient(135deg, rgba(239, 246, 255, 0.7) 0%, rgba(245, 243, 255, 0.7) 100%)',
          borderColor: 'var(--accent-blue-border)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'var(--accent-blue)',
                color: '#fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <FileCode2 size={18} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 style={{ fontSize: '17px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                  AST Codebase Scanner &amp; Auto-Discovery
                </h2>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: '11px',
                    fontWeight: 600,
                    padding: '2px 8px',
                    borderRadius: '12px',
                    background: 'var(--accent-mint-bg)',
                    color: 'var(--accent-mint)',
                    border: '1px solid var(--accent-mint-border)',
                  }}
                >
                  <Activity size={10} /> Live Hot Watcher Active
                </span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                Continuous polyglot AST detection (Go &amp; Python) across Layers 1–7 in <code>{scanResult.root_dir}</code>
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
            Last sync {new Date(scanResult.scanned_at).toLocaleTimeString()}
          </span>
          <button
            className="btn btn-primary"
            onClick={onRescan}
            disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            <span>{loading ? 'Scanning AST...' : 'Rescan Codebase'}</span>
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '12px' }}>
        <div className="card" style={{ padding: '16px 20px', borderLeft: '4px solid var(--accent-blue)' }}>
          <div style={{ fontSize: '11.5px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
            Modules &amp; Packages
          </div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: 'var(--accent-blue)', marginTop: '4px' }}>
            {summary.package_count}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Across source tree
          </div>
        </div>

        <div className="card" style={{ padding: '16px 20px', borderLeft: '4px solid var(--accent-purple)' }}>
          <div style={{ fontSize: '11.5px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
            Source Files
          </div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: 'var(--accent-purple)', marginTop: '4px' }}>
            {summary.file_count}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
            {summary.go_count || 0} Go + {summary.python_count || 0} Python
          </div>
        </div>

        <div className="card" style={{ padding: '16px 20px', borderLeft: '4px solid var(--accent-coral)' }}>
          <div style={{ fontSize: '11.5px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
            Exported Types
          </div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: 'var(--accent-coral)', marginTop: '4px' }}>
            {summary.type_count}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Structs &amp; Classes
          </div>
        </div>

        <div className="card" style={{ padding: '16px 20px', borderLeft: '4px solid var(--accent-amber)' }}>
          <div style={{ fontSize: '11.5px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
            Exported Methods
          </div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: 'var(--accent-amber)', marginTop: '4px' }}>
            {summary.method_count + summary.function_count}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
            {summary.callable_count} callable signatures
          </div>
        </div>

        <div className="card" style={{ padding: '16px 20px', borderLeft: '4px solid var(--accent-mint)' }}>
          <div style={{ fontSize: '11.5px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
            Live Test Adapters
          </div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: 'var(--accent-mint)', marginTop: '4px' }}>
            {summary.integrated_count}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Active in workbench
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="card" style={{ padding: '16px 20px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '14px', alignItems: 'center', justifyContent: 'space-between' }}>
          {/* Search Box */}
          <div style={{ position: 'relative', flex: '1 1 280px', minWidth: '240px' }}>
            <Search
              size={15}
              style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}
            />
            <input
              type="text"
              placeholder="Search methods, classes, layers, signatures, or docstrings..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ paddingLeft: '36px', width: '100%' }}
            />
          </div>

          {/* View Tab Buttons */}
          <div style={{ display: 'inline-flex', background: 'var(--bg-app)', padding: '3px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
            <button
              onClick={() => setViewTab('methods')}
              style={{
                border: 'none',
                background: viewTab === 'methods' ? '#ffffff' : 'transparent',
                color: viewTab === 'methods' ? 'var(--accent-blue)' : 'var(--text-secondary)',
                fontWeight: 600,
                fontSize: '12.5px',
                padding: '6px 14px',
                borderRadius: '6px',
                cursor: 'pointer',
                boxShadow: viewTab === 'methods' ? '0 1px 3px rgba(0,0,0,0.06)' : 'none',
              }}
            >
              Exported Methods ({filteredMethods.length})
            </button>
            <button
              onClick={() => setViewTab('types')}
              style={{
                border: 'none',
                background: viewTab === 'types' ? '#ffffff' : 'transparent',
                color: viewTab === 'types' ? 'var(--accent-blue)' : 'var(--text-secondary)',
                fontWeight: 600,
                fontSize: '12.5px',
                padding: '6px 14px',
                borderRadius: '6px',
                cursor: 'pointer',
                boxShadow: viewTab === 'types' ? '0 1px 3px rgba(0,0,0,0.06)' : 'none',
              }}
            >
              Structs &amp; Classes ({filteredTypes.length})
            </button>
          </div>

          {/* Language Filter */}
          <div style={{ display: 'inline-flex', background: 'var(--bg-app)', padding: '3px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
            <button
              onClick={() => setSelectedLang('all')}
              style={{
                border: 'none',
                background: selectedLang === 'all' ? '#ffffff' : 'transparent',
                color: selectedLang === 'all' ? 'var(--text-primary)' : 'var(--text-secondary)',
                fontWeight: selectedLang === 'all' ? 600 : 400,
                fontSize: '11.5px',
                padding: '4px 10px',
                borderRadius: '6px',
                cursor: 'pointer',
              }}
            >
              All Languages
            </button>
            <button
              onClick={() => setSelectedLang('go')}
              style={{
                border: 'none',
                background: selectedLang === 'go' ? 'var(--accent-blue-bg)' : 'transparent',
                color: selectedLang === 'go' ? 'var(--accent-blue)' : 'var(--text-secondary)',
                fontWeight: selectedLang === 'go' ? 600 : 400,
                fontSize: '11.5px',
                padding: '4px 10px',
                borderRadius: '6px',
                cursor: 'pointer',
              }}
            >
              Go ({summary.go_count || 0})
            </button>
            <button
              onClick={() => setSelectedLang('python')}
              style={{
                border: 'none',
                background: selectedLang === 'python' ? 'var(--accent-amber-bg)' : 'transparent',
                color: selectedLang === 'python' ? 'var(--accent-amber)' : 'var(--text-secondary)',
                fontWeight: selectedLang === 'python' ? 600 : 400,
                fontSize: '11.5px',
                padding: '4px 10px',
                borderRadius: '6px',
                cursor: 'pointer',
              }}
            >
              Python ({summary.python_count || 0})
            </button>
          </div>

          {/* Quick Toggles */}
          {viewTab === 'methods' && (
            <div style={{ display: 'flex', gap: '14px', alignItems: 'center', fontSize: '12px', color: 'var(--text-secondary)' }}>
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={filterCallableOnly}
                  onChange={(e) => setFilterCallableOnly(e.target.checked)}
                />
                Callable Only
              </label>
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={filterIntegratedOnly}
                  onChange={(e) => setFilterIntegratedOnly(e.target.checked)}
                />
                Live Runners Only
              </label>
            </div>
          )}
        </div>

        {/* System Layer Filter Pills */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '14px', alignItems: 'center' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginRight: '4px' }}>
            System Layer:
          </span>
          <button
            onClick={() => setSelectedLayer('all')}
            style={{
              fontSize: '11.5px',
              padding: '3px 10px',
              borderRadius: '16px',
              border: '1px solid',
              borderColor: selectedLayer === 'all' ? 'var(--accent-purple)' : 'var(--border-subtle)',
              background: selectedLayer === 'all' ? 'var(--accent-purple-bg)' : '#ffffff',
              color: selectedLayer === 'all' ? 'var(--accent-purple)' : 'var(--text-secondary)',
              cursor: 'pointer',
              fontWeight: selectedLayer === 'all' ? 600 : 400,
            }}
          >
            All Layers
          </button>
          {layerNames.map((layer) => (
            <button
              key={layer}
              onClick={() => setSelectedLayer(layer)}
              style={{
                fontSize: '11.5px',
                padding: '3px 10px',
                borderRadius: '16px',
                border: '1px solid',
                borderColor: selectedLayer === layer ? 'var(--accent-purple)' : 'var(--border-subtle)',
                background: selectedLayer === layer ? 'var(--accent-purple-bg)' : '#ffffff',
                color: selectedLayer === layer ? 'var(--accent-purple)' : 'var(--text-secondary)',
                cursor: 'pointer',
                fontWeight: selectedLayer === layer ? 600 : 400,
              }}
            >
              {layer}
            </button>
          ))}
        </div>

        {/* Package Filter Pills */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '10px', alignItems: 'center' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginRight: '4px' }}>
            Package:
          </span>
          <button
            onClick={() => setSelectedPkg('all')}
            style={{
              fontSize: '11.5px',
              padding: '2px 8px',
              borderRadius: '16px',
              border: '1px solid',
              borderColor: selectedPkg === 'all' ? 'var(--accent-blue)' : 'var(--border-subtle)',
              background: selectedPkg === 'all' ? 'var(--accent-blue-bg)' : '#ffffff',
              color: selectedPkg === 'all' ? 'var(--accent-blue)' : 'var(--text-secondary)',
              cursor: 'pointer',
              fontWeight: selectedPkg === 'all' ? 600 : 400,
            }}
          >
            All
          </button>
          {packageNames.map((pkg) => (
            <button
              key={pkg}
              onClick={() => setSelectedPkg(pkg)}
              style={{
                fontSize: '11.5px',
                padding: '2px 8px',
                borderRadius: '16px',
                border: '1px solid',
                borderColor: selectedPkg === pkg ? 'var(--accent-blue)' : 'var(--border-subtle)',
                background: selectedPkg === pkg ? 'var(--accent-blue-bg)' : '#ffffff',
                color: selectedPkg === pkg ? 'var(--accent-blue)' : 'var(--text-secondary)',
                cursor: 'pointer',
                fontWeight: selectedPkg === pkg ? 600 : 400,
              }}
            >
              {pkg}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content List */}
      {viewTab === 'methods' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {filteredMethods.length === 0 ? (
            <div className="card" style={{ padding: '36px', textAlign: 'center', color: 'var(--text-secondary)' }}>
              No methods matched the current search or filter criteria.
            </div>
          ) : (
            filteredMethods.map((m) => {
              const isExpanded = !!expandedItems[m.id];
              return (
                <div
                  key={m.id}
                  className="card"
                  style={{
                    padding: '16px 20px',
                    transition: 'all 0.15s ease',
                    borderLeft: m.has_registered_runner
                      ? '4px solid var(--accent-mint)'
                      : m.is_callable
                      ? '4px solid var(--accent-blue)'
                      : '4px solid var(--border-subtle)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
                    <div style={{ flex: '1 1 500px' }}>
                      {/* Meta Tags */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '6px' }}>
                        {/* Language Tag */}
                        <span
                          className={`badge ${m.language === 'python' ? 'badge-amber' : 'badge-sky'}`}
                          style={{ textTransform: 'uppercase', fontWeight: 700 }}
                        >
                          <Code2 size={11} style={{ marginRight: '3px' }} />
                          {m.language}
                        </span>

                        {/* Layer Tag */}
                        {m.layer && (
                          <span className="badge badge-purple" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                            <Layers size={11} /> {m.layer}
                          </span>
                        )}

                        <span className="badge badge-gray" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          <Package size={11} /> {m.package}
                        </span>

                        {m.receiver && (
                          <span className="badge badge-purple" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                            {m.receiver}
                          </span>
                        )}

                        {m.has_registered_runner ? (
                          <span className="badge badge-mint" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                            <CheckCircle2 size={11} /> Live Runner Attached
                          </span>
                        ) : m.is_callable ? (
                          <span className="badge badge-amber" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                            <Play size={11} /> Auto-Registered in Workbench
                          </span>
                        ) : (
                          <span className="badge badge-gray">AST Export</span>
                        )}

                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {m.file_path}:{m.line_number}
                        </span>
                      </div>

                      {/* Signature */}
                      <div
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: '13px',
                          fontWeight: 600,
                          color: 'var(--text-primary)',
                          background: 'var(--bg-app)',
                          padding: '8px 12px',
                          borderRadius: '6px',
                          border: '1px solid var(--border-subtle)',
                          display: 'inline-block',
                          maxWidth: '100%',
                          overflowX: 'auto',
                        }}
                      >
                        {m.signature}
                      </div>

                      {/* Docstring */}
                      {m.doc && (
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '8px', lineHeight: 1.5 }}>
                          {m.doc}
                        </div>
                      )}
                    </div>

                    {/* Action Buttons */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <button
                        className="btn btn-primary"
                        onClick={() => onOpenInRunner(m)}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px', padding: '6px 12px' }}
                      >
                        <Play size={13} fill="currentColor" />
                        <span>Run in Workbench</span>
                      </button>

                      <button
                        className="btn btn-secondary"
                        onClick={() => toggleExpand(m.id)}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '12px', padding: '6px 10px' }}
                      >
                        <span>AST Details</span>
                        {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </button>
                    </div>
                  </div>

                  {/* Expanded AST Details Drawer */}
                  {isExpanded && (
                    <div
                      style={{
                        marginTop: '16px',
                        paddingTop: '14px',
                        borderTop: '1px solid var(--border-subtle)',
                        fontSize: '12px',
                      }}
                    >
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
                        Parameters Breakdown:
                      </div>
                      {m.params.length === 0 ? (
                        <div style={{ color: 'var(--text-muted)' }}>No parameters.</div>
                      ) : (
                        <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '12px' }}>
                          <thead>
                            <tr style={{ background: 'var(--bg-app)', textAlign: 'left', borderBottom: '1px solid var(--border-subtle)' }}>
                              <th style={{ padding: '6px 10px', fontSize: '11px', color: 'var(--text-muted)' }}>Name</th>
                              <th style={{ padding: '6px 10px', fontSize: '11px', color: 'var(--text-muted)' }}>Type</th>
                              <th style={{ padding: '6px 10px', fontSize: '11px', color: 'var(--text-muted)' }}>Required</th>
                              <th style={{ padding: '6px 10px', fontSize: '11px', color: 'var(--text-muted)' }}>JSON Tag</th>
                            </tr>
                          </thead>
                          <tbody>
                            {m.params.map((p, idx) => (
                              <tr key={idx} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{p.name}</td>
                                <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)', color: 'var(--accent-blue)' }}>{p.type}</td>
                                <td style={{ padding: '6px 10px' }}>{p.is_required ? 'Yes' : 'No'}</td>
                                <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{p.json_name || '-'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}

                      {m.returns.length > 0 && (
                        <div>
                          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Return Types: </span>
                          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-purple)' }}>
                            {m.returns.join(', ')}
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      ) : (
        /* Exported Types, Structs & Classes View */
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '14px' }}>
          {filteredTypes.length === 0 ? (
            <div className="card" style={{ padding: '36px', textAlign: 'center', color: 'var(--text-secondary)', gridColumn: '1 / -1' }}>
              No types matched the current filter.
            </div>
          ) : (
            filteredTypes.map((t) => (
              <div key={`${t.package}.${t.name}`} className="card" style={{ padding: '16px 18px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                      <span className={`badge ${t.language === 'python' ? 'badge-amber' : 'badge-sky'}`} style={{ textTransform: 'uppercase', fontWeight: 700 }}>
                        {t.language}
                      </span>
                      <span className="badge badge-gray">{t.package}</span>
                      <span className={`badge ${t.kind === 'struct' || t.kind === 'class' ? 'badge-purple' : 'badge-amber'}`}>{t.kind}</span>
                      {t.layer && <span className="badge badge-purple">{t.layer}</span>}
                    </div>
                    <div style={{ fontSize: '15px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', marginTop: '6px' }}>
                      {t.name}
                    </div>
                  </div>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    :{t.line_number}
                  </span>
                </div>

                {t.doc && (
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '10px', lineHeight: 1.4 }}>
                    {t.doc}
                  </div>
                )}

                {t.methods && t.methods.length > 0 && (
                  <div style={{ background: 'var(--bg-app)', padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--border-subtle)', marginBottom: '8px' }}>
                    <div style={{ fontSize: '10.5px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>
                      Methods ({t.methods.length}):
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                      {t.methods.map((meth, i) => (
                        <span key={i} className="badge badge-gray" style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                          {meth}()
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {t.fields && t.fields.length > 0 && (
                  <div style={{ background: 'var(--bg-app)', padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ fontSize: '10.5px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>
                      Fields ({t.fields.length}):
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                      {t.fields.slice(0, 8).map((f, i) => (
                        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11.5px', fontFamily: 'var(--font-mono)' }}>
                          <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{f.name}</span>
                          <span style={{ color: 'var(--accent-blue)' }}>{f.type}</span>
                        </div>
                      ))}
                      {t.fields.length > 8 && (
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontStyle: 'italic', marginTop: '2px' }}>
                          + {t.fields.length - 8} more fields
                        </div>
                      )}
                    </div>
                  </div>
                )}

                <div style={{ marginTop: '10px', fontSize: '11px', color: 'var(--text-muted)' }}>
                  {t.file_path}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};
