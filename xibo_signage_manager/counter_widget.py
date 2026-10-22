"""Responsive SVG text safety counter for Xibo 4.5 Embedded widgets."""
import datetime as dt
import html
import hashlib
import logging
from pathlib import Path
WIDGET_NAME = "XSM - Accident Counter"
LEGACY_WIDGET_NAME = "Days Since Last Incident"
COUNTER_STYLE = """*{box-sizing:border-box}html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:transparent!important}#xsm-accident-counter{position:relative;width:100%;height:100%;overflow:hidden;background:transparent;color:#0867b3}.xsm-counter-panel{position:absolute;inset:0;width:100%;height:100%;display:flex;align-items:center;justify-content:center;transform:translateX(-100%);transition:none;will-change:transform}#xsm-counter-panel{transform:translateX(0)}#xsm-safety-image{display:block;width:100%;height:100%;object-fit:contain}@media(prefers-reduced-motion:reduce){.xsm-counter-panel{transition-duration:0ms!important}}"""
COUNTER_SCRIPT = r'''<script>
(function(){var started=false;
function day(s){var m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(s||'');if(!m)return NaN;var u=Date.UTC(+m[1],+m[2]-1,+m[3]),d=new Date(u);return(d.getUTCFullYear()===+m[1]&&d.getUTCMonth()===+m[2]-1&&d.getUTCDate()===+m[3])?u/86400000:NaN;}
function today(){var p=new Intl.DateTimeFormat('en-US',{timeZone:'America/Chicago',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());var o={};for(var i=0;i<p.length;i++)o[p[i].type]=p[i].value;return o.year+'-'+o.month+'-'+o.day;}
function update(){var b=document.getElementById('xsm-accident-counter'),t=document.getElementById('xsm-days');if(!b||!t)return;var n=day(today())-day(b.getAttribute('data-last-accident'));t.textContent=isFinite(n)&&n>=0?String(n):'—';t.setAttribute('font-size',String(n>=100000?130:n>=10000?170:235));}
function rotate(){var panels=[document.getElementById('xsm-counter-panel'),document.getElementById('xsm-safety-panel')],img=document.getElementById('xsm-safety-image'),current=0,timer,stopped=false;if(!panels[0]||!panels[1]||!img)return;
function schedule(){timer=window.setTimeout(next,current===0?30000:6000);}
function next(){if(stopped)return;var outgoing=panels[current],incoming=panels[1-current];incoming.style.transition='none';incoming.style.transform='translateX(-100%)';incoming.offsetWidth;outgoing.style.transition=incoming.style.transition='transform 800ms ease-in-out';outgoing.style.transform='translateX(100%)';incoming.style.transform='translateX(0)';outgoing.setAttribute('aria-hidden','true');incoming.setAttribute('aria-hidden','false');current=1-current;timer=window.setTimeout(function(){outgoing.style.transition='none';outgoing.style.transform='translateX(-100%)';schedule();},800);}
function ready(){if(stopped||!img.naturalWidth)return;schedule();}if(img.complete)ready();else img.addEventListener('load',ready,{once:true});window.addEventListener('pagehide',function(){stopped=true;window.clearTimeout(timer);},{once:true});}
function init(){if(started)return;started=true;update();window.setInterval(update,60000);rotate();}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();window.EmbedInit=init;
})();
</script>'''

SAFETY_TAG = "xsm_counter_assets"


