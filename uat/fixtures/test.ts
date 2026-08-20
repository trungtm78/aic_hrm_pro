import { test as base } from '@playwright/test';

/**
 * The browser fixture every web spec uses.
 *
 * It blocks Odoo's bus (long-polling) endpoints. That is a deliberate,
 * narrow exception to "don't touch the system under test", and the reason is
 * environmental rather than cosmetic: this UAT server runs threaded
 * (`workers = 0`, the only mode Windows supports), and every page that has
 * ever been opened holds a long-poll connection open. Run several specs in a
 * row and the held connections starve the pool, the next request stalls, and
 * Odoo raises its "connection lost" dialog over the UI - failing the spec for
 * a reason that has nothing to do with the product.
 *
 * What is blocked is the notification transport, not any screen, action or
 * record under test. If a spec ever needs live notifications it must opt out
 * of this fixture and say why.
 */
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route(/\/(longpolling|bus)\//, (route) => route.abort());
    await use(page);
  },
});

export { expect } from '@playwright/test';
