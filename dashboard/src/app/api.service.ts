import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { Agent, AuditRecord, Identity, Metrics, Run, RunGraph } from './models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  listRuns(status?: string): Promise<Run[]> {
    const params = status ? { status } : undefined;
    return firstValueFrom(this.http.get<Run[]>('/v1/runs', { params }));
  }

  getRun(id: string): Promise<Run> {
    return firstValueFrom(this.http.get<Run>(`/v1/runs/${id}`));
  }

  getGraph(id: string): Promise<RunGraph> {
    return firstValueFrom(this.http.get<RunGraph>(`/v1/runs/${id}/graph`));
  }

  listAgents(): Promise<Agent[]> {
    return firstValueFrom(this.http.get<Agent[]>('/v1/agents'));
  }

  registerDemoAgent(): Promise<Agent> {
    return firstValueFrom(
      this.http.post<Agent>('/v1/agents', {
        name: 'demo-ops-agent',
        allowed_tools: ['send_email'],
        approval_policy: { require_approval_for: ['send_email'] },
      }),
    );
  }

  startDemoRun(agentId: string): Promise<Run> {
    return firstValueFrom(
      this.http.post<Run>('/v1/runs', {
        agent_id: agentId,
        payload: {
          to: 'ops@example.com',
          subject: 'Outage',
          body: 'Please page on-call.',
        },
      }),
    );
  }

  decide(runId: string, decision: 'approve' | 'reject'): Promise<Run> {
    return firstValueFrom(
      this.http.post<Run>(`/v1/runs/${runId}/approvals`, {
        decision,
        actor: 'signal-box',
      }),
    );
  }

  metrics(): Promise<Metrics> {
    return firstValueFrom(this.http.get<Metrics>('/v1/metrics'));
  }

  me(): Promise<Identity> {
    return firstValueFrom(this.http.get<Identity>('/v1/me'));
  }

  listAudit(params?: {
    agent_id?: string;
    outcome?: string;
    since?: string;
    until?: string;
  }): Promise<AuditRecord[]> {
    const query: Record<string, string> = {};
    if (params?.agent_id) {
      query['agent_id'] = params.agent_id;
    }
    if (params?.outcome) {
      query['outcome'] = params.outcome;
    }
    if (params?.since) {
      query['since'] = params.since;
    }
    if (params?.until) {
      query['until'] = params.until;
    }
    return firstValueFrom(this.http.get<AuditRecord[]>('/v1/audit', { params: query }));
  }

  runAudit(runId: string): Promise<AuditRecord[]> {
    return firstValueFrom(this.http.get<AuditRecord[]>(`/v1/runs/${runId}/audit`));
  }

  auditExportUrl(format: 'json' | 'csv', params?: { agent_id?: string; outcome?: string }): string {
    const search = new URLSearchParams({ format });
    if (params?.agent_id) {
      search.set('agent_id', params.agent_id);
    }
    if (params?.outcome) {
      search.set('outcome', params.outcome);
    }
    return `/v1/audit?${search.toString()}`;
  }
}
