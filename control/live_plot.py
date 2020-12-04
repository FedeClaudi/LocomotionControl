import matplotlib.pyplot as plt
import numpy as np
import logging

from fcutils.plotting.utils import clean_axes
from fcutils.plotting.colors import desaturate_color
from fcutils.plotting.plot_elements import plot_line_outlined

from .plot import colors
from .config import dt, px_to_cm, MOUSE


def press(event, self):
    """ 
        Deals with key press during interactive visualization
    """
    if event.key == "c":
        logging.info(
            "Stopping because user manually terminated simulation (presed C)"
        )
        self.stop = True


class Plotter:
    _cache = dict(speed_plot_x=[], speed_plot_y=[],)

    def __init__(
        self, frames_folder, trajectory, plot_every=10, goal_duration=1
    ):
        self.frames_folder = frames_folder
        self.trajectory = trajectory
        self.plot_every = plot_every
        self.goal_duration = goal_duration

    def make_figure(self):
        plt.ion()

        self.f = plt.figure(figsize=(12, 8))

        gs = self.f.add_gridspec(2, 3)  # 6)
        self.xy_ax = self.f.add_subplot(gs[:, :2])
        self.xy_ax.axis("equal")
        self.xy_ax.axis("off")

        self.tau_ax = self.f.add_subplot(gs[0, 2:4])

        self.sax = self.f.add_subplot(gs[1, 2:4])

        clean_axes(self.f)

        self.f.canvas.mpl_connect(
            "key_press_event", lambda event: press(event, self)
        )

    def update(
        self, history, curr_goals, current_traj_waypoint, itern, elapsed=None
    ):
        ax = self.xy_ax
        ax.clear()

        # plot trajectory
        ax.scatter(
            self.trajectory[:: self.plot_every, 0],
            self.trajectory[:: self.plot_every, 1],
            s=50,
            color=colors["trajectory"],
            lw=1,
            edgecolors=[0.8, 0.8, 0.8],
        )

        # highlight current trajectory point
        ax.scatter(
            current_traj_waypoint[0],
            current_traj_waypoint[1],
            s=30,
            color="r",
            lw=1,
            edgecolors=[0.8, 0.8, 0.8],
            zorder=99,
        )

        # plot XY tracking
        self._plot_xy(ax, curr_goals, history)
        ax.set(
            title=f"Elapsed time: {round(elapsed, 2)}s | goal: {round(self.goal_duration, 2)}s\n"
        )

        # plot control
        self._plot_control(history)

        # plot sped
        self._plot_current_variables(history)

        # display plot
        self.f.canvas.draw()
        plt.pause(0.01)

        # save figure for gif making
        if itern < 10:
            n = f"0{itern}"
        else:
            n = str(itern)
        self.f.savefig(str(self.frames_folder / n))

    # ------------------------------- Live plotting ------------------------------ #
    def _plot_xy(self, ax, curr_goals, history):
        # plot currently selected goals
        ax.plot(
            curr_goals[:, 0],
            curr_goals[:, 1],
            lw=10,
            color="r",
            alpha=0.5,
            zorder=-1,
            solid_capstyle="round",
        )

        # plot position history
        ax.plot(
            history["x"],
            history["y"],
            lw=9,
            color=desaturate_color(colors["tracking"]),
            zorder=-1,
            solid_capstyle="round",
        )

        # plot current position
        x, y, t = history["x"][-1], history["y"][-1], history["theta"][-1]

        ax.scatter(  # plot body
            x,
            y,
            s=200,
            color=colors["tracking"],
            lw=1.5,
            edgecolors=[0.3, 0.3, 0.3],
        )

        # plot body axis
        dx = np.cos(t) * (MOUSE["length"] * (1 / px_to_cm) - 0.5)
        dy = np.sin(t) * (MOUSE["length"] * (1 / px_to_cm))

        ax.plot([x, x + dx], [y, y + dy], lw=8, color=colors["tracking"])
        ax.scatter(  # plot head
            x + dx,
            y + dy,
            s=125,
            color=colors["tracking"],
            lw=1.5,
            edgecolors=[0.3, 0.3, 0.3],
        )

        ax.axis("equal")
        ax.axis("off")

    def _plot_control(self, history, keep_s=1.2):
        keep_n = int(keep_s / dt)
        ax = self.tau_ax
        ax.clear()

        R, L = history["tau_r"], history["tau_l"]
        n = len(R)

        # plot traces
        plot_line_outlined(
            ax,
            R,
            color=colors["tau_r"],
            label="$\\tau_R$",
            lw=2,
            solid_joinstyle="round",
            solid_capstyle="round",
        )
        plot_line_outlined(
            ax,
            L,
            color=colors["tau_l"],
            label="$\\tau_L$",
            lw=2,
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

        ax.set(ylabel="Torque\n($\\frac{cm^2 g}{s^2}$)", xlabel="step n")
        ax.legend()
        ax.set(title="Control")

    def _plot_current_variables(self, history):
        """
            Plot the agent's current state vs where it should be
        """

        ax = self.sax
        ax.clear()

        # plot speed trajectory
        ax.scatter(
            np.arange(len(self.trajectory[:, 3]))[:: self.plot_every],
            self.trajectory[:, 3][:: self.plot_every],
            color=colors["v"],
            label="trajectory speed",
            lw=1,
            edgecolors=[0.8, 0.8, 0.8],
            s=100,
        )

        # plot current speed
        ax.scatter(
            history["trajectory_idx"][-1],
            history["v"][-1],
            zorder=100,
            s=300,
            lw=1,
            color=colors["v"],
            edgecolors="k",
            label="models speed",
        )

        # store the scatter coords for later plots
        self._cache["speed_plot_x"].append(history["trajectory_idx"][-1])
        self._cache["speed_plot_y"].append(history["v"][-1])

        # plot line
        ax.plot(
            self._cache["speed_plot_x"],
            self._cache["speed_plot_y"],
            color=desaturate_color(colors["v"]),
            zorder=-1,
            lw=9,
        )

        ax.legend()
        ax.set(title="Speed")
        ax.set(ylabel="speed", xlabel="trajectory progression")