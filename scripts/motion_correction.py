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

	dataset_path = args['directory']
	brain_master = args['brain_master']

	# OPTIONAL brain_mirror
	brain_mirror = args.get('brain_mirror', None)

	# OPTIONAL PARAMETERS
	type_of_transform = args.get('type_of_transform', 'SyN')  # For ants.registration(), see ANTsPy docs | Default 'SyN'
	output_format = args.get('output_format', 'h5')  #  Save format for registered image data | Default h5. Also allowed: 'nii'
	assert output_format in ['h5', 'nii'], 'OPTIONAL PARAM output_format MUST BE ONE OF: "h5", "nii"'
	flow_sigma = int(args.get('flow_sigma', 3))  # For ants.registration(), higher sigma focuses on coarser features | Default 3
	total_sigma = int(args.get('total_sigma', 0))  # For ants.registration(), higher values will restrict the amount of deformation allowed | Default 0
	meanbrain_n_frames = args.get('meanbrain_n_frames', None)  # First n frames to average over when computing mean/fixed brain | Default None (average over all frames)

	#####################
	### SETUP LOGGING ###
	#####################

	width = 120

	try:
		logfile = args['logfile']
		printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')
		save_type = 'parent_dir'
	except:
		# no logfile provided; create one
		# this will be the case if this script was directly run from a .sh file
		logfile = './logs/' + strftime("%Y%m%d-%H%M%S") + '.txt'
		printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')
		sys.stderr = brainsss.Logger_stderr_sherlock(logfile)
		save_type = 'curr_dir'

		title = pyfiglet.figlet_format("Brainsss", font="cyberlarge" ) #28 #shimrod
		title_shifted = ('\n').join([' '*28+line for line in title.split('\n')][:-2])
		printlog(title_shifted)
		day_now = datetime.datetime.now().strftime("%B %d, %Y")
		time_now = datetime.datetime.now().strftime("%I:%M:%S %p")
		printlog(F"{day_now+' | '+time_now:^{width}}")
		printlog("")

	brainsss.print_datetime(logfile, width)
	printlog(F"Dataset path{dataset_path:.>{width-12}}")
	printlog(F"Brain master{brain_master:.>{width-12}}")
	printlog(F"Brain mirror{str(brain_mirror):.>{width-12}}")

	printlog(F"type_of_transform{type_of_transform:.>{width-17}}")
	printlog(F"output_format{output_format:.>{width-13}}")
	printlog(F"flow_sigma{flow_sigma:.>{width-10}}")
	printlog(F"total_sigma{total_sigma:.>{width-11}}")
	printlog(F"meanbrain_n_frames{str(meanbrain_n_frames):.>{width-18}}")

	######################
	### PARSE SCANTYPE ###
	######################

	try:
		scantype = args['scantype']
		if scantype == 'func':
			stepsize = 100 # if this is too high if may crash from memory error. If too low it will be slow.
		if scantype == 'anat':
			stepsize = 5
	except:
		# try to extract from file name
		if 'func' in brain_master:
			scantype = 'func'
			stepsize = 100
		elif 'anat' in brain_master:
			scantype = 'anat'
			stepsize = 5
		else:
			scantype = 'func'
			stepsize = 100
			printlog(F"{'   Could not determine scantype. Using default stepsize of 100   ':*^{width}}")
	printlog(F"Scantype{scantype:.>{width-8}}")
	printlog(F"Stepsize{stepsize:.>{width-8}}")

	##############################
	### Check that files exist ###
	##############################

	filepath_brain_master = os.path.join(dataset_path, brain_master)

	### Quit if no master brain
	if not brain_master.endswith('.nii'):
		printlog("Brain master does not end with .nii")
		printlog(F"{'   Aborting Moco   ':*^{width}}")
		return
	if not os.path.exists(filepath_brain_master):
		printlog("Could not find {}".format(filepath_brain_master))
		printlog(F"{'   Aborting Moco   ':*^{width}}")
		return

	### Brain mirror is optional
	if brain_mirror is not None:
		filepath_brain_mirror = os.path.join(dataset_path, brain_mirror)
		if not brain_mirror.endswith('.nii'):
			printlog("Brain mirror does not end with .nii. Continuing without a mirror brain.")
			# filepath_brain_mirror = None
			brain_mirror = None
		if not os.path.exists(filepath_brain_mirror):
			printlog(F"Could not find{filepath_brain_mirror:.>{width-8}}")
			printlog("Will continue without a mirror brain.")
			# filepath_brain_mirror = None
			brain_mirror = None

	########################################
	### Calculate Meanbrain of Channel 1 ###
	########################################

	### Get Brain Shape ###
	img_ch1 = nib.load(filepath_brain_master) # this loads a proxy
	ch1_shape = img_ch1.header.get_data_shape()
	brain_dims = ch1_shape
	printlog(F"Master brain shape{str(brain_dims):.>{width-18}}")

	### Try to load meanbrain
	existing_meanbrain_file = brain_master[:-4] + '_mean.nii'
	existing_meanbrain_path = os.path.join(dataset_path, existing_meanbrain_file)
	if os.path.exists(existing_meanbrain_path):
		meanbrain = np.asarray(nib.load(existing_meanbrain_path).get_data(), dtype='uint16')
		fixed = ants.from_numpy(np.asarray(meanbrain, dtype='float32'))
		printlog(F"Loaded meanbrain{existing_meanbrain_file:.>{width-16}}")

	### Create if can't load
	else:
		printlog(F"Could not find{existing_meanbrain_file:.>{width-14}}")
		printlog(F"Creating meanbrain{'':.>{width-18}}")

		### Make meanbrain ###
		t0 = time()
		if meanbrain_n_frames is None:
			meanbrain_n_frames = brain_dims[-1]  # All frames
		else:
			meanbrain_n_frames = int(meanbrain_n_frames)

		meanbrain = np.zeros(brain_dims[:3]) # create empty meanbrain from the first 3 axes, x/y/z
		for i in range(meanbrain_n_frames):
			if i%1000 == 0:
				printlog(brainsss.progress_bar(i, meanbrain_n_frames, width))
			meanbrain += img_ch1.dataobj[...,i]
		meanbrain = meanbrain/meanbrain_n_frames # divide by number of volumes
		fixed = ants.from_numpy(np.asarray(meanbrain, dtype='float32'))
		printlog(F"Meanbrain created. Duration{str(int(time()-t0))+'s':.>{width-27}}")

	#########################
	### Load Mirror Brain ###
	#########################

	if brain_mirror is not None:
		img_ch2 = nib.load(filepath_brain_mirror) # this loads a proxy
		# make sure channel 1 and 2 have same shape
		ch2_shape = img_ch2.header.get_data_shape()
		if ch1_shape != ch2_shape:
			printlog(F"{'   WARNING Channel 1 and 2 do not have the same shape!   ':*^{width}}")
			printlog("{} and {}".format(ch1_shape, ch2_shape))

	############################################################
	### Make Empty MOCO files that will be filled vol by vol ###
	############################################################

	h5_file_name = f"{brain_master.split('.')[0]}_moco.h5"
	moco_dir, savefile_master = make_empty_h5(dataset_path, h5_file_name, brain_dims, save_type)
	printlog(F"Created empty hdf5 file{h5_file_name:.>{width-23}}")

	if brain_mirror is not None:
		h5_file_name = f"{brain_mirror.split('.')[0]}_moco.h5"
		_ ,savefile_mirror = make_empty_h5(dataset_path, h5_file_name, brain_dims, save_type)
		printlog(F"Created empty hdf5 file{h5_file_name:.>{width-23}}")

	#################################
	### Perform Motion Correction ###
	#################################
	printlog(F"{'   STARTING MOCO   ':-^{width}}")
	transform_matrix = []

	### prepare chunks to loop over ###
	# the chunks defines how many vols to moco before saving them to h5 (this save is slow, so we want to do it less often)
	steps = list(range(0,brain_dims[-1],stepsize))
	# add the last few volumes that are not divisible by stepsize
	if brain_dims[-1] > steps[-1]:
		steps.append(brain_dims[-1])

	# loop over all brain vols, motion correcting each and insert into hdf5 file on disk
	#for i in range(brain_dims[-1]):
	start_time = time()
	print_timer = time()
	for j in range(len(steps)-1):
		#printlog(F"j: {j}")

		### LOAD A SINGLE BRAIN VOL ###
		moco_ch1_chunk = []
		moco_ch2_chunk = []
		for i in range(stepsize):
			t0 = time()
			index = steps[j] + i
			# for the very last j, adding the step size will go over the dim, so need to stop here
			if index == brain_dims[-1]:
				break

			vol = img_ch1.dataobj[...,index]
			moving = ants.from_numpy(np.asarray(vol, dtype='float32'))

			### MOTION CORRECT ###
			moco = ants.registration(fixed, moving,
									 type_of_transform=type_of_transform,
									 flow_sigma=flow_sigma,
                                	 total_sigma=total_sigma)
			moco_ch1 = moco['warpedmovout'].numpy()
			moco_ch1_chunk.append(moco_ch1)
			transformlist = moco['fwdtransforms']
			#printlog(F'vol, ch1 moco: {index}, time: {time()-t0}')

			### APPLY TRANSFORMS TO CHANNEL 2 ###
			#t0 = time()
			if brain_mirror is not None:
				vol = img_ch2.dataobj[...,index]
				ch2_moving = ants.from_numpy(np.asarray(vol, dtype='float32'))
				moco_ch2 = ants.apply_transforms(fixed, ch2_moving, transformlist)
				moco_ch2 = moco_ch2.numpy()
				moco_ch2_chunk.append(moco_ch2)
				#printlog(F'moco vol done: {index}, time: {time()-t0}')

			### SAVE AFFINE TRANSFORM PARAMETERS FOR PLOTTING MOTION ###
			transformlist = moco['fwdtransforms']
			for x in transformlist:
				if '.mat' in x:
					temp = ants.read_transform(x)
					transform_matrix.append(temp.parameters)

			### DELETE FORWARD TRANSFORMS ###
			transformlist = moco['fwdtransforms']
			for x in transformlist:
				if '.mat' not in x:
					os.remove(x)

			### DELETE INVERSE TRANSFORMS ###
			transformlist = moco['invtransforms']
			for x in transformlist:
				if '.mat' not in x:
					os.remove(x)

			### Print progress ###
			elapsed_time = time() - start_time
			if elapsed_time < 1*60: # if less than 1 min has elapsed
				print_frequency = 1 # print every sec if possible, but will be every vol
			elif elapsed_time < 5*60:
				print_frequency = 1*60
			elif elapsed_time < 30*60:
				print_frequency = 5*60
			else:
				print_frequency = 60*60
			if time() - print_timer > print_frequency:
				print_timer = time()
				print_progress_table(total_vol=brain_dims[-1], complete_vol=index, printlog=printlog, start_time=start_time, width=width)

		moco_ch1_chunk = np.moveaxis(np.asarray(moco_ch1_chunk),0,-1)
		if brain_mirror is not None:
			moco_ch2_chunk = np.moveaxis(np.asarray(moco_ch2_chunk),0,-1)
		#printlog("chunk shape: {}. Time: {}".format(moco_ch1_chunk.shape, time()-t0))

		### APPEND WARPED VOL TO HD5F FILE - CHANNEL 1 ###
		t0 = time()
		with h5py.File(savefile_master, 'a') as f:
			f['data'][...,steps[j]:steps[j+1]] = moco_ch1_chunk
		#printlog(F'Ch_1 append time: {time()-t0}')

		### APPEND WARPED VOL TO HD5F FILE - CHANNEL 2 ###
		t0 = time()
		if brain_mirror is not None:
			with h5py.File(savefile_mirror, 'a') as f:
				f['data'][...,steps[j]:steps[j+1]] = moco_ch2_chunk
			#printlog(F'Ch_2 append time: {time()-t0}')

	### SAVE TRANSFORMS ###
	printlog("saving transforms")
	printlog(F"savefile_master: {savefile_master}")
	transform_matrix = np.array(transform_matrix)
	save_file = os.path.join(moco_dir, 'motcorr_params')
	np.save(save_file,transform_matrix)

	### MAKE MOCO PLOT ###
	printlog("making moco plot")
	printlog(F"moco_dir: {moco_dir}")
	save_motion_figure(transform_matrix, dataset_path, moco_dir, scantype, printlog)

	### OPTIONAL: SAVE REGISTERED IMAGES AS NII ###
	if output_format == 'nii':
		printlog('saving .nii images')

		# Save master:
		nii_savefile_master = h5_to_nii(savefile_master)
		printlog(F"nii_savefile_master: {str(nii_savefile_master)}")
		if nii_savefile_master is not None: # If .nii conversion went OK, delete h5 file
			printlog('deleting .h5 file at {}'.format(savefile_master))
			os.remove(savefile_master)
		else:
			printlog('nii conversion failed for {}'.format(savefile_master))

		# Save mirror:
		if brain_mirror is not None:
			nii_savefile_mirror = h5_to_nii(savefile_mirror)
			printlog(F"nii_savefile_mirror: {str(nii_savefile_mirror)}")
			if nii_savefile_mirror is not None: # If .nii conversion went OK, delete h5 file
				printlog('deleting .h5 file at {}'.format(savefile_mirror))
				os.remove(savefile_mirror)
			else:
				printlog('nii conversion failed for {}'.format(savefile_mirror))


