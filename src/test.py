"""
This is a simple example of what HoloOcean can do
We create the environment (env) and choose the pre-installed "PierHarbor-Hovering" scenario
Running env.step will step the simulation one step and send a command to the ROV; that is what the action parameter is for 
command = np.array([10,10,10,10,0,0,0,0]) is a command that just means to do nothing?? (still looking into)
We get the state of the ROV with env.step(action=command)
state is a dictionary with keys defined by the agent and the scenario. These keys can be found in ~/AppData/Local/holoocean/2.4.0/worlds/Ocean/PierHarbor-Hovering.json
The JSON format allows us to add sensors easily and see what their names are so we can access them here
"""

import argparse
import json
from pathlib import Path

import holoocean
import manual_control
import control_recorder
import traceback
import time
import cv2

parser = argparse.ArgumentParser(description="Run the HoloOcean ROV controller")
parser.add_argument(
    "--use-recorded-control",
    "--allow-recorded-control",
    dest="use_recorded_control",
    action="store_true",
    help="replay control_sequence.json instead of reading the keyboard",
)
parser.add_argument(
    "--record-manual-control",
    action=argparse.BooleanOptionalAction,
    default=True,
    help="record live manual commands (default: enabled)",
)
args = parser.parse_args()

USE_RECORDED_CONTROL = args.use_recorded_control
RECORD_MANUAL_CONTROL = args.record_manual_control

manual_recorder = (
    control_recorder.Recorder()
    if RECORD_MANUAL_CONTROL and not USE_RECORDED_CONTROL
    else None
)

scenario_path = Path(__file__).with_name("pier_harbor_hovering_camera.json")
with scenario_path.open() as scenario_file:
    scenario = json.load(scenario_file)

env = holoocean.make(scenario_cfg=scenario)

def get_sensors(env, _command):
    state = env.step(action=_command)
    sensors = list(state.keys())
    print(sensors)

sensor_poll_rate = 1

last_sensor_fetch = time.time()

camera_feed_poll_rate = 30

last_camera_poll = time.time()

try:
    if not USE_RECORDED_CONTROL:
        manual_control.init()

    while True:
        if USE_RECORDED_CONTROL:
            command = control_recorder.get_command()
        elif manual_recorder is not None:
            command = manual_recorder.get_command()
        else:
            command = manual_control.get_command()
        state = env.step(action=command)

        if time.time() - last_sensor_fetch > (1/sensor_poll_rate):
            last_sensor_fetch = time.time()
            for k in state:
                if k in ["PoseSensor", "VelocitySensor", "IMUSensor", "DepthSensor"]:
                    print(k, state[k])

        if time.time() - last_camera_poll > (1/camera_feed_poll_rate):
            for k in ["LeftCamera", "RightCamera"]:
                print("New frame")
                frame = state[k]
                cv2.imshow(f"HoloOcean Camera Feed: {k}", frame)
                cv2.waitKey(1)

except KeyboardInterrupt:
    print("Finished")
except Exception as e:
    print(traceback.format_exception(e))
finally:
    if manual_recorder is not None:
        manual_recorder.save()

