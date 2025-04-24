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
    dataset_path = settings["dataset_path"]
    later_path=settings["later_path"]

    ### Grab buildflies from command line args first since it will impact parsing
    if args["BEST_FLIES"] == "":
        best_flies = False
    else:
        best_flies = True
        fly_list=[208,209,210,217,218,226,227,228,233,234,239,240,241,242,249,250]
        num_flies = len(fly_list)
        fly_dirs = []
        for fly in fly_list:
            fly_name= f"fly_{fly}"
            fly_dir=os.path.join(dataset_path, fly_name)
            fly_dirs.append(fly_dir)
    if args["POSTPROCESS"] == "":
        # printlog('not building flies')
        post_process = False
    else:
        # printlog('building flies')
        post_process = True
        if best_flies:
            dirs_to_process= fly_dirs
            printlog(f"Best flies: {dirs_to_process}")  
        else:
            dirs_to_process = args["POSTPROCESS"].split(",")
            for i in range(len(fly_dirs)):
                if not fly_dirs[i].startswith("fly_"):
                    fly_dirs[i] = "fly_" + fly_dirs[i]
            printlog(f"Flies to process: {dirs_to_process}")
    
        # # dir_to_build = args["BUILDFLIES"]
        # fly_dirs = args["PREPROCESS"].split(",")
        # ### add 'fly_' to beginning if it isn't there
        # for i in range(len(fly_dirs)):
        #     if not fly_dirs[i].startswith("fly_"):
        #         fly_dirs[i] = "fly_" + fly_dirs[i]

#     ### Parse user settings
#     
#     if postprocess:
#         filter_bins = brainsss.parse_true_false(settings.get("filter_bins", False))
#         relative_ts = brainsss.parse_true_false(settings.get("relative_ts", False))
#         temp_filter = brainsss.parse_true_false(settings.get("temp_filter", False))
#         whole_brain_interp = brainsss.parse_true_false(settings.get("whole_brain_interp", False))
#         make_supervoxels = brainsss.parse_true_false(
#             settings.get("make_supervoxels", False)
#         )
#     else:
#         filter_bins = False
#         relative_ts = False
#         temp_filter = False
#         whole_brain_interp = False
#         make_supervoxels = False

#     ### Parse remaining command line args
#     if args["FLIES"] == "":
#         # printlog('no flies specified')
#         fly_dirs = None
#     else:
#         fly_dirs = args["FLIES"].split(",")

#         ### add 'fly_' to beginning if it isn't there
#         for i in range(len(fly_dirs)):
#             if not fly_dirs[i].startswith("fly_"):
#                 fly_dirs[i] = "fly_" + fly_dirs[i]

#     if args["DIRTYPE"] == "":
#         # printlog('no dirtype specified')
#         dirtype = None
#     else:
#         dirtype = args["DIRTYPE"].lower()
#         # printlog('dirtype is {}'.format(dirtype))

#     # These command line arguments will be empty unless the flag is called from the command line
#     if args["FILTER_BINS"] != "":
#         filter_bins = True
#     if args["RELATIVE_TS"] != "":
#         relative_ts = True
#     if args["TEMP_FILTER"] != "":
#         temp_filter = True
#     if args["WHOLE_BRAIN_INTERP"] != "":
#         whole_brain_interp = True
#     if args["MAKE_SUPERVOXELS"] != "":
#         make_supervoxels = True

#     ### catch errors with incorrect argument combos
#     # if fly builder is false, fly dirs must be provided
#     if not postprocess and fly_dirs is None:
#         printlog(
#             "ERROR: you did not provide a directory to process flies from, nor a fly directory to process."
#         )
#         printlog("Aborting.")
#         return

#     #################################
#     ############# BEGIN #############
#     #################################

#     if postprocess:

#         #######################
#         ### post processing ###
#         #######################

#         flagged_dir = os.path.join(dataset_path, fly_dirs)
#         args = {
#             "logfile": logfile,
#             "flagged_dir": flagged_dir,
#             "dataset_path": dataset_path,
#             "fly_dirs": fly_dirs,
#             "user": user,
#         }
#         script = "analysis_builder.py"
#         job_id = brainsss.sbatch(
#             jobname="analyze",
#             script=os.path.join(scripts_path, script),
#             modules=modules,
#             args=args,
#             logfile=logfile,
#             time=3,
#             cpus=1,
#             nice=nice,
#             nodes=nodes,
#         )
#         brainsss.wait_for_job(job_id, logfile, com_path)
       

#     if filter_bins:

#     #######################
#     ### Temporal Filter ###
#     #######################

#        for fly in fly_dirs:
#             fly_directory = os.path.join(dataset_path, fly)
#             save_directory = os.path.join(fly_directory, "temp_filter")
#             if not os.path.exists(save_directory):
#                 os.mkdir(save_directory)
            
#             timestamp_file = "warp/timestamps_warp.h5"
#             args = {
#                 "logfile": logfile,
#                 "fly_directory": fly_directory,
#                 "save_directory": save_directory,
#                 "timestamp_file": timestamp_file,
#             }
#             script = "filter_bins.py"
#             job_id = brainsss.sbatch(
#                 jobname="filter_bins",
#                 script=os.path.join(scripts_path, script),
#                 modules=modules,
#                 args=args,
#                 logfile=logfile,
#                 time=10,
#                 cpus=10,
#                 mem='200GB',
#                 nice=nice,
#                 nodes=nodes,
#                 #global_resources=True, 
#             )
#             brainsss.wait_for_job(job_id, logfile, com_path)

#     if relative_ts:

#     ######################################
#     ### Relative timestamps & odd mask ###
#     ######################################

