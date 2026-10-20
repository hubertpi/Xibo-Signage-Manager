"""Build the Xibo Embedded widget body updated by the synchronizer."""
import datetime as dt
import html

WIDGET_NAME = "XSM - Accident Counter"

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
                        name == WIDGET_NAME or 'data-xsm-accident-counter="1"' in markup
                    ):
                        targets.append((layout, widget))
    return targets
