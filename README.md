# Xibo Signage Manager

Home Assistant add-on for synchronizing a Samba bulletin folder to **Xibo CMS 4.5.1**, with MQTT auto-discovery. No Ingress web UI.

## Install

Add this repository to Home Assistant's add-on/app store:

`https://github.com/hubertpi/Xibo-Signage-Manager`

The app uses a **prebuilt amd64/arm64 image** at `ghcr.io/hubertpi/xibo-signage-manager:0.3.1`, built and pushed by GitHub Actions in [publish.yml](.github/workflows/publish.yml). It does not compile Docker images on the Home Assistant machine.

**Check the GitHub Actions run has finished and that the GHCR package is public before installing.** Newly-created GitHub Container Registry packages may be private until their visibility is changed in the package settings.

Configure the app with your Xibo CMS URL and API client credentials, plus your MQTT settings. Defaults:

- Bulletins: `/share/digital_signage/bulletins`
- Incident-date text file: `/share/digital_signage/config/last_accident.txt`
- Managed Xibo tag: `xibo_signage_manager`

These are Supervisor-mounted Home Assistant paths corresponding to your Debian host's `/var/lib/homeassistant/share/digital_signage`. Do not put secrets in this repository or Samba.

## Sync behavior (v0.3.1)

- **New file:** Upload as Xibo library media with configured tag and `XSM - ` name prefix to avoid clashes with manually uploaded files.
- **Existing tagged file:** Detect an existing managed name and adopt its media ID after a previous interrupted upload; compare the Xibo MD5 with the local source to avoid an unnecessary upload. Untagged existing media is left untouched.
- **Changed file:** Re-upload using Xibo's documented `oldMediaId`, `updateInLayouts=1`, `deleteOldRevisions=1` mechanism.
- **Deleted file:** DELETE the Xibo media by its tracked ID using `forceDelete=1` and `purge=1`. This intentionally removes the media even if used in a layout, since the share is authoritative.
- Only media IDs recorded in the add-on's persistent state (including adopted tagged media) are eligible for replacement or deletion. Unrelated Xibo library media is not touched.
- Ignore source files younger than ten seconds, then verify stable size and modification time to avoid importing partial Samba copies.
- Supports JPG/JPEG/PNG/GIF/PDF. Actual PDF display depends on your Xibo player.
- State persists in the add-on configuration directory. The sync interval and auto-sync MQTT controls also persist across restarts.

## Live HTML accident counter (v0.3.1)

The add-on can **upgrade the existing 'Days Since Last Incident' embedded placeholder** in the imported 4K layout directly through the API, replacing its markup/style/script with the dynamic blue counter. You do not need to re-import the layout for the counter. Fresh installations can import the revised 4K ZIP with the `XSM - Accident Counter` widget already embedded.

The add-on reads `/share/digital_signage/config/last_accident.txt` (single ISO date) on each sync. It locates the widget by the configured `counter_layout_name`, updates only the embedded HTML date attribute via Xibo's `PUT /playlist/widget/{widgetId}` API, then publishes the layout if needed. This updates the Xibo layout only when the DATE changes. JavaScript in the Xibo player recalculates local calendar days once per minute in the America/Chicago time zone; **no counter image is created** and Home Assistant is not used for rendering.

`counter_layout_name` defaults to `Main Digital Bulletin - 4K Replica`. If you rename the imported layout, update that option. Until the new widget has been imported, the add-on logs that the widget was not found, while bulletin syncing continues.

Publishing the modified layout follows Xibo 4.5's draft/checkout API and needs a test against your CMS. If editing a published layout is blocked, the add-on reports an error rather than altering unrelated widgets.

## MQTT device

Discovery creates **Xibo Signage Manager** with Xibo connectivity, sync status, last successful sync, last duration, bulletin count, sync errors, last error, days since last accident, adjustable sync interval, auto sync switch and sync now button.

## Xibo layout connection

This release manages media library assets only. In Xibo, create a dynamic playlist filtered to the `xibo_signage_manager` tag and assign it to your slideshow region. Google Calendar integration, PDF rendering/playback and custom slide transitions will be tested separately.

## Build

GitHub Actions builds and publishes a multi-architecture image for each new release version configured in `xibo_signage_manager/config.yaml`. Wait for publishing before using the version in Home Assistant. The workflow uses Docker Buildx and GHCR with the repository's `GITHUB_TOKEN`.

The `Dockerfile` uses a self-contained Python Alpine base and does not depend on an undefined Supervisor `BUILD_FROM` argument.
