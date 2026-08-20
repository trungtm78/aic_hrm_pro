import { expect, Locator, Page } from '@playwright/test';
import { call, target } from '../fixtures/rpc';

/**
 * Page objects for the Odoo backend.
 *
 * Locators are user-facing on purpose - roles, labels and visible text, the
 * things a person actually looks for. A CSS chain like `.o_list_view tbody
 * tr:nth-child(2) td.o_data_cell` passes today and breaks on the next Odoo
 * point release without a line of product code changing, and that maintenance
 * bill is why most UI suites get abandoned. Two exceptions are made and named
 * where they occur: the apps launcher and the menu bar are icon-only chrome
 * with no accessible name, which is itself worth reporting.
 *
 * URL note: this checkout answers the backend on /aic as well as /odoo (the
 * suite ships that entry point in aic_hrm_brand, and this machine's Odoo core
 * has been edited to prefer it). Nothing here may assume either one.
 */
export const BACKEND_URL = /\/(odoo|aic)\b/;

export class LoginPage {
  constructor(private readonly page: Page) {}

  async login(login: string, password: string) {
    await this.page.goto('/web/login');
    await this.page.getByLabel('Email').fill(login);
    await this.page.getByLabel('Password').fill(password);
    await this.page.getByRole('button', { name: 'Log in' }).click();
    await this.page.waitForURL(BACKEND_URL);
  }

  async loginAsAdmin() {
    await this.login(target.login, target.password);
  }
}

export class Backend {
  constructor(readonly page: Page) {}

  /**
   * On a narrow viewport the whole stage bar collapses behind a hamburger.
   * That is the product working as designed, so the page object opens it -
   * rather than the specs each learning about phones.
   */
  async revealMenuBar() {
    const toggle = this.page.getByRole('button', { name: 'Toggle menu' });
    if (await toggle.isVisible().catch(() => false)) {
      await toggle.click();
      await expect(this.page.locator('.o_menu_sections')).toBeVisible();
    }
  }

  /** Open the Performance app through the launcher, the way a person does. */
  async openPerformance() {
    // The launcher is an icon-only button with no accessible name - hence the
    // structural locator. Filed as a testability defect, not worked around
    // silently.
    await this.page.locator('.o_main_navbar button').first().click();
    await this.page.getByRole('menuitem', { name: 'Performance', exact: true })
      .first().click();
    await this.revealMenuBar();
    await expect(this.stage('Plan')).toBeVisible();
  }

  /**
   * One of the eight stages of the operating loop in the menu bar.
   *
   * A stage with children renders as a dropdown button; a stage that is a
   * single screen (Cockpit) renders as a plain link. Both are "the stage" to
   * the person reading the bar, so the locator accepts either.
   */
  stage(name: string): Locator {
    const bar = this.page.locator('.o_menu_sections');
    return bar.getByRole('button', { name, exact: true })
      .or(bar.getByRole('menuitem', { name, exact: true }))
      .first();
  }

  async openMenu(stage: string, item: string) {
    const menu = await this.openStage(stage);
    await menu.getByRole('menuitem', { name: item, exact: true })
      .first().click();
    await this.expectSomethingRendered();
  }

  /**
   * Open one stage's dropdown and return it.
   *
   * The retry is not defensive padding. A click that lands while a client
   * action is still drawing its own root - the alignment tree does this - is
   * swallowed, the dropdown never opens, and the next locator waits twenty
   * seconds for an item that was never rendered.
   */
  async openStage(stage: string): Promise<Locator> {
    const menu = this.page.locator('.o-dropdown--menu').last();
    await this.revealMenuBar();
    const button = this.stage(stage);
    await button.click();
    try {
      await menu.waitFor({ state: 'visible', timeout: 4000 });
    } catch {
      // The click was swallowed while a client action was drawing. Clicking
      // again is safe here precisely because the dropdown did NOT open - a
      // blind second click would have closed it.
      await button.click();
      await menu.waitFor({ state: 'visible', timeout: 8000 });
    }
    return menu;
  }

