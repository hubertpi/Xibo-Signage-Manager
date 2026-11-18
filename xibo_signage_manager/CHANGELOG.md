## 0.7.0

- Add events_days per additional layout: use 1 for today's Design Engineer
  Schedule in America/Chicago. Other calendars and birthdays keep 30 days.
- Add independent full-screen video layouts, including Lobby Safety, with their
  own upload folders, native downloadable video widget, and natural-duration repeat.
- Retain the published video during incomplete uploads, empty/multiple-file
  folders, or failed publishing. Purge old video media only after publication.
- Create video instructions in each video folder. Preserve existing schedules.

## 0.6.1

- Allow a separate calendar heading on each additional layout, such as
  "Design Engineer Schedule", while preserving the main bulletin heading.

## 0.6.0

- Manage additional layouts with separate slideshow folders and events calendars.
- Copy the published main design once for each new layout; inherit birthdays and
  the shared incident date. Leave display schedules and defaults unchanged.
- Isolate upload tracking, media titles/tags, PDF caches, and deletion per folder.
- Continue syncing other feeds when one layout is locked or its calendar fails.
- Avoid logging private calendar URLs on download/parse errors.

## 0.5.7

- Register slideshow images and PDF pages for player downloads while preserving their preview URLs.

## 0.5.6

- Upload the Safety First image automatically to Xibo's media library and reuse
  it across syncs and restarts. The widget uses a linked, downloadable image.
- Remove the large base64 image from widget HTML to stay within Xibo's 64 KB
  audit record limit and allow the counter rotation update to publish.
- Keep the 30-second counter, 6-second image and rightward slide timing.

## 0.5.5

- Group all display layout sensors under the existing Xibo Signage Manager device.
- Name each sensor using its display name in Xibo, including future displays and
  subsequent renames; retain existing MQTT topics and unique IDs.
- For existing 0.5.4 sensors, reload the MQTT integration once after updating to
  apply the new device association and remove the empty display devices.

## 0.5.4

- Alternate the live accident counter (30 seconds) with the supplied Safety First
  image (6 seconds), using a clipped rightward slide in the existing region.
- Bundle the original JPG for offline playback without separate CMS setup.
- Automatically discover Current Layout sensors for existing and future Xibo
  displays, using player reports with per-display availability.
