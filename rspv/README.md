# Generative Visuals from OSC Signals

A Python library that generates real-time generative visuals using data from OpenBCI sensors, generated signals, files, or LSL streams.

## Table of Contents
- [Generative Visuals from OSC Signals](#generative-visuals-from-osc-signals)
  - [Table of Contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Features](#features)
  - [Project Structure](#project-structure)
  - [Requirements](#requirements)
  - [Installation](#installation)
    - [with venv](#with-venv)
    - [with Conda](#with-conda)
    - [Configurable Parameters:](#configurable-parameters)
  - [Available Visual Presets](#available-visual-presets)
  - [Extending the Library](#extending-the-library)
    - [Example of a Minimal Visual Preset:](#example-of-a-minimal-visual-preset)

## Introduction
This Python project leverages the py5 library (Processing in Python) to create real-time generative visuals by processing brain waves signals. It supports multiple signal sources, including OpenBCI sensors, generated signals, pre-recorded files, and LSL streams.

## Features
- **Real-Time Signal Processing**: Visualize signals from OpenBCI sensors or other inputs (from file, from lsl, ...).
- **Pre-Defined Visual Presets**: A collection of ready-to-use, aesthetically rich visualizations.
- **Customizable Configuration**: Use a `config.json` file to adjust signal sources and visual presets.
- **Multi-Source Compatibility**: Supports OpenBCI, LSL streams, generated signals, and files.
- **Extensible Architecture**: Easily add new visual presets or signal processing methods.

## Project Structure
```plaintext
.
├── assets
│   ├── fonts          # Font files for visuals
│   └── images         # Images used in visuals
├── docs               # Documentation and project information
├── examples           # Example scripts for using the library
├── src
│   ├── rendering      # Visual rendering code
│   ├── signal_processing
│   │   ├── alpha_waves.py     # Alpha wave signal generation and processing
│   │   └── signal_handler.py  # OSC signal handling logic
│   ├── utils          # Utility functions
│   └── visuals
│       ├── shaders    # Shader files for advanced visual effects
│       └── visual_preset1.py   # Visual preset 1
│   └── version.py     # Version information for the project
├── tests              # Unit tests for the project
├── venv               # Virtual environment for the project
└── config.json        # Configuration file to customize signal source and visuals
```

## Requirements

Below are the requirements for using this library:

1. **Python 3.10+**

2. **Java 17+ (but preferably Java 21+)**
    - Make sure Env path are properly set-up
    - Look for JAVA_HOME (on Windows)
3. **Hardware Requirements**:
   - For OpenBCI: Use OSC to communicate the power band - address "/openbci/band-power/2", port: 12346.
   - For LSL: An LSL-compatible device or stream.
   - For generated signals: No additional hardware is required.
   - For pre-recorded files: Nothing additional is required.

## Installation
1. Ensure your Python 3.9+ installation path is defined in your system's PATH.

2. Clone the repository:
    ```bash
    git clone git@gitlab.uzh.ch:ant/rspv.git
    ```

### with venv
3. Set up a virtual environment (optional but recommended):
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: .\env\Scripts\activate or venv\Scripts\activate
    ```

4. Navigate to the project directory and install dependencies:
    ```bash
    cd rspv
    pip install -r requirements.txt
    ```

### with Conda
3. Create a Conda environment:
   ```bash
   conda env create -f environment.yml

4. Activate Conda
    ```bash
    conda activate rspv

## Usage

### Basic Usage

1. Configure the signal source and visual presets in the `config.json` file.
2. Run the main script to start processing signals and rendering visuals:
    ```bash
    python src/main.py config.json
    ```

### Customizing Presets
To customize visual behavior:
1. Edit the `config.json` file to modify signal source parameters or visual presets.
2. Create new presets by adding files to the `src/visuals` directory and registering them in `src/main.py`.

## Configuration

The configuration is defined in the `config.json` file, which is used to set up parameters for signal sourcing, visualization, color schemes, and recording options.

```json
{
    "signal_source": {
        "file": {
            "file_signal_path": "Signal.txt",
            "duration": 120
        },
        "_generated": {
            "duration": 120,
            "osc_ip": "127.0.0.1",
            "osc_port": 12346,
            "osc_address": "/openbci/band-power/2"
        },
        "_lsl": {},
        "_osc": {
            "osc_ip": "127.0.0.1",
            "osc_port": 12346,
            "osc_address": "/openbci/band-power/2"
        }
    },
    "min_power": 0.0,
    "max_power": 50.0,
    "sample_rate": 0.1,
    "visual_preset": "VisualSunflower",
    "is_full_screen": true,
    "colors": {
        "color1a": [58, 71, 102],
        "color1b": [111, 136, 196],
        "color1c": [91, 112, 212],
        "color2": [12, 90, 110],
        "color3a": [50, 32, 115],
        "color3b": [88, 59, 196],
        "color3c": [183, 173, 217],
        "color4a": [115, 35, 99],
        "color4b": [166, 83, 150],
        "color4c": [214, 189, 217],
        "color5": [115, 35, 36],
        "color6": [115, 100, 35],
        "color7": [35, 115, 92],
        "universalColor": [],
        "backgroundColor1": [242, 244, 247],
        "backgroundColor2": [240, 246, 247],
        "backgroundColor3": [246, 245, 250],
        "backgroundColor4": [249, 240, 250],
        "backgroundColor5": [250, 240, 240],
        "backgroundColor6": [250, 249, 240],
        "backgroundColor7": [240, 250, 248],
        "paperColor": [252, 232, 225],
        "universalBackgroundColor": []
    },
    "draw_signal_mode": {
        "enabled": true,
        "min_range_viz": 8,
        "max_range_viz": 13
    }
}
```

### Configurable Parameters:

#### signal_source:

- **file**:
  - `file_signal_path`: File path to the signal data (e.g., `Signal.txt`).
  - `duration`: Duration in seconds for the signal playback.

- **generated**:
  - `duration`: Duration in seconds for the generated signal.
  - `osc_ip`: IP address for the OSC server.
  - `osc_port`: Port for OSC communication.
  - `osc_address`: OSC address pattern for incoming messages.

- **lsl**: Leave empty for LSL configuration.

- **osc**: The configuration for the OSC signal source, including:
  - `osc_ip`: IP address for the OSC server.
  - `osc_port`: Port for OSC communication.
  - `osc_address`: OSC address pattern for incoming messages.

#### min_power:
- Minimum value of the incoming signal.

#### max_power:
- Maximum value of the incoming signal.

#### sample_rate:
- The sampling rate for the signal (in seconds).

#### visual_preset:
- The name of the visual preset to render (e.g., `VisualSunflower`).

#### is_full_screen:
- A boolean value to specify if the visual should be displayed in full-screen mode.

#### colors:
Defines the color scheme for various visual elements, including:
- `color1a`, `color1b`, `color1c`: Primary colors.
- `color2`, `color3a`, `color3b`, `color3c`: Secondary and accent colors.
- `backgroundColor1` to `backgroundColor7`: Various background color shades.
- `paperColor`: Color for paper elements.
- `universalColor`, `universalBackgroundColor`: define a consistent color scheme across the visuals

#### draw input process signal
- **draw_signal_mode**: An object controlling the on‑screen signal plot:

- ***enabled (bool)***: whether to launch the live signal visualization. Default is "true".

- ***min_range_viz (number)***: minimum signal value mapped to the bottom of the plot.

- ***max_range_viz (number)***: maximum signal value mapped to the top of the plot.

- ***window_x (number)***: the horizontal screen coordinate where the visualization window opens. Optional; defaults to 0.

- ***window_y (number)***: the vertical screen coordinate where the visualization window opens. Optional; defaults to 0.

## Available Visual Presets
The library includes a variety of pre-defined visual presets. see main.py for updated list
below a list (warning may not be up to data):

- **VisualRorschach**: Symmetrical inkblot-inspired visualization.
- **VisualEllipses**: Dynamic ellipses forming evolving patterns.
- **VisualWire**: Lines wrapped around a sphere.
- **VisualSunflower**: Sunflower seed-inspired visualization.
- **VisualGalaxySpiral**: Starfield galaxy with rotational depth.
- **VisualRings**: Concentric expanding and contracting rings.
- **VisualFlowField**: Flow field visualization using vector fields.
- **VisualAmoeba**: Organic shapes with amoeba-like movements.
- **VisualTree**: L-system-based fractals with custom rules.
- **VisualVogel**: Cavernous-like forms.

### Visual Preset Parameters
Every visual preset is influenced by the alpha signal, which affects its appearance and behavior in different ways. Below is a list of how each visual responds to changes in the alpha signal.

- **VisualRorschach**:
  - Influences the size of the inkblot effect. Larger alpha signal values shrink the drawing, while smaller values enlarge it.
  - Controls texture complexity, affecting the detail level in the inkblot.

- **VisualEllipses**:
  - A higher alpha signal results in:
    - Increased tilt of the ellipses.
    - More distortion due to tilt interacting with noise.
    - Greater separation adjustments between ellipses.
  - A lower alpha signal results in:
    - Reduced tilt, making the ellipses more aligned.
    - Less distortion, leading to a more structured pattern.
    - Minimal spacing adjustments, keeping the ellipses more evenly distributed.

- **VisualWire**:
  - Higher alpha signals:
    - Larger and more detailed sphere, with a stable shape.
  - Lower alpha signals:
    - The sphere contracts, with randomized distortions in its structure.

- **VisualSunflower**:
  - Scaling Effect: The alpha signal scales the entire visual (scale), making the pattern expand (low alpha) or shrink (high alpha).
  - Pattern Complexity: The number of subdivisions (dynamic_N) increases with higher alpha, adding finer details to the structure.

- **VisualGalaxySpiral**:
  - Scaling Effect: Higher alpha expands the visual structure, making patterns appear smaller (scale).
  - Animation Speed: The speed of movement increases with higher alpha (speed), creating a faster flow in the visual.
  - Pattern Complexity: Alpha waves modulate the layering of noise and textures, affecting the density and contrast of the generated forms.
  - Elliptical Distortions: The tilting and spacing of ellipses shift dynamically based on alpha input, subtly modifying shapes and structures over time.

- **VisualRings**:
  - Ring Size: Higher alpha signals reduce the ring size (alpha_scale), while lower signals enlarge them.
  - Animation Speed: The speed of movement (alpha_speed) increases with alpha levels, making rings evolve faster.
  - Ring Deformation: Alpha influences noise-based distortions (dynamic_amp), affecting the waviness of rings.
  - Resolution: Higher alpha reduces vertex count (dynamic_res), making rings smoother, while lower values increase complexity.
  - Stroke Weight: Adjusts based on alpha signal, subtly affecting line thickness of the rings.

- **VisualFlowField**:
  - When alpha signals are higher:
    - Particles move within a smaller radius.
    - Particles are fewer in number.
    - Motion is more concentrated toward the center.
  - When alpha signals are lower:
    - Particles spread out over a larger radius.
    - Particles are more numerous.
    - Movement pattern becomes more chaotic.

- **VisualAmoeba**:
  - When alpha signals are lower:
    - Triggers synchronized movement.
    - Adds new amoebas if the count is below 50.
    - Rotates the canvas.
  - When alpha signals are higher:
    - Stops rotation.
    - Sets amoebas to free movement.
    - Removes random amoebas if more than 20 remain.
  - When alpha signals are intermediate:
    - Stops rotation and allows free movement.

- **VisualTree**:
  - Leaf Count: The number of leaves dynamically adjusts based on the alpha signal, mapped between a minimum (8) and maximum (100) leaf count.
  - Tree Animation: The tree grows progressively, and each level of branches animates sequentially based on the alpha signal.
  - Leaf Addition/Removal: If the current leaf count is lower than the mapped alpha signal, new leaves are added. If it is higher, leaves start falling.
  - Randomized Growth Parameters: The tree resets periodically, randomizing growth parameters influenced indirectly by the alpha signal.

### Configuring Multiple Visual Presets
You can define a set of visuals to be used in sequence by specifying an array in the config.json file under the "visual_preset" key. For example:

```json
"visual_preset": ["VisualRorschach", "VisualSunflower", "VisualGalaxySpiral", "VisualRings"]
```

With this setup, the system will cycle through the listed visual presets during execution.

## Extending the Library
To add new visual presets:

1. Create a new file in the `src/visuals` directory.
2. Implement a class with at least the `draw()` method. Optionally, include `settings()` and `setup()` methods for further customization.
3. Register the new class in the `VISUAL_PRESETS` dictionary in `src/main.py`.
4. Update the `visual_preset` parameter in `config.json` to use your new preset.

### Example of a Minimal Visual Preset:

```python
class VisualCustom:
    def setup(self):
        py5.size(800, 600)
    
    def draw(self):
        py5.background(0)
        py5.fill(255, 0, 0)
        py5.ellipse(py5.width / 2, py5.height / 2, 100, 100)
```