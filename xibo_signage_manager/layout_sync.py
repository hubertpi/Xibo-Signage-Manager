"""Batch updates for one 4K Xibo layout; avoid repeated draft/publish cycles."""
import datetime as dt
import logging
from zoneinfo import ZoneInfo
from counter_widget import (
    WIDGET_NAME as COUNTER_NAME, LEGACY_WIDGET_NAME as LEGACY_COUNTER,
    get_widget_option, build_widget_payload, widget_needs_update
)
from calendar_widget import (
    WIDGET_NAME as CALENDAR_NAME, LEGACY_WIDGET_NAME as LEGACY_CALENDAR,
    events_from_ics, build_calendar_payload
)

LOG=logging.getLogger("xibo-signage")
def _playlist(region):
    p=region.get("regionPlaylist") or region.get("playlist")
    if isinstance(p,dict):return p
    for entry in region.get("playlists") or []:
        if isinstance(entry,dict) and entry.get("regionId"):return entry
    return None

def _role(region,widget=None):
    name=(region.get("name") or "").lower()
    if "bulletin slideshow" in name:return "slideshow"
    if "events" in name and "birthdays" in name:return "calendar"
    if "accident" in name or "incident" in name:return "counter"
    if widget:
        title=get_widget_option(widget,"name") or ""
        markup=get_widget_option(widget,"embedHtml") or ""
        if title in (COUNTER_NAME,LEGACY_COUNTER) or 'data-xsm-accident-counter="1"' in markup:
            return "counter"
        if title in (CALENDAR_NAME,LEGACY_CALENDAR) or 'data-xsm-calendar="1"' in markup:
            return "calendar"
        if "Bulletin Slideshow" in title:return "slideshow"
    return None

def find_parts(layout):
    found={}
    for r in layout.get("regions") or []:
        p=_playlist(r)
        if not p:continue
        role=_role(r)
        if role and role not in found:found[role]=(r,p)
        for w in p.get("widgets") or []:
            role=_role(r,w)
            if role and role not in found:found[role]=(r,p)
    return found

def _widget(parts,role):
    region,playlist=parts[role]
    for w in playlist.get("widgets") or []:
        if _role(region,w)==role or (
            role=="counter" and get_widget_option(w,"name") in (COUNTER_NAME,LEGACY_COUNTER)
        ) or (
            role=="calendar" and get_widget_option(w,"name") in (CALENDAR_NAME,LEGACY_CALENDAR)
        ):
            return w
    if role in ("counter","calendar") and len(playlist.get("widgets") or [])==1:
        w=playlist["widgets"][0]
        if w.get("type")=="embedded":return w
    return None

def _get_layouts(api,name):
    layouts=api("GET","layout",params={
        "layout":name,"showDrafts":1,"embed":"regions,playlists,widgets"})
    if not isinstance(layouts,list):raise ValueError("Xibo layout search returned invalid JSON")
    return [x for x in layouts if x.get("layout")==name]

def _preferred(layouts):
    # Prefer a draft for continued work; otherwise a published layout.
    return max(layouts,key=lambda l:(
        int(l.get("parentId") or l.get("layoutId") or 0),
        1 if l.get("parentId") else 0,
        int(l.get("layoutId") or 0)))

def _matches(widget,payload):
    if not widget:return False
    return not widget_needs_update(widget,payload)

def _update_widget(api,widget,payload,description):
    api("PUT",f"playlist/widget/{int(widget['widgetId'])}",data=payload)
    LOG.info("Updated %s HTML widget %s",description,widget["widgetId"])

