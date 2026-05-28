import py5
import random
import math
from .visual_base import VisualBase

from .spider.spider_branch import SpiderBranch
from .spider.spider_particles import SpiderParticle
from utils.ant_utils import random_position, smooth_signal


class VisualSpider(VisualBase):

    def __init__(self, signal_handler, config):
        super().__init__(signal_handler, config)
        self.signal_handler = signal_handler
        self.config = config

        self.particles = []
        self.branches = []
        self.signal_value = 0.0
        self.center = py5.Py5Vector(py5.width / 2, py5.height / 2)
        self.init = False

        self.incoming_signal_min = 8
        self.incoming_signal_max = 13
        self.color = self.get_color("color3a")
        self.background_color = self.get_backgroundcolor("backgroundColor3")

        self.CONNECT_THRESHOLD = 0.5
        self.EPS = 1e-3
        self.RADIUS = py5.width / 2
        self.NEW_BRANCH_PROB = 0.02          # probability of spawning new branch per frame when signal rises
        self.MIN_RETRACT_DELAY = 2000        # ms a branch must stay attached before eligible
        self.MIN_SELECT_INTERVAL = 2000      # min ms between random retractions
        self.MAX_SELECT_INTERVAL = 5000      # max ms between random retractions
        self.MIN_CONNECTED_BRANCHES = 10     # minimum number of connected branches to maintain

        # --- Initial growth phase ---
        self.initial_growth_duration = 10000   # ms (8 seconds)
        self.initial_growth_start_time = py5.millis()

        # ------------------ Timers ------------------
        self.last_retract_choice_time = 0
        self.next_retract_interval = random.randint(self.MIN_SELECT_INTERVAL, self.MAX_SELECT_INTERVAL)

        # ----------- base layout reference --------------
        self.base_width = 2560
        self.base_height = 1440
        self.scale = 1.0  # will be updated in first draw

    def draw(self):

        # ---------------- Initialization ----------------
        if not self.init:
            
            # update scale for current resolution
            self.scale = min(py5.width / self.base_width,
                             py5.height / self.base_height)
            
            self.center = py5.Py5Vector(py5.width / 2, py5.height / 2)
            self.RADIUS = int(py5.width / 6)
            print(self.RADIUS)

            # Random initial particles
            num = random.randint(30, 40)
            for _ in range(num):
                radius = random.randint(int(self.RADIUS / 2), self.RADIUS)
                p = SpiderParticle(
                    random_position(self.center, radius),
                    self.center,
                    radius,
                    self.color,
                    scale=self.scale
                )
                self.particles.append(p)

            # Central particle
            center_size = int(90 * self.scale)
            p = SpiderParticle(
                self.center,
                self.center,
                0,
                self.color,
                size=center_size,
                limit_velocity=0.1 * self.scale,
                scale=self.scale
            )
            self.particles.append(p)

            self.init = True

        py5.background(*self.background_color)

        # ---------------- Get and normalize signal ----------------
        raw_signal = self.signal_handler.get_signal()
        signal_value = max(0.0, min(1.0, (raw_signal - self.incoming_signal_min) /
                                    (self.incoming_signal_max - self.incoming_signal_min)))
        # Optional global smoothing
        signal_value = smooth_signal(signal_value, alpha=0.05)

        # ---------------- Randomly add new particles ----------------
        if signal_value > 0.6 and random.random() < self.NEW_BRANCH_PROB:
            radius = random.randint(int(self.RADIUS / 2), self.RADIUS)
            p = SpiderParticle(
                random_position(self.center, radius),
                self.center,
                radius,
                self.color,
                scale=self.scale
            )
            self.particles.append(p)
            self.branches.append(
                SpiderBranch(self.center, p, self.color, scale=self.scale)
            )

        current_time = py5.millis()

        # ---------------- Choose random branch for retraction ----------------
        connected_count = sum(1 for b in self.branches if b.connected_to_particle and not b.retracting)
        if connected_count >= self.MIN_CONNECTED_BRANCHES + 1:  # allow retraction only if more than 10
            if current_time - self.last_retract_choice_time > self.next_retract_interval:
                eligible = [
                    b for b in self.branches
                    if b.connected_to_particle
                    and not b.retracting
                    and (current_time - b.connection_time > self.MIN_RETRACT_DELAY)
                ]
                if eligible:
                    random.choice(eligible).start_retracting()
                    self.last_retract_choice_time = current_time
                    self.next_retract_interval = random.randint(self.MIN_SELECT_INTERVAL, self.MAX_SELECT_INTERVAL)

        # ---------------- Update particles ----------------
        for p in self.particles:
            p.update(self.particles)
            p.show()

        # ---------------- Update branches ----------------
        to_remove = []
        time_since_start = py5.millis() - self.initial_growth_start_time

        for b in self.branches:
            # --- Smooth per-branch target length ---
            if not hasattr(b, "smoothed_length"):
                b.smoothed_length = 0.0

            # --- Initial random growth phase (for visual richness) ---
            if not b.connected_to_particle:
                if time_since_start < self.initial_growth_duration:
                    target_length = 1.0
                else:
                    # Normal signal-driven growth after initial phase
                    if signal_value < self.CONNECT_THRESHOLD:
                        target_length = min(signal_value / self.CONNECT_THRESHOLD, 1.0 - self.EPS)
                        target_length = 0.0
                    else:
                        target_length = 1.0

                # Apply exponential smoothing to target
                ALPHA = 0.05
                b.smoothed_length = (1 - ALPHA) * b.smoothed_length + ALPHA * target_length
                b.set_direction_toward(b.smoothed_length)

            else:
                # Once connected, stay attached unless retracting
                if b.retracting:
                    b.set_direction_toward(0.0)   # retract fully toward particle
                else:
                    b.growth_direction = 0
                    b.length_factor = 1.0

            # --- Update geometry and connection check ---
            b.update(signal_value)

            if (not b.connected_to_particle) and (signal_value >= self.CONNECT_THRESHOLD) and (b.length_factor >= 1.0 - self.EPS):
                b.connected_to_particle = True
                b.connection_time = current_time
                b.length_factor = 1.0

            # --- Remove if retracted and allowed ---
            if b.retracting and b.length_factor <= 0.0 + self.EPS:
                still_connected = sum(1 for br in self.branches if br.connected_to_particle and not br.retracting)
                if still_connected > self.MIN_CONNECTED_BRANCHES:
                    to_remove.append(b)
                else:
                    # pause retraction if removal would break minimum rule
                    b.growth_direction = 0
                    b.length_factor = 0.0
                    b.retracting = False
                    b.connected_to_particle = False

            b.show()

        # ---------------- Remove retracted branches ----------------
        for b in to_remove:
            if b in self.branches:
                idx = self.branches.index(b)
                self.branches.pop(idx)
                if idx < len(self.particles):
                    self.particles.pop(idx)
