import React from 'react';
import { Preset } from '../types';
import { Zap } from 'lucide-react';

interface PresetPickerProps {
  presets: Preset[];
  onSelectPreset: (preset: Preset) => void;
}

export const PresetPicker: React.FC<PresetPickerProps> = ({ presets, onSelectPreset }) => {
  if (!presets || presets.length === 0) return null;

  return (
    <div style={{ marginBottom: '16px' }}>
      <div className="form-group-label" style={{ marginBottom: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Zap size={14} style={{ color: 'var(--accent-amber)' }} />
          <span>Preset Scenarios &amp; Boundary Payloads</span>
        </div>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Click to Load</span>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
        {presets.map((p) => {
          let badgeClass = 'badge badge-slate';
          if (p.category === 'Security' || p.category === 'Violation') {
            badgeClass = 'badge badge-rose';
          } else if (p.category === 'HITL') {
            badgeClass = 'badge badge-amber';
          } else if (p.category === 'Happy Path') {
            badgeClass = 'badge badge-mint';
          } else if (p.category === 'Agent Targeting') {
            badgeClass = 'badge badge-sky';
          }

          return (
            <button
              key={p.id}
              type="button"
              className={badgeClass}
              style={{
                cursor: 'pointer',
                padding: '6px 10px',
                fontSize: '11.5px',
                borderRadius: '6px',
                transition: 'all 0.15s ease',
              }}
              onClick={() => onSelectPreset(p)}
              title={p.description}
            >
              {p.name}
            </button>
          );
        })}
      </div>
    </div>
  );
};
