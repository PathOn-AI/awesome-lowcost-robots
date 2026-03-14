from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("host", default_value="192.168.1.100",
                              description="iPhone IP address"),
        DeclareLaunchArgument("port", default_value="8888",
                              description="TCP port"),
        DeclareLaunchArgument("camera_name", default_value="camera",
                              description="Camera name prefix for topics and TF"),
        DeclareLaunchArgument("publish_pointcloud", default_value="true"),
        DeclareLaunchArgument("publish_aligned_depth", default_value="true"),
        DeclareLaunchArgument("publish_confidence", default_value="true"),
        DeclareLaunchArgument("publish_imu", default_value="true"),

        Node(
            package="ros2_driver",
            executable="iphone_sensor_node",
            name="iphone_sensor_node",
            output="screen",
            parameters=[{
                "host": LaunchConfiguration("host"),
                "port": LaunchConfiguration("port"),
                "camera_name": LaunchConfiguration("camera_name"),
                "publish_pointcloud": LaunchConfiguration("publish_pointcloud"),
                "publish_aligned_depth": LaunchConfiguration("publish_aligned_depth"),
                "publish_confidence": LaunchConfiguration("publish_confidence"),
                "publish_imu": LaunchConfiguration("publish_imu"),
            }],
        ),
    ])
