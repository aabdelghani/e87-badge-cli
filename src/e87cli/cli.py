"""`badge`: program an E87 round smart badge over Bluetooth LE."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import pathlib
import secrets
import sys

from bleak import BleakScanner

from . import __version__

CONFIG_DIR = pathlib.Path(os.environ.get("XDG_CONFIG_HOME", pathlib.Path.home() / ".config")) / "e87badge"
ADDRESS_FILE = CONFIG_DIR / "address"
HOST_ID_FILE = CONFIG_DIR / "host_id"


# ── Local settings ─────────────────────────────────────────────────────────

def saved_address() -> str | None:
    env = os.environ.get("E87_ADDRESS")
    if env:
        return env.strip()
    try:
        return ADDRESS_FILE.read_text().strip() or None
    except OSError:
        return None


def host_id() -> int:
    """Stable random number identifying this computer to the badge."""
    try:
        return int(HOST_ID_FILE.read_text().strip(), 16)
    except (OSError, ValueError):
        value = secrets.randbits(40)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        HOST_ID_FILE.write_text(f"{value:x}\n")
        return value


# ── Finding the badge ──────────────────────────────────────────────────────

async def find_badge(address: str | None, wait: float):
    """Scan until the badge advertises. It sleeps quickly, so this can take a
    button press from the user."""
    from e87_badge import discover

    loop = asyncio.get_running_loop()
    deadline = loop.time() + wait
    hinted = False
    while True:
        if address:
            device = await BleakScanner.find_device_by_address(address, timeout=5.0)
        else:
            found = await discover(timeout=5.0)
            device = found[0] if found else None
        if device is not None:
            return device
        if loop.time() >= deadline:
            target = address or "any E87 badge"
            raise SystemExit(
                f"Could not find {target}. Wake the badge with its button, keep the "
                "phone app closed, and try again."
            )
        if not hinted:
            print("Badge not seen yet. Press its button to wake it...", file=sys.stderr)
            hinted = True


async def open_badge(args):
    from e87_badge import E87Client

    device = await find_badge(args.address or saved_address(), args.wait)
    return E87Client(device)


# ── Commands ───────────────────────────────────────────────────────────────

async def cmd_scan(args) -> int:
    from e87_badge import discover

    devices = await discover(timeout=args.wait if args.wait < 30 else 10.0)
    if not devices:
        print("No badge found. Press its button to wake it and scan again.", file=sys.stderr)
        return 1
    for device in devices:
        print(f"{device.address}\t{device.name or ''}")
    return 0


async def cmd_use(args) -> int:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ADDRESS_FILE.write_text(args.mac.strip().upper() + "\n")
    print(f"Saved {args.mac.strip().upper()} as the default badge.")
    return 0


async def cmd_bind(args) -> int:
    from .bind import bind

    async with await open_badge(args) as client:
        result = await bind(client, host_id(), english=not args.chinese, hour12=args.hour12)
    if result is None:
        print("Bind request sent; the badge gave no readable reply.")
    else:
        print(f"Bound. Firmware {result.firmware}, protocol {result.protocol}, state {result.state}.")
    return 0


async def cmd_unbind(args) -> int:
    from .bind import unbind

    async with await open_badge(args) as client:
        await unbind(client)
    print("Unbind sent. The badge returns to its QR pairing screen.")
    return 0


async def cmd_text(args) -> int:
    async with await open_badge(args) as client:
        await client.send_text(
            args.text.replace("\\n", "\n"),
            font=args.font, size=args.size, colour=args.colour, bg=args.bg,
        )
    return 0


async def cmd_image(args) -> int:
    async with await open_badge(args) as client:
        await client.send_image(args.path)
    return 0


async def cmd_gif(args) -> int:
    async with await open_badge(args) as client:
        await client.send_gif(args.path, max_fps=args.max_fps)
    return 0


async def cmd_slideshow(args) -> int:
    async with await open_badge(args) as client:
        await client.send_slideshow(args.paths, frame_ms=args.ms)
    return 0


async def cmd_scroll(args) -> int:
    async with await open_badge(args) as client:
        await client.send_danmaku(
            args.text, fg=args.colour, bg=args.bg, font=args.font,
            font_size=args.size, speed_px_per_frame=args.speed, fps=args.fps,
        )
    return 0


# ── Argument parsing ───────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="badge",
        description="Program an E87 round Bluetooth smart badge from this computer.",
    )
    parser.add_argument("--version", action="version", version=f"badge {__version__}")
    parser.add_argument("-a", "--address", help="badge Bluetooth address (default: saved one, else first found)")
    parser.add_argument("-w", "--wait", type=float, default=60.0,
                        help="seconds to wait for the badge to wake up (default 60)")
    parser.add_argument("-v", "--verbose", action="store_true", help="show protocol logs")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("scan", help="list nearby badges").set_defaults(func=cmd_scan)

    p = sub.add_parser("use", help="remember a badge address as the default")
    p.add_argument("mac")
    p.set_defaults(func=cmd_use)

    p = sub.add_parser("bind", help="leave the QR pairing screen (once per badge)")
    p.add_argument("--chinese", action="store_true", help="set the badge language to Chinese")
    p.add_argument("--hour12", action="store_true", help="use a 12 hour clock")
    p.set_defaults(func=cmd_bind)

    sub.add_parser("unbind", help="return the badge to its QR pairing screen").set_defaults(func=cmd_unbind)

    def text_options(p, size):
        p.add_argument("text")
        p.add_argument("--font", help="path to a .ttf font")
        p.add_argument("--size", type=int, default=size, help=f"font size (default {size})")
        p.add_argument("--colour", "--color", default="white", help="text colour")
        p.add_argument("--bg", default="black", help="background colour")

    p = sub.add_parser("text", help="show text (use \\n for a new line)")
    text_options(p, 72)
    p.set_defaults(func=cmd_text)

    p = sub.add_parser("image", help="show a PNG or JPEG")
    p.add_argument("path", type=pathlib.Path)
    p.set_defaults(func=cmd_image)

    p = sub.add_parser("gif", help="show an animated GIF")
    p.add_argument("path", type=pathlib.Path)
    p.add_argument("--max-fps", type=int, default=24)
    p.set_defaults(func=cmd_gif)

    p = sub.add_parser("slideshow", help="cycle through several images")
    p.add_argument("paths", type=pathlib.Path, nargs="+")
    p.add_argument("--ms", type=int, default=500, help="time per image in milliseconds")
    p.set_defaults(func=cmd_slideshow)

    p = sub.add_parser("scroll", help="show scrolling text")
    text_options(p, 64)
    p.add_argument("--speed", type=int, default=4, help="pixels per frame")
    p.add_argument("--fps", type=int, default=20)
    p.set_defaults(func=cmd_scroll)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    for path in getattr(args, "paths", None) or filter(None, [getattr(args, "path", None)]):
        if not path.is_file():
            print(f"badge: no such file: {path}", file=sys.stderr)
            return 2
    try:
        code = asyncio.run(args.func(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        if args.verbose:
            raise
        print(f"badge: {args.cmd} failed: {exc}", file=sys.stderr)
        return 1
    if code == 0 and args.cmd in {"text", "image", "gif", "slideshow", "scroll"}:
        print("Sent.")
    return code


if __name__ == "__main__":
    sys.exit(main())
