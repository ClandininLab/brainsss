import numpy as np
import os
import nibabel as nib
import pickle
import ants
from scipy.ndimage.morphology import binary_erosion
from scipy.ndimage.morphology import binary_dilation
import cv2
import time
import matplotlib

def load_roi_atlas():
    atlas_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/anat_templates/jfrc_2018_rois_improve_reorient_transformed.nii"
    atlas = np.asarray(nib.load(atlas_path).get_fdata().squeeze(), dtype='float32')
    atlas = ants.from_numpy(atlas)
    atlas.set_spacing((.76,.76,.76))
    atlas = ants.resample_image(atlas,(2,2,2),use_voxels=False)
    atlas = atlas.numpy()
    atlas_int = np.rint(atlas)
    atlas_clean = np.copy(atlas_int)
    diff_atlas = atlas_int - atlas
    thresh = 0.001
    atlas_clean[np.where(np.abs(diff_atlas)>thresh)] = 0
    return atlas_clean

def load_explosion_groups():
    explosion_rois_file = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/anat_templates/20220425_explosion_plot_rois.pickle'
    explosion_rois = pickle.load(open(explosion_rois_file,"rb"))
    return explosion_rois
    
def make_single_roi_masks(all_rois, atlas):
    masks = {}
    for roi in all_rois:
        mask = np.zeros(atlas.shape)
        mask[np.where(atlas == roi)] = 1
        mask_eroded = binary_erosion(mask, structure=np.ones((2,2,2)))
        mask_dilated = binary_dilation(mask_eroded, iterations=2)
        masks[roi] = mask_dilated
    return masks
    
def make_single_roi_contours(roi_masks, atlas):
    roi_contours = {}
    for roi in roi_masks:
        mask = roi_masks[roi]
        _, mask_binary = cv2.threshold(np.max(mask,axis=-1).astype('uint8'), 0, 1, cv2.THRESH_BINARY) 
        contours, _ = cv2.findContours(mask_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)#cv2.RETR_TREE

        canvas = np.ones(atlas[:,:,0].shape)
        out = cv2.drawContours(canvas, contours, -1, (0,255,0), 1)
        out = np.abs(out-1) #flip 0/1
        roi_contour = np.repeat(out[:,:,np.newaxis],repeats=4,axis=-1) ### copy into rgba channels to make white

        # get edge location
        left_edge = np.where(np.sum(np.nan_to_num(roi_contour),axis=0)>0)[0][0]
        right_edge = np.where(np.sum(np.nan_to_num(roi_contour),axis=0)>0)[0][-1]
        top_edge = np.where(np.sum(np.nan_to_num(roi_contour),axis=1)>0)[0][0]
        bottom_edge = np.where(np.sum(np.nan_to_num(roi_contour),axis=1)>0)[0][-1]
        
        roi_contours[roi] = {}
        roi_contours[roi]['contour'] = roi_contour
        roi_contours[roi]['left_edge'] = left_edge
        roi_contours[roi]['right_edge'] = right_edge
        roi_contours[roi]['top_edge'] = top_edge
        roi_contours[roi]['bottom_edge'] = bottom_edge
    return roi_contours
    
def unnest_roi_groups(explosion_rois):
    all_rois = []
    for roi_group in explosion_rois:
        all_rois.extend(explosion_rois[roi_group]['rois'].keys())
    return all_rois

def get_dim_info(item, full_x_mid, full_y_mid):
    y_mid = int(item.shape[0]/2)
    x_mid = int(item.shape[1]/2)

    height = item.shape[0]
    width = item.shape[1]

    left = full_x_mid-x_mid
    right = left + width

    top = full_y_mid-y_mid
    bottom = top + height
    return {'left': left, 'right': right, 'top': top, 'bottom': bottom}

