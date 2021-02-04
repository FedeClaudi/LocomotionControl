import numpy as np
import pandas as pd
from loguru import logger

from fcutils.maths.geometry import (
    calc_angle_between_points_of_vector_2d,
    calc_distance_between_points_in_a_vector_2d,
)
from fcutils.maths.signals import derivative
from fcutils.maths.coordinates import pol2cart

from .utils import interpolate_nans, calc_bezier_path
from .config import dt, px_to_cm, TRAJECTORY_CONFIG

# --------------------------------- from file -------------------------------- #


def from_file(file_path):
    """
        Load a trajectory from a .npy file. Currently the duration parameter
        is hardcoded, but ideally it should be inferred somehow. 
    """
    duration = 10  # ! this is hardcoded but it shouldn't be ideally

    logger.debug(f"Loading saved trajectory from: {file_path}")
    trajectory = np.load(file_path)

    return trajectory, duration, None


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

        rho = np.random.uniform(10, 25)
        if n < 3:
            rho = 30

        # get next point's coordinates
        previous = points[-1]
        nxt = np.array(pol2cart(rho, phi)) + previous

        # append to list
        points.append(nxt)

    # Interpolate line segments
    xy = calc_bezier_path(np.vstack(points), TRAJECTORY_CONFIG["n_steps"])
    x, y = xy[:, 0], xy[:, 1]

    # Get theta
    theta = calc_angle_between_points_of_vector_2d(x, y)
    theta = np.radians(90 - theta)
    theta = np.unwrap(theta)
    theta[0] = theta[1]

    # Get ang vel
    speedup_factor = TRAJECTORY_CONFIG["n_steps"] / n_frames

    omega = derivative(theta) * speedup_factor / 2
    omega[0] = omega[1]
    omega *= 1 / dt

    # Get speed
    v = calc_distance_between_points_in_a_vector_2d(x, y)

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
        trajectory,
        duration,
        None,
    )


# ------------------------------ From real data ------------------------------ #


def from_tracking(cache_file, trialn=None):
    """
        Get a trajectory from real tracking data, cleaning it up
        a little in the process.
    """
    logger.debug(f"Loading trajectory from tracing. Trial number: {trialn}")

    # Get a trial
    trials = pd.read_hdf(cache_file, key="hdf")
    if trialn is None:
        trial = trials.sample().iloc[0]
    else:
        trial = trials.iloc[trialn]

    # Get variables
    fps = trial.fps
    x = trial.x * px_to_cm
    y = trial.y * px_to_cm

    angle = interpolate_nans(trial.theta)
    angle = np.radians(90 - angle)
    angle = np.unwrap(angle)

    speed = trial.v * fps * px_to_cm
    ang_speed = derivative(angle)

    # resample variables so that samples are uniformly distributed
    zeros = np.zeros_like(speed) * 0.001  # to avoid 0 in divisions
    vrs = (x, y, angle, speed, ang_speed, zeros, zeros)
    t = np.arange(len(x))
    vrs = [
        calc_bezier_path(
            np.vstack([t, v]).T[:, 1], TRAJECTORY_CONFIG["n_steps"]
        )
        for v in vrs
    ]

    # stack
    trajectory = np.vstack(vrs).T
    return (
        trajectory,
        len(x) / fps,
        trial,
    )
