import h5py
import numpy as np
import pandas as pd
import glob
from keras import backend as K
from scipy import io
from scipy import misc
from os.path import join, isdir
import sys

# Input raw dataset dimensions
WIDTH=224
HEIGHT=224
N_CHANNELS=3

# Input OT Maps dimensions
OT_WIDTH=256
OT_HEIGHT=256
OT_CHANNELS=2

def load_data(dataset, data_type, ref, normalization_method):
    """
    Load a dataset in either image space or transport space.

    This function assumes that the data are stored in:
        root/data/raw
        root/data/ot_maps
	root/data/references

    Parameters
    ----------
    dataset : str
        Dataset name to compose output files

    data_type : str (optional)
        Return images, transport maps or image derivatives
        ('image', 'ot', 'derivative')

    ref: bool (optional)
        Whether or not to multiply the reference in OT case
	(True, False)

    normalization_method: str (optional)
        ('feature', 'image', 'none')

    Returns
    -------
    data : (n_imgs, width, length, n_channels) numpy array
        Data array

    labels : (n_imgs, 1) numpy array
        Data labels

    We appreciate and thank Liam Cattell from UVa's BME Department for scripting this data.py!
    """

    root = '/Users/gustavo/Documents/LibKeras/data'

    # Check if the data type exists (image, ot or derivative)
    if data_type == 'image':
        data, labels = load_image(dataset, root)
    elif data_type == 'ot':
        data, labels = load_ot(dataset, root)
    elif data_type == 'derivative':
        data, labels = load_derivative(dataset, root)
    else:
        raise ValueError("Unknown data_type: '%s'" % data_type)

    # Check whether to multiply or not the ot maps by their reference
    if ref == True:
        data = multiply_reference(data, dataset, root)

    # Check if the normalizatiom method exists (feature, image or none)
    if normalization_method == 'feature':
        data = normalize_feature(data)
    elif normalization_method == 'image':
        data = normalize_image(data)
    elif normalization_method == 'none':
        data = data
    else:
        raise ValueError("Unknown normalization method: '%s'" % data_type)

    return data, labels

def load_image(dataset, root):

    # Amount of files to read
    N_FILES = 1

    # Load input .mat files
    paths = list()
    for i in range(0, N_FILES):
    	fpath = join(root, 'raw', dataset + '_' + str(i+1) + '.mat')
    	paths.append(fpath)

    labels = np.empty((0, 1))
    # Instanciating data array according to backend's data format
    data_format = K.image_data_format()
    assert data_format in {'channels_last', 'channels_first'}
    if data_format == 'channels_last':
        data = np.empty((0, WIDTH, HEIGHT, N_CHANNELS))
    else:
        data = np.empty((0, N_CHANNELS, WIDTH, HEIGHT))

    # Looping and concatenating all .mat files
    for k in paths:
    	f = h5py.File(k)
    	l = f["l"]
    	x = f["x"]
    	label = np.array(l) - 1
    	datamat = np.array(x)
    	labels = np.concatenate((labels, label), axis=0)
    	data = np.concatenate((data, datamat), axis=0)

    return data, labels

def load_derivative(dataset, root):

    # Loading initial images
    data, labels = load_image(dataset, root)

    # Getting actual data format
    data_format = K.image_data_format()
    assert data_format in {'channels_last', 'channels_first'}

    if data_format == 'channels_last':
        # Compute the derivative of the images in each direction
        dx = np.gradient(np.squeeze(data[:,:,:,0]), axis=2)
        dy = np.gradient(np.squeeze(data[:,:,:,0]), axis=1)

        data[:,:,:,0] = dx
        data[:,:,:,1] = dy
    else:
        # Compute the derivative of the images in each direction
        dx = np.gradient(np.squeeze(data[:,0,:,:]), axis=2)
        dy = np.gradient(np.squeeze(data[:,0,:,:]), axis=1)

        data[:,0,:,:] = dx
        data[:,1,:,:] = dy

    return data, labels

def load_ot(dataset, root):

    # Load the transport maps
    fpath = join(root, 'ot_maps', dataset + '_maps.mat')
    datamat = io.loadmat(fpath)

    # Dataset dimensions
    h, w, n_imgs = datamat['f'].shape
    data_format = K.image_data_format()

    # Instanciating data array according to backend's data format
    assert data_format in {'channels_last', 'channels_first'}
    if data_format == 'channels_last':
        data = np.zeros((n_imgs, OT_WIDTH, OT_HEIGHT, OT_CHANNELS))
    else:
        data = np.zeros((n_imgs, OT_CHANNELS, OT_WIDTH, OT_HEIGHT))

    # Create meshgrind according to desired dimensions
    x, y = np.meshgrid(np.arange(0,w), np.arange(0,h))
    for i in range(n_imgs):
        if data_format == 'channels_last':
            # Subtract x from the transport maps, and pad the resulting image
            data[i,:,:,0] = pad_array(datamat['f'][:,:,i] - x)
            data[i,:,:,1] = pad_array(datamat['g'][:,:,i] - y)
        else:
            # Subtract x from the transport maps, and pad the resulting image
            data[i,0,:,:] = pad_array(datamat['f'][:,:,i] - x)
            data[i,1,:,:] = pad_array(datamat['g'][:,:,i] - y)

    labels = datamat['label'].astype('uint8')

    return data, labels

