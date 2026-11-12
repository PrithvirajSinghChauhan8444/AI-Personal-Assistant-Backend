export interface FieldSchema {
  name: string;
  type: string;
  required: boolean;
  description?: string;
  enum?: string[];
  default?: any;
  fields?: FieldSchema[];
}

export interface ModuleSchema {
  type_name: string;
  fields: FieldSchema[];
}

export interface Preset {
  id: string;
  name: string;
  category: string;
  description: string;
  payload: any;
}

export interface Module {
  id: string;
  name: string;
  tier?: 'LAYER_BENCH' | 'COMPONENT' | 'GRANULAR_AST';
  layer?: 'pipeline' | 'layer1' | 'layer2' | 'layer3' | 'layer4' | 'layer5' | 'layer6' | 'layer7' | 'system';
  category: string;
  description: string;
  schema: ModuleSchema;
  presets: Preset[];
}

export interface StreamEvent {
  index: number;
  timestamp: string;
  type: string;
  agent_name?: string;
  payload?: any;
  raw?: string;
}

export interface GoLogEntry {
  timestamp: string;
  level: string; // DEBUG, INFO, WARN, ERROR
  source: string;
  execution_id?: string;
  trace_id?: string;
  message: string;
  fields?: Record<string, any>;
}

export interface APIRequestLog {
  id: string;
  timestamp: string;
  method: string;
  path: string;
  status: number;
  duration_us: number;
  duration_formatted: string;
  client_ip: string;
  bytes_received: number;
  bytes_sent: number;
  trace_id: string;
  request_body?: string;
  response_body?: string;
}

export interface RuntimeTelemetry {
  trace_id: string;
  span_id: string;
  goroutines_start: number;
  goroutines_end: number;
  goroutine_delta: number;
  mem_alloc_start_bytes: number;
  mem_alloc_end_bytes: number;
  mem_delta_bytes: number;
  num_gc: number;
}

export interface SystemStats {
  goroutines: number;
  mem_alloc_mb: number;
  mem_total_mb: number;
  mem_sys_mb: number;
  num_gc: number;
  num_cpu: number;
}

export interface ExecutionRecord {
  id: string;
  module_id: string;
  module_name: string;
  category: string;
  started_at: string;
  completed_at: string;
  duration_us: number;
  duration_formatted: string;
  input: any;
  events: StreamEvent[];
  logs?: GoLogEntry[];
  telemetry?: RuntimeTelemetry;
  output?: any;
  error?: string;
  panic?: string;
  aborted: boolean;
  status: 'SUCCESS' | 'ERROR' | 'PANIC' | 'ABORTED' | 'RUNNING';
}

export interface HITLApprovalPrompt {
  request_id: string;
  tool_name: string;
  reason: string;
  arguments_json: string;
  available_choices?: string[];
}

export interface ASTField {
  name: string;
  type: string;
  tag?: string;
  json_name?: string;
  doc?: string;
  is_exported: boolean;
  is_required: boolean;
}

export interface ASTMethod {
  id: string;
  name: string;
  package: string;
  layer: string;
  language: 'go' | 'python';
  receiver?: string;
  receiver_raw?: string;
  signature: string;
  doc: string;
  params: ASTField[];
  returns: string[];
  file_path: string;
  line_number: number;
  is_callable: boolean;
  has_registered_runner: boolean;
  registered_module_id?: string;
}

export interface ASTType {
  name: string;
  package: string;
  layer: string;
  language: 'go' | 'python';
  kind: string;
  doc: string;
  fields?: ASTField[];
  methods?: string[];
  file_path: string;
  line_number: number;
  is_exported: boolean;
}

export interface ASTPackage {
  name: string;
  rel_path: string;
  layer: string;
  language: 'go' | 'python';
  doc: string;
  files: string[];
  types: ASTType[];
  methods: ASTMethod[];
  functions: ASTMethod[];
}

export interface ASTScanSummary {
  package_count: number;
  file_count: number;
  type_count: number;
  method_count: number;
  function_count: number;
  callable_count: number;
  integrated_count: number;
  go_count?: number;
  python_count?: number;
  layers?: Record<string, number>;
}

export interface ASTScanResult {
  scanned_at: string;
  root_dir: string;
  packages: ASTPackage[];
  all_methods: ASTMethod[];
  all_types: ASTType[];
  summary: ASTScanSummary;
}

