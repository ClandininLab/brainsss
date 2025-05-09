import os
import sys
import numpy as np
import brainsss.brain_utils as brain_utils
import brainsss.utils as utils
import json
import brainsss
import h5py
import ants
from scipy.ndimage import gaussian_filter
from multiprocessing import Pool

def apply_gaussian_filter(slice_data):
    return gaussian_filter(slice_data, sigma=2)

def single_vol_blur(vol):
    return gaussian_filter(vol, sigma=2)

def parallel_vol_blur(vol_stack, n_proc=20):
    with Pool(processes=n_proc) as p:
        res = p.imap(single_vol_blur, vol_stack, 128)
        blur = []
        for r in res:
            blur.append(r)
    return blur

def main(args):
    load_directory = args['load_directory']
    save_directory = args['save_directory']
    brain_file = args['brain_file']
    redo = args['redo']
    # stepsize = 100

    full_load_path = os.path.join(load_directory, brain_file)
    save_file = os.path.join(save_directory, brain_file.split('.')[0] + '_blurred.h5')

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ################
    ### BLURRRRR ###
    ################
    if os.path.exists(save_file)==False or redo:
        printlog("Beginning blurring")
        with h5py.File(full_load_path, 'r') as hf:
            brain = hf['data'][:]
            dims = np.shape(brain)
            stepsize=100


            printlog(f"Data shape is {dims}")

            #gaussian blur data for less noise
            
            warps_blur = np.array([gaussian_filter(brain[..., i], sigma=2) for i in range(dims[-1])])
            
            warps_blur = np.moveaxis(np.array(warps_blur), 0, -1) 
            blur_dim=np.shape(warps_blur)
            printlog(f"Blurred data shape is {blur_dim}")
            
            del brain
            
            with h5py.File(save_file, "w") as data_file:
                data_file.create_dataset("data", data=warps_blur.astype('float32'))
            # utils.save_h5_chunks(save_file, warps_blur, stepsize=stepsize)
            printlog("Blurring done")
    else:
        printlog("Blurring already done")

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))