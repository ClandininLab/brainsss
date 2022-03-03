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
import matplotlib.pyplot as plt
from time import time
from time import strftime
from time import sleep

def main(args):
	
	dataset_path = args['directory']
	brain_master = args['brain_master']
	brain_mirror = args['brain_mirror']

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
	printlog(F"Dataset path{dataset_path:.>{width-12}}")
	printlog(F"Brain master{brain_master:.>{width-12}}")
	printlog(F"Brain mirror{brain_mirror:.>{width-12}}")

	######################
	### PARSE SCANTYPE ###
	######################

	try:
		scantype = args['scantype']
		if scantype == 'func':
			stepsize = 100 # if this is too high if may crash from memory error. If too low it will be slow.
		if scantype == 'anat':
			stepsize = 10
	except:
		# try to extract from file name
		if 'func' in brain_master:
			scantype = 'func'
			stepsize = 100 
		if 'anat' in brain_master:
			scantype = 'anat'
			stepsize = 10
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
	filepath_brain_mirror = os.path.join(dataset_path, brain_mirror)

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
	if not brain_mirror.endswith('.nii'):
		printlog("Brain mirror does not end with .nii. Continuing without a mirror brain.")
		filepath_brain_mirror = None
	if not os.path.exists(filepath_brain_mirror):
		printlog(F"Could not find{filepath_brain_mirror:.>{width-8}}")
		printlog("Will continue without a mirror brain.")
		filepath_brain_mirror = None

	########################################
	### Calculate Meanbrain of Channel 1 ###
	########################################

	### Get Brain Shape ###
	img_ch1 = nib.load(filepath_brain_master) # this loads a proxy
	ch1_shape = img_ch1.header.get_data_shape()
	brain_dims = ch1_shape
	printlog(F"Master brain shape{str(brain_dims):.>{width-15}}")


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
		meanbrain = np.zeros(brain_dims[:3]) # create empty meanbrain from the first 3 axes, x/y/z
		for i in range(brain_dims[-1]):
			if i%1000 == 0:
				printlog(brainsss.progress_bar(i, brain_dims[-1], width))
			meanbrain += img_ch1.dataobj[...,i]
		meanbrain = meanbrain/brain_dims[-1] # divide by number of volumes
		fixed = ants.from_numpy(np.asarray(meanbrain, dtype='float32'))
		printlog(F"Meanbrain created. Duration{str(int(time()-t0))+'s':.>{width-27}}")

	#########################
	### Load Mirror Brain ###
	#########################

	if filepath_brain_mirror is not None:
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

	if filepath_brain_mirror is not None:
		h5_file_name = f"{brain_mirror.split('.')[0]}_moco.h5"
		_ ,savefile_mirror = make_empty_h5(dataset_path, h5_file_name, brain_dims, save_type)
		printlog(F"Created empty hdf5 file{h5_file_name:.>{width-23}}")

	#################################
	### Perform Motion Correction ###
	#################################
	printlog(F"{'   STARTING MOCO   ':~^{width}}")
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
			moco = ants.registration(fixed, moving, type_of_transform='SyN')
			moco_ch1 = moco['warpedmovout'].numpy()
			moco_ch1_chunk.append(moco_ch1)
			transformlist = moco['fwdtransforms']
			#printlog(F'vol, ch1 moco: {index}, time: {time()-t0}')
			
			### APPLY TRANSFORMS TO CHANNEL 2 ###
			#t0 = time()
			if filepath_brain_mirror is not None: 
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

		moco_ch1_chunk = np.moveaxis(np.asarray(moco_ch1_chunk),0,-1)
		if filepath_brain_mirror is not None:
			moco_ch2_chunk = np.moveaxis(np.asarray(moco_ch2_chunk),0,-1)
		#printlog("chunk shape: {}. Time: {}".format(moco_ch1_chunk.shape, time()-t0))

		### APPEND WARPED VOL TO HD5F FILE - CHANNEL 1 ###
		t0 = time()
		with h5py.File(savefile_master, 'a') as f:
			f['data'][...,steps[j]:steps[j+1]] = moco_ch1_chunk																		
		#printlog(F'Ch_1 append time: {time()-t0}')
																						
		### APPEND WARPED VOL TO HD5F FILE - CHANNEL 2 ###
		t0 = time()
		if filepath_brain_mirror is not None:
			with h5py.File(savefile_mirror, 'a') as f:
				#f['data'][...,i] = moco_ch2
				f['data'][...,steps[j]:steps[j+1]] = moco_ch2_chunk
			#printlog(F'Ch_2 append time: {time()-t0}')

		### Print progress ###
		print_progress_table(total_vol=brain_dims[-1], complete_vol=index, printlog=printlog, start_time=start_time, width=width)

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
	#printlog("Could not make moco plot, probably can't find xml file to grab image resolution.")

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

if __name__ == '__main__':
	main(json.loads(sys.argv[1]))
