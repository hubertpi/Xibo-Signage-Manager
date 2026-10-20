"""Responsive SVG text safety counter for Xibo 4.5 Embedded widgets."""
import datetime as dt
import html
WIDGET_NAME = "XSM - Accident Counter"
LEGACY_WIDGET_NAME = "Days Since Last Incident"
COUNTER_STYLE = """*{box-sizing:border-box}html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:transparent!important}#xsm-accident-counter{width:100%;height:100%;overflow:hidden;display:flex;align-items:center;justify-content:center;background:transparent}"""
COUNTER_SCRIPT = r'''<script>
(function(){var started=false;
function day(s){var m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(s||'');if(!m)return NaN;var u=Date.UTC(+m[1],+m[2]-1,+m[3]),d=new Date(u);return(d.getUTCFullYear()===+m[1]&&d.getUTCMonth()===+m[2]-1&&d.getUTCDate()===+m[3])?u/86400000:NaN;}
function today(){var p=new Intl.DateTimeFormat('en-US',{timeZone:'America/Chicago',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());var o={};for(var i=0;i<p.length;i++)o[p[i].type]=p[i].value;return o.year+'-'+o.month+'-'+o.day;}
function update(){var b=document.getElementById('xsm-accident-counter'),t=document.getElementById('xsm-days');if(!b||!t)return;var n=day(today())-day(b.getAttribute('data-last-accident'));t.textContent=isFinite(n)&&n>=0?String(n):'—';t.setAttribute('font-size',String(n>=100000?130:n>=10000?170:235));}
function init(){if(started)return;started=true;update();window.setInterval(update,60000);}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();window.EmbedInit=init;
})();
</script>'''

def render_counter_markup(last_accident:dt.date)->str:
    d=html.escape(last_accident.isoformat(),quote=True)
    return f'''<div id="xsm-accident-counter" data-xsm-accident-counter="1" data-last-accident="{d}">
<svg viewBox="0 0 1120 400" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet" aria-label="Days since last accident" style="display:block;width:100%;height:100%;overflow:visible;">
<text id="xsm-days" x="560" y="225" fill="#0867b3" font-family="Arial,Helvetica,sans-serif" font-size="235" font-weight="700" text-anchor="middle">—</text>
<text x="560" y="343" fill="#0867b3" font-family="Arial,Helvetica,sans-serif" font-size="65" font-weight="500" text-anchor="middle">Days Since Last Accident</text>
</svg></div>'''

def get_widget_option(widget:dict,key:str):
    for opt in widget.get("widgetOptions",[]) or []:
        if opt.get("option")==key:return opt.get("value")
    return None

def build_widget_payload(last_accident:dt.date,widget:dict):
    return {"name":WIDGET_NAME,"useDuration":"1",
            "duration":str(widget.get("duration") or 3600),
            "enableStat":get_widget_option(widget,"enableStat") or "Inherit",
            "transparency":"1","scaleContent":"1","isPreNavigate":"0",
            "embedHtml":render_counter_markup(last_accident),
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
