# original: https://github.com/google-research/fixmatch
import torch
import torch.nn as nn


class BasicBlock(nn.Module):
    def __init__(self, cᵢ, cₒ, s=1, dropout=0.,
                 norm_layer=None, relu_layer=None,
                 activate_before_residual=False):
        super().__init__()

        self.activate_before_residual = activate_before_residual

        if norm_layer is None:
            norm_layer = nn.BatchNorm2d
        if relu_layer is None:
            relu_layer = nn.ReLU

        self.conv0 = nn.Conv2d(cᵢ, cₒ, 3, s, 1, bias=False)
        self.conv1 = nn.Conv2d(cₒ, cₒ, 3, 1, 1, bias=False)
        self.bn0 = norm_layer(cᵢ)
        self.bn1 = norm_layer(cₒ)

        self.relu0 = relu_layer()
        self.relu1 = relu_layer()
        self.drop = nn.Dropout(dropout)

        self.convdim = None
        if cᵢ != cₒ:
            self.convdim = nn.Conv2d(cᵢ, cₒ, 1, s, 0, bias=False)

    def forward(self, x):
        z = self.relu0(self.bn0(x))
        if self.activate_before_residual:
            x = z
        z = self.conv0(z)
        z = self.relu1(self.bn1(z))
        z = self.conv1(self.drop(z))
        if self.convdim is not None:
            x = self.convdim(x)
        return x + z


def _make_layer(n, cᵢ, cₒ, s=1, **kwargs):
    layers = [BasicBlock(cᵢ, cₒ, s, **kwargs)]
    kwargs['activate_before_residual'] = False
    layers += [BasicBlock(cₒ, cₒ, 1, **kwargs) for _ in range(n - 1)]
    return nn.Sequential(*layers)


class WideResNet(nn.Module):
    def __init__(self, num_classes, depth, width,
                 block_dropout=0., dense_dropout=0.,
                 norm_layer=None, relu_layer=None):
        super().__init__()

        assert (depth - 4) % 6 == 0
        n = (depth - 4) // 6
        c = [16, 16 * width, 32 * width, 64 * width]

        if norm_layer is None:
            norm_layer = nn.BatchNorm2d
        if relu_layer is None:
            relu_layer = nn.ReLU

        self.conv = nn.Conv2d(3, c[0], 3, 1, 1, bias=False)
        self.block1 = _make_layer(n, c[0], c[1], 1, dropout=block_dropout,
                                  norm_layer=norm_layer, relu_layer=relu_layer,
                                  activate_before_residual=True)
        self.block2 = _make_layer(n, c[1], c[2], 2, dropout=block_dropout,
                                  norm_layer=norm_layer, relu_layer=relu_layer)
        self.block3 = _make_layer(n, c[2], c[3], 2, dropout=block_dropout,
                                  norm_layer=norm_layer, relu_layer=relu_layer)
        self.bn = norm_layer(c[3])
        self.relu = relu_layer()
        self.pool = nn.AdaptiveAvgPool2d((1, 1))
        self.drop = nn.Dropout(dense_dropout)
        self.fc = nn.Linear(c[3], num_classes)

        # initialize parameters
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1.0)
                nn.init.constant_(m.bias, 0.0)
            elif isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight)
                nn.init.constant_(m.bias, 0.0)

    def forward(self, x):
        out = self.conv(x)
        out = self.block1(out)
        out = self.block2(out)
        out = self.block3(out)
        out = self.relu(self.bn(out))
        out = self.pool(out)
        out = torch.flatten(out, 1)
        return self.fc(self.drop(out))


class FixMatchBatchNorm(torch.nn.BatchNorm2d):
    def __init__(self, num_features):
        super().__init__(num_features, momentum=0.001)


class FixMatchReLU(torch.nn.LeakyReLU):
    def __init__(self):
        super().__init__(0.1, inplace=True)


def build_wide_resnet28(name, num_classes=10, fixmatch=False, **kwargs):
    assert 'wide_resnet28' in name
    kwargs['depth'] = 28
    kwargs['width'] = int(name.rsplit('_', 1)[1])

    if fixmatch is True:
        kwargs['norm_layer'] = FixMatchBatchNorm
        kwargs['relu_layer'] = FixMatchReLU

    return WideResNet(num_classes, **kwargs)