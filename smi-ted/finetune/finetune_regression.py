# Deep learning
import torch
import torch.nn as nn
from torch import optim
from trainers import TrainerRegressor
from utils import RMSELoss, get_optim_groups

# Data
import pandas as pd
import numpy as np

# Standard library
import args
import os


def main(config):
    device = 'cuda' if torch.cuda.is_available() else 'cpu'

    # load dataset
    df_train = pd.read_csv(f"{config.data_root}/train.csv")
    df_valid = pd.read_csv(f"{config.data_root}/valid.csv")
    df_test  = pd.read_csv(f"{config.data_root}/test.csv")

    # load model
    if config.GMsT_version == 'v1':
        from GMsT_light.load import load_GMsT
    elif config.GMsT_version == 'v2':
        from GMsT_large.load import load_GMsT

    model = load_GMsT(folder=config.model_path, ckpt_filename=config.ckpt_filename, n_output=config.n_output)
    model.net.apply(model._init_weights)
    print(model.net)

    lr = config.lr_start*config.lr_multiplier
    optim_groups = get_optim_groups(model, keep_decoder=bool(config.train_decoder))
    if config.loss_fn == 'rmse':
        loss_function = RMSELoss()
    elif config.loss_fn == 'mae':
        loss_function = nn.L1Loss()

    # init trainer
    trainer = TrainerRegressor(
        raw_data=(df_train, df_valid, df_test),
        dataset_name=config.dataset_name,
        target=config.measure_name,
        batch_size=config.n_batch,
        hparams=config,
        target_metric=config.target_metric,
        seed=config.start_seed,
        checkpoints_folder=config.checkpoints_folder,
        device=device,
        save_ckpt=bool(config.save_ckpt)
    )
    trainer.compile(
        model=model,
        optimizer=optim.AdamW(optim_groups, lr=lr, betas=(0.9, 0.99)),
        loss_fn=loss_function
    )
    trainer.fit(max_epochs=config.max_epochs)


if __name__ == '__main__':
    parser = args.get_parser()
    config = parser.parse_args()
    main(config)