import React, { useState } from 'react';
import { HITLApprovalPrompt } from '../types';
import { AlertTriangle, Check, X } from 'lucide-react';

interface HitlPromptProps {
  prompt: HITLApprovalPrompt;
  onSubmit: (approved: boolean, feedback: string) => void;
}

export const HitlPrompt: React.FC<HitlPromptProps> = ({ prompt, onSubmit }) => {
  const [feedback, setFeedback] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleDecision = (approved: boolean) => {
    setSubmitting(true);
    onSubmit(approved, feedback);
  };

  return (
    <div className="hitl-banner">
      <div className="hitl-header">
        <AlertTriangle size={16} />
        <span>Human-In-The-Loop Approval Required</span>
        <span className="badge badge-amber" style={{ marginLeft: 'auto' }}>
          {prompt.tool_name}
        </span>
      </div>

      <div style={{ fontSize: '12px', color: 'var(--text-main)', marginBottom: '8px' }}>
        {prompt.reason}
      </div>

      {prompt.arguments_json && (
        <div style={{ marginBottom: '10px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginBottom: '3px' }}>
            Requested Arguments:
          </div>
          <pre
            style={{
              background: 'var(--bg-app)',
              padding: '6px 10px',
              borderRadius: '4px',
              fontSize: '11px',
              overflowX: 'auto',
              border: '1px solid var(--border-dim)',
            }}
          >
            {prompt.arguments_json}
          </pre>
        </div>
      )}

      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <input
          type="text"
          placeholder="Optional feedback or rationale..."
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          disabled={submitting}
          style={{ flex: 1, padding: '5px 8px', fontSize: '12px' }}
        />

        <button
          className="btn btn-primary"
          onClick={() => handleDecision(true)}
          disabled={submitting}
        >
          <Check size={14} />
          <span>Approve</span>
        </button>

        <button
          className="btn btn-danger"
          onClick={() => handleDecision(false)}
          disabled={submitting}
        >
          <X size={14} />
          <span>Deny</span>
        </button>
      </div>
    </div>
  );
};
