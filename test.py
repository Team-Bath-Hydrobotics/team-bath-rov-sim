"""
This is a simple example of what holoocean can do
We create the environment (env) and choose the pre-installed "PierHarbor-Hovering" scenario
running env.step will step the simulation one step and send a command to the rov, that is what the action parameter is for 
command = np.array([10,10,10,10,0,0,0,0]) is a command that just means to do nothing?? (still looking into)
we get the state of the rov with env.step(action=command)
state is a dicionary with keys defined by the agent and the scenario. These keys can be found in ~/AppData/Local/holoocean/2.4.0/worlds/Ocean/PierHarbor-Hovering.json
The JSON format allows us to add sensors easily and see what their names are so we can access them here
"""

import holoocean
import numpy as np

env = holoocean.make("PierHarbor-Hovering")

def get_sensors(env):
    state = env.step(action=command)
    sensors = list(state.keys())
    print(sensors)


# The hovering AUV takes a command for each thruster
command = np.array([10,10,10,10,0,0,0,0])
#get_sensors(env)

for i in range(2000):
    state = env.step(action=command)
    dv1 = state["DepthSensor"]
    print(f"{i}: {dv1}")
print("Finished!")