def ensure_safety_media(api):
    """Reuse the bundled image in Xibo's library; never inline it in audit text."""
    image = Path(__file__).with_name('assets') / 'safety-first.jpg'
    digest = hashlib.sha256(image.read_bytes()).hexdigest()[:16]
    title = f'XSM - Safety First - {digest}'
    items = api('GET', 'library', params={'tags': SAFETY_TAG, 'exactTags': 1})
    if not isinstance(items, list):
        raise ValueError('Xibo safety image search returned invalid JSON')
    for item in items:
        if item.get('name') == title and str(item.get('retired', 0)) == '0':
            media_id = int(item.get('mediaId') or 0)
            if media_id > 0:
                return media_id
    with image.open('rb') as stream:
        result = api('POST', 'library', data={'name': title, 'tags': SAFETY_TAG},
                     files={'files': (image.name, stream, 'image/jpeg')})
    uploaded = result.get('files', [result]) if isinstance(result, dict) else result
    if not isinstance(uploaded, list):
        raise ValueError('Xibo safety image upload returned invalid JSON')
    for item in uploaded:
        if not isinstance(item, dict) or item.get('error'):
            raise ValueError('Xibo rejected the safety image upload')
    media_id = next((int(item[key]) for item in uploaded
                     for key in ('mediaId', 'media_id', 'id') if item.get(key)), 0)
    if media_id <= 0:
        raise ValueError('Xibo safety image upload did not provide a media ID')
    logging.getLogger('xibo-signage').info('Uploaded Safety First library image %s', media_id)
    return media_id

def render_counter_markup(last_accident:dt.date, safety_media_id=None)->str:
    d=html.escape(last_accident.isoformat(),quote=True)
    media_id = int(safety_media_id or 0)
    source = f"[[mediaId={media_id}]]" if media_id > 0 else ""
    dependency = f"[{media_id}]" if media_id > 0 else ""
    return f'''<div id="xsm-accident-counter" data-xsm-accident-counter="1" data-last-accident="{d}">
<div id="xsm-counter-panel" class="xsm-counter-panel" aria-hidden="false">
<svg viewBox="0 0 1120 400" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet" aria-label="Days since last accident" style="display:block;width:100%;height:100%;overflow:visible;">
<text id="xsm-days" x="560" y="225" fill="#0867b3" font-family="Arial,Helvetica,sans-serif" font-size="235" font-weight="700" text-anchor="middle">—</text>
<text x="560" y="343" fill="#0867b3" font-family="Arial,Helvetica,sans-serif" font-size="65" font-weight="500" text-anchor="middle">Days Since Last Accident</text>
</svg></div>
<div id="xsm-safety-panel" class="xsm-counter-panel" aria-hidden="true"><img id="xsm-safety-image" src="{source}" data-library-ref="{dependency}" alt="Safety First"></div></div>'''

def get_widget_option(widget:dict,key:str):
    for opt in widget.get("widgetOptions",[]) or []:
        if opt.get("option")==key:return opt.get("value")
    return None

def build_widget_payload(last_accident:dt.date,widget:dict,safety_media_id):
    return {"name":WIDGET_NAME,"useDuration":"1",
            "duration":str(widget.get("duration") or 3600),
            "enableStat":get_widget_option(widget,"enableStat") or "Inherit",
            "transparency":"1","scaleContent":"1","isPreNavigate":"0",
            "embedHtml":render_counter_markup(last_accident,safety_media_id),
            "embedStyle":COUNTER_STYLE,"embedJavaScript":"","embedScript":COUNTER_SCRIPT}

def widget_needs_update(widget:dict,payload:dict):
    return any((get_widget_option(widget,k) or "")!=payload[k]
        for k in ("name","embedHtml","embedStyle","embedScript","embedJavaScript"))

def counter_targets(layouts:list,target_name:str):
    targets=[]
    for layout in layouts:
        if layout.get("layout")!=target_name:continue
        for region in layout.get("regions") or []:
            playlists=[region.get("regionPlaylist"),region.get("playlist")]
            if isinstance(region.get("playlists"),list):playlists+=region["playlists"]
            for playlist in playlists:
                if not isinstance(playlist,dict):continue
                for widget in playlist.get("widgets") or []:
                    name=get_widget_option(widget,"name")
                    markup=get_widget_option(widget,"embedHtml") or ""
                    if widget.get("type")=="embedded" and (name in (WIDGET_NAME,LEGACY_WIDGET_NAME)
                       or 'data-xsm-accident-counter="1"' in markup):
                        targets.append((layout,widget))
    return targets
