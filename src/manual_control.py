import pygame
import numpy as np

pygame.init()

clock = pygame.time.Clock()

screen = pygame.display.set_mode((10, 10))


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
    thrust = 10.0
    forward = thrust * (keys[pygame.K_w] - keys[pygame.K_s])
    strafe = thrust * (keys[pygame.K_a] - keys[pygame.K_d])
    yaw = thrust * (keys[pygame.K_LEFT] - keys[pygame.K_RIGHT])
    roll = thrust * (keys[pygame.K_q] - keys[pygame.K_e])
    pitch = thrust * (keys[pygame.K_r] - keys[pygame.K_f])

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
