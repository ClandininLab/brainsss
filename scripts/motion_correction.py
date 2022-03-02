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

	try:
		logfile = args['logfile']
		printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')
		save_type = 'back_one_dir'
	except:
		# no logfile provided; create one
		logfile = './logs/' + strftime("%Y%m%d-%H%M%S") + '.txt'
		printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')
		sys.stderr = brainsss.Logger_stderr_sherlock(logfile)
		save_type = 'curr_dir'
	printlog(f'save_type: {save_type}')

	try:
		scantype = args['scantype']
		if scantype == 'func':
			stepsize = 100 # if this is too high if may crash from memory error. If too low it will be slow.
		if scantype == 'anat':
			stepsize = 10
		printlog(F'Scantype is {scantype}. Stepsize is {stepsize}')
	except:
		scantype = 'func'
		stepsize = 100 
		printlog('scantype not specified. Using default chunksize of 100')

	printlog(F'\nArguments:\ndataset_path: {dataset_path}\nbrain_master: {brain_master}\nbrain_mirror: {brain_mirror}\n')

	# ##############################
	# ### Check that files exist ###
	# ##############################
	# filepath_ch1 = check_for_file(brain_master, dataset_path)
	# filepath_ch2 = check_for_file(brain_mirror, dataset_path)
	# # Abort if no channel 1
	# if filepath_ch1 is None:
	# 	printlog("Aborting moco - could not find {}".format(brain_master))
	# 	return
	# else:
	# 	printlog("Channel 1 is: {}".format(filepath_ch1))
	# printlog("Channel 2 is: {}".format(filepath_ch2))

	# ########################################
	# ### Calculate Meanbrain of Channel 1 ###
	# ########################################

	# ### Get Brain Shape ###
	# img_ch1 = nib.load(filepath_ch1) # this loads a proxy
	# ch1_shape = img_ch1.header.get_data_shape()
	# brain_dims = ch1_shape
	# printlog("Channel 1 shape is {}".format(brain_dims))

	# ### Try to load meanbrain
	# existing_meanbrain = filepath_ch1[:-4] + '_mean.nii'
	# printlog(F'Looking for meanbrain {existing_meanbrain}')
	# if os.path.exists(existing_meanbrain):
	# 	meanbrain = np.asarray(nib.load(existing_meanbrain).get_data(), dtype='uint16')
	# 	fixed = ants.from_numpy(np.asarray(meanbrain, dtype='float32'))
	# 	printlog('Found and loaded.')

	# ### Create if can't load
	# else:
	# 	printlog('No existing meanbrain found; Creating...')

	# 	### Make meanbrain ###
	# 	t0 = time()
	# 	meanbrain = np.zeros(brain_dims[:3]) # create empty meanbrain from the first 3 axes, x/y/z
	# 	for i in range(brain_dims[-1]):
	# 		if i%1000 == 0:
	# 			printlog(brainsss.progress_bar(i, brain_dims[-1], 120))
	# 		meanbrain += img_ch1.dataobj[...,i]
	# 	meanbrain = meanbrain/brain_dims[-1] # divide by number of volumes
	# 	fixed = ants.from_numpy(np.asarray(meanbrain, dtype='float32'))
	# 	printlog('meanbrain DONE. Duration: {}'.format(time()-t0))

	# ### Load channel 2 proxy here ###
	# if filepath_ch2 is not None:
	# 	img_ch2 = nib.load(filepath_ch2) # this loads a proxy
	# 	# make sure channel 1 and 2 have same shape
	# 	ch2_shape = img_ch2.header.get_data_shape()
	# 	if ch1_shape != ch2_shape:
	# 		printlog("Channel 1 and 2 do not have the same shape! {} and {}".format(ch1_shape, ch2_shape))
	# 		#printlog("Aborting.")
	# 		#return

	# ############################################################
	# ### Make Empty MOCO files that will be filled vol by vol ###
	# ############################################################

	# savefile_master = make_empty_h5(dataset_path, f"{brain_master.split('.')[0]}_moco.h5", brain_dims, save_type)
	# printlog(f'created empty hdf5 file: {savefile_master}')

	# if filepath_ch2 is not None:
	# 	savefile_mirror = make_empty_h5(dataset_path, f"{brain_mirror.split('.')[0]}_moco.h5", brain_dims, save_type)
	# 	printlog(f'created empty hdf5 file: {savefile_mirror}')

	# #################################
	# ### Perform Motion Correction ###
	# #################################
	# printlog("Starting MOCO")
	# transform_matrix = []
	
	# ### prepare chunks to loop over ###
	# # the chunks defines how many vols to moco before saving them to h5 (this save is slow, so we want to do it less often)
	# steps = list(range(0,brain_dims[-1],stepsize))
	# # add the last few volumes that are not divisible by stepsize
	# if brain_dims[-1] > steps[-1]:
	# 	steps.append(brain_dims[-1])

	# # loop over all brain vols, motion correcting each and insert into hdf5 file on disk
	# #for i in range(brain_dims[-1]):
	# for j in range(len(steps)-1):
	# 	printlog(F"j: {j}")

	# 	### LOAD A SINGLE BRAIN VOL ###
	# 	moco_ch1_chunk = []
	# 	moco_ch2_chunk = []
	# 	for i in range(stepsize):
	# 		t0 = time()
	# 		index = steps[j] + i
	# 		# for the very last j, adding the step size will go over the dim, so need to stop here
	# 		if index == brain_dims[-1]:
	# 			break

	# 		vol = img_ch1.dataobj[...,index]
	# 		moving = ants.from_numpy(np.asarray(vol, dtype='float32'))

	# 		### MOTION CORRECT ###
	# 		moco = ants.registration(fixed, moving, type_of_transform='SyN')
	# 		moco_ch1 = moco['warpedmovout'].numpy()
	# 		moco_ch1_chunk.append(moco_ch1)
	# 		transformlist = moco['fwdtransforms']
	# 		#printlog(F'vol, ch1 moco: {index}, time: {time()-t0}')
			
	# 		### APPLY TRANSFORMS TO CHANNEL 2 ###
	# 		#t0 = time()
	# 		if filepath_ch2 is not None: 
	# 			vol = img_ch2.dataobj[...,index]
	# 			ch2_moving = ants.from_numpy(np.asarray(vol, dtype='float32'))
	# 			moco_ch2 = ants.apply_transforms(fixed, ch2_moving, transformlist)
	# 			moco_ch2 = moco_ch2.numpy()
	# 			moco_ch2_chunk.append(moco_ch2)
	# 			printlog(F'moco vol done: {index}, time: {time()-t0}')

	# 		### SAVE AFFINE TRANSFORM PARAMETERS FOR PLOTTING MOTION ###
	# 		transformlist = moco['fwdtransforms']
	# 		for x in transformlist:
	# 			if '.mat' in x:
	# 				temp = ants.read_transform(x)
	# 				transform_matrix.append(temp.parameters)

	# 		### DELETE FORWARD TRANSFORMS ###
	# 		transformlist = moco['fwdtransforms']
	# 		for x in transformlist:
	# 			if '.mat' not in x:
	# 				os.remove(x)

	# 		### DELETE INVERSE TRANSFORMS ###
	# 		transformlist = moco['invtransforms']
	# 		for x in transformlist:
	# 			if '.mat' not in x:
	# 				os.remove(x)

	# 	moco_ch1_chunk = np.moveaxis(np.asarray(moco_ch1_chunk),0,-1)
	# 	if filepath_ch2 is not None:
	# 		moco_ch2_chunk = np.moveaxis(np.asarray(moco_ch2_chunk),0,-1)
	# 	#printlog("chunk shape: {}. Time: {}".format(moco_ch1_chunk.shape, time()-t0))

	# 	### APPEND WARPED VOL TO HD5F FILE - CHANNEL 1 ###
	# 	t0 = time()
	# 	with h5py.File(savefile_master, 'a') as f:
	# 		f['data'][...,steps[j]:steps[j+1]] = moco_ch1_chunk																		
	# 	printlog(F'Ch_1 append time: {time()-t0}')
																						
	# 	### APPEND WARPED VOL TO HD5F FILE - CHANNEL 2 ###
	# 	t0 = time()
	# 	if filepath_ch2 is not None:
	# 		with h5py.File(savefile_mirror, 'a') as f:
	# 			#f['data'][...,i] = moco_ch2
	# 			f['data'][...,steps[j]:steps[j+1]] = moco_ch2_chunk
	# 		printlog(F'Ch_2 append time: {time()-t0}')

	# ### SAVE TRANSFORMS ###
	# printlog("saving transforms")
	# printlog(F"savefile_master: {savefile_master}")
	# transform_matrix = np.array(transform_matrix)
	# save_file = os.path.join(os.path.dirname(savefile_master), 'motcorr_params')
	# np.save(save_file,transform_matrix)

	savefile_master = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20190101_walking_dataset/fly_123/func_0/moco/functional_channel_1_moco.h5"
	file = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20190101_walking_dataset/fly_123/func_0/moco/motcorr_params.npy"
	transform_matrix = np.load(file)
	### MAKE MOCO PLOT ###
	#try:
	printlog("making moco plot")

	moco_dir = os.path.dirname(savefile_master)
	xml_dir = os.path.join(os.path.dirname(moco_dir), 'imaging')

	printlog(F"moco_dir: {moco_dir}")
	printlog(F"savefile_master: {savefile_master}")
	printlog(F"xml_dir: {xml_dir}")

	save_motion_figure(transform_matrix, xml_dir, moco_dir, scantype)
	#except:
	#	printlog("Could not make moco plot, probably can't find xml file to grab image resolution.")

