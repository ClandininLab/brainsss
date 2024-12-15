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

def main(args):
    load_directory = args['load_directory']
    save_directory = args['save_directory']
    brain_file = args['brain_file']
    stepsize = 100

    full_load_path = os.path.join(load_directory, brain_file)
    save_file = os.path.join(save_directory, brain_file.split('.')[0] + '_blurred.h5')

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ################
    ### RAW WARP ###
    ################

    printlog("Beginning blurring")
    with h5py.File(full_load_path, 'r') as hf:
        brain = hf['data']
        dims = np.shape(brain)
        stepsize=100


        printlog("Data shape is {}".format(dims))

        #gaussian blur data for less noise
        warps_blur=[]
        for i in range(np.shape(brain)[-1]):
            warps_temp = gaussian_filter(brain[...,i], sigma=2)
            warps_blur.append(warps_temp)
        warps_blur=np.asarray(warps_blur)
        warps_blur=np.moveaxis(warps_blur,0,-1)
        blur_dim=np.shape(warps_blur)
        printlog("Blurred data shape is {}".format(blur_dim))
        # save_img = os.path.join(load_directory, 'blurred_brain.nii')
        # save_img_file=utils.save_qc_png(warps_blur, save_img)
        # printlog("Raw data QC figure saved in {}".format(save_img_file))

        
        utils.save_h5_chunks(save_file, warps_blur, stepsize=stepsize)
        printlog("Blurring done")

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))