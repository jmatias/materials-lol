# -*- coding:utf-8 -*-
# Rhizome
# Version beta 0.0, August 2023
# Property of IBM Research, Accelerated Discovery
#

from typing import Any, Dict, List, Optional, Union

import pandas as pd
import torch
from huggingface_hub import hf_hub_download
from rdkit import Chem
from torch_geometric.utils.smiles import from_smiles
from typing_extensions import Self

from fm4m.path_utils import add_path
from .graph_grammar.io.smi import hg_to_mol
from .models.mhgvae import GrammarGINVAE
from ...config.constants import MODELS_PATH
from ...config.model_files import MHG_MODEL_PICKLE


class PretrainedModelWrapper:
    model: GrammarGINVAE

    def __init__(self, model_dict: Dict[str, Any]) -> None:
        json_params = model_dict["gnn_params"]
        encoder_params = json_params["encoder_params"]
        encoder_params["node_feature_size"] = model_dict["num_features"]
        encoder_params["edge_feature_size"] = model_dict["num_edge_features"]
        self.model = GrammarGINVAE(
            model_dict["hrg"],
            rank=-1,
            encoder_params=encoder_params,
            decoder_params=json_params["decoder_params"],
            prod_rule_embed_params=json_params["prod_rule_embed_params"],
            batch_size=512,
            max_len=model_dict["max_length"],
        )
        self.model.load_state_dict(model_dict["model_state_dict"])

        self.model.eval()

    def to(self, device: Union[str, int, torch.device]) -> Self:
        dev_type = type(device)
        if dev_type != torch.device:
            if dev_type == str or torch.cuda.is_available():
                device = torch.device(device)
            else:
                device = torch.device("mps", device)

        self.model = self.model.to(device)
        return self

    def encode(self, data: List[str] | pd.DataFrame) -> List[torch.tensor]:
        # Need to encode them into a graph nn
        if isinstance(data, pd.DataFrame):
            data = data.to_list()
        output = []
        for d in data:
            params = next(self.model.parameters())
            g = from_smiles(d)
            if (g.cpu() and params != "cpu") or (not g.cpu() and params == "cpu"):
                g.to(params.device)
            ltvec = self.model.graph_embed(g.x, g.edge_index, g.edge_attr, g.batch)
            output.append(ltvec[0])
        return output

    def decode(self, data: List[torch.tensor]) -> List[str]:
        output = []
        for d in data:
            mu, logvar = self.model.get_mean_var(d.unsqueeze(0))
            z = self.model.reparameterize(mu, logvar)
            flags, _, hgs = self.model.decode(z)
            if flags[0]:
                reconstructed_mol, _ = hg_to_mol(hgs[0], True)
                output.append(Chem.MolToSmiles(reconstructed_mol))
            else:
                output.append(None)
        return output


def load(
    model_name: str = MHG_MODEL_PICKLE,
) -> Optional[PretrainedModelWrapper]:
    repo_id = "ibm/materials.mhg-ged"
    filename = "pytorch_model.bin"  # "mhggnn_pretrained_model_0724_2023.pickle"
    file_path = hf_hub_download(repo_id=repo_id, filename=filename)

    with add_path(MODELS_PATH):
        with open(file_path, "rb") as f:
            model_dict = torch.load(f)
            return PretrainedModelWrapper(model_dict)
