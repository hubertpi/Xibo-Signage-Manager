"""Execute the shipped widget script against deterministic timers and DOM state."""
import base64
from datetime import date
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'xibo_signage_manager'))
from counter_widget import COUNTER_SCRIPT, render_counter_markup


class SafetyAssetTests(unittest.TestCase):
    def test_embedded_image_matches_bundled_original(self):
        markup = render_counter_markup(date(2026, 10, 1))
        encoded = re.search(r'src="data:image/jpeg;base64,([^"]+)"', markup).group(1)
        self.assertEqual(base64.b64decode(encoded),
                         (ROOT / 'xibo_signage_manager/assets/safety-first.jpg').read_bytes())
        self.assertIn('aria-hidden="true"', markup)


@unittest.skipUnless(shutil.which('node'), 'requires Node to execute the actual widget script')
class RotationTests(unittest.TestCase):
    def test_timing_direction_duplicate_init_failure_and_cleanup(self):
        script = COUNTER_SCRIPT.removeprefix('<script>').removesuffix('</script>')
        harness = r'''
const assert=require('assert');
function fixture(imageReady=true, imageComplete=true){
  let now=0,serial=0,timers=new Map(),intervals=[],handlers={};
  function element(){return {style:{},attrs:{},offsetWidth:1120,
    setAttribute(k,v){this.attrs[k]=v;},getAttribute(k){return this.attrs[k];}};}
  const ids={};for(const id of ['xsm-accident-counter','xsm-days','xsm-counter-panel','xsm-safety-panel','xsm-safety-image'])ids[id]=element();
  ids['xsm-accident-counter'].attrs['data-last-accident']='2026-10-01';
  const image=ids['xsm-safety-image'];image.complete=imageComplete;image.naturalWidth=imageReady?612:0;
  image.addEventListener=(name,fn)=>handlers['image:'+name]=fn;
  const window={setTimeout(fn,delay){let id=++serial;timers.set(id,{fn,at:now+delay});return id;},
    clearTimeout(id){timers.delete(id);},setInterval(fn,delay){intervals.push({fn,delay});},
    addEventListener(name,fn){handlers[name]=fn;}};
  const document={readyState:'complete',getElementById(id){return ids[id];}};
  new Function('window','document',SCRIPT)(window,document);
  function advance(ms){let target=now+ms;for(;;){let entry=[...timers].sort((a,b)=>a[1].at-b[1].at)[0];if(!entry||entry[1].at>target)break;now=entry[1].at;timers.delete(entry[0]);entry[1].fn();}now=target;}
  return {ids,window,handlers,timers,intervals,advance};
}
const f=fixture();f.window.EmbedInit();f.window.EmbedInit();
assert.equal(f.intervals.length,1);assert.equal(f.intervals[0].delay,60000);
assert.equal(f.timers.size,1);assert.match(f.ids['xsm-days'].textContent,/^\d+$/);
f.advance(29999);assert.equal(f.ids['xsm-safety-panel'].attrs['aria-hidden'],undefined);
f.advance(1);assert.equal(f.ids['xsm-counter-panel'].style.transform,'translateX(100%)');
assert.equal(f.ids['xsm-safety-panel'].style.transform,'translateX(0)');
assert.equal(f.ids['xsm-safety-panel'].attrs['aria-hidden'],'false');
f.advance(800);assert.equal(f.ids['xsm-counter-panel'].style.transform,'translateX(-100%)');
f.advance(5999);assert.equal(f.ids['xsm-safety-panel'].attrs['aria-hidden'],'false');
f.advance(1);assert.equal(f.ids['xsm-counter-panel'].style.transform,'translateX(0)');
assert.equal(f.ids['xsm-safety-panel'].style.transform,'translateX(100%)');
f.advance(800);assert.equal(f.ids['xsm-safety-panel'].style.transform,'translateX(-100%)');
f.advance(30000);assert.equal(f.ids['xsm-safety-panel'].attrs['aria-hidden'],'false');
f.handlers.pagehide();assert.equal(f.timers.size,0);
const failed=fixture(false);failed.advance(200000);assert.equal(failed.timers.size,0);
assert.match(failed.ids['xsm-days'].textContent,/^\d+$/);
const loading=fixture(false,false);assert.equal(loading.timers.size,0);
loading.ids['xsm-safety-image'].naturalWidth=612;loading.handlers['image:load']();
assert.equal(loading.timers.size,1);loading.advance(30000);
assert.equal(loading.ids['xsm-safety-panel'].attrs['aria-hidden'],'false');
console.log('counter rotation verified');
'''.replace('SCRIPT', json.dumps(script), 1)
        result = subprocess.run(['node', '-e', harness], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
