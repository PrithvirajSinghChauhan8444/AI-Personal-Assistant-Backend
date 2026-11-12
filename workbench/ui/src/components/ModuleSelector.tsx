import React, { useState, useMemo, useEffect } from 'react';
import { Module } from '../types';
import { Layers, Sparkles, Cpu, CheckCircle2, Filter } from 'lucide-react';

interface ModuleSelectorProps {
  modules: Module[];
  selectedId: string;
  onSelect: (mod: Module) => void;
}

export const ModuleSelector: React.FC<ModuleSelectorProps> = ({ modules, selectedId, onSelect }) => {
  const [selectedLayer, setSelectedLayer] = useState<string>('all');
  const [showGranularAST, setShowGranularAST] = useState<boolean>(false);

  const selectedModule = modules.find((m) => m.id === selectedId);

  // Filter modules based on selected layer and whether granular AST items are visible
  const filteredModules = useMemo(() => {
    return modules.filter((m) => {
      const isGranular = m.tier === 'GRANULAR_AST' || m.category.startsWith('AST:');

      // By default hide granular AST unless toggle is on
      if (!showGranularAST && isGranular) {
        return false;
      }

      // Filter by layer
      if (selectedLayer !== 'all') {
        if (selectedLayer === 'pipeline') {
          return m.layer === 'pipeline' || m.id.includes('pipeline');
        }
        if (selectedLayer === 'layer1') {
          return m.layer === 'layer1' || m.id.startsWith('l1_') || m.id.includes('gateway');
        }
        if (selectedLayer === 'layer2') {
          return m.layer === 'layer2' || m.id.startsWith('l2_') || m.id.includes('orchestrator') || m.id.includes('safety') || m.id.includes('session');
        }
        if (selectedLayer === 'layer3') {
          return m.layer === 'layer3' || m.id.startsWith('l3_') || m.id.includes('tool');
        }
        if (selectedLayer === 'layer4') {
          return m.layer === 'layer4' || m.id.startsWith('l4_') || m.id.includes('bridge');
        }
        if (selectedLayer === 'layer6') {
          return m.layer === 'layer6' || m.id.startsWith('l6_') || m.id.includes('agent');
        }
        if (selectedLayer === 'layer7') {
          return m.layer === 'layer7' || m.id.startsWith('l7_') || m.id.includes('model') || m.id.includes('provider');
        }
      }

      return true;
    });
  }, [modules, selectedLayer, showGranularAST]);

  // Keep selection valid when filters change
  useEffect(() => {
    if (filteredModules.length > 0) {
      const isCurrentValid = filteredModules.some((m) => m.id === selectedId);
      if (!isCurrentValid) {
        onSelect(filteredModules[0]);
      }
    }
  }, [filteredModules, selectedId, onSelect]);

  const categories = useMemo(() => {
    return Array.from(new Set(filteredModules.map((m) => m.category)));
  }, [filteredModules]);

  const layerBenchCount = modules.filter((m) => m.tier === 'LAYER_BENCH' || (!m.category.startsWith('AST:') && (m.id.startsWith('pipeline') || m.id.startsWith('l1_') || m.id.startsWith('l2_') || m.id.startsWith('l3_') || m.id.startsWith('l6_')))).length;
  const granularCount = modules.filter((m) => m.tier === 'GRANULAR_AST' || m.category.startsWith('AST:')).length;

  return (
    <div style={{ marginBottom: '18px' }}>
      {/* Layer Navigation Tabs */}
      <div style={{ marginBottom: '10px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.04em' }}>
            System Layer Filter
          </span>
          <button
            type="button"
            onClick={() => setShowGranularAST(!showGranularAST)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '11px',
              padding: '2px 8px',
              borderRadius: '12px',
              border: '1px solid',
              borderColor: showGranularAST ? 'var(--accent-purple)' : 'var(--border-subtle)',
              background: showGranularAST ? 'var(--accent-purple-bg)' : '#ffffff',
              color: showGranularAST ? 'var(--accent-purple)' : 'var(--text-muted)',
              cursor: 'pointer',
              fontWeight: 500,
            }}
          >
            <Filter size={11} />
            <span>{showGranularAST ? `Hiding AST Noise (${granularCount})` : `Show Granular AST (${granularCount})`}</span>
          </button>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
          <button
            type="button"
            onClick={() => setSelectedLayer('all')}
            style={{
              fontSize: '11.5px',
              padding: '4px 10px',
              borderRadius: '6px',
              border: '1px solid',
              borderColor: selectedLayer === 'all' ? 'var(--accent-blue)' : 'var(--border-subtle)',
              background: selectedLayer === 'all' ? 'var(--accent-blue-bg)' : '#ffffff',
              color: selectedLayer === 'all' ? 'var(--accent-blue)' : 'var(--text-secondary)',
              cursor: 'pointer',
              fontWeight: selectedLayer === 'all' ? 700 : 500,
            }}
          >
            ⭐ All Layers ({layerBenchCount})
          </button>
          <button
            type="button"
            onClick={() => setSelectedLayer('pipeline')}
            style={{
              fontSize: '11.5px',
              padding: '4px 10px',
              borderRadius: '6px',
              border: '1px solid',
              borderColor: selectedLayer === 'pipeline' ? 'var(--accent-purple)' : 'var(--border-subtle)',
              background: selectedLayer === 'pipeline' ? 'var(--accent-purple-bg)' : '#ffffff',
              color: selectedLayer === 'pipeline' ? 'var(--accent-purple)' : 'var(--text-secondary)',
              cursor: 'pointer',
              fontWeight: selectedLayer === 'pipeline' ? 700 : 500,
            }}
          >
            E2E Pipeline
          </button>
          <button
            type="button"
            onClick={() => setSelectedLayer('layer1')}
            style={{
              fontSize: '11.5px',
              padding: '4px 10px',
              borderRadius: '6px',
              border: '1px solid',
              borderColor: selectedLayer === 'layer1' ? 'var(--accent-blue)' : 'var(--border-subtle)',
              background: selectedLayer === 'layer1' ? 'var(--accent-blue-bg)' : '#ffffff',
              color: selectedLayer === 'layer1' ? 'var(--accent-blue)' : 'var(--text-secondary)',
              cursor: 'pointer',
              fontWeight: selectedLayer === 'layer1' ? 700 : 500,
            }}
          >
            L1: Gateway
          </button>
          <button
            type="button"
            onClick={() => setSelectedLayer('layer2')}
            style={{
              fontSize: '11.5px',
              padding: '4px 10px',
              borderRadius: '6px',
              border: '1px solid',
              borderColor: selectedLayer === 'layer2' ? 'var(--accent-mint)' : 'var(--border-subtle)',
              background: selectedLayer === 'layer2' ? 'var(--accent-mint-bg)' : '#ffffff',
              color: selectedLayer === 'layer2' ? 'var(--accent-mint)' : 'var(--text-secondary)',
              cursor: 'pointer',
              fontWeight: selectedLayer === 'layer2' ? 700 : 500,
            }}
          >
            L2: Orchestrator
          </button>
          <button
            type="button"
            onClick={() => setSelectedLayer('layer3')}
            style={{
              fontSize: '11.5px',
              padding: '4px 10px',
              borderRadius: '6px',
              border: '1px solid',
              borderColor: selectedLayer === 'layer3' ? 'var(--accent-coral)' : 'var(--border-subtle)',
              background: selectedLayer === 'layer3' ? 'var(--accent-coral-bg)' : '#ffffff',
              color: selectedLayer === 'layer3' ? 'var(--accent-coral)' : 'var(--text-secondary)',
              cursor: 'pointer',
              fontWeight: selectedLayer === 'layer3' ? 700 : 500,
            }}
          >
            L3: Tools
          </button>
          <button
            type="button"
            onClick={() => setSelectedLayer('layer4')}
            style={{
              fontSize: '11.5px',
              padding: '4px 10px',
              borderRadius: '6px',
              border: '1px solid',
              borderColor: selectedLayer === 'layer4' ? 'var(--accent-teal)' : 'var(--border-subtle)',
              background: selectedLayer === 'layer4' ? 'var(--accent-teal-bg)' : '#ffffff',
              color: selectedLayer === 'layer4' ? 'var(--accent-teal)' : 'var(--text-secondary)',
              cursor: 'pointer',
              fontWeight: selectedLayer === 'layer4' ? 700 : 500,
            }}
          >
            L4: Bridge
          </button>
          <button
            type="button"
            onClick={() => setSelectedLayer('layer6')}
            style={{
              fontSize: '11.5px',
              padding: '4px 10px',
              borderRadius: '6px',
              border: '1px solid',
              borderColor: selectedLayer === 'layer6' ? 'var(--accent-amber)' : 'var(--border-subtle)',
              background: selectedLayer === 'layer6' ? 'var(--accent-amber-bg)' : '#ffffff',
              color: selectedLayer === 'layer6' ? 'var(--accent-amber)' : 'var(--text-secondary)',
              cursor: 'pointer',
              fontWeight: selectedLayer === 'layer6' ? 700 : 500,
            }}
          >
            L6: Agents
          </button>
        </div>
      </div>

      {/* Target Module Dropdown */}
      <div className="form-group-label" style={{ marginBottom: '6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Layers size={14} style={{ color: 'var(--accent-blue)' }} />
          <span>Active Test Bench Module ({filteredModules.length})</span>
        </div>
        {selectedModule && (
          <div style={{ display: 'flex', gap: '6px' }}>
            {selectedModule.tier === 'LAYER_BENCH' && (
              <span className="badge badge-mint" style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                <CheckCircle2 size={10} /> Full Layer Bench
              </span>
            )}
            <span className="badge badge-sky">{selectedModule.category}</span>
          </div>
        )}
      </div>

      <select
        value={selectedId}
        onChange={(e) => {
          const mod = modules.find((m) => m.id === e.target.value);
          if (mod) onSelect(mod);
        }}
        style={{ fontSize: '13.5px', fontWeight: 600, padding: '10px 14px', width: '100%', borderRadius: '8px' }}
      >
        {categories.map((cat) => (
          <optgroup key={cat} label={cat}>
            {filteredModules
              .filter((m) => m.category === cat)
              .map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
          </optgroup>
        ))}
      </select>

      {selectedModule && (
        <div
          style={{
            marginTop: '8px',
            fontSize: '12px',
            color: 'var(--text-secondary)',
            background: 'var(--bg-app)',
            padding: '10px 14px',
            borderRadius: '8px',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '8px',
          }}
        >
          <span style={{ flex: 1, lineHeight: 1.4 }}>{selectedModule.description}</span>
          {selectedModule.tier === 'LAYER_BENCH' ? (
            <span className="badge badge-mint" style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', whiteSpace: 'nowrap' }}>
              <Sparkles size={11} /> Primary Bench
            </span>
          ) : selectedModule.category.startsWith('AST:') ? (
            <span className="badge badge-purple" style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', whiteSpace: 'nowrap' }}>
              <Cpu size={11} /> AST Function
            </span>
          ) : (
            <span className="badge badge-sky" style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', whiteSpace: 'nowrap' }}>
              <Layers size={11} /> Component
            </span>
          )}
        </div>
      )}
    </div>
  );
};
