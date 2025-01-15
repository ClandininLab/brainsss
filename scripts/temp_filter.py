import os
import sys
import brainsss.fictrac as fictrac
import numpy as np
import json
import brainsss
import h5py
import ants
import psutil

def main(args):
    fly_directory = args['fly_directory']
    load_directory = args['load_directory']
    save_directory = args['save_directory']
    brain_file = args['brain_file']
    timestamp_file = args['timestamp_file']
    filter_file = args['filter_file']
    stepsize = 100

    filter_load_path=os.path.join(save_directory, filter_file)
    brain_load_path = os.path.join(load_directory, brain_file)
    ts_load_path = os.path.join(fly_directory, timestamp_file)
    save_file = os.path.join(save_directory, brain_file.split('.')[0] + '_filtered.h5')

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    #######################
    ### TEMPORAL FILTER ###
    #######################

    printlog("Beginning temporal filter")
   
    #load brain
    with h5py.File(brain_load_path, 'r') as hf, \
        h5py.File(ts_load_path, 'r') as tf, \
        h5py.File(filter_load_path, 'r') as ff:
            
        brain_all = hf['data']
        ts_all = tf['data']
        bin_all = ff['bins']
        loom_all = ff['loom_starts'] 
        bin_shape = ff['bin_shape']    
                
        # loop through sections of the matricies
        dims=np.shape(brain_all)
        printlog(F"Brain data shape is {dims}")
        
        T=(ts[0,0,0,1]-ts[0,0,0,0])/1000
        fs=1/T #sample rate, Hz
        max_len=int((((bin_shape[1]-bin_shape[0])/1000)*fs)*np.shape(loom_all)[0])+100
        filter_dims=np.append(np.shape(ts_all)[:-1], max_len)
        brain_final=np.full(filter_dims, np.nan)
        ts_final=np.full(filter_dims, np.nan) #create nan arrays of the biggest possible number of voxel collections 
        
        chunk_size = 500  # Adjust this based on your memory constraints
        t_start=0
        for i in range(0, dims[-1], chunk_size):
            if t_start<np.shape(brain_final)[-1]:
                end = i + chunk_size if i + chunk_size < dims[-1] else dims[-1]
                printlog(F"vol: {i} to {end}")
                brain = brain_all[...,i:end]
                ts = ts_all[...,i:end]
                bin_idx = bin_all[...,i:end]
                bool_starts=(loom_all>=(np.min(ts))) & (loom_all<=(np.max(ts)))
                starts_loom_ms=np.array(loom_all[bool_starts])
        
                # Loop through each loom-containing bin_idx and subtract starts_loom_ms
                for i in range(len(starts_loom_ms)):
                    # subtract loom onset time for corresponding timestamps
                    ts[bin_idx == i*2 + 1] -= starts_loom_ms[i]

                # boolean mask of where bin_idx is odd
                odd_mask = bin_idx % 2 == 1

                # Create flattened (xyz X time) 
                n_timesteps = ts.shape[-1]
                ts_rel_flat = ts.reshape(-1, n_timesteps)
                brain_flat = brain.reshape(-1, n_timesteps)
                odd_mask_flat = odd_mask.reshape(-1, n_timesteps)

                # Collect ts_rel and brain elements that fall within loom window / bin
                within_bin_brain_flat  = [brain_flat[xyz][odd_mask_flat[xyz]] for xyz in range(brain_flat.shape[0])]
                within_bin_ts_rel_flat = [ts_rel_flat[xyz][odd_mask_flat[xyz]] for xyz in range(ts_rel_flat.shape[0])]

                # Find the maximum length of the sublists
                max_len = max(len(sublist) for sublist in within_bin_brain_flat)
                temp_len = max_len+t_start #for populating the right temporal position of the final array
                
                # Create a 2D NumPy array filled with np.nan, with the appropriate shape
                n_voxels = len(within_bin_brain_flat)
                within_bin_brain_flat_np = np.full((n_voxels, max_len), np.nan)
                within_bin_ts_rel_flat_np = np.full((n_voxels, max_len), np.nan)

                # Populate the array with the values from the original list of lists
                for i, (brain_sl, ts_rel_sl) in enumerate(zip(within_bin_brain_flat, within_bin_ts_rel_flat)):
                    within_bin_brain_flat_np[i, :len(brain_sl)] = brain_sl
                    within_bin_ts_rel_flat_np[i, :len(ts_rel_sl)] = ts_rel_sl

                # unflatten
                static_brain_shape = brain.shape[:-1]
                within_bin_brain_np = within_bin_brain_flat_np.reshape(*static_brain_shape, max_len)
                brain_size=np.shape(within_bin_brain_np)
                within_bin_ts_rel_np = within_bin_ts_rel_flat_np.reshape(*static_brain_shape, max_len) 
                ts_size=np.shape(within_bin_brain_np)
                printlog(f"Ts shape {ts_size}. Brain shape {brain_size}")   
                brain_final[...,t_start:temp_len]=within_bin_brain_np
                ts_final[...,t_start:temp_len]=within_bin_ts_rel_np
                t_start+=max_len
        brain_final = np.array(brain_final)
        ts_final=np.array(ts_final)
        brain_shape=np.shape(brain_final)
        ts_shape=np.shape(ts_final)
        printlog(f"Temporal filtered data shape is {brain_shape} and timestamp shape is {ts_shape}")
        
        with h5py.File(save_file, "w") as data_file:
                data_file.create_dataset("brain", data=brain_final.astype('float32'))
                data_file.create_dataset("time_stamps", data=ts_final.astype('float32'))
            
        printlog(f"Temporal filtering done. Data saved in {save_file}")
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

