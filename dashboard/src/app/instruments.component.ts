import { Component, input } from '@angular/core';

import { Metrics } from './models';

@Component({
  selector: 'app-instruments',
  template: `
    <section class="bank" aria-label="Instruments">
      @for (gauge of gauges(); track gauge.label) {
        <article class="gauge">
          <svg viewBox="0 0 160 140" aria-hidden="true">
            <defs>
              <radialGradient [attr.id]="'glass-' + gauge.id" cx="38%" cy="32%" r="70%">
                <stop offset="0%" [attr.stop-color]="gauge.hot" />
                <stop offset="70%" [attr.stop-color]="gauge.color" />
                <stop offset="100%" stop-color="#0b100c" />
              </radialGradient>
            </defs>
            <circle cx="80" cy="78" r="58" fill="#0b100c" stroke="#d9d4c6" stroke-width="2" />
            <circle cx="80" cy="78" r="50" [attr.fill]="'url(#glass-' + gauge.id + ')'" opacity="0.35" />
            <path
              d="M 38 110 A 48 48 0 1 1 122 110"
              fill="none"
              stroke="#2a352c"
              stroke-width="6"
              stroke-linecap="round"
            />
            <path
              d="M 38 110 A 48 48 0 1 1 122 110"
              fill="none"
              [attr.stroke]="gauge.color"
              stroke-width="6"
              stroke-linecap="round"
              [attr.stroke-dasharray]="148"
              [attr.stroke-dashoffset]="148 - 148 * gauge.ratio"
            />
            <line
              x1="80"
              y1="78"
              x2="80"
              y2="38"
              [attr.stroke]="gauge.color"
              stroke-width="2.5"
              stroke-linecap="round"
              [attr.transform]="'rotate(' + gauge.angle + ' 80 78)'"
            />
            <circle cx="80" cy="78" r="4" fill="#d9d4c6" />
          </svg>
          <p class="reading">{{ gauge.reading }}</p>
          <p class="caption">{{ gauge.label }}</p>
        </article>
      }
    </section>
  `,
  styles: [
    `
      .bank {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 1rem;
        padding: 0.5rem 0 0;
      }
      .gauge {
        text-align: center;
        background: linear-gradient(180deg, #1a221b, #10160f);
        border: 1px solid #d9d4c6;
        box-shadow: 0 10px 18px rgb(0 0 0 / 0.35);
        padding: 0.6rem 0.4rem 0.85rem;
      }
      svg {
        width: 100%;
        max-width: 11rem;
        height: auto;
      }
      .reading {
        margin: 0;
        font-size: 1.35rem;
        font-weight: 700;
        letter-spacing: 0.08em;
      }
      .caption {
        margin: 0.15rem 0 0;
        color: #c45c26;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        font-size: 0.72rem;
      }
      @media (max-width: 900px) {
        .bank {
          grid-template-columns: 1fr 1fr;
        }
      }
    `,
  ],
})
export class InstrumentsComponent {
  readonly metrics = input<Metrics | null>(null);

  gauges() {
    const data = this.metrics();
    const success = data?.success_rate ?? 0;
    const duration = data?.avg_duration_seconds ?? 0;
    const hold = data?.avg_approval_seconds ?? 0;
    const cost = data?.cost_per_run ?? 0;
    return [
      meter('clear', 'Clear', `${Math.round(success * 100)}%`, success, 1, '#3f7a52', '#7dce96'),
      meter('time', 'Duration', formatSeconds(duration), duration, 120, '#c45c26', '#e89a5a'),
      meter('hold', 'Turnaround', formatSeconds(hold), hold, 120, '#8b1e1e', '#d45c5c'),
      meter('cost', 'Cost / run', formatCost(cost), cost, 0.01, '#8a6a32', '#d4b56a'),
    ];
  }
}

function meter(
  id: string,
  label: string,
  reading: string,
  value: number,
  max: number,
  color: string,
  hot: string,
) {
  const ratio = Math.max(0, Math.min(1, max ? value / max : 0));
  return {
    id,
    label,
    reading,
    color,
    hot,
    ratio,
    angle: -120 + 240 * ratio,
  };
}

function formatCost(value: number): string {
  if (!value) {
    return 'dark';
  }
  if (value < 0.01) {
    return `$${value.toFixed(6)}`;
  }
  return `$${value.toFixed(3)}`;
}

function formatSeconds(value: number): string {
  if (!value) {
    return '0s';
  }
  if (value < 60) {
    return `${Math.round(value)}s`;
  }
  if (value < 3600) {
    return `${Math.round(value / 60)}m`;
  }
  return `${(value / 3600).toFixed(1)}h`;
}
