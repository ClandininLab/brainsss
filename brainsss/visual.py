import os
import h5py
import numpy as np
import pandas as pd
import pickle


def pd_csv_to_h5py(directory, file):
	""" Loads photodiode data from csv file and saves to h5py file.

	Parameters
	----------
	directory: full path to vision folder
	file: csv file

	Returns
	-------
	Nothing. """

	print('loading raw photodiode data... ',end='')
	#load raw data from csv
	load_file = os.path.join(directory, file)
	temp = np.genfromtxt(load_file, delimiter=',',skip_header=1)
	t = temp[:,0]
	ft_triggers = temp[:,1]
	pd1 = temp[:,2]
	pd2 = temp[:,3]
	print('done')

	#save as h5py file
	print('saving photodiode data as h5py file...',end='')
	save_file = os.path.join(directory, 'photodiode.h5')
	with h5py.File(save_file, 'w') as hf:
		hf.create_dataset('time',  data=t)
		hf.create_dataset('ft_triggers',  data=ft_triggers)
		hf.create_dataset('pd1',  data=pd1)
		hf.create_dataset('pd2',  data=pd2)
	print('done')
	
def load_h5py_pd_data(directory):
	""" Loads photodiode data from h5py file.

	Parameters
	----------
	directory: full path to vision folder

	Returns
	-------
	t: 1D numpy array, times of photodiode measurement (in ms)
	pd1: 1D numpy array, photodiode 1 measurements
	pd2: 1D numpy array, photodiode 1 measurements """

	print('loading photodiode data... ',end='')
	#load from h5py file
	load_file = os.path.join(directory, 'photodiode.h5')
	with h5py.File(load_file, 'r') as hf:
		t = hf['time'][:]
		ft_triggers = hf['ft_triggers'][:]
		pd1 = hf['pd1'][:]
		pd2 = hf['pd2'][:]
	print('done')
	return t, ft_triggers, pd1, pd2

def load_photodiode(vision_path):
	""" Tries to load photodiode data from h5py file, and if it doesn't exist loads from csv file.

	Parameters
	----------
	vision_path: full path to vision folder

	Returns
	-------
	t: 1D numpy array, times of photodiode measurement (in ms)
	pd1: 1D numpy array, photodiode 1 measurements
	pd2: 1D numpy array, photodiode 1 measurements """

	# Try to load from h5py file
	try:
		t, ft_triggers, pd1, pd2 = load_h5py_pd_data(vision_path)
		
	# First convert from csv to h5py, then load h5py
	except:
		pd_csv_to_h5py(vision_path,'photodiode.csv')
		t, ft_triggers, pd1, pd2 = load_h5py_pd_data(vision_path)
	return t, ft_triggers, pd1, pd2

def get_stimulus_metadata(vision_path, printlog=None):
	# if this function is not being used with a printlog, redirect printlog to simply print
	if printlog is None:
		printlog = print


	### try to get from pickle ###
	pickle_path = os.path.join(vision_path, 'stimulus_metadata.pkl')
	if os.path.exists(pickle_path):
		printlog("Loaded from Pickle.")
		with open(pickle_path, 'rb') as f:
			metadata = pickle.load(f)
		return metadata['stim_ids'], metadata['angles']
	
	### if no pickle, load from .h5 and save pickle for future ###
	printlog("No pickle; parsing visprotocol.h5")
	fname = [x for x in os.listdir(vision_path) if '.hdf5' in x][0]
	visprotocol_file = os.path.join(vision_path, fname)

	stim_ids = []
	angles = []
	found_a_full_series = False
	with h5py.File(visprotocol_file, 'r') as f:

		### loop over flies and series to find the one that has many stim presentations (others were aborted)
		# note it is critical each fly has their own .h5 file saved
		fly_ids = list(f['Flies'].keys())
		printlog("Found fly ids: {}".format(fly_ids))
		for fly_id in fly_ids:
			
			series = list(f['Flies'][fly_id]['epoch_runs'].keys())
			printlog("Found series: {}".format(series))
			for serie in series:

				epoch_ids = f['Flies'][fly_id]['epoch_runs'][serie].get('epochs').keys()
				printlog(str(len(epoch_ids)))
				for i, epoch_id in enumerate(epoch_ids):
					stim_id = f['Flies'][fly_id]['epoch_runs'][serie].get('epochs').get(epoch_id).attrs['component_stim_type']
					stim_ids.append(stim_id)
					if stim_id == 'DriftingSquareGrating':
						angle = f['Flies'][fly_id]['epoch_runs'][serie].get('epochs').get(epoch_id).attrs['angle']
						angles.append(angle)
					else:
						angles.append(None)
						
				if len(stim_ids) > 100:
					if found_a_full_series:
						printlog('WARNING - FOUND 2 FULL SERIES IN THIS VISPROTOCOL HDF5 FILE. YOU NEED TO RESOLVE WHICH TO CHOOSE')
						printlog('QUITING')
						return
					found_a_full_series = True
					### save dic for final save below
					metadata = {'stim_ids': stim_ids, 'angles': angles}

		### SAVE ###
		if found_a_full_series:
			save_file = os.path.join(vision_path, 'stimulus_metadata.pkl')
			with open(save_file, 'wb') as f:
				pickle.dump(metadata, f)
			printlog("created {}".format(save_file))
		else:
			"did not find any series longer than 100 stimuli. Not saving metadata pickle."
		
		return stim_ids, angles
		printlog('Could not get visual metadata.')
	

def extract_stim_times_from_pd(photodiode_trace, time_vector):
	threshold=0.8,
	command_frame_rate=120
	sample_rate = 10000
	minimum_epoch_separation = 0.9 * (1 + 0) * sample_rate

	# shift & normalize so frame monitor trace lives on [0 1]
	photodiode_trace = photodiode_trace - np.min(photodiode_trace)
	photodiode_trace = photodiode_trace / np.max(photodiode_trace)

	# find frame flip times
	V_orig = photodiode_trace[0:-2]
	V_shift = photodiode_trace[1:-1]
	ups = np.where(np.logical_and(V_orig < threshold, V_shift >= threshold))[0] + 1
	downs = np.where(np.logical_and(V_orig >= threshold, V_shift < threshold))[0] + 1
	frame_times = np.sort(np.append(ups, downs))

	# Use frame flip times to find stimulus start times
	stimulus_start_frames = np.append(0, np.where(np.diff(frame_times) > minimum_epoch_separation)[0] + 1)
	stimulus_end_frames = np.append(np.where(np.diff(frame_times) > minimum_epoch_separation)[0], len(frame_times)-1)
	stimulus_start_times = frame_times[stimulus_start_frames] / sample_rate  # datapoints -> sec
	stimulus_end_times = frame_times[stimulus_end_frames] / sample_rate  # datapoints -> sec

	stim_durations = stimulus_end_times - stimulus_start_times # sec
	return stimulus_start_times