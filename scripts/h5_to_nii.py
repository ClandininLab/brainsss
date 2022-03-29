import os
import sys
import numpy as np
import argparse
import subprocess
import json
import nibabel as nib
import brainsss
import h5py
import ants
import datetime
import pyfiglet
import matplotlib.pyplot as plt
from time import time
from time import strftime
from time import sleep

def main(args):

	h5_path = args['h5_path']
	logfile = args['logfile']
	printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

	printlog('loading {}'.format(h5_path))

	nii_savefile = h5_path.split('.')[0] + '.nii'
	with h5py.File(h5_path, 'r+') as h5_file:
		image_array = h5_file.get("data")[:].astype('float32')

	pringlog('saving')
	nib.Nifti1Image(image_array, np.eye(4)).to_filename(nii_savefile)

if __name__ == '__main__':
	main(json.loads(sys.argv[1]))