"""Single-owner HoloOcean runner and thread-safe simulator snapshots.

The simulator deliberately has one thread that touches a HoloOcean environment.
Handlers may submit controls and read snapshots, but must never call ``env.step``.
"""

from __future__ import annotations

import copy
import json
import math
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np
from common.data_interface.rov_data import ROVData
from common.data_interface.vector_data import Vector3


ControlVector = tuple[float, float, float, float, float, float, float, float]
EnvironmentFactory = Callable[[Mapping[str, Any]], Any]


@dataclass(frozen=True)
class SimulationSnapshot:
    """The latest state produced by the simulation thread.

    ``sensor_data`` is never handed out directly: :meth:`sensor_data_copy` returns
    a defensive copy because ``ROVData`` itself is mutable. Camera arrays are
    copied and marked read-only before they are published.
    """

    sensor_data: ROVData | None
    frames: Mapping[str, np.ndarray]
    tick: int
    timestamp: float

    def sensor_data_copy(self) -> ROVData | None:
        return copy.deepcopy(self.sensor_data)


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
            sensor_data=None,
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
    def current_sensor_data(self) -> ROVData | None:
        """Return a mutable copy of the latest shared telemetry model."""
        return self.get_snapshot().sensor_data_copy()

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
                    sensor_data=_rov_data_from_state(state),
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


def _rov_data_from_state(state: Mapping[str, Any]) -> ROVData:
    """Convert the HoloOcean sensors configured by the current scenario.

    Values unavailable in the scenario intentionally retain ``ROVData`` defaults.
    HoloOcean's IMU is acceleration, angular velocity, magnetometer; its velocity
    sensor is linear velocity followed by angular velocity.
    """
    data = ROVData()

    depth = _scalar(state.get("DepthSensor"))
    if depth is not None:
        data.depth = depth

    velocity = _vector(state.get("VelocitySensor"))
    if velocity.size >= 3:
        data.velocity = _vector3(velocity[:3])
    if velocity.size >= 6:
        data.angular_velocity = _vector3(velocity[3:6])

    imu = np.asarray(state.get("IMUSensor", ()), dtype=float)
    if imu.size >= 3:
        data.acceleration = _vector3(imu.reshape(-1, 3)[0])
    if imu.size >= 6:
        data.angular_velocity = _vector3(imu.reshape(-1, 3)[1])

    pose = np.asarray(state.get("PoseSensor", ()), dtype=float)
    if pose.shape == (4, 4):
        data.attitude = _euler_from_rotation_matrix(pose[:3, :3])

    return data


def _scalar(value: Any) -> float | None:
    if value is None:
        return None
    array = np.asarray(value, dtype=float).reshape(-1)
    return float(array[0]) if array.size else None


def _vector(value: Any) -> np.ndarray:
    if value is None:
        return np.empty(0, dtype=float)
    return np.asarray(value, dtype=float).reshape(-1)


def _vector3(values: Sequence[float]) -> Vector3:
    return Vector3(x=float(values[0]), y=float(values[1]), z=float(values[2]))


def _euler_from_rotation_matrix(rotation: np.ndarray) -> Vector3:
    """Return roll, pitch and yaw (radians) from a 3x3 rotation matrix."""
    pitch = math.asin(float(np.clip(-rotation[2, 0], -1.0, 1.0)))
    roll = math.atan2(float(rotation[2, 1]), float(rotation[2, 2]))
    yaw = math.atan2(float(rotation[1, 0]), float(rotation[0, 0]))
    return Vector3(x=roll, y=pitch, z=yaw)
