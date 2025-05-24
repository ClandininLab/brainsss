import os
import argparse
import time

import numpy as np
import nibabel as nib
from skimage import io
import matplotlib.pyplot as plt
from scipy import signal

class BleedthroughRemoverLine:
    """
    Removes bleedthrough artifacts from 3D+time images using either:
    1. A percentile-based approach: Selects pixels below a specified percentile
       threshold in each line scan, then subtracts the mean background signal from each line.
    2. A kernel-based approach: Uses a sliding window to find the darkest region in each
       line, which is assumed to be the background region.
    """

    def __init__(self, img_path, method='percentile', percentile_threshold=10, half_width=20, channel=None, root_save_dir=None):
        """
        Parameters:
        - img_path: str. Path to the nii file.
        - method: str. Method to use for background identification: 'percentile' or 'kernel'. Default='percentile'.
        - percentile_threshold: int. Percentile threshold to identify dark pixels.
                  Lower values (e.g. 5-10) select darker pixels. Default=10.
        - half_width: int. Half width of the kernel used to identify background regions
                  when using the kernel method. Default=20.
        - channel: int or None. If provided, use the specified channel for background detection,
                  otherwise assume there is only one channel.
        - root_save_dir: str or None. Directory to save the output files. If None, saves in the same directory as img_path.
        """
        self.path = img_path
        self.method = method
        self.percentile_threshold = percentile_threshold
        self.half_width = half_width
        self.channel = channel
        self.root_save_dir = root_save_dir

        # self.img should have dimension x, y, z, t, (c) here, x is along the line scan direction
        self.og_img = np.asarray(nib.load(img_path).get_fdata().squeeze(), dtype='uint16')
        if channel is not None:
            self.img = self.og_img[..., channel]
        else:
            self.img = self.og_img
        assert len(self.img.shape) == 4

        self.make_savedir(root_save_dir)
    
    def make_savedir(self, root_save_dir=None):
        """Create directories for saving output files for intermediate analysis."""

        if root_save_dir is None:
            root_save_dir = os.path.dirname(self.path)
       #Minseung original code 
        # if self.method == 'percentile':
        #     save_dir = os.path.join(root_save_dir, 'bts', 'line', 'percentile', f'p{self.percentile_threshold}')
        #     self.suffix = f'_bts_line_p{self.percentile_threshold}'
        # else:  # kernel method
        #     save_dir = os.path.join(root_save_dir, 'bts', 'line', 'kernel', f'hw{self.half_width}')
        #     self.suffix = f'_bts_line_hw{self.half_width}'
        #Yandan's try to aviod f'
        if self.method == 'percentile':
            save_dir = os.path.join(root_save_dir, 'bts', 'line', 'percentile', 'p{}'.format(self.percentile_threshold))
            self.suffix = '_bts_line_p{}'.format(self.percentile_threshold)
        else:  # kernel method
            save_dir = os.path.join(root_save_dir, 'bts', 'line', 'kernel', 'hw{}'.format(self.half_width))
            self.suffix = '_bts_line_hw{}'.format(self.half_width)
            
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        self.save_dir = save_dir
        self.file_head = self.path.split('.')[0].split('/')[-1]
    
    def find_bg(self):
        """
        Identifies the background regions along the x-axis (line scan direction)
        for each y-z position in the image using either percentile or kernel-based approach.
        """
        # Average across time dimension to create a static 3D template
        template = np.mean(self.img, axis=-1)
        
        # Rearrange axes to (z,y,x) for easier processing
        template = np.moveaxis(template, (0, 2), (2, 0))
        
        if self.method == 'percentile':
            # Store the mask indices directly for each z,y position
            bg_masks = []
            for z_idx in range(template.shape[0]):  # For each z-slice
                bg_masks_z = []
                for y_idx in range(template.shape[1]):  # For each line
                    line = template[z_idx, y_idx]
                    # Find pixels below the percentile threshold
                    threshold = np.percentile(line, self.percentile_threshold)
                    dark_pixels = np.where(line <= threshold)[0]
                    bg_masks_z.append(dark_pixels)
                bg_masks.append(bg_masks_z)
            
            self.bg_masks = bg_masks
            self.using_masks = True
                     
        else:  # kernel method
            half_width = self.half_width
            wid = 2*half_width
            # Create uniform averaging kernel for smoothing
            kernel = np.ones(wid)/wid
            
            # Convolve with kernel to find the darkest region
            # Find the index boundaries (darkest-half_width, darkest+half_width) of the background
            # region for each line
            bg_ind = []
            for patch in template:
                bg_ind_tmp = []
                for line in patch:
                    tmp = np.convolve(line, kernel, 'valid')
                    bg_center = np.argmin(tmp) + half_width
                    bg_ind_tmp.append([bg_center-half_width, bg_center+half_width])
                bg_ind.append(bg_ind_tmp)
                
            self.bg_ind = bg_ind
            
            # Also convert to masks format for compatibility with show_bg
            bg_masks = []
            for z_idx in range(template.shape[0]):
                bg_masks_z = []
                for y_idx in range(template.shape[1]):
                    start, end = bg_ind[z_idx][y_idx]
                    dark_pixels = np.arange(start, end)
                    bg_masks_z.append(dark_pixels)
                bg_masks.append(bg_masks_z)
            
            self.bg_masks = bg_masks
            self.using_masks = False
          
    def show_bg(self):
        """
        Visualizes the background regions identified by find_bg().
        The background regions are marked with the maximum value in the image.

        Outputs:
        1. A tiff file with all z-planes showing background regions; (background as maximum value in the image)
        2. A png figure showing a subset of z-slices with original and marked background regions; (background as overlay)
        """
        show_bg = np.mean(self.img, axis=-1)  # average across time
        show_bg = np.moveaxis(show_bg, (0, 2), (2, 0))  # rearrange axes for visualization
        
        # Scale values to utilize full INT16 range
        min_val = np.min(show_bg)
        max_val = np.max(show_bg)
        
        # Scale to 95% of INT16 range to leave room for bg marker
        int16_max = np.iinfo(np.int16).max
        int16_min = np.iinfo(np.int16).min
        
        # Reserve the top 5% of the range for background marking
        display_max = int16_max * 0.95
        
        # Scale the data: (val - min) / (max - min) * (new_max - new_min) + new_min
        show_bg_scaled = (show_bg - min_val) / (max_val - min_val) * (display_max - int16_min) + int16_min
        
        # Mark background regions with the maximum value
        for i in range(show_bg_scaled.shape[0]):  # for each z-plane
            for j in range(show_bg_scaled.shape[1]):  # for each y-line
                show_bg_scaled[i, j, self.bg_masks[i][j]] = int16_max
                    
        #save_name = os.path.join(self.save_dir, self.file_head+f'{self.suffix}_bg_visualization.tif')
        save_name = os.path.join(self.save_dir, '{}{}_bg_visualization.tif'.format(self.file_head, self.suffix))

        io.imsave(save_name, np.round(show_bg_scaled).astype('int16'))
        
        # Create a figure showing a subset of z-slices
        # Prepare the original image for visualization
        orig_img = np.mean(self.img, axis=-1)  # average across time
        
        # Select a subset of z-slices to visualize
        num_slices = min(6, orig_img.shape[2])
        z_indices = np.linspace(0, orig_img.shape[2]-1, num_slices).astype(int)
        
        # Create a figure with rows of original and background-marked images
        fig, axes = plt.subplots(2, num_slices, figsize=(15, 6))
        
        for i, z in enumerate(z_indices):
            # Original image - flipped upside down
            axes[0, i].imshow(np.flipud(orig_img[:,:,z]), cmap='gray')
            #axes[0, i].set_title(f"Z={z}")
            axes[0, i].set_title("Z={}".format(z))
            axes[0, i].axis('off')
            
            # Background-marked image with color overlay - flipped upside down            
            marked_img = orig_img[:,:,z].copy()
            # Create a mask for this z-slice
            mask = np.zeros_like(marked_img, dtype=bool)
            for j in range(marked_img.shape[1]):  # for each y-line
                if len(self.bg_masks[z][j]) > 0:  # Check if there are any background pixels
                    mask[self.bg_masks[z][j], j] = True
            
            # Display the image in gray with red overlay for background - flipped upside down
            axes[1, i].imshow(np.flipud(marked_img), cmap='gray')
            # Create a red mask with transparency for background regions - flipped upside down
            #bg_overlay = np.zeros((*marked_img.shape, 4))
            shape = marked_img.shape + (4,)
            bg_overlay = np.zeros(shape)
            bg_overlay[mask, 0] = 1.0  # Red channel
            bg_overlay[mask, 3] = 0.7  # Alpha channel (transparency)
            axes[1, i].imshow(np.flipud(bg_overlay), interpolation='nearest')
            
            if self.method == 'percentile':
                #axes[1, i].set_title(f"Background (p{self.percentile_threshold})")
                axes[1, i].set_title("Background (p{})".format(self.percentile_threshold))

            else:
                #axes[1, i].set_title(f"Background (hw{self.half_width})")
                axes[1, i].set_title("Background (hw{})".format(self.half_width))

                
            axes[1, i].axis('off')
        
        plt.tight_layout()
        #plt.savefig(os.path.join(self.save_dir, self.file_head+f'{self.suffix}_bg_visualization.png'))
        plt.savefig(os.path.join(self.save_dir, self.file_head + '{}_bg_visualization.png'.format(self.suffix)))
        plt.close()

    def remove_bg(self):
        """
        Removes the background from the image by subtracting the mean of background pixels
        from each line.
        """
        img = np.moveaxis(self.img, (0,1,2,3), (3,1,2,0))
        out = np.zeros_like(img)
        
        if self.method == 'percentile' or self.using_masks:
            for ind_y in range(img.shape[1]):
                for ind_z in range(img.shape[2]):
                    patch = img[:, ind_y, ind_z, :]
                    mask = self.bg_masks[ind_z][ind_y]
                    
                    if len(mask) > 0:  # Make sure there are background pixels
                        # Extract background values using the mask
                        bg_values = patch[:, mask]
                        # Calculate mean across background pixels
                        bg = np.mean(bg_values, axis=1)
                        # Subtract background from entire line
                        patch = patch - bg[:, np.newaxis]
                        # Clip values to avoid negative values
                        patch = np.clip(patch, 0, None)
                    
                    out[:, ind_y, ind_z, :] = patch
        else:  # kernel method using bg_ind
            for ind_y in range(img.shape[1]):
                for ind_z in range(img.shape[2]):
                    patch = img[:, ind_y, ind_z, :]
                    start, end = self.bg_ind[ind_z][ind_y]
                    bg_patch = img[:, ind_y, ind_z, start:end]
                    bg = bg_patch.mean(axis=-1)
                    patch = patch - bg[:, np.newaxis]
                    patch = np.clip(patch, 0, None) # Clip values to avoid negative values
                    out[:, ind_y, ind_z, :] = patch
                
        self.out = np.moveaxis(out, (0,1,2,3), (3,1,2,0))

    def show_spectrum(self, fs=180, half_width=20):
        """
        Visualizes the power spectral density of the image data before and after background removal.
        
        Parameters:
        -----------
        fs : float, default=180
            Sampling frequency in Hz used for the spectral analysis.
        half_width : int, default=20
            Half-width of the patch to analyze.

        Returns:
        --------
        None
            Displays a figure with two subplots showing the power spectral density before and after background removal.
            The plots use a logarithmic scale for the y-axis to better visualize the spectral components.
        """
        # Create an averaging kernel for convolution
        kernel2d = np.ones((half_width*2, half_width*2))/(4*half_width*half_width)
        # Find the darkest region in the image by convolving with the kernel
        # Average across time dimension and z-planes
        conv_template = signal.convolve2d(self.img.mean(-1).mean(-1), kernel2d, boundary='symm', mode='valid')
        # Get coordinates of the minimum value (darkest region)
        test_x, test_y = np.unravel_index(np.argmin(conv_template), conv_template.shape)
        # Adjust coordinates to account for convolution padding
        test_x += half_width
        test_y += half_width
        
        def calculate_spectrum(image_data):
            # Extract a patch around the identified coordinates
            test_patch = image_data[test_x-half_width:test_x+half_width, test_y-half_width:test_y+half_width, :, :]
            # Average the patch across spatial dimensions (x,y)
            test = test_patch.mean(axis=(0,1))
            # Flatten the data in column-major order (Fortran-style)
            test = test.flatten(order='F') 
            # Normalize the data (z-score)
            test = (test-test.mean())/test.std()
            # Calculate power spectral density using periodogram
            # fs parameter is the sampling frequency in Hz
            f, Pxx_den = signal.periodogram(test, fs)
            return f, Pxx_den
        
        # Create a figure with two subplots side by side
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        # BEFORE BACKGROUND REMOVAL
        f_before, Pxx_before = calculate_spectrum(self.img)
        ax1.semilogy(f_before, Pxx_before)
        ax1.set_ylim([1e-7, 1000])
        ax1.set_xlabel('Frequency (Hz)')
        ax1.set_ylabel('Power Spectral Density')
        ax1.set_title('Before Background Removal')
        
        # AFTER BACKGROUND REMOVAL
        f_after, Pxx_after = calculate_spectrum(self.out)
        ax2.semilogy(f_after, Pxx_after)
        ax2.set_ylim([1e-7, 1000])
        ax2.set_xlabel('Frequency (Hz)')
        ax2.set_ylabel('Power Spectral Density')
        ax2.set_title('After Background Removal')
        
        # # Add a main title and adjust layout
        # if self.method == 'percentile':
        #     fig.suptitle(f'Spectrum Comparison (Percentile={self.percentile_threshold})', fontsize=16)
        # else:
        #     fig.suptitle(f'Spectrum Comparison (Half Width={self.half_width})', fontsize=16)
            
        # plt.tight_layout()
        # Save the combined figure
        #plt.savefig(os.path.join(self.save_dir, self.file_head+f'{self.suffix}_spectrum_comparison.png'))
        #plt.close()
        
        # Save the combined figure
        #plt.savefig(os.path.join(self.save_dir, self.file_head+f'{self.suffix}_spectrum_comparison.png'))
        #plt.close()
        # Add a main title and adjust layout
        if self.method == 'percentile':
            fig.suptitle('Spectrum Comparison (Percentile={})'.format(self.percentile_threshold), fontsize=16)
        else:
            fig.suptitle('Spectrum Comparison (Half Width={})'.format(self.half_width), fontsize=16)

        plt.tight_layout()

        # Save the combined figure
        plt.savefig(os.path.join(self.save_dir, self.file_head + '{}_spectrum_comparison.png'.format(self.suffix)))
        plt.close()

    def save_out(self, use_gzip=False, save_in_root=False, save_merged=False):
        """
        Save the background-removed image as a NIfTI file.
        
        Parameters:
        -----------
        use_gzip : bool, default=False
            Whether to compress the output file with gzip.
        save_in_root : bool, default=False
            Whether to save in the root directory rather than the nested directory.
        save_merged : bool, default=False
            If True and a specific channel was processed, merge the processed channel back into
            the original multi-channel image. If False, save only the processed channel.
        """
        assert self.img.shape == self.out.shape

        if self.channel is not None:
            out_1ch = self.out
            if not save_merged:
                # Save only the processed channel (default behavior)
                self.out = out_1ch
                #suffix = f'_ch{self.channel+1}' + self.suffix # +1 for 1-based indexing
                suffix = '_ch{}'.format(self.channel + 1) + self.suffix

            else:
                # Reconstruct the full multi-channel image
                self.out = self.og_img.copy()
                self.out[..., self.channel] = out_1ch
                suffix = self.suffix
                assert self.out.shape == self.og_img.shape
        else:
            suffix = self.suffix
        
        save_fn = self.file_head + suffix + '.nii'
        if use_gzip:
            save_fn += '.gz'
        save_dir = self.root_save_dir if save_in_root else self.save_dir
        save_path = os.path.join(save_dir, save_fn)
        nib.Nifti1Image(np.round(self.out).astype('uint16'), np.eye(4)).to_filename(save_path)

        #print(f"Saved background-removed image to {save_path}")
        print("Saved background-removed image to {}".format(save_path))



