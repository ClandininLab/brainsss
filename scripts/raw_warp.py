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
        printlog('RAM memory used::{}'.format(psutil.virtual_memory()[2]))
        printlog('RAM Used (GB)::{}'.format(psutil.virtual_memory()[3]/1000000000))
        
        #QC fig of raw data
        save_file = os.path.join(save_directory, 'raw_brain.nii')
        nib.Nifti1Image(data, np.eye(4)).to_filename(save_file)
        printlog("Saved {}".format(save_file))
        brain_img = np.asarray(nib.load(save_file).get_data().squeeze(), dtype='float32')
        plt.figure(figsize=(10,4))
        plt.imshow(np.max(brain_img[:,:,20,:],axis=-1).T,cmap='gray')
        plt.axis('off')
        save_file_f = save_file[:-3] + 'png'
        plt.savefig(save_file_f, bbox_inches='tight', dpi=300)
        
        #Warp in chunks so we don't run out of memory, this is creating the stepsize of chunks
        stepsize = 100
        steps = list(range(0,dims[-1],stepsize))
        steps.append(dims[-1])

        #Load mean brain
        fixed = brainsss.load_fda_meanbrain()
        
        #Warp the brain
        warped = warp_raw(data=data, steps=steps, fixed=fixed, func_path=fly_directory)
        printlog("Warped brain shape is {}".format(np.shape(warped)))
        printlog('RAM memory used::{}'.format(psutil.virtual_memory()[2]))
        printlog('RAM Used (GB)::{}'.format(psutil.virtual_memory()[3]/1000000000))
    
        #Save the warped brain
        with h5py.File(save_file, "w") as data_file:
            data_file.create_dataset("data", data=warped.astype('float32'))
        printlog('RAM memory used::{}'.format(psutil.virtual_memory()[2]))
        printlog('RAM Used (GB)::{}'.format(psutil.virtual_memory()[3]/1000000000))
    
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

