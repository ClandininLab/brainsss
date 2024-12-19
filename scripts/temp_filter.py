import os
import sys
import brainsss.brain_utils as brain_utils
import brainsss.utils as utils
import brainsss.fictrac as fictrac
import numpy as np
import argparse
import subprocess
import json
import brainsss
import h5py
import ants
import psutil
from scipy.ndimage import gaussian_filter



def main(args):
    fly_directory = args['fly_directory']
    load_directory = args['load_directory']
    save_directory = args['save_directory']
    brain_file = args['brain_file']
    timestamp_file = args['timestamp_file']
    stepsize = 100

    brain_load_path = os.path.join(load_directory, brain_file)
    ts_load_path = os.path.join(load_directory, timestamp_file)
    save_file = os.path.join(save_directory, brain_file.split('.')[0] + '_filtered.h5')

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    #######################
    ### TEMPORAL FILTER ###
    #######################

    printlog("Beginning temporal filter")
    #load brain
    with h5py.File(brain_load_path, 'r') as hf:
        brain = hf['data']
        with h5py.File(ts_load_path, 'r') as hf:
            ts = hf['data']
        
    ###########################
    ### PREP VISUAL STIMULI ###
    ###########################

    vision_path = os.path.join(fly_directory,'func_0', 'visual')

    ### Load Photodiode ###
    t, ft_triggers, pd1, pd2 = brainsss.load_photodiode(vision_path)
    stimulus_start_times = brainsss.extract_stim_times_from_pd(pd2, t)

    # *100 puts in units of 10ms, which will match fictrac
    st_10ms = [int(stimulus_start_times[i]*100) for i in range(len(stimulus_start_times))]

    # get 1ms version to match neural timestamps
    starts_loom = st_10ms

    ####################
    ### Prep Fictrac ###
    ####################

    fictrac_path = os.path.join(fly_directory, 'func_0', 'fictrac')
    fictrac_raw = brainsss.load_fictrac(fictrac_path)

    fps = 100
    resolution = 10 #desired resolution in ms
    expt_len = fictrac_raw.shape[0]/fps*1000
    behaviors = ['dRotLabY', 'dRotLabZ', 'dRotLabX', 'speed']
    fictrac = {}
    for behavior in behaviors:
        if behavior == 'dRotLabY': short = 'Y'
        elif behavior == 'dRotLabZ': short = 'Z'
        elif behavior == 'dRotLabX': short = 'X'
        fictrac[short] = brainsss.smooth_and_interp_fictrac(fictrac_raw, fps, resolution, expt_len, behavior)
    starts_loom_ms=[n*10 for n in starts_loom]
    
    bin_start = -500; bin_end = 2000; bin_size = 100 #ms
    neural_bins = np.arange(bin_start,bin_end,bin_size)
    
    
    #if loom starts are outside of the neural data, remove them
    bool_starts=(starts_loom_ms>=(np.min(ts))) & (starts_loom_ms<=(np.max(ts)))
    starts_loom_ms=np.array(starts_loom_ms)
    starts_loom_ms=starts_loom_ms[bool_starts]
    
    bins_array=[]
    for loom in starts_loom_ms:
    #     print(loom)
        start=loom+bin_start
        end=loom+bin_end-bin_size
    #     edges=[start,end]
        bins_array.append(start)
        bins_array.append(end)
    # bins_test=np.vstack(bins_test)
    bins_array=np.array(bins_array)
    bins_shape=np.shape(bins_array)
    printlog("Bins shape is {}".format(bins_shape))
    
    bin_idx = np.digitize(ts, bins_array)

    # make loom-relative version of ts
    ts_rel = ts.copy()

    # Loop through each loom-containing bin_idx and subtract starts_loom_ms
    for i in range(len(starts_loom_ms)):
        # subtract loom onset time for corresponding timestamps
        ts_rel[bin_idx == i*2 + 1] -= starts_loom_ms[i]

    # boolean mask of where bin_idx is odd
    odd_mask = bin_idx % 2 == 1

    # Create flattened (xyz X time) 
    n_timesteps = ts_rel.shape[-1]
    ts_rel_flat = ts_rel.reshape(-1, n_timesteps)
    brain_flat = brain.reshape(-1, n_timesteps)
    odd_mask_flat = odd_mask.reshape(-1, n_timesteps)

    # Collect ts_rel and brain elements that fall within loom window / bin
    within_bin_brain_flat  = [brain_flat[xyz][odd_mask_flat[xyz]] for xyz in range(brain_flat.shape[0])]
    within_bin_ts_rel_flat = [ts_rel_flat[xyz][odd_mask_flat[xyz]] for xyz in range(ts_rel_flat.shape[0])]

    # Find the maximum length of the sublists
    max_len = max(len(sublist) for sublist in within_bin_brain_flat)

    # Create a 2D NumPy array filled with np.nan, with the appropriate shape
    n_voxels = len(within_bin_brain_flat)
    within_bin_brain_flat_np = np.full((n_voxels, max_len), np.nan)
    within_bin_ts_rel_flat_np = np.full((n_voxels, max_len), np.nan)

    # Populate the array with the values from the original list of lists
    for i, (brain_sl, ts_rel_sl) in enumerate(zip(within_bin_brain_flat, within_bin_ts_rel_flat)):
        within_bin_brain_flat_np[i, :len(brain_sl)] = brain_sl
        within_bin_ts_rel_flat_np[i, :len(ts_rel_sl)] = ts_rel_sl

    # unflatten
    static_brain_shape = brain.shape[:-1]
    within_bin_brain_np = within_bin_brain_flat_np.reshape(*static_brain_shape, max_len)
    within_bin_ts_rel_np = within_bin_ts_rel_flat_np.reshape(*static_brain_shape, max_len)    
    
    brain_shape=within_bin_brain_np.shape()
    ts_shape=within_bin_ts_rel_np.shape()
    printlog(f"Temporal filtered data shape is {brain_shape} and timestamp shape is {ts_shape}")
    
    
    printlog("Temporal filtering done. Data saved in {}".format(save_file))
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

