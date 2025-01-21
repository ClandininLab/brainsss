import os
import sys
import brainsss.brain_utils as brain_utils
import brainsss.utils as utils
import numpy as np
import argparse
import subprocess
import json
import brainsss
import h5py
import ants
import psutil
from scipy.ndimage import gaussian_filter, gaussian_filter1d



def main(args):
    load_directory = args['load_directory']
    save_directory = args['save_directory']
    brain_file = args['brain_file']
    stepsize = 100

    full_load_path = os.path.join(load_directory, brain_file)
    # full_load_path_l = os.path.join(load_directory, brain_lpf)
    save_file = os.path.join(save_directory, brain_file.split('.')[0] + '_dff.h5')

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ###########
    ### DFF ###
    ###########
    stepsize=100
    printlog("Beginning DFF")
    with h5py.File(full_load_path, 'r') as hf:
        hpf = hf['hpf'][:]
        lpf = hf['lpf'][:]
        dimsh = np.shape(hpf)
        dimsl = np.shape(lpf)

        printlog(f"Highpass filter shape is {dimsh}, lowpass filter shape is {dimsl}")
        
        # #load the mean brain
        # fixed = brainsss.load_fda_meanbrain()
        lpf_min=np.min(lpf)
        #do dff
        with np.errstate(divide='ignore', invalid='ignore'):
            dff = np.true_divide(hpf, lpf-lpf_min)
        
        #mask brain
        # dff=np.where(fixed.numpy()[...,None]>0.1, dff, 0)
        dff_dims = np.shape(dff)
        printlog("dff data shape is {}".format(dff_dims))
        # save dff data
        with h5py.File(save_file, "w") as data_file:
            data_file.create_dataset("data", data=dff.astype('float32')) 
      
    printlog(f"Df/f done. Data saved in {save_file}")
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

