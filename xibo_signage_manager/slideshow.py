"""Deterministic folder-driven slideshow with PDF page images.
Source PDFs stay in the shared folder; rendered pages are cached under /config.
"""
import hashlib
import logging
import pathlib
import re
import subprocess
import time
import uuid

LOG = logging.getLogger("xibo-signage")
EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".pdf"}
NAME = re.compile(r"^(\d{2,4})\s+-\s+(?:(\d{1,4})s\s+-\s+)?(.+)$", re.I)
DURATION = re.compile(r"^(\d{1,4})s\s+-\s+(.+)$", re.I)
DOC_FILE = "BULLETIN_UPLOAD_INSTRUCTIONS.txt"
DOC = """DIGITAL BULLETIN - FILE UPLOAD INSTRUCTIONS
===========================================

Drop JPG, JPEG, PNG, GIF or PDF files into this folder. The signage manager
will add a sequence number and a 10-second duration on its next sync.

STANDARD FILE NAME:  01 - 10s - Safety Meeting.pdf
                     02 - 15s - Company News.jpg
The first number sets the playback position. The 10s/15s sets playback time.
For PDFs, that many seconds is spent on EACH page. For images, it is total.
All newly uploaded files default to 10s. The manager always adds the prefix.

APPEND: Drop a plain file such as Birthday Photo.jpg in this folder.
        It is appended and renamed to NN - 10s - Birthday Photo.jpg.

INSERT / MOVE: Use FOUR digits for a one-time positioning request, e.g.
        0002 - 15s - New Bulletin.pdf
        On sync this becomes 02 - 15s - New Bulletin.pdf and the following
        slides shift down one number. Existing slides can be moved this way.
        Do not submit multiple four-digit moves in the same sync.

CHANGE TIME: Rename 03 - 10s - Safety.pdf to 03 - 20s - Safety.pdf.
             No four-digit number is needed if order should not change.

DELETE: Remove the file. Remaining files are renumbered on the next sync.

Please wait until file copying has finished before renaming. Leave this TXT
file in place; it is ignored by the slide importer. Do not upload an empty
file or multiple slides with exactly the same descriptive filename.
The originals stay in this folder; PDF page images are generated internally.
"""

def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def parse_name(name):
    p = pathlib.Path(name)
    m = NAME.match(p.stem)
    if m:
        pos, secs, original = m.groups()
        return (int(pos), len(pos) == 4, int(secs or 10), original + p.suffix)
    m = DURATION.match(p.stem)
    if m:
        secs, original = m.groups()
        return (None, False, int(secs), original + p.suffix)
    return (None, False, 10, name)

def rename_bulletins(folder):
    """Rename files safely in one transaction; recover interrupted renames."""
    import json
    folder = pathlib.Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError("Bulletin folder not found: " + str(folder))
    guide = folder / DOC_FILE
    if not guide.exists():
        guide.write_text(DOC, encoding="utf-8")
    journal = folder / ".xsm-rename-journal"
    if journal.exists():
        plan = json.loads(journal.read_text(encoding="utf-8"))
        for old, staged, _ in plan:
            if not (folder / staged).exists() and (folder / old).exists():
                (folder / old).rename(folder / staged)
        for _, staged, new in plan:
            if (folder / staged).exists():
                if (folder / new).exists():
                    raise RuntimeError("Rename recovery collision for " + new)
                (folder / staged).rename(folder / new)
        journal.unlink()
    paths = sorted((p for p in folder.iterdir()
                    if p.is_file() and p.suffix.lower() in EXTENSIONS),
                   key=lambda p:p.name.casefold())
    if any(time.time() - p.stat().st_mtime < 10 for p in paths):
        LOG.info("Bulletin copy is still in progress; renaming deferred")
        return None
    records, inserts, seen = [], [], set()
    for p in paths:
        pos, insert, secs, original = parse_name(p.name)
        if secs < 1 or secs > 3600:
            raise ValueError("Duration must be 1-3600 seconds: " + p.name)
        if original.casefold() in seen:
            raise ValueError("Duplicate descriptive bulletin filename: " + original)
        seen.add(original.casefold())
        entry = {"path":p, "pos":pos, "secs":secs, "original":original}
        (inserts if insert else records).append(entry)
    records.sort(key=lambda x:(x["pos"] is None,x["pos"] or 0,
                               x["path"].name.casefold()))
    if len(inserts) > 1:
        raise ValueError("Submit only one four-digit move per sync")
    for entry in inserts:
        records.insert(max(0,min(len(records),entry["pos"]-1)),entry)
    width = max(2,len(str(len(records))))
    plan = []
    for i,entry in enumerate(records,1):
        target = f"{i:0{width}d} - {entry['secs']}s - {entry['original']}"
        entry["desired_name"] = target
        if entry["path"].name != target:
            plan.append((entry["path"].name, ".xsm-stage-"+uuid.uuid4().hex, target))
    if plan:
        journal.write_text(json.dumps(plan),encoding="utf-8")
        for old,staged,_ in plan:
            (folder/old).rename(folder/staged)
        for _,staged,target in plan:
            (folder/staged).rename(folder/target)
        journal.unlink()
    for entry in records:
        entry["path"] = folder/entry["desired_name"]
        entry["digest"] = file_hash(entry["path"])
    return records

