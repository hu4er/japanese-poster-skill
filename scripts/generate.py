#!/usr/bin/env python3
"""Convenience wrapper: resolves this skill's jp_poster.py and forwards all args.

Usage (identical to jp_poster.py):
    python3 generate.py --preset A --title "朝に起きる。" --out poster.png
    python3 generate.py --config spec.json --out poster.png
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "jp_poster.py")
sys.exit(subprocess.call([sys.executable, ENGINE] + sys.argv[1:]))
