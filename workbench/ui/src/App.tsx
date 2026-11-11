import React, { useState, useEffect, useMemo } from 'react';
import {
  Module,
  Preset,
  StreamEvent,
  ExecutionRecord,
  HITLApprovalPrompt,
  APIRequestLog,
  GoLogEntry,
  SystemStats,
} from './types';
import { Header, WorkbenchMode } from './components/Header';
import { ModuleSelector } from './components/ModuleSelector';
import { PresetPicker } from './components/PresetPicker';
import { SchemaInspector } from './components/SchemaInspector';
import { JsonEditor } from './components/JsonEditor';
import { VisualFormBuilder } from './components/VisualFormBuilder';
import { ExecutionControls } from './components/ExecutionControls';
import { ExecutionDashboard } from './components/ExecutionDashboard';
import { LiveStreamViewer } from './components/LiveStreamViewer';
import { FlightRecorderView } from './components/FlightRecorderView';
import { SystemTelemetryViewer } from './components/SystemTelemetryViewer';
import { ApiRequestsViewer } from './components/ApiRequestsViewer';
import { GoLogsViewer } from './components/GoLogsViewer';
import { ResultViewer } from './components/ResultViewer';
import { HitlPrompt } from './components/HitlPrompt';
import { SlidersHorizontal, Code } from 'lucide-react';

