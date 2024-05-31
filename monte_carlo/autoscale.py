from contextlib import contextmanager
import matplotlib.pyplot as plt

@contextmanager
def autoscale_turned_off(ax=None):
  ax = ax or plt.gca()
  lims = [ax.get_xlim(), ax.get_ylim()]
  yield
  ax.set_xlim(*lims[0])
  ax.set_ylim(*lims[1])