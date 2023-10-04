# Copyright (c) 2023 Itos Inc (Itos.Fi)
import math


def calcX(liq, low_sqrt, high_sqrt):
    return liq * ((1 / low_sqrt) - (1 / high_sqrt))


def calcY(liq, low_sqrt, high_sqrt):
    return liq * (high_sqrt - low_sqrt)


class Maker:
    def __init__(self, liq, low_px, high_px):
        self.low = low_px
        self.high = high_px
        self.low_sqrt = math.sqrt(low_px)
        self.high_sqrt = math.sqrt(high_px)
        self.liq = liq

    def value(self, px):
        sqrt_px = math.sqrt(px)
        if sqrt_px < self.low_sqrt:
            x = self.liq * (1 / self.low_sqrt - 1 / self.high_sqrt)
            return x * px
        elif sqrt_px < self.high_sqrt:
            x = self.liq * (1 / sqrt_px - 1 / self.high_sqrt)
            y = self.liq * (sqrt_px - self.low_sqrt)
            return x * px + y
        else:
            y = self.liq * (self.high_sqrt - self.low_sqrt)
            return y

    def in_range(self, px):
        return (px >= self.low) and (px < self.high)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.liq:.2f}, {self.low:.2f}, {self.high:.2f})"


class TakerCall(Maker):
    def value(self, px):
        x = self.liq * (1 / self.low_sqrt - 1 / self.high_sqrt)
        return x * px - super().value(px)


class TakerPut(Maker):
    def value(self, px):
        y = self.liq * (self.high_sqrt - self.low_sqrt)
        return y - super().value(px)