export const App: React.FC = () => {
  const [currentMode, setCurrentMode] = useState<WorkbenchMode>('runner');
  const [modules, setModules] = useState<Module[]>([]);
  const [selectedModule, setSelectedModule] = useState<Module | null>(null);
  const [inputPayload, setInputPayload] = useState<string>('{}');
  const [inputMode, setInputMode] = useState<'form' | 'json'>('form');
  const [timeoutSeconds, setTimeoutSeconds] = useState<number>(30);

  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [currentExecutionId, setCurrentExecutionId] = useState<string | null>(null);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [latestRecord, setLatestRecord] = useState<ExecutionRecord | null>(null);
  const [activeHitl, setActiveHitl] = useState<HITLApprovalPrompt | null>(null);

  const [history, setHistory] = useState<ExecutionRecord[]>([]);

  // Telemetry & Logs State
  const [apiRequests, setApiRequests] = useState<APIRequestLog[]>([]);
  const [goLogs, setGoLogs] = useState<GoLogEntry[]>([]);
  const [systemStats, setSystemStats] = useState<SystemStats | null>(null);
  const [telemetryLoading, setTelemetryLoading] = useState<boolean>(false);
  const [streamViewMode, setStreamViewMode] = useState<'dashboard' | 'raw_feed'>('dashboard');

  const parsedFormValues = useMemo(() => {
    try {
      return JSON.parse(inputPayload);
    } catch {
      return {};
    }
  }, [inputPayload]);

  const handleFormChange = (newValues: Record<string, any>) => {
    setInputPayload(JSON.stringify(newValues, null, 2));
  };

  useEffect(() => {
    fetch('/api/modules')
      .then((res) => res.json())
      .then((data: Module[]) => {
        setModules(data);
        if (data.length > 0) {
          handleSelectModule(data[0]);
        }
      })
      .catch((err) => console.error('Failed to load modules:', err));

    loadHistory();
    loadTelemetry();

    const eventSource = new EventSource('/api/telemetry/stream');
    eventSource.onmessage = (e) => {
      try {
        const item = JSON.parse(e.data);
        if (item.type === 'API_LOG') {
          setApiRequests((prev) => [item.data, ...prev.slice(0, 99)]);
        } else if (item.type === 'GO_LOG') {
          setGoLogs((prev) => [item.data, ...prev.slice(0, 199)]);
        }
      } catch (err) {
        console.error('Error parsing telemetry stream event:', err);
      }
    };

    return () => {
      eventSource.close();
    };
  }, []);

  const loadHistory = () => {
    fetch('/api/history')
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) setHistory(data);
      })
      .catch((err) => console.error('Failed to load history:', err));
  };

  const loadTelemetry = () => {
    setTelemetryLoading(true);
    fetch('/api/telemetry')
      .then((res) => res.json())
      .then((data) => {
        if (data.api_requests) setApiRequests(data.api_requests);
        if (data.go_logs) setGoLogs(data.go_logs);
        if (data.system) setSystemStats(data.system);
      })
      .catch((err) => console.error('Failed to load telemetry:', err))
      .finally(() => setTelemetryLoading(false));
  };

  const handleSelectModule = (mod: Module) => {
    setSelectedModule(mod);
    if (mod.presets && mod.presets.length > 0) {
      setInputPayload(JSON.stringify(mod.presets[0].payload, null, 2));
    } else {
      const def: Record<string, any> = {};
      mod.schema?.fields?.forEach((f) => {
        def[f.name] = f.default ?? (f.type.startsWith('[]') ? [] : '');
      });
      setInputPayload(JSON.stringify(def, null, 2));
    }
  };

  const handleSelectPreset = (preset: Preset) => {
    setInputPayload(JSON.stringify(preset.payload, null, 2));
  };

  const handleExecute = async () => {
    if (!selectedModule || isRunning) return;

    let parsedInput: any;
    try {
      parsedInput = JSON.parse(inputPayload);
    } catch {
      alert('Please correct the JSON input payload before executing.');
      return;
    }

    setIsRunning(true);
    setEvents([]);
    setLatestRecord(null);
    setActiveHitl(null);
    setCurrentMode('runner'); // Ensure user is on runner tab when executing

    try {
      const response = await fetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          module_id: selectedModule.id,
          input: parsedInput,
          timeout_seconds: timeoutSeconds,
        }),
      });

      if (!response.body) throw new Error('ReadableStream not supported by browser');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;
          const matchEvent = line.match(/^event: (.*)$/m);
          const matchData = line.match(/^data: (.*)$/m);

          const eventType = matchEvent ? matchEvent[1].trim() : 'message';
          const dataStr = matchData ? matchData[1].trim() : '';

          if (eventType === 'event' && dataStr) {
            try {
              const ev: StreamEvent = JSON.parse(dataStr);
              setEvents((prev) => [...prev, ev]);

              if (ev.type === 'HITL_REQUEST' && ev.payload) {
                setActiveHitl(ev.payload);
              }
            } catch (e) {
              console.error('Error parsing SSE event data:', e);
            }
          } else if (eventType === 'complete' && dataStr) {
            try {
              const rec: ExecutionRecord = JSON.parse(dataStr);
              setLatestRecord(rec);
              setCurrentExecutionId(rec.id);
            } catch (e) {
              console.error('Error parsing complete record:', e);
            }
          }
        }
      }
    } catch (err: any) {
      console.error('Execution stream failed:', err);
    } finally {
      setIsRunning(false);
      loadHistory();
      loadTelemetry();
    }
  };

  const handleAbort = async () => {
    const execId = currentExecutionId || latestRecord?.id;
    await fetch('/api/abort', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ execution_id: execId || '' }),
    });
  };

  const handleHitlSubmit = async (approved: boolean, feedback: string) => {
    if (!activeHitl) return;

    await fetch('/api/hitl', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        request_id: activeHitl.request_id,
        approved: approved,
        user_feedback: feedback,
      }),
    });

    setActiveHitl(null);
  };

  const handleReplayInRunner = (rec: ExecutionRecord) => {
    const targetModule = modules.find((m) => m.id === rec.module_id);
    if (targetModule) setSelectedModule(targetModule);
    setInputPayload(JSON.stringify(rec.input, null, 2));
    setCurrentMode('runner');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleInspectFlightRun = (rec: ExecutionRecord) => {
    setLatestRecord(rec);
    setEvents(rec.events || []);
    setCurrentMode('runner');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="app-container">
      <Header
        currentMode={currentMode}
        onSelectMode={setCurrentMode}
        isRunning={isRunning}
        historyCount={history.length}
        apiCount={apiRequests.length}
        logCount={goLogs.length}
      />

      <main className="page-body">
        {/* MODE 1: WORKBENCH RUNNER */}
        {currentMode === 'runner' && (
          <div className="runner-grid">
            {/* Left Column: Target Module & Input Config */}
            <div>
              {/* Card 1: Module & Presets Selection */}
              <div className="card">
                <div className="card-header">
                  <span className="card-title">1. Target Module &amp; Scenarios</span>
                </div>
                <div className="card-body">
                  <ModuleSelector
                    modules={modules}
                    selectedId={selectedModule?.id || ''}
                    onSelect={handleSelectModule}
                  />

                  {selectedModule && (
                    <>
                      <PresetPicker
                        presets={selectedModule.presets}
                        onSelectPreset={handleSelectPreset}
                      />
                      <SchemaInspector schema={selectedModule.schema} />
                    </>
                  )}
                </div>
              </div>

              {/* Card 2: Interactive Input Payload */}
              <div className="card">
                <div className="card-header">
                  <span className="card-title">2. Input Parameters</span>

                  <div style={{ display: 'flex', gap: '4px' }}>
                    <button
                      className={`pill-btn ${inputMode === 'form' ? 'active' : ''}`}
                      style={{ padding: '4px 10px', fontSize: '11.5px' }}
                      onClick={() => setInputMode('form')}
                    >
                      <SlidersHorizontal size={12} />
                      <span>Visual Form</span>
                    </button>
                    <button
                      className={`pill-btn ${inputMode === 'json' ? 'active' : ''}`}
                      style={{ padding: '4px 10px', fontSize: '11.5px' }}
                      onClick={() => setInputMode('json')}
                    >
                      <Code size={12} />
                      <span>JSON Editor</span>
                    </button>
                  </div>
                </div>

                <div className="card-body" style={{ padding: inputMode === 'form' ? '6px 18px' : '18px' }}>
                  {selectedModule && inputMode === 'form' ? (
                    <VisualFormBuilder
                      module={selectedModule}
                      values={parsedFormValues}
                      onChange={handleFormChange}
                    />
                  ) : (
                    <JsonEditor value={inputPayload} onChange={setInputPayload} />
                  )}

                  <ExecutionControls
                    isRunning={isRunning}
                    onExecute={handleExecute}
                    onAbort={handleAbort}
                    timeoutSeconds={timeoutSeconds}
                    setTimeoutSeconds={setTimeoutSeconds}
                    disabled={!selectedModule}
                  />
                </div>
              </div>
            </div>

            {/* Right Column: Execution Stepper & Flight Output */}
            <div>
              {activeHitl && (
                <HitlPrompt prompt={activeHitl} onSubmit={handleHitlSubmit} />
              )}

              {/* View Mode Toggle Bar */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '12px',
                }}
              >
                <div style={{ fontSize: '12.5px', fontWeight: 700, color: 'var(--text-secondary)' }}>
                  Execution Timeline &amp; Live Telemetry
                </div>

                <div style={{ display: 'flex', gap: '4px' }}>
                  <button
                    className={`pill-btn ${streamViewMode === 'dashboard' ? 'active' : ''}`}
                    style={{ padding: '4px 10px', fontSize: '11.5px' }}
                    onClick={() => setStreamViewMode('dashboard')}
                  >
                    Visual Stepper
                  </button>
                  <button
                    className={`pill-btn ${streamViewMode === 'raw_feed' ? 'active' : ''}`}
                    style={{ padding: '4px 10px', fontSize: '11.5px' }}
                    onClick={() => setStreamViewMode('raw_feed')}
                  >
                    Raw Stream Cards
                  </button>
                </div>
              </div>

              {streamViewMode === 'dashboard' ? (
                <ExecutionDashboard
                  events={events}
                  record={latestRecord}
                  isRunning={isRunning}
                />
              ) : (
                <div className="card" style={{ padding: '16px' }}>
                  <LiveStreamViewer events={events} isRunning={isRunning} />
                </div>
              )}

              <ResultViewer record={latestRecord} />
            </div>
          </div>
        )}

        {/* MODE 2: FLIGHT RECORDER */}
        {currentMode === 'history' && (
          <FlightRecorderView
            history={history}
            onReplay={handleReplayInRunner}
            onInspect={handleInspectFlightRun}
          />
        )}

        {/* MODE 3: SYSTEM TELEMETRY */}
        {currentMode === 'telemetry' && (
          <SystemTelemetryViewer
            system={systemStats}
            onRefresh={loadTelemetry}
            loading={telemetryLoading}
          />
        )}

        {/* MODE 4: API NETWORK INSPECTOR */}
        {currentMode === 'apireqs' && (
          <ApiRequestsViewer requests={apiRequests} />
        )}

        {/* MODE 5: GO SYSTEM LOGS */}
        {currentMode === 'gologs' && (
          <GoLogsViewer logs={goLogs} />
        )}
      </main>
    </div>
  );
};
