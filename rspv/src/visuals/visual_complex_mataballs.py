# src/visuals/visual_complex_metaballs.py
# pylint: disable=no-member
import os
import py5
from .visual_base import VisualBase


class VisualComplexMetaBalls(VisualBase):
    def __init__(self, signal_handler, config):
        """
        Visual with dynamic metaballs and persistent capsule shapes.

        Persistent shapes:
        - vertical and horizontal capsules (shape types 4 and 5)
        - larger and thinner
        - do not move, do not grow or shrink
        - fade by color intensity according to alpha signal

        Non persistent shapes:
        - circle (0), ring (1), vertical capsule (4), horizontal capsule (5)
        - can move and change size/number with alpha
        - also fade by color intensity according to the same alpha factor
        """
        super().__init__(signal_handler, config)
        self.shader = None
        self.signal_handler = signal_handler
        self.config = config

        # Signal smoothing
        self.previous_alpha_signal = None
        self.initialized = False
        self.smooth_factor = 0.5

        # Alpha signal mapping — signal_handler.get_signal() returns [0, 1]
        self.alpha_signal_min = 0.0
        self.alpha_signal_max = 1.0
        self.alpha_scale_min = 1
        self.alpha_scale_max = 12

        # Metaball state (non persistent)
        self.points = []
        self.time = 0.0
        self.radius = 200
        self.velocity = 10
        self.min_scale_factor = 0.05
        self.max_scale_factor = 0.1
        self.size_smooth = 0.015
        self.death_threshold = 0.02
        self.max_total = 16
        self.intensity = 1.5
        self.contour = 1.5

        # Persistent shapes (capsules)
        self.persistent_points = []
        self.persistent_size = 0.15   # larger than typical non persistent size
        self.persistent_fade_min = 0.2
        self.persistent_fade_max = 1.0

        # Shape types available for non persistent shapes
        # 0 = filled circle, 1 = circular ring, 4 = vertical capsule, 5 = horizontal capsule
        self.shape_types = [0, 1, 4, 5]

        self.frame_count = 0
        self.size_update_interval = 5

    # ─── Helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def lerp_color(c1, c2, t):
        """Linearly interpolate between two RGB colors (0..255)."""
        return (
            c1[0] + (c2[0] - c1[0]) * t,
            c1[1] + (c2[1] - c1[1]) * t,
            c1[2] + (c2[2] - c1[2]) * t,
        )

    def add_point(self):
        """Add one non persistent metaball."""
        t_color = py5.random(0.0, 1.0)
        shape_index = int(py5.random(len(self.shape_types)))
        shape_type = float(self.shape_types[shape_index])

        p = {
            "pos": py5.Py5Vector(py5.random(py5.width), py5.random(py5.height)),
            "color": (255, 0, 0),
            "t_color": t_color,
            "phase": py5.random(py5.TWO_PI),
            "velX": py5.random(-1, 1),
            "velY": py5.random(-1, 1),
            "size": 0.0,
            "target_size": 0.5,
            "dying": False,
            "shape_type": shape_type,
            "weight": 1.0,
            "persistent": False,
        }
        self.points.append(p)

    def add_persistent_capsules(self, persistent_size, weight):
        """
        Add one vertical and one horizontal persistent capsule at the centre.
        They share the same behaviour and fade factor.
        """
        t_color = py5.random(0.0, 1.0)
        base_pos = py5.Py5Vector(py5.width / 2, py5.height / 2)
        self.persistent_size = persistent_size
        
        color_a = self.get_color("color8a")

        # Vertical capsule (shape_type 4)
        p_vert = {
            "pos": py5.Py5Vector(base_pos.x, base_pos.y),
            "color": color_a,
            "t_color": t_color,
            "phase": 0.0,  # not used for fade anymore
            "velX": 0.0,
            "velY": 0.0,
            "size": self.persistent_size,
            "target_size": self.persistent_size,
            "dying": False,
            "shape_type": 4.0,
            "weight": weight,
            "persistent": True,
        }
        self.persistent_points.append(p_vert)

        # Horizontal capsule (shape_type 5)
        p_horiz = {
            "pos": py5.Py5Vector(base_pos.x, base_pos.y),
            "color": color_a,
            "t_color": t_color,
            "phase": 0.0,
            "velX": 0.0,
            "velY": 0.0,
            "size": self.persistent_size,
            "target_size": self.persistent_size,
            "dying": False,
            "shape_type": 5.0,
            "weight": weight,
            "persistent": True,
        }
        self.persistent_points.append(p_horiz)

    def update_point_color(self, p, color_a, color_b, color_c):
        """Compute color along gradient based on t_color."""
        t = p["t_color"]
        if t < 0.5:
            p["color"] = self.lerp_color(color_a, color_b, t * 2.0)
        else:
            p["color"] = self.lerp_color(color_b, color_c, (t - 0.5) * 2.0)

    # ─── Main draw loop ───────────────────────────────────────────────────────
    def draw(self):
        current_alpha_signal = self.signal_handler.get_signal()

        # Initialization
        if not self.initialized:
            self.previous_alpha_signal = current_alpha_signal
            current_dir = os.path.dirname(__file__)

            shader_path = os.path.join(current_dir, "shaders", "complex_metaballs.frag")
            self.shader = py5.load_shader(shader_path)

            if not self.points:
                for _ in range(1):
                    self.add_point()

            if not self.persistent_points:
                self.add_persistent_capsules(0.15, 0.1)
                self.add_persistent_capsules(0.18, 0.1)
                self.add_persistent_capsules(0.21, 0.1)

            self.initialized = True

        # Smooth alpha signal
        alpha_signal = py5.lerp(self.previous_alpha_signal, current_alpha_signal, self.smooth_factor)
        self.previous_alpha_signal = alpha_signal

        # Time update
        self.time += self.velocity / 1000.0

        # Global fade factor based on alpha signal (same for persistent and non persistent)
        fade_factor = py5.remap(
            alpha_signal,
            self.alpha_signal_min,
            self.alpha_signal_max,
            self.persistent_fade_min,
            self.persistent_fade_max,
        )
        fade_factor = max(0.0, min(fade_factor, 1.0))

        # Desired number of non persistent metaballs
        desired_total = int(py5.remap(
            alpha_signal,
            self.alpha_signal_min,
            self.alpha_signal_max,
            self.alpha_scale_min,
            self.alpha_scale_max,
        ))
        desired_total = max(0, min(desired_total, self.max_total))

        # Add or mark non persistent points for removal
        while len(self.points) < desired_total:
            self.add_point()
        if len(self.points) > desired_total:
            for p in self.points[desired_total:]:
                p["dying"] = True
                p["target_size"] = 0.0

        # Centre and velocity
        center_x, center_y = py5.width / 2, py5.height / 2
        velocity_factor = py5.remap(
            alpha_signal,
            self.alpha_signal_min,
            self.alpha_signal_max,
            0.1,
            0.2,
        )
        adjusted_velocity = self.velocity * velocity_factor

        self.frame_count += 1
        do_update_sizes = (self.frame_count % self.size_update_interval == 0)
        size_factor = py5.remap(
            alpha_signal,
            self.alpha_signal_min,
            self.alpha_signal_max,
            self.min_scale_factor,
            self.max_scale_factor,
        )
        radius_factor = py5.remap(
            alpha_signal,
            self.alpha_signal_min,
            self.alpha_signal_max,
            0.01,
            0.02,
        )
        adjusted_radius = self.radius * radius_factor

        # Gradient colors
        color_a = self.get_color("color8a")
        color_b = self.get_color("color8b")
        color_c = self.get_color("color8c")

        # Keep persistent shapes in sync with fade_factor
        for p in self.persistent_points:
            p["weight"] = fade_factor

        # Update non persistent points
        new_points = []
        for p in self.points:
            # Motion
            p["pos"].x += p["velX"] * adjusted_velocity * 0.1
            p["pos"].y += p["velY"] * adjusted_velocity * 0.1

            # Constrain inside circle
            dx = p["pos"].x - center_x
            dy = p["pos"].y - center_y
            dist = (dx * dx + dy * dy) ** 0.5
            if dist > adjusted_radius:
                nx = dx / dist
                ny = dy / dist
                dot = p["velX"] * nx + p["velY"] * ny
                p["velX"] -= 2 * dot * nx
                p["velY"] -= 2 * dot * ny
                p["pos"].x = center_x + nx * adjusted_radius
                p["pos"].y = center_y + ny * adjusted_radius

            # Size target
            if not p.get("dying", False) and do_update_sizes:
                p["target_size"] = size_factor

            # Size smoothing
            p["size"] += (p["target_size"] - p["size"]) * self.size_smooth

            # Color and fade
            self.update_point_color(p, color_a, color_b, color_c)
            p["weight"] = fade_factor

            # Keep if not completely gone
            if not (p.get("dying") and p["size"] < self.death_threshold):
                new_points.append(p)

        self.points = new_points


        # Combine persistent and non persistent points
        all_points = list(self.persistent_points) + list(self.points)
        if len(all_points) > self.max_total:
            all_points = all_points[: self.max_total]

        pos_x, pos_y = [], []
        R_vals, G_vals, B_vals = [], [], []
        size_vals = []
        shape_type_vals = []
        weight_vals = []

        for p in all_points:
            pos_x.append(p["pos"].x / py5.width)
            pos_y.append(p["pos"].y / py5.height)
            R_vals.append(p["color"][0] / 255.0)
            G_vals.append(p["color"][1] / 255.0)
            B_vals.append(p["color"][2] / 255.0)
            size_vals.append(max(p["size"], 0.0001))
            shape_type_vals.append(float(p["shape_type"]))
            weight_vals.append(float(p["weight"]))

        u_total = min(len(all_points), self.max_total)

        # Shader uniforms
        self.shader.set("u_resolution", float(py5.width), float(py5.height))
        self.shader.set("u_total", u_total)
        self.shader.set("posX", pos_x)
        self.shader.set("posY", pos_y)
        self.shader.set("R", R_vals)
        self.shader.set("G", G_vals)
        self.shader.set("B", B_vals)
        self.shader.set("SIZE", size_vals)
        self.shader.set("SHAPE_TYPE", shape_type_vals)
        self.shader.set("WEIGHT", weight_vals)
        self.shader.set("u_intensity", self.intensity)
        self.shader.set("u_contour", self.contour)

        # Background
        bg_color = self.get_backgroundcolor("backgroundColor1")
        self.shader.set("u_backgroundColor", *(c / 255.0 for c in bg_color))

        # Draw
        py5.background(*bg_color)
        py5.shader(self.shader)
        py5.rect(0, 0, py5.width, py5.height)
        py5.reset_shader()

        super().draw()
