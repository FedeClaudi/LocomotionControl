import numpy as np
from pathlib import Path
import os
class Config:
    # ----------------------------- Simulation params ---------------------------- #
    save_folder = Path('/Users/federicoclaudi/Dropbox (UCL - SWC)/Rotation_vte/Locomotion/control')
    save_name = 'parabola'

    warmup_length = 0
    dt  = .01
    
    # -------------------------------- Cost params ------------------------------- #
    STATE_SIZE = 5
    INPUT_SIZE = 2

    R = np.diag([.01, .01]) # control cost
    Q = np.diag([2.5, 2.5, 2.5, 5, 0]) # state cost | x, y, theta, v, omega
    Sf = np.diag([2.5, 2.5, 2.5, 5, 0]) # final state cost

    # ------------------------------- Mouse params ------------------------------- #

    mouse = dict(
        L = 1.5, # half body width | cm
        R = 1, # radius of wheels | cm
        d = 0.1, # distance between axel and CoM | cm
        length = 6, # cm
        m = round(20/9.81, 2), # mass | g
        m_w = round(2/9.81, 2), # mass of wheels/legs |g
    )

    # ------------------------------ Goal trajectory ----------------------------- #

    trajectory = dict( # parameters of the goals trajectory
        name = 'parabola',
        nsteps = 300, 
        distance = 100,
        max_speed = 20,
        min_speed = 10,
        min_dist = 20, # if agent is within this distance from trajectory end the goal is considered achieved
    )

    # ------------------------------ Planning params ----------------------------- #    
    planning = dict( # params used to compute goal states to be used for control
        prediction_length = 40,
        n_ahead = 5, # start prediction states from N steps ahead
    )

    # ------------------------------ Control params ------------------------------ #
    iLQR = dict(
            max_iter = 500, 
            init_mu = 1.,
            mu_min = 1e-6,
            mu_max = 1e10,
            init_delta = 2.,
            threshold = 1e-6,
    )

    def config_dict(self):
        return dict(
            dt = self.dt,
            STATE_SIZE = self.STATE_SIZE,
            INPUT_SIZE = self.INPUT_SIZE,
            R = list(np.diag(self.R).tolist()),
            Q = list(np.diag(self.Q).tolist()),
            Sf = list(np.diag(self.Sf).tolist()),
            mouse = self.mouse,
            trajectory = self.trajectory,
            planning = self.planning,
            iLQR = self.iLQR,
        )