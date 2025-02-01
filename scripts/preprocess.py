import argparse
import json
import os
import re
import sys
import textwrap
import time

import brainsss
import nibabel as nib


def main(args):

    modules = "gcc/6.3.0 python/3.6 py-numpy/1.14.3_py36 py-pandas/0.23.0_py36 viz py-scikit-learn/0.19.1_py36 py-ants/0.3.2_py36"

    #########################
    ### Setup preferences ###
    #########################

    width = 120  # width of print log
    nodes = 2  # 1 or 2
    nice = True  # true to lower priority of jobs. ie, other users jobs go first

    #####################
    ### Setup logging ###
    #####################

    logfile = "./logs/" + time.strftime("%Y%m%d-%H%M%S") + ".txt"
    printlog = getattr(brainsss.Printlog(logfile=logfile), "print_to_log")
    sys.stderr = brainsss.Logger_stderr_sherlock(logfile)
    brainsss.print_title(logfile, width)

    #############################
    ### Parse input arguments ###
    #############################

    ### Get user settings
    # printlog("PWD: {}".format(args['PWD']))
    scripts_path = args["PWD"]
    com_path = os.path.join(scripts_path, "com")
    user = scripts_path.split("/")[3]
    settings = brainsss.load_user_settings(user, scripts_path)

    ### Grab buildflies from command line args first since it will impact parsing
    if args["BUILDFLIES"] == "":
        # printlog('not building flies')
        build_flies = False
    else:
        # printlog('building flies')
        build_flies = True
        dir_to_build = args["BUILDFLIES"]

    ### Parse user settings
    imports_path = settings["imports_path"]
    dataset_path = settings["dataset_path"]
    if build_flies:
        fictrac_qc = brainsss.parse_true_false(settings.get("fictrac_qc", False))
        bleaching_qc = brainsss.parse_true_false(settings.get("bleaching_qc", False))
        temporal_mean_brain_pre = brainsss.parse_true_false(
            settings.get("temporal_mean_brain_pre", False)
        )
        motion_correction = brainsss.parse_true_false(
            settings.get("motion_correction", False)
        )
        channel_change = brainsss.parse_true_false(settings.get("channel_change", False))
        temporal_mean_brain_post = brainsss.parse_true_false(
            settings.get("temporal_mean_brain_post", False)
        )
        background_subtraction = brainsss.parse_true_false(settings.get("background_subtraction", False))
        raw_warp = brainsss.parse_true_false(settings.get("raw_warp", False))
        timestamp_warp = brainsss.parse_true_false(settings.get("timestamp_warp", False))
        blur = brainsss.parse_true_false(settings.get("blur", False))
        butter_highpass = brainsss.parse_true_false(settings.get("butter_highpass", False))
        dff = brainsss.parse_true_false(settings.get("dff", False))
        filter_bins = brainsss.parse_true_false(settings.get("filter_bins", False))
        relative_ts = brainsss.parse_true_false(settings.get("relative_ts", False))
        temp_filter = brainsss.parse_true_false(settings.get("temp_filter", False))
        whole_brain_interp = brainsss.parse_true_false(settings.get("whole_brain_interp", False))
        build_STA = brainsss.parse_true_false(settings.get("build_STA", False))
        h5_to_nii = brainsss.parse_true_false(settings.get("h5_to_nii", False))
        clean_anat = brainsss.parse_true_false(settings.get("clean_anat", False))
        func2anat = brainsss.parse_true_false(settings.get("func2anat", False))
        anat2atlas = brainsss.parse_true_false(settings.get("anat2atlas", False))
        make_supervoxels = brainsss.parse_true_false(
            settings.get("make_supervoxels", False)
        )
    else:
        fictrac_qc = False
        bleaching_qc = False
        temporal_mean_brain_pre = False
        motion_correction = False
        channel_change = False
        temporal_mean_brain_post = False
        background_subtraction = False
        raw_warp = False
        timestamp_warp = False
        blur = False
        butter_highpass = False
        dff = False
        filter_bins = False
        relative_ts = False
        temp_filter = False
        whole_brain_interp = False
        build_STA = False
        h5_to_nii = False
        clean_anat = False
        func2anat = False
        anat2atlas = False
        make_supervoxels = False

    ### Parse remaining command line args
    if args["FLIES"] == "":
        # printlog('no flies specified')
        fly_dirs = None
    else:
        fly_dirs = args["FLIES"].split(",")

        ### add 'fly_' to beginning if it isn't there
        for i in range(len(fly_dirs)):
            if not fly_dirs[i].startswith("fly_"):
                fly_dirs[i] = "fly_" + fly_dirs[i]

    if args["DIRTYPE"] == "":
        # printlog('no dirtype specified')
        dirtype = None
    else:
        dirtype = args["DIRTYPE"].lower()
        # printlog('dirtype is {}'.format(dirtype))

    # These command line arguments will be empty unless the flag is called from the command line
    if args["FICTRAC_QC"] != "":
        fictrac_qc = True
    if args["BLEACHING_QC"] != "":
        bleaching_qc = True
    if args["TEMPORAL_MEAN_BRAIN_PRE"] != "":
        temporal_mean_brain_pre = True
    if args["MOCO"] != "":
        motion_correction = True
    if args["CHANNEL_CHANGE"] != "":
        channel_change = True
    if args["TEMPORAL_MEAN_BRAIN_POST"] != "":
        temporal_mean_brain_post = True
    if args["BACKGROUND_SUBTRACTION"] != "":
        background_subtraction = True	
    if args["RAW_WARP"] != "":
        raw_warp = True	
    if args["TIMESTAMP_WARP"] != "":
        timestamp_warp = True	
    if args["BLUR"] != "":
        blur = True	
    if args["HPF"] != "":
        butter_highpass = True
    if args["DFF"] != "":
        dff = True	
    if args["FILTER_BINS"] != "":
        filter_bins = True
    if args["RELATIVE_TS"] != "":
        relative_ts = True
    if args["TEMP_FILTER"] != "":
        temp_filter = True
    if args["WHOLE_BRAIN_INTERP"] != "":
        whole_brain_interp = True
    if args["BUILD_STA"] != "":
        build_STA = True
    if args["H5_TO_NII"] != "":
        h5_to_nii = True
    if args["CLEAN_ANAT"] != "":
        clean_anat = True
    if args["FUNC2ANAT"] != "":
        func2anat = True
    if args["ANAT2ATLAS"] != "":
        anat2atlas = True
    if args["MAKE_SUPERVOXELS"] != "":
        make_supervoxels = True

    ### catch errors with incorrect argument combos
    # if fly builder is false, fly dirs must be provided
    if not build_flies and fly_dirs is None:
        printlog(
            "ERROR: you did not provide a directory to build flies from, nor a fly directory to process."
        )
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
        args = {
            "logfile": logfile,
            "flagged_dir": flagged_dir,
            "dataset_path": dataset_path,
            "fly_dirs": fly_dirs,
            "user": user,
        }
        script = "fly_builder.py"
        job_id = brainsss.sbatch(
            jobname="bldfly",
            script=os.path.join(scripts_path, script),
            modules=modules,
            args=args,
            logfile=logfile,
            time=3,
            cpus=1,
            nice=nice,
            nodes=nodes,
        )
        func_and_anats = brainsss.wait_for_job(job_id, logfile, com_path)
        func_and_anats = func_and_anats.split("\n")[:-1]
        funcs = [
            x.split(":")[1] for x in func_and_anats if "func:" in x
        ]  # will be full paths to fly/expt
        anats = [x.split(":")[1] for x in func_and_anats if "anat:" in x]

    else:
        funcs = []
        anats = []
        for fly_dir in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly_dir)
            if dirtype == "func" or dirtype == None:
                funcs.extend(
                    [
                        os.path.join(fly_directory, x)
                        for x in os.listdir(fly_directory)
                        if "func" in x
                    ]
                )
            if dirtype == "anat" or dirtype == None:
                anats.extend(
                    [
                        os.path.join(fly_directory, x)
                        for x in os.listdir(fly_directory)
                        if "anat" in x
                    ]
                )

    brainsss.sort_nicely(funcs)
    brainsss.sort_nicely(anats)
    funcanats = funcs + anats
    dirtypes = ["func"] * len(funcs) + ["anat"] * len(anats)

    if fictrac_qc:

        ##################
        ### Fictrac QC ###
        ##################

        job_ids = []
        for func in funcs:
            directory = os.path.join(func, "fictrac")
            if os.path.exists(directory):
                args = {"logfile": logfile, "directory": directory, "fps": 100}
                script = "fictrac_qc.py"
                job_id = brainsss.sbatch(
                    jobname="fictracqc",
                    script=os.path.join(scripts_path, script),
                    modules=modules,
                    args=args,
                    logfile=logfile,
                    time=1,
                    cpus=1,
                    nice=nice,
                    nodes=nodes,
                )
                job_ids.append(job_id)
        for job_id in job_ids:
            brainsss.wait_for_job(job_id, logfile, com_path)

    # because the scripts below are not built to handle slices, only volumes
    # this will also break if only an anat scan was taken

    if bleaching_qc:

        ####################
        ### Bleaching QC ###
        ####################

        # job_ids = []
        for funcanat, dirtype in zip(funcanats, dirtypes):
            directory = os.path.join(funcanat, "imaging")
            args = {"logfile": logfile, "directory": directory, "dirtype": dirtype}
            script = "bleaching_qc.py"
            job_id = brainsss.sbatch(
                jobname="bleachqc",
                script=os.path.join(scripts_path, script),
                modules=modules,
                args=args,
                logfile=logfile,
                time=1,
                cpus=4,
                nice=nice,
                nodes=nodes,
            )
            brainsss.wait_for_job(job_id, logfile, com_path)

    if temporal_mean_brain_pre:

        #######################################
        ### Create temporal mean brains PRE ###
        #######################################

        for funcanat, dirtype in zip(funcanats, dirtypes):
            directory = os.path.join(funcanat, "imaging")

            if dirtype == "func":
                files = ["functional_channel_1.nii", "functional_channel_2.nii"]
            if dirtype == "anat":
                files = ["anatomy_channel_1.nii", "anatomy_channel_2.nii"]

            args = {"logfile": logfile, "directory": directory, "files": files}
            script = "make_mean_brain.py"
            job_id = brainsss.sbatch(
                jobname="meanbrn",
                script=os.path.join(scripts_path, script),
                modules=modules,
                args=args,
                logfile=logfile,
                time=1,
                cpus=2,
                nice=nice,
                nodes=nodes,
            )
            brainsss.wait_for_job(job_id, logfile, com_path)

    if motion_correction:

        #########################
        ### Motion Correction ###
        #########################

        for funcanat, dirtype in zip(funcanats, dirtypes):

            directory = os.path.join(funcanat, "imaging")
            if dirtype == "func":
                brain_master = "functional_channel_1.nii"
                brain_mirror = "functional_channel_2.nii"
            if dirtype == "anat":
                brain_master = "anatomy_channel_1.nii"
                brain_mirror = "anatomy_channel_2.nii"

            args = {
                "logfile": logfile,
                "directory": directory,
                "brain_master": brain_master,
                "brain_mirror": brain_mirror,
                "scantype": dirtype,
            }

            script = "motion_correction.py"
            # if global_resources:
            #     dur = 48
            #     mem = 8
            # else:
            #     dur = 96
            #     mem = 4
            global_resources = False
            dur = 48
            cpus = 8
            job_id = brainsss.sbatch(
                jobname="moco",
                script=os.path.join(scripts_path, script),
                modules=modules,
                args=args,
                logfile=logfile,
                time=dur,
                cpus=cpus,
                nice=nice,
                nodes=nodes,
                global_resources=global_resources,
            )
        ### currently submitting these jobs simultaneously since using global resources
        brainsss.wait_for_job(job_id, logfile, com_path)
   
    if temporal_mean_brain_post:

        #########################################
        ### Create temporal mean brains, POST ###
        #########################################

        for funcanat, dirtype in zip(funcanats, dirtypes):
            directory = os.path.join(funcanat, "moco")

            if dirtype == "func":
                files = ["functional_channel_1_moco.h5", "functional_channel_2_moco.h5"]
            if dirtype == "anat":
                files = ["anatomy_channel_1_moco.h5", "anatomy_channel_2_moco.h5"]

            args = {"logfile": logfile, "directory": directory, "files": files}
            script = "make_mean_brain.py"
            job_id = brainsss.sbatch(
                jobname="meanbrn",
                script=os.path.join(scripts_path, script),
                modules=modules,
                args=args,
                logfile=logfile,
                time=3,
                cpus=12,
                nice=nice,
                nodes=nodes,
                global_resources=False,
            )
        brainsss.wait_for_job(job_id, logfile, com_path)

    if clean_anat:

        ##################
        ### Clean Anat ###
        ##################

        for anat in anats:
            directory = os.path.join(anat, "moco")
            args = {"logfile": logfile, "directory": directory}
            script = "clean_anat.py"
            job_id = brainsss.sbatch(
                jobname="clnanat",
                script=os.path.join(scripts_path, script),
                modules=modules,
                args=args,
                logfile=logfile,
                time=1,
                cpus=1,
                nice=nice,
                nodes=nodes,
            )
            brainsss.wait_for_job(job_id, logfile, com_path)

    if func2anat:

        #################
        ### func2anat ###
        #################

        res_anat = (0.653, 0.653, 1)
        res_func = (2.611, 2.611, 5)

        for fly in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly)
            
            moving_path = os.path.join(
                fly_directory, "func_0", "moco", "functional_channel_1_moc_mean.nii"
            )
            moving_fly = "func"
            moving_resolution = res_func

            fixed_path = os.path.join(
                fly_directory, "anat_0", "moco", "anatomy_channel_1_moc_mean.nii"
            )
            fixed_fly = "anat"
            fixed_resolution = res_anat

            save_directory = os.path.join(fly_directory, "warp")
            if not os.path.exists(save_directory):
                os.mkdir(save_directory)

            type_of_transform = "Affine"
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

            args = {
                "logfile": logfile,
                "save_directory": save_directory,
                "fixed_path": fixed_path,
                "moving_path": moving_path,
                "fixed_fly": fixed_fly,
                "moving_fly": moving_fly,
                "type_of_transform": type_of_transform,
                "flip_X": flip_X,
                "flip_Z": flip_Z,
                "moving_resolution": moving_resolution,
                "fixed_resolution": fixed_resolution,
                "save_warp_params": save_warp_params,
                "low_res": low_res,
                "very_low_res": very_low_res,
                "iso_2um_fixed": iso_2um_fixed,
                "iso_2um_moving": iso_2um_moving,
                "grad_step": grad_step,
                "flow_sigma": flow_sigma,
                "total_sigma": total_sigma,
                "syn_sampling": syn_sampling,
            }

            script = "align_anat.py"
            job_id = brainsss.sbatch(
                jobname="align",
                script=os.path.join(scripts_path, script),
                modules=modules,
                args=args,
                logfile=logfile,
                time=8,
                cpus=4,
                nice=nice,
                nodes=nodes,
            )  # 2 to 1
            brainsss.wait_for_job(job_id, logfile, com_path)

    if anat2atlas:

        #################
        ### anat2mean ###
        #################
        # res_anat = (1.3,1.3,1.3) # new anat res <------------------ this is set !!!!!
        res_anat = (0.653, 0.653, 1)
        res_meanbrain = (2, 2, 2)

        for fly in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly)

            moving_path = os.path.join(
                fly_directory,
                "anat_0",
                "moco",
                "anatomy_channel_1_moc_mean_clean.nii",
            )
            moving_fly = "anat"
            moving_resolution = res_anat

            # for gcamp6f with actual myr-tdtom
            fixed_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/anat_templates/20220301_luke_2_jfrc_affine_zflip_2umiso.nii"  # luke.nii"
            fixed_fly = "meanbrain"

            # for gcamp8s with non-myr-tdtom
            # fixed_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20220421_make_nonmyr_meanbrain/non_myr_2_fdaatlas_40_8.nii"
            # fixed_fly = 'non_myr_mean'

            fixed_resolution = res_meanbrain

            save_directory = os.path.join(fly_directory, "warp")
            if not os.path.exists(save_directory):
                os.mkdir(save_directory)

            type_of_transform = "SyN"
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

            args = {
                "logfile": logfile,
                "save_directory": save_directory,
                "fixed_path": fixed_path,
                "moving_path": moving_path,
                "fixed_fly": fixed_fly,
                "moving_fly": moving_fly,
                "type_of_transform": type_of_transform,
                "flip_X": flip_X,
                "flip_Z": flip_Z,
                "moving_resolution": moving_resolution,
                "fixed_resolution": fixed_resolution,
                "save_warp_params": save_warp_params,
                "low_res": low_res,
                "very_low_res": very_low_res,
                "iso_2um_fixed": iso_2um_fixed,
                "iso_2um_moving": iso_2um_moving,
                "grad_step": grad_step,
                "flow_sigma": flow_sigma,
                "total_sigma": total_sigma,
                "syn_sampling": syn_sampling,
            }

            script = "align_anat.py"
            job_id = brainsss.sbatch(
                jobname="align",
                script=os.path.join(scripts_path, script),
                modules=modules,
                args=args,
                logfile=logfile,
                time=8,
                cpus=8,
                nice=nice,
                nodes=nodes,
            )
            brainsss.wait_for_job(job_id, logfile, com_path)
   
    if channel_change:
        ch_num = '1'
    else:
        ch_num = '2'
    printlog('Channel number: {}'.format(ch_num))

    if background_subtraction:

        ##############################
        ### BACKGROUND SUBTRACTION ###
        ##############################

        for func in funcs:
            load_directory = os.path.join(func, "moco")
            save_directory = os.path.join(func)
            brain_file = f"functional_channel_{ch_num}_moco.h5"
                
            args = {
                "logfile": logfile,
                "load_directory": load_directory,
                "save_directory": save_directory,
                "brain_file": brain_file,
            }
            script = "background_subtraction.py"
            job_id = brainsss.sbatch(
                jobname="background_subtraction",
                script=os.path.join(scripts_path, script),
                modules=modules,
                args=args,
                logfile=logfile,
                time=1,
                cpus=10,
                mem='150GB',
                nice=nice,
                nodes=nodes,
                #global_resources=True, 
            )
            brainsss.wait_for_job(job_id, logfile, com_path)
            
    if raw_warp:

        ######################
        ### Warp Raw Brain ###
        ######################

       for fly in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly)
            
            load_directory = os.path.join(fly_directory, "func_0", "background_subtraction")

            save_directory = os.path.join(fly_directory, "warp")
            if not os.path.exists(save_directory):
                os.mkdir(save_directory)
            
            brain_file = f"functional_channel_{ch_num}_moco.h5"
            
            args = {
                "logfile": logfile,
                "fly_directory": fly_directory,
                "load_directory": load_directory,
                "save_directory": save_directory,
                "brain_file": brain_file,
            }
            script = "raw_warp.py"
            job_id = brainsss.sbatch(
                jobname="raw_warp",
                script=os.path.join(scripts_path, script),
                modules=modules,
                args=args,
                logfile=logfile,
                time=2,
                cpus=32,
                mem='200GB',
                nice=nice,
                nodes=nodes,
                #global_resources=True, 
            )
            brainsss.wait_for_job(job_id, logfile, com_path)
    
    if timestamp_warp:

        #######################
        ### Warp timestamps ###
        #######################

       for fly in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly)
            
            load_directory = os.path.join(fly_directory, "func_0", "imaging")

            save_directory = os.path.join(fly_directory, "warp")
            if not os.path.exists(save_directory):
                os.mkdir(save_directory)
            
            brain_file = "timestamps.h5"
            
            args = {
                "logfile": logfile,
                "fly_directory": fly_directory,
                "load_directory": load_directory,
                "save_directory": save_directory,
                "brain_file": brain_file,
            }
            script = "timestamp_warp.py"
            job_id = brainsss.sbatch(
                jobname="timestamp_warp",
                script=os.path.join(scripts_path, script),
                modules=modules,
                args=args,
                logfile=logfile,
                time=2,
                cpus=32,
                mem='250GB',
                nice=nice,
                nodes=nodes,
                # global_resources=True, 
            )
            brainsss.wait_for_job(job_id, logfile, com_path)
            
    if blur:

    ############
    ### Blur ###
    ############

       for fly in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly)
            
            load_directory = os.path.join(fly_directory, "warp")

            save_directory = os.path.join(fly_directory, "dff")
            if not os.path.exists(save_directory):
                os.mkdir(save_directory)
            
            brain_file = f"functional_channel_{ch_num}_moco_warp.h5"
            
            args = {
                "logfile": logfile,
                "load_directory": load_directory,
                "save_directory": save_directory,
                "brain_file": brain_file,
            }
            script = "blur.py"
            job_id = brainsss.sbatch(
                jobname="blur",
                script=os.path.join(scripts_path, script),
                modules=modules,
                args=args,
                logfile=logfile,
                time=8,
                cpus=32,
                mem='200GB',
                nice=nice,
                nodes=nodes,
                #global_resources=True, 
            )
            brainsss.wait_for_job(job_id, logfile, com_path)

    if butter_highpass:

    ##############################
    ### BUTTER HIGHPASS FILTER ###
    ##############################

       for fly in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly)
            
            load_directory = os.path.join(fly_directory, "dff")

            save_directory = os.path.join(fly_directory, "dff")
            
            brain_file = f"functional_channel_{ch_num}_moco_warp_blurred.h5"
            
            args = {
                "logfile": logfile,
                "load_directory": load_directory,
                "save_directory": save_directory,
                "brain_file": brain_file,
            }
            script = "butter_highpass.py"
            job_id = brainsss.sbatch(
                jobname="butter_highpass",
                script=os.path.join(scripts_path, script),
                modules=modules,
                args=args,
                logfile=logfile,
                time=2,
                cpus=10,
                mem='200GB',
                nice=nice,
                nodes=nodes,
                #global_resources=True, 
            )
            brainsss.wait_for_job(job_id, logfile, com_path)
    
    if dff:

    #################
    ### Delta f/f ###
    #################

       for fly in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly)
            
            load_directory = os.path.join(fly_directory, "dff")

            save_directory = os.path.join(fly_directory, "dff")
            if not os.path.exists(save_directory):
                os.mkdir(save_directory)
            
            brain_file = f"functional_channel_{ch_num}_moco_warp_blurred_hpf.h5"
            # brain_file_l = f"functional_channel_{ch_num}_moco_warp_blurred_lpf.h5"
            
            args = {
                "logfile": logfile,
                "load_directory": load_directory,
                "save_directory": save_directory,
                "brain_file": brain_file,
            }
            script = "dff.py"
            job_id = brainsss.sbatch(
                jobname="dff",
                script=os.path.join(scripts_path, script),
                modules=modules,
                args=args,
                logfile=logfile,
                time=2,
                cpus=32,
                mem='250GB',
                nice=nice,
                nodes=nodes,
                #global_resources=True, 
            )
            brainsss.wait_for_job(job_id, logfile, com_path)

    if filter_bins:

    #######################
    ### Temporal Filter ###
    #######################

       for fly in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly)
            save_directory = os.path.join(fly_directory, "temp_filter")
            if not os.path.exists(save_directory):
                os.mkdir(save_directory)
            
            timestamp_file = "warp/timestamps_warp.h5"
            args = {
                "logfile": logfile,
                "fly_directory": fly_directory,
                "save_directory": save_directory,
                "timestamp_file": timestamp_file,
            }
            script = "filter_bins.py"
            job_id = brainsss.sbatch(
                jobname="filter_bins",
                script=os.path.join(scripts_path, script),
                modules=modules,
                args=args,
                logfile=logfile,
                time=10,
                cpus=10,
                mem='200GB',
                nice=nice,
                nodes=nodes,
                #global_resources=True, 
            )
            brainsss.wait_for_job(job_id, logfile, com_path)

    if relative_ts:

    ######################################
    ### Relative timestamps & odd mask ###
    ######################################

       for fly in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly)
            save_directory = os.path.join(fly_directory, "temp_filter")
            if not os.path.exists(save_directory):
                os.mkdir(save_directory)
            
            timestamp_file = "warp/timestamps_warp.h5"
            filter_file = "filter_needs.h5"
            args = {
                "logfile": logfile,
                "fly_directory": fly_directory,
                "save_directory": save_directory,
                "timestamp_file": timestamp_file,
                "filter_file": filter_file,
            }
            script = "relative_ts.py"
            job_id = brainsss.sbatch(
                jobname="relative_ts",
                script=os.path.join(scripts_path, script),
                modules=modules,
                args=args,
                logfile=logfile,
                time=10,
                cpus=32,
                mem='250GB',
                nice=nice,
                nodes=nodes,
                #global_resources=True, 
            )
            brainsss.wait_for_job(job_id, logfile, com_path)
        
    
    if temp_filter:

    #######################
    ### Temporal Filter ###
    #######################

       for fly in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly)
            load_directory = os.path.join(fly_directory, "dff")
            save_directory = os.path.join(fly_directory, "temp_filter")
            if not os.path.exists(save_directory):
                os.mkdir(save_directory)
            
            brain_file = f"functional_channel_{ch_num}_moco_warp_blurred_hpf_dff.h5"
            timestamp_file = "warp/timestamps_warp.h5"
            filter_file = "filter_needs.h5"
            ts_rel_file = "ts_rel_odd_mask.h5"
            args = {
                "logfile": logfile,
                "fly_directory": fly_directory,
                "load_directory": load_directory,
                "save_directory": save_directory,
                "brain_file": brain_file,
                "timestamp_file": timestamp_file,
                "filter_file": filter_file,
                "ts_rel_file": ts_rel_file,
            }
            script = "temp_filter.py"
            job_id = brainsss.sbatch(
                jobname="temp_filter",
                script=os.path.join(scripts_path, script),
                modules=modules,
                args=args,
                logfile=logfile,
                time=10,
                cpus=32,
                mem='250GB',
                nice=nice,
                nodes=nodes,
                #global_resources=True, 
            )
            brainsss.wait_for_job(job_id, logfile, com_path)
    if whole_brain_interp:

    ##########################
    ### Whole brain interp ###
    ##########################

        for fly in fly_dirs:
                fly_directory = os.path.join(dataset_path, fly)
                load_directory = os.path.join(fly_directory, "temp_filter")
                save_directory = os.path.join(fly_directory, "temp_filter")
                
                tf_file = f"functional_channel_{ch_num}_moco_warp_blurred_hpf_dff_filtered.h5"
                args = {
                    "logfile": logfile,
                    "fly_directory": fly_directory,
                    "load_directory": load_directory,
                    "save_directory": save_directory,
                    "tf_file": tf_file,
                }
                script = "whole_brain_interp.py"
                job_id = brainsss.sbatch(
                    jobname="interp",
                    script=os.path.join(scripts_path, script),
                    modules=modules,
                    args=args,
                    logfile=logfile,
                    time=10,
                    cpus=32,
                    mem='250GB',
                    nice=nice,
                    nodes=nodes,
                    #global_resources=True, 
                )
                brainsss.wait_for_job(job_id, logfile, com_path)
    if h5_to_nii:

        #################
        ### H5 TO NII ###
        #################

        for func in funcs:
            name = f"functional_channel_{ch_num}_moco_warp_blurred_hpf_dff.h5"
            args = {
                "logfile": logfile,
                "h5_path": os.path.join(
                    func, name
                ),
            }
            script = "h5_to_nii.py"
            job_id = brainsss.sbatch(
                jobname="h5tonii",
                script=os.path.join(scripts_path, script),
                modules=modules,
                args=args,
                logfile=logfile,
                time=2,
                mem=10,
                nice=nice,
                nodes=nodes,
            )
            brainsss.wait_for_job(job_id, logfile, com_path)

    if make_supervoxels:
        for fly in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly)
            load_directory = os.path.join(fly_directory, "temp_filter")
            for func in funcs:
                brain_file = f"functional_channel_{ch_num}_moco_warp_blurred_hpf_dff_filtered.h5"
                args = {"logfile": logfile, 
                        "func_path": func, 
                        'brain_file': brain_file, 
                        'ch_num': ch_num,
                        "load_directory": load_directory,
                        }
                script = "make_supervoxels.py"
                job_id = brainsss.sbatch(
                    jobname="supervox",
                    script=os.path.join(scripts_path, script),
                    modules=modules,
                    args=args,
                    logfile=logfile,
                    cpus=20,
                    mem='100GB',
                    nice=nice,
                    nodes=nodes,
                )
            brainsss.wait_for_job(job_id, logfile, com_path)
            
    if build_STA:
        for fly in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly)
            load_directory = os.path.join(fly_directory, "temp_filter")
            save_directory = os.path.join(fly_directory, "STA")
            if not os.path.exists(save_directory):
                os.mkdir(save_directory)
            tf_file = f"functional_channel_{ch_num}_moco_warp_blurred_hpf_dff_filtered.h5"
            args = {"logfile": logfile, 
                    "fly_directory": fly_directory, 
                    'tf_file': tf_file, 
                    'ch_num': ch_num,
                    "load_directory": load_directory,
                    "save_directory": save_directory,
                    }
            script = "build_STA.py"
            job_id = brainsss.sbatch(
                jobname="STA",
                script=os.path.join(scripts_path, script),
                modules=modules,
                args=args,
                logfile=logfile,
                cpus=20,
                mem='100GB',
                nice=nice,
                nodes=nodes,
            )
            brainsss.wait_for_job(job_id, logfile, com_path)

    ############
    ### Done ###
    ############

    brainsss.print_footer(logfile, width)


if __name__ == "__main__":
    main(json.loads(sys.argv[1]))
    # parser = argparse.ArgumentParser()
    # parser.add_argument("PWD")
    # args = parser.parse_args()
    # main(args)
