import os
import sys
import brainsss.fictrac as fictrac
import numpy as np
import json
import brainsss
import h5py
import ants
import psutil

def main(args):
    fly_directory = args['fly_directory']
    save_directory = args['save_directory']
    timestamp_file = args['timestamp_file']
    filter_file = args['filter_file']
    stepsize = 100

    filter_load_path=os.path.join(save_directory, filter_file)
    ts_load_path = os.path.join(fly_directory, timestamp_file)
    save_file = os.path.join(save_directory, 'ts_rel_odd_mask.h5')

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ###########################
    ### REL TIME & ODD MASK ###
    ###########################

    printlog("Beginning relative timestamp & odd mask creation")
   
    #load brain
    with h5py.File(ts_load_path, 'r') as tf, \
        h5py.File(filter_load_path, 'r') as ff:

        ts = tf['data'][:]
        bins = ff['bins'][:]
        looms = ff['loom_starts'][:]  
    
        
        for i in range(len(looms)):
            # subtract loom onset time for corresponding timestamps
            ts[bins == i*2 + 1] -= looms[i]
        
        # Get the odd indices of the bin_idx array
        
        # boolean mask of where bin_idx is odd
        odd_mask = bins % 2 == 1

        ts_shape=np.shape(ts)
        om_shape=np.shape(odd_mask)
        
        printlog(f"Relative time shape is {ts_shape} and timestamp shape is {om_shape}")
        
        with h5py.File(save_file, "w") as data_file:
                data_file.create_dataset("odd_mask", data=odd_mask.astype('boolean'))
                data_file.create_dataset("ts_rel", data=ts.astype('float32'))
            
        printlog(f"Relative timestamps and odd mask creation done. Data saved in {save_file}")
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

