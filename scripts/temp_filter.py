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
        
        T=(ts_all[0,0,0,1]-ts_all[0,0,0,0])/1000
        fs=1/T #sample rate, Hz
        max_len=int((((bin_shape[1]-bin_shape[0])/1000)*fs)*np.shape(loom_all)[0])+100
        # filter_dims=np.append(np.shape(ts_all)[:-1], max_len)
        # brain_final=np.full(filter_dims, np.nan)
        # ts_final=np.full(filter_dims, np.nan) #create nan arrays of the biggest possible number of voxel collections 

        #### Loop over z planes (io access is done nz times!!)

        ts_rel=ts_all[:,:,:,:]
        for i in range(len(loom_all)):
            # subtract loom onset time for corresponding timestamps
            ts_rel[bin_all == i*2 + 1] -= loom_all[i]

        # boolean mask of where bin_idx is odd
        odd_mask = bin_all % 2 == 1

        nx, ny, nz, nt = brain_all.shape
        # n_voxels = nx * ny * nz

        within_bin_brain_np = np.full((nx, ny, nz, max_len), np.nan)
        within_bin_ts_rel_np = np.full((nx, ny, nz, max_len), np.nan)

        for z in (range(nz)):

            # Read in z plane
            plane = brain_all[:,:,z,:]
            plane_ts_rel = ts_rel[:,:,z,:]

            for x in range(nx):
                for y in range(ny):
                    within_bin_vox = plane[x, y, odd_mask[x,y,z,:]]
                    within_bin_vox_ts_rel = plane_ts_rel[x, y, odd_mask[x,y,z,:]]
                    
                    # Get the sorted indices of the timestamp array and sort both arrays using the sorted indices
                    sorted_indices = np.argsort(within_bin_vox_ts_rel)
                    within_bin_vox = within_bin_vox[sorted_indices]
                    within_bin_vox_ts_rel = within_bin_vox_ts_rel[sorted_indices]

                    # populate the output array
                    within_bin_brain_np[x,y,z,:len(within_bin_vox)] = within_bin_vox
                    within_bin_ts_rel_np[x,y,z,:len(within_bin_vox)] = within_bin_vox_ts_rel

        
        # brain_final = np.array(brain_final)
        # ts_final=np.array(ts_final)
        brain_shape=np.shape(within_bin_brain_np)
        ts_shape=np.shape(within_bin_ts_rel_np)
        printlog(f"Temporal filtered data shape is {brain_shape} and timestamp shape is {ts_shape}")
        
        with h5py.File(save_file, "w") as data_file:
                data_file.create_dataset("brain", data=within_bin_brain_np.astype('float32'))
                data_file.create_dataset("time_stamps", data=within_bin_ts_rel_np.astype('float32'))
            
        printlog(f"Temporal filtering done. Data saved in {save_file}")
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

