import os
import sys
import brainsss.fictrac as fictrac
from scipy.ndimage import gaussian_filter1d
import numpy as np
import json
import brainsss
import h5py
import ants
import psutil
import gc

def main(args):
    later_directory = args['later_directory']
    ch_num = args['ch_num'] 
    
    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ###########
    ### STA ###
    ###########

    printlog("Beginning giant STA")
    behaviors = ['inc', 'dec', 'flat', 'total']
    
    
    for behavior in behaviors:
        behave_dir = os.path.join(later_directory, behavior)
        range_start=-500; range_end=1900; steps=100
        STA=[]  

        for file in os.listdir(behave_dir):
                load_path = os.path.join(behave_dir,file)
                print(load_path)
                temp=[]
                with h5py.File(load_path, 'r+') as hf:    
                        ts = hf['time_stamps'][:]
                        brain = hf['brain']
                        dimst = np.shape(ts)
                        dims = np.shape(brain)
                        printlog(f'Brain shape: {dims}, time stamp shape: {dimst}')
                        for i in range(range_start, range_end, steps):
                            end = i + steps if i + steps < range_end else range_end
                            mask = (ts > i) & (ts < end)
                            result = np.nanmean(np.where(mask, brain, np.nan),axis=-1)
                            temp.append(result)
                printlog(f'Temp shape is {np.shape(temp)}')
                STA.append(temp)
                printlog(f'STA is {np.shape(STA)}')
        STA=np.asarray(np.nanmean(STA, axis=0))
    
        save_file= os.path.join(behave_dir, 'STA_total.h5')
        printlog(f'Saving STA to {save_file}')
        with h5py.File(save_file, "w") as data_file:
                data_file.create_dataset("data", data=STA.astype('float32'))
        
        printlog(f"STA for {behavior} done. Data saved in {save_file}")
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

