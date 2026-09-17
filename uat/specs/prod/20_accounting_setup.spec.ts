import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { test, expect, read, loginAsAdmin } from '../../fixtures/prod';
import { OdooUi } from '../../pages/prod';

/**
 * Accounting ground for the department's real revenue and costs.
 *
 * The instance was installed with Odoo's generic chart (USD, United States,
 * 15 % tax) and has never posted an entry, which is the only moment the
 * localization can still be switched. The owner decided (2026-09-17) on the
 * Vietnamese chart: VND, VAT 8 %, revenue split per stream under 5113, an
 * accrual receivable for revenue not yet invoiced, the detailed cost accounts
 * the ledger uses, and two journals for the accrual and cost entries.
 *
 * Everything is done on the settings and configuration screens an
 * accountant would use. Each step first reads whether it is already done, so
 * the spec can run again after a fix.
 */

const books = JSON.parse(readFileSync(resolve(__dirname, '..', '..', 'data', 'kddv_actuals_q3_2026.json'), 'utf-8')).accounting;

async function xmlid(name: string): Promise<number> {
  const [module, ref] = name.split('.');
  const [row] = await read('ir.model.data', 'search_read', [[['module', '=', module], ['name', '=', ref]]], { fields: ['res_id'] });
  if (!row) throw new Error(`No record ${name}`);
  return row.res_id;
}

function accountType(code: string): string {
  if (code.startsWith('24')) return 'asset_prepayments';
  if (code.startsWith('62')) return 'expense_direct_cost';
  return 'expense';
}

test.describe.configure({ mode: 'serial' });

