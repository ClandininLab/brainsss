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

    behavior = args['behavior']

    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    printlog(load_directory)

    fps = 100 # of fictrac camera

    ### load brain timestamps ###
    timestamps = brainsss.load_timestamps(os.path.join(load_directory, 'imaging'))

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
    
    ### Correlate ###
    printlog("Performing Correlation on {}; behavior: {}".format(brain_file, behavior))
    corr_brain = np.zeros((256,128,49))
    for z in range(49):
        
        ### interpolate fictrac to match the timestamps of this slice
        printlog(F"{z}")
        fictrac_interp = brainsss.smooth_and_interp_fictrac(fictrac_raw, fps, resolution, expt_len, behavior, timestamps=timestamps, z=z)

        for i in range(256):
            for j in range(128):
                # nan to num should be taken care of in zscore, but checking here for some already processed brains
                if np.any(np.isnan(brain[i,j,z,:])):
                    printlog(F'warning found nan at x = {i}; y = {j}; z = {z}')
                    corr_brain[i,j,z] = 0
                elif len(np.unique(brain[i,j,z,:])) == 1:
                    printlog(F'warning found constant value at x = {i}; y = {j}; z = {z}')
                    corr_brain[i,j,z] = 0
                else:
                    corr_brain[i,j,z] = scipy.stats.pearsonr(fictrac_interp, brain[i,j,z,:])[0]

    ### SAVE ###
    if not os.path.exists(save_directory):
        os.mkdir(save_directory)

    if 'warp' in full_load_path:
       save_str = '_warp'
    else:
        save_str = ''

    date = time.strftime("%Y%m%d")

    save_file = os.path.join(save_directory, '{}_corr_{}{}.nii'.format(date, behavior, save_str))
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