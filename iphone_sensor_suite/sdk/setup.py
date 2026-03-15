from setuptools import setup, find_packages

setup(
    name="iphone-sensor-sdk",
    version="0.1.0",
    description="Python client for iPhone RGBD streaming",
    author="PathOn Robotics",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "numpy>=1.20.0",
        "opencv-python>=4.5.0",
    ],
    extras_require={
        "visualization": ["open3d>=0.17.0"],
    },
    entry_points={
        "console_scripts": [
            "iphone-sensor-viewer=examples.simple_viewer:main",
        ],
    },
)
