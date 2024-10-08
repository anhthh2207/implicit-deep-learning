import torch
from torch import nn
import torch.nn.functional as F
from typing import Optional
from .implicit_function import ImplicitFunction, ImplicitFunctionInf
from .utils import transpose
import math

class ImplicitModel(nn.Module):
    def __init__(self, n: int, p: int, q: int,
                 f: Optional[ImplicitFunction] = ImplicitFunctionInf,
                 no_D: Optional[bool] = False,
                 bias: Optional[bool] = False):
        """
        Create a new Implicit Model:
            A: n*n  B: n*p  C: q*n  D: q*p
            X: n*m  U: p*m, m = batch size
            Note that for X and U, the batch size comes first when inputting into the model.
            These sizes reflect that the model internally transposes them so that their sizes line up with ABCD.
        
        Args:
            n: the number of hidden features.
            p: the number of input features.
            q: the number of output classes.
            f: the implicit function to use.
            no_D: whether or not to use the D matrix (i. e. whether the prediction equation should explicitly depend on the input U).
            bias: whether or not to use a bias.
        """
        super(ImplicitModel, self).__init__()

        if bias:
            p += 1

        self.n = n
        self.p = p
        self.q = q

        self.A = nn.Parameter(torch.randn(n, n)/n)
        self.B = nn.Parameter(torch.randn(n, p)/n)
        self.C = nn.Parameter(torch.randn(q, n)/n)
        self.D = nn.Parameter(torch.randn(q, p)/n) if not no_D else torch.zeros((q, p), requires_grad=False)

        self.f = f
        self.bias = bias

    def forward(self, U: torch.Tensor, X0: Optional[torch.Tensor] = None):
        if (len(U.size()) == 3):
            U = U.flatten(1, -1)
        U = transpose(U)
        if self.bias:
            U = F.pad(U, (0, 0, 0, 1), value=1)
        assert U.shape[0] == self.p, f'Given input size {U.shape[0]} does not match expected input size {self.p}.'

        m = U.shape[1]
        X_shape = torch.Size([self.n, m])

        if X0 is not None:
            X0 = transpose(X0)
            assert X0.shape == X_shape
        else:
            X0 = torch.zeros(X_shape, dtype=U.dtype, device=U.device)

        X = self.f.apply(self.A, self.B, X0, U)
        return transpose(self.C @ X + self.D @ U)

class ImplicitModelLoRA(nn.Module):
    def __init__(self, k: int, n: int, p: int, q: int,
                 f: Optional[ImplicitFunction] = ImplicitFunctionInf,
                 no_D: Optional[bool] = False,
                 bias: Optional[bool] = False):
        """
        Create a new Implicit Model:
            A1: n*r  A2: r*n  B: n*p  C: q*n  D: q*p
            X: n*m  U: p*m, m = batch size
            Note that for X and U, the batch size comes first when inputting into the model.
            These sizes reflect that the model internally transposes them so that their sizes line up with ABCD.
        
        Args:
            r: the LoRA dimension of A
            n: the number of hidden features.
            p: the number of input features.
            q: the number of output classes.
            f: the implicit function to use.
            no_D: whether or not to use the D matrix (i. e. whether the prediction equation should explicitly depend on the input U).
            bias: whether or not to use a bias.
        """
        super(ImplicitModelLoRA, self).__init__()

        if bias:
            p += 1

        self.k = k
        self.n = n
        self.p = p
        self.q = q

        self.L = nn.Parameter(torch.randn(n, k)/n)
        self.R = nn.Parameter(torch.randn(n, k)/n)
        self.B = nn.Parameter(torch.randn(n, p)/n)
        self.C = nn.Parameter(torch.randn(q, n)/n)
        self.D = nn.Parameter(torch.randn(q, p)/n) if not no_D else torch.zeros((q, p), requires_grad=False)

        self.f = f
        self.bias = bias

    def project_onto_Linf_ball(self, A, v=0.97):
        norm_inf_A = torch.linalg.matrix_norm(A, ord=float('inf')) 
        if (norm_inf_A > v):
            A = v*A/norm_inf_A
        else:
            pass
        return A

    def forward(self, U: torch.Tensor, X0: Optional[torch.Tensor] = None):
        if (len(U.size()) == 3):
            U = U.flatten(1, -1)
        U = transpose(U)
        if self.bias:
            U = F.pad(U, (0, 0, 0, 1), value=1)
        assert U.shape[0] == self.p, f'Given input size {U.shape[0]} does not match expected input size {self.p}.'

        m = U.shape[1]
        X_shape = torch.Size([self.n, m])

        if X0 is not None:
            X0 = transpose(X0)
            assert X0.shape == X_shape
        else:
            X0 = torch.zeros(X_shape, dtype=U.dtype, device=U.device)

        L_projected = self.project_onto_Linf_ball(self.L, 0.97)
        RT_projected = self.project_onto_Linf_ball(self.R.transpose(-1,-2), 0.97)

        X = self.f.apply(L_projected @ RT_projected, self.B, X0, U)
        return transpose(self.C @ X + self.D @ U)

