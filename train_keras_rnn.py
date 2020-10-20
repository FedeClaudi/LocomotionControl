from proj.rnn.dataset import DatasetMaker
from proj.rnn.train import RNNTrainer

train = True

# TODO make it predict wheels velocity instead of controls

# ? Make dataset
if not train:
    maker = DatasetMaker()
    maker.make_dataset()

# ? Train
if train:
    trainer = RNNTrainer()
    trainer.train()

# TODO make custom layers work when loading mdoelq

# TODO look into time steps resolution and match it to simulations

# TODO make winstor save to dropbox

# TODO look into normalizations etc.
# TODO parameters grid search


# TODO implement continous time RNN to match other stuff
# see https://github.com/Faur/CTRNN/blob/master/CTRNN.py
