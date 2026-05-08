#!/usr/bin/env python3
"""Compute the wrist-mount pos offset H for an end-effector MJCF.

Some end-effector MJCFs (notably mujoco_menagerie's wonik_allegro hands)
place the root body's *origin* at the front face of the palm — where the
fingers attach — with the rest of the palm geometry extending in
palm-local -Z. With identity quat at the wrist flange (the attach
script's default), this puts the back of the palm INSIDE the arm.

Fix: add `pos="0 0 H"` on the prefixed root body in the combined MJCF,
where H is the negative-Z extent of the root body's COLLISION geoms in
body-local frame.

This script computes H systematically. Convention: collision-flush.
- We consider only collision geoms (contype | conaffinity != 0). Visual
  meshes often extend further behind the palm (cables, mounting plate)
  and are not what defines the contact volume.
- For each collision geom, take its AABB (which MuJoCo fills for every
  primitive AND for meshes from vertex bounds), transform the 8 corners
  into body frame via geom_pos/geom_quat, take min_z.
- H = max(0, -min_z_over_all_collision_geoms).

H = 0 means the root origin already sits at the back of the palm — no
offset needed.

Usage:
    ./.venv/bin/python compute_wrist_offset.py <eef.xml>

Prints both the collision-only H (recommended) and the visual-union H
(reference, for sanity-check).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import mujoco
import numpy as np


def _quat_to_mat(q: np.ndarray) -> np.ndarray:
    w, x, y, z = float(q[0]), float(q[1]), float(q[2]), float(q[3])
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w),     2 * (x * z + y * w)],
        [2 * (x * y + z * w),     1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w),     2 * (y * z + x * w),     1 - 2 * (x * x + y * y)],
    ])


_AABB_SIGNS = np.array(
    [[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)],
    dtype=float,
)


def _geom_corners_in_body_frame(model: mujoco.MjModel, geom_id: int) -> np.ndarray:
    aabb = np.asarray(model.geom_aabb)[geom_id]
    center, half = aabb[:3], aabb[3:]
    rot = _quat_to_mat(np.asarray(model.geom_quat)[geom_id])
    pts_geom = center + _AABB_SIGNS * half
    return (rot @ pts_geom.T).T + np.asarray(model.geom_pos)[geom_id]


def compute_wrist_offset(eef_xml: Path) -> dict:
    model = mujoco.MjModel.from_xml_path(str(eef_xml))
    parent = np.asarray(model.body_parentid)
    roots = [b for b in range(1, model.nbody) if parent[b] == 0]
    if len(roots) != 1:
        raise RuntimeError(
            f"expected one root body under worldbody, got {len(roots)}: "
            f"{[model.body(b).name for b in roots]}"
        )
    root = roots[0]
    root_name = model.body(root).name

    geom_body = np.asarray(model.geom_bodyid)
    contype = np.asarray(model.geom_contype)
    conaff = np.asarray(model.geom_conaffinity)

    collision_min_z, union_min_z = [], []
    geom_report = []
    for g in range(model.ngeom):
        if geom_body[g] != root:
            continue
        is_collision = bool(contype[g] | conaff[g])
        corners = _geom_corners_in_body_frame(model, g)
        z_min = float(corners[:, 2].min())
        z_max = float(corners[:, 2].max())
        union_min_z.append(z_min)
        if is_collision:
            collision_min_z.append(z_min)
        geom_report.append({
            "id": g,
            "kind": "collision" if is_collision else "visual",
            "z_min": z_min,
            "z_max": z_max,
        })

    if not geom_report:
        raise RuntimeError(f"root body {root_name!r} has no geoms")

    h_collision = (
        max(0.0, -min(collision_min_z)) if collision_min_z else None
    )
    h_union = max(0.0, -min(union_min_z))

    return {
        "root_body": root_name,
        "geoms": geom_report,
        "H_collision": h_collision,
        "H_union": h_union,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("eef_xml", type=Path, help="end-effector MJCF")
    args = ap.parse_args()

    result = compute_wrist_offset(args.eef_xml.resolve())

    print(f"Root body: {result['root_body']!r}")
    print(f"Geoms on root body: {len(result['geoms'])}")
    for g in result["geoms"]:
        print(
            f"  geom[{g['id']}] {g['kind']:9s} "
            f"z=[{g['z_min']:+.4f}, {g['z_max']:+.4f}]"
        )

    h_col = result["H_collision"]
    if h_col is None:
        print("\nNo collision geoms on root body — falling back to visual union.")
        print(f"H = {result['H_union']:.4f} m  (visual union)")
    else:
        print(f"\nH (collision-flush, recommended) = {h_col:.4f} m")
        print(f"H (visual + collision union)     = {result['H_union']:.4f} m")
        if abs(result["H_union"] - h_col) > 1e-3:
            print(
                "Note: visual mesh extends past the collision volume. The "
                "collision-flush value is correct for contact physics; the "
                "visual overhang behind the wrist is hardware-realistic "
                "(cables, mounting plate)."
            )

    print(f"\nApply on the prefixed root body in the combined MJCF:")
    h_apply = h_col if h_col is not None else result["H_union"]
    print(f'  pos="0 0 {h_apply:.4f}" quat="1 0 0 0"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
