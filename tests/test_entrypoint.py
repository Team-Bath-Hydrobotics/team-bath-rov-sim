import team_bath_rov_sim
import team_bath_rov_sim.simulator as simulator


def test_main_runs_the_simulator(monkeypatch) -> None:
    called = False

    def fake_run_simulator() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(simulator, "run_simulator", fake_run_simulator)

    team_bath_rov_sim.main()

    assert called
