import numpy as np
import pandas as pd
from loguru import logger


from fcutils.maths.signals import derivative
from fcutils.maths.coordinates import pol2cart
from fcutils.maths.geometry import (
    calc_distance_between_points_in_a_vector_2d as get_speed_from_xy,
)

from .utils import calc_bezier_path, get_theta_omega_from_xy
from .config import dt, TRAJECTORY_CONFIG


# --------------------------------- from file -------------------------------- #


def from_file(file_path):
    """
        Load a trajectory from a .npy file. Currently the duration parameter
        is hardcoded, but ideally it should be inferred somehow. 
    """
    duration = 10  # ! this is hardcoded but it shouldn't be ideally

    logger.debug(f"Loading saved trajectory from: {file_path}")
    trajectory = np.load(file_path)

    return None, trajectory, duration, None


# --------------------------------- simulated -------------------------------- #


def simulated():
    """
        Creates an artificial trajectory similar to the ones
        you'd get by loading trajectories from tracking data.

        To define a trajectory of N points:
            1. start with a point (origin at first)
            2. draw an angle and a distance from uniform distributions
            3. turn these into cartesian coordinates and add to previous
                point's coordiates
            4. this is the coordiates for the next point

        in practice two nearby points are drawn at each cycle to ensure steeper bends

        The finally compute the bezier path across all these points
    """
    logger.debug("Creating a simulated trajectory")

    duration = np.random.uniform(3, 6)
    n_frames = int(duration / dt)

    logger.info(
        f"Making simulated traj with duration: {duration} and n steps: {n_frames}"
    )

    # ? make simulated trajectory of N points
    # first point is origin
    points = [np.array([0, 0])]
    prev_phi = 0

    for n in range(50):
        # draw random angle and distance for next point
        sign = -1 if np.random.random() < 0.5 else 1
        _phi = np.random.uniform(0, 65) * sign
        if n == 0:
            _phi = np.random.uniform(0, 360)
        elif n == 1:  # second segment should be straight
            _phi = 0

        phi = _phi + prev_phi
        prev_phi += _phi
        phi = 0

        rho = np.random.uniform(10, 25)
        if n < 3:
            rho = 30

        # get next point's coordinates
        previous = points[-1]
        nxt = np.array(pol2cart(rho, phi)) + previous

        # append to list
        points.append(nxt)

    # Interpolate line segments
    original_xy = np.vstack(points)
    xy = calc_bezier_path(np.vstack(points), TRAJECTORY_CONFIG["n_steps"])
    x, y = xy[:, 0], xy[:, 1]

    # Get theta and omega
    speedup_factor = TRAJECTORY_CONFIG["n_steps"] / n_frames

    theta, omega = get_theta_omega_from_xy(x, y, dt=dt)
    omega *= speedup_factor

    # Get speed
    v = get_speed_from_xy(x, y)

    logger.info(
        f"Simulated trajectory total distance: {np.sum(np.abs(v)):.3f}, total angle: {np.sum(np.abs(np.degrees(derivative(theta)))):.3f}"
    )

    # adjust speed
    v *= speedup_factor / 2
    v *= 1 / dt

    # get 0 vectors for tau
    zeros = np.zeros_like(v) * 0.001  # to avoid 0 in divisions

    # stack
    trajectory = np.vstack([x, y, theta, v, omega, zeros, zeros]).T
    trajectory = trajectory[200:-200, :]

    return (
        original_xy,
        trajectory,
        duration,
        None,
    )


# ------------------------------ From real data ------------------------------ #


def from_tracking(cache_file, trialn=None):
    """
        Get a trajectory from real tracking data, cleaning it up
        a little in the process.

        It expects that XY coordinates are given in cm, angular velocity is in degrees
        per second (and theta in degrees) and speed in cm per second
    """
    logger.debug(f"Loading trajectory from tracing. Trial number: {trialn}")

    # Get a trial
    trials = pd.read_hdf(cache_file, key="hdf")
    if trialn is None:
        trial = trials.sample().iloc[0]
    else:
        trial = trials.iloc[trialn]

    # get expected number of simulation steps
    duration = len(trial.x) / trial.fps  # duration in seconds
    n_frames = int(duration / dt)  # n simulation steps

    """
        the trajectory will be M waypoint nd has to be completed in n_frames .
        How many waypoints should we cover per frame?

    """
    speedup_factor = TRAJECTORY_CONFIG["n_steps"] / (n_frames)

    # Get XY coordinates and interpolate
    x = trial.x
    y = trial.y

    original_xy = np.vstack([x, y])

    xy = calc_bezier_path(np.vstack([x, y]).T, TRAJECTORY_CONFIG["n_steps"])
    x, y = xy[:, 0], xy[:, 1]

    # Get theta and omega
    theta, omega = get_theta_omega_from_xy(x, y, dt=dt)
    omega *= speedup_factor

    # Get speed
    v = get_speed_from_xy(x, y)
    v[0] = v[1]

    logger.info(
        f"Tracking trajectory total distance: {np.sum(np.abs(v)):.3f}cm, total angle: {np.sum(np.abs(np.degrees(derivative(theta)))):.3f}deg"
    )

    # adjust speed
    v *= speedup_factor
    v *= 1 / dt

    # get 0 vectors for tau
    zeros = np.zeros_like(v) * 0.001  # to avoid 0 in divisions

    # stack
    trajectory = np.vstack([x, y, theta, v, omega, zeros, zeros]).T
    trajectory = trajectory[150:-150, :]  # remove artefacts from bezier

    return (
        original_xy,
        trajectory,
        duration,
        trial,
    )
