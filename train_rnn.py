import matplotlib.pyplot as plt
import os

from pyinspect.utils import timestamp
from pyrnn import CTRNN as RNN
from pyrnn.plot import plot_training_loss
import click
from loguru import logger
import json
import numpy as np
import torch

from fcutils.path import to_json

from control._io import DropBoxUtils, upload_folder

from rnn.dataset.dataset import is_win
from rnn.dataset import plot_predictions, datasets
from rnn.train_params import (
    DATASET,
    N_trials,
    n_units,
    dale_ratio,
    autopses,
    w_in_bias,
    w_in_train,
    w_out_bias,
    w_out_train,
    batch_size,
    epochs,
    lr_milestones,
    lr,
    stop_loss,
    name,
    l2norm,
    tau,
    dt,
)
from rnn.analysis import Pipeline


# Set up
os.environ["KMP_DUPLICATE_LIB_OK"] = "True"


def setup_loggers(winstor, data):
    if winstor:
        main = str(data.rnn_folder / "log.log")
        train = str(data.rnn_folder / "log_training.log")
    else:
        main = "log.log"
        train = "log_training.log"

    logger.add(
        main,
        backtrace=True,
        diagnose=True,
        filter=lambda record: "main" in record["extra"],
        format="{time:YYYY-MM-DD at HH:mm} | {level} | {message}",
    )
    logger.add(
        train,
        filter=lambda record: "training" in record["extra"],
        format="{time:YYYY-MM-DD at HH:mm} |{level}| {message}",
    )
    logger.level("Params", no=38, color="<yellow>", icon="🐍")


# --------------------------------- Make RNNR -------------------------------- #


@logger.catch
def make_rnn(data, winstor):
    logger.bind(main=True).info("Creating RNN")
    rnn = RNN(
        input_size=len(data.inputs_names),
        output_size=len(data.outputs_names),
        n_units=n_units,
        dale_ratio=dale_ratio,
        autopses=autopses,
        w_in_bias=w_in_bias,
        w_in_train=w_in_train,
        w_out_bias=w_out_bias,
        w_out_train=w_out_train,
        on_gpu=is_win if not winstor else True,
        tau=tau,
        dt=dt,
    )
    logger.bind(main=True).info(
        f"Rnn params:\n{json.dumps(rnn.params, sort_keys=True, indent=4)}",
    )

    if winstor:
        # save RNN params
        params = rnn.params
        params["dataset_name"] = data.name
        params["dataset_length"] = len(data)
        to_json(data.rnn_folder / f"rnn.json", params)
    return rnn


# ------------------------------------ fit ----------------------------------- #


@logger.catch
def fit(rnn, winstor, data):
    logger.bind(main=True).info(
        f"Training RNN:", rnn, f"with dataset: {data.name}", sep="\n",
    )

    # log/save training parameters
    try:
        info = dict(
            dataset=data.name,
            dataset_length=len(data),
            n_epochs=epochs,
            lr=lr,
            batch_size=batch_size,
            lr_milestones=lr_milestones,
            l2norm=l2norm,
            stop_loss=stop_loss,
            report_path=None,
            augment_probability=data.augment_probability,
            to_chunks=data.to_chunks,
            chunk_length=data.chunk_length if data.to_chunks else None,
            warmup=data.warmup,
            warmup_len=data.warmup_len,
            smoothing_window_size=data.smoothing_window,
        )
    except Exception as e:
        logger.bind(main=True).warning(
            f"Failed to collate training info with error: {e}",
        )
        raise ValueError("Failed to collate info prior to fitting model")

    logger.bind(main=True).info(
        f"Training params:\n{json.dumps(info, sort_keys=True, indent=4)}",
    )
    to_json(data.rnn_folder / f"training_params.json", info)

    # FIT
    save_path = (
        "minloss.pt" if not winstor else str(data.rnn_folder / "minloss.pt")
    )
    logger.bind(main=True).info(f"Saving min loss weights at: {save_path}",)

    loss_history = rnn.fit(
        data,
        n_epochs=epochs,
        lr=lr,
        batch_size=batch_size,
        lr_milestones=lr_milestones,
        l2norm=l2norm,
        stop_loss=stop_loss,
        plot_live=True if not winstor else False,
        report_path=None,
        logger=logger,
        save_at_min_loss=True,
        save_path=save_path,
    )
    logger.bind(main=True).info(
        f"Finished training.\nMin loss: {np.min(loss_history)}\nLast loss: {loss_history[-1]}",
    )

    return loss_history


