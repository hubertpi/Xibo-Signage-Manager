# Cafeteria Xibo SD image

Once `.github/workflows/build-image.yml` is on the default branch, run
**Actions → Build cafeteria Xibo SD image → Run workflow**. When it finishes,
download **cafeteria-xibo-pi4** from the run's Artifacts section and extract it.
GitHub account sign-in and access to the repository are required for downloads.

On Windows, use Raspberry Pi Imager 2.x and double-click `Open-in-Imager.cmd`
next to the extracted image. If Imager does not open automatically, open it
and load `cafeteria-xibo.rpi-imager-manifest` via App Options → Content Repository
→ Edit → Use custom file. This preserves the customisation options for the
local image. Enter the Pi hostname, user, Wi-Fi and SSH preferences in Imager
before writing to the target SD card. Nothing in this repository needs a password.

The Pi downloads and configures the Xibo player on its first connected boot.
It still needs the CMS URL, key, display authorisation and layout assignment.
The workflow builds and checks the disk image; it does not boot a physical Pi.
