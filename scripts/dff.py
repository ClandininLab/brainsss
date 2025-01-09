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
        hpf = hf['hpf']
        lpf = hf['lpf']
        dimsh = np.shape(hpf)
        dimsl = np.shape(lpf)

        printlog(f"Highpass filter shape is {dimsh}, lowpass filter shape is {dimsl}")
        
        #load the mean brain
        fixed = brainsss.load_fda_meanbrain()
        
        #do dff
        lpf[lpf==0]=np.nan #change 0s to nan so doesn't divide by 0
        dff=hpf/lpf 
        
        #mask brain
        dff=np.where(fixed.numpy()[...,None]>0.1, dff, 0)
        dff_dims = np.shape(dff)
        printlog("dff data shape is {}".format(dff_dims))
        
        #save dff data
        # utils.save_h5_chunks(save_file, dff, stepsize=stepsize)
        with h5py.File(save_file, "w") as data_file:
            data_file.create_dataset("data", data=dff.astype('float32'))
    printlog("dff done. Data saved in {}".format(save_file))
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

