import numpy as np
from pathlib import Path
import pandas as pd

from fcutils.file_io.io import load_yaml
from fcutils.maths.geometry import calc_distance_from_point

# ---------------------------------- Data IO --------------------------------- #


def load_results_from_folder(folder):
    folder = Path(folder)
    if not folder.exists():
        raise ValueError(f"Results folder {folder} doesnt exist")

    files = dict(
        config=folder / "config.yml",
        control=folder / "control_vars.yml",
        state=folder / "state_vars.yml",
        trajectory=folder / "trajectory.npy",
        history=folder / "history.h5",
    )

    for f in files.values():
        if not f.exists():
            raise ValueError(
                f"Data folder incomplete, something missing in : {str(folder)}.\n {f} is missing"
            )

    config = load_yaml(str(files["config"]))
    control = load_yaml(str(files["control"]))
    state = load_yaml(str(files["state"]))
    trajectory = np.load(str(files["trajectory"]))
    history = pd.read_hdf(str(files["history"]), key="hdf")

    return config, control, state, trajectory, history


# -------------------------------- Coordinates ------------------------------- #


def cartesian_to_polar(x, y):
    r = np.sqrt(x ** 2 + y ** 2)
    gamma = np.arctan2(y, x)
    return r, gamma


def polar_to_cartesian(r, gamma):
    x = r * np.cos(gamma)
    y = r * np.sin(gamma)
    return x, y


def traj_to_polar(traj):
    """ 
        Takes a trjectory expressed as (x,y,theta,v,s)
        and converts it to (r, gamma, v, s)
    """

    new_traj = np.zeros((len(traj), 4))

    new_traj[:, 0] = calc_distance_from_point(traj[:, :2], [0, 0])

    new_traj[:, 1] = np.arctan2(traj[:, 1], traj[:, 0])

    # import matplotlib.pyplot as plt
    # f = plt.figure()
    # ax = f.add_subplot(121)
    # pax = f.add_subplot(122, projection="polar")

    # ax.scatter(traj[:, 0], traj[:, 1], cmap='bwr', c=np.arange(len(traj[:, 0])))
    # pax.scatter(new_traj[:, 1], new_traj[:, 0], cmap='bwr', c=np.arange(len(traj[:, 0])))

    # plt.show()

    return new_traj


# ----------------------------------- Misc ----------------------------------- #


def merge(*ds):
    """
        Merges an arbitrary number of dicts or named tuples
    """
    res = {}
    for d in ds:
        if not isinstance(d, dict):
            res = {**res, **d._asdict()}
        else:
            res = {**res, **d}
    return res


def wrap_angle(angles):
    """ 
        Maps a list of angles in RADIANS to [-pi, pi]
    """
    angles = np.array(angles)
    return (angles + np.pi) % (2 * np.pi) - np.pi
