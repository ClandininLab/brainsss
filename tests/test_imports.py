# check whether the necessary modules are installed
# any missing modules should be added to install_requires in setup.py

import sys


def test_imports():
    sys.path.append('../brainsss')
    import fictrac
    import utils
    import visual
