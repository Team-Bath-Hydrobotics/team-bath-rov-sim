import logging

import numpy as np

from team_bath_rov_sim.handlers.sim_sensor_handler import SimSensorHandler


class FakeRunner:
    current_sensor_state = {
        "DepthSensor": np.array([7.5]),
        "VelocitySensor": np.array([1, 2, 3, 4, 5, 6]),
        "IMUSensor": np.array([[7, 8, 9], [10, 11, 12], [0, 0, 0]]),
        "PoseSensor": np.eye(4),
    }


def test_converts_the_latest_runner_sensor_snapshot_to_telemetry() -> None:
    handler = SimSensorHandler(logging.getLogger("test"), FakeRunner())
    telemetry = handler.get_sensor_data()

    assert telemetry.depth == 7.5
    assert telemetry.velocity.x == 1.0
    assert telemetry.acceleration.z == 9.0
    assert telemetry.angular_velocity.y == 11.0
