# `urdf-to-mjcf` Gotchas

The five post-tune fix categories that turn a raw conversion into a
usable MJCF. Read this before declaring a conversion "done".

A raw output that *compiles* and *opens in the viewer* can still be
unusable if any of these are wrong (fingers won't move, joints fly
off, dynamics blow up at first contact).

---

## 1. Mimic joints are silently dropped

**Symptom.** The standalone viewer shows the right number of sliders
*on the URDF side* (with mimic joints folded in), but the converted
MJCF shows one slider per *raw* joint — including the mimic'd ones.
Driving the "primary" joint doesn't move the "mimic" joint.

**Cause.** MuJoCo's URDF loader has no way to express URDF
`<mimic>` semantics in pure MJCF — there's no `mimic` element. The
loader silently drops the relationship; both joints become independent
hinges.

**Concrete example we hit.** Barrett: 8 joints in the URDF (4 mimic
relationships), 4 actuators in the original SDK. The raw converted
MJCF had 8 free joints and zero coupling — finger phalanges flopped
independently of their proximals.

**Fix.** Add `<equality><joint .../>` blocks for each mimic
relationship:

```xml
<equality>
  <joint joint1="<mimic-joint>" joint2="<primary-joint>"
         polycoef="0 <multiplier> 0 0 0"/>
</equality>
```

The `polycoef` is `c0 c1 c2 c3 c4` for `joint1 = c0 + c1*joint2 + c2*joint2^2 + ...`.
For a simple URDF mimic (`joint = multiplier * primary + offset`), use
`polycoef="<offset> <multiplier> 0 0 0"`.

**Concrete example for barrett:**

```xml
<equality>
  <joint joint1="bh_j33_joint" joint2="bh_j32_joint" polycoef="0 0.344262295082 0 0 0"/>
  <joint joint1="bh_j13_joint" joint2="bh_j12_joint" polycoef="0 0.344262295082 0 0 0"/>
  <joint joint1="bh_j21_joint" joint2="bh_j11_joint" polycoef="0 1 0 0 0"/>
  <joint joint1="bh_j23_joint" joint2="bh_j22_joint" polycoef="0 0.344262295082 0 0 0"/>
</equality>
```

**Detection.** Diff the joint count vs. actuator count of the *original*
URDF (joints minus mimics) — that's how many actuators the converted
MJCF should have after you also add actuators (gotcha §3). If
joint-count > actuator-count, you have unhandled mimics.

---

## 2. Inertias are often 100x oversized

**Symptom.** Joints don't respond to commanded actuator targets even
with very high `kp`; or, the simulation is sluggish; or, contact
forces are unrealistic.

**Cause.** Many URDFs (especially xacro-generated ones) ship
placeholder inertia values that are much larger than physically
correct. URDF doesn't enforce physical plausibility; MuJoCo does the
math literally. A 100x inertia means `kp` needs to be 100x higher to
get the same response.

**Detection.** For each link, compare:

```python
import mujoco
m = mujoco.MjModel.from_xml_path('robots/<robot>/<robot>.xml')
for i in range(m.nbody):
    body = m.body(i)
    print(body.name, 'mass=', body.mass[0], 'diaginertia=', body.inertia)
```

Sanity rules of thumb for finger-sized links:
- mass: 0.01–0.05 kg per phalanx, ~0.5 kg for palm
- diaginertia: 1e-6 to 5e-5 for phalanges, ~1e-3 for palm

Anything 100x outside these ranges is suspect.

**Fix.** Override the link's inertial block in the converted MJCF:

```xml
<body name="..." pos="..." quat="...">
  <inertial pos="0 0 0" mass="0.05" diaginertia="2e-5 2e-5 2e-5"/>
  ...
</body>
```

For dexterous hands specifically, the menagerie barrett/allegro
inertias are good reference values to copy from.

---

## 3. No actuators — joints exist but nothing drives them

**Symptom.** Viewer shows joint sliders but they don't actually drive
any motion (only adjust `qpos` directly, which gets corrected each
step).

**Cause.** MuJoCo's URDF loader doesn't generate `<actuator>` blocks.
URDF has no concept of an actuator/motor as a first-class element.

**Fix.** Add a `<position>` (or `<motor>` / `<velocity>`) actuator per
controlled joint:

```xml
<default class="<robot>">
  <position ctrlrange="<min> <max>" forcerange="-10 10" kp="10" kv="0.5"/>
</default>

...

<actuator>
  <position class="<robot>" name="<actuator-name>" joint="<joint-name>"
            ctrlrange="<joint min> <joint max>"/>
  ...
</actuator>
```

For underactuated hands (joints coupled via `<equality>` from gotcha §1):
add actuators only for the **primary** joints, not the mimic'd ones.
Barrett has 4 actuators driving 8 joints; allegro has 16
(no mimics).

`kp` and `kv` are starting points — tune in the viewer until the joint
tracks the commanded angle smoothly without oscillation.

---

## 4. No contact excludes — palm-knuckle pairs block motion

**Symptom.** The actuator sees the commanded target but the joint
sticks at some lower value (e.g. spread joint stuck at 1.74 rad
instead of 3.14). High actuator force fails to overcome it. Looks
mechanical, not numerical.

**Cause.** Adjacent links that touch in the rest pose are being treated
as active contacts. Increasing actuator force pushes harder on the
contact. Common culprit: palm and the proximal link of a finger
(`bh_j11` spread getting blocked by palm/finger collision).

**Fix.** Add `<contact><exclude>` for palm↔first-link pairs (and any
others adjacent in rest pose):

```xml
<contact>
  <exclude body1="<palm-body>" body2="<finger-1-link>"/>
  <exclude body1="<palm-body>" body2="<finger-2-link>"/>
  <exclude body1="<palm-body>" body2="<thumb-1-link>"/>
</contact>
```

**Detection.** With the actuator targeted at its joint limit, set a
breakpoint and inspect `data.contact[i]` for any contact pair between
palm and first-link bodies. If found, exclude.

---

## 5. Compiler / option defaults that matter

The converter doesn't set these but they're load-bearing for stable
dexterous-hand sim:

```xml
<compiler angle="radian" autolimits="true" .../>
<option integrator="implicitfast"/>
```

- `autolimits="true"` — joint range checking from the joint definition
  (otherwise you can drive past the limit).
- `implicitfast` integrator — much more stable than the default for
  stiff actuator gains (kp=10+) typical in dex hands.

Add these to the converted MJCF's `<compiler>` and `<option>` elements.

