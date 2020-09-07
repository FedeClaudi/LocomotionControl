# %%
from proj import (
    Model,
    Environment,
    Controller,
    run_experiment,
    # plot_trajectory,
    # run_manual,
)
from proj.animation.animate import animate_from_images

# import matplotlib.pyplot as plt
import numpy as np

# import matplotlib.pyplot as plt

# TODO move rat image to within package
# ! TODO  formula I_c for cube!
# ! energy considerations, you should need more force to accelerate when going faster?

# TODO fix orientation at start of trajectory

agent = Model()
env = Environment(agent)
control = Controller(agent)

n_steps = 500

t = np.linspace(0, 1, n_steps)
u = np.ones((n_steps, 2)) * 2
u[:, 0] = (np.sin(t) - 0.5) * 2
# u[:, 1] = np.cos(t) * 2
agent.model

# plot_trajectory(env.reset())
# plt.show()

# %%
# agent.curr_x = agent._state(0, 0, 0, 0, 0)

folder = "/Users/federicoclaudi/Dropbox (UCL - SWC)/Rotation_vte/Locomotion/control/tests/anim"
savefolder = "/Users/federicoclaudi/Dropbox (UCL - SWC)/Rotation_vte/Presentations/Presentations/goal_directed_locomotion"
name = "/line.mp4"
savepath = savefolder + name

# run_manual(env, agent, n_steps, u,
#                 ax_kwargs=dict(xlim=[-250, 250], ylim=[-250, 250]),
#                 folder=folder)

run_experiment(env, control, agent, n_steps=2000, frames_folder=None)

animate_from_images(folder, savepath)