def make_empty_h5(directory, file, brain_dims, save_type):
	if save_type == 'curr_dir':
		moco_dir = os.path.join(directory,'moco')
		if not os.path.exists(moco_dir):
			os.mkdir(moco_dir)
	elif save_type == 'parent_dir':
		directory = os.path.dirname(directory) # go back one directory
		moco_dir = os.path.join(directory,'moco')
		if not os.path.exists(moco_dir):
			os.mkdir(moco_dir)

	savefile = os.path.join(moco_dir, file)
	with h5py.File(savefile, 'w') as f:
		dset = f.create_dataset('data', brain_dims, dtype='float32', chunks=True)
	return moco_dir, savefile

def check_for_file(file, directory):
	filepath = os.path.join(directory, file)
	if os.path.exists(filepath):
		return filepath
	else:
		return None

def save_motion_figure(transform_matrix, dataset_path, moco_dir, scantype, printlog):

	# Get voxel resolution for figure
	if scantype == 'func':
		xml_name = 'functional.xml'
	elif scantype == 'anat':
		xml_name = 'anatomy.xml'

	xml_file = os.path.join(dataset_path, xml_name)
	printlog(F'xml_file: {xml_file}')
	if not os.path.exists(xml_file):
		printlog('Could not find xml file for scan dimensions. Skipping plot.')
		return

	printlog(F'Found xml file.')
	x_res, y_res, z_res = brainsss.get_resolution(xml_file)

	# Save figure of motion over time
	save_file = os.path.join(moco_dir, 'motion_correction.png')
	plt.figure(figsize=(10,10))
	plt.plot(transform_matrix[:,9]*x_res, label = 'y') # note, resolutions are switched since axes are switched
	plt.plot(transform_matrix[:,10]*y_res, label = 'x')
	plt.plot(transform_matrix[:,11]*z_res, label = 'z')
	plt.ylabel('Motion Correction, um')
	plt.xlabel('Time')
	plt.title(moco_dir)
	plt.legend()
	plt.savefig(save_file, bbox_inches='tight', dpi=300)

