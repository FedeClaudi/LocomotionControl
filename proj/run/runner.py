from tqdm import tqdm
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

from proj.plotting.live import (
    update_interactive_plot,
    update_interactive_plot_manual,
    update_interactive_plot_polar,
)


def run_experiment(
    environment,
    controller,
    model,
    n_secs=10,
    plot=True,
    folder=None,
    frames_folder=None,
):
    """
        Runs an experiment

        :param environment: instance of Environment, is used to specify 
            a goals trajectory (reset) and to identify the next goal 
            states to be considered (plan)

        :param controller: isntance of Controller, used to compute controls

        :param model: instance of Model

        :param n_steps: int, number of steps in iteration

        :returns: the history of events as stored by model
    """
    if folder is not None:
        model.save_folder = Path(folder)

    # reset things
    trajectory = environment.reset()
    model.reset()

    # setup interactive plot
    if plot:
        plt.ion()

        if model.MODEL_TYPE == "cartesian":
            f, axarr = plt.subplots(figsize=(16, 8), ncols=3, nrows=2)
            axarr = axarr.flatten()
        else:
            f = plt.figure(figsize=(22, 8))
            ax = f.add_subplot(131)
            ax2 = f.add_subplot(132)
            pax = f.add_subplot(133, projection="polar")
            axarr = [ax, ax2, pax]

    # save frames
    if frames_folder is not None:
        f2, ax2, = plt.subplots(figsize=(12, 8))

    # Get number of steps
    n_steps = int(n_secs / model.dt)
    print(
        f"Starting simulation with {n_steps} steps [{n_secs} at {model.dt} s/step]"
    )

    # RUN
    for itern in tqdm(range(n_steps)):
        curr_x = np.array(model.curr_x)

        # plan
        g_xs = environment.plan(curr_x, trajectory, itern)

        # obtain sol
        u = controller.obtain_sol(curr_x, g_xs)

        # step
        model.step(u)

        # update world
        environment.update_world(g_xs)

        # Check if we're done
        if environment.isdone(model.curr_x, trajectory):
            print(f"Reached end of trajectory after {itern} steps")
            break

        # update interactieve plot
        if plot:

            if model.MODEL_TYPE == "cartesian":
                goal = model._state(
                    g_xs[0, 0], g_xs[0, 1], g_xs[0, 2], g_xs[0, 3], g_xs[0, 4]
                )
                update_interactive_plot(
                    axarr, model, goal, trajectory, g_xs, itern
                )
            else:
                update_interactive_plot_polar(axarr, model, trajectory, itern)

            f.canvas.draw()
            plt.pause(0.01)

            # save frames for animation
            if frames_folder is not None:
                update_interactive_plot_manual(
                    ax2, model, trajectory=trajectory
                )

                if itern < 10:
                    n = f"0{itern}"
                else:
                    n = str(itern)

                ax2.set(xlim=[-20, 120], ylim=[-20, 20])
                ax2.axis("off")
                f2.savefig(str(Path(frames_folder) / n))

    # SAVE results
    model.save(trajectory)

    return model.history
