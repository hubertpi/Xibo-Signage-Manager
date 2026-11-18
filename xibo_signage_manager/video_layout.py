"""Manage a single downloadable native video in an independent full-screen layout."""
import logging
import mimetypes
import time

from counter_widget import get_widget_option
from layout_sync import _get_layouts, _preferred, _playlist
from slideshow import file_hash, cleanup_assets

LOG = logging.getLogger('xibo-signage')
REGION_NAME = 'XSM - Fullscreen Video'
VIDEO_EXTENSIONS = {'.mp4', '.webm'}
GUIDE = '''LOBBY VIDEO UPLOADS
Place one MP4 (H.264 video, AAC audio) or WebM file in this folder.
The add-on uploads it to Xibo, publishes a full-screen video layout, and loops
it at its natural duration. Filename timing prefixes are not needed.
Keep only ONE video here. To replace it, finish copying the new file and remove
the previous file. While copying, or if zero/multiple videos are present, the
previous published layout and its media are retained.
Video is muted by default; set video_mute: false on this layout for audio.
Assign the Lobby Safety layout to the intended display using Xibo Scheduling.
'''


def video_record(folder):
    guide = folder / 'VIDEO_UPLOAD_INSTRUCTIONS.txt'
    if not guide.exists():
        guide.write_text(GUIDE, encoding='utf-8')
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS)
    if not files:
        LOG.info('Waiting for one MP4 or WebM video in %s; published video retained', folder)
        return None
    if len(files) != 1:
        raise ValueError('Keep exactly one MP4 or WebM video in the video folder; prior video retained')
    path = files[0]
    before = path.stat()
    if not before.st_size or time.time() - before.st_mtime < 10:
        return None
    digest = file_hash(path)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        return None
    return path, digest


def get_video_layout(api, name):
    layouts = _get_layouts(api, name)
    if not layouts:
        # CMS chooses its standard landscape resolution and returns an editable draft.
        api('POST', 'layout', data={'name': name, 'description': 'XSM full-screen looping video', 'returnDraft': '1'})
        layouts = _get_layouts(api, name)
    if not layouts:
        raise RuntimeError('Xibo did not return the newly created video layout')
    roots = {int(x.get('parentId') or x['layoutId']) for x in layouts}
    if len(roots) != 1:
        raise ValueError(f'More than one layout is named {name!r}; use a unique name')
    return _preferred(layouts)


def upload_video(api, options, state, save_state, path, digest):
    assets = state.setdefault('slide_assets', {})
    if digest in assets:
        return int(assets[digest]['media_id'])
    title = f"XSM [{options['media_tag']}] - {path.stem[:100]} [{digest[:16]}]"
    library = api('GET', 'library', params={'tags': options['media_tag'], 'exactTags': 1})
    if not isinstance(library, list):
        raise ValueError('Invalid Xibo video library response')
    match = next((x for x in library if x.get('name') == title and x.get('mediaId')), None)
    if match:
        media_id = int(match['mediaId'])
    else:
        # Upload a new revision separately. Don't delete a working video's bytes
        # until the replacement layout has successfully published.
        with path.open('rb') as stream:
            result = api('POST', 'library', data={'name': title, 'tags': options['media_tag']},
                         files={'files': (path.name, stream, mimetypes.guess_type(path.name)[0] or 'application/octet-stream')})
        items = result.get('files', [result]) if isinstance(result, dict) else result
        media_id = next((int(item[key]) for item in items if isinstance(item, dict) and not item.get('error')
                         for key in ('mediaId', 'media_id', 'id') if item.get(key)), None)
        if media_id is None:
            raise RuntimeError('Xibo video upload did not return a media ID')
    assets[digest] = {'media_id': media_id, 'name': title, 'sha256': digest}
    save_state()
    return media_id


def video_region(layout):
    regions = layout.get('regions') or []
    if len(regions) > 1:
        raise ValueError('Video layout must contain only its full-screen region; unrelated layout retained')
    if not regions:
        return None, None
    region = regions[0]
    playlist = _playlist(region)
    if not playlist:
        raise ValueError('Video region playlist is unavailable')
    if region.get('name') != REGION_NAME and playlist.get('widgets'):
        raise ValueError('Existing layout is not an XSM full-screen video layout; left unchanged')
    return region, playlist


