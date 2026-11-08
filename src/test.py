"""
This is a simple example of what HoloOcean can do
We create the environment (env) and choose the pre-installed "PierHarbor-Hovering" scenario
Running env.step will step the simulation one step and send a command to the ROV; that is what the action parameter is for 
command = np.array([10,10,10,10,0,0,0,0]) is a command that just means to do nothing?? (still looking into)
We get the state of the ROV with env.step(action=command)
state is a dictionary with keys defined by the agent and the scenario. These keys can be found in ~/AppData/Local/holoocean/2.4.0/worlds/Ocean/PierHarbor-Hovering.json
The JSON format allows us to add sensors easily and see what their names are so we can access them here
"""

import holoocean
import manual_control
import traceback
import time

env = holoocean.make("PierHarbor-Hovering")

def get_sensors(env, _command):
    state = env.step(action=_command)
    sensors = list(state.keys())
    print(sensors)

sensor_poll_rate = 10

last_sensor_fetch = time.time()

try:
    while True:
        command = manual_control.get_command()
        state = env.step(action=command)

        if time.time() - last_sensor_fetch > (1/sensor_poll_rate):
            for k in state:
                print(k, state[k])

except KeyboardInterrupt:
    print("Finished")
except Exception as e:
    print(traceback.format_exception(e))

