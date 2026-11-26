import logging

import numpy as np

from team_bath_rov_sim.handlers.sim_sensor_handler import SimSensorHandler


class FakeRunner:
    current_sensor_state = {
        "DepthSensor": np.array([-7.5]),
        "VelocitySensor": np.array([1, 2, 3]),
        "IMUSensor": np.array([[7, 8, 9], [10, 11, 12]]),
        "PoseSensor": np.array(
            [
                [0, 0, 1, 0],
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 0, 1],
            ]
        ),
    }


def test_converts_the_latest_runner_sensor_snapshot_to_telemetry() -> None:
    handler = SimSensorHandler(logging.getLogger("test"), FakeRunner())
    telemetry = handler.get_sensor_data()

    assert telemetry.depth == 7.5
    assert telemetry.velocity.x == 1.0
    assert telemetry.acceleration.z == 9.0
    assert telemetry.angular_velocity.y == 11.0
    assert telemetry.attitude.x == 0.0
    assert telemetry.attitude.y == 90.0
    assert telemetry.attitude.z == 90.0
    assert telemetry.cardinal_direction == 90.0