def multiply_reference(data, dataset, root):

    # Getting actual data format
    data_format = K.image_data_format()
    assert data_format in {'channels_last', 'channels_first'}

    if data_format == 'channels_last':
        # Loading initial dimensions
        [N,P,Q,C] = data.shape

        # Loading .mat reference file
        dataset = io.loadmat(join(root, 'references/' + dataset + '_reference.mat'))
        I0 = dataset['I0']
        I0 = np.asarray(I0);
        I0 = pad_array(I0[:,:,4])

        I0 = np.tile(I0.reshape((1,P,Q)), (1,1,C))
        I0 = np.tile(I0.reshape((1,P,Q,C)), (N,1,1,1))
    else:
        # Loading initial dimensions
        [N,C,P,Q] = data.shape

        # Loading .mat reference file
        dataset = io.loadmat(join(root, 'references/' + dataset + '_reference.mat'))
        I0 = dataset['I0']
        I0 = np.asarray(I0);
        I0 = pad_array(I0[:,:,4])

        I0 = np.tile(I0.reshape((1,P,Q)), (C,1,1))
        I0 = np.tile(I0.reshape((1,C,P,Q)), (N,1,1,1))

    # Multiplying ot maps by their reference
    data = np.multiply(data, np.sqrt(I0))

    return data

def normalize_feature(img):

    # Getting actual data format
    data_format = K.image_data_format()
    assert data_format in {'channels_last', 'channels_first'}

    if data_format == 'channels_last':
        # Loading initial dimensions
        [N,P,Q,C] = img.shape

        # Normalizing features
        mean_img = np.mean(img, axis = 0)
        std_img = np.std(img, axis=0)

        if mean_img.shape != (P,Q,C) or std_img.shape != (P,Q,C):
            raise ValueError("Mean and Standard Deviation size is wrong.")

        # Stop divide-by-zero errors, by replacing small standard deviations with 1
        std_img[std_img<1.0e-12] = 1

        # Outputting final images
        img = img - np.tile(mean_img.reshape((1,P,Q,C)), (N,1,1,1))
        img = img / np.tile(std_img.reshape((1,P,Q,C)), (N,1,1,1))
    else:
        # Loading initial dimensions
        [N,C,P,Q] = img.shape

        # Normalizing features
        mean_img = np.mean(img, axis = 0)
        std_img = np.std(img, axis=0)

        if mean_img.shape != (C,P,Q) or std_img.shape != (C,P,Q):
            raise ValueError("Mean and Standard Deviation size is wrong.")

        # Stop divide-by-zero errors, by replacing small standard deviations with 1
        std_img[std_img<1.0e-12] = 1

        # Outputting final images
        img = img - np.tile(mean_img.reshape((1,C,P,Q)), (N,1,1,1))
        img = img / np.tile(std_img.reshape((1,C,P,Q)), (N,1,1,1))

    return img

def normalize_image(img):

    # Getting actual data format
    data_format = K.image_data_format()
    assert data_format in {'channels_last', 'channels_first'}

    if data_format == 'channels_last':
        # Loading initial dimensions
        [N,P,Q,C] = img.shape;

        # Looping for all images and channels
        for i in range(N):
            for c in range(C):
                mu = np.mean(np.squeeze(img[i,:,:,c]))
                std = np.std(np.squeeze(img[i,:,:,c]))
                img[i,:,:,c] = (img[i,:,:,c] - mu)/std
                if std < 1.0e-12:
                    raise ValueError("Standard Deviation is too small. Watch out!")
    else:
        # Loading initial dimensions
        [N,C,P,Q] = img.shape;

        # Looping for all images and channels
        for i in range(N):
            for c in range(C):
                mu = np.mean(np.squeeze(img[i,c,:,:]))
                std = np.std(np.squeeze(img[i,c,:,:]))
                img[i,c,:,:] = (img[i,c,:,:] - mu)/std
                if std < 1.0e-12:
                    raise ValueError("Standard Deviation is too small. Watch out!")

    return img;

def pad_array(arr, new_dim=(OT_WIDTH, OT_HEIGHT)):

    # Loading initial derivatives
    dy = new_dim[0] - arr.shape[0]
    dx = new_dim[1] - arr.shape[1]

    if dy < 0 or dx < 0:
        raise ValueError("Input array must be smaller than new dimensions")

    if dy == 0 and dx == 0:
        return arr

    dy2 = int(round(dy/2))
    dx2 = int(round(dx/2))

    # Padding final array
    arr_out = np.pad(arr, ((dy2,dy-dy2), (dx2,dx-dx2)), 'constant',
                     constant_values=0)

    return arr_out

# Test the function(s)
if __name__ == "__main__":
    root = '/home/gustavo/src/keras/data'
    data, labels = load_data('imagenet', 'none')
