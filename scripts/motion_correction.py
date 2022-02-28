import os
import sys
import numpy as np
import argparse
import subprocess
import json
from time import time
from time import strftime
from time import sleep
import nibabel as nib
import brainsss.utils as brainsss
import h5py
import ants

def main(args):

	print(args)
	
	dataset_path = args['directory']
	ch1_input = args['brain_master']
	ch2_input = args['brain_mirror']
	try:
		logfile = args['logfile']
		printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')
	except:
		# no logfile provided; create one
		logfile = './logs/' + strftime("%Y%m%d-%H%M%S") + '.txt'
		printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')
		sys.stderr = brainsss.Logger_stderr_sherlock(logfile)

	printlog(F'dataset_path: {dataset_path}, brain_master: {ch1_input}, brain_mirror: {ch2_input}')
	sleep(3)
	return

	##############################
	### Check that files exist ###
	##############################
	filepath_ch1 = check_for_file(ch1_input, dataset_path)
	filepath_ch2 = check_for_file(ch2_input, dataset_path)
	# Abort if no channel 1
	if filepath_ch1 is None:
		printlog("Aborting moco - could not find {}".format(ch1_input))
		return
	else:
		printlog("Channel 1 is: {}".format(filepath_ch1))
	printlog("Channel 2 is: {}".format(filepath_ch2))


	########################################
	### Calculate Meanbrain of Channel 1 ###
	########################################
	# This will be fixed in moco

	### Get Brain Shape ###
	img_ch1 = nib.load(filepath_ch1) # this loads a proxy
	ch1_shape = img_ch1.header.get_data_shape()
	brain_dims = ch1_shape
	printlog("Channel 1 shape is {}".format(brain_dims))

	### Make meanbrain ###
	t0 = time()
	printlog('Creating temporal meanbrain...')
	meanbrain = np.zeros(brain_dims[:3]) # create empty meanbrain from the first 3 axes, x/y/z
	for i in range(brain_dims[-1]):
		if i%1000 == 0:
			printlog(brainsss.progress_bar(i, brain_dims[-1], 120))
		meanbrain += img_ch1.dataobj[...,i]
	meanbrain = meanbrain/brain_dims[-1] # divide by number of volumes
	fixed = ants.from_numpy(np.asarray(meanbrain, dtype='float32'))
	printlog('meanbrain DONE. Duration: {}'.format(time()-t0))

	### Load channel 2 proxy here ###
	if filepath_ch2 is not None:
		img_ch2 = nib.load(filepath_ch2) # this loads a proxy
		# make sure channel 1 and 2 have same shape
		ch2_shape = img_ch2.header.get_data_shape()
		if ch1_shape != ch2_shape:
			printlog("Channel 1 and 2 do not have the same shape! {} and {}".format(ch1_shape, ch2_shape))
			#printlog("Aborting.")
			#return

	############################################################
	### Make Empty MOCO files that will be filled vol by vol ###
	############################################################

	savefile_ch1 = make_empty_h5(dataset_path, f"{ch1_input.split('.')[0]}_moco.h5", brain_dims)
	printlog(f'created empty hdf5 file: {savefile_ch1}')

	if filepath_ch2 is not None:
		savefile_ch2 = make_empty_h5(dataset_path, f"{ch2_input.split('.')[0]}_moco.h5", brain_dims)
		printlog(f'created empty hdf5 file: {savefile_ch2}')

	#################################
	### Perform Motion Correction ###
	#################################
	printlog("Starting MOCO")
	
	### prepare chunks to loop over ###
	# the stepsize defines how many vols to moco before saving them to h5 (this save is slow, so we want to do it less often)
	stepsize = 100 # if this is too high if may crash from memory error. If too low it will be slow.
	steps = list(range(0,brain_dims[-1],stepsize))
	# add the last few volumes that are not divisible by stepsize
	if brain_dims[-1] > steps[-1]:
		steps.append(brain_dims[-1])

	# loop over all brain vols, motion correcting each and insert into hdf5 file on disk
	#for i in range(brain_dims[-1]):
	for j in range(len(steps)-1):
		printlog(F"j: {j}")

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
			if filepath_ch2 is not None: 
				vol = img_ch2.dataobj[...,index]
				ch2_moving = ants.from_numpy(np.asarray(vol, dtype='float32'))
				moco_ch2 = ants.apply_transforms(fixed, ch2_moving, transformlist)
				moco_ch2 = moco_ch2.numpy()
				moco_ch2_chunk.append(moco_ch2)
				printlog(F'moco vol done: {index}, time: {time()-t0}')

			### DELETE INVERSE TRANSFORMS ###
			transformlist = moco['invtransforms']
			for x in transformlist:
				if '.mat' not in x:
					os.remove(x)

			### DELETE FORWARD TRANSFORMS ###
			transformlist = moco['fwdtransforms']
			for x in transformlist:
				if '.mat' not in x:
					os.remove(x)

		
		moco_ch1_chunk = np.moveaxis(np.asarray(moco_ch1_chunk),0,-1)
		if filepath_ch2 is not None:
			moco_ch2_chunk = np.moveaxis(np.asarray(moco_ch2_chunk),0,-1)
		#printlog("chunk shape: {}. Time: {}".format(moco_ch1_chunk.shape, time()-t0))

		### APPEND WARPED VOL TO HD5F FILE - CHANNEL 1 ###
		t0 = time()
		with h5py.File(savefile_ch1, 'a') as f:
			f['data'][...,steps[j]:steps[j+1]] = moco_ch1_chunk																		
		printlog(F'Ch_1 append time: {time()-t0}')
																						
		### APPEND WARPED VOL TO HD5F FILE - CHANNEL 2 ###
		t0 = time()
		if filepath_ch2 is not None:
			with h5py.File(savefile_ch2, 'a') as f:
				#f['data'][...,i] = moco_ch2
				f['data'][...,steps[j]:steps[j+1]] = moco_ch2_chunk
			printlog(F'Ch_2 append time: {time()-t0}')

def make_empty_h5(directory, file, brain_dims):
	savefile = os.path.join(directory, file)
	with h5py.File(savefile, 'w') as f:
		dset = f.create_dataset('data', brain_dims, dtype='float32', chunks=True)
	return savefile

def check_for_file(file, directory):
	filepath = os.path.join(directory, file)
	if os.path.exists(filepath):
		return filepath
	else:
		return None

if __name__ == '__main__':
	print(sys.argv[1])
	main(json.loads(sys.argv[1]))
