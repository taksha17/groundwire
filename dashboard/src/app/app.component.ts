import { DatePipe, JsonPipe, NgClass } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';

import { ApiService } from './api.service';
import { AuthService } from './auth.service';
import { DiagramComponent } from './diagram.component';
import { InstrumentsComponent } from './instruments.component';
import { Agent, AuditRecord, Metrics, Run, RunGraph } from './models';
import { ageLabel, lampFor } from './status';

type StripFilter = 'all' | 'held' | 'live' | 'register' | 'instruments';

@Component({
  selector: 'app-root',
  imports: [DatePipe, JsonPipe, NgClass, DiagramComponent, InstrumentsComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthService);
  readonly runs = signal<Run[]>([]);
  readonly selected = signal<Run | null>(null);
  readonly graph = signal<RunGraph | null>(null);
  readonly timeline = signal<AuditRecord[]>([]);
  readonly register = signal<AuditRecord[]>([]);
  readonly agents = signal<Agent[]>([]);
  readonly filter = signal<StripFilter>('all');
  readonly error = signal<string | null>(null);
  readonly busy = signal(false);
  readonly needsAuth = signal(false);
  readonly username = signal<string | null>(null);
  readonly auditAgent = signal('');
  readonly auditOutcome = signal('');
  readonly metrics = signal<Metrics | null>(null);
  readonly lampFor = lampFor;
  readonly ageLabel = ageLabel;
  private timer?: number;

  async ngOnInit(): Promise<void> {
    try {
      await this.auth.handleCallback();
    } catch {
      this.error.set('Sign-in did not complete. Pull Sign in again.');
    }
    this.username.set(this.auth.username());
    await this.refresh();
    this.timer = window.setInterval(() => void this.refresh(true), 2000);
  }

  ngOnDestroy(): void {
    if (this.timer) {
      window.clearInterval(this.timer);
    }
  }

  visibleRuns(): Run[] {
    const filter = this.filter();
    return this.runs().filter((run) => {
      if (filter === 'held') {
        return run.status === 'awaiting_approval';
      }
      if (filter === 'live') {
        return ['planning', 'awaiting_approval', 'executing'].includes(run.status);
      }
      return true;
    });
  }

  async select(run: Run): Promise<void> {
    this.selected.set(run);
    try {
      this.graph.set(await this.api.getGraph(run.id));
      this.timeline.set(await this.api.runAudit(run.id));
    } catch {
      this.error.set('Could not load the interlocking diagram.');
    }
  }

  setFilter(filter: StripFilter): void {
    this.filter.set(filter);
    if (filter === 'register') {
      void this.loadRegister();
    }
    if (filter === 'instruments') {
      void this.loadMetrics();
    }
  }

  async setRoute(): Promise<void> {
    this.busy.set(true);
    this.error.set(null);
    try {
      const agents = await this.api.listAgents();
      const agent = agents[0] ?? (await this.api.registerDemoAgent());
      const run = await this.api.startDemoRun(agent.id);
      this.filter.set('all');
      await this.refresh();
      await this.select(run);
    } catch (err) {
      if (isUnauthorized(err)) {
        this.needsAuth.set(true);
        this.error.set('Sign in before you set a route.');
      } else {
        this.error.set('Could not set a route. Is the control plane up?');
      }
    } finally {
      this.busy.set(false);
    }
  }

  async decide(decision: 'approve' | 'reject'): Promise<void> {
    const run = this.selected();
    if (!run) {
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    try {
      await this.api.decide(run.id, decision);
      await this.refresh();
    } catch {
      this.error.set('The lever did not travel. The run may no longer be held.');
    } finally {
      this.busy.set(false);
    }
  }

  async loadMetrics(): Promise<void> {
    try {
      this.metrics.set(await this.api.metrics());
    } catch (err) {
      if (isUnauthorized(err)) {
        this.needsAuth.set(true);
      }
    }
  }

  async loadRegister(): Promise<void> {
    try {
      const rows = await this.api.listAudit({
        agent_id: this.auditAgent() || undefined,
        outcome: this.auditOutcome() || undefined,
      });
      this.register.set(rows);
    } catch (err) {
      if (isUnauthorized(err)) {
        this.needsAuth.set(true);
      }
    }
  }

  async exportRegister(format: 'json' | 'csv'): Promise<void> {
    const url = this.api.auditExportUrl(format, {
      agent_id: this.auditAgent() || undefined,
      outcome: this.auditOutcome() || undefined,
    });
    const token = this.auth.accessToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const response = await fetch(url, { headers });
    if (!response.ok) {
      this.error.set('Could not pull the occurrence book.');
      return;
    }
    const blob = await response.blob();
    const anchor = document.createElement('a');
    anchor.href = URL.createObjectURL(blob);
    anchor.download = `groundwire-audit.${format}`;
    anchor.click();
    URL.revokeObjectURL(anchor.href);
  }

  login(): void {
    void this.auth.login();
  }

  logout(): void {
    this.auth.logout();
  }

  private async refresh(silent = false): Promise<void> {
    try {
      const me = await this.api.me();
      this.username.set(me.username);
      this.needsAuth.set(false);
      const [runs, agents] = await Promise.all([this.api.listRuns(), this.api.listAgents()]);
      this.runs.set(runs);
      this.agents.set(agents);
      const current = this.selected();
      const next = current ? (runs.find((run) => run.id === current.id) ?? current) : (runs[0] ?? null);
      this.selected.set(next);
      if (this.filter() === 'register') {
        await this.loadRegister();
      } else if (this.filter() === 'instruments') {
        await this.loadMetrics();
      } else if (next) {
        this.graph.set(await this.api.getGraph(next.id));
        this.timeline.set(await this.api.runAudit(next.id));
      } else {
        this.graph.set(null);
        this.timeline.set([]);
      }
      if (!silent) {
        this.error.set(null);
      }
    } catch (err) {
      if (isUnauthorized(err)) {
        this.needsAuth.set(true);
        if (!silent) {
          this.error.set('Sign in to the box. Admin / admin or operator / operator.');
        }
        return;
      }
      if (!silent) {
        this.error.set('No signal from the control plane.');
      }
    }
  }
}

function isUnauthorized(err: unknown): boolean {
  return err instanceof HttpErrorResponse && err.status === 401;
}
