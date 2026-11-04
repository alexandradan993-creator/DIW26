"""Parcours navigateur facultatif : RUN_BROWSER_TESTS=1, Playwright et Chromium."""
import os
import sys
import threading
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'API'))


@unittest.skipUnless(os.environ.get('RUN_BROWSER_TESTS')=='1','Activer RUN_BROWSER_TESTS=1 pour Chromium')
class InterfaceTests(unittest.TestCase):
    def test_refresh_and_failure_keep_same_version(self):
        from playwright.sync_api import sync_playwright
        from test_service_contraintes import ServiceTests
        from serveur_contraintes import make_server
        fixture=ServiceTests();fixture.setUp()
        server=make_server(fixture.service,port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':1440,'height':900})
                errors=[];requests=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.on('request',lambda request:requests.append((request.method,request.url)))
                page.route('https://fonts.googleapis.com/**',lambda route:route.abort())
                page.goto(f'http://127.0.0.1:{server.server_address[1]}',wait_until='domcontentloaded')
                page.wait_for_function("document.querySelector('#applicationStatus').textContent.includes('2 parcelles')")
                page.evaluate("localStorage.setItem('pully-dossiers',JSON.stringify(['E1']));localStorage.setItem('pully-suivi',JSON.stringify({E1:{personalNote:'Note à conserver'}}))")
                page.reload(wait_until='domcontentloaded')
                page.wait_for_function("document.querySelector('#applicationStatus').textContent.includes('2 parcelles')")
                page.locator('[data-tab="data"]').click()
                page.locator('#refreshData').focus();page.keyboard.press('Enter')
                page.wait_for_function("document.querySelector('#refreshStatus').textContent.includes('Actualisation terminée')")
                self.assertTrue(any(method=='POST' and url.endswith('/actualisations') for method,url in requests))
                self.assertTrue(any('/actualisations/' in url and not url.endswith('/etat') for _,url in requests))
                page.locator('[data-tab="list"]').click()
                page.locator('#listIdSelect').select_option('E1')
                page.locator('#details').wait_for(state='visible')
                self.assertIn('Observations cantonales actualisées',page.locator('#parcelSections').inner_text())
                self.assertIn('50 %',page.locator('#parcelSections').inner_text())
                page.keyboard.press('Escape')
                old=fixture.service.active()
                def fail(layer,bbox):raise ValueError('Source de test indisponible')
                fixture.service.collector=fail
                page.locator('[data-tab="data"]').click();page.locator('#refreshData').click()
                page.wait_for_function("document.querySelector('#refreshStatus').textContent.includes('Source de test indisponible')")
                self.assertEqual(fixture.service.active(),old)
                self.assertFalse(page.locator('#refreshData').is_disabled())
                self.assertEqual(page.evaluate("JSON.parse(localStorage.getItem('pully-suivi')).E1.personalNote"),'Note à conserver')
                page.set_viewport_size({'width':390,'height':844})
                self.assertTrue(page.locator('#refreshData').is_visible())
                self.assertEqual(errors,[])
                browser.close()
        finally:
            server.shutdown();server.server_close();thread.join();fixture.tearDown()

if __name__=='__main__':unittest.main()
