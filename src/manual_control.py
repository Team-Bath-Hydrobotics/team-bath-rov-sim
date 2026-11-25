import pygame
import numpy as np
from pygame._sdl2 import controller

pygame.init()

clock = pygame.time.Clock()

screen = None
controllers = []

STICK_DEADZONE = 0.15

# SDL's GameController API normalises these positions across supported Xbox
# controllers, rather than relying on platform-specific joystick axis numbers.
LEFT_X, LEFT_Y, RIGHT_X, RIGHT_Y = range(4)
BUTTON_A = 0
BUTTON_B = 1
DPAD_UP, DPAD_DOWN, DPAD_LEFT, DPAD_RIGHT = 11, 12, 13, 14


def _axis_value(gamepad, axis):
    """Return a controller axis value after applying a small dead zone."""
    value = gamepad.get_axis(axis)
    if abs(value) < STICK_DEADZONE:
        return 0.0
    return value


def _connected_controllers():
    """Return the currently connected SDL game controllers.

    Polling here also makes controllers connected after the simulator starts
    immediately available, without requiring a restart.
    """
    global controllers

    controllers = [gamepad for gamepad in controllers if gamepad.attached()]
    if len(controllers) != controller.get_count():
        controllers = []
        for index in range(controller.get_count()):
            gamepad = controller.Controller(index)
            gamepad.init()
            controllers.append(gamepad)
    return controllers

def init():
    global screen

    screen = pygame.display.set_mode((10, 10))
    controller.init()
    _connected_controllers()

def get_command():
    pygame.event.pump()
    keys = pygame.key.get_pressed()
    pygame.display.flip()

    # HoloOcean's HoveringAUV thrusters are ordered as:
    #
    #   0: vertical front starboard     1: vertical front port
    #   2: vertical back port           3: vertical back starboard
    #   4: angled front starboard       5: angled front port
    #   6: angled back port             7: angled back starboard
    #
    # Zero is the command-free state. Any buoyancy/vehicle drift is therefore
    # handled by the simulator rather than being hidden in the input mix.
    vertical = 10.0 * (keys[pygame.K_UP] - keys[pygame.K_DOWN])

    # Keyboard controls:
    #   W/S        forward/backward
    #   A/D        strafe left/right
    #   Left/Right yaw left/right
    #   Up/Down    ascend/descend
    #   Q/E        roll left/right
    #   R/F        pitch up/down
    #
    # Xbox controller controls:
    #   Left stick       W/A/S/D (forward/backward and strafe)
    #   Right stick      yaw/pitch
    #   D-pad left/right roll left/right
    #   A/B              ascend/descend
    thrust = 10.0
    forward = thrust * (keys[pygame.K_w] - keys[pygame.K_s])
    strafe = thrust * (keys[pygame.K_a] - keys[pygame.K_d])
    yaw = thrust * (keys[pygame.K_LEFT] - keys[pygame.K_RIGHT])
    roll = thrust * (keys[pygame.K_q] - keys[pygame.K_e])
    pitch = thrust * (keys[pygame.K_r] - keys[pygame.K_f])

    for gamepad in _connected_controllers():
        # Stick Y is negative when pushed up.  Left is also inverted so its
        # directions match the keyboard convention (A/left and W/up are +).
        forward -= thrust * _axis_value(gamepad, LEFT_Y)
        strafe -= thrust * _axis_value(gamepad, LEFT_X)
        yaw -= thrust * _axis_value(gamepad, RIGHT_X)
        pitch -= thrust * _axis_value(gamepad, RIGHT_Y)
        roll += thrust * (
            gamepad.get_button(DPAD_LEFT) - gamepad.get_button(DPAD_RIGHT)
        )
        vertical += thrust * (
            gamepad.get_button(BUTTON_A) - gamepad.get_button(BUTTON_B)
        )

    # Approximate X-frame mixer for the four angled thrusters.  All four equal
    # values produce forward motion; opposite diagonal pairs produce strafe
    # and yaw.
    horizontal = np.array([
        forward + strafe + yaw,   # front starboard
        forward - strafe - yaw,   # front port
        forward - strafe + yaw,   # back port
        forward + strafe - yaw,   # back starboard
    ], dtype=np.float32)

    vertical_thrusters = np.array([
        vertical + roll + pitch,  # front starboard
        vertical - roll + pitch,  # front port
        vertical - roll - pitch,  # back port
        vertical + roll - pitch,  # back starboard
    ], dtype=np.float32)

    command = np.concatenate([
        vertical_thrusters,
        horizontal,
    ])

    return command

if __name__ == "__main__":
    try:
        while True:
            get_command()
            clock.tick(60)
    except KeyboardInterrupt:
        pygame.quit()
