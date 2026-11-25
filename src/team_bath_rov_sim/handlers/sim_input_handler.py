"""Simulator implementation of the broker's control-input handler."""

from collections.abc import Sequence

from communicationv2.handler_base_classes.input_handler import InputHandler

from ..simulation_runner import SimulationRunner


class SimInputHandler(InputHandler):
    """Pass surface control vectors to the simulator's next tick."""

    def __init__(self, logger, runner: SimulationRunner) -> None:
        super().__init__(logger)
        self._runner = runner

    def handle_input(self, control_vector: Sequence[float]) -> None:
        self._runner.set_control_command(control_vector)
