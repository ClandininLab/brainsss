import os
import sys
import numpy as np
import argparse
import subprocess
import json
import time
from scipy.ndimage import gaussian_filter1d
import nibabel as nib
import brainsss
import scipy
from scipy.interpolate import interp1d

def main(args):

    load_directory = args['load_directory']
    save_directory = args['save_directory']
    brain_file = args['brain_file']

    behavior = args['behavior']

    logfile = args['logfile']
    printlog = getattr(flow.Printlog(logfile=logfile), 'print_to_log')

    fps = 100 # of fictrac camera


    ### Load brain ###
    printlog('loading brain')
    full_load_path = os.path.join(load_directory, brain_file)
    with h5py.File(full_load_path, 'r') as hf:
        brain = hf['data']
    printlog('done')

    ### load brain timestamps ###
    timestamps = brainsss.load_timestamps(os.path.join(load_directory, 'imaging'))

    ### Load fictrac ###
    fictrac_raw = brainsss.load_fictrac(load_directory)
    resolution = 10 #desired resolution in ms
    expt_len = fictrac_raw.shape[0]/fps*1000    
    if behavior == 'dRotLabY': short = 'Y'
    elif behavior == 'dRotLabZ': short = 'Z'
    
    ### Correlate ###
    printlog("Performing Correlation on {}; behavior: {}".format(brain_file, behavior))
    corr_brain = np.zeros((256,128,49))
    for z in range(49):
        printlog(F"{z}")

        ### interpolate fictrac to match the timestamps of this slice
        fictrac_interp = brainsss.smooth_and_interp_fictrac(fictrac_raw, fps, resolution, expt_len, timestamps, behavior, z)

        for i in range(256):
            for j in range(128):
                corr_brain[i,j,z] = scipy.stats.pearsonr(fictrac_interp, brain[i,j,z,:])[0]

    ### save ###
    corr_directory = os.path.join(directory, 'corr')

    if not os.path.exists(save_directory):
        os.mkdir(save_directory)

    save_file = os.path.join(save_directory, 'corr_{}.nii'.format(behavior))
    nib.Nifti1Image(corr_brain, np.eye(4)).to_filename(save_file)
    printlog("Saved {}".format(save_file))


if __name__ == '__main__':
    main(json.loads(sys.argv[1]))