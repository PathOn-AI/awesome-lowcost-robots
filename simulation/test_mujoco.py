"""
MuJoCo SO-ARM100 Robot Control - Actually Working Version

Real user input that actually works on macOS with MuJoCo.
Uses threading to handle input without blocking the viewer.

Usage:
    mjpython script.py --control threaded_input
    mjpython script.py --control pause_input
    mjpython script.py --control continuous
"""

import mujoco
import mujoco.viewer
import numpy as np
import time
import argparse
import threading
import queue
import sys

# Load the XML model
model = mujoco.MjModel.from_xml_path("trs_so_arm100/so_arm100.xml")
data = mujoco.MjData(model)

def reset_simulation():
    """Reset the simulation to initial state"""
    mujoco.mj_resetData(model, data)
    mujoco.mj_forward(model, data)

# Global variables for control
current_targets = np.zeros(6)
control_increment = 0.05
simulation_running = True
joint_limits = [
    (-2.2, 2.2),         # Rotation
    (-3.14158, 0.2),     # Pitch
    (0.0, 3.14158),      # Elbow
    (-2.0, 1.8),         # Wrist_Pitch
    (-3.14158, 3.14158), # Wrist_Roll
    (-0.2, 2.0)          # Jaw
]

joint_names = ["Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll", "Jaw"]

def apply_pd_control():
    """Apply PD control to reach target positions"""
    kp = 50.0  # Proportional gain
    kd = 5.0   # Derivative gain
    
    current_pos = data.qpos[:model.nv]
    current_vel = data.qvel[:model.nv]
    
    position_error = current_targets[:len(current_pos)] - current_pos
    velocity_error = -current_vel
    
    control_torques = kp * position_error + kd * velocity_error
    data.ctrl[:] = control_torques[:model.nu]

def update_joint_target(joint_idx, direction):
    """Update target position for a specific joint"""
    global current_targets, control_increment
    
    if joint_idx < len(current_targets):
        delta = direction * control_increment
        new_target = current_targets[joint_idx] + delta
        
        # Apply joint limits
        min_limit, max_limit = joint_limits[joint_idx]
        current_targets[joint_idx] = np.clip(new_target, min_limit, max_limit)
        
        print(f"🎮 {joint_names[joint_idx]}: {current_targets[joint_idx]:.3f}")

def input_thread(command_queue):
    """Background thread to handle user input"""
    global simulation_running
    
    print("\n🎮 ROBOT CONTROL STARTED!")
    print("Enter commands (type 'help' for options):")
    
    while simulation_running:
        try:
            cmd = input("> ").strip().lower()
            command_queue.put(cmd)
            if cmd in ['quit', 'exit']:
                simulation_running = False
                break
        except EOFError:
            simulation_running = False
            break
        except KeyboardInterrupt:
            simulation_running = False
            break

def process_command(cmd, command_queue):
    """Process a single command"""
    global control_increment, current_targets, simulation_running
    
    if cmd == 'help':
        print("\n" + "="*50)
        print("🎮 ROBOT CONTROL COMMANDS")
        print("="*50)
        print("Joint Controls:")
        print("  q+ / q-  : Rotation joint")
        print("  w+ / w-  : Pitch joint")
        print("  e+ / e-  : Elbow joint")
        print("  r+ / r-  : Wrist Pitch joint")
        print("  t+ / t-  : Wrist Roll joint")
        print("  y+ / y-  : Jaw joint")
        print("\nUtility Commands:")
        print("  reset    : Reset all joints to zero")
        print("  status   : Show current positions")
        print("  speed X  : Set speed (e.g., 'speed 0.1')")
        print("  help     : Show this help")
        print("  quit     : Exit")
        print("="*50)
        
    elif cmd in ['quit', 'exit']:
        print("🛑 Exiting...")
        simulation_running = False
        return False
        
    elif cmd == 'reset':
        current_targets.fill(0)
        print("🔄 Reset all joints to zero")
        
    elif cmd == 'status':
        print(f"📊 Target positions:")
        for i, name in enumerate(joint_names):
            if i < len(current_targets):
                print(f"   {name}: {current_targets[i]:.3f}")
        print(f"📊 Current positions: {data.qpos[:model.nv]}")
        print(f"📊 Control speed: {control_increment}")
        
    elif cmd.startswith('speed '):
        try:
            new_speed = float(cmd.split()[1])
            control_increment = max(0.001, min(0.2, new_speed))
            print(f"⚡ Speed set to: {control_increment}")
        except:
            print("❌ Invalid speed. Use: speed 0.05")
            
    elif len(cmd) == 2 and cmd[1] in ['+', '-']:
        # Joint control commands
        joint_char = cmd[0]
        direction = 1 if cmd[1] == '+' else -1
        
        joint_map = {'q': 0, 'w': 1, 'e': 2, 'r': 3, 't': 4, 'y': 5}
        if joint_char in joint_map:
            update_joint_target(joint_map[joint_char], direction)
        else:
            print("❌ Unknown joint. Use: q, w, e, r, t, y")
            
    elif cmd == '':
        pass  # Empty command, do nothing
        
    else:
        print("❌ Unknown command. Type 'help' for available commands.")
    
    return True

