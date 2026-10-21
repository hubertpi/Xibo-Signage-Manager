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
    """Render PDF pages at aspect-preserving dimensions within 2608x2104."""
    cache = pathlib.Path(cache_dir)/("aspect-v2-"+digest)
    cache.mkdir(parents=True,exist_ok=True)
    info = subprocess.run(["pdfinfo","-f","1","-l","100",str(path)],capture_output=True,
                          text=True,timeout=30,check=True)
    m = re.search(r"^Pages:\s*(\d+)\s*$",info.stdout,re.M)
    if not m:
        raise ValueError("Cannot determine PDF page count: " + path.name)
    count = int(m.group(1))
    if not 1 <= count <= 100:
        raise ValueError("PDF page count must be 1-100: " + path.name)
    # Read each page's own dimensions: a PDF may mix portrait and landscape.
    dimensions = {}
    for match in re.finditer(r"^Page\s+(\d+)\s+size:\s*([\d.]+)\s+x\s+([\d.]+)\s+pts", info.stdout, re.M):
        dimensions[int(match.group(1))] = (float(match.group(2)), float(match.group(3)))
    rotations = {
        int(m.group(1)): int(m.group(2))
        for m in re.finditer(r"^Page\s+(\d+)\s+rot:\s*(\d+)", info.stdout, re.M)
    }
    if len(dimensions) != count:
        raise ValueError("Cannot determine all PDF page sizes: " + path.name)
    output = []
    for n in range(1,count+1):
        target = cache/f"p{n:04d}.jpg"
        if not target.is_file() or target.stat().st_size == 0:
            prefix = cache/f"new{n:04d}"
            width, height = dimensions[n]
            if rotations.get(n, 0) % 180:
                width, height = height, width
            ratio = min(2608 / width, 2104 / height)
            out_width = max(1, round(width * ratio))
            out_height = max(1, round(height * ratio))
            subprocess.run(["pdftoppm","-f",str(n),"-l",str(n),
                "-scale-to-x",str(out_width),"-scale-to-y",str(out_height),
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
    # All migrated media are recorded by stable descriptive filenames.
    # Retire old filename-based state to avoid adopting a deleted Xibo ID later.
    # Do NOT purge old Xibo media here; another layout may still reference it.
    if state.get("files"):
        state["files"] = {}
        save_state()
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


# Run the slideshow INSIDE an Embedded widget's iframe, not with Xibo's
# native fly animations: its region elements do not clip overflowing media.
SLIDESHOW_WIDGET_NAME = "XSM - Clipped Bulletin Slideshow"
SLIDESHOW_STYLE = """*{box-sizing:border-box}html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:transparent!important}
#xsm-slideshow{position:relative;width:100%;height:100%;overflow:hidden;border-radius:34px;isolation:isolate;background:#fff}
#xsm-slideshow .xsm-picture{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;object-position:center center;background:#fff;display:none;transform:translateX(100%);will-change:transform}
#xsm-slideshow .xsm-source{display:none}
#xsm-slideshow .xsm-empty{position:absolute;inset:0;display:flex;justify-content:center;align-items:center;text-align:center;font:bold 40px Arial,sans-serif;color:#777}"""
SLIDESHOW_SCRIPT = r'''<script>
(function(){
var started=false;
function init(){
 if(started)return;started=true;
 var entries=Array.prototype.slice.call(document.querySelectorAll("#xsm-slideshow .xsm-source")).map(function(el){
  return {url:el.getAttribute("data-url"),ms:Math.max(1000,parseInt(el.getAttribute("data-ms"),10)||10000)};
 });
 if(!entries.length)return;
 var front=document.getElementById("xsm-front"),back=document.getElementById("xsm-back");
 front.src=entries[0].url;front.style.display="block";front.style.transform="translateX(0)";
 var current=0;
 function advance(){
  if(entries.length===1){window.setTimeout(advance,entries[0].ms);return;}
  var next=(current+1)%entries.length, incoming=back, outgoing=front;
  incoming.style.transition="none";
  incoming.style.transform="translateX(100%)";
  incoming.style.display="block";
  incoming.src=entries[next].url;
  // Force initial position before enabling the westward 800ms animation.
  void incoming.offsetWidth;
  outgoing.style.transition="transform 800ms ease";
  incoming.style.transition="transform 800ms ease";
  incoming.style.transform="translateX(0)";
  outgoing.style.transform="translateX(-100%)";
  window.setTimeout(function(){
   outgoing.style.transition="none";
   outgoing.style.display="none";
   outgoing.style.transform="translateX(100%)";
   front=incoming;back=outgoing;current=next;
   window.setTimeout(advance,entries[current].ms);
  },820);
 }
 window.setTimeout(advance,entries[0].ms);
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
window.EmbedInit=init;
})();
</script>'''

def slideshow_payload(slides):
    """Generate a bounded, rounded, locally animated slideshow.

    Xibo's [mediaId] substitutions in Embedded HTML register each referenced
    library asset for Player download, including generated PDF page images.
    """
    sources = "".join(
        f'<span class="xsm-source" data-url="[{int(slide["media_id"])}]" '
        f'data-ms="{int(slide["duration"])*1000}"></span>'
        for slide in slides
    )
    empty = '' if slides else '<div class="xsm-empty">No bulletins available</div>'
    markup = ('<div id="xsm-slideshow" data-xsm-slideshow="1">'
              '<img id="xsm-front" class="xsm-picture" alt="">'
              '<img id="xsm-back" class="xsm-picture" alt="">'
              + sources + empty + '</div>')
    return {
        "name":SLIDESHOW_WIDGET_NAME,"useDuration":"1",
        "duration":"3600","enableStat":"Inherit",
        "transparency":"1","scaleContent":"1","isPreNavigate":"0",
        "embedHtml":markup,"embedStyle":SLIDESHOW_STYLE,
        "embedScript":SLIDESHOW_SCRIPT,"embedJavaScript":"",
    }

def widget_options(widget):
    return {x.get("option"):str(x.get("value"))
            for x in widget.get("widgetOptions") or [] if isinstance(x,dict)}

def needs_playlist_sync(playlist,slides):
    if int(playlist.get("isDynamic") or 0):
        return True
    widgets=playlist.get("widgets") or []
    if len(widgets)!=1 or widgets[0].get("type")!="embedded":
        return True
    widget=widgets[0]
    wanted=slideshow_payload(slides)
    opts=widget_options(widget)
    if int(widget.get("duration") or 0)!=3600 or int(widget.get("useDuration") or 0)!=1:
        return True
    return any(opts.get(key)!=value for key,value in wanted.items()
               if key in ("name","embedHtml","embedStyle","embedScript","embedJavaScript"))

def apply_playlist(api,playlist,slides,reload_playlist):
    """Replace native media fly transitions with an iframe-clipped slideshow."""
    playlist_id=int(playlist["playlistId"])
    if int(playlist.get("isDynamic") or 0):
        api("PUT",f"playlist/{playlist_id}",data={
            "name":"XSM - Bulletin Slideshow","isDynamic":"0",
            "folderId":str(playlist.get("folderId") or 1),
            "enableStat":"Inherit"})
    current=playlist.get("widgets") or []
    matches=[w for w in current if w.get("type")=="embedded"
             and widget_options(w).get("name")==SLIDESHOW_WIDGET_NAME]
    selected=matches[0] if matches else None
    for widget in current:
        if selected and int(widget["widgetId"])==int(selected["widgetId"]):
            continue
        api("DELETE",f"playlist/widget/{int(widget['widgetId'])}")
    if selected is None:
        created=api("POST",f"playlist/widget/embedded/{playlist_id}",data={})
        widget_id=created.get("id") if isinstance(created,dict) else None
        if not widget_id and isinstance(created,dict):
            widget_id=(created.get("data") or {}).get("widgetId")
        if not widget_id:
            refreshed=reload_playlist()
            candidates=[w for w in refreshed.get("widgets") or []
                        if w.get("type")=="embedded"]
            if len(candidates)!=1:
                raise RuntimeError("Xibo created a slideshow widget but returned no usable widget ID")
            widget_id=candidates[0]["widgetId"]
    else:
        widget_id=selected["widgetId"]
    api("PUT",f"playlist/widget/{int(widget_id)}",data=slideshow_payload(slides))
    LOG.info("Updated clipped slideshow widget %s with %d media pages",
             widget_id,len(slides))
