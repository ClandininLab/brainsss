import os
import sys
import numpy as np
import argparse
import subprocess
import json
import h5py
import time
from scipy.ndimage import gaussian_filter1d
import nibabel as nib
import brainsss
import scipy
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt

def main(args):

    load_directory = args['load_directory']
    save_directory = args['save_directory']
    brain_file = args['brain_file']
    grey_only = args['grey_only']

    behavior = args['behavior']
    fps = args['fps'] # of fictrac camera

    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    printlog(load_directory)

    ### load brain timestamps ###
    timestamps = brainsss.load_timestamps(os.path.join(load_directory, 'imaging'))

    ### this means only calculat correlation during periods of grey stimuli ###
    if grey_only:
        vision_path = os.path.join(load_directory, 'visual')
        stim_ids, angles = brainsss.get_stimulus_metadata(vision_path)
        t, ft_triggers, pd1, pd2 = brainsss.load_photodiode(vision_path)
        stimulus_start_times = brainsss.extract_stim_times_from_pd(pd2, t)
        grey_starts = []
        grey_stops = []
        for i,stim in enumerate(stim_ids):
            if stim == 'ConstantBackground':
                grey_starts.append(stimulus_start_times[i])
                grey_stops.append(stimulus_start_times[i]+60)
        grey_starts = [i*1000 for i in grey_starts] # convert from s to ms
        grey_stops = [i*1000 for i in grey_stops] # convert from s to ms
        idx_to_use = []
        for i in range(len(grey_starts)):
            idx_to_use.extend(np.where((grey_starts[i] < timestamps[:,0]) & (timestamps[:,0] < grey_stops[i]))[0])
        ### this is now a list of indices where grey stim was presented
    else:
        idx_to_use = list(range(timestamps.shape[0]))

    ### Load fictrac ###
    fictrac_raw = brainsss.load_fictrac(os.path.join(load_directory, 'fictrac'))
    resolution = 10 #desired resolution in ms
    expt_len = fictrac_raw.shape[0]/fps*1000    

    ### Load brain ###
    printlog('loading brain')
    full_load_path = os.path.join(load_directory, brain_file)

    if full_load_path.endswith('.h5'):
        with h5py.File(full_load_path, 'r') as hf:
            brain = hf['data'][:]
    elif full_load_path.endswith('.nii'):
        brain = np.asarray(nib.load(full_load_path).get_data().squeeze(), dtype='float32')
    printlog('done')
    
    # Get brain size
    x_dim = brain.shape[0]
    y_dim = brain.shape[1]
    z_dim = brain.shape[2]

    ### Correlate ###
    printlog("Performing Correlation on {}; behavior: {}".format(brain_file, behavior))
    corr_brain = np.zeros((x_dim,y_dim,z_dim))
    for z in range(z_dim):
        
        ### interpolate fictrac to match the timestamps of this slice
        printlog(F"{z}")
        fictrac_interp = brainsss.smooth_and_interp_fictrac(fictrac_raw, fps, resolution, expt_len, behavior, timestamps=timestamps, z=z)

        for i in range(x_dim):
            for j in range(y_dim):
                # nan to num should be taken care of in zscore, but checking here for some already processed brains
                if np.any(np.isnan(brain[i,j,z,:])):
                    printlog(F'warning found nan at x = {i}; y = {j}; z = {z}')
                    corr_brain[i,j,z] = 0
                elif len(np.unique(brain[i,j,z,:])) == 1:
                #     if np.unique(brain[i,j,z,:]) != 0:
                #         printlog(F'warning found non-zero constant value at x = {i}; y = {j}; z = {z}')
                    corr_brain[i,j,z] = 0
                else:
                    #idx_to_use can be used to select a subset of timepoints
                    corr_brain[i,j,z] = scipy.stats.pearsonr(fictrac_interp[idx_to_use], brain[i,j,z,:][idx_to_use])[0]

    ### SAVE ###
    if not os.path.exists(save_directory):
        os.mkdir(save_directory)

    if 'warp' in full_load_path:
       warp_str = '_warp'
    else:
        warp_str = ''
    if grey_only:
        grey_str = '_grey'
    else:
        grey_str = ''
    if 'zscore' not in full_load_path:
        no_zscore_highpass_str = '_mocoonly'
    else:
        no_zscore_highpass_str = ''

    #date = time.strftime("%Y%m%d")
    date = '20220420'

    save_file = os.path.join(save_directory, '{}_corr_{}{}{}{}.nii'.format(date, behavior, warp_str, grey_str, no_zscore_highpass_str))
    nib.Nifti1Image(corr_brain, np.eye(4)).to_filename(save_file)
    printlog("Saved {}".format(save_file))
    save_maxproj_img(save_file)

def save_maxproj_img(file):
    brain = np.asarray(nib.load(file).get_data().squeeze(), dtype='float32')

    plt.figure(figsize=(10,4))
    plt.imshow(np.max(brain,axis=-1).T,cmap='gray')
    plt.axis('off')
    plt.colorbar()
    
    save_file = file[:-3] + 'png'
    plt.savefig(save_file, bbox_inches='tight', dpi=300)

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))