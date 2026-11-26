# Team Bath Hydrobotics - ROV Simulator

HoloOcean simulation connected to the same surface-facing communication layer as the physical ROV.

## Prerequisites

- Unreal Engine 5.3.4 must be installed.
- Your GitHub account must be linked to Epic Games and you must accept Epic's
  GitHub-organisation invitation before cloning HoloOcean. See the
  [HoloOcean installation guide](https://byu-holoocean.github.io/holoocean-docs/v2.4.0/usage/installation.html).

## Run the simulator

After installing the project dependencies, start it with:

```bash
uv run team-bath-rov-sim
```

To run tests with coverage report:

```bash
uv run pytest --cov=team_bath_rov_sim --cov-report=html
```

The default HoloOcean scenario is
`src/pier_harbor_hovering_camera.json`. Surface-controller 
and telemetry network settings are in `config/simulator-communication.json`.

## Architecture

`SimulationRunner` is the only component that accesses HoloOcean. It runs in
its own fixed-rate thread, applies the latest eight-value control command, and
publishes immutable raw sensor snapshots and camera frames.

`RovBroker` from `communicationv2` provides the common surface interface. It
constructs the simulator-specific handlers:

- `SimInputHandler` passes surface control commands to `SimulationRunner`.
- `SimSensorHandler` converts the runner's latest sensor snapshot into `ROVData`
  for the telemetry processor.
- Video uses the base no-op handler until `SimVideoHandler` is implemented.

The runner begins with a neutral eight-zero control vector. Once it receives a
surface command, it uses that command on every tick until a newer command
arrives. Broker or handler startup failures are retried without stopping the
simulation thread.

HoloOcean resources: [GitHub](https://github.com/wellscrosby/MRGHoloOcean) and
[documentation](https://byu-holoocean.github.io/holoocean-docs/develop/index.html).
