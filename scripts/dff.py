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
from scipy.ndimage import gaussian_filter



def main(args):
    load_directory = args['load_directory']
    save_directory = args['save_directory']
    brain_file = args['brain_file']
    stepsize = 100

    full_load_path = os.path.join(load_directory, brain_file)
    save_file = os.path.join(save_directory, brain_file.split('.')[0] + '_dff.h5')

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ################
    ### RAW WARP ###
    ################

    printlog("Beginning DFF")
    with h5py.File(full_load_path, 'r') as hf:
        brain = hf['data'][:]
        dims = np.shape(brain)
        stepsize=100


        printlog("Data shape is {}".format(dims))
        
        #filter requirements
        order = 2
        fs = 1.8 #sample rate, Hz
        cutoff =0.01 #desired cutoff frequency of the filter, Hz

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
        
        #create high pass filter data
        hpf_total = np.zeros(dims)
        steps = list(range(0,dims[-1],stepsize))
        steps.append(dims[-1])
        for z in range(dims[-2]):
            for chunk in steps:
                cs=chunk
                ce=chunk+stepsize
                if ce<=steps[-1]:
                    hpf_warps = brain_utils.apply_butter_highpass(warps_blur[...,cs:ce], z, cutoff, order, fs)
                    hpf_total[...z,cs:ce]=hpf_warps
        hpf_total = np.array(hpf_total)
        dims_hpfw = np.shape(hpf_total)
        printlog("High Pass Filter Data shape is {}".format(dims_hpfw))
        
        #subtract the high pass filter data from the blurred data to get low pass filter data as f nought
        lpf_total = warps_blur-hpf_total
        
        #load the mean brain
        fixed = brainsss.load_fda_meanbrain()
        
        #do dff
        dff=hpf_total/(lpf_total-lpf_total.min()+100) #end is to get normalized numbers
        
        #mask brain
        dff=np.where(fixed.numpy()[...,None]>0.1, dff, 0)
        dff_dims = np.shape(dff)
        printlog("dff data shape is {}".format(dff_dims))
        # hpf_img = os.path.join(load_directory, 'hpf_brain.nii')
        # hpf_img_file=utils.save_qc_png(hpf_total, hpf_img)
        # lpf_img = os.path.join(load_directory, 'lpf_brain.nii')
        # lpf_img_file=utils.save_qc_png(lpf_total, lpf_img)
        # dff_img = os.path.join(load_directory, 'dff_brain.nii')
        # dff_img_file=utils.save_qc_png(dff, dff_img)
        # printlog("Raw data QC figure saved in {}{}{}".format(hpf_img_file, lpf_img_file, dff_img_file))
    
        #save dff data
        utils.save_h5_chunks(save_file, dff, stepsize=stepsize)
    printlog("dff done. Data saved in {}".format(save_file))
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

