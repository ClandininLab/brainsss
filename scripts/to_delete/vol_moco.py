## this will run moco on each volume independently and save to help with memory issues
#may change to only create one hdf5 file in the future


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
    directory = args['directory'] # full fly path 
    file_names = args['file_names'] ## should be ch2_stitched.nii and ch1_stitched.nii 
    save_path = args['save_path']
    # smooth = args['smooth']
    # colors = args['colors']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')
    
    save_file_ch1 = os.path.join(save_path, 'MOCO_ch1.h5')
    save_file_ch2 = os.path.join(save_path, 'MOCO_ch2.h5')
#     save_file_ch1 = '/oak/stanford/groups/trc/data/Ashley2/moco_test/20220207_ch1.h5'
#     save_file_ch2 = '/oak/stanford/groups/trc/data/Ashley2/moco_test/20220207_ch2.h5'

    # Get brain shape
    #brain_file = '/oak/stanford/groups/trc/data/Ashley2/imports/20210802/fly1_40s-011/ch2_stitched.nii'
    ch1_brain_file = None
    ch2_brain_file = None
    for name in file_names:
      if 'ch1' in name:
        ch1_brain_file = os.path.join(directory, name)
      elif 'ch2' in name:
        ch2_brain_file = os.path.join(directory, name)
      else:
        printlog('No directory with ch1 or ch2 in it')
                 
    if ch1_brain_file is not None:
      ch1_img = nib.load(ch1_brain_file) # this loads a proxy
      brain_dims = ch1_img.header.get_data_shape()

      #calculate the meanbrain of channel 1, which will be fixed in moco
      printlog('meanbrain START...')
      meanbrain = np.zeros(brain_dims[:3])
      for i in range(brain_dims[-1]):
          meanbrain += ch1_img.dataobj[...,i]
      meanbrain = meanbrain/brain_dims[-1] # divide by number of volumes
      fixed = ants.from_numpy(np.asarray(meanbrain, dtype='float32'))
      printlog('meanbrain DONE')

      # Make empty hdf5 file to append processed volumes to with matching shape
      
      with h5py.File(save_file_ch1, 'w') as f_ch1:
          dset_ch1 = f_ch1.create_dataset('data', (*brain_dims[:3],0), maxshape=(*brain_dims[:3],None), dtype='float32')
      printlog('created empty hdf5 file ch1')
                 
      with h5py.File(save_file_ch2, 'w') as f_ch2:
          dset_ch2 = f_ch2.create_dataset('data', (*brain_dims[:3],0), maxshape=(*brain_dims[:3],None), dtype='float32')
      printlog('created empty hdf5 file ch2')

      # loop over all brain vols, motion correcting each and append to growing hdf5 file on disk
      printlog('moco vol by vol')
      for i in range(brain_dims[-1]):
          t0 = time()
          # Load a single brain volume
          vol = ch1_img.dataobj[...,i]

          ### Process vol (moco, zscore, etc) ###
          # Make ants image of ch1 brain
          moving = ants.from_numpy(np.asarray(vol, dtype='float32'))

          # Motion correct
          moco = ants.registration(fixed,moving,type_of_transform='SyN')
          moco_out = moco['warpedmovout'].numpy()
          transformlist = moco['fwdtransforms']
          
          ##also make ch2 warped brain correction using transforms
          if ch2_brain_file is not None: 
            ch2_img = nib.load(ch2_brain_file) # this loads a proxy
            ch2_vol = ch2_img.dataobj[...,i]
            ch2_moving = ants.from_numpy(np.asarray(ch2_vol, dtype='float32'))
            moco_ch2 = ants.apply_transforms(fixed, ch2_moving, transformlist)
            moco_ch2 = moco_ch2.numpy()
            
                 
                 
                 

          ### DELETE INVERSE TRANSFORMS
          transformlist = moco['invtransforms']
          for x in transformlist:
              if '.mat' not in x:
                  os.remove(x)
                  printlog('Deleted inv: {}'.format(x))

          ### DELETE FORWARD TRANSFORMS
          transformlist = moco['fwdtransforms']
          for x in transformlist:
              if '.mat' not in x:
                  os.remove(x)
                  printlog('Deleted fwd: {}'.format(x))

          # Append to hdf5 file
          with h5py.File(save_file_ch1, 'a') as f_ch1:

              # Increase hdf5 size by one brain volume
              current_num_vol = f_ch1['data'].shape[-1] # this is the last axis, which is time
              new_num_vol = current_num_vol + 1 # will want one more volume
              f_ch1['data'].resize(new_num_vol,axis=3) # increase size by one volume

              # Append to hdf5 file
              f_ch1['data'][...,-1] = moco_out  ##
                                                  
          printlog(F'vol: {i}, time: {time()-t0}')
                                                  
          # Append to hdf5 file for ch2   ##Alternatively I could put them in the same file with different keys
          if ch2_brain_file is not None:
            with h5py.File(save_file_ch2, 'a') as f_ch2:

                # Increase hdf5 size by one brain volume
                current_num_vol = f_ch2['data'].shape[-1] # this is the last axis, which is time
                new_num_vol = current_num_vol + 1 # will want one more volume
                f_ch2['data'].resize(new_num_vol,axis=3) # increase size by one volume

                # Append to hdf5 file
                f_ch2['data'][...,-1] = moco_ch2
            printlog(F'vol: {i}, time: {time()-t0}')

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))
