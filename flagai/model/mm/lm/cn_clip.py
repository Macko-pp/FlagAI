import torch
import torch.nn as nn
from einops import rearrange, repeat
import json

class AbstractEncoder(nn.Module):
    def __init__(self):
        super().__init__()

    def encode(self, *args, **kwargs):
        raise NotImplementedError

class LayerNorm(nn.Module):

    def __init__(self, hidden_size, eps=1e-12):
        """Construct a layernorm module in the TF style (epsilon inside the square root).
        """
        super(LayerNorm, self).__init__()
        self.weight = nn.Parameter(torch.ones(hidden_size))
        self.bias = nn.Parameter(torch.zeros(hidden_size))
        self.variance_epsilon = eps

    def forward(self, x):
        u = x.mean(-1, keepdim=True)
        s = (x - u).pow(2).mean(-1, keepdim=True)
        x = (x - u) / torch.sqrt(s + self.variance_epsilon)
        return self.weight * x + self.bias

class CN_CLIP(AbstractEncoder):
    def __init__(self, version='ViT-L/14', device="cuda", max_length=77, n_repeat=1, normalize=True, **kwargs):
        super().__init__()

        chkpt = kwargs.get("model_dir", None)
        text_model_config_file = kwargs.get("text_model_config_file", None)
        vision_model_config_file = kwargs.get("vision_model_config_file", None)
        from clip_cn.model import CLIP
        from clip_cn.clip import tokenize
        self.tokenize = tokenize

        self.device = device
        self.max_length = max_length

        with open(vision_model_config_file, 'r') as fv, open(text_model_config_file, 'r') as ft:
            model_info = json.load(fv)
            for k, v in json.load(ft).items():
                model_info[k] = v

        self.model = CLIP(**model_info)
        checkpoint = torch.load(chkpt)

        sd = checkpoint["state_dict"]
        if next(iter(sd.items()))[0].startswith('module'):
            sd = {k[len('module.'):]: v for k, v in sd.items()}
        self.model.load_state_dict(sd)
        # 冻结权重
        # for param in self.model.parameters():
        #     param.requires_grad = False

        self.normalize = normalize
        self.layer_norm1 = LayerNorm(768)
        self.layer_norm2 = LayerNorm(768)

        self.proj = nn.Linear(768,768)

        
    def forward(self, text):
        text = self.tokenize(text).to(self.device)
        z = self.model.encode_text(text)
        z = self.layer_norm1(z)
        z = self.proj(z)
        z = self.layer_norm2(z)

        return z

    def encode(self, text):
        z = self(text)
        if z.ndim==2:
            z = z[:, None, :]
        return z
