"""Small WAV helpers on the standard library only (wave, struct, array).

Enough to build test audio, read durations, and carry a text label inside a WAV file
(a RIFF LIST/INFO "ICMT" comment) so the fake adapters can round-trip offline.
"""

from __future__ import annotations

import io
import math
import struct
import wave
from array import array
from typing import Optional


def pcm_to_wav(pcm: bytes, sample_rate: int = 24_000, channels: int = 1, sampwidth: int = 2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


def wav_info(data: bytes) -> tuple[int, int, float]:
    """(sample_rate, channels, duration_s) of WAV bytes. Raises wave.Error otherwise."""
    with wave.open(io.BytesIO(data), "rb") as w:
        return w.getframerate(), w.getnchannels(), w.getnframes() / float(w.getframerate())


def wav_pcm(data: bytes) -> bytes:
    with wave.open(io.BytesIO(data), "rb") as w:
        return w.readframes(w.getnframes())


def duration_of(data: bytes, fmt: str = "wav", sample_rate: int = 24_000) -> Optional[float]:
    """Seconds of audio, when it can be known without a decoder (wav, raw 16-bit pcm)."""
    try:
        if fmt == "pcm":
            return len(data) / 2 / sample_rate
        if data[:4] == b"RIFF":
            return wav_info(data)[2]
    except (wave.Error, EOFError, struct.error):
        return None
    return None


def tone(seconds: float, freq: float = 220.0, sample_rate: int = 16_000, volume: float = 0.2) -> bytes:
    """Raw 16-bit mono PCM: a sine tone (or silence with volume=0). Deterministic."""
    n = int(seconds * sample_rate)
    amp = int(32767 * volume)
    samples = array("h", (int(amp * math.sin(2 * math.pi * freq * i / sample_rate)) for i in range(n)))
    return samples.tobytes()


def add_comment(wav: bytes, text: str) -> bytes:
    """Append a RIFF LIST/INFO chunk with an ICMT (comment) holding `text` (UTF-8)."""
    payload = text.encode("utf-8") + b"\x00"
    if len(payload) % 2:
        payload += b"\x00"
    icmt = b"ICMT" + struct.pack("<I", len(payload)) + payload
    lst = b"LIST" + struct.pack("<I", 4 + len(icmt)) + b"INFO" + icmt
    body = wav[8:] + lst
    return b"RIFF" + struct.pack("<I", len(body)) + body


def read_comment(wav: bytes) -> Optional[str]:
    """The ICMT text written by add_comment (or by any tool that writes INFO/ICMT)."""
    if wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
        return None
    i = 12
    while i + 8 <= len(wav):
        cid, size = wav[i:i + 4], struct.unpack("<I", wav[i + 4:i + 8])[0]
        if cid == b"LIST" and wav[i + 8:i + 12] == b"INFO":
            j, end = i + 12, i + 8 + size
            while j + 8 <= end:
                sid, ssize = wav[j:j + 4], struct.unpack("<I", wav[j + 4:j + 8])[0]
                if sid == b"ICMT":
                    return wav[j + 8:j + 8 + ssize].rstrip(b"\x00").decode("utf-8", "replace")
                j += 8 + ssize + (ssize % 2)
        i += 8 + size + (size % 2)
    return None
