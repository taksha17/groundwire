export interface Run {
  id: string;
  agent_definition_id: string;
  agent_version: number;
  temporal_workflow_id: string;
  status: string;
  payload: Record<string, unknown>;
  pending_action: PendingAction | null;
  current_step: string | null;
  created_at: string | null;
  agent_name: string | null;
}

export interface PendingAction {
  tool: string;
  params: Record<string, unknown>;
  rationale: string;
  model?: string;
  estimated_cost_usd?: number;
}

export interface GraphNode {
  id: string;
  type: string;
  name: string;
  status: string;
  detail: PendingAction | null;
}

export interface GraphEdge {
  source: string;
  target: string;
}

export interface RunGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface Agent {
  id: string;
  name: string;
  allowed_tools: string[];
  version: number;
}

export interface Identity {
  subject: string;
  username: string;
  tenant_id: string;
  roles: string[];
}

export interface Metrics {
  runs: number;
  completed: number;
  rejected: number;
  failed: number;
  success_rate: number;
  avg_duration_seconds: number;
  avg_approval_seconds: number;
  cost_per_run: number;
}

export interface AuditRecord {
  id: string;
  tenant_id: string;
  run_id: string;
  agent_id: string | null;
  event_type: string;
  actor: string;
  payload: Record<string, unknown>;
  created_at: string | null;
  outcome: string | null;
}
