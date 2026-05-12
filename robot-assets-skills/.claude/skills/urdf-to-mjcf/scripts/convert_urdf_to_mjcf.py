#!/usr/bin/env python3
"""Convert URDF to MJCF and apply deterministic post-conversion fixups."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


DEFAULT_VENDOR_PATH = Path("/home/aidy/Projects/pathonai_diy_pipeline/scripts/urdf2mjcf")


@dataclass(frozen=True)
class ControlProfile:
    name: str
    simulation_level: str
    calibration_source: str
    position_kp: float
    position_force: float | None
    joint_damping: float | None
    joint_armature: float | None
    joint_frictionloss: float | None


CONTROL_PROFILES: dict[str, ControlProfile] = {
    "generic": ControlProfile(
        name="generic",
        simulation_level="level_1_controllable",
        calibration_source="generic_defaults",
        position_kp=30.0,
        position_force=12.0,
        joint_damping=0.5,
        joint_armature=0.01,
        joint_frictionloss=None,
    ),
    "so101-sts3215": ControlProfile(
        name="so101-sts3215",
        simulation_level="level_1_controllable",
        calibration_source="template_estimate",
        position_kp=17.8,
        position_force=3.35,
        joint_damping=0.60,
        joint_armature=0.028,
        joint_frictionloss=0.052,
    ),
}


def resolve_control_profile(
    name: str,
    *,
    position_kp: float | None,
    position_force: float | None,
    joint_damping: float | None,
    joint_armature: float | None,
    joint_frictionloss: float | None,
) -> ControlProfile:
    profile = CONTROL_PROFILES[name]
    overridden = any(
        value is not None
        for value in (position_kp, position_force, joint_damping, joint_armature, joint_frictionloss)
    )
    return ControlProfile(
        name=profile.name,
        simulation_level=profile.simulation_level,
        calibration_source="manual_override" if overridden else profile.calibration_source,
        position_kp=profile.position_kp if position_kp is None else position_kp,
        position_force=profile.position_force if position_force is None else position_force,
        joint_damping=profile.joint_damping if joint_damping is None else joint_damping,
        joint_armature=profile.joint_armature if joint_armature is None else joint_armature,
        joint_frictionloss=profile.joint_frictionloss if joint_frictionloss is None else joint_frictionloss,
    )


def load_kscale_converter(vendor_path: Path | None):
    if vendor_path and vendor_path.exists():
        sys.path.insert(0, str(vendor_path))
    try:
        from urdf2mjcf.convert import convert_urdf_to_mjcf
    except Exception as exc:
        return None, exc
    return convert_urdf_to_mjcf, None


def convert_with_mujoco(urdf_path: Path, output_path: Path) -> None:
    import mujoco

    model = mujoco.MjModel.from_xml_path(str(urdf_path))
    mujoco.mj_saveLastXML(str(output_path), model)


def strip_file_uri(value: str) -> str:
    if value.startswith("file://"):
        return value.removeprefix("file://")
    return value


def find_asset_mesh(root: ET.Element, mesh_name: str) -> ET.Element | None:
    asset = root.find("asset")
    if asset is None:
        return None
    for mesh in asset.findall("mesh"):
        if mesh.get("name") == mesh_name:
            return mesh
    return None


def convert_motor_actuators_to_position(root: ET.Element, *, kp: float, force: float | None) -> list[str]:
    changes: list[str] = []
    joint_ranges: dict[str, str] = {}
    for joint in root.findall(".//joint"):
        name = joint.get("name")
        joint_range = joint.get("range")
        if name and joint_range:
            joint_ranges[name] = joint_range

    actuator = root.find("actuator")
    if actuator is None:
        return changes

    for index, child in enumerate(list(actuator)):
        if child.tag != "motor":
            continue
        joint_name = child.get("joint")
        if not joint_name:
            continue
        attrs = {
            "name": child.get("name") or f"{joint_name}_ctrl",
            "joint": joint_name,
            "kp": f"{kp:g}",
        }
        if joint_name in joint_ranges:
            attrs["ctrlrange"] = joint_ranges[joint_name]
        if force is not None:
            attrs["forcerange"] = f"{-force:g} {force:g}"
        position = ET.Element("position", attrs)
        actuator.remove(child)
        actuator.insert(index, position)
        changes.append("converted motor actuators to position")

    return changes


def postprocess_mjcf(
    path: Path,
    *,
    fixed_base: bool,
    add_joint_dynamics: bool,
    joint_damping: float | None,
    joint_armature: float | None,
    joint_frictionloss: float | None,
    position_actuators: bool,
    position_kp: float,
    position_force: float | None,
) -> list[str]:
    tree = ET.parse(path)
    root = tree.getroot()
    changes: list[str] = []

    compiler = root.find("compiler")
    if compiler is None:
        compiler = ET.Element("compiler", {"angle": "radian", "autolimits": "true"})
        root.insert(0, compiler)
        changes.append("added compiler")
    elif compiler.get("autolimits") != "true":
        compiler.set("autolimits", "true")
        changes.append("set compiler autolimits=true")

    option = root.find("option")
    if option is None:
        compiler_index = list(root).index(compiler)
        option = ET.Element("option", {"integrator": "implicitfast"})
        root.insert(compiler_index + 1, option)
        changes.append("added option integrator=implicitfast")
    elif option.get("integrator") is None:
        option.set("integrator", "implicitfast")
        changes.append("set option integrator=implicitfast")

    for mesh in root.findall(".//asset/mesh"):
        file_attr = mesh.get("file")
        if file_attr:
            stripped = strip_file_uri(file_attr)
            if stripped != file_attr:
                mesh.set("file", stripped)
                changes.append("stripped file:// mesh URI")

    for geom in root.findall(".//geom"):
        scale = geom.get("scale")
        mesh_name = geom.get("mesh")
        if scale and mesh_name:
            asset_mesh = find_asset_mesh(root, mesh_name)
            if asset_mesh is not None and asset_mesh.get("scale") is None:
                asset_mesh.set("scale", scale)
                changes.append("moved geom scale to asset mesh")
            del geom.attrib["scale"]

    for inertial in root.findall(".//inertial"):
        if inertial.get("pos") is None:
            inertial.set("pos", "0 0 0")
            changes.append("added inertial pos")

    for body in root.findall(".//body"):
        if body.get("name") == "world":
            body.set("name", "world_link")
            changes.append("renamed user body named world")

    for elem in root.iter():
        for attr in ("body", "body1", "body2", "target", "objname"):
            if elem.get(attr) == "world":
                elem.set(attr, "world_link")
                changes.append("updated world body reference")

    if fixed_base:
        for body in root.findall(".//body"):
            for freejoint in list(body.findall("freejoint")):
                body.remove(freejoint)
                changes.append("removed freejoint for fixed base")

    if add_joint_dynamics:
        for joint in root.findall(".//joint"):
            if joint_damping is not None and joint.get("damping") is None:
                joint.set("damping", f"{joint_damping:g}")
                changes.append("added joint damping")
            if joint_armature is not None and joint.get("armature") is None:
                joint.set("armature", f"{joint_armature:g}")
                changes.append("added joint armature")
            if joint_frictionloss is not None and joint.get("frictionloss") is None:
                joint.set("frictionloss", f"{joint_frictionloss:g}")
                changes.append("added joint frictionloss")

    if position_actuators:
        changes.extend(convert_motor_actuators_to_position(root, kp=position_kp, force=position_force))

    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=False)
    return sorted(set(changes))


def compile_report(path: Path) -> str:
    import mujoco

    model = mujoco.MjModel.from_xml_path(str(path))
    return (
        f"nq={model.nq} nu={model.nu} nbody={model.nbody} "
        f"njnt={model.njnt} ngeom={model.ngeom} nmesh={model.nmesh}"
    )


def sync_referenced_meshes(path: Path, source_dir: Path) -> list[str]:
    tree = ET.parse(path)
    root = tree.getroot()
    output_dir = path.parent
    copied: list[str] = []

    for mesh in root.findall(".//asset/mesh"):
        file_attr = mesh.get("file")
        if not file_attr:
            continue
        mesh_path = Path(file_attr)
        if mesh_path.is_absolute():
            continue
        output_mesh = output_dir / mesh_path
        if output_mesh.exists():
            continue
        source_mesh = source_dir / mesh_path
        if not source_mesh.exists():
            continue
        output_mesh.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_mesh, output_mesh)
        copied.append(str(mesh_path))

    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert URDF to MJCF and apply common fixups.")
    parser.add_argument("urdf", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--engine", choices=["auto", "kscale", "mujoco"], default="auto")
    parser.add_argument("--vendor-path", type=Path, default=Path(os.environ.get("URDF2MJCF_VENDOR_PATH", DEFAULT_VENDOR_PATH)))
    parser.add_argument("--copy-meshes", action="store_true")
    parser.add_argument("--floating-base", action="store_true", help="Keep converter-generated freejoint.")
    parser.add_argument("--no-joint-dynamics", action="store_true")
    parser.add_argument("--keep-motors", action="store_true", help="Keep K-Scale torque motor actuators instead of converting them to position actuators.")
    parser.add_argument("--control-profile", choices=sorted(CONTROL_PROFILES), default="generic")
    parser.add_argument("--position-kp", type=float)
    parser.add_argument("--position-force", type=float)
    parser.add_argument("--joint-damping", type=float)
    parser.add_argument("--joint-armature", type=float)
    parser.add_argument("--joint-frictionloss", type=float)
    parser.add_argument("--no-postprocess", action="store_true")
    args = parser.parse_args()
    control_profile = resolve_control_profile(
        args.control_profile,
        position_kp=args.position_kp,
        position_force=args.position_force,
        joint_damping=args.joint_damping,
        joint_armature=args.joint_armature,
        joint_frictionloss=args.joint_frictionloss,
    )

    urdf_path = args.urdf.resolve()
    if not urdf_path.exists():
        raise FileNotFoundError(f"URDF file not found: {urdf_path}")

    output_path = args.output.resolve() if args.output else urdf_path.with_suffix(".xml")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    engine_used = args.engine
    if args.engine in {"auto", "kscale"}:
        converter, error = load_kscale_converter(args.vendor_path)
        if converter is not None:
            converter(urdf_path=urdf_path, mjcf_path=output_path, copy_meshes=args.copy_meshes)
            engine_used = "kscale"
        elif args.engine == "kscale":
            raise RuntimeError(f"Unable to load kscale urdf2mjcf: {error}") from error
        else:
            convert_with_mujoco(urdf_path, output_path)
            engine_used = "mujoco"
    else:
        convert_with_mujoco(urdf_path, output_path)

    changes: list[str] = []
    if not args.no_postprocess:
        changes = postprocess_mjcf(
            output_path,
            fixed_base=not args.floating_base,
            add_joint_dynamics=not args.no_joint_dynamics,
            joint_damping=control_profile.joint_damping,
            joint_armature=control_profile.joint_armature,
            joint_frictionloss=control_profile.joint_frictionloss,
            position_actuators=not args.keep_motors,
            position_kp=control_profile.position_kp,
            position_force=control_profile.position_force,
        )
        copied = sync_referenced_meshes(output_path, urdf_path.parent)
        if copied:
            changes.append(f"copied {len(copied)} referenced meshes")

    print(f"engine={engine_used}")
    print(f"output={output_path}")
    if args.no_postprocess:
        print("simulation_level=level_0_loadable")
        print("actuator_source=none")
        print("calibration_source=none")
    elif args.keep_motors:
        print("simulation_level=level_0_loadable")
        print(f"actuator_source={engine_used}_motor_defaults")
        print("calibration_source=converter_defaults")
    else:
        print(f"simulation_level={control_profile.simulation_level}")
        print(f"actuator_source=position_actuators:{control_profile.name}")
        print(f"calibration_source={control_profile.calibration_source}")
    if changes:
        print("postprocess=" + ", ".join(changes))
    else:
        print("postprocess=none")
    print("compile " + compile_report(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
