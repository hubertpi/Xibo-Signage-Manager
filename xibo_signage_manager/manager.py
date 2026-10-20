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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("xibo-signage")
OPTIONS = json.loads(pathlib.Path("/data/options.json").read_text())
STATE_FILE = pathlib.Path("/config/xibo_signage_manager_state.json")
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
STATE = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {"files": {}}
STATE.setdefault("files", {})
STATE.setdefault("controls", {})
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
    """Xibo responses can be objects or collections, depending on API config."""
    items = result if isinstance(result, list) else [result]
    for item in items:
        if isinstance(item, dict):
            for key in ("mediaId", "media_id", "id"):
                if item.get(key) is not None:
                    return int(item[key])
            if isinstance(item.get("media"), dict) and item["media"].get("mediaId"):
                return int(item["media"]["mediaId"])
    if fallback is not None:
        return int(fallback)
    raise ValueError(f"Xibo upload did not return a media ID: {str(result)[:300]}")


def upload(path, old_id=None):
    data = {"name": path.name, "tags": TAG}
    if old_id is not None:
        data.update({"oldMediaId": str(old_id),
                     "updateInLayouts": "1", "deleteOldRevisions": "1"})
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with path.open("rb") as src:
        result = api("POST", "library", data=data,
                     files={"files": (path.name, src, mime)})
    return media_id_from_upload(result, old_id)


def sync():
    start = time.monotonic()
    RUNTIME["status"] = "syncing"
    publish()
    problems = []
    try:
        api("GET", "library", params={"mediaId": 0})
        RUNTIME["connection"] = True
        files = scan()
        RUNTIME["bulletins"] = len(files)
        present = set()
        for path in files:
            present.add(path.name)
            try:
                if not is_stable(path):
                    LOG.info("Waiting for completed copy: %s", path.name)
                    continue
                digest = file_hash(path)
                prior = STATE["files"].get(path.name)
                if prior and prior.get("sha256") == digest:
                    continue
                old_id = prior.get("media_id") if prior else None
                new_id = upload(path, old_id)
                STATE["files"][path.name] = {"sha256": digest, "media_id": new_id}
                save_state()
                action = "Replaced" if old_id else "Imported"
                LOG.info("%s %s: media %s -> %s", action, path.name, old_id, new_id)
            except Exception as exc:
                LOG.exception("Import/update failed for %s", path.name)
                problems.append(f"{path.name}: {exc}")
        for missing in sorted(set(STATE["files"]) - present):
            media_id = STATE["files"][missing].get("media_id")
            try:
                if media_id is not None:
                    # Only IDs previously uploaded and recorded by this add-on.
                    api("DELETE", f"library/{int(media_id)}",
                        data={"forceDelete": "1", "purge": "1"})
                del STATE["files"][missing]
                save_state()
                LOG.info("Deleted removed bulletin %s (media %s)", missing, media_id)
            except Exception as exc:
                LOG.exception("Delete failed for %s", missing)
                problems.append(f"Delete {missing}: {exc}")
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
