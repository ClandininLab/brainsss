import os
import sys
import numpy as np
import argparse
import subprocess
import json
import nibabel as nib
import brainsss
import h5py
import datetime
import matplotlib.pyplot as plt
from time import time
from time import strftime
from time import sleep

def main(args):
    
    load_directory = args['load_directory']
    save_directory = args['save_directory']
    brain_file = args['brain_file']
    stepsize = 2

    full_load_path = os.path.join(load_directory, brain_file)
    save_file = os.path.join(save_directory, brain_file.split('.')[0] + '_highpass.h5')

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    #################
    ### HIGH PASS ###
    #################

    printlog("Beginning high pass")
    with h5py.File(full_load_path, 'r') as hf:
        data = hf['data'] # this doesn't actually LOAD the data - it is just a proxy
        dims = np.shape(data)
        printlog("Data shape is {}".format(dims))
        
        steps = list(range(0,dims[-1],stepsize))
        steps.append(dims[-1])

        with h5py.File(save_file, 'w') as f:
            dset = f.create_dataset('data', dims, dtype='float32', chunks=True) 
            
            for chunk_num in range(len(steps)):
                t0 = time()
                if chunk_num + 1 <= len(steps)-1:
                    chunkstart = steps[chunk_num]
                    chunkend = steps[chunk_num + 1]
                    chunk = data[:,:,chunkstart:chunkend,:]
                    printlog("Chunk shape: {}".format(np.shape(chunk)))
                    chunk_mean = np.mean(chunk,axis=-1)
                    printlog("Chunk_mean shape: {}".format(np.shape(chunk_mean)))

                    ### SMOOTH ###
                    printlog('smoothing')
                    t0 = time.time()
                    smoothed_chunk = gaussian_filter1d(chunk,sigma=200,axis=-1,truncate=1)
                    printlog("brain smoothed duration: ({})".format(time.time()-t0))

                    ### Apply Smooth Correction ###
                    t0 = time.time()
                    chunk_high_pass = chunk - smoothed_chunk + chunk_mean[:,:,:,None] #need to add back in mean to preserve offset
                    printlog("brain corrected duration: ({})".format(time.time()-t0))

                    ### Save ###
                    t0 = time.time()
                    f['data'][:,:,chunkstart:chunkend,:] = chunk_high_pass
                    printlog(F"Saved vol: {chunkstart} to {chunkend} time: {time()-t0}")

    printlog("high pass done")

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))