def make_empty_h5(directory, file, brain_dims, save_type):
	if save_type == 'curr_dir':
		moco_dir = os.path.join(directory,'moco')
		if not os.path.exists(moco_dir):
			os.mkdir(moco_dir)
	elif save_type == 'back_one_dir':
		directory = os.path.dirname(directory) # go back one directory
		moco_dir = os.path.join(directory,'moco')
		if not os.path.exists(moco_dir):
			os.mkdir(moco_dir)

	savefile = os.path.join(moco_dir, file)
	with h5py.File(savefile, 'w') as f:
		dset = f.create_dataset('data', brain_dims, dtype='float32', chunks=True)
	return savefile

def check_for_file(file, directory):
	filepath = os.path.join(directory, file)
	if os.path.exists(filepath):
		return filepath
	else:
		return None

def save_motion_figure(transform_matrix, directory, motcorr_directory, scantype):
	# Get voxel resolution for figure
	if scantype == 'func':
		file = os.path.join(directory, 'functional.xml')
	elif scantype == 'anat':
		file = os.path.join(directory, 'anatomy.xml')
	x_res, y_res, z_res = brainsss.get_resolution(file)

	# Save figure of motion over time
	save_file = os.path.join(motcorr_directory, 'motion_correction.png')
	plt.figure(figsize=(10,10))
	plt.plot(transform_matrix[:,9]*x_res, label = 'y') # note, resolutions are switched since axes are switched
	plt.plot(transform_matrix[:,10]*y_res, label = 'x')
	plt.plot(transform_matrix[:,11]*z_res, label = 'z')
	plt.ylabel('Motion Correction, um')
	plt.xlabel('Time')
	plt.title(directory)
	plt.legend()
	plt.savefig(save_file, bbox_inches='tight', dpi=300)

if __name__ == '__main__':
	# print(sys.argv[1])
	main(json.loads(sys.argv[1]))
