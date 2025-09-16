from setuptools import setup, find_packages

setup(
    name="recorder",
    version="0.1.0",
    description="Multi-Camera Capture System for Jetson, Linux, Windows, and macOS using PyAV",
    author="Jetson Multi-Camera Recorder",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "av==12.3.0",
        "Pillow==10.4.0",
        "PyYAML==5.3.1",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "recorder=recorder.main:main",
        ],
    },
)
