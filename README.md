# brainsss
Preprocessing of volumetric neural data on sherlock (motion correction, zscoring, etc)

At its core, brainsss is a wrapper to interface with Slurm via python. It can handle complex submission of batches of jobs with job dependencies and makes it easy to pass variables between jobs. It also has full logging of job progress, output, and errors.

For clarity, this package currently only contains a few functions to demonstrate its usage (and includes some demo data). One function that may be particularly useful is motion correction.

Installing the package:
login to sherlock and navigate to where you would like to install this package.
```shell
> git clone https://github.com/ClandininLab/brainsss.git
> cd brainsss
> ml python/3.6.1
> pip3 install -e . --user
```
change the paths:
  - in scripts/main.sh, line 13 must point to scripts/main.py
  - in scripts/main.py, scripts_path, com_path, and dataset_path must be set

Running the demo:
```shell
cd scripts
sbatch main.sh
```
progress and errors will be printed into a file in the scripts/logs folder
