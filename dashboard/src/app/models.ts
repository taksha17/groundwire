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
