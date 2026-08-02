# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install', 'aic_hrm_brand')
class TestBrandSurfaces(HttpCase):
    """The white-label surfaces are asserted, not assumed.

    Each of these broke once during the walkthrough build: the tab title
    fell back to the platform name, the login footer carried an outbound
    vendor link, and the product had no address of its own. A template
    override is exactly the kind of change that survives a release and
    then silently stops applying, so each surface gets a test.
    """

    def test_login_page_carries_no_vendor_branding(self):
        response = self.url_open('/web/login')
        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertNotIn('Powered by', body)
        self.assertNotIn('www.odoo.com', body)
        self.assertIn('AIC HRM Pro', body)

    def test_browser_title_defaults_to_the_product(self):
        body = self.url_open('/web/login').text
        self.assertIn('<title>AIC HRM Pro</title>', body)

    def test_product_entry_point_reaches_the_web_client(self):
        """/aic is the address handed to customers; it must resolve."""
        response = self.url_open('/aic', allow_redirects=False)
        self.assertIn(response.status_code, (301, 302, 303, 307, 308))
        self.assertTrue(response.headers.get('Location', '').endswith('/odoo'))

    def test_entry_point_keeps_the_requested_path(self):
        response = self.url_open('/aic/action-123', allow_redirects=False)
        self.assertTrue(
            response.headers.get('Location', '').endswith('/odoo/action-123'))

    def test_automation_account_is_not_named_after_the_platform(self):
        """Every tracking message is authored by this partner."""
        root = self.env.ref('base.partner_root')
        self.assertNotIn('odoo', root.name.lower())
