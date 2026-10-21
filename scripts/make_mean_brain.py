import os
import sys
import json
from time import sleep
import datetime
import brainsss
import numpy as np
import nibabel as nib
import h5py
import gc

# Timepoints read per step; the anat moco .h5 is ~50 GB, so the brain is never loaded whole
STEPSIZE = 10

def streamed_mean(data, n_frames):
    ''' Mean over the first n_frames of the last axis of a lazily indexed 4D array
    (h5py dataset or nibabel dataobj), read STEPSIZE timepoints at a time into a float64 sum. '''
    total = np.zeros(data.shape[:-1], dtype='float64')
    for start in range(0, n_frames, STEPSIZE):
        stop = min(start + STEPSIZE, n_frames)
        # sum(dtype=float64) accumulates in float64 without a float64 copy of the slab
        total += np.asarray(data[..., start:stop]).sum(axis=-1, dtype='float64')
    return total / n_frames

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
            if not os.path.exists(full_path):
                raise FileNotFoundError(full_path)
            if full_path.endswith('.nii'):
                img = nib.load(full_path)
                brain_shape = img.shape
                n_total = brain_shape[-1]
                n_frames = n_total if meanbrain_n_frames is None else min(int(meanbrain_n_frames), n_total)
                meanbrain = streamed_mean(img.dataobj, n_frames)
                img.uncache()
            elif full_path.endswith('.h5'):
                with h5py.File(full_path, 'r') as hf:
                    brain_shape = hf['data'].shape
                    n_total = brain_shape[-1]
                    n_frames = n_total if meanbrain_n_frames is None else min(int(meanbrain_n_frames), n_total)
                    meanbrain = streamed_mean(hf['data'], n_frames)
            else:
                raise ValueError('expected a .nii or .h5 file')

            ### Save ###
            save_file = os.path.join(directory, file[:-4] + '_mean.nii')
            aff = np.eye(4)
            img = nib.Nifti1Image(meanbrain.astype('float32'), aff)
            img.to_filename(save_file)

            fly_func_str = ('|').join(directory.split('/')[-3:-1])
            fly_print = directory.split('/')[-3]
            func_print = directory.split('/')[-2]
            #printlog(f"COMPLETE | {fly_func_str} | {file} | {brain.shape} --> {meanbrain.shape}")
            printlog(F"meanbrn | COMPLETED | {fly_print} | {func_print} | {file} | {brain_shape} ===> {meanbrain.shape}")
            print(n_total) ### IMPORTANT: for communication to main
        except FileNotFoundError:
            printlog(F"Not found (skipping){file:.>{width-20}}")
            #printlog(f'{file} not found.')
        except Exception as e:
            printlog(f"ERROR processing {file}: {str(e)}")

        finally:
            # ALWAYS clean up memory, even if error occurs
            meanbrain = None
            img = None
            gc.collect()  # Force garbage collection

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))
