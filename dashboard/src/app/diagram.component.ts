import {
  Component,
  ElementRef,
  OnDestroy,
  effect,
  input,
  output,
  viewChild,
} from '@angular/core';
import * as d3 from 'd3';

import { RunGraph } from './models';
import { lampFor } from './status';

@Component({
  selector: 'app-diagram',
  template: `
    <svg #canvas class="diagram" role="img" [attr.aria-label]="label()"></svg>
  `,
  styles: [
    `
      :host {
        display: block;
        height: 100%;
        min-height: 22rem;
      }
      .diagram {
        width: 100%;
        height: 100%;
        display: block;
      }
    `,
  ],
})
export class DiagramComponent implements OnDestroy {
  readonly graph = input<RunGraph | null>(null);
  readonly label = input('Interlocking diagram');
  readonly decide = output<'approve' | 'reject'>();
  private readonly canvas = viewChild<ElementRef<SVGSVGElement>>('canvas');
  private resize?: ResizeObserver;

  constructor() {
    effect(() => {
      this.graph();
      this.draw();
    });
  }

  ngOnDestroy(): void {
    this.resize?.disconnect();
  }

  private draw(): void {
    const el = this.canvas()?.nativeElement;
    const graph = this.graph();
    if (!el) {
      return;
    }
    if (!this.resize) {
      this.resize = new ResizeObserver(() => this.draw());
      this.resize.observe(el);
    }
    const svg = d3.select(el);
    svg.selectAll('*').remove();
    const width = el.clientWidth || 640;
    const height = el.clientHeight || 360;
    svg.attr('viewBox', `0 0 ${width} ${height}`);

    if (!graph || graph.nodes.length === 0) {
      svg
        .append('text')
        .attr('x', width / 2)
        .attr('y', height / 2)
        .attr('text-anchor', 'middle')
        .attr('fill', '#D9D4C6')
        .attr('font-family', '"Archivo Narrow", sans-serif')
        .attr('font-size', 18)
        .attr('letter-spacing', '0.08em')
        .text('SELECT A ROUTE');
      return;
    }

    const pad = 72;
    const nodeW = 148;
    const nodeH = 88;
    const xs = d3
      .scalePoint<string>()
      .domain(graph.nodes.map((n) => n.id))
      .range([pad, width - pad])
      .padding(0.4);
    const y = height / 2;

    const track = d3.line<[number, number]>().curve(d3.curveBasis);
    for (const edge of graph.edges) {
      const x1 = xs(edge.source) ?? pad;
      const x2 = xs(edge.target) ?? pad;
      svg
        .append('path')
        .attr(
          'd',
          track([
            [x1 + nodeW / 2, y],
            [(x1 + x2) / 2, y],
            [x2 - nodeW / 2, y],
          ])!,
        )
        .attr('fill', 'none')
        .attr('stroke', '#6E7A6A')
        .attr('stroke-width', 6)
        .attr('stroke-linecap', 'square');
    }

    for (const node of graph.nodes) {
      const x = (xs(node.id) ?? pad) - nodeW / 2;
      const g = svg.append('g').attr('transform', `translate(${x},${y - nodeH / 2})`);
      g.append('rect')
        .attr('width', nodeW)
        .attr('height', nodeH)
        .attr('rx', 2)
        .attr('fill', '#151C16')
        .attr('stroke', '#D9D4C6')
        .attr('stroke-width', 1.5);
      const lamp = lampFor(node.status);
      const color =
        lamp === 'danger' ? '#8B1E1E' : lamp === 'amber' ? '#C45C26' : lamp === 'clear' ? '#3F7A52' : '#4A5248';
      const glass = g
        .append('circle')
        .attr('cx', 22)
        .attr('cy', 24)
        .attr('r', 10)
        .attr('fill', color)
        .attr('stroke', '#D9D4C6')
        .attr('stroke-width', 1);
      if (node.status === 'awaiting_approval') {
        glass.append('title').text('Held at danger');
        glass
          .append('animate')
          .attr('attributeName', 'opacity')
          .attr('values', '1;0.45;1')
          .attr('dur', '1.6s')
          .attr('repeatCount', 'indefinite');
      }
      g.append('text')
        .attr('x', 40)
        .attr('y', 22)
        .attr('fill', '#D9D4C6')
        .attr('font-family', '"Archivo Narrow", sans-serif')
        .attr('font-size', 11)
        .attr('letter-spacing', '0.14em')
        .text(node.type.replace('_', ' ').toUpperCase());
      g.append('text')
        .attr('x', 40)
        .attr('y', 42)
        .attr('fill', '#D9D4C6')
        .attr('font-family', '"Archivo Narrow", sans-serif')
        .attr('font-size', 16)
        .attr('font-weight', 600)
        .text(node.name);
      g.append('text')
        .attr('x', 22)
        .attr('y', 72)
        .attr('fill', '#C45C26')
        .attr('font-family', '"Archivo Narrow", sans-serif')
        .attr('font-size', 12)
        .attr('letter-spacing', '0.08em')
        .text(node.status.replace('_', ' '));

      if (node.status === 'awaiting_approval') {
        const levers = g.append('g').attr('transform', `translate(12, ${nodeH + 14})`);
        this.drawLever(levers, 0, 'APPROVE', 'approve');
        this.drawLever(levers, 72, 'REJECT', 'reject');
      }
    }
  }

  private drawLever(
    parent: d3.Selection<SVGGElement, unknown, null, undefined>,
    x: number,
    label: string,
    decision: 'approve' | 'reject',
  ): void {
    const btn = parent.append('g').attr('transform', `translate(${x},0)`).style('cursor', 'pointer');
    btn
      .append('rect')
      .attr('width', 64)
      .attr('height', 28)
      .attr('rx', 1)
      .attr('fill', '#8A6A32')
      .attr('stroke', '#D9D4C6');
    btn
      .append('text')
      .attr('x', 32)
      .attr('y', 18)
      .attr('text-anchor', 'middle')
      .attr('fill', '#1C2820')
      .attr('font-family', '"Archivo Narrow", sans-serif')
      .attr('font-size', 11)
      .attr('font-weight', 700)
      .attr('letter-spacing', '0.08em')
      .text(label);
    btn.on('click', (event: Event) => {
      event.stopPropagation();
      this.decide.emit(decision);
    });
  }
}
