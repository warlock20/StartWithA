import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MarginTab } from '../components/intelligence-panel/MarginTab';

const noop = () => {};

function renderTab({ eps, price, growthRate = 15, ticker = 'TEST' }) {
  return render(
    <MarginTab
      companyData={{ eps_ttm: eps, ticker }}
      growthRate={growthRate}
      onGrowthRateChange={noop}
      price={price}
      currencySymbol="$"
    />,
  );
}

describe('MarginTab', () => {
  describe('loss-making company', () => {
    // Regression: a -$97.50 fair value against a $145.02 price was reported as
    // "+248.7% margin -- significantly undervalued".
    it('warns instead of claiming a margin of safety', () => {
      renderTab({ eps: -2.53, price: 145.02 });

      expect(screen.getByText(/losing money/i)).toBeInTheDocument();
      expect(screen.queryByText(/significantly undervalued/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Strong margin of safety/i)).not.toBeInTheDocument();
    });

    it('never renders a positive margin percentage', () => {
      const { container } = renderTab({ eps: -2.53, price: 145.02 });
      expect(container.textContent).not.toMatch(/\+\d+\.\d% margin/);
      expect(container.textContent).not.toContain('248.7');
    });

    it('never renders a negative fair value', () => {
      const { container } = renderTab({ eps: -2.53, price: 145.02 });
      expect(container.textContent).not.toContain('$-97.50');
      expect(container.textContent).not.toMatch(/\$-\d/);
    });

    it('states the loss and price concretely', () => {
      const { container } = renderTab({ eps: -2.53, price: 145.02 });
      expect(container.textContent).toContain('$2.53');    // shown as a magnitude
      expect(container.textContent).toContain('$145.02');
    });

    it('hides the fair-value gauge', () => {
      const { container } = renderTab({ eps: -2.53, price: 145.02 });
      expect(container.querySelector('.mos-gauge')).toBeNull();
    });
  });

  describe('profitable company', () => {
    it('shows a margin of safety when trading below fair value', () => {
      const { container } = renderTab({ eps: 10, price: 100 });   // fair value 385
      expect(container.textContent).toContain('$385.00');
      expect(container.textContent).toMatch(/\+74\.0% margin/);
      // "Undervalued" alone also matches the gauge's axis label
      expect(screen.getByText(/significantly undervalued/i)).toBeInTheDocument();
    });

    it('shows a premium when trading above fair value', () => {
      const { container } = renderTab({ eps: 2, growthRate: 5, price: 100 });  // fair value 37
      expect(container.textContent).toContain('$37.00');
      expect(container.textContent).toMatch(/premium/);
      expect(screen.queryByText(/losing money/i)).not.toBeInTheDocument();
    });

    it('renders the gauge', () => {
      const { container } = renderTab({ eps: 10, price: 100 });
      expect(container.querySelector('.mos-gauge')).not.toBeNull();
    });
  });

  describe('missing data', () => {
    it('reports unavailable EPS', () => {
      renderTab({ eps: null, price: 100 });
      expect(screen.getByText(/EPS data unavailable/i)).toBeInTheDocument();
    });

    it('prompts for a price', () => {
      renderTab({ eps: 5, price: 0 });
      expect(screen.getByText(/Enter a price/i)).toBeInTheDocument();
    });
  });
});
