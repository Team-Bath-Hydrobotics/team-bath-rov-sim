import logging
import threading
from functools import partial

from communicationv2.handler_base_classes.video_handler import VideoHandler
from communicationv2.rov_broker import RovBroker

from team_bath_rov_sim.handlers.sim_input_handler import SimInputHandler
from team_bath_rov_sim.handlers.sim_sensor_handler import SimSensorHandler
from team_bath_rov_sim.simulator import run_broker_supervisor, run_simulator


class FakeRunner:
    current_sensor_state = None

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


def test_run_simulator_starts_the_runner_and_wires_the_broker(monkeypatch, tmp_path) -> None:
    import team_bath_rov_sim.simulator as simulator

    scenario_path = tmp_path / "scenario.json"
    communication_path = tmp_path / "communication.json"
    runner_instances = []
    broker_instances = []

    class FakeSimulationRunner:
        def __init__(self, scenario, *, tick_rate_hz) -> None:
            self.scenario = scenario
            self.tick_rate_hz = tick_rate_hz
            self.started = False
            self.stopped = False
            self.failure_checked = False
            runner_instances.append(self)

        def start(self) -> None:
            self.started = True

        def stop(self) -> None:
            self.stopped = True

        def raise_if_failed(self) -> None:
            self.failure_checked = True

    class FakeRovBroker:
        def __init__(
            self,
            logger,
            sensor_handler_factory,
            input_handler_factory,
            video_handler_cls,
            *,
            config_path,
        ) -> None:
            self.logger = logger
            self.sensor_handler_factory = sensor_handler_factory
            self.input_handler_factory = input_handler_factory
            self.video_handler_cls = video_handler_cls
            self.config_path = config_path
            broker_instances.append(self)

        def run(self, stop_event) -> None:
            stop_event.set()

    monkeypatch.setattr(simulator, "SimulationRunner", FakeSimulationRunner)
    monkeypatch.setattr(simulator, "RovBroker", FakeRovBroker)

    run_simulator(
        scenario_path=scenario_path,
        communication_config_path=communication_path,
        tick_rate_hz=20,
    )

    runner = runner_instances[0]
    broker = broker_instances[0]
    assert runner.scenario == scenario_path
    assert runner.tick_rate_hz == 20
    assert runner.started
    assert runner.failure_checked
    assert runner.stopped
    assert broker.config_path == communication_path
    assert broker.video_handler_cls is VideoHandler
