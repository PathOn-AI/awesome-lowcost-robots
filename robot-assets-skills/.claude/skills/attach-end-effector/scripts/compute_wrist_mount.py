#!/usr/bin/env python3
"""Compute the wrist-mount pos + quat for an end-effector MJCF.

Why this exists. After `attach_arm_end_effector.py` runs, the prefixed
root body of the end-effector usually needs three things fixed by hand:

1. Orientation. The script copies the standalone eef root body's quat
   onto the combined model. This composes with the arm's
   `attachment_site` quat in unpredictable ways — the standalone palm
   may end up rotated 90°/180° from where it should mount.
2. Translation along the flange-out axis. Some standalone eefs
   (notably mujoco_menagerie's wonik_allegro) place the palm body's
   *origin* on the front face of the palm; without an offset the back
   half of the palm sits inside the wrist link.
3. The translation direction is in the WRIST BODY FRAME, not the site
   frame. If the arm's attachment_site has a non-trivial quat
   (e.g. SO101's site is +90° around Y), then a naive `pos="0 0 H"`
   translates the palm along the wrong axis (e.g. world Z instead of
   the flange-out direction).

This helper computes all three correctly given both the arm and the
eef MJCF:

- Reads `<site name="<site-name>"/>` (default `attachment_site`) from
  the arm to get the site's quat + pos relative to the wrist body.
- Walks the eef root body's descendants, computes their centroid in
  root-local frame, and picks the dominant principal axis (one of
  ±X/±Y/±Z) as the "fingers-out" axis.
- Composes the alignment rotation Q_align (out-axis → site +Z),
  optional twist Q_twist around site +Z, and the site's own quat
  Q_site to produce the palm body's quat in wrist body frame:
      Q_palm = Q_site * Q_twist * Q_align
- Computes H as the negative-Z extent of the root body's COLLISION
  geoms after applying Q_twist * Q_align (so H is in site frame).
- Translates the palm in wrist body frame by H along site +Z, plus the
  site's pos offset:
      pos = site_pos + R(Q_site) @ (0, 0, H)

Convention: collision-flush.
- Only collision geoms (contype | conaffinity != 0) define H. Visual
  meshes often extend further behind the palm (cables, mounting
  plate), but we only care that the contact volume sits flush with
  the flange.

Limitations.
- The auto-detected quat aligns the palm's out-axis with parent +Z but
  does NOT determine the rotation around that out-axis (palm-up vs
  palm-down vs thumb-left/right). This twist is convention-dependent
  per arm/hand pair; pass --twist {0,90,180,270} to add a rotation
  around site +Z. Eyeball in the viewer and adjust until the palm
  faces the right way.
- Multiple collision geoms with different -Z extents. When the root
  body has more than one collision geom (e.g. a thin mounting plate
  AND a larger gripper body that extends behind it for mesh-authoring
  reasons), the auto-pick uses the DEEPEST geom — guaranteeing no
  geom penetrates the arm. This can leave a visible gap at the actual
  mount face if the deeper geom is just a body whose mesh origin sits
  forward of the body origin. The output prints a per-geom H column;
  if the auto-pick gives a gap, pass `--h-override <H>` using the
  shallower geom's H. The deeper geom will then visually overlap the
  wrist link (typically hidden inside its mesh), but the actual mount
  face will sit flush. Example: PincOpen has both an `interface_arm100`
  plate (H=0.0066, the real mount face) and a `base` body (H=0.0159,
  geom origin offset by 16mm); use `--h-override 0.0066`.
- The eef-only mode (no --arm) outputs values in *site-aligned* frame
  with a warning. These are only correct when the arm's
  attachment_site has identity quat at the wrist body origin — for
  any non-trivial site quat, pass --arm.

Usage:
    ./.venv/bin/python compute_wrist_mount.py <eef.xml> --arm <arm.xml> [--twist DEG] [--site-name NAME] [--h-override H]
    ./.venv/bin/python compute_wrist_mount.py <eef.xml>     # site-aligned, with warning
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import mujoco
import numpy as np


SQRT2_2 = float(np.sqrt(2.0) / 2.0)

# Quat (w, x, y, z) that maps the body-local axis (key) to body +Z.
# Each is a single 0°/90°/180° rotation around a principal axis.
QUAT_FOR_OUT_AXIS = {
    ( 1,  0,  0): (SQRT2_2, 0.0, -SQRT2_2, 0.0),  # +X → +Z (rot Y by -90°)
    (-1,  0,  0): (SQRT2_2, 0.0,  SQRT2_2, 0.0),  # -X → +Z (rot Y by +90°)
    ( 0,  1,  0): (SQRT2_2,  SQRT2_2, 0.0, 0.0),  # +Y → +Z (rot X by +90°)
    ( 0, -1,  0): (SQRT2_2, -SQRT2_2, 0.0, 0.0),  # -Y → +Z (rot X by -90°)
    ( 0,  0,  1): (1.0, 0.0, 0.0, 0.0),           # +Z → +Z (identity)
    ( 0,  0, -1): (0.0, 1.0, 0.0, 0.0),           # -Z → +Z (rot X by 180°)
}


def _quat_to_mat(q) -> np.ndarray:
    w, x, y, z = float(q[0]), float(q[1]), float(q[2]), float(q[3])
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w),     2 * (x * z + y * w)],
        [2 * (x * y + z * w),     1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w),     2 * (y * z + x * w),     1 - 2 * (x * x + y * y)],
    ])


def _quat_mul(q1, q2) -> tuple:
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return (
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    )


def _twist_quat_z(degrees: float) -> tuple:
    half = float(np.deg2rad(degrees)) / 2.0
    return (float(np.cos(half)), 0.0, 0.0, float(np.sin(half)))


def _quat_for_out_axis(axis_vec: np.ndarray) -> tuple:
    key = tuple(int(round(c)) for c in axis_vec)
    return QUAT_FOR_OUT_AXIS[key]


_AABB_SIGNS = np.array(
    [[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)],
    dtype=float,
)


def _geom_corners_in_body_frame(model: mujoco.MjModel, geom_id: int) -> np.ndarray:
    """Return the 8 AABB corners of a geom expressed in its parent body frame."""
    aabb = np.asarray(model.geom_aabb)[geom_id]
    center, half = aabb[:3], aabb[3:]
    rot = _quat_to_mat(np.asarray(model.geom_quat)[geom_id])
    pts_geom = center + _AABB_SIGNS * half
    return (rot @ pts_geom.T).T + np.asarray(model.geom_pos)[geom_id]


def _detect_out_axis(model: mujoco.MjModel, root_id: int) -> dict:
    """Find the body-local axis along which descendants extend.

    Walks all descendants of the root body and computes their centroid
    in root-local frame. The dominant principal axis (largest absolute
    component) of that centroid is the direction fingers/payload extend.
    """
    parent = np.asarray(model.body_parentid)
    descendants = []
    for b in range(1, model.nbody):
        cur = b
        while cur != 0 and cur != root_id:
            cur = parent[cur]
        if cur == root_id and b != root_id:
            descendants.append(b)

    if not descendants:
        return {
            "axis_vec": np.array([0.0, 0.0, 1.0]),
            "axis_name": "+Z",
            "centroid_local": np.zeros(3),
            "n_descendants": 0,
            "ambiguous": False,
            "fallback_reason": "no descendants — defaulting to +Z (identity Q_align)",
        }

    data = mujoco.MjData(model)
    mujoco.mj_kinematics(model, data)
    root_pos = np.asarray(data.xpos)[root_id]
    root_mat = np.asarray(data.xmat)[root_id].reshape(3, 3)

    positions_world = np.asarray(data.xpos)[descendants]
    positions_local = (positions_world - root_pos) @ root_mat
    centroid = positions_local.mean(axis=0)

    abs_c = np.abs(centroid)
    axis_idx = int(abs_c.argmax())
    sorted_abs = np.sort(abs_c)[::-1]
    ambiguous = sorted_abs[0] > 0 and sorted_abs[1] / sorted_abs[0] > 0.7

    sign = 1 if centroid[axis_idx] >= 0 else -1
    axis_vec = np.zeros(3)
    axis_vec[axis_idx] = sign

    return {
        "axis_vec": axis_vec,
        "axis_name": f"{'+' if sign > 0 else '-'}{'XYZ'[axis_idx]}",
        "centroid_local": centroid,
        "n_descendants": len(descendants),
        "ambiguous": ambiguous,
        "fallback_reason": None,
    }


def _read_site(arm_xml: Path, site_name: str) -> tuple:
    """Return (site_pos_in_wrist_body, site_quat_in_wrist_body, wrist_body_name)."""
    arm_model = mujoco.MjModel.from_xml_path(str(arm_xml))
    sid = mujoco.mj_name2id(arm_model, mujoco.mjtObj.mjOBJ_SITE, site_name)
    if sid < 0:
        raise RuntimeError(
            f"site {site_name!r} not found in arm {arm_xml}. "
            "Pass --site-name if the arm uses a different name."
        )
    site_pos = np.asarray(arm_model.site_pos[sid]).copy()
    site_quat = tuple(float(c) for c in arm_model.site_quat[sid])
    wrist_bid = int(arm_model.site_bodyid[sid])
    wrist_name = arm_model.body(wrist_bid).name
    return site_pos, site_quat, wrist_name


def compute_wrist_mount(
    eef_xml: Path,
    arm_xml: Path | None = None,
    twist_deg: float = 0.0,
    site_name: str = "attachment_site",
    h_override: float | None = None,
) -> dict:
    if arm_xml is not None:
        site_pos, site_quat, wrist_name = _read_site(arm_xml, site_name)
    else:
        site_pos = np.zeros(3)
        site_quat = (1.0, 0.0, 0.0, 0.0)
        wrist_name = None

    eef_model = mujoco.MjModel.from_xml_path(str(eef_xml))
    parent = np.asarray(eef_model.body_parentid)
    roots = [b for b in range(1, eef_model.nbody) if parent[b] == 0]
    if len(roots) != 1:
        raise RuntimeError(
            f"expected one root body in {eef_xml}, got {len(roots)}: "
            f"{[eef_model.body(b).name for b in roots]}"
        )
    root = roots[0]
    root_name = eef_model.body(root).name

    axis_info = _detect_out_axis(eef_model, root)
    q_align = _quat_for_out_axis(axis_info["axis_vec"])
    q_twist = _twist_quat_z(twist_deg)

    # Q_palm_in_wrist = Q_site * Q_twist * Q_align
    q_palm = _quat_mul(site_quat, _quat_mul(q_twist, q_align))

    # H is in site frame. Transform palm geom corners by Q_twist * Q_align
    # to express them in site frame (post-alignment + twist), then take
    # the negative-Z extent.
    rot_align_twist = _quat_to_mat(_quat_mul(q_twist, q_align))

    geom_body = np.asarray(eef_model.geom_bodyid)
    contype = np.asarray(eef_model.geom_contype)
    conaff = np.asarray(eef_model.geom_conaffinity)

    collision_min_z, union_min_z = [], []
    geom_report = []
    geom_dataid = np.asarray(eef_model.geom_dataid)
    for g in range(eef_model.ngeom):
        if geom_body[g] != root:
            continue
        is_collision = bool(contype[g] | conaff[g])
        corners_body = _geom_corners_in_body_frame(eef_model, g)
        corners_site = corners_body @ rot_align_twist.T
        z_min = float(corners_site[:, 2].min())
        z_max = float(corners_site[:, 2].max())
        union_min_z.append(z_min)
        if is_collision:
            collision_min_z.append(z_min)
        mesh_name = None
        if geom_dataid[g] >= 0:
            try:
                mesh_name = eef_model.mesh(int(geom_dataid[g])).name
            except Exception:
                mesh_name = None
        geom_report.append({
            "id": g,
            "kind": "collision" if is_collision else "visual",
            "mesh": mesh_name,
            "z_min": z_min,
            "z_max": z_max,
            "h_for_this_geom": max(0.0, -z_min),
        })

    if not geom_report:
        raise RuntimeError(f"root body {root_name!r} has no geoms")

    h_collision = (
        max(0.0, -min(collision_min_z)) if collision_min_z else None
    )
    h_union = max(0.0, -min(union_min_z))
    h_auto = h_collision if h_collision is not None else h_union
    h_apply = h_override if h_override is not None else h_auto

    # Count distinct collision-geom H values to flag the multi-geom case.
    distinct_collision_h = sorted(
        {round(g["h_for_this_geom"], 4) for g in geom_report if g["kind"] == "collision"}
    )

    # Translation in wrist body frame.
    site_rot = _quat_to_mat(site_quat)
    pos_palm = site_pos + site_rot @ np.array([0.0, 0.0, h_apply])

    return {
        "root_body": root_name,
        "wrist_body": wrist_name,
        "site_pos": site_pos,
        "site_quat": site_quat,
        "axis": axis_info,
        "q_align": q_align,
        "q_twist": q_twist,
        "q_palm": q_palm,
        "pos_palm": pos_palm,
        "H_collision": h_collision,
        "H_union": h_union,
        "H_apply": h_apply,
        "h_override": h_override,
        "distinct_collision_h": distinct_collision_h,
        "geoms": geom_report,
        "twist_deg": twist_deg,
        "arm_provided": arm_xml is not None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("eef_xml", type=Path, help="end-effector MJCF")
    ap.add_argument(
        "--arm",
        type=Path,
        default=None,
        help="arm MJCF. REQUIRED for correct pos/quat in wrist body frame "
        "when the arm's attachment_site has a non-identity quat or pos. "
        "If omitted, output is in site-aligned frame with a warning.",
    )
    ap.add_argument(
        "--site-name",
        default="attachment_site",
        help="name of the mounting site on the arm (default: attachment_site)",
    )
    ap.add_argument(
        "--twist",
        type=float,
        default=0.0,
        help="extra rotation (degrees) around site +Z, applied on top of "
        "the auto-detected out-axis alignment. Use to dial in palm-up vs "
        "palm-down vs thumb-side. Try 0/90/180/270 and pick visually.",
    )
    ap.add_argument(
        "--h-override",
        type=float,
        default=None,
        help="override the auto-picked H (meters). Use when the root body "
        "has multiple collision geoms with different -Z extents (e.g. a "
        "thin mounting plate AND a larger gripper body that extends "
        "behind for modeling reasons) and the auto-pick (deepest geom = "
        "no penetration) leaves a visible gap at the actual mount face. "
        "Read the per-geom H column in the output and pick the one for "
        "the geom that's the real mounting interface.",
    )
    args = ap.parse_args()

    result = compute_wrist_mount(
        eef_xml=args.eef_xml.resolve(),
        arm_xml=args.arm.resolve() if args.arm else None,
        twist_deg=args.twist,
        site_name=args.site_name,
        h_override=args.h_override,
    )

    print(f"Eef root body: {result['root_body']!r}")
    if result["arm_provided"]:
        print(f"Arm wrist body: {result['wrist_body']!r}")
        print(
            f"Site {args.site_name!r}: pos={result['site_pos']}, "
            f"quat={result['site_quat']}"
        )
    else:
        print(
            "WARNING: no --arm given. Output is in site-aligned frame, "
            "ONLY correct when the site has identity quat at the wrist "
            "body origin. Pass --arm <arm.xml> for correct values."
        )

    axis = result["axis"]
    if axis["fallback_reason"]:
        print(f"\nOut-axis: {axis['axis_name']}  ({axis['fallback_reason']})")
    else:
        c = axis["centroid_local"]
        print(
            f"\nOut-axis: {axis['axis_name']}  "
            f"(centroid of {axis['n_descendants']} descendants in eef-root-local "
            f"frame: [{c[0]:+.4f}, {c[1]:+.4f}, {c[2]:+.4f}])"
        )
        if axis["ambiguous"]:
            print(
                "  WARNING: centroid is near-balanced across two axes — the "
                "detected out-axis may be wrong. Inspect visually and override."
            )

    print(f"\nGeoms on root body (in site frame, post-Q_twist*Q_align): "
          f"{len(result['geoms'])}")
    print(f"  {'idx':5s} {'kind':10s} {'mesh':22s} {'z range':24s} {'H':>8s}")
    for g in result["geoms"]:
        mesh_str = g["mesh"] or "-"
        print(
            f"  [{g['id']:>2d}]  {g['kind']:10s} {mesh_str[:22]:22s} "
            f"[{g['z_min']:+.4f}, {g['z_max']:+.4f}]   "
            f"{g['h_for_this_geom']:.4f}"
        )

    h_col = result["H_collision"]
    if h_col is None:
        print("\nNo collision geoms on root body — falling back to visual union.")
        print(f"H = {result['H_union']:.4f} m  (visual union)")
    else:
        print(f"\nH (collision-flush, recommended) = {h_col:.4f} m"
              f"  (deepest collision geom — no geom penetrates the arm)")
        print(f"H (visual + collision union)     = {result['H_union']:.4f} m")
        if abs(result["H_union"] - h_col) > 1e-3:
            print(
                "Note: visual mesh extends past the collision volume. The "
                "collision-flush value is correct for contact physics; the "
                "visual overhang behind the wrist is hardware-realistic "
                "(cables, mounting plate)."
            )
        if len(result["distinct_collision_h"]) > 1:
            print(
                "\nMULTI-GEOM NOTE: the root body has collision geoms with "
                "different -Z extents — see the per-geom H column above. "
                "The auto-pick uses the deepest geom (strict no-penetration). "
                "If the actual mounting interface is a SHALLOWER geom (e.g. "
                "a thin plate that bolts to the wrist while a larger body "
                "extends behind it for modeling reasons), pass `--h-override "
                "<value>` using that geom's H instead. The deeper geom will "
                "visually overlap the wrist link (hidden inside its mesh), "
                "but the mount face will sit flush."
            )

    if result["h_override"] is not None:
        print(
            f"\n--h-override {result['h_override']:.4f} applied (auto would "
            f"have used {h_col if h_col is not None else result['H_union']:.4f})."
        )

    p = result["pos_palm"]
    q = result["q_palm"]
    print(f"\nApply on the prefixed root body in the combined MJCF:")
    print(
        f'  pos="{p[0]:.6f} {p[1]:.6f} {p[2]:.6f}" '
        f'quat="{q[0]:.6f} {q[1]:.6f} {q[2]:.6f} {q[3]:.6f}"'
    )
    if args.twist == 0.0:
        print(
            "\nTwist around site +Z is 0°. If the palm visually mounts "
            "rotated (palm facing wrong way, fingers poking the arm), "
            "re-run with --twist 90 / 180 / 270."
        )
    else:
        print(f"\n(Includes --twist {args.twist}° around site +Z.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
