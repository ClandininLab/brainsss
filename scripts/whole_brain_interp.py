import os
import sys
import brainsss.fictrac as fictrac
import numpy as np
import json
import brainsss
import h5py
import ants
import psutil

def interp_wholebrain(brain,ts, range_start, range_end, steps):
    nx, ny, nz, nt = brain.shape
    # n_voxels = nx * ny * nz

    t_interp_full = np.full((nx, ny, nz, steps), np.nan)
    y_interp_full = np.full((nx, ny, nz, steps), np.nan)
    
    #### Loop over z planes (io access is done nz times!!)
    for z in (range(nz)):
    
        # Read in z plane
        plane = brain[:,:,z,:]#signal
        plane_ts = ts[:,:,z,:]#time
    
        for x in range(nx):
            for y in range(ny):
                brain_vox = plane[x, y, :]
                ts_vox = plane_ts[x, y, :]
#                 print(f"time shape: {np.shape(ts_vox)}, signal shape: {np.shape(brain_vox)}")
                sort_idx = np.argsort(ts_vox)
                t_sorted = ts_vox[sort_idx]
                y_sorted = brain_vox[sort_idx]
   
                t_interp = np.linspace(range_start, range_end, steps) #these are the times in ms that we will resample everything to
    
                f_interp = scipy.interpolate.interp1d(t_sorted,y_sorted, fill_value='extrapolate') #can look at the docstring for interp1d
                y_interp = f_interp(t_interp) # these will be y values interpolated to the new standardized times
    
                y_interp_full[x,y,z,:] = y_interp
                t_interp_full[x,y,z,:] = t_interp
    return y_interp_full, t_interp_full

def main(args):
    load_directory = args['load_directory']
    save_directory = args['save_directory']
    tf_file = args['tf_file']

    tf_load_path = os.path.join(load_directory, tf_file)
    save_file = os.path.join(save_directory, 'whole_brain_interp.h5')

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ##############
    ### Interp ###
    ##############

    printlog("Beginning temporal filter")
   
    #load brain
    with h5py.File(tf_load_path, 'r') as hf:
            
        brain = hf['brain'][:]
        ts = hf['time_stamps'][:]
        dimsb = np.shape(brain)
        dimst = np.shape(ts)
        printlog(f"Brain shape is {dimsb}, time stamp shape is {dimst}")
        
        
        stepsize = 100  

        range_start=int(np.nanmin(ts))
        range_end=int(np.nanmax(ts))+1
        
        y_interp_full, t_interp_full=interp_wholebrain(brain, ts,range_start, range_end, steps=stepsize)
        
        brain_shape=np.shape(y_interp_full)
        ts_shape=np.shape(t_interp_full)
        printlog(f"Temporal filtered data shape is {brain_shape} and timestamp shape is {ts_shape}")
        
        with h5py.File(save_file, "w") as data_file:
                data_file.create_dataset("brain", data=y_interp_full.astype('float32'))
                data_file.create_dataset("time_stamps", data=t_interp_full.astype('float32'))
            
        printlog(f"Temporal filtering done. Data saved in {save_file}")
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

