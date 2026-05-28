import py5
import random
import math
import copy

from utils.ant_utils import limit_vector

class SpiderParticle:
    def __init__(self, pos, center, radius, color, size=random.randint(8,12), limit_velocity=0.1, scale =1.0):
        
        self.scale = scale
        
        self.pos = pos
        self.first_pos = copy.deepcopy(pos)
        self.center = center
        self.radius_limit = radius
        self.vel = py5.Py5Vector(random.uniform(-1, 1), random.uniform(-1, 1))

        # velocity scaled to keep motion visually similar
        self.limit_velocity = limit_velocity * self.scale
        self.vel = limit_vector(self.vel, self.limit_velocity)

        # particle size scaled
        self.w = size * self.scale
        self.h = size * self.scale

        self.rot = random.uniform(0, math.tau)
        self.rot_speed = random.uniform(-0.9, 0.9)
        self.color = color
        

    def update(self, others):
        jitter = py5.Py5Vector(random.uniform(-0.2, 0.2),
                               random.uniform(-0.2, 0.2))
        self.vel += jitter
        self.vel = limit_vector(self.vel, self.limit_velocity)
        self.pos += self.vel

        # stay within circular boundary
        to_first_pos = self.pos - self.first_pos
        dist = to_first_pos.mag
        if dist > self.radius_limit:
            to_first_pos /= dist
            self.vel -= to_first_pos * 0.5
            self.pos = self.first_pos + to_first_pos * self.radius_limit

        # soft collision
        for other in others:
            if other is self:
                continue
            delta = self.pos - other.pos
            d = delta.mag
            min_dist = (self.w + other.w) * 0.5
            if d < min_dist and d > 0:
                overlap = (min_dist - d) * 0.5
                delta /= d
                self.pos += delta * overlap
                other.pos -= delta * overlap
                self.vel += delta * 0.1
                other.vel -= delta * 0.1

        self.rot += self.rot_speed

    def show(self):
        py5.push_matrix()
        py5.translate(self.pos.x, self.pos.y)
        py5.rotate(self.rot)
        py5.no_stroke()
        py5.fill(*self.color)
        py5.ellipse(0, 0, self.w, self.h)
        py5.pop_matrix()
