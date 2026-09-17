import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { test, expect, read, loginAsAdmin } from '../../fixtures/prod';
import { OdooUi } from '../../pages/prod';

/**
 * Customer invoices for the revenue the register marks as invoiced.
 *
 * One invoice per partner, register section and month, dated the month's
 * last day, one line with the section's service product at the amount before
 * VAT; the product carries VAT 8 % and the stream's revenue account. Where the
 * register's VAT is not 8 % the invoice says so in its terms, for the
 * accountant to check. Invoices are found again by their reference, so a
 * rerun posts what is missing and adds nothing twice.
 */

const books = JSON.parse(readFileSync(resolve(__dirname, '..', '..', 'data', 'kddv_actuals_q3_2026.json'), 'utf-8')).accounting;

async function xmlid(name: string): Promise<number> {
  const [module, ref] = name.split('.');
  const [row] = await read('ir.model.data', 'search_read', [[['module', '=', module], ['name', '=', ref]]], { fields: ['res_id'] });
  return row.res_id;
}

test('posted customer invoices from the receipts register', async ({ page }) => {
  test.setTimeout(3 * 60 * 60_000);
  const ui = new OdooUi(page);
  await loginAsAdmin(page);
  const action = await xmlid('account.action_move_out_invoice_type');
  const [admin] = await read('res.users', 'search_read', [[['login', '=', 'admin']]], { fields: ['lang'] });
  const [lang] = await read('res.lang', 'search_read', [[['code', '=', admin.lang]]], { fields: ['date_format'] });
  const userDate = (iso: string) => {
    const [y, m, d] = iso.split('-');
    return lang.date_format.replace('%d', d).replace('%m', m).replace('%Y', y);
  };

  await test.step('no half-entered invoices left behind', async () => {
    // An interrupted run can leave an auto-saved draft without reference.
    const leftovers = await read('account.move', 'search_read', [[
      ['move_type', '=', 'out_invoice'], ['state', '=', 'draft'], ['ref', '=', false]]], { fields: ['id'] });
    for (const leftover of leftovers) {
      await ui.openRecord(action, leftover.id);
      await ui.deleteOpenRecord(`draft invoice ${leftover.id}`);
    }
  });

  for (const invoice of books.invoices) {
    await test.step(invoice.ref, async () => {
      let [move] = await read('account.move', 'search_read',
        [[['ref', '=', invoice.ref], ['move_type', '=', 'out_invoice']]], { fields: ['state', 'amount_untaxed'] });
      if (move && move.state === 'draft' && move.amount_untaxed !== invoice.untaxed) {
        // Auto-saved by an interrupted run before its line was complete.
        await ui.openRecord(action, move.id);
        await ui.deleteOpenRecord(`incomplete ${invoice.ref}`);
        move = undefined;
      }
      if (!move) {
        const [partner] = await read('res.partner', 'search_read', [[['name', '=', invoice.partner], ['is_company', '=', true]]], { fields: ['display_name'] });
        await ui.newRecord(action);
        await ui.pickMany2one('partner_id', invoice.partner, undefined,
          new RegExp(`^\\s*${partner.display_name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*$`));
        await ui.fill('invoice_date', userDate(invoice.date));
        await ui.tab(/Chi tiết hóa đơn|Chi tiết hoá đơn|Invoice Lines/);
        const lines = page.locator('.o_field_widget[name="invoice_line_ids"]').first();
        {
          // The product column is optional and hidden by default; the choice
          // is not reliably remembered, so it is checked on every invoice.
          if (!(await lines.locator('th[data-name="product_id"]').count())) {
            await lines.locator('.o_optional_columns_dropdown button, .o_optional_columns_dropdown_toggle').first().click();
            await page.locator('.o-dropdown--menu .o-dropdown-item, .o-dropdown--menu .dropdown-item')
              .filter({ hasText: /^\s*(Sản phẩm|Product)\s*$/ }).first().click();
            await expect(lines.locator('th[data-name="product_id"]')).toHaveCount(1);
            await page.keyboard.press('Escape');
          }
        }
        const row = await ui.addRow('invoice_line_ids');
        await ui.pickMany2one('product_id', invoice.product, row);
        await ui.fill('price_unit', invoice.untaxed, row);
        await ui.fill('narration', invoice.note);
        await ui.tab(/Thông tin khác|Other Info/);
        await ui.fill('ref', invoice.ref);
        const id = await ui.save(invoice.ref);
        move = { id, state: 'draft' };
      }
      if (move.state === 'draft') {
        await ui.openRecord(action, move.id);
        await ui.clickButton('action_post', `post ${invoice.ref}`);
      }
      const [saved] = await read('account.move', 'search_read', [[['ref', '=', invoice.ref], ['move_type', '=', 'out_invoice']]],
        { fields: ['state', 'invoice_date', 'amount_untaxed', 'amount_tax', 'partner_id', 'invoice_line_ids'] });
      expect(saved.state).toBe('posted');
      expect(saved.invoice_date).toBe(invoice.date);
      expect(saved.partner_id[1]).toContain(invoice.partner);
      expect(saved.invoice_line_ids.length).toBe(1);
      expect(saved.amount_untaxed).toBe(invoice.untaxed);
      expect(Math.abs(saved.amount_tax - invoice.untaxed * books.sale_vat / 100)).toBeLessThanOrEqual(1);
    });
  }

  await test.step('monthly totals equal the register', async () => {
    const byMonth: Record<string, number> = {};
    for (const invoice of books.invoices) byMonth[invoice.month] = (byMonth[invoice.month] ?? 0) + invoice.untaxed;
    for (const [month, total] of Object.entries(byMonth)) {
      const mm = String(month).padStart(2, '0');
      const moves = await read('account.move', 'search_read', [[
        ['move_type', '=', 'out_invoice'], ['state', '=', 'posted'], ['ref', '=like', `PT2026-T${mm}-%`]]], { fields: ['amount_untaxed'] });
      expect(moves.reduce((sum: number, m: any) => sum + m.amount_untaxed, 0), `month ${month}`).toBe(total);
    }
    expect(await read('account.move', 'search_count', [[['move_type', '=', 'out_invoice'], ['ref', '=like', 'PT2026-%']]]))
      .toBe(books.invoices.length);
  });
});
