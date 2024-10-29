import os
import sys
import numpy as np
import argparse
import subprocess
import json
import nibabel as nib
import brainsss
import h5py
import ants
import matplotlib.pyplot as plt
import psutil
from brainsss.brain_utils import warp_raw
from brainsss.utils import save_qc_png, save_h5_chunks



def main(args):
    fly_directory = args['fly_directory']
    load_directory = args['load_directory']
    save_directory = args['save_directory']
    brain_file = args['brain_file']
    stepsize = 100

    full_load_path = os.path.join(load_directory, brain_file)
    save_file = os.path.join(save_directory, brain_file.split('.')[0] + '_warp.h5')

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ################
    ### RAW WARP ###
    ################

    printlog("Beginning RAW WARP")
    with h5py.File(full_load_path, 'r') as hf:
        data = hf['data'][:]
        dims = np.shape(data)

        printlog("Data shape is {}".format(dims))
        # printlog('RAM memory used::{}'.format(psutil.virtual_memory()[2]))
        # printlog('RAM Used (GB)::{}'.format(psutil.virtual_memory()[3]/1000000000))
        
        #QC fig of raw data
        save_img = os.path.join(load_directory, 'raw_brain.nii')
        save_img_file=save_qc_png(data, save_img)
        printlog("Raw data QC figure saved in {}".format(save_img_file))
       

        #Load mean brain
        fixed = brainsss.load_fda_meanbrain()
        
        #Warp the brain
        warped = warp_raw(data=data, stepsize=100, fixed=fixed, func_path=fly_directory)
        printlog("Warped brain shape is {}".format(np.shape(warped)))
        # printlog('RAM memory used::{}'.format(psutil.virtual_memory()[2]))
        # printlog('RAM Used (GB)::{}'.format(psutil.virtual_memory()[3]/1000000000))

        ### CHECK IF THIS WORKS!!!!!!! theoretically
        ### should save the .h5 in chunks and therefore should help with memory issues??
        ### not sure tho. If works put into timestamp warp as well
        
        
        
        # with h5py.File(save_file, 'w') as f:
        #     dset = f.create_dataset('data', dims, dtype='float32', chunks=True) 
            
        #     for chunk_num in range(len(steps)):
        #         if chunk_num + 1 <= len(steps)-1:
        #             chunkstart = steps[chunk_num]
        #             chunkend = steps[chunk_num + 1]
        #             data_chunk = warped[...,chunkstart:chunkend]
        #             f['data'][:,:,:,chunkstart:chunkend] = np.nan_to_num(data_chunk) ### Added nan to num because if a pixel is a constant value (over saturated) will divide by 0
        #             printlog(F"vol: {chunkstart} to {chunkend}")
        
        save_h5_chunks(save_file, warped, stepsize=100)
            
        #Save the warped brain
        # with h5py.File(save_file, "w") as data_file:
        #     data_file.create_dataset("data", data=warped.astype('float32'))
        # # printlog('RAM memory used::{}'.format(psutil.virtual_memory()[2]))
        # # printlog('RAM Used (GB)::{}'.format(psutil.virtual_memory()[3]/1000000000))
    printlog("Warp done. Data saved in {}".format(save_file))
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

