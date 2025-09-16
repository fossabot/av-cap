import argparse
import logging
import platform
from pathlib import Path

from .camera import CameraCapture
from .multi_camera import MultiCameraCapture
from .utils import load_config, get_setting, list_available_cameras, IS_WINDOWS, IS_LINUX, IS_JETSON

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Multi-Camera Capture System for Jetson")
    parser.add_argument("--config", type=str, default="./config.yaml",
                       help="Path to YAML config with cameras/output_dir/fps/duration (default: ./config.yaml)")
    parser.add_argument("--cameras", nargs="+", default=None,
                       help="Camera IDs or names to capture from (overrides config). On Windows, use names like 'Integrated Webcam'")
    parser.add_argument("--output", type=str, default=None,
                       help="Output directory for captured frames (overrides config)")
    parser.add_argument("--fps", type=int, default=None,
                       help="Frames per second for each camera (overrides config)")
    parser.add_argument("--duration", type=int, default=None,
                       help="Capture duration in seconds (default: continuous)")
    parser.add_argument("--list-cameras", action="store_true",
                       help="List available cameras and exit")

    args = parser.parse_args()

    # Handle list cameras option
    if args.list_cameras:
        print(f"Platform: {platform.system()}")
        print(f"Jetson detected: {IS_JETSON}")
        print("Scanning for available cameras...")
        
        available_cameras = list_available_cameras()
        if available_cameras:
            print(f"Found {len(available_cameras)} available cameras: {available_cameras}")
        else:
            print("No cameras found")
        return

    # Load config YAML from the path specified in --config
    config_data = {}
    config_path = Path(args.config) if args.config else None

    if config_path is not None and config_path.exists():
        try:
            config_data = load_config(args.config)
            logger.info(f"Loaded config from {config_path}")
        except Exception as e:
            logger.error(f"Failed to load config file {config_path}: {e}")
    else:
        logger.info("Config file not found; using CLI values or defaults")

    # Determine effective settings with CLI overriding config, and sensible defaults
    effective_cameras = get_setting(args.cameras, config_data.get("cameras"), [0])
    # Only coerce to int on Linux. On Windows/macOS, keep strings to support backend requirements.
    if IS_LINUX:
        try:
            effective_cameras = [int(cam) for cam in effective_cameras] if effective_cameras else [0]
        except (ValueError, TypeError):
            pass
    
    effective_output = get_setting(args.output, config_data.get("output_dir"), "./frames")
    effective_fps = int(get_setting(args.fps, config_data.get("fps"), 30))
    effective_duration = get_setting(args.duration, config_data.get("duration"), None)

    # Create output directory
    output_dir = Path(effective_output)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Starting multi-camera capture system")
    logger.info(f"Platform: {platform.system()}")
    logger.info(f"Jetson detected: {IS_JETSON}")
    logger.info(f"Cameras: {effective_cameras}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"FPS: {effective_fps}")

    # Choose the appropriate capture system based on camera count
    if len(effective_cameras) == 1:
        # Use single camera mode for better performance
        logger.info("Single camera detected - using optimized single camera mode")
        camera = CameraCapture(effective_cameras[0], str(output_dir), effective_fps)
        camera.run(effective_duration)
    else:
        # Use multi-camera mode with threading
        logger.info("Multiple cameras detected - using threaded multi-camera mode")
        capture_system = MultiCameraCapture(effective_cameras, str(output_dir), effective_fps)
        capture_system.run(effective_duration)


if __name__ == "__main__":
    main()