def sync_fullscreen_layout(api, layout, name, media_id, mute):
    root = int(layout.get('parentId') or layout['layoutId'])
    desired = {'name': REGION_NAME, 'useDuration': '0', 'loop': '1',
               'scaleType': 'aspect', 'mute': '1' if mute else '0', 'showFullScreen': '1'}
    width, height = int(layout['width']), int(layout['height'])
    region, playlist = video_region(layout)

    def matches():
        if not region or not playlist or int(playlist.get('isDynamic') or 0):
            return False
        if any(int(region.get(k, -1)) != v for k, v in
               {'left': 0, 'top': 0, 'width': width, 'height': height}.items()):
            return False
        region_options = {x.get('option'): str(x.get('value')) for x in region.get('regionOptions') or []}
        if region_options.get('loop') != '1':
            return False
        widgets = playlist.get('widgets') or []
        if len(widgets) != 1 or widgets[0].get('type') != 'video':
            return False
        widget = widgets[0]
        if [int(x) for x in widget.get('mediaIds') or []] != [media_id]:
            return False
        return int(widget.get('useDuration') or 0) == 0 and all(
            str(get_widget_option(widget, key) or '0') == value
            for key, value in desired.items() if key != 'useDuration')

    # Existing drafts are always finished/published, even if their contents match.
    if not layout.get('parentId') and int(layout.get('publishedStatusId') or 0) == 1 and matches():
        return
    if not layout.get('parentId'):
        api('PUT', f'layout/checkout/{root}', data={})
        layout = get_video_layout(api, name)
        if int(layout.get('parentId') or 0) != root:
            raise RuntimeError('Checkout returned no editable video draft')
        region, playlist = video_region(layout)
    if region is None:
        api('POST', f"region/{int(layout['layoutId'])}", data={
            'type': 'frame', 'left': '0', 'top': '0', 'width': str(width), 'height': str(height)})
        layout = get_video_layout(api, name)
        region, playlist = video_region(layout)
        if region is None:
            raise RuntimeError('Xibo did not return the new video region')
    api('PUT', f"region/{int(region['regionId'])}", data={
        'name': REGION_NAME, 'type': 'frame', 'left': '0', 'top': '0',
        'width': str(width), 'height': str(height), 'zIndex': '1', 'loop': '1',
        'transitionType': '', 'transitionDuration': '0', 'transitionDirection': ''})
    if int(playlist.get('isDynamic') or 0):
        raise ValueError('Video region must use a static playlist')
    widgets = playlist.get('widgets') or []
    selected = next((w for w in widgets if w.get('type') == 'video'
                     and [int(x) for x in w.get('mediaIds') or []] == [media_id]), None)
    if selected is None:
        api('POST', f"playlist/library/assign/{int(playlist['playlistId'])}", data={'media[]': [str(media_id)]})
        layout = get_video_layout(api, name)
        region, playlist = video_region(layout)
        selected = next((w for w in playlist.get('widgets') or [] if w.get('type') == 'video'
                         and [int(x) for x in w.get('mediaIds') or []] == [media_id]), None)
        if selected is None:
            raise RuntimeError('Assigned video widget was not returned by Xibo')
    api('PUT', f"playlist/widget/{int(selected['widgetId'])}", data=desired)
    for widget in playlist.get('widgets') or []:
        if int(widget['widgetId']) != int(selected['widgetId']):
            api('DELETE', f"playlist/widget/{int(widget['widgetId'])}")
    api('PUT', f'layout/publish/{root}', data={'publishNow': '1'})
    LOG.info('Published full-screen looping video layout %s', name)


def sync_video_source(api, options, folder, state, save_state):
    record = video_record(folder)
    layout = get_video_layout(api, options['counter_layout_name'])
    if record is None:
        return False
    path, digest = record
    media_id = upload_video(api, options, state, save_state, path, digest)
    sync_fullscreen_layout(api, layout, options['counter_layout_name'], media_id, options.get('video_mute', True))
    cleanup_assets(api, state, {digest}, save_state)
    return True
