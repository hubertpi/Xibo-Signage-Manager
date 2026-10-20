# Xibo Signage Manager

Home Assistant add-on (no Ingress) for importing bulletin images and PDFs from the existing Home Assistant Samba share into Xibo CMS 4.5.1 with MQTT auto-discovery.

## Installation

In Home Assistant **Settings → Add-ons → Add-on Store → Repositories**, add:

`https://github.com/hubertpi/Xibo-Signage-Manager`

Install **Xibo Signage Manager**. Configure the Xibo CMS URL and API Client ID/Secret created for **Bulletin Sync**, plus the MQTT broker settings. The standard folder defaults are:

- Bulletins: `/share/digital_signage/bulletins`
- Incident date: `/share/digital_signage/config/last_accident.txt`

**Important:** Add-on container uses the Supervisor-mounted `/share`, not the Debian host path `/var/lib/homeassistant/share`. Credentials go in the HA add-on config; do not commit them to Git.

## Initial release: 0.1.0

- Uploads **new** stable .jpg/.jpeg/.png/.gif/.pdf files to the Xibo library, with tag `xibo_signage_manager`.
- Records SHA-256 hashes and imported Xibo IDs in persistent add-on state.
- Discovers MQTT device with sync button, interval number, auto-sync switch, connectivity, last-successful-sync timestamp, last error, file count, and accident counter.
- **Does not automatically create Xibo playlists or update the existing layout**. Create a dynamic playlist in Xibo filtered on the specified tag and insert it into the slideshow region.
- **Does not automatically replace or remove library media yet.** Changed and deleted source files are reported as warnings to avoid deleting in-use Xibo media. This is an early integration/test release, not yet a full bidirectional reconciler.
- PDF API acceptance and rendering must be verified with your actual Xibo installation/player. Some media types may require additional modules or conversion.
- MQTT controls currently reset to configured defaults on add-on restart; persistence of control changes is planned.
- The accident counter is only an HA MQTT sensor so far; it is **not** embedded into the Xibo layout yet.
- Google Calendar and layout transitions are outside this add-on release.

## Initial checks

After installing and starting, look at the add-on log for imported file IDs and verify Xibo **Library** has media with tag `xibo_signage_manager`. In HA MQTT integration you should see the **Xibo Signage Manager** device.

Only connect your dedicated dynamic playlist after confirming the uploaded library entries and their tags. Never remove unrelated Xibo assets.

## Security

The configured API application needs library permission. Keep Client Secret and MQTT password in private add-on settings, not Samba or repository. The share is mounted read-only to the add-on.
