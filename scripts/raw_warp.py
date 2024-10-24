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



def main(args):
    fly_directory = args['fly_directory']
    load_directory = args['load_directory']
    save_directory = args['save_directory']
    brain_file = args['brain_file']
    stepsize = 100

    full_load_path = os.path.join(load_directory, brain_file)
    save_file = os.path.join(save_directory, brain_file.split('.')[0] + '_warp.h5')

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ##############
    ### ZSCORE ###
    ##############

    printlog("Beginning RAW WARP")
    with h5py.File(full_load_path, 'r') as hf:
        data = hf['data'][:]
        dims = np.shape(data)

        printlog("Data shape is {}".format(dims))

        
        #Warp in chunks so we don't run out of memory, this is creating the stepsize of chunks
        stepsize = 100
        steps = list(range(0,dims[-1],stepsize))
        steps.append(dims[-1])

        #Load mean brain
        fixed = brainsss.load_fda_meanbrain()
        
        #Warp the brain
        warped = warp_raw_brain(data=data, steps=steps, fixed=fixed, func_path=fly_directory)
        printlog("Warped brain shape is {}".format(np.shape(warped)))
    
    #Timestamps need to be warped as well, load them here    
    timestamps = brainsss.load_timestamps(os.path.join(fly_directory,'func_0', 'imaging'))    
    
    #Get the values of the differences between each timestamp to create a relative timestamp matrix
    relative=timestamps[0]-timestamps[0][0]
    
    #Create a list of the relative timestamps
    vals=[]
    for ts in range(np.shape(timestamps)[0]):
        val=timestamps[ts]-relative
        vals.append(val[0])
    
    #Create a matrix of the relative timestamps for each frame, should be same shape as the data
    x=dims[0]
    y=dims[1]
    ts_xl=[]
    for val in relative:
        fframe=np.zeros((x,y))
        fframe.fill(val)
        ts_xl.append(fframe)
    ts_xl=np.array(ts_xl)
    ts_xl=np.moveaxis(ts_xl,0,-1)
    printlog("Timestamp shape is {}".format(np.shape(ts_xl)))
    
    #Warp this extra large timestamp matrix
    warped_ts = warp_ts(data=ts_xl, fixed=fixed, func_path=fly_directory)
    
    #Add the relative timestamps to the warped timestamps to get the absolute timestamps
    total_ts=[]
    for i in range(np.shape(vals)[0]):
        temp_ts=warped_ts+vals[i]
    #     print(np.shape(temp_ts))
        total_ts.append(temp_ts)
    total_ts=np.array(total_ts)
    total_ts=np.moveaxis(total_ts,0,-1)
    printlog("Warped brain shape is {}".format(np.shape(total_ts)))
    
    #Save the warped brain and timestamps
    with h5py.File(save_file, "w") as data_file:
        data_file.create_dataset("data", data=warped.astype('float32'))
        data_file.create_dataset("timestamps", data=total_ts.astype('float32'))
    
    def apply_ants_trans(array, moving_resolution, fixed, transforms):
        if array.ndim>3:
            warpst=[]
            for i in range(np.shape(array)[-1]):
                moving = ants.from_numpy(array[...,i])
                moving.set_spacing(moving_resolution)
                moco = ants.apply_transforms(fixed, moving, transforms)
                warped = moco.numpy()
                warpst.append(warped)
        else:
            moving = ants.from_numpy(array)
            moving.set_spacing(moving_resolution)
            moco = ants.apply_transforms(fixed, moving, transforms, interpolator='nearestNeighbor')
            warpst = moco.numpy()
        return warpst

    def warp_raw_brain(data, steps, fixed, func_path):
        moving_resolution = (2.611, 2.611, 5)
        ###########################
        ### Organize Transforms ###
        ###########################
        warp_directory = os.path.join(func_path,'warp')
        warp_sub_dir = 'func-to-anat_fwdtransforms_2umiso'
        affine_file = os.listdir(os.path.join(warp_directory, warp_sub_dir))[0]
        affine_path = os.path.join(warp_directory, warp_sub_dir, affine_file)
        warp_sub_dir = 'anat-to-meanbrain_fwdtransforms_2umiso'
        syn_files = os.listdir(os.path.join(warp_directory, warp_sub_dir))
        syn_linear_path = os.path.join(warp_directory, warp_sub_dir, [x for x in syn_files if '.mat' in x][0])
        syn_nonlinear_path = os.path.join(warp_directory, warp_sub_dir, [x for x in syn_files if '.nii.gz' in x][0])
        ####transforms = [affine_path, syn_linear_path, syn_nonlinear_path]
        transforms = [syn_nonlinear_path, syn_linear_path, affine_path] ### INVERTED ORDER ON 20220503!!!!
        #ANTS DOCS ARE SHIT. THIS IS PROBABLY CORRECT, AT LEAST IT NOW WORKS FOR THE FLY(134) THAT WAS FAILING

        warp_dims=[314, 146, 91, np.shape(data)[-1]]#this probs shouldn't be hard coded but idk what else to do here
        warps = np.zeros(warp_dims)
        ### Warp timeponts
    #     with h5py.File(save_dir, 'w') as f:
    #             dset = f.create_dataset('warps', warp_dims, dtype='float16', chunks=True) 
                
        for chunk_num in range(len(steps)):
    #                 t0 = time()
            if chunk_num + 1 <= len(steps)-1:
                print(chunk_num)
                chunkstart = steps[chunk_num]
                chunkend = steps[chunk_num + 1]
                chunk = np.array(data[:,:,:,chunkstart:chunkend]).astype(np.float)
                warps_chunk = apply_ants_trans(chunk, moving_resolution, fixed, transforms)
    #             print(np.shape(warps_chunk))
                warps_chunk = np.moveaxis(np.array(warps_chunk),0,-1)
                warps[..., chunkstart:chunkend] = np.nan_to_num(warps_chunk)
    #                     print(F"vol: {chunkstart} to {chunkend} time: {time()-t0}")
        return warps
    def warp_ts(data, fixed, func_path):
        moving_resolution = (2.611, 2.611, 5)
        ###########################
        ### Organize Transforms ###
        ###########################
        warp_directory = os.path.join(func_path,'warp')
        warp_sub_dir = 'func-to-anat_fwdtransforms_2umiso'
        affine_file = os.listdir(os.path.join(warp_directory, warp_sub_dir))[0]
        affine_path = os.path.join(warp_directory, warp_sub_dir, affine_file)
        warp_sub_dir = 'anat-to-meanbrain_fwdtransforms_2umiso'
        syn_files = os.listdir(os.path.join(warp_directory, warp_sub_dir))
        syn_linear_path = os.path.join(warp_directory, warp_sub_dir, [x for x in syn_files if '.mat' in x][0])
        syn_nonlinear_path = os.path.join(warp_directory, warp_sub_dir, [x for x in syn_files if '.nii.gz' in x][0])
        ####transforms = [affine_path, syn_linear_path, syn_nonlinear_path]
        transforms = [syn_nonlinear_path, syn_linear_path, affine_path] ### INVERTED ORDER ON 20220503!!!!
        #ANTS DOCS ARE SHIT. THIS IS PROBABLY CORRECT, AT LEAST IT NOW WORKS FOR THE FLY(134) THAT WAS FAILING
                
        data = np.array(data).astype(np.float)
        warps = apply_ants_trans(data, moving_resolution, fixed, transforms)
    #     warps = np.nan_to_num(data_warp)
        return warps
if __name__ == '__main__':
    main(json.loads(sys.argv[1]))

