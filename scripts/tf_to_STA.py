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
import pickle

def main(args):
    later_path = args['later_path']
    temp_dir=args['temp_directory']
    cc = args['ch_num'] 
    event = args['event']
    flies = args['fly_num']
    
    
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
    if event != None:
        event_times_path = os.path.join(later_path, f'{event}_event_times_split_dic.pkl')
    else:
        event_times_path = os.path.join(later_path, 'event_times_split_dic.pkl')
    with open(event_times_path, 'rb') as file:
        event_times_struct = pickle.load(file)
        f=list(event_times_struct.keys())[0]
        behaviors=list(event_times_struct[f].keys())
        printlog(f"Found behaviors: {behaviors}")
    
    
    range_start=-500; range_end=1900; steps=100
    printlog(f"Flies: {flies}")
    num_flies = len(flies)
    
    for behavior in behaviors:
        printlog(f"\n=======================================")
        printlog(f'Processing behavior: {behavior}')
        behave_dir = os.path.join(temp_dir, behavior)
        printlog(f'Processing directory {behave_dir}')
        STA = []
        tf_files = [] 
        for file in os.listdir(behave_dir):
            if event!=None:
                if '_tf_' in file and f'_{cc}' in file and behavior in file and event in file:
                    tf_files.append(file)
                    save_file= os.path.join(behave_dir, f'STA_{num_flies}flies_{cc}_{behavior}_{steps}_{event}_.h5')
            elif '_tf_' in file and f'_{cc}' in file and behavior in file and f'_{cc}_' not in file:
                    tf_files.append(file)
                    save_file= os.path.join(behave_dir, f'STA_{num_flies}flies_{cc}_{behavior}_{steps}.h5')
        for file in tf_files:
            fly_val=int(file.split("_")[0])
            if fly_val in flies:
                load_path = os.path.join(behave_dir,file)
                printlog(f"being processes {load_path}")
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
            else:
                printlog(f'Fly {fly_val} not in {flies}')
        STA=np.asarray(np.nanmean(STA, axis=0))
    
        # printlog(f'Saving STA to {save_file}')
        with h5py.File(save_file, "w") as data_file:
                data_file.create_dataset("data", data=STA.astype('float32'))
        
        printlog(f"STA for {behavior} done. Data saved in {save_file}")
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

