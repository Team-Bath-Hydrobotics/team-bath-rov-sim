"""HoloOcean-backed simulator components for Team Bath Hydrobotics."""

from .simulation_runner import SimulationRunner, SimulationSnapshot
from .handlers import SimInputHandler, SimSensorHandler

__all__ = [
    "SimInputHandler",
    "SimSensorHandler",
    "SimulationRunner",
    "SimulationSnapshot",
]


def main() -> None:
    from .simulator import run_simulator

    run_simulator()
