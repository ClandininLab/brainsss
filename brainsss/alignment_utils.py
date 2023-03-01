import numpy as np
import ants
import scipy
import nibabel as nib
import os
import time

def load_template_brain(brain_name, new_resolution=(2,2,2),use_voxels=False):

	if brain_name == "luke_exp":
		luke_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/anat_templates/20210310_luke_exp_thresh.nii"
		luke_exp = np.asarray(nib.load(luke_path).get_data().squeeze(), dtype='float32')
		luke_exp = ants.from_numpy(luke_exp)
		luke_exp.set_spacing((0.65,0.65,1))
		brain = ants.resample_image(luke_exp,new_resolution,use_voxels=use_voxels)
		print('Loaded Luke Exp')

	if brain_name == "luke_raw":
		in_file = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/anat_templates/luke.nii"
		luke_raw = np.asarray(nib.load(in_file).get_data(), dtype='float32')
		luke_raw = ants.from_numpy(luke_raw)
		luke_raw.set_spacing((.65,.65,1))
		brain = ants.resample_image(luke_raw,new_resolution,use_voxels=use_voxels)
		print('Loaded Luke Raw')

	if brain_name == "FDA":
		FDA_file = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/anat_templates/20220301_luke_2_jfrc_affine.nii'
		FDA = np.asarray(nib.load(FDA_file).get_fdata().squeeze(), dtype='float32')
		FDA = ants.from_numpy(FDA[...,::-1]) #FLIP Z
		FDA.set_spacing((0.38,0.38,0.38))
		brain = ants.resample_image(FDA,new_resolution,use_voxels=use_voxels)
		print('Loaded FDA')

	if brain_name == "JRC2018":
		fixed_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/anat_templates/JRC2018_FEMALE_38um_iso_16bit.nii"
		res_JRC2018 = (0.38, 0.38, 0.38)
		fixed_jrc = np.asarray(nib.load(fixed_path).get_data().squeeze(), dtype='float32')
		fixed_jrc = ants.from_numpy(fixed_jrc[:,:,::-1])
		fixed_jrc.set_spacing(res_JRC2018)
		brain = ants.resample_image(fixed_jrc,new_resolution,use_voxels=use_voxels)
		print('Loaded JRC2018')

	return brain