def place_roi_groups_on_canvas(explosion_rois, roi_masks, roi_contours, data_to_plot, input_canvas, vmax, cmap, diverging=False):
    full_y_mid = int(input_canvas.shape[0]/2)
    full_x_mid = int(input_canvas.shape[1]/2)
    
    for roi_group in explosion_rois:
        
        x_shift = explosion_rois[roi_group]['x_shift']
        y_shift = explosion_rois[roi_group]['y_shift']
        
        roi_data = []
        left_edges = []
        right_edges = []
        bottom_edges = []
        top_edges = []
        
        for roi in explosion_rois[roi_group]['rois']:
            mask = roi_masks[roi]
            #masked_roi = mask[...,np.newaxis]*data_to_plot # for 3 channel
            masked_roi = mask*data_to_plot

            ### maximum projection along z-axis
            # works for negative values
            maxs = np.max(masked_roi,axis=2)
            mins = np.min(masked_roi,axis=2)
            maxs[np.where(np.abs(mins)>maxs)] = mins[np.where(np.abs(mins)>maxs)]
            roi_data.append(maxs)
            #masked_roi_flat = maxs

            ### maximum projection along z-axis
            #masked_roi_flat = np.max(masked_roi,axis=2)
            #roi_data.append(masked_roi_flat)
            
            left_edges.append(roi_contours[roi]['left_edge'])
            right_edges.append(roi_contours[roi]['right_edge'])
            top_edges.append(roi_contours[roi]['top_edge'])
            bottom_edges.append(roi_contours[roi]['bottom_edge'])
        
            
        # get extreme edges from all rois used
        left_edge = np.min(left_edges) - 1
        right_edge = np.max(right_edges) + 1
        top_edge = np.min(top_edges) - 1
        bottom_edge = np.max(bottom_edges) + 1
        
        ### this projects across all the roi_data from each roi 
        #roi_datas = np.max(np.asarray(roi_data),axis=0) # this one line is sufficient for not diverging
        maxs = np.max(np.asarray(roi_data),axis=0)
        mins = np.min(np.asarray(roi_data),axis=0)
        maxs[np.where(np.abs(mins)>maxs)] = mins[np.where(np.abs(mins)>maxs)]
        roi_datas = maxs

        ###ADD MAX MIN HERE LIKE ABOVE

        ### cutout this grouping
        #data_map = np.swapaxes(roi_datas[top_edge:bottom_edge,left_edge:right_edge,:],0,1) # for 3 channel
        data_map = np.swapaxes(roi_datas[top_edge:bottom_edge,left_edge:right_edge],0,1)
        ### apply gain
        #data_map = data_map * gain

        mycmap = matplotlib.cm.get_cmap(cmap)
        #mycmap.set_bad('k',1) # make nans black

        if diverging:
            # this will normalize all value to [0,1], with 0.5 being the new "0" basically
            # current issue - a zero that should be background now looks like negative.
            # solution: could use nans instead and set bad color
            # with diverging we should make background white!
            # so actually just set the input_canvas as 0.5!!!
            # then make contours nan and set back as black
            norm = matplotlib.colors.Normalize(vmin=-vmax, vmax=vmax)
            data_map = norm(data_map)
        else:
            data_map = data_map/vmax
        
        data_map = mycmap(data_map)[...,:3] #lose alpha channel

        dims = get_dim_info(data_map, full_x_mid, full_y_mid)

        ### ADD TO CANVAS
        input_canvas[dims['top']+y_shift:dims['bottom']+y_shift,
                     dims['left']+x_shift:dims['right']+x_shift,
                     :3] = data_map
        

        ### ADD CONTOUR TO CANVAS
        for roi in explosion_rois[roi_group]['rois']:
            contour = roi_contours[roi]['contour']
            contour = np.swapaxes(contour[top_edge:bottom_edge,left_edge:right_edge],0,1)
            ys = np.where(contour[:,:,0]>0)[0] + dims['top'] + y_shift
            xs = np.where(contour[:,:,0]>0)[1] + dims['left'] + x_shift
            input_canvas[ys,xs]=0#1
    return input_canvas
