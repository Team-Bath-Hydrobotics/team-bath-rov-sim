import logging
import threading
from functools import partial

from communicationv2.handler_base_classes.video_handler import VideoHandler
from communicationv2.rov_broker import RovBroker

from team_bath_rov_sim.handlers.sim_input_handler import SimInputHandler
from team_bath_rov_sim.handlers.sim_sensor_handler import SimSensorHandler
from team_bath_rov_sim.simulator import run_broker_supervisor


class FakeRunner:
    current_sensor_data = None

    def set_control_command(self, _command) -> None:
        pass


def test_broker_uses_the_simulator_communication_config(tmp_path) -> None:
    path = tmp_path / "communication.json"
    path.write_text(
        '{"network": {"host": "surface", "port": 1234}, '
        '"telemetry_processor": {"host": "127.0.0.1", "port": 5678}}',
        encoding="utf-8",
    )
    runner = FakeRunner()
    broker = RovBroker(
        logging.getLogger("test"),
        partial(SimSensorHandler, runner=runner),
        partial(SimInputHandler, runner=runner),
        VideoHandler,
        config_path=path,
    )

    assert broker.host == "surface"
    assert broker.port == 1234
    assert broker.telemetry_port == 5678
    assert isinstance(broker.sensor_handler, SimSensorHandler)
    assert isinstance(broker.input_handler, SimInputHandler)
    assert broker.video_handler_cls is VideoHandler


def test_broker_startup_failure_is_retried_without_stopping_simulation() -> None:
    stop_event = threading.Event()
    attempts = 0

    def broker_factory():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("surface is unavailable")

        class StoppingBroker:
            def run(self, event) -> None:
                event.set()

        return StoppingBroker()

    run_broker_supervisor(
        logging.getLogger("test"),
        stop_event,
        broker_factory,
        retry_delay_s=0,
    )

    assert attempts == 2