test('Vietnamese chart of accounts, VND and VAT 8%', async ({ page }) => {
  test.setTimeout(30 * 60_000);
  const ui = new OdooUi(page);
  await loginAsAdmin(page);

  await test.step('localization', async () => {
    let [company] = await read('res.company', 'read', [[1]], { fields: ['chart_template', 'currency_id'] });
    if (company.chart_template !== 'vn') {
      const moves = await read('account.move', 'search_count', [[]]);
      expect(moves, 'the chart can only be switched before any entry exists').toBe(0);
      await ui.openAction(await xmlid('account.action_account_config'));
      await page.locator('.o_field_widget[name="chart_template"]').first().waitFor({ timeout: 90_000 });
      await ui.select('res.config.settings', 'chart_template', 'vn', page.locator('.o_form_view').first());
      // Saving the settings installs l10n_vn and loads its chart; the page
      // reloads when the module installation finishes.
      await Promise.all([
        page.waitForEvent('load', { timeout: 15 * 60_000 }),
        page.locator('.o_form_button_save:visible, button[name="execute"]:visible').first().click(),
      ]);
      await page.locator('.o_action_manager').first().waitFor({ timeout: 5 * 60_000 });
      [company] = await read('res.company', 'read', [[1]], { fields: ['chart_template', 'currency_id'] });
    }
    expect(company.chart_template).toBe('vn');
    if (company.currency_id[1] !== 'VND') {
      await ui.openRecord(await xmlid('base.action_res_company_form'), 1);
      await ui.pickMany2one('currency_id', 'VND');
      await ui.save('company currency VND');
    }
    const [partner] = await read('res.company', 'read', [[1]], { fields: ['country_id', 'currency_id'] });
    if (partner.country_id?.[1] !== 'Việt Nam' && partner.country_id?.[1] !== 'Vietnam') {
      await ui.openRecord(await xmlid('base.action_res_company_form'), 1);
      await ui.pickMany2one('country_id', 'Việt Nam', undefined, /^\s*(Việt Nam|Vietnam)\s*$/);
      await ui.save('company country Vietnam');
    }
    const taxes = await read('account.tax', 'search_read', [[['type_tax_use', '=', 'sale'], ['amount', '=', books.sale_vat]]], { fields: ['name'] });
    expect(taxes.length, 'a sale VAT 8% exists').toBeGreaterThan(0);
  });

  const accountAction = await xmlid('account.action_account_form');
  const accounts: { code: string; name: string; type: string }[] = [
    ...Object.values(books.stream_accounts).map((a: any) => ({ code: a.code, name: a.name, type: 'income' })),
    { code: books.accrual_account.code, name: books.accrual_account.name, type: 'asset_current' },
    { code: books.cost_clearing_account.code, name: books.cost_clearing_account.name, type: 'liability_current' },
    ...books.cost_accounts.map((a: any) => ({ code: a.code, name: a.name, type: accountType(a.code) })),
  ];
  for (const account of accounts) {
    await test.step(`account ${account.code}`, async () => {
      const found = await read('account.account', 'search_read', [[['code', '=', account.code]]], { fields: ['name', 'account_type'] });
      if (found.length) return;
      await ui.newRecord(accountAction);
      await ui.fill('code', account.code);
      await ui.fill('name', account.name);
      await ui.select('account.account', 'account_type', account.type);
      await ui.save(`account ${account.code}`);
    });
  }

  const journalAction = await xmlid('account.action_account_journal_form');
  for (const journal of [books.accrual_journal, books.cost_journal]) {
    await test.step(`journal ${journal.code}`, async () => {
      const found = await read('account.journal', 'search_count', [[['code', '=', journal.code]]]);
      if (found) return;
      await ui.newRecord(journalAction);
      await ui.fill('name', journal.name);
      await ui.select('account.journal', 'type', 'general');
      await ui.fill('code', journal.code);
      await ui.save(`journal ${journal.code}`);
    });
  }

  await test.step('full accounting features for the administrator', async () => {
    // Income accounts on products (and journal items) are shown only to
    // users with "Show Full Accounting Features", a technical group that the
    // user form lists in developer mode.
    const group = await xmlid('account.group_account_user');
    const [admin] = await read('res.users', 'search_read', [[['login', '=', 'admin']]], { fields: ['all_group_ids'] });
    if (admin.all_group_ids.includes(group)) return;
    const [groupRow] = await read('res.groups', 'read', [[group]], { fields: ['name'], context: { lang: 'vi_VN' } });
    await ui.gotoWithRetry(`/odoo/action-${await xmlid('base.action_res_users')}/${admin.id}?debug=1`);
    await page.locator('.o_form_view').first().waitFor({ timeout: 90_000 });
    await ui.tab(/Quyền truy cập|Access Rights/);
    const box = page.getByRole('checkbox', { name: new RegExp(`^${groupRow.name}\\??$`) }).first();
    await box.check();
    await ui.save('full accounting features');
    const [after] = await read('res.users', 'search_read', [[['login', '=', 'admin']]], { fields: ['all_group_ids'] });
    expect(after.all_group_ids).toContain(group);
  });

  const productAction = await xmlid('account.product_product_action_sellable');
  for (const product of books.products) {
    await test.step(`product ${product.name}`, async () => {
      const found = await read('product.template', 'search_count', [[['name', '=', product.name]]]);
      if (found) return;
      const [income] = await read('account.account', 'search_read', [[['code', '=', product.account]]], { fields: ['display_name'] });
      const [tax] = await read('account.tax', 'search_read', [[['type_tax_use', '=', 'sale'], ['amount', '=', books.sale_vat]]], { fields: ['name'] });
      await ui.newRecord(productAction);
      await ui.fill('name', product.name);
      await ui.field('type').getByRole('radio', { name: /^(Dịch vụ|Service)$/ }).check();
      // The chart's default sale tax (10%) is pre-filled; tag delete links
      // only appear on hover, so remove tags from the keyboard instead.
      const taxes = ui.field('taxes_id');
      const taxInput = taxes.locator('input').first();
      for (let tags = await taxes.locator('.o_tag').count(); tags > 0; tags -= 1) {
        await taxInput.click();
        await taxInput.press('Backspace');
        await expect(taxes.locator('.o_tag')).toHaveCount(tags - 1);
      }
      await ui.pickMany2one('taxes_id', tax.name, undefined, new RegExp(`^\\s*${tax.name.replace('%', '%')}`));
      await ui.tab(/Kế toán|Accounting/);
      await ui.pickMany2one('property_account_income_id', product.account, undefined, new RegExp(`^\\s*${product.account}\\b`));
      await ui.save(`product ${product.name}`);
      const [saved] = await read('product.template', 'search_read', [[['name', '=', product.name]]],
        { fields: ['property_account_income_id', 'taxes_id', 'type'] });
      expect(saved.property_account_income_id[0]).toBe(income.id);
      expect(saved.type).toBe('service');
    });
  }

  const partnerAction = await xmlid('account.res_partner_action_customer');
  for (const name of books.partners) {
    await test.step(`partner ${name}`, async () => {
      const found = await read('res.partner', 'search_count', [[['name', '=', name], ['is_company', '=', true]]]);
      if (found) return;
      await ui.newRecord(partnerAction);
      await page.locator('.o_field_widget[name="company_type"] input[value="company"], .o_field_widget[name="company_type"] label:has-text("Công ty")').first().click();
      await ui.fill('name', name);
      await ui.save(`partner ${name}`);
    });
  }

  await test.step('read back', async () => {
    for (const account of accounts) {
      const [found] = await read('account.account', 'search_read', [[['code', '=', account.code]]], { fields: ['account_type'] });
      expect(found, `account ${account.code}`).toBeTruthy();
    }
    for (const journal of [books.accrual_journal, books.cost_journal]) {
      expect(await read('account.journal', 'search_count', [[['code', '=', journal.code], ['type', '=', 'general']]])).toBe(1);
    }
    for (const name of books.partners) {
      expect(await read('res.partner', 'search_count', [[['name', '=', name], ['is_company', '=', true]]]), name).toBe(1);
    }
    const [company] = await read('res.company', 'read', [[1]], { fields: ['currency_id', 'chart_template'] });
    expect([company.chart_template, company.currency_id[1]]).toEqual(['vn', 'VND']);
  });
});
