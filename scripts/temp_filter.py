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
    load_directory = args['load_directory']
    save_directory = args['save_directory']
    brain_file = args['brain_file']
    timestamp_file = args['timestamp_file']
    later_path = args['later_path']
    event= args['event']
    redo = args['redo']
    cc = args['cc']
    stepsize = 100

    brain_load_path = os.path.join(load_directory, brain_file)
    ts_load_path = os.path.join(fly_directory, timestamp_file)

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
            filter_load_path=os.path.join(save_directory, f"filter_needs_{cc}_{behavior}.h5")
            ts_rel_load_path=os.path.join(save_directory, f"ts_rel_odd_mask_{cc}_{behavior}.h5")
            save_file = os.path.join(save_directory, brain_file.split('.')[0] + '_filtered_' + f'{behavior}_{event}.h5')
        else:
            filter_load_path=os.path.join(save_directory, f"filter_needs_{cc}_{behavior}.h5")
            ts_rel_load_path=os.path.join(save_directory, f"ts_rel_odd_mask_{cc}_{behavior}.h5")
            save_file = os.path.join(save_directory, brain_file.split('.')[0] + '_filtered_' + f'{behavior}.h5')
        if os.path.exists(save_file)==False or redo:
            #load brain
            with h5py.File(brain_load_path, 'r') as hf, \
                h5py.File(ts_load_path, 'r') as tf, \
                h5py.File(ts_rel_load_path, 'r') as of, \
                h5py.File(filter_load_path, 'r') as ff:
                    
                brain_all = hf['data']
                ts_all = tf['data']
                loom_all = ff['loom_starts'] 
                bin_shape = ff['bin_shape']
                odd_mask = of['odd_mask']   
                ts_rel = of['ts_rel']     
                        
                # loop through sections of the matricies
                dims=np.shape(brain_all)
                printlog(F"Brain data shape is {dims}")
                
                T=(ts_all[0,0,0,1]-ts_all[0,0,0,0])/1000
                fs=1/T #sample rate, Hz
                max_len=int((((bin_shape[1]-bin_shape[0])/1000)*fs)*np.shape(loom_all)[0])+100
                printlog(F"Max length of filtered data is {max_len}")

                nx, ny, nz, nt = brain_all.shape
                # n_voxels = nx * ny * nz

                within_bin_brain_np = np.full((nx, ny, nz, max_len), np.nan)
                within_bin_ts_rel_np = np.full((nx, ny, nz, max_len), np.nan)

                #### Loop over z planes (io access is done nz times!!)
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
                
                printlog(f"Temporal filtering for {behavior} is done. Data saved in {save_file}")
                # Delete variables to free up memory
                del brain_all, ts_all, loom_all, bin_shape, odd_mask, ts_rel, within_bin_brain_np, within_bin_ts_rel_np
                del dims, T, fs, max_len, nx, ny, nz, nt, plane, plane_ts_rel, within_bin_vox, within_bin_vox_ts_rel, sorted_indices
                
                # Manually invoke the garbage collector
                gc.collect() 
                    
                
        else:
            printlog(f"Filtered data for {behavior} already exists. Skipping...")
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

