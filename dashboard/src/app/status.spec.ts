import { lampFor } from './status';

describe('lampFor', () => {
  it('puts awaiting_approval at danger', () => {
    expect(lampFor('awaiting_approval')).toBe('danger');
  });

  it('puts executing at amber', () => {
    expect(lampFor('executing')).toBe('amber');
  });

  it('puts completed at clear', () => {
    expect(lampFor('completed')).toBe('clear');
  });
});
