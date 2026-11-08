import pygame
import numpy as np

pygame.init()

clock = pygame.time.Clock()

screen = pygame.display.set_mode((10, 10))

def get_command():
    pygame.event.pump()
    keys = pygame.key.get_pressed()
    pygame.display.flip()

    command = np.array([keys[pygame.K_LEFT], keys[pygame.K_LEFT],
                    keys[pygame.K_RIGHT], keys[pygame.K_RIGHT],
                    keys[pygame.K_UP], keys[pygame.K_UP],
                    keys[pygame.K_DOWN], keys[pygame.K_DOWN],
                    0, 0])
    command *= 10

    print(command)

    return command

if __name__ == "__main__":
    try:
        while True:
            get_command()
            clock.tick(60)
    except KeyboardInterrupt:
        pygame.quit()