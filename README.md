# Xibo Signage Manager

Home Assistant add-on for Xibo CMS 4.5.1; full automatic synchronization from a Samba bulletin folder, incident date file, and two optional ICS calendars. Precompiled image for amd64 and aarch64: `ghcr.io/hubertpi/xibo-signage-manager:0.4.3`.

## Installation

Add `https://github.com/hubertpi/Xibo-Signage-Manager` to the Home Assistant add-on repository and configure the Xibo CMS URL and OAuth client credentials. MQTT creates a Xibo Signage Manager device with sync status and controls.

## Source paths

- Bulletins: `/share/digital_signage/bulletins` (JPG/JPEG/PNG/GIF/PDF)
- Safety date: `/share/digital_signage/config/last_accident.txt`, containing an ISO date `YYYY-MM-DD`
- Calendar: optional private `events_ics_url` and `birthdays_ics_url` in add-on Configuration. Never commit feed URLs/tokens to GitHub.
- CMS layout: `counter_layout_name`, default `Main Digital Bulletin - 4K Replica`
- Managed media tag: `xibo_signage_manager` (configurable)

On each sync:
1. Synchronize changed/new/deleted bulletin files into Xibo media library using the management tag and `oldMediaId` replacements.
2. Assign sequential playlist items to the existing `Bulletin Slideshow` region through the Xibo API (no random playback). Image items and individually rendered PDF pages have explicit, folder-controlled durations and westward fly-in/fly-out transitions. Multi-page PDFs are rendered to JPEG images in the add-on's `/config/xsm_pdf_pages` cache to prevent page timers from running independently; original PDFs are unchanged. The first sync converts the previous dynamic playlist to an ordered, add-on-managed playlist.
3. Update the existing `XSM - Accident Counter` Embedded widget using full Xibo HTML/CSS/JavaScript properties. The displayed figure is **SVG text, not an image**; the browser recalculates the number of calendar days every minute in America/Chicago time.
4. Fetch both ICS feeds server-side, expand recurring events and exceptions, keep only events and birthdays occurring in the next 30 calendar days (including today), escape content, then update the Events/Birthdays Embedded widget. Its header and content slide upward together every 10 seconds. Until feed URLs are entered, the panels explicitly show 'calendar not connected' and **never invented sample events**. URLs stay in add-on configuration and are not embedded in the player.
5. Reposition the existing native `Live Time` and `Live Date` clock regions in the upper-right clock panel, providing more vertical separation while keeping the two lines centered together. Their `clock-digital` widgets and styling remain unchanged.
6. Make **one** checkout/publish transaction for the entire layout when changes are necessary. Changes are deferred if the Xibo editor holds a lock (Xibo locks last up to five minutes) or if the API account lacks layout.modify.

The companion `Main Digital Bulletin - 4K Complete.zip` includes this layout ready to import once. **The add-on can also upgrade the previously imported version in place**, provided its region names are unchanged. No manual widgets or playlists need to be added.

For private Google calendars, obtain the **Secret address in iCal format** under that calendar's Integrate calendar settings. The built-in Google Birthdays calendar may not offer a direct ICS URL; if so, use an exportable secondary calendar. A calendar must be accessible over HTTPS from the add-on.

## Behavior / limitations

- On each sync, bulletin files are renamed in-place to `NN - XXs - Original.ext`, with a default `10s` duration and at least two position digits. A file with four position digits (e.g. `0002 - 15s - Notice.pdf`) is inserted/moved to position 2, and later files are renumbered. Normal two-digit positions are already ordered. The add-on automatically creates `BULLETIN_UPLOAD_INSTRUCTIONS.txt` in that folder and ignores TXT files. The Home Assistant add-on mounts `/share` read-write for this feature.
- PDF time is **per page**, image time is **per file**. The PDF originals remain on the share; the player receives timed JPEG pages.
- Media display names are prefixed `XSM -` for namespacing; unrelated Xibo library media are not modified.
- Deletes only previously tracked managed media. State persists under the add-on configuration directory.
- Source files younger than 10 seconds are deferred to avoid incomplete Samba copies.
- ICS feeds are fetched every sync interval (default 5 minutes); maximum 5 MB response, 30-day lookahead (today plus 29 days), 8 items per calendar.
- Xibo player schedule and file polling determine how quickly media and layout changes appear.
- PDFs are rendered by Poppler into individual timed images to eliminate embedded PDF viewer timing. Fly transitions are configured on individual Xibo widgets and should be verified on the actual Xibo Player; browser Preview can differ.
- The built-in sample safety page and sample events are removed; there is no substitute static content.

## Build

GitHub Actions runs Python tests and publishes images on source changes. The add-on uses a Python Alpine base and requires no compilation on Home Assistant.
