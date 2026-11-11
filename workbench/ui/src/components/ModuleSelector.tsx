import React from 'react';
import { Module } from '../types';
import { Layers } from 'lucide-react';

interface ModuleSelectorProps {
  modules: Module[];
  selectedId: string;
  onSelect: (mod: Module) => void;
}

export const ModuleSelector: React.FC<ModuleSelectorProps> = ({ modules, selectedId, onSelect }) => {
  const selectedModule = modules.find((m) => m.id === selectedId);
  const categories = Array.from(new Set(modules.map((m) => m.category)));

  return (
    <div style={{ marginBottom: '16px' }}>
      <div className="form-group-label" style={{ marginBottom: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Layers size={14} style={{ color: 'var(--accent-blue)' }} />
          <span>Select Module or Execution Pipeline</span>
        </div>
        {selectedModule && (
          <span className="badge badge-sky">{selectedModule.category}</span>
        )}
      </div>

      <select
        value={selectedId}
        onChange={(e) => {
          const mod = modules.find((m) => m.id === e.target.value);
          if (mod) onSelect(mod);
        }}
        style={{ fontSize: '13.5px', fontWeight: 500, padding: '10px 14px' }}
      >
        {categories.map((cat) => (
          <optgroup key={cat} label={cat}>
            {modules
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
            padding: '8px 12px',
            borderRadius: '6px',
            border: '1px solid var(--border-subtle)',
          }}
        >
          {selectedModule.description}
        </div>
      )}
    </div>
  );
};
