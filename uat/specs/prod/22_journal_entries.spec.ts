import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { Page } from '@playwright/test';
import { test, expect, read, loginAsAdmin } from '../../fixtures/prod';
import { OdooUi } from '../../pages/prod';

/**
 * Journal entries for revenue delivered but not yet invoiced, and for costs.
 *
 * Accrual (journal DTHU): per month, each partner's amount is credited to its
 * stream's revenue account and the total debited to receivable 1388; a
 * negative amount (a correction) goes the other way.
 *
 * Costs (journal CPTH): per month, each ledger line is debited to its own
 * account and the total credited to clearing account 3388, which the
 * accountant later allocates to payroll, suppliers and so on.
 *
 * Entries are found again by reference; a rerun posts what is missing.
 */

const books = JSON.parse(readFileSync(resolve(__dirname, '..', '..', 'data', 'kddv_actuals_q3_2026.json'), 'utf-8')).accounting;

type Line = { account: string; partner?: string; label: string; debit: number; credit: number };

async function xmlid(name: string): Promise<number> {
  const [module, ref] = name.split('.');
  const [row] = await read('ir.model.data', 'search_read', [[['module', '=', module], ['name', '=', ref]]], { fields: ['res_id'] });
  return row.res_id;
}

async function addLine(ui: OdooUi, page: Page, line: Line) {
  const row = await ui.addRow('line_ids');
  await ui.pickMany2one('account_id', line.account, row, new RegExp(`^\\s*${line.account}\\b`));
  if (line.partner) {
    await ui.pickMany2one('partner_id', line.partner, row);
  }
  await ui.fill('name', line.label, row);
  // A new line proposes the balancing amount; overwrite both sides.
  await ui.fill('debit', line.debit, row);
  await ui.fill('credit', line.credit, row);
}

function entries() {
  const out: { ref: string; date: string; journal: string; lines: Line[]; total: number }[] = [];
  for (const entry of Object.values(books.accruals) as any[]) {
    const lines: Line[] = [{ account: books.accrual_account.code, label: `Dự thu doanh thu chưa xuất hoá đơn ${entry.ref}`,
      debit: entry.total, credit: 0 }];
    for (const line of entry.lines) {
      lines.push({ account: line.account, partner: line.partner, label: line.label,
        debit: line.amount < 0 ? -line.amount : 0, credit: line.amount > 0 ? line.amount : 0 });
    }
    out.push({ ref: entry.ref, date: entry.date, journal: books.accrual_journal.code, lines, total: entry.total });
  }
  for (const entry of Object.values(books.cost_entries) as any[]) {
    const lines: Line[] = entry.lines.map((line: any) => ({ account: line.account, label: line.label, debit: line.amount, credit: 0 }));
    lines.push({ account: books.cost_clearing_account.code, label: `Đối ứng tổng hợp chi phí ${entry.ref}`, debit: 0, credit: entry.total });
    out.push({ ref: entry.ref, date: entry.date, journal: books.cost_journal.code, lines, total: entry.total });
  }
  return out;
}

test('accrual and cost journal entries', async ({ page }) => {
  test.setTimeout(3 * 60 * 60_000);
  const ui = new OdooUi(page);
  await loginAsAdmin(page);
  const action = await xmlid('account.action_move_journal_line');
  const [admin] = await read('res.users', 'search_read', [[['login', '=', 'admin']]], { fields: ['lang'] });
  const [lang] = await read('res.lang', 'search_read', [[['code', '=', admin.lang]]], { fields: ['date_format'] });
  const userDate = (iso: string) => {
    const [y, m, d] = iso.split('-');
    return lang.date_format.replace('%d', d).replace('%m', m).replace('%Y', y);
  };

  for (const entry of entries()) {
    await test.step(entry.ref, async () => {
      let [move] = await read('account.move', 'search_read', [[['ref', '=', entry.ref], ['move_type', '=', 'entry']]], { fields: ['state', 'line_ids'] });
      if (move && move.state === 'draft' && move.line_ids.length !== entry.lines.length) {
        // A draft auto-saved by an interrupted run: never post it half-typed.
        await ui.openRecord(action, move.id);
        await ui.deleteOpenRecord(`incomplete ${entry.ref}`);
        move = undefined;
      }
      if (!move) {
        const [journal] = await read('account.journal', 'search_read', [[['code', '=', entry.journal]]], { fields: ['display_name'] });
        await ui.newRecord(action);
        await ui.pickMany2one('journal_id', journal.display_name.replace(/\s*\(.*\)$/, ''), undefined,
          new RegExp(journal.display_name.replace(/\s*\(.*\)$/, '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
        // The accounting date renders as a compact button until clicked.
        const dateButton = ui.field('date').locator('button').first();
        if (await dateButton.isVisible().catch(() => false)) await dateButton.click();
        await ui.fill('date', userDate(entry.date));
        await page.keyboard.press('Escape');
        await ui.fill('ref', entry.ref);
        await ui.tab(/Hạng mục bút toán|Journal Items/);
        for (const line of entry.lines) await addLine(ui, page, line);
        const id = await ui.save(entry.ref);
        move = { id, state: 'draft' };
      }
      if (move.state === 'draft') {
        await ui.openRecord(action, move.id);
        await ui.clickButton('action_post', `post ${entry.ref}`);
      }
      const [saved] = await read('account.move', 'search_read', [[['ref', '=', entry.ref], ['move_type', '=', 'entry']]],
        { fields: ['state', 'date', 'line_ids', 'journal_id'] });
      expect(saved.state).toBe('posted');
      expect(saved.date).toBe(entry.date);
      const lines = await read('account.move.line', 'search_read', [[['move_id', '=', saved.id]]],
        { fields: ['account_id', 'debit', 'credit', 'partner_id'] });
      expect(lines.length, `${entry.ref} lines`).toBe(entry.lines.length);
      for (const code of new Set(entry.lines.map((line) => line.account))) {
        const expected = entry.lines.filter((line) => line.account === code)
          .reduce((sum, line) => sum + line.debit - line.credit, 0);
        const got = lines.filter((line: any) => line.account_id[1].startsWith(`${code} `))
          .reduce((sum: number, line: any) => sum + line.debit - line.credit, 0);
        expect(got, `${entry.ref} account ${code}`).toBe(expected);
      }
    });
  }
});
