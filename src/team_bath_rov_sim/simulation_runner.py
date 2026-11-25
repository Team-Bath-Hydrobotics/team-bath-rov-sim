"""Single-owner HoloOcean runner and thread-safe simulator snapshots.

The simulator deliberately has one thread that touches a HoloOcean environment.
Handlers may submit controls and read snapshots, but must never call ``env.step``.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np


ControlVector = tuple[float, float, float, float, float, float, float, float]
EnvironmentFactory = Callable[[Mapping[str, Any]], Any]


@dataclass(frozen=True)
class SimulationSnapshot:
    """The latest state produced by the simulation thread.

    Sensor values and camera arrays are copied and marked read-only before they
    are published. Handlers convert the raw sensor state to their own models.
    """

    sensor_state: Mapping[str, np.ndarray] | None
    frames: Mapping[str, np.ndarray]
    tick: int
    timestamp: float


class SimulationRunner:
    """Run HoloOcean at a fixed tick rate and expose its latest snapshot.

    The environment is constructed and stepped only in the runner thread. This
    keeps HoloOcean's non-thread-safe state separate from broker handler threads.
    """

    def __init__(
        self,
        scenario_path: str | Path,
        *,
        tick_rate_hz: float = 30.0,
        environment_factory: EnvironmentFactory | None = None,
        camera_sensor_names: Sequence[str] = ("LeftCamera", "RightCamera"),
    ) -> None:
        if tick_rate_hz <= 0:
            raise ValueError("tick_rate_hz must be greater than zero")

        self._scenario_path = Path(scenario_path)
        self._tick_interval = 1.0 / tick_rate_hz
        self._environment_factory = environment_factory or self._make_holoocean_environment
        self._camera_sensor_names = tuple(camera_sensor_names)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._error: BaseException | None = None
        self._command: ControlVector = (0.0,) * 8
        self._snapshot = SimulationSnapshot(
            sensor_state=None,
            frames=MappingProxyType({}),
            tick=0,
            timestamp=time.monotonic(),
        )

    def start(self) -> None:
        """Start the runner. Calling this twice while running is an error."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("simulation runner is already running")
            self._stop_event.clear()
            self._error = None
            self._thread = threading.Thread(
                target=self._run,
                name="simulation-runner",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float | None = 5.0) -> None:
        """Request shutdown and wait for the sole HoloOcean-owning thread."""
        self._stop_event.set()
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def set_control_command(self, control_vector: Sequence[float]) -> None:
        """Set the command used for the next tick (latest command wins)."""
        values = tuple(float(value) for value in control_vector)
        if len(values) != 8:
            raise ValueError("control_vector must contain exactly eight values")
        with self._lock:
            self._command = values  # type: ignore[assignment]

    def get_snapshot(self) -> SimulationSnapshot:
        """Return the latest immutable snapshot container."""
        with self._lock:
            return self._snapshot

    @property
    def current_sensor_state(self) -> Mapping[str, np.ndarray] | None:
        """Return the latest immutable raw HoloOcean sensor values."""
        return self.get_snapshot().sensor_state

    @property
    def current_frames(self) -> Mapping[str, np.ndarray]:
        """Return the latest read-only camera arrays keyed by sensor name."""
        return self.get_snapshot().frames

    def raise_if_failed(self) -> None:
        """Raise a terminal runner error in the caller's thread, if there is one."""
        with self._lock:
            error = self._error
        if error is not None:
            raise RuntimeError("simulation runner stopped unexpectedly") from error

    def _run(self) -> None:
        try:
            scenario = self._load_scenario()
            environment = self._environment_factory(scenario)
            tick = 0
            deadline = time.monotonic()
            while not self._stop_event.is_set():
                with self._lock:
                    command = self._command
                state = environment.step(action=np.asarray(command, dtype=np.float32))
                tick += 1
                snapshot = SimulationSnapshot(
                    sensor_state=_sensor_state_from_state(
                        state, self._camera_sensor_names
                    ),
                    frames=_frames_from_state(state, self._camera_sensor_names),
                    tick=tick,
                    timestamp=time.monotonic(),
                )
                with self._lock:
                    self._snapshot = snapshot

                deadline += self._tick_interval
                self._stop_event.wait(max(0.0, deadline - time.monotonic()))
                # Do not try to catch up by bursting env.step calls after a stall.
                if deadline < time.monotonic() - self._tick_interval:
                    deadline = time.monotonic()
        except BaseException as error:
            with self._lock:
                self._error = error
            self._stop_event.set()

    def _load_scenario(self) -> Mapping[str, Any]:
        with self._scenario_path.open(encoding="utf-8") as scenario_file:
            return json.load(scenario_file)

    @staticmethod
    def _make_holoocean_environment(scenario: Mapping[str, Any]) -> Any:
        # Import here so unit tests and handlers can use this module without the
        # native HoloOcean runtime being initialised in their process.
        import holoocean

        return holoocean.make(scenario_cfg=scenario)


def _frames_from_state(
    state: Mapping[str, Any], camera_sensor_names: Sequence[str]
) -> Mapping[str, np.ndarray]:
    frames: dict[str, np.ndarray] = {}
    for name in camera_sensor_names:
        value = state.get(name)
        if value is None:
            continue
        frame = np.array(value, copy=True)
        frame.setflags(write=False)
        frames[name] = frame
    return MappingProxyType(frames)


def _sensor_state_from_state(
    state: Mapping[str, Any], camera_sensor_names: Sequence[str]
) -> Mapping[str, np.ndarray]:
    """Copy every non-camera sensor value into an immutable snapshot."""
    camera_names = set(camera_sensor_names)
    sensors: dict[str, np.ndarray] = {}
    for name, value in state.items():
        if name in camera_names:
            continue
        sensor_value = np.array(value, copy=True)
        sensor_value.setflags(write=False)
        sensors[name] = sensor_value
    return MappingProxyType(sensors)
