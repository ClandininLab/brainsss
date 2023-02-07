import os
import sys
import json
from time import sleep
import datetime
import brainsss
import numpy as np
import nibabel as nib
import h5py

def main(args):

    logfile = args['logfile']
    directory = args['directory'] # directory will be a full path to either an anat/imaging folder or a func/imaging folder
    files = args['files']
    meanbrain_n_frames = args.get('meanbrain_n_frames', None)  # First n frames to average over when computing mean/fixed brain | Default None (average over all frames)
    width = 120
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    # Check if files is just a single file path string
    if type(files) is str:
        files = [files]

    

    for file in files:
        try:
            ### make mean ###
            full_path = os.path.join(directory, file)
            if full_path.endswith('.nii'):
                brain = np.asarray(nib.load(full_path).get_data(), dtype='uint16')
            elif full_path.endswith('.h5'):
                with h5py.File(full_path, 'r') as hf:
                    brain = np.asarray(hf['data'][:], dtype='uint16')

            if meanbrain_n_frames is not None:
                # average over first meanbrain_n_frames frames
                meanbrain = np.mean(brain[...,:int(meanbrain_n_frames)], axis=-1)
            else: # average over all frames
                meanbrain = np.mean(brain, axis=-1)

            ### Save ###
            save_file = os.path.join(directory, file[:-4] + '_mean.nii')
            aff = np.eye(4)
            img = nib.Nifti1Image(meanbrain, aff)
            img.to_filename(save_file)

            fly_func_str = ('|').join(directory.split('/')[-3:-1])
            fly_print = directory.split('/')[-3]
            func_print = directory.split('/')[-2]
            #printlog(f"COMPLETE | {fly_func_str} | {file} | {brain.shape} --> {meanbrain.shape}")
            printlog(F"meanbrn | COMPLETED | {fly_print} | {func_print} | {file} | {brain.shape} ===> {meanbrain.shape}")
            print(brain.shape[-1]) ### IMPORTANT: for communication to main
            brain = None
        except FileNotFoundError:
            printlog(F"Not found (skipping){file:.>{width-20}}")
            #printlog(f'{file} not found.')

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))