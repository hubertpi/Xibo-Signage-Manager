"""Xibo media folder synchronizer and Home Assistant MQTT device.

Only media IDs created by this add-on are replaced or deleted.
"""
import datetime as dt
import hashlib
import json
import logging
import mimetypes
import pathlib
import threading
import time
from urllib.parse import urljoin

import requests
import paho.mqtt.client as mqtt
from counter_widget import counter_targets, render_counter_markup, get_widget_option, WIDGET_NAME, COUNTER_STYLE, COUNTER_SCRIPT
from layout_sync import sync_live_layout
from slideshow import rename_bulletins, sync_media, cleanup_assets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("xibo-signage")
OPTIONS = json.loads(pathlib.Path("/data/options.json").read_text())
STATE_FILE = pathlib.Path("/config/xibo_signage_manager_state.json")
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
STATE = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {"files": {}}
STATE.setdefault("files", {})
STATE.setdefault("controls", {})
STATE.setdefault("counter", {})
API = OPTIONS["xibo_url"].rstrip("/") + "/api/"
PATH = pathlib.Path(OPTIONS["bulletin_folder"])
ACCIDENT = pathlib.Path(OPTIONS["accident_file"])
TAG = OPTIONS["media_tag"]
PREFIX = "xibo_signage_manager"
DEVICE = {"identifiers": [PREFIX], "name": "Xibo Signage Manager",
          "manufacturer": "Community", "model": "Bulletin Synchronizer"}
LOCK = threading.RLock()
RUNTIME = {"connection": False, "status": "starting", "last_sync": None,
           "last_duration": None, "bulletins": 0, "errors": 0, "last_error": "",
           "auto": STATE["controls"].get("auto", True),
           "interval": int(STATE["controls"].get("interval", OPTIONS["sync_interval_minutes"]))}
DUE = threading.Event()
TOKEN = None
TOKEN_EXPIRY = 0
CLIENT = None


def save_state():
    temp = STATE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(STATE, indent=2))
    temp.replace(STATE_FILE)


def token():
    global TOKEN, TOKEN_EXPIRY
    if TOKEN and time.monotonic() < TOKEN_EXPIRY:
        return TOKEN
    response = requests.post(
        urljoin(API, "authorize/access_token"),
        data={"grant_type": "client_credentials",
              "client_id": OPTIONS["xibo_client_id"],
              "client_secret": OPTIONS["xibo_client_secret"]}, timeout=20)
    response.raise_for_status()
    data = response.json()
    TOKEN = data["access_token"]
    TOKEN_EXPIRY = time.monotonic() + max(30, int(data.get("expires_in", 3600)) - 90)
    return TOKEN


