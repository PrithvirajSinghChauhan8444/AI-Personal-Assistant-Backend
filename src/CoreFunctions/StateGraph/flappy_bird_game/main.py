import pygame
import random

# Initialize Pygame
pygame.init()

# Screen dimensions
SCREEN_WIDTH = 400
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
clock = pygame.time.Clock()

# Colors
WHITE = (255, 255, 255)
BLUE = (0, 0, 255)

# Bird settings
bird_x = 50
bird_y = 300
bird_velocity = 0
gravity = 0.25

# Game loop
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                bird_velocity = -5

    # Physics
    bird_velocity += gravity
    bird_y += bird_velocity

    # Drawing
    screen.fill(BLUE)
    pygame.draw.rect(screen, WHITE, (bird_x, bird_y, 30, 30))
    
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
