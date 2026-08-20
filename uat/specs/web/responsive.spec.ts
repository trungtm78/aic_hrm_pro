import { expect, test } from '../../fixtures/test';
import { Backend, LoginPage, horizontalOverflow } from '../../pages/odoo';

/**
 * The phone rule, checked on a phone-sized viewport.
 *
 * "All custom UI must be mobile-responsive" is a standing user directive and
 * until now it was verified by hand, once, on the day the CSS was written. A
 * page that scrolls sideways on a phone is not a small blemish - the right
 * hand column of a table is simply gone for that user, and nothing on screen
 * says so.
 *
 * This project runs at 320px. The other widths in the directive
 * (375/414/768) are wider and pass whenever 320 does; 320 is the one that
 * actually bites.
 */
const SURFACES = [
  'Executive Overview',
  'Progress vs Plan',
  'Department Scorecard',
  'Alignment Tree',
  'Objectives',
  'Check-ins',
];

test.describe('Gate 2b - 320px', () => {
  for (const item of SURFACES) {
    test(`${item} does not scroll sideways`, async ({ page }) => {
      const backend = new Backend(page);
      await new LoginPage(page).loginAsAdmin();
      await backend.openScreen(item);
      await page.waitForTimeout(800);

      const overflow = await horizontalOverflow(page);
      expect(overflow,
        `${item} overflows the viewport by ${overflow}px at 320px wide`)
        .toBeLessThanOrEqual(1);
    });
  }

  test('controls on our own screens stay thumb-sized', async ({ page }) => {
    // Scoped to the suite's own components. Odoo's toolbar is the platform's
    // to size; holding it to our directive would be measuring somebody
    // else's product and would bury a real finding in noise.
    const backend = new Backend(page);
    await new LoginPage(page).loginAsAdmin();
    await backend.openScreen('Executive Overview');
    await page.waitForTimeout(800);

    const small = await page.evaluate(() => {
      const roots = document.querySelectorAll('[class*="o_aic_"]');
      const offenders: string[] = [];
      roots.forEach((root) => {
        root.querySelectorAll('button, a[href], [role="button"]').forEach((el) => {
          const box = (el as HTMLElement).getBoundingClientRect();
          if (box.width === 0 && box.height === 0) return;
          if (box.height < 44) {
            offenders.push(
              `${el.tagName.toLowerCase()}.${(el as HTMLElement).className}`.slice(0, 70) +
              ` = ${Math.round(box.height)}px`);
          }
        });
      });
      return offenders;
    });
    expect(small, 'touch targets below the 44px floor').toEqual([]);
  });
});
