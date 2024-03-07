import numpy as np
import os
import sys
import psutil
import nibabel as nib
from time import time
from time import sleep
import json
import dataflow as flow
import matplotlib.pyplot as plt
from contextlib import contextmanager
import warnings
warnings.filterwarnings("ignore")

from shutil import copyfile

import platform
if platform.system() != 'Windows':
	sys.path.insert(0, '/home/users/brezovec/.local/lib/python3.6/site-packages/lib/python/')
	import ants

def main(args):

	logfile = args['logfile']
	width = 120
	printlog = getattr(flow.Printlog(logfile=logfile), 'print_to_log')

	dataset_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20190101_walking_dataset"
	flies = ['fly_087', 'fly_089', 'fly_094', 'fly_095', 'fly_097', 'fly_098', 'fly_099', 'fly_100', 'fly_101', 'fly_105']

	### Load Luke Mean ###
	luke_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/anat_templates/20210310_luke_exp_thresh.nii"
	res_luke_mean = (0.65,0.65,1)
	luke_mean = np.asarray(nib.load(luke_path).get_data().squeeze(), dtype='float32')
	luke_mean = luke_mean[:,:,::-1] #flipz
	luke_mean = ants.from_numpy(luke_mean)
	luke_mean.set_spacing(res_luke_mean)
	luke_mean_lowres =  ants.resample_image(luke_mean,(256,128,49),use_voxels=True)

	### Load JFRC2018 ###
	fixed_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/anat_templates/JRC2018_FEMALE_38um_iso_16bit.nii"
	res_JRC2018 = (0.38, 0.38, 0.38)
	fixed = np.asarray(nib.load(fixed_path).get_data().squeeze(), dtype='float32')
	fixed = ants.from_numpy(fixed)
	fixed.set_spacing(res_JRC2018)
	fixed_lowres = ants.resample_image(fixed,(2,2,2),use_voxels=False)
	#fixed_lowres = ants.resample_image(fixed,(2.6,2.6,5),use_voxels=False)

	out = ants.registration(fixed_lowres, luke_mean_lowres, type_of_transform='Affine')
	
	for fly in flies:

		#reset memory
		warped = None
		moving = None
		sleep(30)

		printlog(fly)
		### Load neural data ###
		# this has already been warped from individual brains into the local meanbrain.
		file = os.path.join(dataset_path, fly, 'func_0', 'brain_zscored_green_high_pass_masked_warped.nii')
		moving = ants.from_numpy(ants.image_read(file)[:,:,::-1,:])
		moving.set_spacing((2.6076, 2.6154, 5.3125, 1)) ### matching this to the slightly off luke mean

		warped = ants.apply_transforms(fixed_lowres, moving, out['fwdtransforms'][0], imagetype=3, interpolator='nearestNeighbor')

		save_file = os.path.join(dataset_path, fly, 'func_0', 'brain_zscored_green_high_pass_masked_warped_to_FDA.nii')
		nib.Nifti1Image(warped.numpy(), np.eye(4)).to_filename(save_file)

def sec_to_hms(t):
		secs=F"{np.floor(t%60):02.0f}"
		mins=F"{np.floor((t/60)%60):02.0f}"
		hrs=F"{np.floor((t/3600)%60):02.0f}"
		return ':'.join([hrs, mins, secs])

@contextmanager
def stderr_redirected(to=os.devnull):

	fd = sys.stderr.fileno()

	def _redirect_stderr(to):
		sys.stderr.close() # + implicit flush()
		os.dup2(to.fileno(), fd) # fd writes to 'to' file
		sys.stderr = os.fdopen(fd, 'w') # Python writes to fd

	with os.fdopen(os.dup(fd), 'w') as old_stderr:
		with open(to, 'w') as file:
			_redirect_stderr(to=file)
		try:
			yield # allow code to be run with the redirected stdout
		finally:
			_redirect_stderr(to=old_stderr) # restore stdout.
											# buffering and flags such as
											# CLOEXEC may be different

if __name__ == '__main__':
	main(json.loads(sys.argv[1]))