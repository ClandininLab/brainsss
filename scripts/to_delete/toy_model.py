import os
import sys
import numpy as np
import argparse
import json
from time import time
import brainsss

def main(args):

    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    a = args['a']
    b = args['b']
    c = a + b

    printlog("{} plus {} is {}".format(a,b,c))

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))
