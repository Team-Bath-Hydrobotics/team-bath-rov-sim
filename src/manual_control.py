import pygame

pygame.init()

current_keys_down = {}

def get_command():
    pygame.event.pump()
    keys = pygame.key.get_pressed()

    print(keys)