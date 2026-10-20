"""Build the Xibo Embedded widget body updated by the synchronizer."""
import datetime as dt
import html

WIDGET_NAME = "XSM - Accident Counter"
LEGACY_WIDGET_NAME = "Days Since Last Incident"
COUNTER_STYLE = """
*{box-sizing:border-box}
html,body{margin:0;width:100%;height:100%;background:transparent!important;overflow:hidden}
#xsm-accident-counter{width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;color:#0867b3;text-align:center;font-family:Arial,Helvetica,sans-serif}
#xsm-days{font-size:226px;font-weight:700;line-height:1;letter-spacing:-4px;white-space:nowrap;max-width:100%}
#xsm-counter-label{font-size:59px;font-weight:400;line-height:1.1;white-space:nowrap}
""".strip()
COUNTER_SCRIPT = r"""<script>
(function(){
  var timezone='America/Chicago',started=false;
  function chicagoDay(){
    var segments=new Intl.DateTimeFormat('en-US',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
    var p={};for(var i=0;i<segments.length;i++)p[segments[i].type]=segments[i].value;
    return [p.year,p.month,p.day].join('-');
  }
  function epochDay(s){
    var m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
    if(!m)return NaN;
    var ms=Date.UTC(+m[1],+m[2]-1,+m[3]),d=new Date(ms);
    if(d.getUTCFullYear()!==+m[1]||d.getUTCMonth()!==+m[2]-1||d.getUTCDate()!==+m[3])return NaN;
    return ms/86400000;
  }
  function update(){
    var box=document.getElementById('xsm-accident-counter');
    var count=document.getElementById('xsm-days');
    if(!box||!count)return;
    var days=epochDay(chicagoDay())-epochDay(box.getAttribute('data-last-accident'));
    count.textContent=Number.isFinite(days)&&days>=0?String(days):'—';
    var size=256;count.style.fontSize=size+'px';
    while(size>70&&count.scrollWidth>box.clientWidth-35){size-=5;count.style.fontSize=size+'px';}
  }
  function init(){if(started)return;started=true;update();setInterval(update,60000);}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
  else init();
  window.EmbedInit=init;
})();
</script>"""


def render_counter_markup(last_accident: dt.date) -> str:
    value = html.escape(last_accident.isoformat(), quote=True)
    return (
        '<div id="xsm-accident-counter" data-xsm-accident-counter="1" '
        f'data-last-accident="{value}">'
        '<div id="xsm-days" aria-label="Days since last accident">—</div>'
        '<div id="xsm-counter-label">Days Since Last Accident</div>'
        '</div>'
    )

def get_widget_option(widget: dict, key: str):
    for option in widget.get("widgetOptions", []):
        if option.get("option") == key:
            return option.get("value")
    return None

def counter_targets(layouts: list, target_name: str):
    """Find only widgets intentionally marked as this add-on's counter."""
    targets = []
    for layout in layouts:
        if layout.get("layout") != target_name:
            continue
        for region in layout.get("regions") or []:
            playlists = [region.get("regionPlaylist"), region.get("playlist")]
            if isinstance(region.get("playlists"), list):
                playlists += region["playlists"]
            for playlist in playlists:
                if not isinstance(playlist, dict):
                    continue
                for widget in playlist.get("widgets") or []:
                    name = get_widget_option(widget, "name")
                    markup = get_widget_option(widget, "embedHtml") or ""
                    if widget.get("type") == "embedded" and (
                        name in (WIDGET_NAME, LEGACY_WIDGET_NAME)
                        or 'data-xsm-accident-counter="1"' in markup
                    ):
                        targets.append((layout, widget))
    return targets
