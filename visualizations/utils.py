import importlib
import os
import sys
import numpy as np
import pprint
import h5py
import glob
import argparse
import math
import socket
import getpass

# This mapping dict needs to be coded manually for every different model we
# want to plot for, and is done via manual, interactive checkpoint inspection.
# This is just meant to identify the layers in the checkpoints
# and map them to pretty, sequential names
MODELS = {
    "logistic": {
        "1": "classifier",
    },
    "fc": {
        "1": "fc1",
        "3": "fc2",
        "5": "fc3",
        "7": "fc4",
        "9": "fc5",
        "11": "classifier",
    },
    "fc-bn": {
        "1": "fc1",
        "2": "bn1",
        "4": "fc2",
        "5": "bn2",
        "7": "fc3",
        "8": "bn3",
        "10": "fc4",
        "11": "bn4",
        "13": "fc5",
        "14": "bn5",
        "16": "classifier",
    },
    "vgg16": {
        "features.0": "conv1",
        "features.2": "conv2",
        "features.5": "conv3",
        "features.7": "conv4",
        "features.10": "conv5",
        "features.12": "conv6",
        "features.14": "conv7",
        "features.17": "conv8",
        "features.19": "conv9",
        "features.21": "conv10",
        "features.24": "conv11",
        "features.26": "conv12",
        "features.28": "conv13",
        "classifier.0": "fc1",
        "classifier.3": "fc2",
        "classifier.6": "classifier",
    },
    "vgg16-bn": {
        "features.0": "conv1",
        "features.1": "bn1",
        "features.3": "conv2",
        "features.4": "bn2",
        "features.7": "conv3",
        "features.8": "bn3",
        "features.10": "conv4",
        "features.11": "bn4",
        "features.14": "conv5",
        "features.15": "bn5",
        "features.17": "conv6",
        "features.18": "bn6",
        "features.20": "conv7",
        "features.21": "bn7",
        "features.24": "conv8",
        "features.25": "bn8",
        "features.27": "conv9",
        "features.28": "bn9",
        "features.30": "conv10",
        "features.31": "bn10",
        "features.34": "conv11",
        "features.35": "bn11",
        "features.37": "conv12",
        "features.38": "bn12",
        "features.40": "conv13",
        "features.41": "bn13",
        "classifier.0": "fc1",
        "classifier.3": "fc2",
        "classifier.6": "classifier",
    },
}

def in_synapses(W, b=None):
    """
    Computes sum of in synapses to next layer
    """
    if np.ndim(W) == 4:
        in_sum = np.sum(W, axis=(1,2,3))
    else:
        in_sum = np.sum(W, axis=1)
    if b is not None:
        in_sum += b
    return in_sum

def out_synapses(W, b=None):
    """
    Computes sum of out synapses from last layer
    """
    if np.ndim(W) == 4:
        out_sum = np.sum(W, axis=(0,2,3))
    else:
        out_sum = np.sum(W, axis=0)
    return out_sum

def makedir_quiet(d):
    """
    Convenience util to create a directory if it doesn't exist
    """
    if not os.path.isdir(d):
        os.makedirs(d)


def make_iterable(x):
    """
    If x is not already array_like, turn it into a list or np.array
    """
    if not isinstance(x, (list, tuple, np.ndarray)):
        return [x]
    return x

def get_layers(model):
    return MODELS[model].values()

def get_features(
    feats_path,
    group,
    keys,
    out_keys=None,
    verbose=False,
):
    """
    Returns features from HDF5 DataSet

    Inputs
        validation_path (str): where to find the HDF5 dataset
        group_name (str): the group name used for the particular validation
        keys (str or list of strs): which keys to extract from the group.
        out_keys (list of strs): keys for the output dict
    """
    assert os.path.isfile(feats_path), "%s is not a file" % (feats_path)

    keys = make_iterable(keys)

    if out_keys is None:
        out_keys = keys
    out_keys = make_iterable(out_keys)

    assert len(keys) == len(
        out_keys
    ), "Number of keys does not match number of output keys"

    out = {}
    with h5py.File(feats_path, "r") as open_file:
        if verbose:
            keys_to_print = open_file[group].keys()
            print("Keys in dataset:")
            pprint.pprint(keys_to_print)

        for in_key, out_key in zip(keys, out_keys):
            out[out_key] = open_file[group][in_key][:]
            if verbose:
                print("Extracted %s:" % out_key, out[out_key].shape)

    return out

def load_features(steps, feats_dir, model, suffix, group):
    """
    layers: is the output keys for the layer feats, or computed quantities
    keys: is the actual keys to be read from the h5 file
    feats: is the output dict
    """

    names = [f"{name}.{suffix}" for name in MODELS[model].keys()]
    layers = MODELS[model].values()

    feats = {layer: {} for layer in layers}

    for step in steps:
        feats_path = f"{feats_dir}/step{step}.h5"
        
        if os.path.isfile(pth):
            feature_dict = get_features(
                feats_path=feats_path, group=group, keys=names, out_keys=layers
            )
            for layer in layers:
                feats[layer][f"step_{step}"] = feature_dict[layer]
    return feats


def default_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--experiment", type=str, required=True, help='name used to save results (default: "")'
    )
    parser.add_argument(
        "--expid", type=str, required=True, help='name used to save results (default: "")'
    )
    parser.add_argument(
        "--save-dir",
        type=str,
        default="results",
        help='Directory to save checkpoints and features (default: "Results")',
    )
    parser.add_argument(
        "--plot-dir", 
        type=str, 
        default=None,
        help="Directory to save cache and figures (default: 'results')",
    )
    parser.add_argument(
        "--overwrite", 
        dest="overwrite", 
        action="store_true",
        default=False
    )
    parser.add_argument(
        "--image-suffix",
        type=str,
        default="",
        help="extra image suffix",
        required=False,
    )
    parser.add_argument(
        "--use-tex", 
        action="store_true",
        help="will use tex rendering for matplotlib labels", 
        default=False
    )
    parser.add_argument(
        "--legend", 
        action="store_true",
        help="will add legend", 
        default=False
    )
    return parser