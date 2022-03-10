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
1) Adopt a specific fly directory structure so you can take advantage of the entire pipeline automation

Your imaging data should be saved like:
    
```
/experiment_folder
    /fly_num
        /func_num
             functional imaging data
        /anat_num
             anatomical imaging data
```

So for me an imaging day might look like:
    
```
/20220307
    /fly_0
         /func_0
         /anat_0
    /fly_1
        /func_0
        /anat_0
```

-This should be uploaded to your imports folder on Oak (probably via BrukerBridge)

Running the demo (Broken in current version. Will fix at some point.):  
```shell
cd scripts
sbatch main.sh
```
progress and errors will be printed into a file in the scripts/logs folder.  
mainlog.out keeps track of all the times the script was run, as well as high-level errors. 
Once the job launches, a log with a date-time string will be created and messages will continue to be appended to it until the job is complete.  
The demo should perform and print information about Fictrac QC, Bleaching QC, creation of meanbrains, Motion Correction, and Z-scoring.  

Example log file:
![example_log_file](example_log_file.png)

*** (Jolie) - you will possibly see errors in the mainlog.out file, about certain packages not being able to import. You will need to install these packages using pip3 install. Let me know if this happens, and if so which packages you needed to install so I can add it to this readme. And let me know if you need help with this, but basically you will type ```pip3 install "package name" --user```

Upon completion, the demo_data directory should contain some new files:
- /fly_001/fictrac will contain a velocity trace and a 2D histogram
- /fly_001 will contain a "bleaching" figure, the meanbrains for each channel, as well as the z-scored motion-corrected green-channel brain
- /fly_001/moco will contain each channel motion corrected, as well as a figure of x/y/z translations involved in the motion correction.

A note that should be mentioned: to achieve creation of a common log file, I have stolen the print() function. So, for anything you want to print, you must use the printlog() function, but otherwise it is the same.

Here is a little more detail on how to use this package as a wrapper for job submission:
main.sh will always be called via sbatch to start the program. This will start main.py, which will use a single core and manage the submission of jobs. Two core functions are:
- brainsss.sbatch
- brainsss.wait_for_job   
These are in the utils.py file if you want to check them out.
Essentially, you will tell brainsss.sbatch what python script you would like to run, as well as which modules to load, memory and time, etc.
The function will return the job_id that was assigned to it via slurm. Then, you can use brainsss.wait_for_job to wait until this job is complete before continuing through main.py
