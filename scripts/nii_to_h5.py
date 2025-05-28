import os
import sys
import numpy as np
import argparse
import subprocess
import json
import nibabel as nib
import brainsss
import h5py
import datetime
import pyfiglet
import matplotlib.pyplot as plt
from time import time
from time import strftime
from time import sleep

def main(args):

    nii_path = args['nii_path']
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    printlog(f'Loading {nii_path}')
    nii_img = nib.load(nii_path)
    image_array = nii_img.get_fdata().astype('float32')

    h5_savefile = nii_path.split('.')[0] + '.h5'

    printlog(f'Saving to {h5_savefile}')
    with h5py.File(h5_savefile, 'w') as h5_file:
        h5_file.create_dataset('data', data=image_array, compression='gzip')

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))
