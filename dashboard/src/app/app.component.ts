import { JsonPipe, NgClass } from '@angular/common';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';

import { ApiService } from './api.service';
import { DiagramComponent } from './diagram.component';
import { Run, RunGraph } from './models';
import { ageLabel, lampFor } from './status';

type StripFilter = 'all' | 'held' | 'live';

@Component({
  selector: 'app-root',
  imports: [JsonPipe, NgClass, DiagramComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  readonly runs = signal<Run[]>([]);
  readonly selected = signal<Run | null>(null);
  readonly graph = signal<RunGraph | null>(null);
  readonly filter = signal<StripFilter>('all');
  readonly error = signal<string | null>(null);
  readonly busy = signal(false);
  readonly lampFor = lampFor;
  readonly ageLabel = ageLabel;
  private timer?: number;

  ngOnInit(): void {
    void this.refresh();
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
    } catch {
      this.error.set('Could not load the interlocking diagram.');
    }
  }

  setFilter(filter: StripFilter): void {
    this.filter.set(filter);
  }

  async setRoute(): Promise<void> {
    this.busy.set(true);
    this.error.set(null);
    try {
      const agents = await this.api.listAgents();
      const agent = agents[0] ?? (await this.api.registerDemoAgent());
      const run = await this.api.startDemoRun(agent.id);
      await this.refresh();
      await this.select(run);
    } catch {
      this.error.set('Could not set a route. Is the control plane up?');
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

  private async refresh(silent = false): Promise<void> {
    try {
      const runs = await this.api.listRuns();
      this.runs.set(runs);
      const current = this.selected();
      const next = current ? (runs.find((run) => run.id === current.id) ?? current) : (runs[0] ?? null);
      this.selected.set(next);
      if (next) {
        this.graph.set(await this.api.getGraph(next.id));
      } else {
        this.graph.set(null);
      }
      if (!silent) {
        this.error.set(null);
      }
    } catch {
      if (!silent) {
        this.error.set('No signal from the control plane.');
      }
    }
  }
}
