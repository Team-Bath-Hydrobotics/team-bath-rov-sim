"""Simulator implementation of the broker's telemetry handler."""

import math
from collections.abc import Mapping, Sequence
from typing import Any, Optional

import numpy as np
from common.data_interface.rov_data import ROVData
from common.data_interface.vector_data import Vector3
from communicationv2.handler_base_classes.sensor_handler import SensorHandler

from ..simulation_runner import SimulationRunner


class SimSensorHandler(SensorHandler):
    """Publish the most recent telemetry snapshot from the simulator."""

    def __init__(self, logger, runner: SimulationRunner) -> None:
        super().__init__(logger)
        self._runner = runner

    def get_sensor_data(self) -> Optional[ROVData]:
        sensor_state = self._runner.current_sensor_state
        if sensor_state is None:
            return None
        return _rov_data_from_sensor_state(sensor_state)


def _rov_data_from_sensor_state(sensor_state: Mapping[str, Any]) -> ROVData:
    """Convert the latest HoloOcean sensor snapshot into shared telemetry."""
    data = ROVData()

    depth = _scalar(sensor_state.get("DepthSensor"))
    if depth is not None:
        data.depth = depth

    velocity = _vector(sensor_state.get("VelocitySensor"))
    if velocity.size >= 3:
        data.velocity = _vector3(velocity[:3])
    if velocity.size >= 6:
        data.angular_velocity = _vector3(velocity[3:6])

    imu = np.asarray(sensor_state.get("IMUSensor", ()), dtype=float)
    if imu.size >= 3:
        data.acceleration = _vector3(imu.reshape(-1, 3)[0])
    if imu.size >= 6:
        data.angular_velocity = _vector3(imu.reshape(-1, 3)[1])

    pose = np.asarray(sensor_state.get("PoseSensor", ()), dtype=float)
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
