import turtle
from turtle import Turtle, Screen
import random

tim = Turtle()
tim.shape("turtle")
turtle.colormode(255)

def random_color():
    """Random color generator"""
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    color = (r, g, b)
    return color



tim.speed("fastest")

def draw_spirograph(size_of_gap):
    for _ in range(int(360 / size_of_gap)):
        tim.color(random_color())
        tim.circle(100)
        tim.setheading(tim.heading() + size_of_gap)

draw_spirograph(5)


# directions = [0, 90, 180, 270]
# tim.pensize(15)
## Random color and directions
# for _ in range(100):
#     tim.color(random_color())
#     tim.forward(15)
#     tim.setheading(random.choice(directions))


screen = Screen()
screen.exitonclick()
