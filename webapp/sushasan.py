#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import importlib.util
import os


# Load the real module from the repository root when this file is checked out
# on platforms that do not preserve the original symlink.
ROOT_MODULE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sushasan.py')
SPEC = importlib.util.spec_from_file_location('_sushasan_root', ROOT_MODULE)

if SPEC is None or SPEC.loader is None:
	raise ImportError('Unable to load sushasan module from repository root')

MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

for name in dir(MODULE):
	if not name.startswith('_'):
		globals()[name] = getattr(MODULE, name)

__all__ = [name for name in globals() if not name.startswith('_')]