import logging

from team_bath_rov_sim.handlers.sim_input_handler import SimInputHandler


class FakeRunner:
    def __init__(self) -> None:
        self.command = None

    def set_control_command(self, command) -> None:
        self.command = tuple(command)


def test_forwards_surface_control_to_the_shared_runner() -> None:
    runner = FakeRunner()
    handler = SimInputHandler(logging.getLogger("test"), runner)

    handler.handle_input(range(8))

    assert runner.command == tuple(range(8))