def pdf_pages(path,digest,cache_dir):
    """Render pages at the panel's 2608x2104 bounding size and cache by SHA."""
    cache = pathlib.Path(cache_dir)/digest
    cache.mkdir(parents=True,exist_ok=True)
    info = subprocess.run(["pdfinfo",str(path)],capture_output=True,
                          text=True,timeout=30,check=True)
    m = re.search(r"^Pages:\s*(\d+)\s*$",info.stdout,re.M)
    if not m:
        raise ValueError("Cannot determine PDF page count: " + path.name)
    count = int(m.group(1))
    if not 1 <= count <= 100:
        raise ValueError("PDF page count must be 1-100: " + path.name)
    output = []
    for n in range(1,count+1):
        target = cache/f"p{n:04d}.jpg"
        if not target.is_file() or target.stat().st_size == 0:
            prefix = cache/f"new{n:04d}"
            subprocess.run(["pdftoppm","-f",str(n),"-l",str(n),
                "-scale-to-x","2608","-scale-to-y","2104",
                "-jpeg","-jpegopt","quality=90","-singlefile",
                str(path),str(prefix)],timeout=120,check=True,
                stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            new = prefix.with_suffix(".jpg")
            if not new.is_file() or new.stat().st_size == 0:
                raise RuntimeError("PDF renderer failed on page "+str(n))
            new.replace(target)
        output.append(target)
    return output

def _legacy_match(state,original,digest):
    for name,record in state.get("files",{}).items():
        if (not name.startswith("pdf-page:") and isinstance(record,dict)
                and record.get("sha256")==digest
                and parse_name(name)[3].casefold()==original.casefold()):
            return record
    return None

def sync_media(api,records,state,save_state,cache_root,media_tag):
    """Keep stable Xibo media IDs across changes to order/duration prefixes."""
    import mimetypes
    assets = state.setdefault("slide_assets",{})
    library = api("GET","library",params={"tags":media_tag,"exactTags":1})
    if not isinstance(library,list):
        raise ValueError("Invalid Xibo library response")
    by_name = {x.get("name"):x for x in library if isinstance(x,dict)}
    slides,used = [],set()
    for entry in records:
        path,secs = entry["path"],entry["secs"]
        original,digest = entry["original"],entry["digest"]
        if path.suffix.lower()==".pdf":
            sources = [(f"{original}#page{n:04d}",page,n)
                       for n,page in enumerate(pdf_pages(path,digest,cache_root),1)]
        else:
            sources = [(original,path,None)]
        for key,source,page in sources:
            used.add(key)
            title = "XSM - "+entry["desired_name"]+(
                f" [Page {page}]" if page else "")
            source_hash = file_hash(source)
            prior = assets.get(key)
            if prior is None and page is None:
                prior = _legacy_match(state,original,source_hash)
            if prior is None and title in by_name:
                matched = by_name[title]
                prior = {"media_id":int(matched["mediaId"]),
                         "sha256":matched.get("sha256")}
            media_id = int(prior["media_id"]) if prior and prior.get("media_id") else None
            if media_id and prior.get("sha256")==source_hash:
                if (prior.get("name")!=title or prior.get("duration")!=secs):
                    api("PUT",f"library/{media_id}",data={
                        "name":title,"duration":str(secs),"retired":"0",
                        "tags":media_tag,"enableStat":"Inherit"})
            else:
                data = {"name":title,"tags":media_tag}
                if media_id:
                    data.update({"oldMediaId":str(media_id),
                                 "updateInLayouts":"1","deleteOldRevisions":"1"})
                kind = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
                with source.open("rb") as stream:
                    uploaded = api("POST","library",data=data,
                                   files={"files":(source.name,stream,kind)})
                items = uploaded.get("files") if isinstance(uploaded,dict) else uploaded
                if not isinstance(items,list): items = [uploaded]
                resolved = next((int(v[k]) for v in items if isinstance(v,dict)
                                 for k in ("mediaId","media_id","id") if v.get(k)),None)
                if resolved is None and media_id and items and all(
                        isinstance(v,dict) and not v.get("error") for v in items):
                    resolved = media_id
                if resolved is None:
                    raise RuntimeError("Xibo upload did not provide a media ID")
                media_id = resolved
                api("PUT",f"library/{media_id}",data={
                    "name":title,"duration":str(secs),"retired":"0",
                    "tags":media_tag,"enableStat":"Inherit"})
            assets[key] = {"media_id":media_id,"sha256":source_hash,
                           "name":title,"duration":secs}
            save_state()
            slides.append({"media_id":media_id,"duration":secs,
                           "title":title,"key":key})
    return slides,used

def cleanup_assets(api,state,used,save_state):
    assets = state.get("slide_assets",{})
    for key in list(assets):
        if key not in used:
            try:
                api("DELETE",f"library/{assets[key]['media_id']}",
                    data={"forceDelete":"1","purge":"1"})
            except Exception:
                LOG.warning("Could not remove unused managed media %s",key)
                continue
            del assets[key]
            save_state()

def widget_media_id(widget):
    media = widget.get("mediaIds") or []
    if isinstance(media,list) and media:
        first=media[0]
        return int(first.get("mediaId") if isinstance(first,dict) else first)
    return None

def widget_options(widget):
    return {x.get("option"):str(x.get("value"))
            for x in widget.get("widgetOptions") or [] if isinstance(x,dict)}

def needs_playlist_sync(playlist,slides):
    if int(playlist.get("isDynamic") or 0):return True
    widgets = sorted(playlist.get("widgets") or [],
                     key=lambda w:int(w.get("displayOrder") or 0))
    if len(widgets)!=len(slides):return True
    for widget,slide in zip(widgets,slides):
        if (widget_media_id(widget)!=slide["media_id"]
                or int(widget.get("duration") or 0)!=slide["duration"]
                or int(widget.get("useDuration") or 0)!=1):
            return True
        opts=widget_options(widget)
        if (opts.get("transIn")!="fly" or opts.get("transOut")!="fly"
                or opts.get("transInDirection")!="W"
                or opts.get("transOutDirection")!="W"
                or opts.get("transInDuration")!="800"
                or opts.get("transOutDuration")!="800"):
            return True
    return False

def apply_playlist(api,playlist,slides,reload_playlist):
    """Convert dynamic playlist once; reassign, time and transition each slide."""
    playlist_id=int(playlist["playlistId"])
    if int(playlist.get("isDynamic") or 0):
        api("PUT",f"playlist/{playlist_id}",data={
            "name":"XSM - Bulletin Slideshow","isDynamic":"0",
            "folderId":str(playlist.get("folderId") or 1),
            "enableStat":"Inherit"})
    widgets=playlist.get("widgets") or []
    unused=list(widgets)
    kept={}
    for slide in slides:
        for widget in list(unused):
            if widget_media_id(widget)==slide["media_id"]:
                kept[slide["media_id"]]=widget
                unused.remove(widget)
                break
    for widget in unused:
        api("DELETE",f"playlist/widget/{int(widget['widgetId'])}")
    for order,slide in enumerate(slides,1):
        if slide["media_id"] not in kept:
            api("POST",f"playlist/library/assign/{playlist_id}",data={
                "media[0]":str(slide["media_id"]),"duration":str(slide["duration"]),
                "useDuration":"1","displayOrder":str(order)})
    latest=reload_playlist()
    by_media={}
    for widget in latest.get("widgets") or []:
        by_media.setdefault(widget_media_id(widget),[]).append(widget)
    sequence=[]
    for slide in slides:
        choices=by_media.get(slide["media_id"]) or []
        if not choices:
            raise RuntimeError("Xibo did not assign media "+str(slide["media_id"]))
        widget=choices.pop(0)
        sequence.append(widget)
        wid=int(widget["widgetId"])
        if (int(widget.get("duration") or 0)!=slide["duration"]
                or int(widget.get("useDuration") or 0)!=1):
            api("PUT",f"playlist/widget/{wid}",data={
                "useDuration":"1","duration":str(slide["duration"]),
                "name":slide["title"],"enableStat":"Inherit"})
        opts=widget_options(widget)
        for direction in ("in","out"):
            prefix="transIn" if direction=="in" else "transOut"
            if (opts.get(prefix)!="fly" or opts.get(prefix+"Direction")!="W"
                    or opts.get(prefix+"Duration")!="800"):
                api("PUT",f"playlist/widget/transition/{direction}/{wid}",data={
                    "transitionType":"fly","transitionDuration":"800",
                    "transitionDirection":"W"})
    if sequence and any(int(widget.get("displayOrder") or 0)!=index
                        for index,widget in enumerate(sequence,1)):
        api("POST",f"playlist/order/{playlist_id}",data={
            f"widgets[{int(widget['widgetId'])}]":str(index)
            for index,widget in enumerate(sequence,1)})
    LOG.info("Sequenced slideshow playlist %s with %d images/pages",
             playlist_id,len(slides))
