# Dynamic Sparsity

This repository has been forked from EvoJAX, and holds all the code used to test and
generate results for accompanying masters project submission.

EvoJAX paper: https://arxiv.org/abs/2202.05008 (presentation [video](https://youtu.be/TMkft3wWpb8))

Please use this BibTeX if you wish to cite EvoJAX in your publications:

```
@article{evojax2022,
  title={EvoJAX: Hardware-Accelerated Neuroevolution},
  author={Tang, Yujin and Tian, Yingtao and Ha, David},
  journal={arXiv preprint arXiv:2202.05008},
  year={2022}
}
```

## Installation

EvoJAX is implemented in [JAX](https://github.com/google/jax) which needs to be installed first.

**Install JAX**: 
Please first follow JAX's [installation instruction](https://github.com/google/jax#installation) with optional GPU/TPU backend support.
In case JAX is not set up, EvoJAX installation will still try pulling a CPU-only version of JAX.
Note that Colab runtimes come with JAX pre-installed.

**Installation**:

To get this repository running the following can be run

```shell
# Clone from github
git clone https://github.com/TNSZ4/masters-project-submission.git
cd masters-project-submission
pip install -e .
```

**Running the Code**:

The core file is ```train_masking.py```, this runs the training of the masking model.

All hyper-parameters can be set from the command line, or the function ```run_train_masking```
can be called from an iteractive environment.

If you have any difficulties running this please reach out.
