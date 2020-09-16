from collections import namedtuple
import numpy as np
import matplotlib.pyplot as plt

from fcutils.maths.geometry import calc_distance_between_points_2d
from fcutils.plotting.utils import clean_axes
from fcutils.plotting.colors import desaturate_color
from fcutils.plotting.plot_elements import plot_line_outlined

from proj.utils import polar_to_cartesian, seagreen, salmon
from proj.paths import frames_cache

_xy = namedtuple("xy", "x, y")
_xyt = namedtuple("xyt", "x, y, t")


def press(event, self):
    """ 
        Deals with key press during interactive visualizatoin
    """
    if event.key == "c":
        print("stopping")
        self.stop = True


class World:
    """
        Class to keep a representation of the world (model + trajectory)
        in euclidean representation, regardless of the model's own coordinates system
    """

    stop = False
    _cache = dict(speed_plot_x=[], speed_plot_y=[],)

    def __init__(self, model):
        self.model = model
        self.plot_every = self.model.traj_plot_every

    # -------------------------------- Initialize -------------------------------- #

    def _initialize_world(self, trajectory):
        # Get the world size from Config
        maxd = self.model.trajectory["distance"]
        world_size = _xy([-maxd, maxd], [-maxd, maxd])

        # check that the trajectory fits in the world size
        if np.min(trajectory[:, 0]) < world_size.x[0]:
            world_size.x[0] = np.min(trajectory[:, 0])

        if np.max(trajectory[:, 0]) > world_size.x[1]:
            world_size.x[1] = np.max(trajectory[:, 0])

        if np.min(trajectory[:, 1]) < world_size.y[0]:
            world_size.y[0] = np.min(trajectory[:, 1])

        if np.max(trajectory[:, 1]) > world_size.y[1]:
            world_size.y[1] = np.max(trajectory[:, 1])

        return world_size

    def _spawn_model_random(self, trajectory, v=0, omega=0):
        # start as a point in the plane with theta 0
        x = np.random.randint(self.world_size.x[0], self.world_size.x[1] / 5)
        y = np.random.randint(self.world_size.y[0], self.world_size.y[1] / 5)

        traj_start = _xy(trajectory[0, 0], trajectory[0, 1])

        if self.model.MODEL_TYPE == "cartesian":
            raise NotImplementedError(
                "Compute theta given position and trajectory"
            )

            # keep track of model's position
            # self.model_position_world = _xyt(x, y, t)

        elif self.model.MODEL_TYPE == "polar":
            # compute r and gamma
            r = calc_distance_between_points_2d(
                [x, y], [traj_start.x, traj_start.y]
            )
            gamma = np.arctan2(traj_start.x - x, traj_start.y - y)

            # update model state
            self.model.curr_x = self.model._state(r, gamma, v, omega)

            # keep track of model's position
            self.model_position_world = _xy(x, y)

    def _spawn_model_trajectory(self, trajectory, v=0, omega=0):
        """
            Spawn model at start/end of trajectory
        """
        if self.model.MODEL_TYPE == "cartesian":
            self.model.curr_x = self.model._state(
                trajectory[0, 0],
                trajectory[0, 1],
                trajectory[0, 2],
                trajectory[0, 3],
                omega,
            )

            # keep track of model's position
            self.model_position_world = _xyt(
                trajectory[0, 0], trajectory[0, 1], trajectory[0, 2]
            )

        elif self.model.MODEL_TYPE == "polar":
            self.model.curr_x = self.model._state(
                trajectory[-1, 0], trajectory[-1, 1], v, omega
            )

            # keep track of model's position
            self.model_position_world = _xy(
                *polar_to_cartesian(trajectory[-1, 0], trajectory[-1, 1])
            )
            polar_to_cartesian

    def _reset_world_history(self, trajectory):
        # trajectory
        self.initial_trajectory = trajectory

        # model position world
        self.initial_model_position_world = self.model_position_world
        self.model_position_history_world = [self.initial_model_position_world]

    def make_figure(self):
        self.f = plt.figure(constrained_layout=True, figsize=(12, 8))

        gs = self.f.add_gridspec(2, 4)
        self.xy_ax = self.f.add_subplot(gs[:, :2])
        self.xy_ax.axis("equal")
        self.xy_ax.axis("off")

        self.tau_ax = self.f.add_subplot(gs[0, 2:])

        self.sax = self.f.add_subplot(gs[1, 2:])

        clean_axes(self.f)

        self.f.canvas.mpl_connect(
            "key_press_event", lambda event: press(event, self)
        )

    def initialize_world(self, trajectory):
        """
            Create the world and the model at some location
        """
        # create world
        self.world_size = self._initialize_world(trajectory)

        # spawn model
        if self.model.SPAWN_TYPE == "random":
            self._spawn_model_random(trajectory)
        else:
            self._spawn_model_trajectory(trajectory)

        # reset history
        self._reset_world_history(trajectory)

        # create a figure for live plotting
        plt.ion()
        self.make_figure()

    # ---------------------------------- Update ---------------------------------- #

    def update_world(self, curr_goals, elapsed=None):
        # Get model's position
        if self.model.MODEL_TYPE == "cartesian":
            x, y = self.model.curr_x.x, self.model.curr_x.y
            t = self.model.curr_x.theta

            self.model_position_history_world.append(_xyt(x, y, t))

        else:
            print("polar to cartesian is incorrect in world history")
            x, y = polar_to_cartesian(
                self.model.curr_x.r, self.model.curr_x.gamma
            )

            self.model_position_history_world.append(_xy(x, y))

        self.model_position_world = self.model_position_history_world[-1]

        # Update plots
        self.visualize_world_live(curr_goals, elapsed=elapsed)

    # ------------------------------- Live plotting ------------------------------ #
    def _plot_xy(self, ax, curr_goals):
        # plot currently selected goals
        if self.model.MODEL_TYPE == "cartesian":
            ax.plot(
                curr_goals[:, 0],
                curr_goals[:, 1],
                lw=10,
                color=salmon,
                zorder=-1,
                solid_capstyle="round",
            )
        else:
            print("current goals for polar")
            # raise NotImplementedError("current goals for polar")

        # plot position history
        X = [pos.x for pos in self.model_position_history_world]
        Y = [pos.y for pos in self.model_position_history_world]

        ax.plot(
            X,
            Y,
            lw=9,
            color=desaturate_color(seagreen),
            zorder=-1,
            solid_capstyle="round",
        )

        # plot current position
        x, y = self.model_position_world.x, self.model_position_world.y

        ax.scatter(
            x, y, s=350, color=seagreen, lw=1.5, edgecolors=[0.3, 0.3, 0.3]
        )

        if self.model.MODEL_TYPE == "cartesian":
            # plot body axis
            t = self.model_position_world.t
            dx = np.cos(t) * self.model.mouse["length"]
            dy = np.sin(t) * self.model.mouse["length"]

            ax.plot([x, x + dx], [y, y + dy], lw=8, color=seagreen)
            ax.scatter(
                x + dx,
                y + dy,
                s=225,
                color=seagreen,
                lw=1.5,
                edgecolors=[0.3, 0.3, 0.3],
            )

        ax.axis("equal")
        ax.axis("off")

    def plot_control(self, keep_s=1.2):
        keep_n = int(keep_s / self.model.dt)
        ax = self.tau_ax
        ax.clear()

        R, L = self.model.history["tau_r"], self.model.history["tau_l"]
        n = len(R)

        # plot traces
        plot_line_outlined(
            ax,
            R,
            color="r",
            label="$\\tau_R$",
            lw=3,
            solid_joinstyle="round",
            solid_capstyle="round",
        )
        plot_line_outlined(
            ax,
            L,
            color="b",
            label="$\\tau_L$",
            lw=3,
            solid_joinstyle="round",
            solid_capstyle="round",
        )

        # set axes
        ymin = np.min(np.vstack([R[n - keep_n : n], L[n - keep_n : n]]))
        ymax = np.max(np.vstack([R[n - keep_n : n], L[n - keep_n : n]]))

        if n > keep_n:
            ymin -= np.abs(ymin) * 0.1
            ymax += np.abs(ymax) * 0.1

            ax.set(xlim=[n - keep_n, n], ylim=[ymin, ymax])

        ax.set(ylabel="Forces", xlabel="step n")
        ax.legend()

        # mark the times a change of traj idx happened
        for v in self.moved_to_next:
            ax.axvline(v, color="k")

    def plot_current_variables(self):
        """
            Plot the agent's current state vs where it should be
        """

        ax = self.sax
        ax.clear()

        # plot speed trajectory
        color = "#B22222"

        if self.model.MODEL_TYPE == "cartesian":
            idx = 3
        else:
            idx = 2

        ax.scatter(
            np.arange(len(self.initial_trajectory[:, idx]))[
                :: self.plot_every
            ],
            self.initial_trajectory[:, idx][:: self.plot_every],
            color=color,
            label="trajectory speed",
            lw=1,
            edgecolors="white",
            s=100,
        )

        # plot current speed
        ax.scatter(
            self.curr_traj_waypoint_idx,
            self.model.history["v"][-1],
            zorder=100,
            s=300,
            lw=1,
            color="m",
            edgecolors="k",
            label="models speed",
        )

        # store the scatter coords for later plots
        self._cache["speed_plot_x"].append(self.curr_traj_waypoint_idx)
        self._cache["speed_plot_y"].append(self.model.history["v"][-1])

        # plot line
        ax.plot(
            self._cache["speed_plot_x"],
            self._cache["speed_plot_y"],
            color=desaturate_color("m"),
            zorder=-1,
            lw=9,
        )

        ax.legend()
        ax.set(ylabel="speed", xlabel="trajectory progression")

    def visualize_world_live(self, curr_goals, elapsed=None):
        ax = self.xy_ax
        ax.clear()

        # plot trajectory
        ax.scatter(
            self.initial_trajectory[:: self.plot_every, 0],
            self.initial_trajectory[:: self.plot_every, 1],
            s=50,
            color=[0.4, 0.4, 0.4],
            lw=1,
            edgecolors="white",
        )

        # highlight current trajectory point
        ax.scatter(
            self.current_traj_waypoint[0],
            self.current_traj_waypoint[1],
            s=30,
            color="r",
            lw=1,
            edgecolors="white",
            zorder=99,
        )

        # plot XY tracking
        self._plot_xy(ax, curr_goals)
        ax.set(
            title=f"Elapsed time: {round(elapsed, 2)}s | goal: {round(self.goal_duration, 2)}s\n"
            + f"trajectory progression: {self.curr_traj_waypoint_idx}/{len(self.initial_trajectory)}"
        )

        # plot control
        self.plot_control()

        # plot current waypoint
        self.plot_current_variables()

        # display plot
        self.f.canvas.draw()
        plt.pause(0.001)

        # save figure for gif making
        if self.itern < 10:
            n = f"0{self.itern}"
        else:
            n = str(self.itern)
        self.f.savefig(str(frames_cache / n))
