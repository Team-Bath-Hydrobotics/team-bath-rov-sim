import logging

from team_bath_rov_sim.handlers.sim_sensor_handler import SimSensorHandler


class FakeRunner:
    current_sensor_data = "telemetry"


def test_returns_the_latest_runner_telemetry() -> None:
    handler = SimSensorHandler(logging.getLogger("test"), FakeRunner())

    assert handler.get_sensor_data() == "telemetry"
