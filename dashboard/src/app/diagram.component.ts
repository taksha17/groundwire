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
        flex: 1 1 32rem;
        min-height: 32rem;
        height: 32rem;
        position: relative;
        z-index: 1;
        background: #0a0d13;
        border: 1px solid #2d374f;
        border-radius: 16px;
        box-shadow: 0 24px 70px rgb(0 0 0 / 0.5);
      }
      .diagram {
        width: 100%;
        height: 32rem;
        display: block;
        overflow: visible;
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
    const extra = graph?.nodes.some((node) => node.status === 'awaiting_approval') ? 52 : 0;
    const height = Math.max(el.clientHeight || 360, 320) + extra;
    svg.attr('viewBox', `0 0 ${width} ${height}`);

    const reduceMotion =
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const defs = svg.append('defs');
    const glow = defs.append('filter').attr('id', 'lamp-glow');
    glow.append('feGaussianBlur').attr('stdDeviation', '3.5').attr('result', 'blur');
    const merge = glow.append('feMerge');
    merge.append('feMergeNode').attr('in', 'blur');
    merge.append('feMergeNode').attr('in', 'SourceGraphic');

    const halo = defs
      .append('radialGradient')
      .attr('id', 'held-halo');
    halo.append('stop').attr('offset', '0%').attr('stop-color', '#ff5d5d').attr('stop-opacity', 0.55);
    halo.append('stop').attr('offset', '55%').attr('stop-color', '#ff5d5d').attr('stop-opacity', 0.18);
    halo.append('stop').attr('offset', '100%').attr('stop-color', '#ff5d5d').attr('stop-opacity', 0);

    const glass: Record<string, [string, string, string]> = {
      danger: ['#ffb3b3', '#ff5d5d', '#a32020'],
      amber: ['#ffd9a0', '#ffb347', '#b96e00'],
      clear: ['#b8f5d8', '#42d392', '#14804e'],
      dim: ['#8b95ab', '#2a3143', '#1c2334'],
    };
    for (const [lamp, [hot, mid, base]] of Object.entries(glass)) {
      const grad = defs
        .append('radialGradient')
        .attr('id', `lamp-glass-${lamp}`)
        .attr('cx', '35%')
        .attr('cy', '30%')
        .attr('r', '80%');
      grad.append('stop').attr('offset', '0%').attr('stop-color', hot);
      grad.append('stop').attr('offset', '45%').attr('stop-color', mid);
      grad.append('stop').attr('offset', '100%').attr('stop-color', base);
    }

    const mono = '"IBM Plex Mono", "Archivo Narrow", ui-monospace, monospace';

    if (!graph || graph.nodes.length === 0) {
      svg
        .append('text')
        .attr('x', width / 2)
        .attr('y', height / 2)
        .attr('text-anchor', 'middle')
        .attr('fill', '#8b95ab')
        .attr('font-family', '"Space Grotesk", ui-sans-serif, sans-serif')
        .attr('font-size', 20)
        .attr('font-weight', 500)
        .attr('letter-spacing', '0.12em')
        .attr('opacity', 0.9)
        .text('SELECT A ROUTE');
      return;
    }

    const pad = 88;
    const nodeW = 168;
    const nodeH = 96;
    const xs = d3
      .scalePoint<string>()
      .domain(graph.nodes.map((n) => n.id))
      .range([pad, width - pad])
      .padding(0.45);
    const y = height / 2 - 8;

    const track = d3.line<[number, number]>().curve(d3.curveBasis);
    for (const edge of graph.edges) {
      const x1 = xs(edge.source) ?? pad;
      const x2 = xs(edge.target) ?? pad;
      const d = track([
        [x1 + nodeW / 2, y],
        [(x1 + x2) / 2, y],
        [x2 - nodeW / 2, y],
      ])!;
      svg.append('path').attr('d', d).attr('fill', 'none').attr('stroke', '#0a0d13').attr('stroke-width', 14);
      svg
        .append('path')
        .attr('d', d)
        .attr('fill', 'none')
        .attr('stroke', '#c9a86a')
        .attr('stroke-width', 6)
        .attr('stroke-linecap', 'round');
      const flow = svg
        .append('path')
        .attr('d', d)
        .attr('fill', 'none')
        .attr('stroke', '#f2ead8')
        .attr('stroke-width', 1.5)
        .attr('stroke-dasharray', '10 8')
        .attr('opacity', 0.7);
      if (!reduceMotion) {
        flow
          .append('animate')
          .attr('attributeName', 'stroke-dashoffset')
          .attr('from', '36')
          .attr('to', '0')
          .attr('dur', '1.8s')
          .attr('repeatCount', 'indefinite');
      }
    }

    for (const node of graph.nodes) {
      const x = (xs(node.id) ?? pad) - nodeW / 2;
      const g = svg.append('g').attr('transform', `translate(${x},${y - nodeH / 2})`);
      const heldStroke = node.status === 'awaiting_approval';
      g.append('rect')
        .attr('width', nodeW)
        .attr('height', nodeH)
        .attr('rx', 12)
        .attr('fill', heldStroke ? '#1a1014' : '#131826')
        .attr('stroke', heldStroke ? '#ff5d5d' : '#232b3d')
        .attr('stroke-width', 1.4)
        .attr('stroke-opacity', heldStroke ? 0.9 : 1);
      g.append('rect')
        .attr('x', 6)
        .attr('y', 6)
        .attr('width', nodeW - 12)
        .attr('height', nodeH - 12)
        .attr('rx', 9)
        .attr('fill', 'none')
        .attr('stroke', '#2d374f');
      const lamp = lampFor(node.status);
      const held = node.status === 'awaiting_approval';
      if (held) {
        const haloCircle = g
          .append('circle')
          .attr('cx', 26)
          .attr('cy', 28)
          .attr('r', 26)
          .attr('fill', 'url(#held-halo)');
        if (!reduceMotion) {
          haloCircle
            .append('animate')
            .attr('attributeName', 'opacity')
            .attr('values', '1;0.45;1')
            .attr('dur', '1.6s')
            .attr('repeatCount', 'indefinite');
        }
      }
      const glassEl = g
        .append('circle')
        .attr('cx', 26)
        .attr('cy', 28)
        .attr('r', 11)
        .attr('fill', `url(#lamp-glass-${lamp})`)
        .attr('stroke', '#2d374f')
        .attr('stroke-width', 0.8)
        .attr('filter', 'url(#lamp-glow)');
      g.append('circle').attr('cx', 22).attr('cy', 24).attr('r', 3.2).attr('fill', '#fff').attr('opacity', 0.55);
      if (held) {
        glassEl.append('title').text('Held at danger');
        if (!reduceMotion) {
          glassEl
            .append('animate')
            .attr('attributeName', 'opacity')
            .attr('values', '1;0.4;1')
            .attr('dur', '1.6s')
            .attr('repeatCount', 'indefinite');
        }
      }
      g.append('text')
        .attr('x', 46)
        .attr('y', 22)
        .attr('fill', '#8b95ab')
        .attr('font-family', mono)
        .attr('font-size', 10)
        .attr('letter-spacing', '0.08em')
        .attr('opacity', 0.9)
        .text(node.type.replace('_', ' ').toUpperCase());
      g.append('text')
        .attr('x', 46)
        .attr('y', 43)
        .attr('fill', '#e8ecf6')
        .attr('font-family', '"Space Grotesk", ui-sans-serif, sans-serif')
        .attr('font-size', 15)
        .attr('font-weight', 600)
        .text(node.name);
      g.append('text')
        .attr('x', 22)
        .attr('y', 78)
        .attr('fill', lamp === 'danger' ? '#ff5d5d' : '#ffb347')
        .attr('font-family', mono)
        .attr('font-size', 11)
        .attr('letter-spacing', '0.04em')
        .text(node.status.replace('_', ' '));

      if (node.status === 'awaiting_approval') {
        const fo = g
          .append('foreignObject')
          .attr('x', 12)
          .attr('y', nodeH + 10)
          .attr('width', 150)
          .attr('height', 40);
        const wrap = fo
          .append('xhtml:div')
          .attr('xmlns', 'http://www.w3.org/1999/xhtml')
          .style('display', 'flex')
          .style('gap', '8px');
        this.htmlLever(wrap, 'Approve', 'approve');
        this.htmlLever(wrap, 'Reject', 'reject');
      }
    }
  }

  private htmlLever(
    parent: d3.Selection<d3.BaseType, unknown, null, undefined>,
    label: string,
    decision: 'approve' | 'reject',
  ): void {
    parent
      .append('xhtml:button')
      .attr('type', 'button')
      .attr('class', 'lever')
      .text(label)
      .style('font', '600 12px "Space Grotesk", ui-sans-serif, sans-serif')
      .style('letter-spacing', '0.02em')
      .style('text-transform', 'none')
      .style('background', decision === 'approve' ? 'linear-gradient(135deg, #c9a86a, #a8874b)' : '#221d12')
      .style('color', decision === 'approve' ? '#141009' : '#f2ead8')
      .style('border', decision === 'approve' ? '0' : '1px solid #4d4331')
      .style('border-radius', '8px')
      .style('padding', '8px 14px')
      .style('cursor', 'pointer')
      .on('click', (event: Event) => {
        event.stopPropagation();
        this.decide.emit(decision);
      });
  }
}
