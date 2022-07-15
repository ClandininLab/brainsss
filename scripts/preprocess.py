import time
import sys
import os
import re
import json
import textwrap
import brainsss
import argparse
import nibabel as nib

def main(args):

    modules = 'gcc/6.3.0 python/3.6 py-numpy/1.14.3_py36 py-pandas/0.23.0_py36 viz py-scikit-learn/0.19.1_py36 antspy/0.2.2'

    #########################
    ### Setup preferences ###
    #########################

    width = 120 # width of print log
    nodes = 2 # 1 or 2
    nice = True # true to lower priority of jobs. ie, other users jobs go first

    #####################
    ### Setup logging ###
    #####################

    logfile = './logs/' + time.strftime("%Y%m%d-%H%M%S") + '.txt'
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')
    sys.stderr = brainsss.Logger_stderr_sherlock(logfile)
    brainsss.print_title(logfile, width)

    #############################
    ### Parse input arguments ###
    #############################

    ### Get user settings
    #printlog("PWD: {}".format(args['PWD']))
    scripts_path = args['PWD']
    com_path = os.path.join(scripts_path, 'com')
    user = scripts_path.split('/')[3]
    settings = brainsss.load_user_settings(user, scripts_path)

    ### Grab buildflies from command line args first since it will impact parsing
    if args['BUILDFLIES'] == '':
        #printlog('not building flies')
        build_flies = False
    else:
        #printlog('building flies')
        build_flies = True
        dir_to_build = args['BUILDFLIES']

    ### Parse user settings
    imports_path = settings['imports_path']
    dataset_path = settings['dataset_path']
    if build_flies:
        fictrac_qc = brainsss.parse_true_false(settings.get('fictrac_qc',False))
        stim_triggered_beh = brainsss.parse_true_false(settings.get('stim_triggered_beh',False))
        bleaching_qc = brainsss.parse_true_false(settings.get('bleaching_qc',False))
        temporal_mean_brain_pre = brainsss.parse_true_false(settings.get('temporal_mean_brain_pre',False))
        motion_correction = brainsss.parse_true_false(settings.get('motion_correction',False))
        temporal_mean_brain_post = brainsss.parse_true_false(settings.get('temporal_mean_brain_post',False))
        zscore = brainsss.parse_true_false(settings.get('zscore',False))
        highpass = brainsss.parse_true_false(settings.get('highpass',False))
        correlation = brainsss.parse_true_false(settings.get('correlation', False))
        STA = brainsss.parse_true_false(settings.get('STA', False))
        h5_to_nii = brainsss.parse_true_false(settings.get('h5_to_nii', False))
        use_warp = brainsss.parse_true_false(settings.get('use_warp', False))
        clean_anat = brainsss.parse_true_false(settings.get('clean_anat', False))
        func2anat = brainsss.parse_true_false(settings.get('func2anat', False))
        anat2atlas = brainsss.parse_true_false(settings.get('anat2atlas', False))
        apply_transforms = brainsss.parse_true_false(settings.get('apply_transforms', False))
        grey_only = brainsss.parse_true_false(settings.get('grey_only', False))
        no_zscore_highpass = brainsss.parse_true_false(settings.get('no_zscore_highpass', False))
        make_supervoxels = brainsss.parse_true_false(settings.get('make_supervoxels', False))
    else:
        fictrac_qc = False
        stim_triggered_beh = False
        bleaching_qc = False
        temporal_mean_brain_pre = False
        motion_correction = False
        temporal_mean_brain_post = False
        zscore = False
        highpass = False
        correlation = False
        STA = False
        h5_to_nii = False
        use_warp = False
        clean_anat = False
        func2anat = False
        anat2atlas = False
        apply_transforms = False
        grey_only = False
        no_zscore_highpass = False
        make_supervoxels = False

    # this arg should not be available to the .json settings
    loco_dataset = False

    ### Parse remaining command line args
    if args['FLIES'] == '':
        #printlog('no flies specified')
        fly_dirs = None
    else:
        fly_dirs = args['FLIES'].split(',')

        ### add 'fly_' to beginning if it isn't there
        for i in range(len(fly_dirs)):
            if not fly_dirs[i].startswith('fly_'):
                fly_dirs[i] = 'fly_' + fly_dirs[i]

    if args['DIRTYPE'] == '':
        #printlog('no dirtype specified')
        dirtype = None
    else:
        dirtype = args['DIRTYPE'].lower()
        #printlog('dirtype is {}'.format(dirtype))

    # These command line arguments will be empty unless the flag is called from the command line
    if args['FICTRAC_QC'] != '':
        fictrac_qc = True
    if args['STB'] != '':
        stim_triggered_beh = True
    if args['BLEACHING_QC'] != '':
        bleaching_qc = True
    if args['TEMPORAL_MEAN_BRAIN_PRE'] != '':
        temporal_mean_brain_pre = True
    if args['MOCO'] != '':
        motion_correction = True
    if args['TEMPORAL_MEAN_BRAIN_POST'] != '':
        temporal_mean_brain_post = True
    if args['ZSCORE'] != '':
        zscore = True
    if args['HIGHPASS'] != '':
        highpass = True
    if args['CORRELATION'] != '':
        correlation = True
    if args ['STA'] != '':
        STA = True
    if args ['H5_TO_NII'] != '':
        h5_to_nii = True
    if args ['USE_WARP'] != '':
        use_warp = True
    if args ['LOCO_DATASET'] != '':
        loco_dataset = True
    if args ['CLEAN_ANAT'] != '':
        clean_anat = True
    if args ['FUNC2ANAT'] != '':
        func2anat = True
    if args ['ANAT2ATLAS'] != '':
        anat2atlas = True
    if args ['APPLY_TRANSFORMS'] != '':
        apply_transforms = True
    if args ['GREY_ONLY'] != '':
        grey_only = True
    if args ['NO_ZSCORE_HIGHPASS'] != '':
        no_zscore_highpass = True
    if args ['MAKE_SUPERVOXELS'] != '':
        make_supervoxels = True

    ### catch errors with incorrect argument combos
    # if fly builder is false, fly dirs must be provided
    if not build_flies and fly_dirs is None:
        printlog("ERROR: you did not provide a directory to build flies from, nor a fly directory to process.")
        printlog("Aborting.")
        return

    # quickly testing using global sherlock resources
    # if user == 'brezovec':
    #     global_resources = True
    # else:
    #     global_resources = False

    #################################
    ############# BEGIN #############
    #################################

    if build_flies:

        ######################
        ### CHECK FOR FLAG ###
        ######################

        # args = {'logfile': logfile, 'imports_path': imports_path}
        # script = 'check_for_flag.py'
        # job_id = brainsss.sbatch(jobname='flagchk',
        #                      script=os.path.join(scripts_path, script),
        #                      modules=modules,
        #                      args=args,
        #                      logfile=logfile, time=1, mem=1, nice=nice, nodes=nodes)
        # flagged_dir = brainsss.wait_for_job(job_id, logfile, com_path)

        ###################
        ### Build flies ###
        ###################

        flagged_dir = os.path.join(imports_path, dir_to_build)
        args = {'logfile': logfile, 'flagged_dir': flagged_dir, 'dataset_path': dataset_path, 'fly_dirs': fly_dirs, 'user': user}
        script = 'fly_builder.py'
        job_id = brainsss.sbatch(jobname='bldfly',
                             script=os.path.join(scripts_path, script),
                             modules=modules,
                             args=args,
                             logfile=logfile, time=1, mem=1, nice=nice, nodes=nodes)
        func_and_anats = brainsss.wait_for_job(job_id, logfile, com_path)
        func_and_anats = func_and_anats.split('\n')[:-1]
        funcs = [x.split(':')[1] for x in func_and_anats if 'func:' in x] # will be full paths to fly/expt
        anats = [x.split(':')[1] for x in func_and_anats if 'anat:' in x]

    else:
        funcs = []
        anats = []
        for fly_dir in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly_dir)
            if dirtype == 'func' or dirtype == None:
                funcs.extend([os.path.join(fly_directory, x) for x in os.listdir(fly_directory) if 'func' in x])
            if dirtype == 'anat'or dirtype == None:
                anats.extend([os.path.join(fly_directory, x) for x in os.listdir(fly_directory) if 'anat' in x])

    brainsss.sort_nicely(funcs)
    brainsss.sort_nicely(anats)
    funcanats = funcs + anats
    dirtypes = ['func']*len(funcs) + ['anat']*len(anats)

    if fictrac_qc:

        ##################
        ### Fictrac QC ###
        ##################

        job_ids = []
        for func in funcs:
            directory = os.path.join(func, 'fictrac')
            if os.path.exists(directory):
                args = {'logfile': logfile, 'directory': directory, 'fps': 100}
                script = 'fictrac_qc.py'
                job_id = brainsss.sbatch(jobname='fictracqc',
                                     script=os.path.join(scripts_path, script),
                                     modules=modules,
                                     args=args,
                                     logfile=logfile, time=1, mem=1, nice=nice, nodes=nodes)
                job_ids.append(job_id)
        for job_id in job_ids:
            brainsss.wait_for_job(job_id, logfile, com_path)

    ### quick hack to not proceed if the functional scan is a single slice ###
    # because the scripts below are not built to handle slices, only volumes
    # this is a dirty solution for a few reasons, in particular it will just base it on 
    # the first func dir
    # this will also break if only an anat scan was taken
    
    # func_to_check = os.path.join(funcanats[0], 'imaging', 'functional_channel_1.nii')
    # img_to_check = nib.load(func_to_check) # this loads a proxy
    # img_shape = img_to_check.header.get_data_shape()
    # if len(img_shape) < 4:
    #     printlog('image is not a volume')
    #     printlog(func_to_check)
    #     printlog('aborting all')
    #     return
    

    if stim_triggered_beh:

        ##########################
        ### Stim Triggered Beh ###
        ##########################

        for func in funcs:
            args = {'logfile': logfile, 'func_path': func}
            script = 'stim_triggered_avg_beh.py'
            job_id = brainsss.sbatch(jobname='stim',
                                 script=os.path.join(scripts_path, script),
                                 modules=modules,
                                 args=args,
                                 logfile=logfile, time=1, mem=2, nice=nice, nodes=nodes)
            brainsss.wait_for_job(job_id, logfile, com_path)

    if bleaching_qc:

        ####################
        ### Bleaching QC ###
        ####################

        #job_ids = []
        for funcanat, dirtype in zip(funcanats, dirtypes):
            directory = os.path.join(funcanat, 'imaging')
            args = {'logfile': logfile, 'directory': directory, 'dirtype': dirtype}
            script = 'bleaching_qc.py'
            job_id = brainsss.sbatch(jobname='bleachqc',
                                 script=os.path.join(scripts_path, script),
                                 modules=modules,
                                 args=args,
                                 logfile=logfile, time=1, mem=2, nice=nice, nodes=nodes)
            brainsss.wait_for_job(job_id, logfile, com_path)

    if temporal_mean_brain_pre:

        #######################################
        ### Create temporal mean brains PRE ###
        #######################################

        for funcanat, dirtype in zip(funcanats, dirtypes):
            directory = os.path.join(funcanat, 'imaging')

            if dirtype == 'func':
                files = ['functional_channel_1.nii', 'functional_channel_2.nii']
            if dirtype == 'anat':
                files = ['anatomy_channel_1.nii', 'anatomy_channel_2.nii']

            args = {'logfile': logfile, 'directory': directory, 'files': files}
            script = 'make_mean_brain.py'
            job_id = brainsss.sbatch(jobname='meanbrn',
                                 script=os.path.join(scripts_path, script),
                                 modules=modules,
                                 args=args,
                                 logfile=logfile, time=1, mem=2, nice=nice, nodes=nodes)
            brainsss.wait_for_job(job_id, logfile, com_path)

    if motion_correction:

        #########################
        ### Motion Correction ###
        #########################

        for funcanat, dirtype in zip(funcanats, dirtypes):

            directory = os.path.join(funcanat, 'imaging')
            if dirtype == 'func':
                brain_master = 'functional_channel_1.nii'
                brain_mirror = 'functional_channel_2.nii'
            if dirtype == 'anat':
                brain_master = 'anatomy_channel_1.nii'
                brain_mirror = 'anatomy_channel_2.nii'

            args = {'logfile': logfile,
                    'directory': directory,
                    'brain_master': brain_master,
                    'brain_mirror': brain_mirror,
                    'scantype': dirtype}

            script = 'motion_correction.py'
            # if global_resources:
            #     dur = 48
            #     mem = 8
            # else:
            #     dur = 96
            #     mem = 4
            global_resources = True
            dur = 48
            mem = 8
            job_id = brainsss.sbatch(jobname='moco',
                                 script=os.path.join(scripts_path, script),
                                 modules=modules,
                                 args=args,
                                 logfile=logfile, time=dur, mem=mem, nice=nice, nodes=nodes, global_resources=global_resources)
        ### currently submitting these jobs simultaneously since using global resources
        brainsss.wait_for_job(job_id, logfile, com_path)

    if zscore:

        ##############
        ### ZSCORE ###
        ##############

        for func in funcs:
            load_directory = os.path.join(func, 'moco')
            save_directory = os.path.join(func)
            brain_file = 'functional_channel_2_moco.h5'

            args = {'logfile': logfile, 'load_directory': load_directory, 'save_directory': save_directory, 'brain_file': brain_file}
            script = 'zscore.py'
            job_id = brainsss.sbatch(jobname='zscore',
                                 script=os.path.join(scripts_path, script),
                                 modules=modules,
                                 args=args,
                                 logfile=logfile, time=1, mem=2, nice=nice, nodes=nodes)
            brainsss.wait_for_job(job_id, logfile, com_path)

    if highpass:

        ################
        ### HIGHPASS ###
        ################

        for func in funcs:
            load_directory = os.path.join(func)
            save_directory = os.path.join(func)
            brain_file = 'functional_channel_2_moco_zscore.h5'

            args = {'logfile': logfile, 'load_directory': load_directory, 'save_directory': save_directory, 'brain_file': brain_file}
            script = 'temporal_high_pass_filter.py'
            job_id = brainsss.sbatch(jobname='highpass',
                                 script=os.path.join(scripts_path, script),
                                 modules=modules,
                                 args=args,
                                 logfile=logfile, time=4, mem=2, nice=nice, nodes=nodes)
            brainsss.wait_for_job(job_id, logfile, com_path)

    if correlation:

        ###################
        ### CORRELATION ###
        ###################

        for func in funcs:
            load_directory = os.path.join(func)
            save_directory = os.path.join(func, 'corr')
            if use_warp:
                brain_file = 'functional_channel_2_moco_zscore_highpass_warped.nii'
                fps = 100
            elif loco_dataset:
                brain_file = 'brain_zscored_green_high_pass_masked.nii'
                fps = 50
            elif no_zscore_highpass:
                brain_file = 'moco/functional_channel_2_moco.h5'
                #load_directory = os.path.join(func, 'moco')
                fps = 100
            else:
                brain_file = 'functional_channel_2_moco_zscore_highpass.h5'
                fps = 100

            behaviors = ['dRotLabZneg', 'dRotLabZpos', 'dRotLabY']
            for behavior in behaviors:

                args = {'logfile': logfile, 'load_directory': load_directory,
                'save_directory': save_directory, 'brain_file': brain_file, 
                'behavior': behavior, 'fps': fps, 'grey_only': grey_only}
                script = 'correlation.py'
                job_id = brainsss.sbatch(jobname='corr',
                                     script=os.path.join(scripts_path, script),
                                     modules=modules,
                                     args=args,
                                     logfile=logfile, time=2, mem=4, nice=nice, nodes=nodes)
                brainsss.wait_for_job(job_id, logfile, com_path)

    if STA:

        #########################################
        ### STIMULUS TRIGGERED NEURAL AVERAGE ###
        #########################################

        for func in funcs:
            args = {'logfile': logfile, 'func_path': func}
            script = 'stim_triggered_avg_neu.py'
            job_id = brainsss.sbatch(jobname='STA',
                                 script=os.path.join(scripts_path, script),
                                 modules=modules,
                                 args=args,
                                 logfile=logfile, time=4, mem=4, nice=nice, nodes=nodes)
            brainsss.wait_for_job(job_id, logfile, com_path)

    if h5_to_nii:

        #################
        ### H5 TO NII ###
        #################

        for func in funcs:
            args = {'logfile': logfile, 'h5_path': os.path.join(func, 'functional_channel_2_moco_zscore_highpass.h5')}
            script = 'h5_to_nii.py'
            job_id = brainsss.sbatch(jobname='h5tonii',
                                 script=os.path.join(scripts_path, script),
                                 modules=modules,
                                 args=args,
                                 logfile=logfile, time=2, mem=10, nice=nice, nodes=nodes)
            brainsss.wait_for_job(job_id, logfile, com_path)

    if temporal_mean_brain_post:

        #########################################
        ### Create temporal mean brains, POST ###
        #########################################

        for funcanat, dirtype in zip(funcanats, dirtypes):
            directory = os.path.join(funcanat, 'moco')

            if dirtype == 'func':
                files = ['functional_channel_1_moco.h5', 'functional_channel_2_moco.h5']
            if dirtype == 'anat':
                files = ['anatomy_channel_1_moco.h5', 'anatomy_channel_2_moco.h5']

            args = {'logfile': logfile, 'directory': directory, 'files': files}
            script = 'make_mean_brain.py'
            job_id = brainsss.sbatch(jobname='meanbrn',
                                 script=os.path.join(scripts_path, script),
                                 modules=modules,
                                 args=args,
                                 logfile=logfile, time=3, mem=12, nice=nice, nodes=nodes, global_resources=True)
        brainsss.wait_for_job(job_id, logfile, com_path)

    if clean_anat:

        ##################
        ### Clean Anat ###
        ##################

        for anat in anats:
            directory = os.path.join(anat, 'moco')
            args = {'logfile': logfile, 'directory': directory}
            script = 'clean_anat.py'
            job_id = brainsss.sbatch(jobname='clnanat',
                                 script=os.path.join(scripts_path, script),
                                 modules=modules,
                                 args=args,
                                 logfile=logfile, time=1, mem=1, nice=nice, nodes=nodes)
            brainsss.wait_for_job(job_id, logfile, com_path)

    if func2anat:

        #################
        ### func2anat ###
        #################

        res_anat = (0.653, 0.653, 1)
        res_func = (2.611, 2.611, 5)

        for fly in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly)

            if loco_dataset:
                moving_path = os.path.join(fly_directory, 'func_0', 'imaging', 'functional_channel_1_mean.nii')
            else:
                moving_path = os.path.join(fly_directory, 'func_0', 'moco', 'functional_channel_1_moc_mean.nii')
            moving_fly = 'func'
            moving_resolution = res_func

            if loco_dataset:
                fixed_path = os.path.join(fly_directory, 'anat_0', 'moco', 'stitched_brain_red_mean.nii')
            else:
                fixed_path = os.path.join(fly_directory, 'anat_0', 'moco', 'anatomy_channel_1_moc_mean.nii')
            fixed_fly = 'anat'
            fixed_resolution = res_anat

            save_directory = os.path.join(fly_directory, 'warp')
            if not os.path.exists(save_directory):
                os.mkdir(save_directory)

            type_of_transform = 'Affine'
            save_warp_params = True
            flip_X = False
            flip_Z = False

            low_res = False
            very_low_res = False

            iso_2um_fixed = True
            iso_2um_moving = False

            grad_step = 0.2
            flow_sigma = 3
            total_sigma = 0
            syn_sampling = 32

            args = {'logfile': logfile,
                    'save_directory': save_directory,
                    'fixed_path': fixed_path,
                    'moving_path': moving_path,
                    'fixed_fly': fixed_fly,
                    'moving_fly': moving_fly,
                    'type_of_transform': type_of_transform,
                    'flip_X': flip_X,
                    'flip_Z': flip_Z,
                    'moving_resolution': moving_resolution,
                    'fixed_resolution': fixed_resolution,
                    'save_warp_params': save_warp_params,
                    'low_res': low_res,
                    'very_low_res': very_low_res,
                    'iso_2um_fixed': iso_2um_fixed,
                    'iso_2um_moving': iso_2um_moving,
                    'grad_step': grad_step,
                    'flow_sigma': flow_sigma,
                    'total_sigma': total_sigma,
                    'syn_sampling': syn_sampling}

            script = 'align_anat.py'
            job_id = brainsss.sbatch(jobname='align',
                                 script=os.path.join(scripts_path, script),
                                 modules=modules,
                                 args=args,
                                 logfile=logfile, time=8, mem=4, nice=nice, nodes=nodes) # 2 to 1
            brainsss.wait_for_job(job_id, logfile, com_path)

    if anat2atlas:

        #################
        ### anat2mean ###
        #################
        res_anat = (1.3,1.3,1.3) # new anat res <------------------ this is set !!!!!
        #res_anat = (0.653, 0.653, 1)
        res_meanbrain = (2,2,2)

        for fly in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly)

            if loco_dataset:
                moving_path = os.path.join(fly_directory, 'anat_0', 'moco', 'anat_red_clean.nii')
            else:
                moving_path = os.path.join(fly_directory, 'anat_0', 'moco', 'anatomy_channel_1_moc_mean_clean.nii')
            moving_fly = 'anat'
            moving_resolution = res_anat

            # for gcamp6f with actual myr-tdtom
            fixed_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/anat_templates/20220301_luke_2_jfrc_affine_zflip_2umiso.nii"#luke.nii"
            fixed_fly = 'meanbrain'

            # for gcamp8s with non-myr-tdtom
            #fixed_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20220421_make_nonmyr_meanbrain/non_myr_2_fdaatlas_40_8.nii"
            #fixed_fly = 'non_myr_mean'

            fixed_resolution = res_meanbrain

            save_directory = os.path.join(fly_directory, 'warp')
            if not os.path.exists(save_directory):
                os.mkdir(save_directory)

            type_of_transform = 'SyN'
            save_warp_params = True
            flip_X = False
            flip_Z = False

            low_res = False
            very_low_res = False

            iso_2um_fixed = False
            iso_2um_moving = True

            grad_step = 0.2
            flow_sigma = 3
            total_sigma = 0
            syn_sampling = 32

            args = {'logfile': logfile,
                    'save_directory': save_directory,
                    'fixed_path': fixed_path,
                    'moving_path': moving_path,
                    'fixed_fly': fixed_fly,
                    'moving_fly': moving_fly,
                    'type_of_transform': type_of_transform,
                    'flip_X': flip_X,
                    'flip_Z': flip_Z,
                    'moving_resolution': moving_resolution,
                    'fixed_resolution': fixed_resolution,
                    'save_warp_params': save_warp_params,
                    'low_res': low_res,
                    'very_low_res': very_low_res,
                    'iso_2um_fixed': iso_2um_fixed,
                    'iso_2um_moving': iso_2um_moving,
                    'grad_step': grad_step,
                    'flow_sigma': flow_sigma,
                    'total_sigma': total_sigma,
                    'syn_sampling': syn_sampling}

            script = 'align_anat.py'
            job_id = brainsss.sbatch(jobname='align',
                                 script=os.path.join(scripts_path, script),
                                 modules=modules,
                                 args=args,
                                 logfile=logfile, time=8, mem=8, nice=nice, nodes=nodes)
            brainsss.wait_for_job(job_id, logfile, com_path)

    if apply_transforms:

        ########################
        ### Apply transforms ###
        ########################
        res_func = (2.611, 2.611, 5)
        res_anat = (2,2,2)#(0.38, 0.38, 0.38)
        final_2um_iso = False #already 2iso so don't need to downsample

        for fly in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly)

            behaviors = ['dRotLabY', 'dRotLabZneg', 'dRotLabZpos']
            for behavior in behaviors:
                if loco_dataset:
                    moving_path = os.path.join(fly_directory, 'func_0', 'corr', '20220418_corr_{}.nii'.format(behavior))
                else:
                    moving_path = os.path.join(fly_directory, 'func_0', 'corr', '20220420_corr_{}.nii'.format(behavior))
                moving_fly = 'corr_{}'.format(behavior)
                moving_resolution = res_func

                #fixed_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/anat_templates/luke.nii"
                fixed_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/anat_templates/20220301_luke_2_jfrc_affine_zflip_2umiso.nii"#luke.nii"
                fixed_fly = 'meanbrain'
                fixed_resolution = res_anat

                save_directory = os.path.join(fly_directory, 'warp')
                if not os.path.exists(save_directory):
                    os.mkdir(save_directory)

                args = {'logfile': logfile,
                        'save_directory': save_directory,
                        'fixed_path': fixed_path,
                        'moving_path': moving_path,
                        'fixed_fly': fixed_fly,
                        'moving_fly': moving_fly,
                        'moving_resolution': moving_resolution,
                        'fixed_resolution': fixed_resolution,
                        'final_2um_iso': final_2um_iso}

                script = 'apply_transforms.py'
                job_id = brainsss.sbatch(jobname='aplytrns',
                                     script=os.path.join(scripts_path, script),
                                     modules=modules,
                                     args=args,
                                     logfile=logfile, time=12, mem=4, nice=nice, nodes=nodes) # 2 to 1
                brainsss.wait_for_job(job_id, logfile, com_path)

    if make_supervoxels:
        for func in funcs:
            args = {'logfile': logfile, 'func_path': func}
            script = 'make_supervoxels.py'
            job_id = brainsss.sbatch(jobname='supervox',
                                 script=os.path.join(scripts_path, script),
                                 modules=modules,
                                 args=args,
                                 logfile=logfile, time=2, mem=8, nice=nice, nodes=nodes)
            brainsss.wait_for_job(job_id, logfile, com_path)

    ############
    ### Done ###
    ############

    brainsss.print_footer(logfile, width)

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))
    # parser = argparse.ArgumentParser()
    # parser.add_argument("PWD") 
    # args = parser.parse_args()
    # main(args)