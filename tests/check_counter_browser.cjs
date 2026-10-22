// Exercise the generated Xibo HTML in a real Chromium, at full and half size.
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const html = execFileSync('python3', ['-c', `
import sys
from datetime import date
sys.path.insert(0, 'xibo_signage_manager')
from counter_widget import COUNTER_STYLE, COUNTER_SCRIPT, render_counter_markup
print('<!doctype html><html><head><style>' + COUNTER_STYLE + '</style></head><body>' + render_counter_markup(date(2026,10,1)) + COUNTER_SCRIPT + '</body></html>')
`], {encoding:'utf8'});

(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_EXECUTABLE || undefined});
  try {
    for (const [width,height] of [[1120,400],[560,200]]) {
      const page = await browser.newPage({viewport:{width,height}});
      const errors=[];
      page.on('pageerror', error=>errors.push(error.message));
      await page.clock.install({time:new Date('2026-10-22T17:00:00Z')});
      await page.clock.pauseAt(new Date('2026-10-22T17:00:01Z'));
      await page.setContent(html, {waitUntil:'load'});
      await page.waitForFunction(()=>document.getElementById('xsm-safety-image').naturalWidth===612);
      assert.equal(await page.locator('#xsm-days').textContent(), '21');
      await page.evaluate(()=>{window.EmbedInit();window.EmbedInit();});
      await page.clock.runFor(29999);
      assert.equal(await page.locator('#xsm-safety-panel').getAttribute('aria-hidden'),'true');
      await page.clock.runFor(801);
      assert.equal(await page.locator('#xsm-safety-panel').getAttribute('aria-hidden'),'false');
      assert.equal(await page.locator('#xsm-counter-panel').evaluate(e=>e.style.transform),'translateX(-100%)');
      const dimensions=await page.locator('#xsm-safety-image').evaluate(e=>({width:e.clientWidth,height:e.clientHeight,fit:getComputedStyle(e).objectFit}));
      assert.deepEqual(dimensions,{width,height,fit:'contain'});
      assert.equal(await page.locator('#xsm-accident-counter').evaluate(e=>getComputedStyle(e).overflow),'hidden');
      await page.clock.runFor(5999);
      assert.equal(await page.locator('#xsm-safety-panel').getAttribute('aria-hidden'),'false');
      await page.clock.runFor(801);
      assert.equal(await page.locator('#xsm-counter-panel').getAttribute('aria-hidden'),'false');
      assert.equal(await page.locator('#xsm-safety-panel').evaluate(e=>e.style.transform),'translateX(-100%)');
      assert.deepEqual(errors,[]);
      await page.close();
    }
    console.log('Chromium: 30s counter / 6s safety image, repeat and responsive containment verified');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
