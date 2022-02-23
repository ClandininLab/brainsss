import numpy as np
import sys
import os
import json
import matplotlib.pyplot as plt
import matplotlib as mpl
import brainsss
import pandas as pd
import scipy
from scipy.interpolate import interp1d

def main(args):

    logfile = args['logfile']
    directory = args['directory'] # directory will be a full path to a func/fictrac folder
    width = 120
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    fictrac_raw = load_fictrac(directory)

    #fly = os.path.split(os.path.split(directory)[0])[1]
    #expt = os.path.split(directory)[1]
    full_id = ', '.join(directory.split('/')[-3:-1])

    resolution = 10 #desired resolution in ms
    expt_len = 1000*30*60
    fps = 50 #of fictrac camera
    behaviors = ['dRotLabY', 'dRotLabZ']
    fictrac = {}
    for behavior in behaviors:
        if behavior == 'dRotLabY': short = 'Y'
        elif behavior == 'dRotLabZ': short = 'Z'
        fictrac[short] = smooth_and_interp_fictrac(fictrac_raw, fps, resolution, expt_len, behavior)
    xnew = np.arange(0,expt_len,resolution)

    make_2d_hist(fictrac, directory, full_id, save=True, fixed_crop=True)
    make_velocity_trace(fictrac, directory, full_id, xnew, save=True)

def make_2d_hist(fictrac, fictrac_folder, full_id, save=True, fixed_crop=True):
        plt.figure(figsize=(10,10))
        norm = mpl.colors.LogNorm()
        plt.hist2d(fictrac['Y'],fictrac['Z'],bins=100,cmap='Blues',norm=norm);
        plt.ylabel('Rotation, deg/sec')
        plt.xlabel('Forward, mm/sec')
        plt.title('Behavior 2D hist {}'.format(full_id))
        plt.colorbar()
        name = 'fictrac_2d_hist.png'
        if fixed_crop:
            plt.ylim(-400,400)
            plt.xlim(-10,15)
            name = 'fictrac_2d_hist_fixed.png'
        if save:
            fname = os.path.join(fictrac_folder, name)
            plt.savefig(fname,dpi=100,bbox_inches='tight')
            
def make_velocity_trace(fictrac, fictrac_folder, full_id, xnew, save=True):
    plt.figure(figsize=(10,10))
    plt.plot(xnew/1000,fictrac['Y'],color='xkcd:dusk')
    plt.ylabel('forward velocity mm/sec')
    plt.xlabel('time, sec')
    plt.title(full_id)
    if save:
        fname = os.path.join(fictrac_folder, 'velocity_trace.png')
        plt.savefig(fname,dpi=100,bbox_inches='tight')

def load_fictrac(directory, file='fictrac.dat'):
    """ Loads fictrac data from .dat file that fictrac outputs.
    To-do: change units based on diameter of ball etc.
    For speed sanity check, instead remove bad frames so we don't have to throw out whole trial.
    Parameters
    ----------
    directory: string of full path to file
    file: string of file name
    Returns
    -------
    fictrac_data: pandas dataframe of all parameters saved by fictrac """

    for item in os.listdir(directory):
      if '.dat' in item:
        file = item

    with open(os.path.join(directory, file),'r') as f:
        df = pd.DataFrame(l.rstrip().split() for l in f)

        # Name columns
        df = df.rename(index=str, columns={0: 'frameCounter',
                                       1: 'dRotCamX',
                                       2: 'dRotCamY',
                                       3: 'dRotCamZ',
                                       4: 'dRotScore',
                                       5: 'dRotLabX',
                                       6: 'dRotLabY',
                                       7: 'dRotLabZ',
                                       8: 'AbsRotCamX',
                                       9: 'AbsRotCamY',
                                       10: 'AbsRotCamZ',
                                       11: 'AbsRotLabX',
                                       12: 'AbsRotLabY',
                                       13: 'AbsRotLabZ',
                                       14: 'positionX',
                                       15: 'positionY',
                                       16: 'heading',
                                       17: 'runningDir',
                                       18: 'speed',
                                       19: 'integratedX',
                                       20: 'integratedY',
                                       21: 'timeStamp',
                                       22: 'sequence'})

        # Remove commas
        for column in df.columns.values[:-1]:
            df[column] = [float(x[:-1]) for x in df[column]]

        fictrac_data = df
                
    # sanity check for extremely high speed (fictrac failure)
    speed = np.asarray(fictrac_data['speed'])
    max_speed = np.max(speed)
    if max_speed > 10:
        raise Exception('Fictrac ball tracking failed (reporting impossibly high speed).')
    return fictrac_data

def smooth_and_interp_fictrac(fictrac, fps, resolution, expt_len, behavior, timestamps=None, smoothing=25):
    camera_rate = 1/fps * 1000 # camera frame rate in ms
    
    x_original = np.arange(0,expt_len,camera_rate)
    fictrac_smoothed = scipy.signal.savgol_filter(np.asarray(fictrac[behavior]),smoothing,3)
    fictrac_interp_temp = interp1d(x_original, fictrac_smoothed, bounds_error = False)
    xnew = np.arange(0,expt_len,resolution) #0 to last time at subsample res

    if timestamps is None:
      fictrac_interp = fictrac_interp_temp(xnew)
    else:
      fictrac_interp = fictrac_interp_temp(timestamps[:,25])

    # convert units for common cases
    sphere_radius = 4.5e-3 # in m
    if behavior in ['dRotLabY']:
        ''' starts with units of rad/frame
        * sphere_radius(m); now in m/frame
        * fps; now in m/sec
        * 1000; now in mm/sec '''
        
        fictrac_interp = fictrac_interp * sphere_radius * fps * 1000 # now in mm/sec
        
    if behavior in ['dRotLabZ']:
        ''' starts with units of rad/frame
        * 180 / np.pi; now in deg/frame
        * fps; now in deg/sec '''
        
        fictrac_interp = fictrac_interp * 180 / np.pi * fps
    
    # Replace Nans with zeros (for later code)
    np.nan_to_num(fictrac_interp, copy=False);
    
    return fictrac_interp

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))