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
    brain_hpf = args['brain_file_h']
    brain_lpf = args['brain_file_l']
    stepsize = 100

    full_load_path_h = os.path.join(load_directory, brain_hpf)
    full_load_path_l = os.path.join(load_directory, brain_lpf)
    save_file = os.path.join(save_directory, brain_hpf.split('.')[0] + '_dff.h5')

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
    with h5py.File(full_load_path_h, 'r') as hf:
        hpf = hf['data'][:]
        dimsh = np.shape(hpf)

        printlog(f"Highpass filter shape is {dimsh}")
        
    with h5py.File(full_load_path_l, 'r') as lf:
        lpf = lf['data'][:]
        dimsl = np.shape(lpf)
        printlog(f"Lowpass filter shape is {dimsl}")
        
        #load the mean brain
        fixed = brainsss.load_fda_meanbrain()
        
        #do dff
        dff=hpf/(lpf-lpf.min()+100) #end is to get normalized numbers
        
        #mask brain
        dff=np.where(fixed.numpy()[...,None]>0.1, dff, 0)
        dff_dims = np.shape(dff)
        printlog("dff data shape is {}".format(dff_dims))
        
        #save dff data
        utils.save_h5_chunks(save_file, dff, stepsize=stepsize)
    printlog("dff done. Data saved in {}".format(save_file))
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

