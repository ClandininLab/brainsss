## take moco h5py file and run zscore on it and output another h5py file
##currently adding the zscore data to the appropriate h5 file as a key called 'zscore'
## this is currently set to run each volume independently

import os
import sys
import numpy as np
import argparse
import subprocess
import json
from time import time
import nibabel as nib
import brainsss
import h5py
import ants

def main(args):

    logfile = args['logfile']
    directory = args['directory'] # full fly path 
    file_names = args['file_names'] ## should be MOCO_ch1.h5 and MOCO_ch2.h5 as specified in vol_main.py
    save_path = args['save_path']
    # smooth = args['smooth']
    # colors = args['colors']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')
    
    #can change the filenames to inputed files later and check if ch1 or ch2
#     ch1_filepath = os.path.join(save_path, 'MOCO_ch1.h5')
#     ch2_filepath = os.path.join(save_path, 'MOCO_ch2.h5')    
    
    #note if savepath is ever not the directory for moco then this will not find the files
    ch1_filepath = None
    ch2_filepath = None
    for name in file_names:
      if 'ch1' in name:
        ch1_filepath = os.path.join(directory, name)
      elif 'ch2' in name:
        ch2_filepath = os.path.join(directory, name)
      else:
        printlog('No file with ch1 or ch2 in it')
    
    
    #open moco file for ch2 (add ch1 later if needed)
    with h5py.File(ch2_filepath, 'a') as hf:   #if want to add zscore to theis file as a new key need to change to 'a' to read+write
        data_ch2 = hf['data']  #I believe this syntax shouldn't load the whole thing in memory
        #get the dimension of the data
        dims = np.shape(data_ch2)
        
        #make file to save zscore data to (this will error if it is run more than once and attempts to make the file again--could check to see if key exists to make it more robust later)
        ##I had it make a new key in the existing file so I didn't have to mess with having multiple h5 files open at once
        zscore_ch2 = hf.create_dataset('zscore', (*dims[:3],0), maxshape=(*dims[:3],None), dtype='float32')
        
        #find meanbrain 
        for i in range(dims[-1]):  #dims[-1] gives number of timepoints => number of volumes
            meanbrain += data_ch2[:,:,:,i]
        meanbrain = meanbrain/dims[-1]
        
        #find std
        total = 0
        for i in range(dims[-1]):
            s = (data_ch2[:,:,:,i] - meanbrain)**2
            total = s + total
        final_std = np.sqrt(total/len(data_ch2[-1]))


        #calculate zscore
        for i in range(dims[-1]):
            each_zscore = (data_ch2[:,:,:,i] - meanbrain)/final_std

            #save zscore
            # Increase hdf5 size by one brain volume
            current_num_vol = hf['zscore'].shape[-1] # this is the last axis, which is time
            new_num_vol = current_num_vol + 1 # will want one more volume
            hf['zscore'].resize(new_num_vol,axis=3) # increase size by one volume

            # Append to hdf5 file
            hf['zscore'][...,-1] = each_zscore
        

    
