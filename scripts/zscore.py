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
    stepsize = 100

    full_load_path = os.path.join(load_directory, brain_file)
    save_file = os.path.join(save_directory, brain_file.split('.')[0] + '_zscore.h5')

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ##############
    ### ZSCORE ###
    ##############

    printlog("Beginning ZSCORE")
    with h5py.File(full_load_path, 'r') as hf:
        data = hf['data'] # this doesn't actually LOAD the data - it is just a proxy
        dims = np.shape(data)

        printlog("Data shape is {}".format(dims))

        running_sum = np.zeros(dims[:3])
        running_sumofsq = np.zeros(dims[:3])
        
        steps = list(range(0,dims[-1],stepsize))
        steps.append(dims[-1])

        ### Calculate meanbrain ###

        for chunk_num in range(len(steps)):
            t0 = time()
            if chunk_num + 1 <= len(steps) - 1:
                chunkstart = steps[chunk_num]
                chunkend = steps[chunk_num + 1]
                chunk = data[:,:,:,chunkstart:chunkend]
                running_sum += np.sum(chunk, axis=3)
                printlog(F"vol: {chunkstart} to {chunkend} time: {time()-t0}")
        meanbrain = running_sum / dims[-1]

        ### Calculate std ###

        for chunk_num in range(len(steps)):
            t0 = time()
            if chunk_num + 1 <= len(steps) - 1:
                chunkstart = steps[chunk_num]
                chunkend = steps[chunk_num + 1]
                chunk = data[:,:,:,chunkstart:chunkend]
                running_sumofsq += np.sum((chunk-meanbrain[...,None])**2, axis=3)
                printlog(F"vol: {chunkstart} to {chunkend} time: {time()-t0}")
        final_std = np.sqrt(running_sumofsq/dims[-1])

        ### Calculate zscore and save ###

        with h5py.File(save_file, 'w') as f:
            dset = f.create_dataset('data', dims, dtype='float32', chunks=True) 
            
            for chunk_num in range(len(steps)):
                t0 = time()
                if chunk_num + 1 <= len(steps)-1:
                    chunkstart = steps[chunk_num]
                    chunkend = steps[chunk_num + 1]
                    chunk = data[:,:,:,chunkstart:chunkend]
                    running_sumofsq += np.sum((chunk-meanbrain[...,None])**2, axis=3)
                    zscored = (chunk - meanbrain[...,None]) / final_std[...,None]
                    f['data'][:,:,:,chunkstart:chunkend] = zscored
                    printlog(F"vol: {chunkstart} to {chunkend} time: {time()-t0}")

    printlog("zscore done")

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))