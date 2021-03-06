import os
os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
import argparse
import common
import numpy as np
import sys
from keras.preprocessing import image
from os.path import join

# Parsing input arguments
parser = argparse.ArgumentParser(description='Feature extraction with own trained weights')
parser.add_argument('-i','--image', help='image path to extract features', required=True)
args = vars(parser.parse_args())

# Input parameters
dataset = 'brain'
grayscale = True

# Default directory
root = common.default_path()

# Model path
model_path = join(root, 'outputs/models/' + dataset + '_model.h5');

# Predictions path
predictions_path = join(root, 'inputs/predictions/' + dataset + '_predictions.json');

# Creating and instanciating the chosen CNN
cnet = common.ConvNet()
cnet.load_model(model_path)

# Loading and pre-processing input image
img_path = sys.argv[2]
img = image.load_img(img_path, grayscale=grayscale)
x = image.img_to_array(img)
x = np.expand_dims(x, axis=0)
print('Input image shape:', x.shape)

# Extracting input image features
features = cnet.predict(x, batch_size=1)

# Concatenating to 1-D array
features = np.ndarray.flatten(features)
print("\n[INFO] Output array shape:", features.shape)

# Features output path
features_path = join(root, 'outputs/features/' + img_path + '_features.txt');

# Saving output
np.savetxt(features_path, features, fmt='%f')

import gc; gc.collect()
