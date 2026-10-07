import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { Agent, Run, RunGraph } from './models';

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
}