def threaded_input_control():
    """Method 1: Threaded input control - Real user input with continuous simulation"""
    print("\n=== Threaded Input Control ===")
    print("This runs the simulation continuously while accepting your commands.")
    
    reset_simulation()
    global current_targets, simulation_running
    current_targets = data.qpos[:model.nu].copy()
    simulation_running = True
    
    # Create command queue for thread communication
    command_queue = queue.Queue()
    
    # Start input thread
    input_thread_obj = threading.Thread(target=input_thread, args=(command_queue,), daemon=True)
    input_thread_obj.start()
    
    with mujoco.viewer.launch_passive(model, data) as viewer:
        step = 0
        last_status_time = time.time()
        
        while viewer.is_running() and simulation_running:
            # Check for new commands
            try:
                while True:
                    cmd = command_queue.get_nowait()
                    if not process_command(cmd, command_queue):
                        simulation_running = False
                        break
            except queue.Empty:
                pass
            
            # Apply control and step simulation
            apply_pd_control()
            mujoco.mj_step(model, data)
            viewer.sync()
            
            # Occasional status update
            if time.time() - last_status_time > 10.0:
                print(f"📈 Step {step} - Simulation running. Type 'status' for positions.")
                last_status_time = time.time()
            
            step += 1
            time.sleep(0.01)
    
    simulation_running = False

def pause_input_control():
    """Method 2: Pause-and-input control - Simulation pauses for each command"""
    print("\n=== Pause Input Control ===")
    print("Simulation pauses while you enter commands, then runs the action.")
    
    reset_simulation()
    global current_targets
    current_targets = data.qpos[:model.nu].copy()
    
    with mujoco.viewer.launch_passive(model, data) as viewer:
        print("\n🚀 Simulation started!")
        print("Type 'help' for commands.")
        
        while viewer.is_running():
            # Get user input
            try:
                cmd = input("\n> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                break
            
            # Process command
            if not process_command(cmd, None):
                break
            
            # Run simulation for a bit to show the change
            print("⚙️  Applying command...")
            for _ in range(200):  # Run for 2 seconds at 100Hz
                if not viewer.is_running():
                    return
                apply_pd_control()
                mujoco.mj_step(model, data)
                viewer.sync()
                time.sleep(0.01)

def continuous_control():
    """Method 3: Continuous movement control"""
    print("\n=== Continuous Control ===")
    print("Enter a sequence of commands to execute continuously.")
    
    reset_simulation()
    global current_targets
    current_targets = data.qpos[:model.nu].copy()
    
    # Get sequence of commands
    print("\nEnter commands separated by spaces (e.g., 'q+ w+ e- reset r+')")
    print("Or type individual commands and press Enter:")
    
    commands = []
    
    try:
        while True:
            cmd_input = input("Command (or 'done' to start): ").strip().lower()
            if cmd_input == 'done':
                break
            elif cmd_input == 'quit':
                return
            elif cmd_input:
                if ' ' in cmd_input:
                    commands.extend(cmd_input.split())
                else:
                    commands.append(cmd_input)
                print(f"Added: {cmd_input}")
    except (EOFError, KeyboardInterrupt):
        return
    
    if not commands:
        print("No commands entered!")
        return
    
    print(f"\n🚀 Executing sequence: {' '.join(commands)}")
    
    with mujoco.viewer.launch_passive(model, data) as viewer:
        for cmd in commands:
            if not viewer.is_running():
                break
                
            print(f"\n⚙️  Executing: {cmd}")
            process_command(cmd, None)
            
            # Run simulation for each command
            for _ in range(300):  # 3 seconds per command
                if not viewer.is_running():
                    return
                apply_pd_control()
                mujoco.mj_step(model, data)
                viewer.sync()
                time.sleep(0.01)
        
        print("\n✅ Sequence completed!")
        print("Simulation will continue running. Close viewer to exit.")
        
        # Keep running
        while viewer.is_running():
            apply_pd_control()
            mujoco.mj_step(model, data)
            viewer.sync()
            time.sleep(0.01)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MuJoCo Robot Control - Working Input Methods')
    parser.add_argument('--control', 
                       choices=['threaded_input', 'pause_input', 'continuous'], 
                       default='threaded_input', 
                       help='Control method to use')
    
    args = parser.parse_args()
    
    print(f"🎮 Starting {args.control} control method...")
    
    try:
        if args.control == 'threaded_input':
            threaded_input_control()
        elif args.control == 'pause_input':
            pause_input_control()
        elif args.control == 'continuous':
            continuous_control()
            
    except KeyboardInterrupt:
        print("\n🛑 Control interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("👋 Control session ended")