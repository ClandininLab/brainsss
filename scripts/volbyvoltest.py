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
    # directory = args['directory'] # full fly func path
    # smooth = args['smooth']
    # colors = args['colors']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    # Get brain shape
    brain_file = '/oak/stanford/groups/trc/data/Ashley2/imports/20210802/fly1_40s-011/ch2_stitched.nii'
    img = nib.load(brain_file) # this loads a proxy
    brain_dims = img.header.get_data_shape()

    # calculate the meanbrain, which will be fixed in moco
    # meanbrain = np.zeros(brain_dims[:3])
    # for i in range(brain_dims[-1]):
    #     meanbrain += img.dataobj[...,i]
    # meanbrain = meanbrain/brain_dims[-1] # divide by number of volumes
    # fixed = ants.from_numpy(np.asarray(meanbrain, dtype='float32'))
    # printlog('meanbrain DONE')

    # Make empty hdf5 file to append processed volumes to with matching shape
    save_file = '/oak/stanford/groups/trc/data/Brezovec/20220207_test.h5'
    with h5py.File(save_file, 'w') as f:
        dset = f.create_dataset('data', (*brain_dims[:3],0), maxshape=(*brain_dims[:3],None), dtype='float32')
    printlog('created empty hdf5 file')

    # loop over all brain vols, motion correcting each and append to growing hdf5 file on disk
    printlog('moco vol by vol')
    for i in range(brain_dims[-1]):
        t0 = time()
        # Load a single brain volume
        vol = img.dataobj[...,i]
        
        # ### Process vol (moco, zscore, etc) ###
        # # Make ants image
        # moving = ants.from_numpy(np.asarray(vol, dtype='float32'))

        # # Motion correct
        # moco = ants.registration(fixed,moving,type_of_transform='SyN')
        # moco_out = moco['warpedmovout'].numpy()

        # Append to hdf5 file
        with h5py.File(save_file, 'a') as f:

            # Increase hdf5 size by one brain volume
            current_num_vol = f['data'].shape[-1] # this is the last axis, which is time
            new_num_vol = current_num_vol + 1 # will want one more volume
            f['data'].resize(new_num_vol,axis=3) # increase size by one volume
            
            # Append to hdf5 file
            f['data'][...,-1] = vol #moco_out
        printlog(F'vol: {i}, time: {time()-t0}')

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))