def api(method, route, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = "Bearer " + token()
    response = requests.request(method, urljoin(API, route.lstrip("/")),
                                headers=headers, timeout=120, **kwargs)
    if response.status_code == 401:
        global TOKEN_EXPIRY
        TOKEN_EXPIRY = 0
        headers["Authorization"] = "Bearer " + token()
        response = requests.request(method, urljoin(API, route.lstrip("/")),
                                    headers=headers, timeout=120, **kwargs)
    response.raise_for_status()
    return response.json() if response.content else {}


def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def scan():
    if not PATH.is_dir():
        raise FileNotFoundError(f"Bulletin directory not found: {PATH}")
    extensions = {".jpg", ".jpeg", ".png", ".gif", ".pdf"}
    return sorted([p for p in PATH.iterdir()
                   if p.is_file() and p.suffix.lower() in extensions],
                  key=lambda p: p.name.lower())


def is_stable(path):
    a = path.stat()
    if time.time() - a.st_mtime < 10:
        return False
    time.sleep(0.2)
    b = path.stat()
    return a.st_size == b.st_size and a.st_mtime_ns == b.st_mtime_ns


def media_id_from_upload(result, fallback=None):
    """Parse Xibo's POST /library response, including its nested files array."""
    if isinstance(result, dict) and "files" in result:
        items = result["files"]
    elif isinstance(result, list):
        items = result
    else:
        items = [result]
    if not isinstance(items, list):
        raise ValueError("Xibo returned a malformed media upload response")
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("error"):
            raise ValueError(f"Xibo rejected the upload: {item['error']}")
        for key in ("mediaId", "media_id", "id"):
            if item.get(key) is not None:
                return int(item[key])
        if isinstance(item.get("media"), dict) and item["media"].get("mediaId"):
            return int(item["media"]["mediaId"])
    if fallback is not None and items and all(
            isinstance(item, dict) and not item.get("error") for item in items):
        return int(fallback)
    raise ValueError(f"Xibo upload did not return a media ID: {str(result)[:300]}")


def managed_title(filename):
    """Namespace new imports so a pre-existing user's media name never blocks sync."""
    return "XSM - " + filename


def find_managed_media(items, filename):
    """Recover previous uploads lost when v0.2.0 misparsed the upload response.

    The library query is explicitly filtered by the add-on's management tag.
    Untagged media are never adopted or deleted by this add-on.
    """
    matching = [item for item in items if isinstance(item, dict)
                and item.get("name") in (filename, managed_title(filename))
                and item.get("mediaId") is not None]
    return max(matching, key=lambda item: int(item["mediaId"])) if matching else None


def file_md5(path):
    checksum = hashlib.md5()  # Match Xibo's non-security file checksum.
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def managed_library():
    result = api("GET", "library", params={"tags": TAG, "exactTags": 1})
    if not isinstance(result, list):
        raise ValueError(f"Xibo's managed media search returned an invalid response: {str(result)[:300]}")
    return result


def upload(path, old_id=None, title=None):
    data = {"name": title or managed_title(path.name), "tags": TAG}
    if old_id is not None:
        data.update({"oldMediaId": str(old_id),
                     "updateInLayouts": "1", "deleteOldRevisions": "1"})
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with path.open("rb") as stream:
        result = api("POST", "library", data=data,
                     files={"files": (path.name, stream, mime)})
    return media_id_from_upload(result, old_id)


def sync():
    start = time.monotonic()
    RUNTIME["status"] = "syncing"
    publish()
    problems = []
    try:
        records = rename_bulletins(PATH)
        RUNTIME["connection"] = True
        if records is None:
            # At least one upload is incomplete. Leave the previous layout
            # intact until all files are stable.
            RUNTIME["status"] = "waiting for file copy"
            return
        RUNTIME["bulletins"] = len(records)
        slides, used = sync_media(
            api, records, STATE, save_state,
            pathlib.Path("/config/xsm_pdf_pages"), TAG)
        try:
            sync_live_layout(api, OPTIONS, ACCIDENT, slides)
            cleanup_assets(api, STATE, used, save_state)
        except (LookupError, ValueError, OSError, requests.HTTPError, RuntimeError) as exc:
            LOG.warning("Live Xibo layout not yet synchronized: %s", exc)
            problems.append(f"Layout: {exc}")
        except Exception as exc:
            LOG.exception("Live Xibo layout synchronization failed")
            problems.append(f"Counter: {exc}")
        if problems:
            RUNTIME["errors"] += len(problems)
            RUNTIME["last_error"] = " | ".join(problems)[:500]
            RUNTIME["status"] = "warning"
        else:
            RUNTIME["last_error"] = ""
            RUNTIME["status"] = "idle"
            RUNTIME["last_sync"] = dt.datetime.now(dt.timezone.utc).isoformat()
    except Exception as exc:
        LOG.exception("Synchronization failed")
        RUNTIME["connection"] = False
        RUNTIME["errors"] += 1
        RUNTIME["last_error"] = str(exc)[:500]
        RUNTIME["status"] = "error"
    finally:
        RUNTIME["last_duration"] = round(time.monotonic() - start, 2)
        publish()



def fetch_counter_targets():
    layouts = api("GET", "layout", params={
        "layout": OPTIONS["counter_layout_name"],
        "showDrafts": 1,
        "embed": "regions,playlists,widgets"
    })
    if not isinstance(layouts, list):
        raise ValueError("Xibo layout search returned unexpected JSON")
    return counter_targets(layouts, OPTIONS["counter_layout_name"])


def sync_accident_counter():
    """Push accident DATE only; browser JavaScript counts days at midnight."""
    raw = ACCIDENT.read_text(encoding="utf-8").strip()
    last_accident = dt.date.fromisoformat(raw)
    if last_accident > dt.datetime.now().date():
        raise ValueError("last_accident.txt contains a future date")
    targets = fetch_counter_targets()
    if not targets:
        raise LookupError(
            "Import the updated 'Main Digital Bulletin - Xibo 4K Replica' layout "
            "with an 'XSM - Accident Counter' embedded widget before enabling date sync."
        )
    # Pick the newest matching top-level layout, never an unrelated widget.
    layout, widget = max(
        targets, key=lambda pair: (
            int(pair[0].get("parentId") or pair[0].get("layoutId") or 0),
            int(pair[0].get("layoutId") or 0)))
    widget_id = int(widget["widgetId"])
    root_id = int(layout.get("parentId") or layout["layoutId"])
    desired = {"date": last_accident.isoformat(), "widget_id": widget_id,
               "layout_id": root_id}
    if STATE.get("counter") == desired:
        return

    # A fully populated published widget needs no checkout or republish.
    # Never repeatedly churn layout versions when the file date is unchanged.
    expected_markup = render_counter_markup(last_accident)
    if (int(layout.get("publishedStatusId") or 0) == 1
            and not layout.get("parentId")
            and get_widget_option(widget, "name") == WIDGET_NAME
            and get_widget_option(widget, "embedHtml") == expected_markup
            and get_widget_option(widget, "embedStyle") == COUNTER_STYLE
            and get_widget_option(widget, "embedScript") == COUNTER_SCRIPT
            and not get_widget_option(widget, "embedJavaScript")):
        return

    # Published layouts need a draft checkout before editing in Xibo 4.5.
    if (int(layout.get("publishedStatusId") or 0) == 1
            and not layout.get("parentId")):
        api("PUT", f"layout/checkout/{root_id}", data={})
        targets = fetch_counter_targets()
        drafts = [(entry, w) for entry, w in targets
                  if int(entry.get("parentId") or 0) == root_id]
        if not drafts:
            raise RuntimeError("Xibo checked out the layout, but no editable counter widget was returned")
        layout, widget = max(drafts, key=lambda pair: int(pair[0]["layoutId"]))
        widget_id = int(widget["widgetId"])
        desired["widget_id"] = widget_id

    markup = render_counter_markup(last_accident)
    update = {"embedHtml": markup}
    if get_widget_option(widget, "name") != WIDGET_NAME:
        # Migrate the placeholder widget from the previously imported 4K layout.
        update.update({"name": WIDGET_NAME, "embedStyle": COUNTER_STYLE,
                       "embedScript": COUNTER_SCRIPT})
        LOG.info("Upgrading legacy placeholder widget %s in place", widget_id)
    api("PUT", f"playlist/widget/{widget_id}", data=update)
    api("PUT", f"layout/publish/{root_id}", data={"publishNow": "1"})
    STATE["counter"] = desired
    save_state()
    LOG.info("Updated Xibo embedded accident counter widget %s to %s (layout %s)",
             widget_id, desired["date"], root_id)

def accident_days():
    try:
        day = dt.date.fromisoformat(ACCIDENT.read_text().strip())
        # Calendar days in system-local time; set TZ on the host if necessary.
        return max(0, (dt.datetime.now().date() - day).days)
    except (ValueError, OSError):
        return None


def discovery(component, object_id, name, extra=None):
    payload = {"name": name, "unique_id": f"{PREFIX}_{object_id}",
               "state_topic": f"{PREFIX}/state", "value_template": "{{ value_json." +
               object_id + " }}", "device": DEVICE,
               "availability_topic": f"{PREFIX}/availability"}
    if extra:
        payload.update(extra)
    CLIENT.publish(f"homeassistant/{component}/{PREFIX}/{object_id}/config",
                   json.dumps(payload), qos=1, retain=True)


def setup_discovery():
    for field, name, extra in [
        ("status", "Sync Status", {}),
        ("last_sync", "Last Successful Sync", {"device_class": "timestamp"}),
        ("last_duration", "Last Sync Duration", {"unit_of_measurement": "s"}),
        ("bulletins", "Bulletin Count", {}),
        ("errors", "Sync Errors", {}),
        ("last_error", "Last Error", {"entity_category": "diagnostic"}),
        ("accident_days", "Days Since Last Accident", {}),
    ]:
        discovery("sensor", field, name, extra)
    discovery("binary_sensor", "connection", "Xibo Connection",
              {"payload_on": "True", "payload_off": "False", "device_class": "connectivity"})
    for component, field, name, extra in [
        ("number", "interval", "Sync Interval",
         {"min": 1, "max": 1440, "step": 1, "mode": "box",
          "command_topic": f"{PREFIX}/set/interval", "unit_of_measurement": "min"}),
        ("switch", "auto", "Auto Sync",
         {"command_topic": f"{PREFIX}/set/auto",
          "payload_on": "ON", "payload_off": "OFF",
          "state_on": "True", "state_off": "False"}),
    ]:
        discovery(component, field, name, extra)
    CLIENT.publish(f"homeassistant/button/{PREFIX}/sync_now/config",
                   json.dumps({"name": "Sync Now", "unique_id": PREFIX+"_sync_now",
                               "command_topic": f"{PREFIX}/set/sync_now",
                               "payload_press": "PRESS",
                               "device": DEVICE,
                               "availability_topic": f"{PREFIX}/availability"}),
                   qos=1, retain=True)


def publish():
    if CLIENT:
        values = dict(RUNTIME)
        values["accident_days"] = accident_days()
        CLIENT.publish(f"{PREFIX}/state", json.dumps(values), qos=1, retain=True)


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code != 0:
        LOG.error("MQTT connect failed: %s", reason_code)
        return
    client.publish(f"{PREFIX}/availability", "online", qos=1, retain=True)
    client.subscribe(f"{PREFIX}/set/#")
    setup_discovery()
    publish()


def on_message(client, userdata, message):
    command = message.topic.rsplit("/", 1)[-1]
    value = message.payload.decode().strip()
    with LOCK:
        if command == "sync_now" and value == "PRESS":
            DUE.set()
        elif command == "auto" and value in ("ON", "OFF"):
            RUNTIME["auto"] = value == "ON"
            STATE["controls"]["auto"] = RUNTIME["auto"]
            save_state()
            DUE.set()
            publish()
        elif command == "interval":
            try:
                RUNTIME["interval"] = min(1440, max(1, int(float(value))))
                STATE["controls"]["interval"] = RUNTIME["interval"]
                save_state()
                DUE.set()
                publish()
            except ValueError:
                LOG.warning("Invalid interval: %s", value)


def main():
    global CLIENT
    CLIENT = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=PREFIX)
    CLIENT.will_set(f"{PREFIX}/availability", "offline", qos=1, retain=True)
    username = OPTIONS.get("mqtt_username")
    if username:
        CLIENT.username_pw_set(username, OPTIONS.get("mqtt_password", ""))
    CLIENT.on_connect = on_connect
    CLIENT.on_message = on_message
    CLIENT.connect_async(OPTIONS["mqtt_host"], int(OPTIONS["mqtt_port"]))
    CLIENT.loop_start()
    LOG.info("Watching %s, managing tag %s", PATH, TAG)
    DUE.set()
    next_poll = 0.0
    while True:
        wait = max(0, next_poll - time.monotonic()) if RUNTIME["auto"] else 2.0
        fired = DUE.wait(timeout=wait)
        DUE.clear()
        if fired or (RUNTIME["auto"] and time.monotonic() >= next_poll):
            with LOCK:
                sync()
                next_poll = time.monotonic() + RUNTIME["interval"] * 60
        else:
            publish()


if __name__ == "__main__":
    main()
