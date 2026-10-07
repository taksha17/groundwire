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
        min-height: 24rem;
        flex: 1;
      }
      .diagram {
        width: 100%;
        height: 100%;
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
    halo.append('stop').attr('offset', '0%').attr('stop-color', '#F07A7A').attr('stop-opacity', 0.55);
    halo.append('stop').attr('offset', '55%').attr('stop-color', '#C43030').attr('stop-opacity', 0.22);
    halo.append('stop').attr('offset', '100%').attr('stop-color', '#C43030').attr('stop-opacity', 0);

    const glass: Record<string, [string, string, string]> = {
      danger: ['#F07A7A', '#C43030', '#8B1E1E'],
      amber: ['#F3B07A', '#E0763A', '#C45C26'],
      clear: ['#9EE0B0', '#58A86F', '#3F7A52'],
      dim: ['#8A9286', '#5A6258', '#4A5248'],
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
        .attr('fill', '#D9D4C6')
        .attr('font-family', '"Space Grotesk", "Archivo Narrow", sans-serif')
        .attr('font-size', 20)
        .attr('font-weight', 500)
        .attr('letter-spacing', '0.3em')
        .attr('opacity', 0.85)
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
      svg.append('path').attr('d', d).attr('fill', 'none').attr('stroke', '#1c2820').attr('stroke-width', 14);
      svg
        .append('path')
        .attr('d', d)
        .attr('fill', 'none')
        .attr('stroke', '#8A6A32')
        .attr('stroke-width', 6)
        .attr('stroke-linecap', 'square');
      const flow = svg
        .append('path')
        .attr('d', d)
        .attr('fill', 'none')
        .attr('stroke', '#D9D4C6')
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
        .attr('rx', 3)
        .attr('fill', heldStroke ? '#161010' : '#10160f')
        .attr('stroke', heldStroke ? '#F07A7A' : '#D9D4C6')
        .attr('stroke-width', 1.6)
        .attr('stroke-opacity', heldStroke ? 0.85 : 1);
      g.append('rect')
        .attr('x', 6)
        .attr('y', 6)
        .attr('width', nodeW - 12)
        .attr('height', nodeH - 12)
        .attr('fill', 'none')
        .attr('stroke', '#2a352c');
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
        .attr('stroke', '#D9D4C6')
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
        .attr('fill', '#D9D4C6')
        .attr('font-family', mono)
        .attr('font-size', 10)
        .attr('letter-spacing', '0.16em')
        .attr('opacity', 0.8)
        .text(node.type.replace('_', ' ').toUpperCase());
      g.append('text')
        .attr('x', 46)
        .attr('y', 43)
        .attr('fill', '#D9D4C6')
        .attr('font-family', '"Space Grotesk", "Archivo Narrow", sans-serif')
        .attr('font-size', 16)
        .attr('font-weight', 600)
        .text(node.name);
      g.append('text')
        .attr('x', 22)
        .attr('y', 78)
        .attr('fill', lamp === 'danger' ? '#F07A7A' : '#C45C26')
        .attr('font-family', mono)
        .attr('font-size', 11)
        .attr('letter-spacing', '0.1em')
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
      .style('font', '600 11px "Space Grotesk", "Archivo Narrow", sans-serif')
      .style('letter-spacing', '0.1em')
      .style('text-transform', 'uppercase')
      .style('background', 'linear-gradient(180deg, #c4a056, #8a6a32 55%, #5c441c)')
      .style('color', '#070a08')
      .style('border', '1px solid #d9d4c6')
      .style('padding', '7px 10px')
      .style('cursor', 'pointer')
      .on('click', (event: Event) => {
        event.stopPropagation();
        this.decide.emit(decision);
      });
  }
}
