from time import sleep
import time
from lerobot.common.motors.feetech import FeetechMotorsBus, OperatingMode
from lerobot.common.motors import Motor, MotorCalibration, MotorNormMode
from lerobot.common.robots.so101_follower import SO101Follower, SO101FollowerConfig

## connect to the robot, change the port and id to the correct one
config = SO101FollowerConfig(
    port="/dev/tty.usbmodem5A460819711",
    id="my_awesome_101_follower_arm",
)
follower = SO101Follower(config)
bus = follower.bus
bus.connect()
print(bus.motors.keys())


## get rest position and zero position
rest_position = {}
zero_positions = {}
calibration = bus.read_calibration()
print(calibration)

for key in bus.motors:
    position = bus.read("Present_Position", key)
    unnormalized_position = bus.read("Present_Position", key, normalize=False)
    print(bus.motors[key])
    print(key, position, unnormalized_position)
    rest_position[key] = unnormalized_position
    zero_positions[key] = int((calibration[key].range_min + calibration[key].range_max) / 2)
    print(key, unnormalized_position, zero_positions[key])

few_steps = 10

## slowly move to zero position
motor_keys = list(bus.motors.keys())
current_positions = {}

step_sizes = {}

for key in motor_keys:
    current_positions[key] = bus.read("Present_Position", key, normalize=False)
    step_sizes[key] = (zero_positions[key] - current_positions[key]) / few_steps
    print(f"{key}: current={current_positions[key]}, zero={zero_positions[key]}")

# Move all motors together in coordinated steps to zero position
for i in range(few_steps):
    for key in motor_keys:
        new_pos = int(current_positions[key] + step_sizes[key] * (i + 1))
        bus.write("Goal_Position", key, new_pos, normalize=False)
    time.sleep(0.5)  # Slow movement with 0.5 second delays

time.sleep(2)  # Final pause

## slowly move back to rest position
for key in motor_keys:
    current_positions[key] = bus.read("Present_Position", key, normalize=False)
    # zero_positions[key] = int((calibration[key].range_min + calibration[key].range_max) / 2)
    step_sizes[key] = (rest_position[key] - current_positions[key]) / few_steps
    print(f"{key}: current={current_positions[key]}, zero={rest_position[key]}")

# Move all motors together in coordinated steps to zero position
for i in range(few_steps):
    for key in motor_keys:
        new_pos = int(current_positions[key] + step_sizes[key] * (i + 1))
        bus.write("Goal_Position", key, new_pos, normalize=False)
    time.sleep(0.5)  # Slow movement with 0.5 second delays

time.sleep(2)  # Final pause






