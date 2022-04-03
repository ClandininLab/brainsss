# check whether the necessary modules are installed
# any missing modules should be added to install_requires in setup.py
# this must be run from the root directory of the project or the tests directory

import sys
import os

def test_imports():
    if os.path.exists('brainsss'):
        sys.path.append('brainsss')
    elif os.path.exists('../brainsss'):
        sys.path.append('../brainsss')
    else:
        raise Exception('brainsss directory not found')
    import fictrac
    import utils
    import visual
