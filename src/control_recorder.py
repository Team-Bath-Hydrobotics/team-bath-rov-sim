"""Record and replay timestamped HoloOcean control commands."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

import manual_control


DEFAULT_FILE = Path(__file__).with_name("control_sequence.json")
CONTROL_RATE_HZ = 60


def save_recording(records: list[dict], filename: str | Path = DEFAULT_FILE) -> None:
    """Save timestamped commands as a human-readable JSON file."""
    path = Path(filename)
    path.write_text(json.dumps(records, indent=2) + "\n")
    print(f"Saved {len(records)} commands to {path}")


def record(
    filename: str | Path = DEFAULT_FILE,
    rate_hz: int = CONTROL_RATE_HZ,
) -> None:
    """Record live commands until Ctrl+C, then save them to *filename*."""
    records: list[dict] = []
    start_time = time.perf_counter()
    period = 1.0 / rate_hz
    next_sample = start_time

    print("Recording controls. Press Ctrl+C to stop and save.")

    try:
        while True:
            now = time.perf_counter()
            if now < next_sample:
                time.sleep(next_sample - now)

            command = np.asarray(manual_control.get_command(), dtype=np.float32)
            records.append(
                {
                    "timestamp": time.perf_counter() - start_time,
                    "command": command.tolist(),
                }
            )
            next_sample += period
    except KeyboardInterrupt:
        save_recording(records, filename)


class Replay:
    """Replay a recording in real time, one command per call."""

    def __init__(self, filename: str | Path = DEFAULT_FILE):
        path = Path(filename)
        self.records = json.loads(path.read_text())
        if not self.records:
            raise ValueError(f"Recording is empty: {path}")
        self.index = 0
        self.finished = False
        self.start_time = time.perf_counter()

    def get_command(self) -> np.ndarray:
        """Wait for the next recorded timestamp and return its command."""
        if self.finished:
            return np.zeros(8, dtype=np.float32)

        record = self.records[self.index]
        target_time = self.start_time + float(record["timestamp"])

        remaining = target_time - time.perf_counter()
        if remaining > 0:
            time.sleep(remaining)

        command = np.asarray(record["command"], dtype=np.float32)
        if self.index < len(self.records) - 1:
            self.index += 1
        else:
            self.finished = True
        return command


_replay: Replay | None = None


def get_command(filename: str | Path = DEFAULT_FILE) -> np.ndarray:
    """Module-level replay function for use by ``test.py``."""
    global _replay
    if _replay is None:
        _replay = Replay(filename)
    return _replay.get_command()


if __name__ == "__main__":
    record()
