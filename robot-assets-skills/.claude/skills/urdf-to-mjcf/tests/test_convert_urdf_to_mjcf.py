from pathlib import Path
import importlib.util
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "convert_urdf_to_mjcf.py"
SPEC = importlib.util.spec_from_file_location("convert_urdf_to_mjcf", SCRIPT)
converter = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = converter
SPEC.loader.exec_module(converter)


class ConvertUrdfToMjcfPostprocessTest(unittest.TestCase):
    def test_postprocess_uses_explicit_level_one_dynamics(self):
        xml = """<mujoco>
  <worldbody>
    <body name="base">
      <freejoint/>
      <joint name="j1" range="-1 1"/>
      <geom type="sphere" size="0.01"/>
    </body>
  </worldbody>
  <actuator>
    <motor name="j1_motor" joint="j1"/>
  </actuator>
</mujoco>
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "robot.xml"
            path.write_text(xml)

            converter.postprocess_mjcf(
                path,
                fixed_base=True,
                add_joint_dynamics=True,
                joint_damping=0.6,
                joint_armature=0.028,
                joint_frictionloss=0.052,
                position_actuators=True,
                position_kp=17.8,
                position_force=3.35,
            )

            out = path.read_text()

        self.assertIn('<joint name="j1" range="-1 1" damping="0.6" armature="0.028" frictionloss="0.052"', out)
        self.assertIn('<position name="j1_motor" joint="j1" kp="17.8" ctrlrange="-1 1" forcerange="-3.35 3.35"', out)
        self.assertNotIn("<freejoint", out)

    def test_profile_resolution_reports_estimated_source(self):
        profile = converter.resolve_control_profile(
            "so101-sts3215",
            position_kp=None,
            position_force=None,
            joint_damping=None,
            joint_armature=None,
            joint_frictionloss=None,
        )

        self.assertEqual(profile.name, "so101-sts3215")
        self.assertEqual(profile.simulation_level, "level_1_controllable")
        self.assertEqual(profile.calibration_source, "template_estimate")
        self.assertEqual(profile.position_force, 3.35)
        self.assertEqual(profile.joint_armature, 0.028)


if __name__ == "__main__":
    unittest.main()
