import sys
import os
import json
import nibabel as nib
import numpy as np
import brainsss
import warnings
warnings.filterwarnings("ignore")

#sys.path.insert(0, '/home/users/brezovec/.local/lib/python3.6/site-packages/lib/python/')
import ants

def main(args):

    logfile = args['logfile']
    directory = args['directory'] # directory will be a full path to either an anat folder or a func folder
    start = int(args['start'])
    stop = int(args['stop'])
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    moco_dir = os.path.join(directory, 'moco')

    try:
      master_path = os.path.join(directory, 'functional_channel_1.nii')
      moving_path = os.path.join(directory, 'functional_channel_2.nii')
      master_path_mean = os.path.join(directory, 'functional_channel_1_mean.nii')

      # For the sake of memory, load only the part of the brain we will need.
      master_brain = load_partial_brain(master_path,start,stop)
      moving_brain = load_partial_brain(moving_path,start,stop)
      mean_brain = ants.from_numpy(np.asarray(nib.load(master_path_mean).get_data(), dtype='float32'))
    except:
      printlog('fuctional data not found; trying anatomical')
      master_path = os.path.join(directory, 'anatomy_channel_1.nii')
      moving_path = os.path.join(directory, 'anatomy_channel_2.nii')
      master_path_mean = os.path.join(directory, 'anatomy_channel_1_mean.nii')

      # For the sake of memory, load only the part of the brain we will need.
      master_brain = load_partial_brain(master_path,start,stop)
      moving_brain = load_partial_brain(moving_path,start,stop)
      mean_brain = ants.from_numpy(np.asarray(nib.load(master_path_mean).get_data(), dtype='float32'))

    motion_correction(master_brain,
                           moving_brain,
                           moco_dir,
                           printlog,
                           mean_brain,
                           suffix='_'+str(start))

def load_partial_brain(file, start, stop):
    brain = nib.load(file).dataobj[:,:,:,start:stop]
    # for ants, supported_ntypes = {'uint8', 'uint32', 'float32', 'float64'}
    brain = ants.from_numpy(np.asarray(np.squeeze(brain), dtype='float32')) #updated dtype 20200626 from float64 to float32
    # always keep 4 axes:
    if len(np.shape(brain)) == 3:
      brain = brain[:,:,:,np.newaxis]
    return brain

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

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))