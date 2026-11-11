import React, { useState } from 'react';
import { ModuleSchema } from '../types';
import { ChevronDown, ChevronRight, Eye } from 'lucide-react';

interface SchemaInspectorProps {
  schema: ModuleSchema;
}

export const SchemaInspector: React.FC<SchemaInspectorProps> = ({ schema }) => {
  const [expanded, setExpanded] = useState(false);

  if (!schema || !schema.fields || schema.fields.length === 0) return null;

  return (
    <div style={{ marginBottom: '16px' }}>
      <button
        type="button"
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 12px',
          background: 'var(--bg-app)',
          border: '1px solid var(--border-main)',
          borderRadius: '6px',
          cursor: 'pointer',
          color: 'var(--text-secondary)',
          fontSize: '12px',
          fontWeight: 600,
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <span>Introspected Input Schema: {schema.type_name}</span>
        </div>
        <Eye size={13} style={{ color: 'var(--accent-blue)' }} />
      </button>

      {expanded && (
        <div style={{ marginTop: '8px', maxHeight: '200px', overflowY: 'auto', border: '1px solid var(--border-main)', borderRadius: '6px' }}>
          <table className="schema-table" style={{ background: 'var(--bg-surface-elevated)' }}>
            <thead>
              <tr style={{ background: 'var(--bg-surface)' }}>
                <th>Field</th>
                <th>Type</th>
                <th>Status</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {schema.fields.map((f) => (
                <tr key={f.name}>
                  <td className="mono" style={{ color: 'var(--accent-blue)', fontWeight: 600 }}>
                    {f.name}
                  </td>
                  <td className="mono" style={{ color: 'var(--accent-lavender)', fontSize: '11px' }}>
                    {f.type}
                    {f.enum && f.enum.length > 0 && ` [${f.enum.join('|')}]`}
                  </td>
                  <td>
                    {f.required ? (
                      <span className="badge badge-rose">required</span>
                    ) : (
                      <span className="badge badge-slate">optional</span>
                    )}
                  </td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                    {f.description || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
