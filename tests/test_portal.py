import unittest
from playwright.sync_api import sync_playwright
from test_browser import BrowserBaselineTest
from app.site import DATA

class PortalInteractionTest(BrowserBaselineTest):
    def test_browser_business_interaction(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(self.origin + "detail?id=" + DATA["items"][0]["id"], wait_until="domcontentloaded")
                page.locator('#city').select_option('江苏');page.locator('#ticket').select_option('演出票');page.locator('#voucher-preview').click();self.assertEqual(page.locator('#voucher').inner_text(),'江苏 / 演出票')
            finally:
                browser.close()
