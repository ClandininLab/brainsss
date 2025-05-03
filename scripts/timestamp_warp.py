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
from brainsss.utils import save_h5_chunks

def main(args):
    fly_directory = args['fly_directory']
    load_directory = args['load_directory']
    save_directory = args['save_directory']
    brain_file = args['brain_file']
    stepsize = 100

    # full_load_path = os.path.join(load_directory, brain_file)
    save_file = os.path.join(save_directory, brain_file.split('.')[0] + '_warp.h5')

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ######################
    ### TIMESTAMP WARP ###
    ######################

    printlog("Beginning TIMESTAMP WARP")
    
    #Timestamps need to be warped as well, load them here    
    if save_file not in os.listdir(save_directory):
        timestamps = brainsss.load_timestamps(load_directory)    
        printlog("Timestamp shape is {}".format(np.shape(timestamps)))
        
        #Load mean brain
        fixed = brainsss.load_fda_meanbrain()
        
        #Get the values of the differences between each timestamp to create a relative timestamp matrix
        relative=timestamps[0]-timestamps[0][0]
        
        #Create a list of the relative timestamps
        vals=[]
        for ts in range(np.shape(timestamps)[0]):
            val=timestamps[ts]-relative
            vals.append(val[0])
        
        #Create a matrix of the relative timestamps for each frame, should be same shape as the data
        x=256 #I know I shouldn't hard code this but it seems a waste of mem to load the brain just to get this....
        y=128
        ts_xl=[]
        for val in relative:
            fframe=np.zeros((x,y))
            fframe.fill(val)
            ts_xl.append(fframe)
        ts_xl=np.array(ts_xl)
        ts_xl=np.moveaxis(ts_xl,0,-1)
        printlog("New timestamp shape is {}".format(np.shape(ts_xl)))
        
        #Warp this extra large timestamp matrix
        warped_ts = warp_raw(data=ts_xl, stepsize=None, fixed=fixed, func_path=fly_directory)
        
        #Add the relative timestamps to the warped timestamps to get the absolute timestamps
        total_ts=[]
        for i in range(np.shape(vals)[0]):
            temp_ts=warped_ts+vals[i]
        #     print(np.shape(temp_ts))
            total_ts.append(temp_ts)
        total_ts=np.array(total_ts)
        total_ts=np.moveaxis(total_ts,0,-1)
        printlog("Warped timestamp shape is {}".format(np.shape(total_ts)))
        
        with h5py.File(save_file, "w") as data_file:
                data_file.create_dataset("data", data=total_ts.astype('float32'))
    else:
        printlog("Warped timestamps already created")
    
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

