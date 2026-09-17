import { expect, Locator, Page, Response } from '@playwright/test';

/**
 * Form and list helpers for entering data on production.
 *
 * The production interface runs in Vietnamese, and the account's language is
 * not something a data-entry script should depend on. Fields are therefore
 * addressed by their technical name (`.o_field_widget[name=...]`), which is
 * the same in every language, and buttons by their method name where Odoo
 * gives them one. Visible text is used only where Odoo renders nothing else
 * (dropdown items, dialog buttons).
 *
 * Waiting: never on "network idle". The long-polling bus is blocked, the
 * client keeps retrying it, and the network is therefore never idle - every
 * wait ran into its full timeout. Each write instead waits for the server's
 * answer to the RPC that performs it (`web_save`, `unlink`, `call_button`)
 * and reads that answer: a refused write fails with Odoo's own message, not
 * with a timeout somewhere later.
 */

const DELETE_LABEL = /^\s*(Xoá|Xóa|Delete)\s*$/i;

export class OdooUi {
  constructor(readonly page: Page) {}

  field(name: string, scope?: Locator): Locator {
    return (scope ?? this.page.locator('.o_form_view').first()).locator(`.o_field_widget[name="${name}"]`).first();
  }

  /**
   * Run `trigger` and return once the server has answered; throw on a
   * server-side error. `method` is an ORM method name, or a route starting
   * with "/" for endpoints outside call_kw (e.g. /mail/message/post).
   */
  async rpc<T = any>(method: string, context: string, trigger: () => Promise<unknown>): Promise<T> {
    const answer = this.page.waitForResponse((response: Response) =>
      method.startsWith('/')
        ? response.url().includes(method)
        : response.url().includes('/web/dataset/call_') &&
          (response.request().postData() ?? '').includes(`"method":"${method}"`), { timeout: 120_000 });
    await trigger();
    const response = await answer;
    const body: any = await response.json().catch(() => ({}));
    if (body.error) {
      const message = body.error?.data?.message ?? body.error?.message ?? JSON.stringify(body.error);
      throw new Error(`Odoo refused ${method} (${context}): ${message}`);
    }
    return body.result as T;
  }

  async openAction(actionId: number, suffix = '') {
    await this.page.goto(`/odoo/action-${actionId}${suffix}`);
    await this.page.locator('.o_action_manager .o_view_controller').first().waitFor({ timeout: 60_000 });
  }

  async openRecord(actionId: number, recordId: number) {
    await this.openAction(actionId, `/${recordId}`);
    await this.page.locator('.o_form_view .o_form_sheet_bg, .o_form_view .o_form_sheet').first().waitFor();
  }

  async newRecord(actionId: number) {
    await this.openAction(actionId, '/new');
    await this.page.locator('.o_form_view .o_form_sheet_bg, .o_form_view .o_form_sheet').first().waitFor();
  }

  async fill(name: string, value: string | number, scope?: Locator) {
    const input = this.field(name, scope).locator('input, textarea').first();
    await input.fill(String(value));
    await input.press('Tab');
  }

  async select(name: string, value: string, scope?: Locator) {
    await this.field(name, scope).locator('select').selectOption(value);
  }

  async check(name: string, checked: boolean, scope?: Locator) {
    const box = this.field(name, scope).locator('input[type="checkbox"]');
    if ((await box.isChecked()) !== checked) await box.click();
  }

  /** Type `text` into a many2one and pick the suggestion matching `match` (default: exactly `text`). */
  async pickMany2one(name: string, text: string, scope?: Locator, match?: RegExp) {
    const input = this.field(name, scope).locator('input').first();
    await input.click();
    await input.fill(text);
    const menu = this.page.locator('.o-autocomplete--dropdown-menu').last();
    await menu.waitFor();
    const exact = menu.locator('.o-autocomplete--dropdown-item')
      .filter({ hasText: match ?? new RegExp(`^\\s*${escapeRegExp(text)}\\s*$`) });
    await expect(exact.first(), `"${text}" must be offered for ${name}`).toBeVisible({ timeout: 20_000 });
    await exact.first().click();
    await expect(menu).toBeHidden();
  }

  async tab(label: RegExp) {
    await this.page.locator('.o_notebook .nav-link').filter({ hasText: label }).first().click();
  }

  /** Save the open form and return its record id. */
  async save(context: string): Promise<number> {
    const button = this.page.locator('.o_form_button_save:visible').first();
    const result = await this.rpc<any[]>('web_save', context, () => button.click());
    const id = Array.isArray(result) && result[0]?.id;
    if (!id) throw new Error(`Saved ${context} but the server returned no id`);
    await expect(this.page.locator('.o_form_button_save:visible')).toHaveCount(0);
    return id;
  }

  async clickButton(method: string, context: string) {
    await this.rpc('call_button', context, () =>
      this.page.locator(`.o_form_view button[name="${method}"]:visible`).first().click());
  }

  async openCogItem(label: RegExp) {
    await this.page.locator('.o_control_panel .o_cp_action_menus .dropdown-toggle, .o_control_panel .o_cp_action_menus button')
      .first().click();
    await this.page.locator('.o-dropdown--menu .o-dropdown-item, .o-dropdown--menu .dropdown-item')
      .filter({ hasText: label }).first().click();
  }

  /** Delete the record currently open in a form. */
  async deleteOpenRecord(context: string) {
    await this.openCogItem(DELETE_LABEL);
    const dialog = this.page.locator('.modal-dialog').last();
    await dialog.waitFor();
    await this.rpc('unlink', context, () => dialog.locator('.modal-footer .btn-primary').first().click());
  }

  /**
   * Delete every record the list shows, across pages.
   * Search facets are cleared first so a default filter hides nothing.
   */
  async deleteAllInList(context: string) {
    await this.page.locator('.o_list_view').first().waitFor();
    const facets = this.page.locator('.o_searchview_facet .o_facet_remove');
    while (await facets.count()) {
      await facets.first().click();
      await this.page.waitForTimeout(500);
    }
    await this.page.waitForTimeout(1000);
    if (!(await this.page.locator('.o_list_view .o_data_row').count())) return;
    await this.page.locator('.o_list_view thead .o_list_record_selector input').first().check();
    const selectDomain = this.page.locator('.o_list_select_domain');
    if (await selectDomain.isVisible().catch(() => false)) await selectDomain.click();
    await this.openCogItem(DELETE_LABEL);
    const dialog = this.page.locator('.modal-dialog').last();
    await dialog.waitFor();
    await this.rpc('unlink', context, () => dialog.locator('.modal-footer .btn-primary').first().click());
  }
}

export function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
