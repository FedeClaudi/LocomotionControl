import numpy as np
from sympy import (
    Matrix,
    symbols,
    init_printing,
    lambdify,
    cos,
    sin,
    SparseMatrix,
)

from collections import namedtuple

from fcutils.maths.geometry import calc_distance_between_points_2d

from proj.model.config import Config
from proj.utils.misc import merge
from proj.control.utils import fit_angle_in_range
from proj.model.fast import (
    fast_dqdt,
    fast_model_jacobian_state,
    fast_model_jacobian_input,
)

init_printing()


class Model(Config):
    MODEL_TYPE = "cartesian"

    _M_args = [
        "theta",
        "v",
        "omega",
        "L",
        "R",
        "m",
        "d",
        "m_w",
        "tau_l",
        "tau_r",
    ]

    _calc_model_jacobian_state_args = [
        "theta",
        "v",
        "omega",
        "L",
        "R",
        "m",
        "d",
        "m_w",
    ]
    _calc_model_jacobian_input_args = ["L", "R", "m", "d", "m_w"]

    _control = namedtuple("control", "tau_r, tau_l")
    _state = namedtuple("state", "x, y, theta, v, omega")
    _goal = namedtuple(
        "state", "goal_x, goal_y, goal_theta, goal_v, goal_omega"
    )
    _dxdt = namedtuple("dxdt", "x_dot, y_dot, theta_dot, v_dot, omega_dot")
    _wheel_state = namedtuple("wheel_state", "nudot_right, nudot_left")

    def __init__(self, startup=True, trial_n=0):
        Config.__init__(self)
        self.trajectory["trial_n"] = trial_n

        self._make_simbols()

        if startup:
            if not self.USE_FAST:
                self.get_combined_dynamics_kinematics()
                # self.get_inverse_dynamics()
                self.get_jacobians()
            else:
                self.calc_dqdt = fast_dqdt
                self.calc_model_jacobian_state = fast_model_jacobian_state
                self.calc_model_jacobian_input = fast_model_jacobian_input

            self.get_wheels_dynamics()
            self.reset()

    def reset(self):
        self.history = dict(
            x=[],
            y=[],
            theta=[],
            v=[],
            omega=[],
            goal_x=[],
            goal_y=[],
            goal_theta=[],
            goal_v=[],
            goal_omega=[],
            tau_r=[],
            tau_l=[],
            r=[],
            gamma=[],
            trajectory_idx=[],
            nudot_left=[],  # acceleration of left wheel
            nudot_right=[],  # acceleration of right wheel
        )

    def _append_history(self):
        for ntuple in [
            self.curr_x,
            self.curr_control,
            self.curr_wheel_state,
            self.curr_goal,
        ]:
            for k, v in ntuple._asdict().items():
                self.history[k].append(v)

        self.history["trajectory_idx"].append(
            self.curr_traj_waypoint_idx
        )  # this is updated by env.plan

    def _make_simbols(self):
        # state variables
        x, y, theta, thetadot = symbols("x, y, theta, thetadot", real=True)

        # static variables
        L, R, m, m_w, d = symbols("L, R, m, m_w, d", real=True)

        # control variables
        tau_r, tau_l = symbols("tau_r, tau_l", real=True)

        # speeds
        v, omega = symbols("v, omega", real=True)
        vdot, omegadot = symbols("vdot, omegadot", real=True)

        # store symbols
        self.variables = dict(
            x=x,
            y=y,
            theta=theta,
            L=L,
            R=R,
            m=m,
            m_w=m_w,
            d=d,
            tau_l=tau_l,
            tau_r=tau_r,
            v=v,
            omega=omega,
        )

    def get_combined_dynamics_kinematics(self):
        (
            x,
            y,
            theta,
            L,
            R,
            m,
            m_w,
            d,
            tau_l,
            tau_r,
            v,
            omega,
        ) = self.variables.values()

        # Define moments of inertia
        I_c = m * d ** 2  # mom. inertia around center of gravity
        I_w = m_w * R ** 2  # mom. inertia of wheels
        I = I_c + m * d ** 2 + 2 * m_w * L ** 2 + I_w

        # Define a constant:
        J = I + (2 * I ** 2 / R ** 2) * I_w

        # Define g vector and input vector
        g = Matrix([0, 0, 0, d * omega ** 2, -(m * d * omega * v) / J])
        inp = Matrix([v, omega, tau_r, tau_l])

        # Define M matrix
        M = Matrix(
            [
                [cos(theta), 0, 0, 0],
                [sin(theta), 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, L / (m * R), L / (m * R)],
                [0, 0, L / (J * R), -L / (J * R)],
            ]
        )

        # vectorize expression
        args = [theta, v, omega, L, R, m, d, m_w, tau_l, tau_r]
        expr = g + M * inp
        self.calc_dqdt = lambdify(args, expr, modules="numpy")

        # store matrices
        self.matrixes = dict(g=g, inp=inp, M=M,)

        # Store dxdt model as sympy expression
        self.model = g + M * inp

    def get_inverse_dynamics(self):
        """
            If the model is
                x_dot = g + M*tau
            the inverse model is
                tau = M_inv * (x_dot - g)
        """
        # Get variables
        (
            x,
            y,
            theta,
            L,
            R,
            m,
            m_w,
            d,
            tau_l,
            tau_r,
            v,
            omega,
        ) = self.variables.values()
        state = Matrix([x, y, theta, v, omega])

        # Get inverse of M matrix
        M_inv = SparseMatrix(
            self.matrixes["M"]
        ).pinv()  # recast as sparse for speed

        # Get inverse model
        self.model_inverse = M_inv * (state - self.matrixes["g"])

        # Vectorize expression
        args = [x, y, theta, v, omega, L, R, m, d, m_w]

        self.calc_inv_dynamics = lambdify(
            args, self.model_inverse, modules="numpy"
        )

    def get_jacobians(self):
        (
            x,
            y,
            theta,
            L,
            R,
            m,
            m_w,
            d,
            tau_l,
            tau_r,
            v,
            omega,
        ) = self.variables.values()

        # Get jacobian wrt state
        self.model_jacobian_state = self.model.jacobian(
            [x, y, theta, v, omega]
        )

        # Get jacobian wrt input
        self.model_jacobian_input = self.model.jacobian([tau_r, tau_l])

        # vectorize expressions
        args = [theta, v, omega, L, R, m, d, m_w]
        self.calc_model_jacobian_state = lambdify(
            args, self.model_jacobian_state, modules="numpy"
        )

        args = [L, R, m, d, m_w]

        self.calc_model_jacobian_input = lambdify(
            args, self.model_jacobian_input, modules="numpy"
        )

    def get_wheels_dynamics(self):
        (
            x,
            y,
            theta,
            L,
            R,
            m,
            m_w,
            d,
            tau_l,
            tau_r,
            v,
            omega,
        ) = self.variables.values()
        nu_l_dot, nu_r_dot = symbols("nudot_L, nudot_R")

        # define vecs and matrices
        vels = Matrix([v, omega])
        K = Matrix(
            [
                [R / 2 * cos(theta), R / 2 * cos(theta)],
                [R / 2 * sin(theta), R / 2 * sin(theta)],
                [R / (2 * L), -R / (2 * L)],
            ]
        )

        Q = Matrix([[sin(theta), 0], [cos(theta), 0], [0, 1]])

        # In the model you can use the wheels accelerations
        # to get the x,y,theta velocity.
        # Here we do the inverse, given x,y,theta velocities
        # we get the wheel's accelerations

        nu = K.pinv() * Q * vels
        args = [L, R, theta, v, omega]
        self.calc_wheels_accels = lambdify(args, nu, modules="numpy")

    def step(self, u, curr_goal):
        # prep some variables
        self.curr_x = self._state(*self.curr_x)
        self.curr_goal = self._goal(*curr_goal)
        u = self._control(*np.array(u))

        variables = merge(u, self.curr_x, self.mouse)
        inputs = [variables[a] for a in self._M_args]

        # Compute wheel accelerations
        w = self.calc_wheels_accels(
            variables["L"],
            variables["R"],
            variables["theta"],
            self.curr_x.v,
            self.curr_x.omega,
        )
        self.curr_wheel_state = self._wheel_state(*w.ravel())

        # Update history
        self.curr_control = u
        self._append_history()

        # Compute dxdt
        dxdt = self.calc_dqdt(*inputs).ravel()
        self.curr_dxdt = self._dxdt(*dxdt)

        if np.any(np.isnan(dxdt)) or np.any(np.isinf(dxdt)):
            raise ValueError("Nans in dxdt")

        # Step
        next_x = np.array(self.curr_x) + dxdt * self.dt
        self.curr_x = self._state(*next_x)

    def _fake_step(self, x, u):
        """
            Simulate a step fiven a state and a control
        """
        x = self._state(*x)
        u = self._control(*u)

        # Compute dxdt
        variables = merge(u, x, self.mouse)
        inputs = [variables[a] for a in self._M_args]
        dxdt = self.calc_dqdt(*inputs).ravel()

        if np.any(np.isnan(dxdt)) or np.any(np.isinf(dxdt)):
            # raise ValueError('Nans in dxdt')
            print("nans in dxdt during fake step")

        # Step
        next_x = np.array(x) + dxdt * self.dt
        return next_x

    def predict_trajectory(self, curr_x, us):
        """
            Compute the trajectory for N steps given a
            state and a (series of) control(s)
        """
        if len(us.shape) == 3:
            pred_len = us.shape[1]
            us = us.reshape((pred_len, -1))
            expand = True
        else:
            expand = False

        # get size
        pred_len = us.shape[0]

        # initialze
        x = curr_x  # (3,)
        pred_xs = curr_x[np.newaxis, :]

        for t in range(pred_len):
            next_x = self._fake_step(x, us[t])
            # update
            pred_xs = np.concatenate((pred_xs, next_x[np.newaxis, :]), axis=0)
            x = next_x

        if expand:
            pred_xs = pred_xs[np.newaxis, :, :]
            # pred_xs = np.transpose(pred_xs, (1, 0, 2))
        return pred_xs

    def calc_gradient(self, xs, us, wrt="x"):
        """
            Compute the models gradient wrt state or control
        """

        # prep some variables
        theta = xs[:, 2]
        v = xs[:, 3]
        omega = xs[:, 4]

        L = self.mouse["L"]
        R = self.mouse["R"]
        m = self.mouse["m"]
        m_w = self.mouse["m_w"]
        d = self.mouse["d"]

        (_, state_size) = xs.shape
        (pred_len, input_size) = us.shape

        if wrt == "x":
            f = np.zeros((pred_len, state_size, state_size))
            for i in range(pred_len):
                f[i, :, :] = self.calc_model_jacobian_state(
                    theta[i], v[i], omega[i], L, R, m, d, m_w
                )
            return f * self.dt + np.eye(state_size)
        else:
            f = np.zeros((pred_len, state_size, input_size))
            f0 = self.calc_model_jacobian_input(
                L, R, m, d, m_w
            )  # no need to iterate because const.
            for i in range(pred_len):
                f[i, :, :] = f0
            return f * self.dt

    def calc_angle_distance_from_goal(self, goal_x, goal_y):
        # Get current position
        x, y = self.curr_x.x, self.curr_x.y

        gamma = np.arctan2(goal_y - y, goal_x - x)
        gamma = fit_angle_in_range(gamma, is_deg=False)
        gamma -= self.curr_x.theta

        # compute distance
        r = calc_distance_between_points_2d([x, y], [goal_x, goal_y])

        return r, gamma
