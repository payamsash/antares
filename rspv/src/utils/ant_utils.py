# src/utils/ant_utils.py
# pylint: disable=no-member

import json
import argparse
import py5
import random
import math

def load_config(config_file_path):
    """
    Load the configuration from a JSON file.
    
    Args:
        config_file_path (str): Path to the JSON config file.
    
    Returns:
        dict: Loaded configuration as a dictionary.
    """
    try:
        with open(config_file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"Config file not found: {config_file_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format in config file: {config_file_path}")
    
def parse_arguments():
    """
    Parse command-line arguments for the config file.
    
    Returns:
        argparse.Namespace: Parsed arguments containing the config file path.
    """
    parser = argparse.ArgumentParser(description="Main script for Alpha Wave generation and Rendering")
    parser.add_argument('config', type=str, help="Path to the main config JSON file")
    return parser.parse_args()


def random_position(center, radius):
    angle = random.uniform(0, math.tau)
    return center + py5.Py5Vector(math.cos(angle), math.sin(angle)) * radius


def limit_vector(v, max_mag):
    mag = v.mag
    if mag > max_mag and mag != 0:
        v = (v / mag) * max_mag
    return v

# -------------------------------------------------------------
# Signal smoothing and hysteresis utilities
# -------------------------------------------------------------

# Keep a persistent smoothed signal between calls
_last_smoothed_value = None

def smooth_signal(raw_value, alpha=0.05):
    """
    Exponential smoother for jittery signals.
    Keeps a persistent internal value across frames.
    Smaller alpha = smoother, slower response.
    """
    global _last_smoothed_value
    if _last_smoothed_value is None:
        _last_smoothed_value = raw_value
    else:
        _last_smoothed_value = (1 - alpha) * _last_smoothed_value + alpha * raw_value
    return _last_smoothed_value


def apply_hysteresis(signal_value, connect_threshold=0.86, disconnect_threshold=0.50, previous_state=False):
    """
    Apply hysteresis to prevent rapid toggling around thresholds.
    Keeps state: returns True only if stable connection conditions hold.
    """
    if previous_state:  # already connected
        if signal_value < disconnect_threshold:
            return False
        return True
    else:
        if signal_value > connect_threshold:
            return True
        return False
