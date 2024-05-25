import os
import sys
import numpy as np
import json
import brainsss
import h5py
import datetime
from time import time
from scipy.signal import butter, filtfilt, freqz

def main(args):
    
    load_directory = args['load_directory']
    save_directory = args['save_directory']
    brain_file = args['brain_file']

    full_load_path = os.path.join(load_directory, brain_file)
    save_file = os.path.join(save_directory, brain_file.split('.')[0] + '_butter_highpass.h5')

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    
    def butter_highpass(cutoff, fs, order=5):
        return butter(order, cutoff, fs=fs, btype='high', analog=False)

    def butter_highpass_filter(data, cutoff, fs, order=5):
        b, a = butter_highpass(cutoff, fs, order=order)
        y = filtfilt(b, a, data)
        return y
    
    def apply_butter_highpass(data, z, cutoff, order, fs):
        # Get the filter coefficients so we can check its frequency response.
        b, a = butter_highpass(cutoff, fs, order)
        hpf_data = butter_highpass_filter(data[:,:,z, :], cutoff, fs, order)
        return hpf_data
    
    #################
    ### HIGH PASS ###
    #################

    printlog("Beginning butter high pass")
    
    #filter requirements 
    order = 2     
    fs = 1.8      # sample rate, Hz
    cutoff = 0.01  # desired cutoff frequency of the filter, Hz
    
    with h5py.File(full_load_path, 'r') as hf:
        data = hf['data'][:] 
        dims = np.shape(data)
        printlog("Data shape is {}".format(dims))
               
        hpf_total = []
        for z in range(dims[-2]):
            hpf_data = apply_butter_highpass(data, z, cutoff, order, fs)
            hpf_total.append(hpf_data)
        hpf_total = np.array(hpf_total)
        hpf_total = np.transpose(hpf_total, (1,2,0,3))
        dims_hpf = np.shape(hpf_total)
        printlog("High Pass Filter Data shape is {}".format(dims_hpf))
            
        ### Save ###
        
        #save numpy matrix as .h5 file
        with h5py.File(save_file, 'w') as hf:
            hf.create_dataset('data', data=hpf_total, dtype='float32')

    printlog("Butter high pass done")

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))