import os
import sys
import numpy as np
import brainsss.brain_utils as brain_utils
import brainsss.utils as utils
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
    save_file_h = os.path.join(save_directory, brain_file.split('.')[0] + '_hpf.h5')
    save_file_l = os.path.join(save_directory, brain_file.split('.')[0] + '_lpf.h5')

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ####################
    ### Butterworth ###
    ###################

    printlog("Beginning highpass filter")
    with h5py.File(full_load_path, 'r') as hf:
        brain = hf['data']
        dims = np.shape(brain)
        stepsize=100
        printlog('RAM memory used::{}'.format(psutil.virtual_memory()[2]))
        printlog('RAM Used (GB)::{}'.format(psutil.virtual_memory()[3]/1000000000))

        printlog("Data shape is {}".format(dims))
        
        #filter requirements
        order = 2
        fs = 1.8 #sample rate, Hz
        cutoff =0.01 #desired cutoff frequency of the filter, Hz

        #create high pass filter data
        hpf_total = np.zeros_like(brain)
        steps = list(range(0,dims[-1],stepsize))
        printlog('RAM memory used::{}'.format(psutil.virtual_memory()[2]))
        printlog('RAM Used (GB)::{}'.format(psutil.virtual_memory()[3]/1000000000))
        steps.append(dims[-1])
        printlog('RAM memory used::{}'.format(psutil.virtual_memory()[2]))
        printlog('RAM Used (GB)::{}'.format(psutil.virtual_memory()[3]/1000000000))
        # for z in range(dims[-2]):
        #     printlog("z is {}".format(z))
        #     for chunk in steps:
        #         cs=chunk
        #         ce=chunk+stepsize
        #         if ce<=steps[-1]:
        #             hpf_warps = brain_utils.apply_butter_highpass(brain[...,cs:ce], z, cutoff, order, fs)
        #             hpf_total[...,z,cs:ce]=hpf_warps
        for z in range(dims[-2]):
            printlog('RAM memory used::{}'.format(psutil.virtual_memory()[2]))
            printlog('RAM Used (GB)::{}'.format(psutil.virtual_memory()[3]/1000000000))
            hpf_warps = brain_utils.apply_butter_highpass(brain, z, cutoff, order, fs)
            # printlog('RAM memory used::{}'.format(psutil.virtual_memory()[2]))
            # printlog('RAM Used (GB)::{}'.format(psutil.virtual_memory()[3]/1000000000))
            hpf_total[...,z,:]=hpf_warps
        hpf_total = np.array(hpf_total)
        dims_hpfw = np.shape(hpf_total)
        printlog(f"High Pass Filter Data shape is {dims_hpfw}")
        
        #subtract the high pass filter data from the blurred data to get low pass filter data as f nought
        lpf_total = brain-hpf_total
        # printlog('RAM memory used::{}'.format(psutil.virtual_memory()[2]))
        # printlog('RAM Used (GB)::{}'.format(psutil.virtual_memory()[3]/1000000000))
        del brain
        with h5py.File(save_file_h, "w") as data_file:
            data_file.create_dataset("hpf", data=hpf_total.astype('float32'))
            data_file.create_dataset("lpf", data=lpf_total.astype('float32'))
        # utils.save_h5_chunks(save_file_h, hpf_total, stepsize=stepsize)
        # utils.save_h5_chunks(save_file_l, lpf_total, stepsize=stepsize)
        # printlog('RAM memory used::{}'.format(psutil.virtual_memory()[2]))
        # printlog('RAM Used (GB)::{}'.format(psutil.virtual_memory()[3]/1000000000))
        printlog("Butter high pass done")

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))