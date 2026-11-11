import React, { useState, useEffect } from 'react';
import { AlignLeft, Copy, Check } from 'lucide-react';

interface JsonEditorProps {
  value: string;
  onChange: (val: string) => void;
}

export const JsonEditor: React.FC<JsonEditorProps> = ({ value, onChange }) => {
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    try {
      if (value.trim()) {
        JSON.parse(value);
      }
      setError(null);
    } catch (e: any) {
      setError(e.message);
    }
  }, [value]);

  const handleFormat = () => {
    try {
      const parsed = JSON.parse(value);
      onChange(JSON.stringify(parsed, null, 2));
      setError(null);
    } catch {
      // ignore
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const target = e.currentTarget;
      const start = target.selectionStart;
      const end = target.selectionEnd;
      const newValue = value.substring(0, start) + '  ' + value.substring(end);
      onChange(newValue);
      setTimeout(() => {
        target.selectionStart = target.selectionEnd = start + 2;
      }, 0);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', marginBottom: '16px' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 12px',
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-main)',
          borderBottom: 'none',
          borderRadius: '8px 8px 0 0',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '11.5px', fontWeight: 600, color: 'var(--text-secondary)' }}>
            Raw Input JSON Payload
          </span>
          {error && <span className="badge badge-rose">Syntax Error</span>}
        </div>

        <div style={{ display: 'flex', gap: '6px' }}>
          <button className="btn btn-default" style={{ padding: '3px 8px', fontSize: '11px' }} onClick={handleFormat} title="Format JSON">
            <AlignLeft size={11} />
            <span>Format</span>
          </button>
          <button className="btn btn-default" style={{ padding: '3px 8px', fontSize: '11px' }} onClick={handleCopy} title="Copy JSON">
            {copied ? <Check size={11} color="var(--accent-mint)" /> : <Copy size={11} />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>
      </div>

      <textarea
        className="editor-textarea"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Enter JSON input parameters..."
        spellCheck={false}
        rows={10}
        style={{
          borderRadius: '0 0 8px 8px',
          border: '1px solid var(--border-main)',
          fontSize: '12.5px',
          fontFamily: 'var(--font-mono)',
          padding: '12px',
          background: '#0f172a',
          color: '#f8fafc',
          lineHeight: '1.6',
        }}
      />

      {error && (
        <div style={{ padding: '8px 12px', background: 'var(--accent-coral-bg)', color: 'var(--accent-coral)', fontSize: '11.5px', borderRadius: '0 0 8px 8px', border: '1px solid var(--accent-coral-border)', borderTop: 'none' }}>
          {error}
        </div>
      )}
    </div>
  );
};
