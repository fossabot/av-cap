from setuptools import setup, find_packages

setup(
    name="recorder",
    version="0.2.0",
    description="Multi-Camera Capture System for Jetson, Linux, Windows, and macOS using PyAV",
    long_description="A cross-platform multi-camera capture system that uses PyAV for video capture and Pillow for image processing. Supports Windows DirectShow, Linux V4L2, and macOS AVFoundation backends.",
    author="Jetson Multi-Camera Recorder",
    url="https://github.com/your-username/jetson-multicamera-recorder",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "av>=10.0.0",
        "Pillow>=9.0.0",
        "PyYAML>=6.0",
    ],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Multimedia :: Video :: Capture",
        "Topic :: Scientific/Engineering :: Image Processing",
    ],
    entry_points={
        "console_scripts": [
            "recorder=recorder.main:main",
        ],
    },
    keywords="camera capture video recording jetson opencv pyav pillow multi-camera",
)