if __name__ == "__main__":

    # Example usages:
    # Percentile method:
    # python remove_bleedthrough_line.py /home/minseung/data/ImagingData/Bruker/20250225/TSeries-20250225-004_reg.nii --method percentile --sampling_rate 7.22 --channel 1 --percentile 5
    # Kernel method:
    # python remove_bleedthrough_line.py /home/minseung/data/ImagingData/Bruker/20250225/TSeries-20250225-004_reg.nii --method kernel --sampling_rate 7.22 --channel 1 --half_width 20
    # Save only processed channel:
    # python remove_bleedthrough_line.py /home/minseung/data/ImagingData/Bruker/20250225/TSeries-20250225-004_reg.nii --channel 1 --save_only_processed_channel

    parser = argparse.ArgumentParser(
        description='Remove bleedthrough from 3D image using either percentile or kernel-based background detection. ' +
                   'The percentile method identifies background pixels below a specified percentile threshold in each line. ' +
                   'The kernel method uses a sliding window to find the darkest region in each line. ' +
                   'Both methods then remove the background signal from the entire line.')

    parser.add_argument('img_path', type=str,
                    help='Path to nii file. E.g. /path/to/data/TSeries-20250225-004_reg.nii')
    parser.add_argument('--channel', type=int, default=None,
                    help='Channel number to process. If not provided, assume single channel data.')
    parser.add_argument('-show_bg_only', action='store_true',
                    help='If provided, only show the background regions and exit.')

    parser.add_argument('--method', type=str, choices=['percentile', 'kernel'], default='percentile',
                    help='Method to use for background detection. Default=percentile')
    parser.add_argument('--percentile', type=int, default=10,
                    help='(For percentile method) Percentile threshold for identifying dark pixels. Lower values select darker pixels. Default=10')
    parser.add_argument('--half_width', type=int, default=10,
                    help='(For kernel method) Half width of the kernel/window for background detection. Default=10')

    parser.add_argument('-do_spectral_analysis', action='store_true',
                    help='If provided, perform spectral analysis on the image data.')
    parser.add_argument('--sampling_rate', type=float, default=7.22,
                    help='Sampling rate of the imaging data. Used for spectral analysis. Default=7.22 (Hz)')
    parser.add_argument('--analysis_half_width', type=int, default=20,
                    help='Half width for spectrum analysis patch. Default=20')

    parser.add_argument('--root_save_dir', type=str, default=None,
                    help='Directory to save the output files. If not provided, saves in the same directory as img_path.')
    parser.add_argument('-save_out_in_root', action='store_true',
                    help='If provided, save the output files in the root save dir instead of the default nested save directory.')
    parser.add_argument('-no_gzip', action='store_true',
                    help='If provided, save the output file without gzip compression. Default is to use gzip.')
    parser.add_argument('-save_merged', action='store_true',
                    help='If provided and a channel was specified, merge the processed channel back into the original multi-channel image. Default is to save only the processed channel.')
    args = parser.parse_args()
    if not os.path.exists(args.img_path):
        #raise FileNotFoundError(f"Image file not found: {args.img_path}")
        raise FileNotFoundError("Image file not found: {}".format(args.img_path))


    t0 = time.time()

    remover = BleedthroughRemoverLine(
        img_path=args.img_path, 
        method=args.method,
        percentile_threshold=args.percentile,
        half_width=args.half_width,
        channel=args.channel,
        root_save_dir=args.root_save_dir
    )

    t1 = time.time()
    #print(f"Image loaded from {args.img_path}. Shape: {remover.img.shape}. ({t1-t0:.2f}s)")
    print("Image loaded from {}. Shape: {}. ({:.2f}s)".format(args.img_path, remover.img.shape, t1 - t0))

    
    remover.find_bg()

    t2 = time.time()
    #print(f"Background regions identified using {args.method} method. ({t2-t1:.2f}s)")
    print("Background regions identified using {} method. ({:.2f}s)".format(args.method, t2 - t1))


    remover.show_bg()

    t3 = time.time()
    #print(f"Background regions visualized and saved. ({t3-t2:.2f}s)")
    print("Background regions visualized and saved. ({:.2f}s)".format(t3 - t2))

    
    if args.show_bg_only:
        exit()
        
    remover.remove_bg()

    t4 = time.time()
    #print(f"Background removed from image. ({t4-t3:.2f}s)")
    print("Background removed from image. ({:.2f}s)".format(t4 - t3))


    if args.do_spectral_analysis:
        remover.show_spectrum(fs=args.sampling_rate, half_width=args.analysis_half_width)
        t5 = time.time()
        #print(f"Spectral analysis completed. ({t5-t4:.2f}s)")
        print("Spectral analysis completed. ({:.2f}s)".format(t5 - t4))

    
    t6 = time.time()
    remover.save_out(use_gzip=not args.no_gzip, save_in_root=args.save_out_in_root, save_merged=args.save_merged)
    t7 = time.time()
    #print(f"Background-removed image saved. ({t7-t6:.2f}s)")
    #print(f"Total time taken: {t7-t0:.2f}s")
    print("Background-removed image saved. ({:.2f}s)".format(t7 - t6))
    print("Total time taken: {:.2f}s".format(t7 - t0))