# ---------------------------------- wrap up --------------------------------- #


def upload_to_db(data):
    dbx = DropBoxUtils()
    dpx_path = data.rnn_folder.name
    logger.bind(main=True).info(
        f"Uploading data to dropbox at: {dpx_path}", extra={"markup": True}
    )

    try:
        upload_folder(dbx, data.rnn_folder, dpx_path)
    except Exception as e:
        logger.bind(main=True)(f"Failed to upload to dropbox with error: {e}")


def load_minloss(data, winstor):
    """
        Load RNN model saved at minimal loss
    """
    min_loss_path = (
        "minloss.pt" if not winstor else str(data.rnn_folder / "minloss.pt")
    )
    use_gpu = is_win if not winstor else True
    rnn = RNN.load(
        min_loss_path,
        n_units=n_units,
        input_size=len(data.inputs_names),
        output_size=len(data.outputs_names),
        on_gpu=use_gpu,
        load_kwargs=dict(map_location=torch.device("cpu"))
        if not use_gpu
        else {},
    )
    return rnn


@logger.catch
def wrap_up(rnn, loss_history, winstor, data):
    logger.bind(main=True).info("Wrapping up")

    # save RNN
    NAME = f"rnn_{name}_{data.name}.pt"
    if winstor:
        NAME = str(data.rnn_folder / NAME)
        rnn.params_to_file(str(data.rnn_folder / f"rnn.txt"))
    rnn.save(NAME, overwrite=True)

    # load lowest loss rnn and plot stuff
    logger.bind(main=True).info(f"Loading min loss RNN to plot accuracy")
    rnn = load_minloss(data, winstor)

    # make/save plots
    f2 = plot_training_loss(loss_history)

    if not winstor:
        plot_predictions(rnn, data)
        plt.show()
    else:
        # plot a bunch of times
        for rep in range(10):
            f1 = plot_predictions(rnn, data)
            f1.savefig(data.rnn_folder / f"predictions_{rep}.png")
        f2.savefig(data.rnn_folder / f"training_loss.png")

    logger.bind(main=True).info(f"Saved RNN at: {NAME}")

    # Run analysis
    logger.bind(main=True).info(f"Running analysis pipeline")
    Pipeline(
        data.rnn_folder,
        winstor=True,
        fit_fps=False,
        _logger=logger.bind(main=True),
    ).run()

    # copy data to dropbox app
    if winstor:
        upload_to_db(data)


# ---------------------------------------------------------------------------- #
#                                   MAIN FUNC                                  #
# ---------------------------------------------------------------------------- #


@click.command()
@click.argument("dataset", default="")
@click.option("-w", "--winstor", is_flag=True, default=False)
def train(dataset, winstor):
    # get userinput dataset
    if dataset:
        try:
            _dataset = datasets[dataset]
        except KeyError:
            raise KeyError(
                f"Could not find dataset {dataset}, available dataset: {datasets.keys()}"
            )
    else:
        _dataset = DATASET

    # load dataset
    data = _dataset(dataset_length=N_trials, winstor=winstor)
    if winstor:
        data.make_save_rnn_folder(name + "_" + data.name)

    # start logging
    setup_loggers(winstor, data)
    logger.bind(main=True).info(
        "\n"
        + "#" * 60
        + "\n"
        + "  " * 5
        + f"Starting: {timestamp()}"
        + "     " * 5
        + "\n"
        + "#" * 60
        + "\n\n"
    )

    if winstor:
        logger.bind(main=True).info(f"RNN folder: {data.rnn_folder}")

    # Create RNN
    rnn = make_rnn(data, winstor)

    # fit
    logger.bind(main=True).info("Starting to fit model")
    loss_history = fit(rnn, winstor, data)

    # wrap up
    wrap_up(rnn, loss_history, winstor, data)


if __name__ == "__main__":
    train()
