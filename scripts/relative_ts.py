import os
import sys
import brainsss.fictrac as fictrac
import numpy as np
import json
import brainsss
import h5py
import ants
import psutil
import gc
import pickle

def main(args):
    fly_directory = args['fly_directory']
    save_directory = args['save_directory']
    timestamp_file = args['timestamp_file']
    later_path = args['later_path']
    event= args['event']

    ts_load_path = os.path.join(fly_directory, timestamp_file)

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ###########################
    ### REL TIME & ODD MASK ###
    ###########################

    printlog("Beginning relative timestamp & odd mask creation")
    
    #Get behaviors
    if event != None:
        event_times_path = os.path.join(later_path, f'{event}_event_times_split_dic.pkl')
    else:
        event_times_path = os.path.join(later_path, 'event_times_split_dic.pkl')
    with open(event_times_path, 'rb') as file:
        event_times_struct = pickle.load(file)
        f=list(event_times_struct.keys())[0]
        behaviors=list(event_times_struct[f].keys())
            
            
    for behavior in behaviors:
        if event != None:
            save_name=f'ts_rel_odd_mask_{behavior}_{event}.h5'
            load_name=f'filter_needs_{behavior}_{event}.h5'
        else:
            save_name=f'ts_rel_odd_mask_{behavior}.h5'
            load_name=f'filter_needs_{behavior}.h5'
        if save_name not in os.listdir(save_directory):
            #load brain
            with h5py.File(ts_load_path, 'r') as tf, \
                h5py.File(os.path.join(save_directory, load_name), 'r') as ff:

                ts = tf['data'][:].astype('float32')
                bins = ff['bins'][:].astype('int32')
                looms = ff['loom_starts'][:].astype('float32')
            
            
                
                for i in range(len(looms)):
                    # subtract loom onset time for corresponding timestamps
                    ts[bins == i*2 + 1] -= looms[i]
                
                # Get the odd indices of the bin_idx array
                
                # boolean mask of where bin_idx is odd
                odd_mask = bins % 2 == 1

                ts_shape=np.shape(ts)
                om_shape=np.shape(odd_mask)
                
                printlog(f"Relative time shape is {ts_shape} and odd mask shape is {om_shape}")
                save_file = os.path.join(save_directory, f'ts_rel_odd_mask_{behavior}.h5')
                with h5py.File(save_file, "w") as data_file:
                        data_file.create_dataset("odd_mask", data=odd_mask.astype('bool'))
                        data_file.create_dataset("ts_rel", data=ts.astype('float32'))
                        
                printlog(f"Relative timestamps for {behavior} and odd mask creation done. Data saved in {save_file}")   
               
                # Delete variables to free up memory
                del ts, bins, looms, odd_mask, ts_shape, om_shape, save_file
                
                # Manually invoke the garbage collector
                gc.collect()
        else:
            printlog(f'{behavior} relative timestamps and odd mask already created')

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

