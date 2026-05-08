#!/usr/bin/env python3
"""
Attach robot arm with end-effector using MuJoCo MjSpec API.

This script combines any compatible arm and end-effector models using the MjSpec attachment API.
The arm must have an 'attachment_site' where the end-effector will be mounted.

Note: Use 'mjpython' on macOS instead of 'python' for MuJoCo scripts.

Examples:
    # UR5e with Robotiq 2F85
    mjpython attach_arm_end_effector.py --arm ur5e/ur5e.xml --end-effector robotiq_2f85/2f85.xml --output ur5e_robotiq_2f85

    # SO101 arm with SO101 gripper
    mjpython attach_arm_end_effector.py --arm SO101_arm/so101_arm.xml --end-effector SO101_gripper/so101_gripper.xml --output SO101_arm_gripper

    # SO101 arm with Pincopen gripper
    mjpython attach_arm_end_effector.py --arm SO101_arm/so101_arm.xml --end-effector pincopen/gripper.xml --output SO101_arm_pincopen

Usage:
    mjpython attach_arm_end_effector.py --arm <arm_xml> --end-effector <eef_xml> --output <output_folder> [--prefix <prefix>]

Arguments:
    --arm: Path to arm model XML file (relative or absolute)
    --end-effector: Path to end-effector model XML file (relative or absolute)
    --output: Output folder name (will be created in same directory as this script)
    --prefix: Prefix for end-effector component names (default: "eef_")
    --no-viewer: Skip launching viewer after generation
"""
import mujoco
import argparse
from pathlib import Path
import shutil


def attach_arm_with_end_effector(arm_path, eef_path, output_dir, prefix="eef_"):
    """
    Attach end-effector to arm via attachment_site using MjSpec API.

    Args:
        arm_path: Path to arm model XML file
        eef_path: Path to end-effector model XML file
        output_dir: Path to output directory
        prefix: Prefix for end-effector component names

    Returns:
        tuple: (compiled_model, arm_spec, output_xml_path)
    """
    arm_path = Path(arm_path)
    eef_path = Path(eef_path)
    output_dir = Path(output_dir)

    print(f"Loading arm from: {arm_path}")
    print(f"Loading end-effector from: {eef_path}")

    # Load both models as MjSpec
    arm_spec = mujoco.MjSpec.from_file(str(arm_path))
    eef_spec = mujoco.MjSpec.from_file(str(eef_path))

    # Find the attachment site on the arm
    attachment_site = None
    for site in arm_spec.sites:
        if site.name == "attachment_site":
            attachment_site = site
            break

    if attachment_site is None:
        raise ValueError(f"Could not find 'attachment_site' in arm model: {arm_path}")

    print(f"\nFound attachment site: {attachment_site.name}")
    print(f"  Position: {attachment_site.pos}")
    print(f"  Quaternion: {attachment_site.quat}")

    # Attach the end-effector to the arm
    print(f"\nAttaching end-effector to arm with prefix '{prefix}'...")
    arm_spec.attach(eef_spec, prefix=prefix, site=attachment_site)

    # Compile the combined model
    print("Compiling combined model...")
    combined_model = arm_spec.compile()

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create assets directory
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    print(f"\nCreated output folder: {output_dir}")
    print("Copying mesh assets...")

    # Copy arm assets
    arm_assets = arm_path.parent / "assets"
    if arm_assets.exists():
        count = 0
        for mesh_file in arm_assets.glob("*"):
            if mesh_file.is_file():
                shutil.copy2(mesh_file, assets_dir / mesh_file.name)
                count += 1
        print(f"  Copied {count} files from {arm_assets.relative_to(Path.cwd())}/")

    # Copy end-effector assets
    eef_assets = eef_path.parent / "assets"
    if eef_assets.exists():
        count = 0
        for mesh_file in eef_assets.glob("*"):
            if mesh_file.is_file():
                dest_file = assets_dir / mesh_file.name
                if not dest_file.exists():
                    shutil.copy2(mesh_file, dest_file)
                    count += 1
        print(f"  Copied {count} files from {eef_assets.relative_to(Path.cwd())}/")

    # Generate output filenames based on output directory name
    model_name = output_dir.name
    output_mjb = output_dir / f"{model_name}.mjb"
    output_xml = output_dir / f"{model_name}.xml"

    # Save binary model
    mujoco.mj_saveModel(combined_model, str(output_mjb))
    print(f"\nSaved binary model to: {output_mjb}")

    # Save XML version
    xml_string = arm_spec.to_xml()
    with open(output_xml, 'w') as f:
        f.write(xml_string)
    print(f"Saved XML model to: {output_xml}")

    # Create a simple scene file
    scene_xml = output_dir / "scene.xml"
    scene_content = f"""<mujoco model="{model_name}_scene">
  <include file="{model_name}.xml"/>

  <statistic center="0.3 0 0.4" extent="0.8"/>

  <visual>
    <headlight diffuse="0.6 0.6 0.6" ambient="0.1 0.1 0.1" specular="0 0 0"/>
    <rgba haze="0.15 0.25 0.35 1"/>
    <global azimuth="120" elevation="-20"/>
  </visual>

  <asset>
    <texture type="skybox" builtin="gradient" rgb1="0.3 0.5 0.7" rgb2="0 0 0" width="512" height="3072"/>
    <texture type="2d" name="groundplane" builtin="checker" mark="edge" rgb1="0.2 0.3 0.4" rgb2="0.1 0.2 0.3"
      markrgb="0.8 0.8 0.8" width="300" height="300"/>
    <material name="groundplane" texture="groundplane" texuniform="true" texrepeat="5 5" reflectance="0.2"/>
  </asset>

  <worldbody>
    <light pos="0 0 1.5" dir="0 0 -1" directional="true"/>
    <geom name="floor" size="0 0 0.05" type="plane" material="groundplane"/>
  </worldbody>
</mujoco>
"""
    with open(scene_xml, 'w') as f:
        f.write(scene_content)
    print(f"Created scene file: {scene_xml}")

    # Create README.md
    readme_path = output_dir / "README.md"

    readme_content = f"""# {model_name}

Combined robot model created using MuJoCo MjSpec API.

## Components

- **Arm**: `{arm_path.relative_to(output_dir.parent)}`
- **End-effector**: `{eef_path.relative_to(output_dir.parent)}`
- **End-effector prefix**: `{prefix}`

## Model Statistics

- **Bodies**: {combined_model.nbody}
- **Actuators**: {combined_model.nu}

## Actuators

"""
    for i in range(combined_model.nu):
        act_name = combined_model.actuator(i).name
        readme_content += f"{i}. `{act_name}`\n"

    readme_content += f"""
## Files

- `{model_name}.xml` - Combined model in XML format
- `{model_name}.mjb` - Combined model in binary format
- `scene.xml` - Scene file with environment (floor, lighting)
- `assets/` - Mesh files from both arm and end-effector

## Usage

### View in MuJoCo viewer (macOS)
```bash
mjview scene.xml
```

### Load in Python (macOS)
```python
import mujoco

model = mujoco.MjModel.from_xml_path('scene.xml')
data = mujoco.MjData(model)
```

### Launch interactive viewer
```bash
mjpython -m mujoco.viewer scene.xml
```

## Generation

This model was generated using:
```bash
mjpython attach_arm_end_effector.py --arm {arm_path.relative_to(output_dir.parent)} --end-effector {eef_path.relative_to(output_dir.parent)} --output {model_name}
```
"""

    with open(readme_path, 'w') as f:
        f.write(readme_content)
    print(f"Created README: {readme_path}")

    # Print model statistics
    print(f"\nCombined model statistics:")
    print(f"  Bodies: {combined_model.nbody}")
    print(f"  Joints: {combined_model.njnt}")
    print(f"  Actuators: {combined_model.nu}")
    print(f"  DOFs: {combined_model.nv}")

    # List actuator names
    print(f"\nActuators:")
    for i in range(combined_model.nu):
        act_name = combined_model.actuator(i).name
        print(f"  [{i}] {act_name}")

    return combined_model, arm_spec, str(output_xml)


