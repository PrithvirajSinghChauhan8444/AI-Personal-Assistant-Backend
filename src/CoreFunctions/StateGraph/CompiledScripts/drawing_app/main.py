import pygame
import sys

# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 800, 600
WHITE = (255, 255, 255)
SKY_BLUE = (135, 206, 235)
SUN_YELLOW = (255, 255, 0)
GREEN = (34, 139, 34)
BROWN = (139, 69, 19)

# Setup Screen
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Scenery Drawing")

def draw_scenery():
    # Fill background
    screen.fill(SKY_BLUE)
    
    # Draw Sun
    pygame.draw.circle(screen, SUN_YELLOW, (700, 100), 50)
    
    # Draw Ground
    pygame.draw.rect(screen, GREEN, (0, 500, WIDTH, 100))
    
    # Draw Tree Trunk
    pygame.draw.rect(screen, BROWN, (100, 400, 40, 100))
    
    # Draw Tree Leaves
    pygame.draw.circle(screen, GREEN, (120, 380), 50)

# Main Loop
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    
    draw_scenery()
    pygame.display.flip()

pygame.quit()
sys.exit()
