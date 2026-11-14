"""Optional PyTorch neural head; data admission does not require PyTorch."""
import torch
from torch import nn

class ReviewedHead(nn.Module):
    def __init__(self,mean,std,width=64):
        super().__init__();self.register_buffer('mean',torch.as_tensor(mean,dtype=torch.float32));self.register_buffer('std',torch.as_tensor(std,dtype=torch.float32))
        self.layers=nn.Sequential(nn.Linear(len(mean),width),nn.ReLU(),nn.Dropout(.25),nn.Linear(width,1))
    def forward(self,x):
        z=self.layers((x-self.mean)/self.std)
        return torch.cat((z/2,-z/2),dim=1)
