# The neural network's shape.
#
#   ingredients (TF-IDF scores, ~one number per ingredient-word)
#        │
#   [ Linear ]  every input connects to every one of 512 hidden "neurons"
#   [ ReLU   ]  keeps positive signals, zeroes negative ones - this is what
#               lets the network learn COMBINATIONS, not just single clues
#   [ Dropout]  while training, randomly switches off half the neurons so
#               the network can't rely on memorising quirks of the data
#   [ Linear ]  512 neurons -> one score per cuisine
#        │
#   20 cuisine scores (highest = the guess)
#
# Without the middle three lines this would be exactly logistic regression -
# your first model.

from torch import nn


class CuisineNet(nn.Module):
    def __init__(self, n_inputs, n_cuisines, hidden=512, dropout=0.5):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(n_inputs, hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, n_cuisines),
        )

    def forward(self, x):
        return self.layers(x)
