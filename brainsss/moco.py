import numpy as np
import os
import sys
import psutil
import nibabel as nib
from time import time
import matplotlib.pyplot as plt
from contextlib import contextmanager
import warnings
warnings.filterwarnings("ignore")

# import platform
# if platform.system() != 'Windows':
#     sys.path.insert(0, '/home/users/brezovec/.local/lib/python3.6/site-packages/lib/python/')
import ants

def align_volume(fixed, moving, vol):

    moving_vol = ants.from_numpy(moving[:,:,:,vol])

    with stderr_redirected(): # to prevent dumb itk gaussian error bullshit infinite printing
        motCorr_vol = ants.registration(fixed, moving_vol, type_of_transform='SyN')

    return motCorr_vol

def motion_correction(brain_master,
                      brain_moving,
                      motcorr_directory,
                      printlog,
                      meanbrain,
                      suffix=''):

    motCorr_brain_master = []
    motCorr_brain_moving = []
    durations = []
    transform_matrix = []

    for i in range(np.shape(brain_master)[-1]):
        #printlog('Aligning brain volume {}'.format(i))
        t0 = time()
        
        #First, align given master volume to master meanbrain
        with stderr_redirected(): # to prevent dumb itk gaussian error bullshit infinite printing
            # note meanbrain is already an ants object
            motCorr_vol = ants.registration(meanbrain, ants.from_numpy(brain_master[:,:,:,i]), type_of_transform='SyN')

        motCorr_brain_master.append(motCorr_vol['warpedmovout'].numpy())
        transformlist = motCorr_vol['fwdtransforms']

        #Use warp parameters on moving volume if provided
        if brain_moving:
            motCorr_brain_moving.append(ants.apply_transforms(meanbrain,ants.from_numpy(brain_moving[:,:,:,i]),transformlist).numpy())
        
        #Lets immediately grab the transform file because otherwise I think it is auto deleted due to "tmp" status...?
        #Indeed I think CentOS possibly perges /tmp pretty frequently
        #printlog('fwd_files: {}'.format(transformlist))
        for x in transformlist:
            if '.mat' in x:
                temp = ants.read_transform(x)
                transform_matrix.append(temp.parameters)
            os.remove(x)
            #printlog('Deleted fwd: {}'.format(x))

        # Delete invtransforms for /tmp directory size issue. note that .mat are shared, so only need to delete .nii.gz
        transformlist = motCorr_vol['invtransforms']
        #printlog('inv_files: {}'.format(transformlist))
        for x in transformlist:
            if '.mat' not in x:
                os.remove(x)
                #printlog('Deleted inv: {}'.format(x))

        print(F"[{i+1}]") #IMPORTANT FOR COMMUNICATION WITH DATAFLOW MAIN
        sys.stdout.flush()

    # Save motcorr brains
    save_motCorr_brain(motCorr_brain_master, motcorr_directory, suffix='red'+suffix)
    if brain_moving:
        save_motCorr_brain(motCorr_brain_moving, motcorr_directory, suffix='green'+suffix)

    # Save transforms
    transform_matrix = np.array(transform_matrix)
    save_file = os.path.join(motcorr_directory, 'motcorr_params{}'.format(suffix))
    np.save(save_file,transform_matrix)

def save_motCorr_brain(brain, directory, suffix):
    brain = np.moveaxis(np.asarray(brain),0,3)
    save_file = os.path.join(directory, 'motcorr_' + suffix + '.nii')
    aff = np.eye(4)
    img = nib.Nifti1Image(brain, aff)
    img.to_filename(save_file)

@contextmanager
def stderr_redirected(to=os.devnull):

    fd = sys.stderr.fileno()

    def _redirect_stderr(to):
        sys.stderr.close() # + implicit flush()
        os.dup2(to.fileno(), fd) # fd writes to 'to' file
        sys.stderr = os.fdopen(fd, 'w') # Python writes to fd

    with os.fdopen(os.dup(fd), 'w') as old_stderr:
        with open(to, 'w') as file:
            _redirect_stderr(to=file)
        try:
            yield # allow code to be run with the redirected stdout
        finally:
            _redirect_stderr(to=old_stderr) # restore stdout.
                                            # buffering and flags such as
                                            # CLOEXEC may be different