def sync_live_layout(api,options,accident):
    name=options["counter_layout_name"]
    layouts=_get_layouts(api,name)
    if not layouts:raise LookupError(f"Cannot find Xibo layout named {name!r}")
    layout=_preferred(layouts)
    parts=find_parts(layout)
    missing={"counter","calendar","slideshow"}-set(parts)
    if missing:raise LookupError(f"Xibo layout {name!r} missing managed regions: {', '.join(sorted(missing))}")

    day=dt.date.fromisoformat(accident.read_text(encoding="utf-8").strip())
    if day>dt.datetime.now(ZoneInfo("America/Chicago")).date():
        raise ValueError("Accident date cannot be in the future")

    events=None;birthdays=None
    for key,title in (("events_ics_url","Events"),("birthdays_ics_url","Birthdays")):
        url=(options.get(key) or "").strip()
        try:
            value=events_from_ics(url)
        except Exception as exc:
            # Never replace working calendar entries with empty data on network failure.
            LOG.warning("%s calendar download/parse failed: %s",title,
                        str(exc).split("?")[0][:200])
            raise RuntimeError(f"{title} ICS download failed; prior calendar retained") from None
        if key=="events_ics_url":events=value
        else:birthdays=value

    counter=_widget(parts,"counter")
    calendar=_widget(parts,"calendar")
    if not counter or not calendar:
        raise LookupError("Expected an Embedded accident counter and Events/Birthdays widget")
    cp=build_widget_payload(day,counter)
    calp=build_calendar_payload(events,birthdays,calendar,get_widget_option)
    need_counter=widget_needs_update(counter,cp)
    need_calendar=widget_needs_update(calendar,calp)
    r,p=parts["slideshow"]
    if not p.get("playlistId"):raise LookupError("Slideshow region playlist ID unavailable")
    dynamic=(int(p.get("isDynamic") or 0)==1
             and (p.get("filterMediaTags") or "")==options["media_tag"])
    need_playlist=not dynamic or any(
        get_widget_option(w,"name")=="Bulletin Slideshow (replace sample with media)"
        for w in p.get("widgets") or []
    )
    if not (need_counter or need_calendar or need_playlist):
        return False

    root=int(layout.get("parentId") or layout["layoutId"])
    if not layout.get("parentId") and int(layout.get("publishedStatusId") or 0)==1:
        api("PUT",f"layout/checkout/{root}",data={})
        candidates=[x for x in _get_layouts(api,name)
                    if int(x.get("parentId") or 0)==root]
        if not candidates:
            raise RuntimeError("Checkout succeeded but API did not return an editable draft")
        layout=_preferred(candidates)
        parts=find_parts(layout)
        counter=_widget(parts,"counter")
        calendar=_widget(parts,"calendar")
        cp=build_widget_payload(day,counter)
        calp=build_calendar_payload(events,birthdays,calendar,get_widget_option)
        need_counter=widget_needs_update(counter,cp)
        need_calendar=widget_needs_update(calendar,calp)
        r,p=parts["slideshow"]
        dynamic=(int(p.get("isDynamic") or 0)==1
                 and (p.get("filterMediaTags") or "")==options["media_tag"])
        need_playlist=not dynamic or any(
            get_widget_option(w,"name")=="Bulletin Slideshow (replace sample with media)"
            for w in p.get("widgets") or []
        )

    if need_playlist:
        widgets=p.get("widgets") or []
        for w in widgets:
            if w.get("type")=="embedded" and (
                get_widget_option(w,"name")=="Bulletin Slideshow (replace sample with media)"
                or "Sample slide" in (get_widget_option(w,"embedHtml") or "")
            ):
                api("DELETE",f"playlist/widget/{int(w['widgetId'])}")
                LOG.info("Removed sample bulletin widget %s",w["widgetId"])
            elif not dynamic:
                raise RuntimeError("Refusing to replace an unexpected slideshow widget")
        api("PUT",f"playlist/{int(p['playlistId'])}",data={
            "name":"XSM - Bulletin Slideshow","isDynamic":"1",
            "filterMediaTag":options["media_tag"],"exactTags":"1",
            "logicalOperator":"OR","maxNumberOfItems":"100",
            "folderId":str(p.get("folderId") or 1),
            "enableStat":"Inherit"
        })
        LOG.info("Connected slideshow region playlist %s to managed tag %s",
                 p["playlistId"],options["media_tag"])

    if need_counter:_update_widget(api,counter,cp,"accident counter")
    if need_calendar:_update_widget(api,calendar,calp,"Events/Birthdays")

    api("PUT",f"layout/publish/{root}",data={"publishNow":"1"})
    LOG.info("Published Xibo layout %s with live bulletin, counter, and calendar configuration",name)
    return True
