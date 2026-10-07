export type Lamp = 'danger' | 'amber' | 'clear' | 'dim';

export function lampFor(status: string): Lamp {
  switch (status) {
    case 'awaiting_approval':
      return 'danger';
    case 'planning':
    case 'executing':
    case 'running':
      return 'amber';
    case 'completed':
      return 'clear';
    default:
      return 'dim';
  }
}

export function ageLabel(iso: string | null): string {
  if (!iso) {
    return '—';
  }
  const then = new Date(iso).getTime();
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m`;
  }
  return `${Math.round(minutes / 60)}h`;
}
