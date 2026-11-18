"""Independent folder/calendar feeds for layouts sharing the main design."""
import hashlib
import logging
from pathlib import Path

from layout_sync import _get_layouts, sync_live_layout
from slideshow import rename_bulletins, sync_media, cleanup_assets

LOG = logging.getLogger("xibo-signage")


def layout_sources(options):
    """Validate all sources before modifying folders, layouts, or library media."""
    sources = [{"name": options["counter_layout_name"],
                "folder": Path(options["bulletin_folder"]).resolve(),
                "options": options, "scope": None}]
    names = {sources[0]["name"].casefold()}
    folders = {sources[0]["folder"]}
    for entry in options.get("additional_layouts") or []:
        name = (entry.get("name") or "").strip()
        raw_folder = (entry.get("bulletin_folder") or "").strip()
        if not name or not raw_folder or not Path(raw_folder).is_absolute():
            raise ValueError("Each additional layout needs a name and an absolute bulletin_folder")
        folder = Path(raw_folder).resolve()
        if name.casefold() in names or folder in folders:
            raise ValueError("Managed layouts must have distinct names and bulletin folders")
        names.add(name.casefold())
        folders.add(folder)
        # A layout rename must not discard its existing media ownership records.
        scope = hashlib.sha256(str(folder).encode()).hexdigest()[:16]
        selected = dict(options, counter_layout_name=name, bulletin_folder=str(folder),
                        media_tag=f"{options['media_tag']}_{scope}",
                        events_ics_url=entry.get("events_ics_url") or "")
        # Omission inherits the shared birthdays feed; an explicit empty value disables it.
        if "birthdays_ics_url" in entry:
            selected["birthdays_ics_url"] = entry["birthdays_ics_url"]
        sources.append({"name": name, "folder": folder,
                        "options": selected, "scope": scope})
    return sources


def ensure_layout(api, name, template_name):
    """Copy the published main design once; never change its schedule or widgets."""
    existing = _get_layouts(api, name)
    if existing:
        roots = {int(item.get("parentId") or item["layoutId"]) for item in existing}
        if len(roots) != 1:
            raise ValueError(f"More than one Xibo layout is named {name!r}; use a unique name")
        return
    templates = [item for item in _get_layouts(api, template_name)
                 if not item.get("parentId") and int(item.get("publishedStatusId") or 0) == 1]
    if len(templates) != 1:
        raise LookupError(f"A single published template named {template_name!r} is required")
    api("POST", f"layout/copy/{int(templates[0]['layoutId'])}", data={
        "name": name, "description": "Independent slideshow and calendar managed by XSM",
        "copyMediaFiles": "0",
    })
    LOG.info("Copied Xibo layout %s as %s", template_name, name)


def sync_sources(api, options, state, save_state, accident, cache_root):
    """Sync every feed, retaining failed feeds and continuing successful ones."""
    sources = layout_sources(options)
    result = {"files": 0, "slides": 0, "pending": False, "problems": [], "connected": False}
    for source in sources:
        name, folder, scope = source["name"], source["folder"], source["scope"]
        try:
            LOG.info("Synchronizing layout %s from %s", name, folder)
            if scope:
                # Create only the explicitly configured leaf; don't hide a missing share mount.
                folder.mkdir(exist_ok=True)
            records = rename_bulletins(folder)
            if records is None:
                result["pending"] = True
                continue
            source_state = state if scope is None else state.setdefault("layout_sources", {}).setdefault(scope, {})
            cache = Path(cache_root) if scope is None else Path(cache_root) / scope
            prefix = "XSM - " if scope is None else f"XSM [{scope}] - "
            slides, used = sync_media(api, records, source_state, save_state, cache,
                                      source["options"]["media_tag"], title_prefix=prefix)
            result["connected"] = True
            result["files"] += len(records)
            result["slides"] += len(slides)
            if scope:
                ensure_layout(api, name, options["counter_layout_name"])
            sync_live_layout(api, source["options"], accident, slides)
            # Never purge this source's media until its updated layout is published.
            cleanup_assets(api, source_state, used, save_state)
            LOG.info("Layout %s synchronized: %d files, %d images/pages", name, len(records), len(slides))
        except Exception as exc:
            LOG.warning("Layout %s synchronization incomplete: %s", name, exc)
            result["problems"].append(f"{name}: {exc}")
    return result
