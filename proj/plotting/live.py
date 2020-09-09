import numpy as np
from matplotlib import transforms
import matplotlib.pyplot as plt

from fcutils.maths.utils import derivative
from fcutils.plotting.colors import desaturate_color

from proj.utils import polar_to_cartesian


def plot_mouse(curr_x, mouse, ax):
    """
        Given the state and mouse params plots a mouse
    """
    # Read image and craete transform to move it to 0, 0

    img = plt.imread("rat.png")
    tr = (
        transforms.Affine2D()
        .scale(0.03)
        .translate(-7, -5)
        .rotate_deg(180 - 90)
        .rotate(curr_x.theta)
    )

    # Move mouse to current place
    tr = tr.translate(curr_x.x, curr_x.y)

    ax.imshow(img, origin="upper", transform=tr + ax.transData)

    _ = ax.set(xlim=[-20, 80], ylim=[-10, 110])


def update_interactive_plot_manual(ax, model, trajectory=None):
    ax.clear()
    x = model.curr_x

    # plot mouse and XY tracking history
    plot_mouse(x, model.mouse, ax)
    ax.plot(model.history["x"], model.history["y"], color="g", lw=1.5, ls="--")

    if trajectory is not None:
        ax.plot(trajectory[:, 0], trajectory[:, 1], color="k", lw=1)


def update_interactive_plot_manual_polar(model, ax, pax, traj=None):
    x, y = polar_to_cartesian(model.curr_x.r, model.curr_x.gamma)

    ax.scatter(x, y)

    pax.scatter(model.curr_x.gamma, model.curr_x.r)

    if traj is not None:
        xtraj, ytraj = polar_to_cartesian(traj[:, 0], traj[:, 1])
        ax.scatter(xtraj, ytraj, lw=1, color="k")

        ax.plot(
            [x, x + (xtraj[0] - x) * 0.1],
            [y, y + (ytraj[0] - y) * 0.1],
            color="k",
            lw=0.5,
        )

        pax.scatter(traj[:, 1], traj[:, 0], lw=1, color="k")

    pax.set(
        title=f"r: {round(model.curr_x.r, 2)} | gamma: {round(model.curr_x.gamma, 2)}"
    )


def update_interactive_plot(axarr, model, goal, trajectory, g_xs, niter):
    """
        Update plot with current situation and controls
    """
    x = model.curr_x

    axarr[0].clear()
    axarr[1].clear()
    axarr[2].clear()
    axarr[4].clear()
    axarr[5].clear()

    # plot trajectory
    axarr[0].scatter(
        trajectory[:, 0],
        trajectory[:, 1],
        c=trajectory[:, 2],
        alpha=0.8,
        zorder=-1,
    )

    # plot currently used goal states
    axarr[0].plot(g_xs[:, 0], g_xs[:, 1], lw=3, color="r", alpha=1, zorder=-1)

    # plot mouse and XY tracking history
    plot_mouse(x, model.mouse, axarr[0])
    axarr[0].plot(
        model.history["x"], model.history["y"], color="g", lw=1.5, ls="--"
    )

    # update ax
    axarr[0].set(
        title=f"ITER: {niter} | x:{round(x.x, 2)}, y:{round(x.y, 2)}, "
        + f" theta:{round(np.degrees(x.theta), 2)}, v:{round(x.v, 2)}\n"
        + f"GOAL: x:{round(goal.x, 2)}, y:{round(goal.y, 2)}, "
        + f" theta:{round(np.degrees(goal.theta), 2)}, v:{round(goal.v, 2)}",
        # xlim=[-15, params['distance']+15], ylim=[-15, params['distance']+15],
    )
    # axarr[0].axis('equal')

    if len(model.history["omega"]) > 5:
        # Plot Angular velocity
        axarr[1].plot(
            model.history["omega"][5:], color="m", lw=4, label="$\omega$"
        )
        axarr[1].legend()
        axarr[1].set(title="Angular velocity")

        # Pot angular accelratopm
        axarr[2].plot(
            derivative(np.array(model.history["omega"][5:])),
            color="m",
            lw=4,
            label="$\dot{\omega}$",
        )
        axarr[2].legend()
        axarr[2].set(title="Angular acceleration")

        # plot controls history
        axarr[3].plot(
            model.history["tau_l"][5:], color="b", lw=4, label="$\\tau_L$"
        )
        axarr[3].plot(
            model.history["tau_r"][5:], color="r", lw=4, label="$\\tau_R$"
        )
        axarr[3].legend()
        axarr[3].set(title="Control")

        # Plot linear velocity
        axarr[4].plot(model.history["v"][5:], color="g", lw=4, label="$v$")
        axarr[4].legend()
        axarr[4].set(title="Linear velocity")

        # Plot linear acceleration
        axarr[5].plot(
            derivative(np.array(model.history["v"][5:])),
            color=desaturate_color("g"),
            lw=4,
            label="$\dot{v}$",
        )
        axarr[5].legend()
        axarr[5].set(title="Linear acceleration")


def update_interactive_plot_polar(axarr, model, trajectory, itern):
    # Setup
    for ax in axarr:
        ax.clear()

    ax, ax2, pax = axarr

    # Plot control history
    ax2.plot(model.history["tau_r"], color="r", lw=2, label="R")
    ax2.plot(model.history["tau_l"], color="b", lw=2, label="L")
    ax2.legend()

    # Plot XY tracking
    x, y = polar_to_cartesian(
        model.history["r"], np.pi - np.array(model.history["gamma"])
    )

    xtraj, ytraj = polar_to_cartesian(trajectory[:, 0], trajectory[:, 1])
    # xtraj += x[-1]
    # ytraj += y[-1]

    ax.plot(xtraj, ytraj, lw=1, color="k")
    ax.scatter(xtraj[-1], ytraj[-1], s=50, color="k")

    ax.plot(x, y, lw=2, color="g", ls="--")
    ax.scatter(x[-1], y[-1], s=100, color="r")

    ax.scatter(model.initial_pos[0], model.initial_pos[1], s=200, color="g")

    # Plot polar tracking
    pax.plot(trajectory[:, 1], trajectory[:, 0], lw=1, color="k")
    pax.plot(
        model.history["gamma"], model.history["r"], lw=2, color="g", ls="--"
    )
    pax.scatter(model.curr_x.gamma, model.curr_x.r, s=200, color="r")

    # Cleanup
    dist = model.trajectory["distance"]
    ax.set(
        title=f"Iteration number: {itern}",
        xlim=[-dist, dist],
        ylim=[-dist, dist],
    )
    pax.set(
        title=f"r: {round(model.curr_x.r, 2)} | gamma: {round(model.curr_x.gamma, 2)} \n"
        + f"v: {round(model.curr_x.v, 2)} | omega: {round(model.curr_x.omega, 2)}"
    )
