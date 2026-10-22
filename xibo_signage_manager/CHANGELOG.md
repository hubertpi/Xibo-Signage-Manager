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
