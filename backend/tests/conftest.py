import os
import sys

# Make backend modules (app, pipeline, ...) importable regardless of the cwd
# pytest is launched from.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