class ImplicitModelLoRA2(nn.Module):
    def __init__(self, k: int, n: int, p: int, q: int,
                 f: Optional[ImplicitFunction] = ImplicitFunctionInf,
                 no_D: Optional[bool] = False,
                 bias: Optional[bool] = False,
                 diag: Optional[bool] = False):
        """
        Create a new Implicit Model:
            A1: n*r  A2: r*n  B: n*p  C: q*n  D: q*p
            X: n*m  U: p*m, m = batch size
            Note that for X and U, the batch size comes first when inputting into the model.
            These sizes reflect that the model internally transposes them so that their sizes line up with ABCD.
        
        Args:
            r: the LoRA dimension of A
            n: the number of hidden features.
            p: the number of input features.
            q: the number of output classes.
            f: the implicit function to use.
            no_D: whether or not to use the D matrix (i. e. whether the prediction equation should explicitly depend on the input U).
            bias: whether or not to use a bias.
        """
        super(ImplicitModelLoRA2, self).__init__()

        if bias:
            p += 1

        self.k = k
        self.n = n
        self.p = p
        self.q = q

        self.L = nn.Parameter(torch.randn(n, k)/n)
        self.R = nn.Parameter(torch.randn(n, k)/n)

        self.diag = diag
        if self.diag:            
            self.Diag = nn.Parameter(torch.randn(n)/n)
        else:
            self.Diag = nn.Parameter(torch.randn(1, 1)/n)

        self.B = nn.Parameter(torch.randn(n, p)/n)
        self.C = nn.Parameter(torch.randn(q, n)/n)
        self.D = nn.Parameter(torch.randn(q, p)/n) if not no_D else torch.zeros((q, p), requires_grad=False)

        self.f = f
        self.bias = bias

    def project_onto_Linf_ball(self, A, v=0.97):
        norm_inf_A = torch.linalg.matrix_norm(A, ord=float('inf')) 
        if (norm_inf_A > v):
            A = v*A/norm_inf_A
        else:
            pass
        return A

    def forward(self, U: torch.Tensor, X0: Optional[torch.Tensor] = None):
        if (len(U.size()) == 3):
            U = U.flatten(1, -1)
        U = transpose(U)
        if self.bias:
            U = F.pad(U, (0, 0, 0, 1), value=1)
        assert U.shape[0] == self.p, f'Given input size {U.shape[0]} does not match expected input size {self.p}.'

        m = U.shape[1]
        X_shape = torch.Size([self.n, m])

        if X0 is not None:
            X0 = transpose(X0)
            assert X0.shape == X_shape
        else:
            X0 = torch.zeros(X_shape, dtype=U.dtype, device=U.device)

        kappa = 0.95
        kapp_diag = 0.45
        if self.diag:       
            Diag_projected = self.project_onto_Linf_ball(torch.diag(self.Diag), kapp_diag)
        else:
            if torch.abs(self.Diag) > kappa:
                self.Diag = kappa * self.Diag/(self.Diag + 1e-10)
            Diag_projected = self.Diag * torch.eye(self.n, self.n)
        L_projected = self.project_onto_Linf_ball(self.L, math.sqrt(kappa-kapp_diag))
        RT_projected = self.project_onto_Linf_ball(self.R.transpose(-1,-2), math.sqrt(kappa-kapp_diag))

        X = self.f.apply(Diag_projected + L_projected @ RT_projected, self.B, X0, U)
        return transpose(self.C @ X + self.D @ U)
