# brainsss
This package performs preprocessing and analysis of volumetric neural data on sherlock. At its core, brainsss is a wrapper to interface with Slurm via python. It can handle complex submission of batches of jobs with job dependencies and makes it easy to pass variables between jobs. It also has full logging of job progress, output, and errors.

## Installing:

Log onto sherlock (ssh sunetid@login.sherlock.stanford.edu)  
Add our lab's custom modules to you modulepath (allows access to ANTs, a brain-warping tool) by adding  
```export MODULEPATH=/home/groups/trc/modules:$MODULEPATH``` to your
```~/.bashrc```  
you will need to source to load the changes:  
```source ~/.bashrc```

Navigate to where you would like to install this package, then:  
```shell
> git clone https://github.com/ClandininLab/brainsss.git
> cd brainsss
> ml python/3.6.1
> pip3 install -e . --user
```

Install required python packages:
```shell
  > pip3 install pyfiglet
  > pip3 install psutil
```

Create your user preferences:  
- Navigate to /brainsss/users
- Copy existing brezovec.json file
- rename with your sunetid and adjust preferences as you desire (more info about variables below)

## Usage:

There are currently two main ways to use this package:
1) Adopt a specific fly directory structure so you can take advantage of the entire pipeline automation.
      - Your imaging data should be saved like:

          ```
          /experiment_folder
              /fly_num
                  /func_num
                       functional imaging data
                  /anat_num
                       anatomical imaging data
          ```

      - So for me an imaging day might look like:
    
          ```
          /20220307
              /fly_0
                   /func_0
                   /anat_0
              /fly_1
                  /func_0
                  /anat_0
          ```

      - This directory should be uploaded to your imports folder on Oak (probably via BrukerBridge), and set appropriately in your user settings.
      - Now, make sure you have defined a dataset_path in your settings. This directory is where flies will be "built", meaning:
        -   fly data will be copied from the imports_path to dataset_path
        -   each fly will recieve a new unique id_num beginning at 0, growing as flies are added over time
        -   files will be renamed for convenience. for example, long bruker names like "TSeries-12172018-1322-002_channel_1.nii" will be changed to functional_channel_1.nii if it was in a func directory, etc.
        -   flies will be added to an excel spreadsheet to help track metadata
      - When you are ready to build flies navigate to brainsss/scripts
      - Launch the job with ```sbatch preprocessing.sh --build_flies 20220307```. Swap the date to match the name of the directory in your imports path. You can watch the progress of your job by navigating to brainsss/scripts/logs. A new logfile with date-time will be created. You can view it with ```nano 20220310-135620.txt``` or whatever the name is. Note that if an error happened very early during the setup of this job this file will not be created but the error will be printed to mainlog.out.
      - After the flies are built the script will automatically continue executing the preprocessing steps as set in your preferences and the output will be saved in the same log.

2) Run specific preprocessing or analysis steps.
      - Launch the job ```sbatch preprocessing.sh``` with specific flags. For example, if you would like to motion correct a file: ```sbatch preprocessing.sh --moco --flies fly_006,fly007```
      - These flies must be in your dataset_path
      - These fly folders must contain a subfolder with 'func' or 'anat' in the name.
      - This func or anat folder must have a subfolder called imaging
      - This imaging folder must contain a file named functional_channel_1.nii (or anatomical_channel_1.nii), which will be motion corrected.
      - If a functional_channel_2.nii exists, the registration parameters from channel 1 will be applied to channel 2.
      - the --flies flag accepts a comma separated list (or one fly)
      - if you want to moco only func or only anat, add the flag --dirtype func (or --dirtype anat).
      - Other preprocessing steps currently implemented are --fictrac_qc, --STB (stimulus triggered behavior), --bleaching_qc, and --temporal_mean_brain.

A note that should be mentioned: to achieve creation of a common log file, I have stolen the print() function. So, for anything you want to print, you must use the printlog() function, but otherwise it is the same.

Here is a little detail on the guts:
preprocessing.sh will always be called via sbatch to start the program. This will start preprocessing.py, which will use a single core and manage the submission of jobs. Two core functions are:
- brainsss.sbatch
- brainsss.wait_for_job   
These are in the utils.py file if you want to check them out.
Essentially, you can tell brainsss.sbatch what python script you would like to run, as well as which modules to load, memory and time, etc.
The function will return the job_id that was assigned to it via slurm. Then, you can use brainsss.wait_for_job to wait until this job is complete before continuing through main.py
