# src/visuals/visual_flow_field.py
# pylint: disable=no-member
import random
from math import cos, sin, pi
from collections import deque
import py5
from .visual_base import VisualBase

class VisualFlowField(VisualBase):
    """
    VisualFlowField generates a dynamic flocking visual based on an alpha signal.
    Boids (particles) move according to flocking rules and leave trails.
    This version integrates an activation/fade system so particles are
    cleanly spawned when alpha increases and fade out when alpha decreases.
    """
    def __init__(self, signal_handler, config):
        super().__init__(signal_handler, config)
        self.signal_handler = signal_handler
        self.config = config

        # Particle setup
        self.particles = []
        self.nums = 140  # Total number of particles

        # Alpha signal parameters
        self.alpha_signal_min = 0.0
        self.alpha_signal_max = 1.0
        self.alpha_scale_min = 25
        self.alpha_scale_max = 450
        self.alpha_particles_min = 5
        self.alpha_particles_max = self.nums
        self.previous_alpha_signal = None
        self.initialized = False
        self.smooth_factor = 0.02

        # track previous active count so we can gracefully activate / deactivate
        self.prev_active_count = 0

        # colors
        self.color = self.get_color("color3a")
        self.background_color = self.get_backgroundcolor("backgroundColor3")
        self.color_choices = [
            self.get_color("color3a"),
            self.get_color("color3b"),
            self.get_color("color3c"),
        ]

        # Boid parameters (easy to tweak)
        self.boid_max_speed = 2.0
        self.boid_max_force = 0.2
        self.boid_neighbor_dist = 60 #40
        self.boid_desired_separation = 40 #20
        self.boid_history_length_range = (10, 40)  # min, max

        # multipliers
        self.boid_sep_mult = 1.5
        self.boid_ali_mult = 0.5
        self.boid_coh_mult = 0.1
        self.boid_seek_mult = 0.2

        # Initial target position for seeking (will default to center in init)
        self.initial_target = None

        # Flock manager
        self.flock = self.Flock()
        self.startup_firework_frames = 120


    def draw(self):
        current_alpha_signal = self.signal_handler.get_signal()
        cx, cy = py5.width * 0.5, py5.height * 0.5

        if not self.initialized:
            self.previous_alpha_signal = current_alpha_signal
            py5.fill(255)
            py5.background(*self.background_color, 20)
            py5.no_stroke()
            py5.stroke_weight(1.0)
            self.init_particles(cx, cy)
            self.initialized = True

        # Smooth alpha signal
        alpha_signal = py5.lerp(self.previous_alpha_signal, current_alpha_signal, self.smooth_factor)
        self.previous_alpha_signal = alpha_signal

        # compute once per frame
        alpha_scale = py5.remap(alpha_signal, self.alpha_signal_min, self.alpha_signal_max, self.alpha_scale_max, self.alpha_scale_min,)
        alpha_particles_num = int(py5.remap(alpha_signal, self.alpha_signal_min, self.alpha_signal_max, self.alpha_particles_max, self.alpha_particles_min,))
        if getattr(self, "startup_firework_frames", 0) > 0:
            alpha_particles_num = len(self.particles)  # force all active so the initial explosion is visible
            self.startup_firework_frames -= 1
        self.boid_sep_mult = py5.remap(alpha_signal, 8.0, 13.0, 1.0, 1.5)
        self.boid_ali_mult = py5.remap(alpha_signal, 8.0, 13.0, 1.0, 0.5)
        self.boid_coh_mult = py5.remap(alpha_signal, 8.0, 13.0, 0.1, 0.1)
        self.boid_seek_mult = py5.remap(alpha_signal, 8.0, 13.0, 0.1, 1.2)

        py5.background(*self.background_color, 20)
        # draw boundary
        """
        radius = alpha_scale
        py5.no_stroke()

        # number of dots around the circle (increase for smoother ring)
        num_dots = int(100 + radius / 5)   # adaptive count based on radius
        dot_size = 3                      # size of each dot (you can make this random or vary with alpha)
        for i in range(num_dots):
            angle = (2 * pi * i) / num_dots
            x = cx + radius * cos(angle)
            y = cy + radius * sin(angle)
            color = random.choice(self.color_choices)
            py5.fill(color[0], color[1], color[2], 120)
            py5.ellipse(x, y, dot_size, dot_size) 
        """

        # Activation / deactivation handling (clean activation on growth, start fade on shrink)
        if alpha_particles_num > self.prev_active_count:
            for i in range(self.prev_active_count, alpha_particles_num):
                if i < len(self.particles):
                    self.particles[i].activate(cx, cy, alpha_scale)
        elif alpha_particles_num < self.prev_active_count:
            for i in range(alpha_particles_num, self.prev_active_count):
                if i < len(self.particles):
                    self.particles[i].start_fade()

        self.prev_active_count = alpha_particles_num

        # Ensure flock target set to center (makes seek() point to center)
        self.flock.set_target(cx, cy)

        py5.stroke(*self.color)
        for boid in self.flock.boids:
            boid.sep_mult = self.boid_sep_mult
            boid.ali_mult = self.boid_ali_mult
            boid.coh_mult = self.boid_coh_mult
            boid.seek_mult = self.boid_seek_mult
        # Run the flock: only active boids are updated/moved; fading boids are only displayed
        self.flock.run(cx, cy, active_count=alpha_particles_num, boundary_radius=alpha_scale)

        super().draw()

    def init_particles(self, center_x, center_y):
        for _ in range(self.nums):
            angle = random.uniform(0, 2 * pi)
            radius = random.uniform(0, self.alpha_scale_max)
            x = center_x + radius * cos(angle)
            y = center_y + radius * sin(angle)

            boid_color = random.choice(self.color_choices)

            boid = self.Boid(
                x,
                y,
                max_speed=self.boid_max_speed,
                max_force=self.boid_max_force,
                neighbor_dist=self.boid_neighbor_dist,
                desired_separation=self.boid_desired_separation,
                history_length_range=self.boid_history_length_range,
                sep_mult=self.boid_sep_mult,
                ali_mult=self.boid_ali_mult,
                coh_mult=self.boid_coh_mult,
                seek_mult=self.boid_seek_mult,
                color=boid_color,
            )
            # start all boids inactive; draw() will activate required ones
            boid.parent = self
            boid.active = False
            boid.fading = False
            self.particles.append(boid)
            self.flock.add_boid(boid)

        # initial flock target default to center
        if self.initial_target is None:
            self.initial_target = (center_x, center_y)
        self.flock.set_target(*self.initial_target)

    class Flock:
        def __init__(self):
            self.boids = []

        def run(self, center_x, center_y, active_count=None, boundary_radius=None):
            if active_count is None:
                active_count = len(self.boids)
            all_boids = self.boids
            n_boids = len(all_boids)
            active_count = min(active_count, n_boids)

            # cache constants used in the loop
            max_index = max(1, n_boids - 1)
            br = boundary_radius  # local ref

            # iterate once and do minimal attribute lookups
            for i, b in enumerate(all_boids):
                # minimal attribute fetches to locals
                b_active = b.active
                b_fading = b.fading

                display_radius = 4 + (i / max_index) * (6 - 4)

                if i < active_count and b_active:
                    # spawn if needed (randomize will clear the flag)
                    if getattr(b, "needs_spawn", True):
                        if br is not None:
                            b.randomize_position_inside(br)
                        else:
                            b.needs_spawn = False

                    # steering + update
                    b.flock(all_boids)
                    b.update()
                    if br is not None:
                        b.edges(br)
                    else:
                        b.borders()

                    b.display(center_x, center_y, display_radius, br)

                elif i < active_count and (not b_active) and (not b_fading):
                    b.activate(center_x, center_y, br)
                    if getattr(b, "needs_spawn", True):
                        if br is not None:
                            b.randomize_position_inside(br)
                        else:
                            b.needs_spawn = False

                    b.flock(all_boids)
                    b.update()
                    if br is not None:
                        b.edges(br)
                    else:
                        b.borders()

                    b.display(center_x, center_y, display_radius, br)

                elif b_fading:
                    # fading boids: update() still appends history but doesn't move them
                    b.update()
                    b.display(center_x, center_y, display_radius, br)

                else:
                    # deactivate and mark for spawn
                    b.active = False
                    b.needs_spawn = True

            # defensive pass: ensure boids beyond active_count are inactive and flagged
            for j in range(active_count, n_boids):
                bo = all_boids[j]
                if not bo.fading:
                    bo.active = False
                    bo.needs_spawn = True


        def set_target(self, x, y):
            for b in self.boids:
                b.set_target(x, y)

        def add_boid(self, b):
            self.boids.append(b)


    class Boid:
        """A single boid (flocking particle with trail and fade)"""

        def __init__(
            self,
            x,
            y,
            max_speed=2.0,
            max_force=0.05,
            neighbor_dist=50,
            desired_separation=20,
            history_length_range=(15, 50),
            sep_mult=1.5,
            ali_mult=1.0,
            coh_mult=1.0,
            seek_mult=0.0,
            color=None,
        ):
            self._temp_vec = py5.Py5Vector(0, 0)
            self.pos = py5.Py5Vector(x, y)
            self.vel = py5.Py5Vector(py5.random(-1, 1), py5.random(-1, 1))
            self.vel.set_mag(random.uniform(0.5, 1.0))
            self.acc = py5.Py5Vector(0, 0)

            self.max_speed = max_speed
            self.max_force = max_force
            self.neighbor_dist = neighbor_dist
            self.desired_separation = desired_separation

            # store the range so respawn can pick a new random history length
            self.history_length_range = history_length_range
            self.history_length = random.randint(*self.history_length_range)
            self.history = deque(maxlen=self.history_length)
            self.parent = None 
            # lifecycle flags
            self.active = False
            self.fading = False
            self.fade_progress = 0.0
            self.fade_speed = random.uniform(0.01, 0.03)

            # spawn control (used by Flock.run)
            self.needs_spawn = True

            # seek target
            self.seek_target = py5.Py5Vector(0, 0)

            # multipliers
            self.sep_mult = sep_mult
            self.ali_mult = ali_mult
            self.coh_mult = coh_mult
            self.seek_mult = seek_mult

            # radius used by borders()
            self.radius = 3

            # color
            self.color = color if color is not None else (255, 255, 255)

            # small randomization parameters used if we respawn
            self.mix_factor = random.uniform(0.5, 0.7)
            self.speed_factor = random.uniform(0.8, 1.2)
            # center_threshold: when closer than this the boid will start fading out
            self.center_threshold = random.uniform(4, 50)

        def respawn(self, center_x, center_y, alpha_scale):
            """Place boid on the boundary of the alpha circle and reset its history."""

            parent = getattr(self, "parent", None)
            if parent and getattr(parent, "startup_firework_frames", 0) > 0:
                # just reset velocity a bit, but keep it at the center
                self.pos.x = center_x
                self.pos.y = center_y
            else:
                angle = random.uniform(0, 2 * pi)   
                self.pos.x = center_x + alpha_scale * cos(angle)
                self.pos.y = center_y + alpha_scale * sin(angle)
     
            rand_angle = random.uniform(0, 2 * pi)
            # use math.cos/sin here (we imported cos, sin from math)
            self.vel.x = cos(rand_angle)
            self.vel.y = sin(rand_angle)
            # pick a new random history length from the stored range and recreate deque
            self.history_length = random.randint(*self.history_length_range)
            self.history = deque(maxlen=self.history_length)

            self.fading = False
            self.fade_progress = 0.0
            self.needs_spawn = False

        def activate(self, center_x, center_y, alpha_scale):
            """Called when alpha increases and this boid must become active."""
            self.respawn(center_x, center_y, alpha_scale)
            self.active = True
            self.fading = False
            self.fade_progress = 0.0
            self.needs_spawn = False

        def start_fade(self):
            """Start fade-out. Freeze movement; history will fade visually."""
            if not self.fading:
                self.fading = True
                self.fade_progress = 0.0
            self.active = False

        # ---------- Steering & physics (unchanged logic, optimized) ----------
        def set_target(self, x, y):
            self.seek_target = py5.Py5Vector(x, y)

        def apply_force(self, force):
            self.acc += force

        def get_steer_from_dir(self, target_v):
            # target_v is a Py5Vector direction / desired velocity
            if target_v.mag == 0:
                return py5.Py5Vector(0, 0)
            t = self._temp_vec
            t.x = target_v.x
            t.y = target_v.y
            t.normalize()
            t.set_mag(self.max_speed)
            steer = t - self.vel
            steer.set_limit(self.max_force)
            return steer

        def flock(self, boids):
            neigh_dist2 = self.neighbor_dist * self.neighbor_dist
            desired_sep2 = self.desired_separation * self.desired_separation

            # scalar accumulators
            sum_sep_x = sum_sep_y = 0.0
            sum_ali_x = sum_ali_y = 0.0
            sum_coh_x = sum_coh_y = 0.0
            count_sep = count_ali = 0

            px = self.pos.x
            py = self.pos.y

            # local copies for speed
            neigh_d2 = neigh_dist2
            des_sep2 = desired_sep2

            for other in boids:
                if other is self:
                    continue
                dx = px - other.pos.x
                dy = py - other.pos.y
                dist2 = dx * dx + dy * dy
                if dist2 == 0:
                    continue

                if dist2 < des_sep2:
                    inv = 1.0 / dist2
                    sum_sep_x += dx * inv
                    sum_sep_y += dy * inv
                    count_sep += 1

                if dist2 < neigh_d2:
                    sum_ali_x += other.vel.x
                    sum_ali_y += other.vel.y
                    sum_coh_x += other.pos.x
                    sum_coh_y += other.pos.y
                    count_ali += 1

            # build vectors once
            sep_vec = self._temp_vec
            sep_vec.x = 0
            sep_vec.y = 0
            if count_sep > 0:
                sep_vec.x = sum_sep_x / count_sep
                sep_vec.y = sum_sep_y / count_sep

            ali_vec = py5.Py5Vector(0, 0)
            coh_vec = py5.Py5Vector(0, 0)
            if count_ali > 0:
                ali_vec = py5.Py5Vector(sum_ali_x / count_ali, sum_ali_y / count_ali)
                center_x = (sum_coh_x / count_ali)
                center_y = (sum_coh_y / count_ali)
                coh_vec = py5.Py5Vector(center_x - px, center_y - py)

            sep = self.get_steer_from_dir(sep_vec) if count_sep > 0 else py5.Py5Vector(0, 0)
            ali = self.get_steer_from_dir(ali_vec) if count_ali > 0 else py5.Py5Vector(0, 0)
            coh = self.get_steer_from_dir(coh_vec) if count_ali > 0 else py5.Py5Vector(0, 0)

            seek_force = (self.seek(self.seek_target.x, self.seek_target.y)
                        if self.seek_mult != 0 else py5.Py5Vector(0, 0))

            # apply multipliers and forces
            sep *= self.sep_mult
            ali *= self.ali_mult
            coh *= self.coh_mult
            seek_force *= self.seek_mult

            self.apply_force(sep)
            self.apply_force(ali)
            self.apply_force(coh)
            self.apply_force(seek_force)

        def update(self):
            """Update position/velocity and append history. Keep lightweight."""
            self.vel += self.acc
            # limit once
            self.vel.set_limit(self.max_speed)
            self.pos += self.vel
            # reset acceleration with scalar op
            self.acc *= 0
            # append history tuple (cheap)
            self.history.append((self.pos.x, self.pos.y))

            # center check
            cx, cy = py5.width * 0.5, py5.height * 0.5
            dx = self.pos.x - cx
            dy = self.pos.y - cy
            dist2 = dx*dx + dy*dy
            if dist2 < self.center_threshold * self.center_threshold:
                self.fading = True
                self.fade_progress = 0.0
                self.active = False

        def randomize_position_inside(self, boundary_radius):
            # place without allocating new Py5Vector objects for pos.x/y
            center_x = py5.width * 0.5
            center_y = py5.height * 0.5
            angle = random.uniform(0, 2 * pi)
            r = random.uniform(0, boundary_radius)
            self.pos.x = center_x + r * cos(angle)
            self.pos.y = center_y + r * sin(angle)
            # set velocity using Py5Vector.random -> only one allocation
            self.vel = py5.Py5Vector.random(2)
            self.vel.set_mag(random.uniform(0.5, self.max_speed))
            self.history.clear()
            self.needs_spawn = False

        def borders(self):
            r = self.radius
            if self.pos.x < -r:
                self.vel.x = abs(self.vel.x)
            if self.pos.y < -r:
                self.vel.y = abs(self.vel.y)
            if self.pos.x > py5.width + r:
                self.vel.x = -abs(self.vel.x)
            if self.pos.y > py5.height + r:
                self.vel.y = -abs(self.vel.y)

        def edges(self, boundary_radius):
            center = self._temp_vec
            center.x = py5.width/2
            center.y = py5.height/2
            d = self.pos.dist(center)
            if d > boundary_radius:
                steer = center - self.pos
                steer.set_mag(self.max_speed)
                steer -= self.vel
                steer.set_limit(self.max_force * 2)
                self.apply_force(steer)

        def seek(self, tx, ty):
            t = self._temp_vec
            t.x = tx - self.pos.x
            t.y = ty - self.pos.y
            return self.get_steer_from_dir(t)

        def display(self, center_x, center_y, radius, alpha_scale, alpha=255):
            if not self.history:
                return

            py5.no_stroke()
            n = len(self.history)
            dx = self.pos.x - center_x
            dy = self.pos.y - center_y
            dist_to_center = (dx*dx + dy*dy) ** 0.5

            thickness = py5.remap(dist_to_center, 0.1, alpha_scale, radius * 2.0, radius)
            thickness = max(0.5, thickness)

            # use class-level/parent alpha steps if available
            alpha_steps = 20
            current_bucket = None

            if self.fading:
                # fading trail: iterate history once, fewer py5.fill calls due to alpha_steps
                for i, (past_pos_x, past_pos_y) in enumerate(self.history):
                    t = (i / n) ** 2
                    raw_alpha = py5.lerp(0, alpha, t) * (1 - self.fade_progress)
                    bucket = int((raw_alpha / alpha) * alpha_steps)
                    if bucket != current_bucket:
                        py5.fill(self.color[0], self.color[1], self.color[2], int(raw_alpha))
                        current_bucket = bucket
                    py5.ellipse(past_pos_x, past_pos_y, thickness, thickness)

                # advance fade
                self.fade_progress += self.fade_speed
                if self.fade_progress >= 1.0:
                    if self.active:
                        self.respawn(center_x, center_y, alpha_scale)
                    else:
                        self.fading = False
                        self.fade_progress = 0.0
                        self.history.clear()
            else:
                # normal trail drawing
                for i, (past_pos_x, past_pos_y) in enumerate(self.history):
                    raw_alpha = py5.lerp(0, alpha, i / n)
                    bucket = int((raw_alpha / alpha) * alpha_steps)
                    if bucket != current_bucket:
                        py5.fill(self.color[0], self.color[1], self.color[2], raw_alpha)
                        current_bucket = bucket
                    py5.ellipse(past_pos_x, past_pos_y, thickness, thickness)
