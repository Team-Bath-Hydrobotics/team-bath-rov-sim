import json
import time

import numpy as np
import pytest

from team_bath_rov_sim.simulation_runner import SimulationRunner


class FakeEnvironment:
    def __init__(self) -> None:
        self.commands: list[np.ndarray] = []

    def step(self, *, action: np.ndarray):
        self.commands.append(action.copy())
        return {
            "DepthSensor": np.array([-7.5]),
            "VelocitySensor": np.array([1, 2, 3]),
            "IMUSensor": np.array([[7, 8, 9], [10, 11, 12]]),
            "PoseSensor": np.eye(4),
            "LeftCamera": np.full((2, 2, 3), 8, dtype=np.uint8),
        }


class FailingEnvironment:
    def step(self, *, action: np.ndarray):
        raise OSError("HoloOcean connection lost")


def test_publishes_sensor_and_read_only_camera_snapshots(tmp_path) -> None:
    environment = FakeEnvironment()
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(json.dumps({}), encoding="utf-8")
    runner = SimulationRunner(
        scenario_path,
        tick_rate_hz=100,
        environment_factory=lambda _scenario: environment,
    )
    runner.set_control_command(range(8))
    runner.start()
    deadline = time.monotonic() + 1
    while runner.get_snapshot().tick == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
    runner.stop()

    snapshot = runner.get_snapshot()
    assert snapshot.tick > 0
    assert environment.commands[0].tolist() == list(range(8))
    assert snapshot.sensor_state["DepthSensor"][0] == -7.5
    assert snapshot.sensor_state["VelocitySensor"][0] == 1.0
    assert not snapshot.sensor_state["DepthSensor"].flags.writeable
    assert not snapshot.frames["LeftCamera"].flags.writeable
    with pytest.raises(ValueError):
        snapshot.frames["LeftCamera"][0, 0, 0] = 0


def test_rejects_non_thruster_sized_control_vectors() -> None:
    with pytest.raises(ValueError):
        SimulationRunner("scenario.json").set_control_command((0.0,) * 7)


def test_raises_with_the_runner_failure_as_its_cause() -> None:
    runner = SimulationRunner("scenario.json")
    failure = ValueError("HoloOcean stopped")
    with runner._lock:
        runner._error = failure

    with pytest.raises(RuntimeError, match="simulation runner stopped unexpectedly") as error:
        runner.raise_if_failed()

    assert error.value.__cause__ is failure


def test_rejects_starting_an_already_running_runner(tmp_path) -> None:
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(json.dumps({}), encoding="utf-8")
    runner = SimulationRunner(
        scenario_path,
        environment_factory=lambda _scenario: FakeEnvironment(),
    )
    runner.start()
    try:
        with pytest.raises(RuntimeError, match="simulation runner is already running"):
            runner.start()
    finally:
        runner.stop()


def test_stores_a_simulation_failure_and_signals_shutdown(tmp_path) -> None:
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(json.dumps({}), encoding="utf-8")
    runner = SimulationRunner(
        scenario_path,
        environment_factory=lambda _scenario: FailingEnvironment(),
    )

    runner.start()

    assert runner._stop_event.wait(timeout=1)
    runner.stop()
    with pytest.raises(RuntimeError, match="simulation runner stopped unexpectedly") as error:
        runner.raise_if_failed()
    assert isinstance(error.value.__cause__, OSError)
