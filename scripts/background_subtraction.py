import os
import sys
import numpy as np
import argparse
import subprocess
import json
import nibabel as nib
import brainsss
import h5py
from scipy import signal
import datetime
from skimage import io
import matplotlib.pyplot as plt
from time import time
from time import strftime
from time import sleep

class BgRemover3D:

    def __init__(self, img_path, half_wid=25):
        self.path = img_path
        self.half_wid = half_wid
        # self.img shoud have dimension x, y, z, t here, x is along the line scan direction
        if '.nii' in img_path:
            self.img = np.asarray(nib.load(img_path).get_data().squeeze(), dtype='float32')
        elif '.h5' in img_path:
            with h5py.File(img_path, "r") as f:
                self.img = f['data'][:]
        else:
            print('format not supported!')
        self.make_savedir()
    
    def make_savedir(self):
        working_dir = os.path.dirname(self.path)
        saving_dir = os.path.join(working_dir, 'background_subtraction')
        if not os.path.exists(saving_dir):
            os.mkdir(saving_dir)
        self.saving_dir = saving_dir
        self.file_head = self.path.split('.')[0].split('/')[-1]
    
    def draw_bg(self):
        half_wid = self.half_wid
        wid = 2*half_wid
        kernel = np.ones(wid)/wid
        template = np.mean(self.img, axis=-1)
        template = np.moveaxis(template, (0, 2), (2, 0))
        bg_ind = []
        for patch in template:
            bg_ind_tmp = []
            for line in patch:
                tmp = np.convolve(line, kernel, 'valid')
                bg_center = np.argmin(tmp) + half_wid
                bg_ind_tmp.append([bg_center-half_wid, bg_center+half_wid])
            bg_ind.append(bg_ind_tmp)
            
        self.bg_ind = bg_ind

    def show_bg(self):
        bg_ind = self.bg_ind
        show_bg = np.mean(self.img, axis=-1)
        mv = np.round(np.max(show_bg))
        show_bg = np.moveaxis(show_bg, (0, 2), (2, 0))
        for i in range(show_bg.shape[0]):
            for j in range(show_bg.shape[1]):
                show_bg[i, j, bg_ind[i][j][0]:bg_ind[i][j][1]] = mv
        
        save_name = os.path.join(self.saving_dir, self.file_head+'_bg_selection.tif')
        io.imsave(save_name, np.round(show_bg).astype('int16'))
        

    def remove_bg(self, offset=300):
        bg_ind = self.bg_ind
        img = np.moveaxis(self.img, (0,1,2,3), (3,1,2,0))
        out = np.zeros_like(img)
        for ind_y in range(img.shape[1]):
            for ind_z in range(img.shape[2]):
                patch = img[:, ind_y, ind_z, :]
                bg_patch = img[:, ind_y, ind_z, bg_ind[ind_z][ind_y][0]:bg_ind[ind_z][ind_y][1]]
                bg = bg_patch.mean(axis=-1)
                patch = patch-bg[None].T
                out[:, ind_y, ind_z, :] = patch
        self.out = np.moveaxis(out, (0,1,2,3), (3,1,2,0))

    def show_spectrum(self, fs=180):
        half_wid = 5
        half_y = 15 
        kernel2d = np.ones((half_wid*2, half_y*2))/(4*half_wid*half_y)
        conv_template = signal.convolve2d(self.img.mean(-1).mean(-1), kernel2d, boundary='symm', mode='valid')
        test_x, test_y = np.unravel_index(np.argmin(conv_template), conv_template.shape)
        test_x += half_wid
        test_y += half_y
        
        test_patch = self.img[test_x-half_wid:test_x+half_wid, test_y-half_y:test_y+half_y, :, :]
        test = test_patch.mean(axis=(0,1))
        test = test.flatten(order='F') 
        test = (test-test.mean())/test.std()
        f, Pxx_den = signal.periodogram(test, fs)
        plt.semilogy(f, Pxx_den)
        plt.ylim([1e-7, 1000])
        plt.savefig(os.path.join(self.saving_dir, self.file_head+'_before_removal.png'))
        plt.close()
        
        test_patch = self.out[test_x-half_wid:test_x+half_wid, test_y-half_y:test_y+half_y, :, :]
        test = test_patch.mean(axis=(0,1))
        test = test.flatten(order='F') 
        test = (test-test.mean())/test.std()
        f, Pxx_den = signal.periodogram(test, fs)
        plt.semilogy(f, Pxx_den)
        plt.ylim([1e-7, 1000])
        plt.savefig(os.path.join(self.saving_dir, self.file_head+'_after_removal.png'))
        plt.close()
    
    def save_out(self):
        assert self.img.shape == self.out.shape
        if '.nii' in self.path:
            save_name = os.path.join(self.saving_dir, self.file_head+'_cleaned.nii')
            nib.Nifti1Image(np.round(self.out).astype('int16'), np.eye(4)).to_filename(save_name)
        elif '.h5' in self.path:
            save_name = os.path.join(self.saving_dir, self.file_head+'_cleaned.h5')
            with h5py.File(save_name, "w") as data_file:
                data_file.create_dataset("data", data=np.round(self.out).astype('int16'))
            

def main(args):
    
    load_directory = args['load_directory']
    save_directory = args['save_directory']
    brain_file = args['brain_file']

    full_load_path = os.path.join(load_directory, brain_file)

    #####################
    ### SETUP LOGGING ###
    #####################

    width = 120
    logfile = args['logfile']
    printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

    ##############################
    ### BACKGROUND SUBTRACTION ###
    ##############################

    printlog("Beginning BACKGROUND SUBTRACTION")
    with h5py.File(full_load_path, 'r') as hf:
        data = hf['data'][:]
        dims = np.shape(data)

        printlog("Data shape is {}".format(dims))  
        br = BgRemover3D(brain_file, half_wid=5)

        br.draw_bg()
        br.show_bg()
        br.remove_bg()
        br.show_spectrum(fs=180)
        br.save_out()

    printlog("background subtraction  done")

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))