def test_combined_model(scene_path):
    """Load and test the combined model in viewer."""
    import mujoco.viewer

    print("\n" + "="*60)
    print("Testing combined model in viewer...")
    print("="*60)

    model = mujoco.MjModel.from_xml_path(str(scene_path))
    data = mujoco.MjData(model)

    print("\nLaunching viewer... Close window to exit.")
    print("Use sliders on right to control joints")

    # Launch viewer
    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            mujoco.mj_step(model, data)
            viewer.sync()


def main():
    parser = argparse.ArgumentParser(
        description='Attach robot arm with end-effector using MuJoCo MjSpec API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)

    parser.add_argument('--arm', required=True, help='Path to arm model XML file')
    parser.add_argument('--end-effector', required=True, dest='end_effector', help='Path to end-effector model XML file')
    parser.add_argument('--output', required=True, help='Output folder name')
    parser.add_argument('--prefix', default='eef_', help='Prefix for end-effector components (default: eef_)')
    parser.add_argument('--no-viewer', action='store_true', help='Skip launching viewer')

    args = parser.parse_args()

    # Get base directory (where this script is located)
    base_dir = Path(__file__).parent

    # Resolve paths (handle both relative and absolute)
    arm_path = Path(args.arm)
    if not arm_path.is_absolute():
        arm_path = base_dir / arm_path

    eef_path = Path(args.end_effector)
    if not eef_path.is_absolute():
        eef_path = base_dir / eef_path

    output_dir = base_dir / args.output

    # Attach the models
    combined_model, arm_spec, output_xml_path = attach_arm_with_end_effector(
        arm_path, eef_path, output_dir, args.prefix
    )

    # Test in viewer unless --no-viewer flag is set
    if not args.no_viewer:
        scene_path = output_dir / "scene.xml"
        response = input("\nLaunch viewer to test? (y/n): ")
        if response.lower() == 'y':
            test_combined_model(scene_path)
        else:
            print("\nDone! You can load the model with:")
            print(f"  python -m mujoco.viewer {scene_path}")
    else:
        print("\nDone!")


if __name__ == "__main__":
    main()
