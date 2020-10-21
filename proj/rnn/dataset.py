import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.model_selection import train_test_split
from rich.progress import track
from rich.prompt import Confirm
from rich import print
import numpy as np


from pyinspect.utils import subdirs

from proj.rnn._utils import RNNLog
from proj.utils.misc import (
    load_results_from_folder,
    trajectory_at_each_simulation_step,
)


def get_inputs(trajectory, history):
    traj_sim = trajectory_at_each_simulation_step(trajectory, history)
    # goal_traj = history[
    #     ["goal_x", "goal_y", "goal_theta", "goal_v", "goal_omega"]
    # ].values

    # delta_traj = goal_traj - traj_sim
    # delta_traj = goal_traj[1:, :] - traj_sim[:-1, :]

    # TODO Fix this once new data come in
    return traj_sim


def get_outputs(history):
    # return np.vstack([history["tau_r"][1:], history["tau_l"][1:]])
    return np.vstack([history["nudot_right"][1:], history["nudot_left"][1:]])


def plot_dataset(inputs, outputs):
    f, axarr = plt.subplots(ncols=4, nrows=2, figsize=(20, 12))
    titles = [
        "X",
        "Y",
        "\\theta",
        "v",
        "\\omega",
        "\\tau_{R}",
        "\\tau_{L}",
    ]
    for n, (ax, ttl) in enumerate(zip(axarr.flatten(), titles)):
        if n <= 4:
            ax.hist(inputs[:, n], bins=100)
        else:
            ax.hist(outputs[:, n - 5], bins=100)
        ax.set(title=f"${ttl}$")
    plt.show()


class DatasetMaker(RNNLog):
    """
        Class to take the results of iLQR and organize them
        into a structured dataset that can be used for training RNNs
    """

    def __init__(self):
        RNNLog.__init__(self, mk_dir=False)

    def _standardize_dataset(self, trials_folders):
        """ 
            Creates preprocessing tools to standardize the dataset's
            inputs and outputs to facilitate RNN training.
            It pools data for the whole dataset to fit the standardizers.
        """
        print("Normalizing dataset")
        # Get normalizer
        if self.config["dataset_normalizer"] == "scale":
            input_scaler = MinMaxScaler(feature_range=(-1, 1))
            output_scaler = MinMaxScaler(feature_range=(-1, 1))
        else:
            input_scaler = StandardScaler()
            output_scaler = StandardScaler()

        # Get ALL data to fit the normalizer
        all_trajs, all_outputs = [], []
        for fld in track(trials_folders):
            try:
                (
                    config,
                    trajectory,
                    history,
                    cost_history,
                    trial,
                    info,
                ) = load_results_from_folder(fld)
            except Exception:
                continue

            if info["traj_duration"] < 1:
                continue

            # stack inputs
            delta_traj = get_inputs(trajectory, history)
            all_trajs.append(delta_traj)

            # stack outputs
            all_outputs.append(get_outputs(history))

        # fit normalizer
        _in, _out = np.vstack(all_trajs), np.hstack(all_outputs).T

        input_scaler = input_scaler.fit(_in)
        output_scaler = output_scaler.fit(_out)

        if self.config["interactive"]:
            print("Visualizing dataset")
            plot_dataset(_in, _out)

            if Confirm.ask("Continue with [b]dataset creation?", default=True):
                # Save normalizer to invert the process in the future
                self.save_normalizers(input_scaler, output_scaler, _in, _out)
                return input_scaler, output_scaler
            else:
                print("Did not create dataset")
                return None, None
        else:
            self.save_normalizers(input_scaler, output_scaler, _in, _out)
            return input_scaler, output_scaler

    def _split_and_save(self, data):
        """ 
            Splits the dataset into training and test data
            before saving.
        """
        data = pd.DataFrame(data)  # .to_hdf(self.dataset_path, key="hdf")

        train, test = train_test_split(data)

        train.to_hdf(self.dataset_train_path, key="hdf")
        test.to_hdf(self.dataset_test_path, key="hdf")

        print(f"Saved at {self.dataset_train_path}, {len(data)} trials")

    def make_dataset(self):
        """ 
            Organizes the standardized data into a single dataframe.
        """
        trials_folders = subdirs(self.trials_folder)
        print(
            f"[bold magenta]Creating dataset...\nFound {len(trials_folders)} trials folders."
        )

        input_scaler, output_scaler = self._standardize_dataset(trials_folders)
        if input_scaler is None:
            return

        print("Creating training data")
        data = dict(trajectory=[], tau_r=[], tau_l=[], sim_dt=[],)
        for fld in track(trials_folders):
            try:
                (
                    config,
                    trajectory,
                    history,
                    cost_history,
                    trial,
                    info,
                ) = load_results_from_folder(fld)
            except Exception:
                continue

            # Get inputs and outputs
            delta_traj = get_inputs(trajectory, history)

            out = get_outputs(history).T

            # Resample imput trajectory
            start_idx = history.trajectory_idx.values[0]
            end_idx = history.trajectory_idx.values[-1] - 30
            delta_traj = delta_traj[start_idx:end_idx, :]
            # delta_traj = resample(delta_traj[start_idx:end_idx, :], out.shape[0])

            # Normalize data
            norm_input = input_scaler.transform(delta_traj)
            norm_output = output_scaler.transform(out)

            # if self.config["dataset_normalizer"] == "scale":
            #     # ? When scaling ignore small trials
            #     if (
            #         np.max(norm_output[50:-50, :]) < 0.2
            #         and np.min(norm_output[50:-50, :]) > -0.2
            #     ):
            #         continue

            # Append to dataset
            data["trajectory"].append(norm_input)
            data["tau_r"].append(norm_output[:, 0])
            data["tau_l"].append(norm_output[:, 1])
            data["sim_dt"].append(config["dt"])

        # Save data to file
        if self.config["interactive"]:
            plot_dataset(
                np.vstack(data["trajectory"]),
                np.vstack(
                    [
                        np.concatenate(data["tau_r"]),
                        np.concatenate(data["tau_l"]),
                    ]
                ).T,
            )

            if Confirm.ask("Save dataset?", default=True):
                self._split_and_save(data)
            else:
                print("Did not save dataset")
        else:
            self._split_and_save(data)
