import os
import sys
import numpy as np
import argparse
import subprocess
import json
from time import time
import nibabel as nib
import brainsss.utils as brainsss
import h5py
import ants

def main(args):

	logfile = args['logfile']
	dataset_path = args['dataset_path'] # full fly path 
	printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')
	
	directory = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20220222_ashley_test"
	ch1_input = "ch1_stitched.nii"
	ch2_input = "ch2_stitched.nii"

	##############################
	### Check that files exist ###
	##############################
	filepath_ch1 = check_for_file(ch1_input, directory)
	filepath_ch2 = check_for_file(ch2_input, directory)
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
	savefile_ch1 = os.path.join(directory, "moco_ch1.h5")
	with h5py.File(savefile_ch1, 'w') as f:
		dset_ch1 = f.create_dataset('data', brain_dims, dtype='float32', chunks=True)
		printlog('created empty hdf5 file: {}'.format(savefile_ch1))

	if filepath_ch2 is not None:
		savefile_ch2 = os.path.join(directory, "moco_ch2.h5") 
		with h5py.File(savefile_ch2, 'w') as f:
			dset_ch2 = f.create_dataset('data', brain_dims, dtype='float32', chunks=True)
		printlog('created empty hdf5 file: {}'.format(savefile_ch2))

	#################################
	### Perform Motion Correction ###
	#################################
	printlog("Starting MOCO")
	# loop over all brain vols, motion correcting each and insert into hdf5 file on disk
	for i in range(brain_dims[-1]):
		t0 = time()

		### LOAD A SINGLE BRAIN VOL ###
		vol = img_ch1.dataobj[...,i]
		moving = ants.from_numpy(np.asarray(vol, dtype='float32'))

		### MOTION CORRECT ###
		moco = ants.registration(fixed, moving, type_of_transform='SyN')
		moco_ch1 = moco['warpedmovout'].numpy()
		transformlist = moco['fwdtransforms']
		printlog(F'vol, ch1 moco: {i}, time: {time()-t0}')
		
		### APPLY TRANSFORMS TO CHANNEL 2 ###
		if filepath_ch2 is not None: 
			vol = img_ch2.dataobj[...,i]
			ch2_moving = ants.from_numpy(np.asarray(vol, dtype='float32'))
			moco_ch2 = ants.apply_transforms(fixed, ch2_moving, transformlist)
			moco_ch2 = moco_ch2.numpy()
			printlog(F'vol, ch2 moco: {i}, time: {time()-t0}')

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

		printlog('here')
		### APPEND WARPED VOL TO HD5F FILE - CHANNEL 1 ###
		with h5py.File(savefile_ch1, 'a') as f:
			f['data'][...,i] = moco_ch1																		
		printlog(F'vol, ch1 append: {i}, time: {time()-t0}')
																						
		### APPEND WARPED VOL TO HD5F FILE - CHANNEL 2 ###
		if filepath_ch2 is not None:
			with h5py.File(savefile_ch2, 'a') as f:
				f['data'][...,i] = moco_ch2
			printlog(F'vol, ch2 append: {i}, time: {time()-t0}')

def check_for_file(file, directory):
	filepath = os.path.join(directory, file)
	if os.path.exists(filepath):
		return filepath
	else:
		return None

if __name__ == '__main__':
	main(json.loads(sys.argv[1]))
