"""Runnable composition of the simulator runner and the shared broker."""

from __future__ import annotations

import logging
import threading
from functools import partial
from pathlib import Path
from collections.abc import Callable
from typing import Any

from communicationv2.handler_base_classes.video_handler import VideoHandler
from communicationv2.rov_broker import RovBroker

from .handlers.sim_input_handler import SimInputHandler
from .handlers.sim_sensor_handler import SimSensorHandler
from .simulation_runner import SimulationRunner


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENARIO_PATH = PROJECT_ROOT / "src" / "pier_harbor_hovering_camera.json"
DEFAULT_COMMUNICATION_CONFIG_PATH = (
    PROJECT_ROOT / "config" / "simulator-communication.json"
)


def run_simulator(
    *,
    scenario_path: str | Path = DEFAULT_SCENARIO_PATH,
    communication_config_path: str | Path = DEFAULT_COMMUNICATION_CONFIG_PATH,
    tick_rate_hz: float = 30.0,
    stop_event: threading.Event | None = None,
) -> None:
    """Start HoloOcean and connect it to the surface-facing broker."""
    logger = logging.getLogger("team_bath_rov_sim")
    event = stop_event or threading.Event()
    runner = SimulationRunner(
        scenario_path,
        tick_rate_hz=tick_rate_hz,
        on_failure=event.set,
    )

    runner.start()
    try:
        run_broker_supervisor(
            logger,
            event,
            lambda: RovBroker(
                logger,
                partial(SimSensorHandler, runner=runner),
                partial(SimInputHandler, runner=runner),
                VideoHandler,
                config_path=communication_config_path,
            ),
        )
        runner.raise_if_failed()
    finally:
        event.set()
        runner.stop()


def run_broker_supervisor(
    logger: logging.Logger,
    stop_event: threading.Event,
    broker_factory: Callable[[], Any],
    *,
    retry_delay_s: float = 1.0,
) -> None:
    """Retry broker startup without interrupting the independent simulation.

    ``RovBroker`` itself already retries transient surface and telemetry socket
    connections. This supervisor covers failures while building or starting a
    handler (including a future video handler), which would otherwise stop the
    simulator's entry point.
    """
    while not stop_event.is_set():
        try:
            broker_factory().run(stop_event)
        except Exception:
            logger.exception("Broker failed; simulator will continue and retry")
        else:
            if stop_event.is_set():
                return
            logger.warning("Broker stopped unexpectedly; retrying")

        stop_event.wait(retry_delay_s)
