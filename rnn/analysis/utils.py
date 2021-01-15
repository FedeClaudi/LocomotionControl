from loguru import logger
import json
import torch
from einops import repeat
import numpy as np


from fcutils.maths.utils import derivative


from pyrnn import RNN, is_win
from pyrnn.analysis import (
    FixedPoints,
    list_fixed_points,
)
from pyrnn._utils import torchify

from rnn.dataset import datasets

# ----------------------------------- misc ----------------------------------- #


def unpad(X, h, O, Y):
    """
        Sequences are padded with 0s during RNN training and inference.
        This function unpads the sequences for analysis

        Arguments:
            X: np.array of N_trials x N_samples x N inputs
            h: np.array of N_trials x N_samples x N units
            O: np.array of N_trials x N_samples x N outputs
            Y: np.array of N_trials x N_samples x N outputs

        Returns:
            X, h: same shapes but replacing the pads with np.nan
    """
    _X = X.copy()
    _h = h.copy()
    _O = O.copy()
    _Y = Y.copy()

    for trialn in range(X.shape[0]):
        try:
            stop = np.where(np.abs(derivative(X[trialn, :, 0])) > 0.1)[0][0]
        except IndexError:
            continue
        else:
            _X[trialn, stop:, :] = np.nan
            _h[trialn, stop:, :] = np.nan
            _O[trialn, stop:, :] = np.nan
            _Y[trialn, stop:, :] = np.nan

    return _X, _h, _O, _Y


# ------------------------------- Fixed points ------------------------------- #


def make_constant_inputs(rnn):
    """
        Makes a list of constant inputs (zeros) for a given RNN
    """
    constant_inputs = [
        repeat(
            torchify(np.zeros(rnn.input_size)).cuda(), "i -> b n i", b=1, n=1
        ),
    ]

    return constant_inputs


def fit_fps(rnn, h, fld, n_fixed_points=10):
    """
        Fit pyrnn FixedPoints analysis to identify fixed points in the dynamics

        Arguments:
            rnn: RNN class instance
            h: np.ndarray. (N trials, N frames, N units) array with hidden states
            fld: Path. Folder where the fixed points will be saved
            n_fixed_points: int. Number of max fixed points to look for

        Returns:
            fps: list of FixedPoint objects

    """
    logger.debug(
        f"Finding fixed pooints with h of shape {h.shape} and number of fixed points: {n_fixed_points}"
    )
    constant_inputs = make_constant_inputs(rnn)

    fp_finder = FixedPoints(rnn, speed_tol=1e-02, noise_scale=2)

    fp_finder.find_fixed_points(
        h,
        constant_inputs,
        n_initial_conditions=150,
        max_iters=9000,
        lr_decay_epoch=1500,
        max_fixed_points=n_fixed_points,
        gamma=0.1,
    )

    # save number of fixed points
    fp_finder.save_fixed_points(fld / "3bit_fps.json")

    # list fps
    fps = FixedPoints.load_fixed_points(fld / "3bit_fps.json")
    logger.debug(f"Found {len(fps)} fixed points in total")
    list_fixed_points(fps)

    return fps


# ------------------------------------ I/O ----------------------------------- #


def to_json(obj, fpath):
    """ saves an object to json """
    with open(fpath, "w") as out:
        json.dump(obj, out)


def from_json(fpath):
    """ loads an object from json """
    with open(fpath, "r") as fin:
        return json.load(fin)


def get_file(folder, pattern):
    """ Finds the path of a file in a folder given a pattern """
    try:
        return list(folder.glob(pattern))[0]
    except IndexError:
        raise ValueError(f"Could not find file in folder")


def load_from_folder(fld, winstor=False):
    """
        Loads a trained RNN from the folder with training outcomes
        Loads settings from rnn.yaml and uses that to load the correct
        dataset used for the RNN and to set the RNN params. 

        Arguments:
            fld: Path. Path to folder with RNN and metadata

        Returns
            dataset: instance of DataSet subclass used for training
            RNN: instance of pyrnn.RNN loaded from saved model
            winstor: bool. True if the fikder lives on winstor

    """
    logger.debug(f"Loading data from {fld.name}")

    # load params from yml
    settings_file = get_file(fld, "rnn.yaml")
    settings = from_json(settings_file)
    logger.debug("Loaded settings")

    # load dataset used for training
    dataset = datasets[settings["dataset_name"]](winstor=winstor)
    logger.debug(f'Loaded dataset: "{dataset.name}"')

    # set dataset settings for inference
    dataset.augment_probability = 0
    dataset.to_chunks = False
    dataset.warmup = False

    # load RNN
    del settings["on_gpu"], settings["dataset_name"]
    rnn = RNN.load(
        str(get_file(fld, "minloss.pt")),
        **settings,
        on_gpu=is_win,
        load_kwargs=dict(map_location=torch.device("cpu"))
        if not is_win
        else {},
    )
    logger.debug(f"Loaded RNN")

    return dataset, rnn
