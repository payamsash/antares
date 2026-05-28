# src/visuals/visual_tree.py
# pylint: disable=no-member
import math
import random
import py5
from .tree.leaf import Leaf
from .visual_base import VisualBase

class Node:
    """
    Represents a single branch of the tree.
    Each Node contains its properties like length, size, rotation, and level in the tree hierarchy.
    Nodes can have child nodes and can optionally contain a leaf.
    """
    def __init__(self, length, size, rot_range, level, params):
        """
        Initializes a Node (branch) with randomized length and rotation based on parameters.
        Generates child nodes if the maximum depth (levelMax) is not reached.

        Args:
            length (float): Length of the branch.
            size (float): Thickness of the branch.
            rot_range (float): Maximum rotation range for the branch.
            level (int): Current depth level of the branch in the tree.
            params (dict): Tree generation parameters.
        """
        # Use Python random/math instead of py5 JNI calls — construction is ~500× faster.
        self.len = length * (1 + random.uniform(-params['lengthRand'], params['lengthRand']))
        self.size = size
        self.level = level
        self.s = 0
        self.rot = math.radians(random.uniform(-rot_range, rot_range))
        if self.level < params['leafLevel']:
            self.rot *= 0.3
        if self.level == 0:
            self.rot = 0
        self.wind_factor = random.uniform(1.0, 2.0)
        self.growing_speed = params['growingSpeed'] * random.uniform(0.5, 2.0)

        # Store branch color as a plain tuple so we can call py5.stroke(*branch_color).
        color1, color2, color3 = params['colors']
        r = random.random()
        self.branch_color = tuple(color1) if r < 0.33 else (tuple(color2) if random.random() < 0.66 else tuple(color3))

        self.leaf = None
        self.children = []
        # Create children nodes if the current level is below the max depth
        if level < params['levelMax']:
            rr = rot_range * params['rotDecay']
            self.children = [
                Node(length * params['lengthDecay'], size * params['sizeDecay'], rr, level + 1, params),
                Node(length * params['lengthDecay'], size * params['sizeDecay'], rr, level + 1, params)
            ]

    def draw(self, current_animation_level):
        """
        Draws the branch and recursively draws child branches.

        Args:
            current_animation_level (int): Current depth level being animated.
        """
        if self.level == current_animation_level:
            self.s = min(self.s + 1.0 / self.growing_speed, 1.0)
        elif self.level < current_animation_level:
            self.s = 1.0

        # Apply branch scaling
        py5.push_matrix()
        py5.scale(self.s)
        # Draw the branch
        py5.stroke_weight(self.size)
        py5.stroke(*self.branch_color)
        rot_offset = py5.sin( py5.millis() * 0.00005 * (self.level * 1))
        py5.rotate(self.rot + (rot_offset * 0.1) * self.wind_factor)
        py5.line(0, 0, 0, -self.len)
        py5.translate(0, -self.len)
        # Recursively draw child branches
        for child in self.children:
            py5.push_matrix()
            child.draw(current_animation_level)
            py5.pop_matrix()

        py5.pop_matrix()

    def draw_leaves(self):
        """
        Recursively draws the leaves attached to the branches.
        """
        py5.push_matrix()
        py5.scale(1.0)
        # Draw the branch
        py5.stroke_weight(self.size)
        py5.stroke(*self.branch_color)
        rot_offset = py5.sin( py5.millis() * 0.00005 * (self.level * 1))
        py5.rotate(self.rot + (rot_offset * 0.1) * self.wind_factor)
        py5.translate(0, -self.len)
        # Draw leaf if available
        if self.leaf:
            self.draw_leaf()
        # Recursively draw child branches
        for child in self.children:
            py5.push_matrix()
            child.draw_leaves()
            py5.pop_matrix()
        py5.pop_matrix()

    def draw_leaf(self):
        """
        Draws and updates the falling state of the leaf attached to the branch.
        """
        self.leaf.draw()  # Draw the leaf
        self.leaf.update_falling()  # Update the leaf's falling state

