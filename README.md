# Multi-Camera Capture System for Jetson

A robust Python-based system for capturing frames from multiple cameras attached to a Jetson device. This system is optimized for Jetson hardware and supports simultaneous capture from multiple cameras with configurable frame rates and output formats. Uses av (PyAV) for video capture and Pillow for image processing instead of OpenCV for better performance and modern video handling.

## Package layout and usage

- `recorder/`: holds the actual package code.
- `examples/run.py`: shows how to use it programmatically as a library (imports `recorder`).
- `setup.py`: lets you run `pip install -e .` and then use both CLI-style module execution and library imports.

### Install (editable)

```bash
pip install -e .
```

### Programmatic usage (see `examples/run.py`)

```python
from recorder.camera import CameraCapture
from recorder.multi_camera import MultiCameraCapture
from recorder.utils import load_config, get_setting

config = load_config("./recorder/config.yaml")
cameras = get_setting(None, config.get("cameras"), [0])
output_dir = get_setting(None, config.get("output_dir"), "./captured_frames")
fps = int(get_setting(None, config.get("fps"), 30))
duration = get_setting(None, config.get("duration"), None)

if len(cameras) == 1:
    CameraCapture(cameras[0], output_dir, fps).run(duration)
else:
    MultiCameraCapture(cameras, output_dir, fps).run(duration)
```

Note: A legacy script (`camera_capture.py`) still exists for direct script usage, but the recommended interface is the package API and the `recorder` CLI documented below.

### Example configuration

An example YAML config is provided at `examples/config.yaml`:

```yaml
# Capture configuration
# cameras: List of integer device IDs
# output_dir: Directory to save frames
# fps: Frames per second
# duration: Optional capture duration in seconds; omit or set null for continuous
cameras: [0]
output_dir: ./captured_frames
fps: 30
duration: null
```

### CLI usage (installed console script)

After `pip install -e .`, use the `recorder` command:

```bash
# Use config file
recorder --config examples/config.yaml

# Override via CLI flags
recorder --cameras 0 1 --fps 25 --output ./captures --duration 60

# Simple single-camera example
recorder --cameras 0 --output ./captured_frames --fps 15

# Windows camera names (use quotes for names with spaces)
recorder --cameras "Integrated Webcam" --output ./captured_frames --fps 15

# List available cameras
recorder --list-cameras
```

### Platform-specific camera handling

**Windows:**
- Use camera names like `"Integrated Webcam"`, `"USB2.0 HD UVC WebCam"`
- Run `--list-cameras` to see available camera names
- Supports both named cameras and numeric indices

**Linux/Jetson:**
- Use numeric camera IDs like `0`, `1`, `2`
- Cameras are typically `/dev/video0`, `/dev/video1`, etc.
- Jetson devices get optimized backend selection
