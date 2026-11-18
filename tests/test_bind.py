from e87cli.bind import (
    CMD_BIND,
    build_bind_payload,
    build_frame,
    parse_bind_reply,
    parse_frames,
)


def test_frame_matches_known_app_frames():
    # Frames captured from the vendor app's start-up sequence.
    assert build_frame(0x08, 0x16, b"\x01") == bytes.fromhex("9E200816010001")
    assert build_frame(0x0B, 0x29, b"\x80") == bytes.fromhex("9EB50B29010080")
    assert build_frame(0x0B, 0xDC, b"\x0c") == bytes.fromhex("9EF40BDC01000C")


def test_bind_payload_layout():
    payload = build_bind_payload(0x02ED29FF, english=True, hour12=True)
    assert payload == bytes.fromhex("06ff29ed020000ff29ed020000")
    assert build_bind_payload(1, english=False, hour12=False)[0] == 0x00


def test_parse_frames_handles_split_and_noise():
    reply = b"\x00" + b"2.7" + b"11.1.0.6\x00\x00" + bytes(16)
    stream = b"\x55" + build_frame(0x00, 0x61, b"\x02") + build_frame(0x00, 0x61, reply)
    frames = parse_frames(stream)
    assert [cmd for _f, cmd, _p in frames] == [0x61, 0x61]
    assert parse_frames(stream[:-3])[-1][2] == b"\x02"  # truncated tail is ignored


def test_parse_bind_reply():
    reply = b"\x00" + b"2.7" + b"11.1.0.6\x00\x00" + bytes(16)
    result = parse_bind_reply(reply)
    assert (result.state, result.protocol, result.firmware) == (0, "2.7", "11.1.0.6")
    assert parse_bind_reply(b"\x02") is None
    assert CMD_BIND == 0x60
