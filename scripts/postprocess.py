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
    scripts_path = args["PWD"]
    printlog(f"PWD: {scripts_path}")
    com_path = os.path.join(scripts_path, "com")
    user = scripts_path.split("/")[3]
    settings = brainsss.load_user_settings(user, scripts_path)
    


    ### Grab postprocess & redo from command line args first since it will impact parsing

    if args["POSTPROCESS"] == "":
        # printlog('not building flies')
        postprocess = False
    else:
        # printlog('building flies')
        postprocess = True
    if args["REDO"] == "":
        redo = False
    else:
        redo = True
    
        
    ### Parse user settings
    dataset_path = settings["dataset_path"]
    later_path=settings["later_path"]
    
    if postprocess:
        filter_bins = brainsss.parse_true_false(settings.get("filter_bins", False))
        relative_ts = brainsss.parse_true_false(settings.get("relative_ts", False))
        temp_filter = brainsss.parse_true_false(settings.get("temp_filter", False))
        make_supervoxels = brainsss.parse_true_false(settings.get("make_supervoxels", False))
        channel_change = brainsss.parse_true_false(settings.get("channel_change", False))
        tf_to_STA = brainsss.parse_true_false(settings.get("tf_to_STA", False))
        build_STA = brainsss.parse_true_false(settings.get("build_STA", False))
        
    else:
        filter_bins = False
        relative_ts = False
        temp_filter = False
        make_supervoxels = False
        channel_change = False
        tf_to_STA = False
        build_STA = False
    
     ### Parse remaining command line args
    if args["BEST_FLIES"] == "" and args["FLIES"] == "":
        printlog('no flies specified')
        fly_dirs = None
    elif args["BEST_FLIES"] != "":
        # fly_list = [234,239,240,241,242,249,250]
        fly_list=[208,209, 210,217,218,226,227,228,233,234,239,240,241,242,249,250]
        num_flies = len(fly_list)
        printlog(f"Number of flies to process: {num_flies}")
        fly_dirs = []
        for fly in fly_list:
            fly_name= f"fly_{fly}"
            fly_dirs.append(fly_name)
        printlog(f"Flies to be processed {fly_dirs}")
    elif args["FLIES"] != "":
        fly_dirs = args["FLIES"].split(",")
        printlog(f"Fly being processed: {fly_dirs}")
    ### add 'fly_' to beginning if it isn't there
        for i in range(len(fly_dirs)):
            if not fly_dirs[i].startswith("fly_"):
                fly_dirs[i] = "fly_" + fly_dirs[i] 
            # printlog(f"Flies to process: {dirs_to_process}")
        
    if args["EVENTS"] == "":
        # printlog('not building flies')
        event = None
    else:
        # printlog('building flies')
        event = args["EVENTS"].lower()          
        
        
    # These command line arguments will be empty unless the flag is called from the command line
    if args["FILTER_BINS"] != "":
        filter_bins = True
    if args["RELATIVE_TS"] != "":
        relative_ts = True
    if args["TEMP_FILTER"] != "":
        temp_filter = True
    if args["MAKE_SUPERVOXELS"] != "":
        make_supervoxels = True
    if args["CHANNEL_CHANGE"] != "":
        channel_change = True
    if args["TF_TO_STA"] != "":
        tf_to_STA = True
    if args["BUILD_STA"] != "":
        build_STA = True
#     #################################
#     ############# BEGIN #############
#     #################################

    if channel_change:
        ch_num = '1'
    else:
        ch_num = '2'
    printlog(f"Channel number: {ch_num}")
        

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
                "redo": redo,
                "later_path": later_path,
                "event": event,
                "fly": fly,
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
                "redo": redo,
                "event": event,
                "later_path": later_path,
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
                "redo": redo,
                "later_path": later_path,
                "event": event,
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

    if make_supervoxels:
        for fly in fly_dirs:
            fly_directory = os.path.join(dataset_path, fly)
            load_directory = os.path.join(fly_directory, "temp_filter")
            for func in funcs:
                brain_file = f"functional_channel_{ch_num}_moco_warp_blurred_hpf_dff_filtered.h5"
                args = {"logfile": logfile,
                        "redo": redo,
                        "func_path": func, 
                        "brain_file": brain_file, 
                        "ch_num": ch_num,
                        "event": event,
                        "later_path": later_path,
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

    if tf_to_STA:
        later_directory = os.path.join(later_path, "temp_filter")
        args = {"logfile": logfile, 
                "later_directory": later_directory, 
                "event": event,
                "ch_num": ch_num,
                }
        script = "tf_to_STA.py"
        job_id = brainsss.sbatch(
            jobname="tf_to_STA",
            script=os.path.join(scripts_path, script),
            modules=modules,
            args=args,
            logfile=logfile,
            time=48,
            cpus=32,
            mem='250GB',
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
            args = {"logfile": logfile, 
                    "fly_directory": fly_directory,
                    "redo": redo,
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
                cpus=32,
                mem='250GB',
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
