from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("host", default_value="192.168.1.100",
                              description="iPhone IP address"),
        DeclareLaunchArgument("port", default_value="8888",
                              description="TCP port"),
        DeclareLaunchArgument("usb", default_value="false",
                              description="Use USB (iproxy) instead of WiFi"),
        DeclareLaunchArgument("camera_name", default_value="camera",
                              description="Camera name prefix for topics and TF"),
        DeclareLaunchArgument("publish_pointcloud", default_value="true"),
        DeclareLaunchArgument("publish_aligned_depth", default_value="true"),
        DeclareLaunchArgument("publish_confidence", default_value="true"),
        DeclareLaunchArgument("publish_imu", default_value="true"),
        DeclareLaunchArgument("publish_scan", default_value="true",
                              description="Start pointcloud_to_laserscan node to publish /scan"),

        # pointcloud_to_laserscan parameters
        DeclareLaunchArgument("scan_target_frame", default_value="camera_link",
                              description="Frame in which the scan is sliced and published; "
                                          "use a level frame so the scan plane stays level when the camera tilts"),
        DeclareLaunchArgument("scan_min_height", default_value="0.10",
                              description="Min height (m) of obstacle band in target_frame"),
        DeclareLaunchArgument("scan_max_height", default_value="0.80",
                              description="Max height (m) of obstacle band in target_frame"),
        DeclareLaunchArgument("scan_range_min", default_value="0.1"),
        DeclareLaunchArgument("scan_range_max", default_value="5.0"),
        DeclareLaunchArgument("scan_angle_min", default_value="-1.5708",
                              description="Min scan angle (rad)"),
        DeclareLaunchArgument("scan_angle_max", default_value="1.5708",
                              description="Max scan angle (rad)"),
        DeclareLaunchArgument("scan_angle_increment", default_value="0.0087",
                              description="Scan angle increment (rad), ~0.5 deg"),

        Node(
            package="ros2_driver",
            executable="iphone_sensor_node",
            name="iphone_sensor_node",
            output="screen",
            parameters=[{
                "host": LaunchConfiguration("host"),
                "port": LaunchConfiguration("port"),
                "usb": LaunchConfiguration("usb"),
                "camera_name": LaunchConfiguration("camera_name"),
                "publish_pointcloud": LaunchConfiguration("publish_pointcloud"),
                "publish_aligned_depth": LaunchConfiguration("publish_aligned_depth"),
                "publish_confidence": LaunchConfiguration("publish_confidence"),
                "publish_imu": LaunchConfiguration("publish_imu"),
            }],
        ),

        Node(
            package="pointcloud_to_laserscan",
            executable="pointcloud_to_laserscan_node",
            name="pointcloud_to_laserscan",
            output="screen",
            condition=IfCondition(LaunchConfiguration("publish_scan")),
            remappings=[
                ("cloud_in", "depth/color/points"),
                ("scan", "scan"),
            ],
            parameters=[{
                "target_frame": LaunchConfiguration("scan_target_frame"),
                "transform_tolerance": 0.05,
                "min_height": LaunchConfiguration("scan_min_height"),
                "max_height": LaunchConfiguration("scan_max_height"),
                "angle_min": LaunchConfiguration("scan_angle_min"),
                "angle_max": LaunchConfiguration("scan_angle_max"),
                "angle_increment": LaunchConfiguration("scan_angle_increment"),
                "scan_time": 0.0333,
                "range_min": LaunchConfiguration("scan_range_min"),
                "range_max": LaunchConfiguration("scan_range_max"),
                "use_inf": True,
            }],
        ),
    ])
