# e87-badge-cli

Program the **E87 round Bluetooth smart badge** from a Linux PC. No phone app, no account, no USB data.

The E87 is a small wearable badge with a 360x360 round screen, built on a JieLi AC707N chip and normally driven by the Zrun phone app. Its USB port only charges it, so it never shows up as a device on the computer. Everything goes over Bluetooth LE, and this tool does that from the command line.

```
badge bind                       # once: leave the QR pairing screen
badge text "Hello\nWorld"        # show text
badge image photo.png            # show a picture
badge gif party.gif              # show an animation
badge slideshow a.png b.png      # cycle through pictures
badge scroll "Welcome"           # scrolling text
```

## Install

Needs Linux with BlueZ, a Bluetooth LE adapter and Python 3.11 or newer.

```bash
git clone https://github.com/aabdelghani/e87-badge-cli
cd e87-badge-cli
python3 -m venv .venv
.venv/bin/pip install -e .
ln -s "$PWD/.venv/bin/badge" ~/.local/bin/badge
```

## First use

1. Charge the badge and press its button. A new badge shows a QR code with its Bluetooth address underneath.
2. Find it and remember it as the default:

   ```bash
   badge scan
   badge use 46:8B:00:00:00:00     # the address printed by scan
   ```

3. Bind it. This is what the phone app does after scanning the QR. Until it is done the badge keeps showing the QR, even after a successful upload:

   ```bash
   badge bind
   ```

4. Send something:

   ```bash
   badge text "Hello" --size 96 --colour white --bg "#0a3d62"
   ```

## Commands

| Command | What it does |
|---|---|
| `badge scan` | List nearby badges |
| `badge use MAC` | Save a badge address as the default |
| `badge bind` | Leave the QR pairing screen (`--hour12`, `--chinese`) |
| `badge unbind` | Go back to the QR pairing screen |
| `badge text "..."` | Centered text (`--size`, `--colour`, `--bg`, `--font`) |
| `badge image FILE` | A PNG or JPEG, fitted to the round screen |
| `badge gif FILE` | An animated GIF (`--max-fps`) |
| `badge slideshow FILES...` | Several images in a loop (`--ms` per image) |
| `badge scroll "..."` | Scrolling text (`--speed`, `--fps`, colours as for text) |

Options that go before the command: `--address MAC` to pick a badge for one call, `--wait SECONDS` to change how long to wait for the badge to wake (default 60), `--verbose` for protocol logs. The address can also come from the `E87_ADDRESS` environment variable.

## Good to know

- **The badge sleeps quickly** and stops advertising. If a command says it cannot see the badge, press the button; the command keeps scanning and continues on its own.
- **One connection at a time.** Close the Zrun app or turn off the phone's Bluetooth, otherwise the phone holds the badge and the PC cannot reach it.
- **Timing.** A still image takes a few seconds, an animation up to a minute.
- Settings live in `~/.config/e87badge/`.

## How it works

The badge speaks JieLi's RCSP protocol on service `AE00` for authentication and file transfer, plus a second control channel on service `c2e6fd00` used by the vendor app for setup, time and binding.

This tool is a thin layer over other people's reverse engineering:

- Uploads and authentication come from [jumpingmushroom/e87_badge](https://github.com/jumpingmushroom/e87_badge) (MIT), itself based on [hybridherbst/web-bluetooth-e87](https://github.com/hybridherbst/web-bluetooth-e87).
- The bind command follows the wire format documented in [vasilievh/e87-badge-firmware](https://github.com/vasilievh/e87-badge-firmware) (MIT), a fork of Electronic Cats' JieLi badge research.

What this repo adds is the bind step on top of the upload client, waiting for a sleeping badge, a saved default address, and one short command for everything.

Tested on an E87 with stock firmware 11.1.0.6. Stock firmware is left untouched; nothing here flashes the badge.

## License

MIT, see [LICENSE](LICENSE).
