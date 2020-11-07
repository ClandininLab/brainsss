import os
import sys
import brainsss
import numpy as np
import re
import json
import nibabel as nib
from time import time
import matplotlib.pyplot as plt

def main(args):

    logfile = args['logfile']
    directory = args['directory'] # moco full path
    dirtype = 'func'
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')
    printlog('\nStitcher started for {}'.format(directory))

    ######################
    ### Get file names ###
    ######################

    colors = ['red', 'green']
    files = {}
    for color in colors:
        files[color] = []
        for file in os.listdir(directory):
            if '.nii' in file and color in file:
                files[color].append(os.path.join(directory, file))
        brainsss.sort_nicely(files[color])

    #####################
    ### Stitch brains ###
    #####################

    for color in colors:
        if len(files[color]) > 0:
            brains = []
            for brain_file in files[color]:
                brain = np.asarray(nib.load(brain_file).get_data(), dtype=np.uint16)

                # Handle edgecase of single volume brain
                if len(np.shape(brain)) == 3:
                    brain = brain[:,:,:,np.newaxis]
                #print('shape of partial brain: {}'.format(np.shape(brain)))
                brains.append(brain)

            #print('brains len: {}'.format(len(brains)))
            stitched_brain = np.concatenate(brains, axis=-1)
            printlog('Stitched brain shape: {}'.format(np.shape(stitched_brain)))

            save_file = os.path.join(directory, 'stitched_brain_{}.nii'.format(color))
            aff = np.eye(4)
            img = nib.Nifti1Image(stitched_brain, aff)
            img.to_filename(save_file)
            stitched_brain = None

            # delete partial brains
            [os.remove(file) for file in files[color]]

    ##########################
    ### Stitch moco params ###
    ##########################

    motcorr_param_files = []
    for item in os.listdir(directory):
        if '.npy' in item:
            file = os.path.join(directory, item)
            motcorr_param_files.append(file)
    brainsss.sort_nicely(motcorr_param_files)
    
    motcorr_params = []
    for file in motcorr_param_files:
        motcorr_params.append(np.load(file))

    if len(motcorr_params) > 0:
        stitched_params = np.concatenate(motcorr_params, axis=0)
        save_file = os.path.join(directory, 'motcorr_params_stitched')
        np.save(save_file, stitched_params)
        [os.remove(file) for file in motcorr_param_files]
        xml_dir = os.path.join(os.path.split(directory)[0], 'imaging')
        save_motion_figure(stitched_params, xml_dir, directory, dirtype)
    else:
        printlog('Empty motcorr params - skipping saving moco figure.')

def save_motion_figure(transform_matrix, directory, motcorr_directory, dirtype):
    # Get voxel resolution for figure
    if dirtype == 'func':
        file = os.path.join(directory, 'functional.xml')
    elif dirtype == 'anat':
        file = os.path.join(directory, 'anatomy.xml')
    #x_res, y_res, z_res = brainsss.get_resolution(file)
    x_res, y_res, z_res = (2.6,2.6,5)


    # Save figure of motion over time
    save_file = os.path.join(motcorr_directory, 'motion_correction.png')
    plt.figure(figsize=(10,10))
    plt.plot(transform_matrix[:,9]*x_res, label = 'y') # note, resolutions are switched since axes are switched
    plt.plot(transform_matrix[:,10]*y_res, label = 'x')
    plt.plot(transform_matrix[:,11]*z_res, label = 'z')
    plt.ylabel('Motion Correction, um')
    plt.xlabel('Time')
    plt.title(directory)
    plt.legend()
    plt.savefig(save_file, bbox_inches='tight', dpi=300)

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))