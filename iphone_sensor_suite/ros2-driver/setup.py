from setuptools import find_packages, setup

package_name = "ros2_driver"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/iphone_sensor.launch.py"]),
        ("share/" + package_name + "/rviz", ["rviz/iphone_sensor.rviz"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="PathOn Robotics",
    maintainer_email="danqing@pathon.ai",
    description="ROS2 driver for iPhone sensor streaming",
    license="MIT",
    entry_points={
        "console_scripts": [
            "iphone_sensor_node = ros2_driver.iphone_sensor_node:main",
        ],
    },
)