def print_progress_table(total_vol, complete_vol, printlog, start_time, width):
	fraction_complete = complete_vol/total_vol

	### Get elapsed time ###
	elapsed = time()-start_time
	elapsed_hms = sec_to_hms(elapsed)

	### Get estimate of remaining time ###
	try:
		remaining = elapsed/fraction_complete - elapsed
	except ZeroDivisionError:
		remaining = 0
	remaining_hms = sec_to_hms(remaining)

	### Get progress bar ###
	complete_vol_str = f"{complete_vol:04d}"
	total_vol_str = f"{total_vol:04d}"
	length = len(elapsed_hms) + len(remaining_hms) + len(complete_vol_str) + len(total_vol_str)
	bar_string = brainsss.progress_bar(complete_vol, total_vol, width-length-10)

	full_line = '| ' + elapsed_hms + '/' + remaining_hms + ' | ' + complete_vol_str + '/' + total_vol_str + ' |' + bar_string + '|'
	printlog(full_line)

def sec_to_hms(t):
	secs=F"{np.floor(t%60):02.0f}"
	mins=F"{np.floor((t/60)%60):02.0f}"
	hrs=F"{np.floor((t/3600)%60):02.0f}"
	return ':'.join([hrs, mins, secs])


def h5_to_nii(h5_path):
	nii_savefile = h5_path.split('.')[0] + '.nii'
	with h5py.File(h5_path, 'r+') as h5_file:
		image_array = h5_file.get("data")[:].astype('uint16')

	nifti1_limit = (2**16 / 2)
	if np.any(np.array(image_array.shape) >= nifti1_limit):  # Need to save as nifti2
		nib.save(nib.Nifti2Image(image_array, np.eye(4)), nii_savefile)
	else:  # Nifti1 is OK
		nib.save(nib.Nifti1Image(image_array, np.eye(4)), nii_savefile)

	return nii_savefile

if __name__ == '__main__':
	main(json.loads(sys.argv[1]))
