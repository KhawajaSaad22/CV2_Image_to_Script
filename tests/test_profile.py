import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np
import engine


class ProfileTests(unittest.TestCase):
    def test_profile_reports_sampled_memory_and_timings(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); image=root/'image.png'; recipe=root/'recipe.json'; output=root/'profile.json'
            engine.write_image(image,np.zeros((32,32,3),np.uint8))
            # Use the public loader's accepted empty recipe schema.
            recipe.write_text(json.dumps({'version':1,'steps':[]}))
            result=subprocess.run([sys.executable,'tools/profile_pipeline.py',str(image),str(recipe),
                '--runs','2','--output',str(output)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            report=json.loads(output.read_text())
            self.assertGreater(report['rss_baseline_bytes'],0)
            self.assertGreaterEqual(report['rss_sampled_peak_bytes'],report['rss_baseline_bytes'])
            self.assertGreaterEqual(report['median_ms'],0)