class VisualTree(VisualBase):
    """
    Manages the procedural generation, animation, and rendering of a dynamic tree visual.
    The tree responds to alpha brainwave signals to dynamically adjust leaf count and appearance.
    """

    def __init__(self, signal_handler, config):
        """
        Initializes the tree visual with the given configuration and signal handler.

        Args:
            signal_handler (SignalHandler): Handles external alpha wave signals.
            config (dict): Configuration parameters for the visual.
        """
        super().__init__(signal_handler, config)
        self.signal_handler = signal_handler
        self.config = config
        self.node = None
        # Signal range: ANTARES sends a reward score in [0, 1]
        # 1.0 = maximum reward (feature at target), 0.0 = minimum
        self.alpha_signal_min = 0.0
        self.alpha_signal_max = 1.0
        self.min_leaves = 8
        self.max_leaves = 100
        self.leaf_count = 0
        self.initialized = False
        # Smoothing is now handled by VisualBase.get_smooth_signal()
        self.current_animation_level = 0  # Start with the first level
        self.animation_complete = False
        self.total_leaves = 0
        self.leaves = []  # List to store all leaves
        self.background_color = None
        self.params = {
            'rotRange': 10,  # Maximum rotation angle for branches (in degrees).
            'rotDecay': 1.1,  # Rate at which the rotation angle decreases as branches go further from the trunk.
            'sizeDecay': 0.7,  # Rate at which the branch size decreases with each level of depth in the tree.
            'lengthDecay': 0.91,  # Rate at which the branch length decreases with each level of depth in the tree.
            'levelMax': 8,  # Maximum depth level of the tree (how many levels of branches).
            'leafLevel': 2,  # The level at which leaves start appearing (leaf generation starts after this level).
            'bloomWidthRatio': 0.6,  # Width-to-height ratio for the leaves (controls their shape).
            'bloomSizeAverage': 15,  # Average size of the leaves.
            'growingSpeed': 600,
            'lengthRand': 1.0,  # Random variation factor for branch length. (Used to add randomness to branch length).
            'startLength': 80,  # Initial length of the root branch (the trunk) of the tree.
            'startSize': 10,  # Initial thickness/size of the root branch (the trunk).
            'colors': [
                    self.get_color("color4a"),
                    self.get_color("color4b"),
                    self.get_color("color4c")
                ]
            }

    def setup(self):
        super().setup()
        self.background_color = self.get_backgroundcolor('backgroundColor4')
        py5.background(*self.background_color)
        reward_signal = self.signal_handler.get_signal()
        self.total_leaves = int(reward_signal * (self.max_leaves - self.min_leaves) + self.min_leaves)
        self.reset_tree()
        self.initialized = True

    def draw(self):
        if not self.initialized:
            return  # setup() not yet called (race on first frame)

        py5.no_stroke()
        # get_smooth_signal() applies a single consistent exponential smooth
        # and returns the direction-corrected reward score in [0, 1] where
        # 1.0 = maximum reward (feature moving in training direction).
        reward_signal = self.get_smooth_signal(alpha=0.08)

        if self.animation_complete:
            self.reset_tree()
            self.current_animation_level = 0
            self.animation_complete = False
            self.leaves.clear()
            return
        if self.node is None:
            return

        # Higher reward → more leaves (reward_signal 0→1 maps to min→max leaves)
        leaves_num = int(reward_signal * (self.max_leaves - self.min_leaves) + self.min_leaves)
        non_falling_leaves = [leaf for leaf in self.leaves if not leaf.falling]
        current_leaf_count = len(non_falling_leaves)

        if current_leaf_count < leaves_num:
            self.add_leaves(leaves_num - current_leaf_count)
        elif current_leaf_count > leaves_num:
            self.remove_leaves(current_leaf_count - leaves_num)

        py5.background(*self.background_color)  # Redraw background
        py5.push_matrix()
        py5.translate(py5.width / 2, py5.height)  # Start from the bottom center

        self.node.draw(self.current_animation_level)
        self.node.draw_leaves()

        # Check if all nodes at the current level are fully scaled
        if self.all_nodes_scaled(self.node, self.current_animation_level):
            self.current_animation_level += 1

        # Stop if all levels are animated
        if self.current_animation_level > self.params['levelMax']:
            self.animation_complete = True
        py5.pop_matrix()
        super().draw()

    def all_nodes_scaled(self, node, level):
        # If the current node is at the target level and not fully scaled, return False
        if node.level == level and node.s < 1.0:
            return False
        # Check all child nodes recursively
        return all(self.all_nodes_scaled(child, level) for child in node.children)

    def add_leaves(self, count):
        branches = []
        self.collect_leaf_branches(self.node, branches)

        # If there are no eligible branches, return early
        if not branches:
            return

        for _ in range(count):
            # Choose a random branch to attach a leaf
            branch = random.choice(branches)
            if branch.leaf is None:  # Add a leaf only if there's no leaf already
                branch.leaf = Leaf(self.params)
                # Add leaf to the list of leaves for animation purposes
                self.leaves.append(branch.leaf)

    def collect_leaf_branches(self, node, branches):
        if node.leaf is None:
            branches.append(node)

        for child in node.children:
            self.collect_leaf_branches(child, branches)

    def remove_leaves(self, count):
        # Filter out leaves that are already falling
        possible_falling_leaves = [leaf for leaf in self.leaves if not leaf.falling]
        # Select the leaves to mark as falling
        leaves_to_fall = possible_falling_leaves[:count]

        for leaf in leaves_to_fall:
            # Initiate the falling process for the leaf
            leaf.init_falling()

    def reset_tree(self):
        self.randomize_parameters()
        self.leaf_count = 0
        self.node = Node(self.params['startLength'],
                            self.params['startSize'],
                            self.params['rotRange'],
                            0,
                            self.params)

    def randomize_parameters(self):
        # Use Python random/math — no py5 JNI calls needed here.
        old_start_length = self.params['startLength']
        new_start_length = random.uniform(70, 100)
        self.params.update({
            'rotRange': random.uniform(30, 60),
            'rotDecay': random.uniform(0.9, 1.1),
            'startLength': new_start_length,
            'startSize': random.uniform(10, 15),
            'growingSpeed': random.uniform(50, 150),
            'lengthRand': random.uniform(0.0, 0.2),
            'sizeDecay': random.uniform(0.6, 0.7),
            # remap(old_start_length, 60, 100, 0.95, 1.1) — preserves original intent
            'lengthDecay': 0.95 + (old_start_length - 60) / (100 - 60) * (1.1 - 0.95),
            'leafLevel': random.uniform(0, 4),
            'bloomWidthRatio': random.uniform(0.2, 0.9),
            'bloomSizeAverage': random.uniform(10, 20)
        })
