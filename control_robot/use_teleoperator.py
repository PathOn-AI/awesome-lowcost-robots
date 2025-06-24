from lerobot.common.teleoperators.so101_leader import SO101LeaderConfig, SO101Leader 
import time

teleop_config = SO101LeaderConfig( port="/dev/tty.usbmodem5A680117941", id="my_awesome_101_leader_arm", )
teleop_device = SO101Leader(teleop_config)
teleop_device.connect()
bus = teleop_device.bus
time.sleep(2)


while True:
    position_dict = {}
    for key in bus.motors:
        position = bus.read("Present_Position", key)
        unnormalized_position = bus.read("Present_Position", key, normalize=False)
        position_dict[key] = unnormalized_position
    print(position_dict)
