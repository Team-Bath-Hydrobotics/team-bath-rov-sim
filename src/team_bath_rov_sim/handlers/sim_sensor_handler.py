"""Simulator implementation of the broker's telemetry handler."""

from typing import Optional

from common.data_interface.rov_data import ROVData
from communicationv2.handler_base_classes.sensor_handler import SensorHandler

from ..simulation_runner import SimulationRunner


class SimSensorHandler(SensorHandler):
    """Publish the most recent telemetry snapshot from the simulator."""

    def __init__(self, logger, runner: SimulationRunner) -> None:
        super().__init__(logger)
        self._runner = runner

    def get_sensor_data(self) -> Optional[ROVData]:
        return self._runner.current_sensor_data
