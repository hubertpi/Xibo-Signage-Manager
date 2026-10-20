"""Convert ICS calendar feeds into Xibo's synchronized Events/Birthdays HTML."""
import datetime as dt
import html
from zoneinfo import ZoneInfo
import requests
from icalendar import Calendar
import recurring_ical_events

TZ=ZoneInfo("America/Chicago")
WIDGET_NAME="XSM - Events and Birthdays"
LEGACY_WIDGET_NAME="Events / Birthdays (10-second alternating)"
CAL_STYLE="""*{box-sizing:border-box}html,body{width:100%;height:100%;margin:0;padding:0;background:transparent!important;overflow:hidden;font-family:Verdana,Arial,sans-serif}
#xsm-calendar{position:relative;width:100%;height:100%;overflow:hidden;color:#090909}
.xsm-panel{position:absolute;left:0;top:0;width:100%;height:100%;transform:translateY(110%);background:transparent;display:flex;flex-direction:column}
.xsm-panel[data-panel="events"]{transform:translateY(0%)}
.xsm-panel.xsm-arriving{transition:transform 850ms ease;transform:translateY(0%)}
.xsm-panel.xsm-departing{transition:transform 850ms ease;transform:translateY(-110%)}
.xsm-heading{height:98px;min-height:98px;display:flex;align-items:center;justify-content:center;text-align:center;font-weight:700;font-size:58px;line-height:1.1}
.xsm-list{background:#fff;border-radius:24px;flex:1;overflow:hidden;padding:20px 36px 20px}
.xsm-item{padding:21px 8px 22px;border-bottom:2px solid #dedede}
.xsm-day{font-size:37px;font-weight:700;margin-bottom:8px}
.xsm-body{display:flex;gap:20px;align-items:flex-start;justify-content:flex-end;font-size:37px;font-weight:700;line-height:1.25}
.xsm-time{white-space:nowrap;font-size:35px}.xsm-name{flex:1;text-align:center}
.xsm-empty{padding:52px 12px;text-align:center;font-size:38px;color:#555}"""
CAL_SCRIPT=r'''<script>
(function(){var started=false,index=0;
function swap(){var panels=document.querySelectorAll('#xsm-calendar .xsm-panel');if(panels.length!==2)return;
var old=panels[index],next=panels[1-index];next.classList.remove('xsm-departing');next.style.transition='none';next.style.transform='translateY(110%)';void next.offsetHeight;next.style.transition='';old.classList.add('xsm-departing');next.classList.add('xsm-arriving');
window.setTimeout(function(){old.classList.remove('xsm-departing');old.style.transform='translateY(110%)';next.classList.remove('xsm-arriving');next.style.transform='translateY(0%)';},950);index=1-index;}
function init(){if(started)return;started=true;window.setInterval(swap,10000);}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();window.EmbedInit=init;
})();
</script>'''

def events_from_ics(url:str,days=90,limit=8,now=None):
    if not url:return None
    if not url.lower().startswith(("https://","http://")):
        raise ValueError("Calendar feed URL must start with http(s)")
    response=requests.get(url,timeout=25,headers={"User-Agent":"XiboSignageManager/0.4"})
    response.raise_for_status()
    if len(response.content)>5_000_000:
        raise ValueError("ICS response exceeds 5 MB")
    if b"BEGIN:VCALENDAR" not in response.content[:500]:
        raise ValueError("Calendar feed did not return an ICS VCALENDAR")
    cal=Calendar.from_ical(response.content)
    today=(now or dt.datetime.now(TZ)).astimezone(TZ).date()
    start=dt.datetime.combine(today,dt.time.min,tzinfo=TZ)
    end=start+dt.timedelta(days=days)
    occurrences=recurring_ical_events.of(cal).between(start,end)
    entries=[]
    for event in occurrences:
        if event.name!="VEVENT" or "DTSTART" not in event:continue
        start_value=event.decoded("DTSTART")
        if isinstance(start_value,dt.datetime):
            local=(start_value.replace(tzinfo=TZ) if start_value.tzinfo is None
                   else start_value.astimezone(TZ))
            day=local.date()
            time=local.strftime("%I:%M%p").lstrip("0").lower()
        elif isinstance(start_value,dt.date):
            day=start_value
            time=""
        else:continue
        if not today<=day<end.date():continue
        title=str(event.get("SUMMARY") or "Untitled event").strip()[:180]
        if title:entries.append({"date":day.isoformat(),"time":time,"name":title})
    entries.sort(key=lambda e:(e["date"],e["time"],e["name"].casefold()))
    unique=set()
    result=[]
    for e in entries:
        key=(e["date"],e["time"],e["name"])
        if key in unique:continue
        unique.add(key);result.append(e)
        if len(result)>=limit:break
    return result

def _rows(items,missing_message):
    if items is None:return '<div class="xsm-empty">'+html.escape(missing_message)+'</div>'
    if not items:return '<div class="xsm-empty">Nothing scheduled</div>'
    result=[]
    for event in items:
        day=dt.date.fromisoformat(event["date"]).strftime("%m/%d/%Y")
        time=html.escape(event.get("time") or "")
        time_tag=f'<span class="xsm-time">{time}</span>' if time else ""
        title=html.escape(event["name"],quote=True)
        result.append(f'<div class="xsm-item"><div class="xsm-day">{day}</div><div class="xsm-body">{time_tag}<span class="xsm-name">{title}</span></div></div>')
    return "".join(result)

def render_calendar(events,birthdays):
    return ('<div id="xsm-calendar" data-xsm-calendar="1">'
            '<div class="xsm-panel" data-panel="events"><div class="xsm-heading">Upcoming Events</div>'
            '<div class="xsm-list" id="xsm-events">'+_rows(events,"Events calendar not connected")+'</div></div>'
            '<div class="xsm-panel" data-panel="birthdays"><div class="xsm-heading">Birthdays</div>'
            '<div class="xsm-list" id="xsm-birthdays">'+_rows(birthdays,"Birthdays calendar not connected")+'</div></div></div>')

def build_calendar_payload(events,birthdays,widget,read_option):
    return {"name":WIDGET_NAME,"useDuration":"1",
            "duration":str(widget.get("duration") or 3600),
            "enableStat":read_option(widget,"enableStat") or "Inherit",
            "transparency":"1","scaleContent":"1","isPreNavigate":"0",
            "embedHtml":render_calendar(events,birthdays),
            "embedStyle":CAL_STYLE,"embedScript":CAL_SCRIPT,"embedJavaScript":""}
