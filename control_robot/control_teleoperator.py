from lerobot.common.teleoperators.so101_leader import SO101LeaderConfig, SO101Leader 
import time

teleop_config = SO101LeaderConfig( port="/dev/tty.usbmodem5A680117941", id="my_awesome_101_leader_arm", )
teleop_device = SO101Leader(teleop_config)
# teleop_device.connect()

bus = teleop_device.bus

print(bus.motors.keys())

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