  /**
   * Landed on something.
   *
   * Not every menu item opens a list: wizards open a dialog and the two
   * dashboards are client actions that draw their own root. Insisting on
   * `.o_content` would report those as broken screens, which is the kind of
   * false red that gets a suite switched off.
   */
  async expectSomethingRendered() {
    // `.o_action` is the root every action gets, list view or OWL client
    // action alike. Asserting on `.o_content` would have failed the three
    // custom dashboards - which render their own root - and reported four
    // working screens as broken.
    await expect(
      this.page.locator('.o_action, .modal-dialog').first()
    ).toBeVisible();
  }

  /**
   * Close a wizard dialog if the menu item opened one.
   *
   * Press the button, do not press Escape. With focus inside one of the
   * wizard's dropdowns Escape closes the dropdown and leaves the dialog
   * standing, and the next click in the run lands on the overlay instead of
   * the menu - which is exactly how this suite first went red.
   */
  async dismissDialog() {
    const dialog = this.page.locator('.modal.d-block');
    // Give a wizard a moment to arrive. The list behind it is already
    // visible, so returning as soon as "something rendered" can outrun the
    // dialog - and then it is still standing when the next click lands.
    await dialog.first().waitFor({ state: 'visible', timeout: 1500 })
      .catch(() => undefined);
    if (!(await dialog.count())) return;
    const close = dialog.first().getByRole('button', { name: /close|discard|cancel/i });
    if (await close.count()) {
      await close.first().click();
    } else {
      await this.page.keyboard.press('Escape');
    }
    await expect(dialog.first()).toBeHidden();
  }

  /**
   * The items inside one stage's dropdown.
   *
   * Scoped to the open dropdown, not the whole page: `getByRole('menuitem')`
   * unscoped also returns the app name and the Cockpit link that live in the
   * bar itself, so an unscoped read reports items that are not in the stage.
   */
  async stageItems(stage: string): Promise<string[]> {
    const menu = await this.openStage(stage);
    const items = await menu.getByRole('menuitem').allTextContents();
    await this.page.keyboard.press('Escape');
    return items.map((text) => text.trim()).filter(Boolean);
  }

  /**
   * Open a screen by its menu name, without going through the launcher.
   *
   * Used by the phone-width project. At 320px the launcher collapses into
   * chrome with no accessible name, and fighting that would test Odoo's
   * navigation rather than our screens - which is what this project is for.
   * The desktop project still clicks the whole way through the menu, so the
   * navigation path is covered where it can be covered honestly.
   */
  async openScreen(menuName: string) {
    const menus = await call('ir.ui.menu', 'search_read',
      [[['name', '=', menuName]], ['action']], { limit: 1 });
    if (!menus.length || !menus[0].action) {
      throw new Error(`No menu named "${menuName}" with an action behind it`);
    }
    const actionId = String(menus[0].action).split(',')[1];
    await this.page.goto(`/odoo/action-${actionId}`);
    await this.expectSomethingRendered();
  }

  get breadcrumb(): Locator {
    return this.page.locator('.o_breadcrumb').first();
  }

  get listRows(): Locator {
    return this.page.locator('.o_list_view .o_data_row');
  }

  async openRowContaining(text: string) {
    await this.page.locator('.o_data_row', { hasText: text }).first().click();
    await expect(this.page.locator('.o_form_view')).toBeVisible();
  }

  /** Switch the current action to another view type. */
  async switchView(name: 'List' | 'Graph' | 'Pivot' | 'Kanban') {
    await this.page.getByRole('button', { name }).first().click();
  }

  /** Any browser console error is a defect, not noise. */
  collectConsoleErrors(): string[] {
    const errors: string[] = [];
    this.page.on('console', (message) => {
      if (message.type() === 'error') errors.push(message.text());
    });
    this.page.on('pageerror', (error) => errors.push(String(error)));
    return errors;
  }
}

/** Horizontal overflow of the page body - the mobile rule with no exceptions. */
export async function horizontalOverflow(page: Page): Promise<number> {
  return page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth);
}
