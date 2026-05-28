# src/visuals/visual_metaballs.py
# pylint: disable=no-member
import os
import py5
from .visual_base import VisualBase


class VisualMetaBalls(VisualBase):
    def __init__(self, signal_handler, config):
        """
        Args:
            signal_handler (SignalHandler): Provides real-time brainwave data.
            config (dict): Visual settings (colors, etc.).
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

        # Metaball state
        self.points = []
        self.time = 0.0
        self.radius = 200
        self.velocity = 10
        self.min_scale_factor = 0.05
        self.max_scale_factor = 1.25
        self.size_smooth = 0.015
        self.death_threshold = 0.02
        self.max_total = 16
        self.intensity = 1.5
        self.contour = 1.5

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
        """Add one metaball with a persistent gradient position."""
        t_color = py5.random(0.0, 1.0)
        p = {
            "pos": py5.Py5Vector(py5.random(py5.width), py5.random(py5.height)),
            "color": (255, 0, 0),  # placeholder
            "t_color": t_color,
            "phase": py5.random(py5.TWO_PI),
            "velX": py5.random(-1, 1),
            "velY": py5.random(-1, 1),
            "size": 0.0,
            "target_size": 0.5,
            "dying": False,
        }
        self.points.append(p)

    def update_point_color(self, p, color_a, color_b, color_c):
        """Compute color along gradient based on t_color."""
        t = p["t_color"]
        if t < 0.5:
            p["color"] = self.lerp_color(color_a, color_b, t * 2)
        else:
            p["color"] = self.lerp_color(color_b, color_c, (t - 0.5) * 2)

    # ─── Main draw loop ───────────────────────────────────────────────────────
    def draw(self):
        # Initialize shader and points
        current_alpha_signal = self.signal_handler.get_signal()
        if not self.initialized:
            self.previous_alpha_signal = current_alpha_signal
            current_dir = os.path.dirname(__file__)
            shader_path = os.path.join(current_dir, "shaders", "metaballs.frag")
            self.shader = py5.load_shader(shader_path)
            if not self.points:
                for _ in range(4):
                    self.add_point()
            self.initialized = True

        # Smooth alpha signal
        alpha_signal = py5.lerp(self.previous_alpha_signal, current_alpha_signal, self.smooth_factor)
        self.previous_alpha_signal = alpha_signal

        # Time update
        self.time += self.velocity / 1000

        # Determine desired number of metaballs
        desired_total = int(py5.remap(
            alpha_signal,
            self.alpha_signal_min,
            self.alpha_signal_max,
            self.alpha_scale_min,
            self.alpha_scale_max
        ))
        desired_total = max(0, min(desired_total, self.max_total))

        # Add or remove points
        while len(self.points) < desired_total:
            self.add_point()
        if len(self.points) > desired_total:
            for p in self.points[desired_total:]:
                p["dying"] = True
                p["target_size"] = 0.0

        # Center and velocity
        center_x, center_y = py5.width / 2, py5.height / 2
        velocity_factor = py5.remap(alpha_signal, self.alpha_signal_min, self.alpha_signal_max, 0.1, 2.5)
        adjusted_velocity = self.velocity * velocity_factor
        self.frame_count += 1
        do_update_sizes = (self.frame_count % self.size_update_interval == 0)
        size_factor = py5.remap(alpha_signal, self.alpha_signal_min, self.alpha_signal_max, self.min_scale_factor, self.max_scale_factor)
        radius_factor = py5.remap(alpha_signal, self.alpha_signal_min, self.alpha_signal_max, 0.01, 1.25)
        adjusted_radius = self.radius * radius_factor

        # Gradient colors
        color_a = self.get_color("color8a")
        color_b = self.get_color("color8b")
        color_c = self.get_color("color8c")

        # Update points
        new_points = []
        for p in self.points:
            # Motion
            p["pos"].x += p["velX"] * adjusted_velocity * 0.1
            p["pos"].y += p["velY"] * adjusted_velocity * 0.1

            # Constrain inside circle
            dx, dy = p["pos"].x - center_x, p["pos"].y - center_y
            dist = (dx ** 2 + dy ** 2) ** 0.5
            if dist > adjusted_radius:
                nx, ny = dx / dist, dy / dist
                dot = p["velX"] * nx + p["velY"] * ny
                p["velX"] -= 2 * dot * nx
                p["velY"] -= 2 * dot * ny
                p["pos"].x = center_x + nx * adjusted_radius
                p["pos"].y = center_y + ny * adjusted_radius

            # Update target size
            if not p.get("dying", False) and do_update_sizes:
                p["target_size"] = size_factor

            # Smooth size
            p["size"] += (p["target_size"] - p["size"]) * self.size_smooth

            # Update color
            self.update_point_color(p, color_a, color_b, color_c)

            # Keep if not fully shrunk
            if not (p.get("dying") and p["size"] < self.death_threshold):
                new_points.append(p)

        self.points = new_points

        # Build shader uniforms
        pos_x, pos_y, R, G, B, size = [], [], [], [], [], []
        for p in self.points:
            pos_x.append(p["pos"].x / py5.width)
            pos_y.append(p["pos"].y / py5.height)
            R.append(p["color"][0] / 255.0)
            G.append(p["color"][1] / 255.0)
            B.append(p["color"][2] / 255.0)
            size.append(max(p["size"], 0.0001))

        self.shader.set("u_resolution", float(py5.width), float(py5.height))
        u_total = min(len(self.points), self.max_total)
        self.shader.set("u_total", u_total)
        self.shader.set("posX", pos_x)
        self.shader.set("posY", pos_y)
        self.shader.set("R", R)
        self.shader.set("G", G)
        self.shader.set("B", B)
        self.shader.set("SIZE", size)
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