#        for fly in fly_dirs:
#             fly_directory = os.path.join(dataset_path, fly)
#             save_directory = os.path.join(fly_directory, "temp_filter")
#             if not os.path.exists(save_directory):
#                 os.mkdir(save_directory)
            
#             timestamp_file = "warp/timestamps_warp.h5"
#             filter_file = "filter_needs.h5"
#             args = {
#                 "logfile": logfile,
#                 "fly_directory": fly_directory,
#                 "save_directory": save_directory,
#                 "timestamp_file": timestamp_file,
#                 "filter_file": filter_file,
#             }
#             script = "relative_ts.py"
#             job_id = brainsss.sbatch(
#                 jobname="relative_ts",
#                 script=os.path.join(scripts_path, script),
#                 modules=modules,
#                 args=args,
#                 logfile=logfile,
#                 time=10,
#                 cpus=32,
#                 mem='250GB',
#                 nice=nice,
#                 nodes=nodes,
#                 #global_resources=True, 
#             )
#             brainsss.wait_for_job(job_id, logfile, com_path)
        
    
#     if temp_filter:

#     #######################
#     ### Temporal Filter ###
#     #######################

#        for fly in fly_dirs:
#             fly_directory = os.path.join(dataset_path, fly)
#             load_directory = os.path.join(fly_directory, "dff")
#             save_directory = os.path.join(fly_directory, "temp_filter")
#             if not os.path.exists(save_directory):
#                 os.mkdir(save_directory)
            
#             brain_file = f"functional_channel_{ch_num}_moco_warp_blurred_hpf_dff.h5"
#             timestamp_file = "warp/timestamps_warp.h5"
#             filter_file = "filter_needs.h5"
#             ts_rel_file = "ts_rel_odd_mask.h5"
#             args = {
#                 "logfile": logfile,
#                 "fly_directory": fly_directory,
#                 "load_directory": load_directory,
#                 "save_directory": save_directory,
#                 "brain_file": brain_file,
#                 "timestamp_file": timestamp_file,
#                 "filter_file": filter_file,
#                 "ts_rel_file": ts_rel_file,
#             }
#             script = "temp_filter.py"
#             job_id = brainsss.sbatch(
#                 jobname="temp_filter",
#                 script=os.path.join(scripts_path, script),
#                 modules=modules,
#                 args=args,
#                 logfile=logfile,
#                 time=10,
#                 cpus=32,
#                 mem='250GB',
#                 nice=nice,
#                 nodes=nodes,
#                 #global_resources=True, 
#             )
#             brainsss.wait_for_job(job_id, logfile, com_path)
#     if whole_brain_interp:

#     ##########################
#     ### Whole brain interp ###
#     ##########################

#         for fly in fly_dirs:
#                 fly_directory = os.path.join(dataset_path, fly)
#                 load_directory = os.path.join(fly_directory, "temp_filter")
#                 save_directory = os.path.join(fly_directory, "temp_filter")
                
#                 tf_file = f"functional_channel_{ch_num}_moco_warp_blurred_hpf_dff_filtered.h5"
#                 args = {
#                     "logfile": logfile,
#                     "fly_directory": fly_directory,
#                     "load_directory": load_directory,
#                     "save_directory": save_directory,
#                     "tf_file": tf_file,
#                 }
#                 script = "whole_brain_interp.py"
#                 job_id = brainsss.sbatch(
#                     jobname="interp",
#                     script=os.path.join(scripts_path, script),
#                     modules=modules,
#                     args=args,
#                     logfile=logfile,
#                     time=10,
#                     cpus=32,
#                     mem='250GB',
#                     nice=nice,
#                     nodes=nodes,
#                     #global_resources=True, 
#                 )
#                 brainsss.wait_for_job(job_id, logfile, com_path)
#     if h5_to_nii:

#         #################
#         ### H5 TO NII ###
#         #################

#         for func in funcs:
#             name = f"functional_channel_{ch_num}_moco_warp_blurred_hpf_dff.h5"
#             args = {
#                 "logfile": logfile,
#                 "h5_path": os.path.join(
#                     func, name
#                 ),
#             }
#             script = "h5_to_nii.py"
#             job_id = brainsss.sbatch(
#                 jobname="h5tonii",
#                 script=os.path.join(scripts_path, script),
#                 modules=modules,
#                 args=args,
#                 logfile=logfile,
#                 time=2,
#                 mem=10,
#                 nice=nice,
#                 nodes=nodes,
#             )
#             brainsss.wait_for_job(job_id, logfile, com_path)

#     if make_supervoxels:
#         for fly in fly_dirs:
#             fly_directory = os.path.join(dataset_path, fly)
#             load_directory = os.path.join(fly_directory, "temp_filter")
#             for func in funcs:
#                 brain_file = f"functional_channel_{ch_num}_moco_warp_blurred_hpf_dff_filtered.h5"
#                 args = {"logfile": logfile, 
#                         "func_path": func, 
#                         'brain_file': brain_file, 
#                         'ch_num': ch_num,
#                         "load_directory": load_directory,
#                         }
#                 script = "make_supervoxels.py"
#                 job_id = brainsss.sbatch(
#                     jobname="supervox",
#                     script=os.path.join(scripts_path, script),
#                     modules=modules,
#                     args=args,
#                     logfile=logfile,
#                     cpus=20,
#                     mem='100GB',
#                     nice=nice,
#                     nodes=nodes,
#                 )
#             brainsss.wait_for_job(job_id, logfile, com_path)

#     ############
#     ### Done ###
#     ############

#     brainsss.print_footer(logfile, width)


# if __name__ == "__main__":
#     main(json.loads(sys.argv[1]))
#     # parser = argparse.ArgumentParser()
#     # parser.add_argument("PWD")
#     # args = parser.parse_args()
#     # main(args)
