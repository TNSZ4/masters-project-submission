# Copyright 2022 The EvoJAX Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import logging
import numpy as np
from typing import Union
from typing import Tuple
from typing import Callable

import jax.numpy as jnp
from jax import tree_util
from flax.core import FrozenDict
import jax
import optax

# Imports the Cloud Logging client library
import google.cloud.logging


def cross_entropy_loss(*, logits, labels):
    labels_onehot = jax.nn.one_hot(labels, num_classes=10)
    return optax.softmax_cross_entropy(logits=logits, labels=labels_onehot).sum()


def compute_metrics(*, logits, labels):
    loss = cross_entropy_loss(logits=logits, labels=labels)
    accuracy = jnp.mean(jnp.argmax(logits, -1) == labels)
    metrics = {
        'loss': loss,
        'accuracy': accuracy,
    }
    return metrics


def get_params_format_fn(init_params: FrozenDict) -> Tuple[int, Callable]:
    """Return a function that formats the parameters into a correct format."""

    flat, tree = tree_util.tree_flatten(init_params)
    params_sizes = np.cumsum([np.prod(p.shape) for p in flat])

    def params_format_fn(params: jnp.ndarray) -> FrozenDict:
        params = tree_util.tree_map(
            lambda x, y: x.reshape(y.shape),
            jnp.split(params, params_sizes, axis=-1)[:-1],
            flat)
        return tree_util.tree_unflatten(tree, params)

    return params_sizes[-1], params_format_fn


def create_logger(name: str,
                  log_dir: str = None,
                  debug: bool = False,
                  google_cloud: bool = True) -> logging.Logger:
    """Create a logger.

    Args:
        name - Name of the logger.
        log_dir - The logger will also log to an external file in the specified
                  directory if specified.
        debug - If we should log in DEBUG mode.
        google_cloud - If being run in google cloud their logging client must be used.

    Returns:
        logging.RootLogger.
    """
    if google_cloud:
        # Instantiates a client
        client = google.cloud.logging.Client()

        # Retrieves a Cloud Logging handler based on the environment
        # you're running in and integrates the handler with the
        # Python logging module. By default this captures all logs
        # at INFO level and higher
        client.setup_logging(log_level=logging.DEBUG if debug else logging.INFO)

    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_format = '%(name)s: %(asctime)s [%(levelname)s] %(message)s'
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO, format=log_format)
    logger = logging.getLogger(name)
    if log_dir:
        log_file = os.path.join(log_dir, f'{name}.txt')
        file_hdl = logging.FileHandler(log_file)
        formatter = logging.Formatter(fmt=log_format)
        file_hdl.setFormatter(formatter)
        logger.addHandler(file_hdl)
    return logger


def load_model(model_dir: str) -> Tuple[np.ndarray, np.ndarray]:
    """Load policy parameters from the specified directory.

    Args:
        model_dir - Directory to load the model from.
    Returns:
        A pair of parameters, the shapes of which are
        (param_size,) and (1 + 2 * obs_params_size,).
    """

    model_file = os.path.join(model_dir, 'model.npz')
    if not os.path.exists(model_file):
        raise ValueError('Model file {} does not exist.')
    with np.load(model_file) as data:
        params = data['params']
        obs_params = data['obs_params']
    return params, obs_params


def save_model(model_dir: str,
               model_name: str,
               params: Union[np.ndarray, jnp.ndarray],
               obs_params: Union[np.ndarray, jnp.ndarray] = None,
               best: bool = False) -> None:
    """Save policy parameters to the specified directory.

    Args:
        model_dir - Directory to save the model.
        model_name - Filename.
        params - The parameters to save.
        obs_params - The observation parameters to save
        best - Whether to save a copy as best.npz.
    """

    model_file = os.path.join(model_dir, '{}.npz'.format(model_name))
    np.savez(model_file,
             params=np.array(params),
             obs_params=np.array(obs_params))
    if best:
        model_file = os.path.join(model_dir, 'best.npz')
        np.savez(model_file,
                 params=np.array(params),
                 obs_params=np.array(obs_params))


def save_lattices(log_dir: str,
                  file_name: str,
                  fitness_lattice: jnp.ndarray,
                  params_lattice: jnp.ndarray,
                  occupancy_lattice: jnp.ndarray) -> None:
    """Save QD method's lattices."""
    file_name = os.path.join(log_dir, '{}.npz'.format(file_name))
    np.savez(file_name,
             params_lattice=np.array(params_lattice),
             fitness_lattice=np.array(fitness_lattice),
             occupancy_lattice=np.array(occupancy_lattice))


def get_tensorboard_log_fn(
        log_dir: str) -> Callable[[int, jnp.ndarray, str], None]:
    """
    Returns a custom logging function for the `evojax` `Trainer`.
    The function logs rewards after every train/test iteration with Tensorboard.
    It tries to use `tensorflow` or `pytorch` as tensorboard provider.

    Args:
        log_dir - directory to save store the tensorboard logs
    """
    try:
        from torch.utils.tensorboard import SummaryWriter

        def log_with_pytorch(i: int, scores: jnp.ndarray, stage: str):
            with SummaryWriter(log_dir=log_dir) as writer:
                writer.add_scalar(
                    f"{stage}/score_min", scores.min().item(), global_step=i)
                writer.add_scalar(
                    f"{stage}/score_max", scores.max().item(), global_step=i)
                writer.add_scalar(
                    f"{stage}/score_mean", scores.mean().item(), global_step=i)
                writer.add_scalar(
                    f"{stage}/score_std", scores.std().item(), global_step=i)
                writer.add_histogram(
                    f"{stage}/score_distribution", np.array(scores),
                    global_step=i)

        return log_with_pytorch

    except ImportError:
        pass

    try:
        import tensorflow as tf

        def log_with_tf(i: int, scores: jnp.ndarray, stage: str):
            with tf.summary.SummaryWriter(log_dir=log_dir).as_default():
                tf.summary.scalar(
                    f"{stage}/score_min", scores.min().item(), step=i)
                tf.summary.scalar(
                    f"{stage}/score_max", scores.max().item(), step=i)
                tf.summary.scalar(
                    f"{stage}/score_mean", scores.mean().item(), step=i)
                tf.summary.scalar(
                    f"{stage}/score_std", scores.std().item(), step=i)
                tf.summary.histogram(
                    f"{stage}/score_distribution", np.array(scores), step=i)

        return log_with_tf

    except ImportError:
        pass

    raise ImportError(
        "Please install the tensorboard AND (tensorflow OR pytorch) "
        "packages to log the rewards to tensorboard")
