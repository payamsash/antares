import py5
import random
import math
import copy


class SpiderBranch:
    def __init__(self, center, particle, color, scale=1.0):
        self.center = copy.deepcopy(center)
        self.particle = particle
        self.points = []
        self.length_factor = 0.0
        self.wave_phase = random.uniform(0, math.tau)

        self.scale = scale

        # wave amplitude scaled relative to resolution
        self.wave_amplitude = random.uniform(20, 40) * self.scale
        self.wave_frequency = random.uniform(1.0, 2.0)
        self.connected_to_particle = False
        self.retracting = False
        self.connection_time = 0
        self.growth_direction = 0
        self.growth_speed = 0.01
        self.color = color
        self.EPS = 1e-3

    def set_direction_toward(self, target):
        if self.length_factor < target - self.EPS:
            self.growth_direction = 1
        elif self.length_factor > target + self.EPS:
            self.growth_direction = -1
        else:
            self.growth_direction = 0

    def start_retracting(self):
        self.retracting = True
        self.growth_direction = -1

    def update(self, signal_value):
        # Grow / retract smoothly
        if self.growth_direction == 1:
            self.length_factor += self.growth_speed
        elif self.growth_direction == -1:
            self.length_factor -= self.growth_speed
        self.length_factor = max(0, min(1, self.length_factor))

        # Straightness modulation with signal
        straightness = signal_value
        effective_amplitude = self.wave_amplitude * (1.0 - 0.95 * straightness)

        start = self.center
        end_pos = copy.deepcopy(self.particle.pos)
        steps = max(40, int(60 * self.scale))

        full_points = []

        # Always compute the full, animated curve (center → particle)
        for i in range(steps):
            t = i / (steps - 1)
            base = py5.Py5Vector.lerp(start, end_pos, t)

            fade_curve = math.sin(t * math.pi)
            amplitude = effective_amplitude * fade_curve

            wave = math.sin(self.wave_phase +
                            py5.frame_count * 0.01 +
                            t * self.wave_frequency * math.pi * 2)
            direction_angle = math.atan2(end_pos.y - start.y, end_pos.x - start.x)
            wave_angle = direction_angle + math.pi / 2
            offset_x = math.cos(wave_angle) * wave * amplitude
            offset_y = math.sin(wave_angle) * wave * amplitude

            pos = py5.Py5Vector(base.x + offset_x, base.y + offset_y)
            full_points.append(pos)

        # During growth: show from center to length_factor * full curve
        # During retraction: show only the last part (toward the particle)
        visible_count = max(2, int(steps * self.length_factor))
        if not self.connected_to_particle or not self.retracting:
            self.points = full_points[:visible_count]
        else:
            self.points = full_points[-visible_count:]

        # Always keep first/last anchors consistent
        if self.points:
            if not self.connected_to_particle:
                self.points[0] = copy.deepcopy(self.center)
            else:
                self.points[-1] = copy.deepcopy(self.particle.pos)



    def show(self):
        if self.length_factor <= 0:
            return
        py5.no_fill()
        py5.stroke(*self.color, 255)
        py5.stroke_weight(6 * self.scale)
        py5.begin_shape()
        for v in self.points:
            py5.vertex(v.x, v.y)
        py5.end_shape()
