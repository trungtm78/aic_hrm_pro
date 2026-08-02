/** @odoo-module **/
// Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
import { registry } from "@web/core/registry";

/**
 * Remove the platform's own entries from the user menu.
 *
 * "Help" points at the platform support site and "My Odoo.com Account"
 * names it outright - both are the vendor's channels, not the ones a
 * customer of this product should be sent to. Preferences, the PWA
 * install entry and Log out are the product's own and stay.
 */
const userMenu = registry.category("user_menuitems");

// "documentation" only exists on the 18 build; the contains() guard keeps
// the same file working on both without a version branch.
for (const item of ["documentation", "support", "odoo_account"]) {
    if (userMenu.contains(item)) {
        userMenu.remove(item);
    }
}
