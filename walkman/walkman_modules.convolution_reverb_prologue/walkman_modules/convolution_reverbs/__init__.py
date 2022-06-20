from __future__ import annotations


import pyo

import walkman


class ConvolutionReverbPrologue(walkman.ConvolutionReverb):
    def _setup_pyo_object(self):
        super()._setup_pyo_object()
        self.compressor = pyo.Compress(self.convolution_reverb, thresh=-12, ratio=3)
        # To avoid crazy peaks
        self.clip = pyo.Clip(self.compressor)
        self.internal_pyo_object_list.extend([self.compressor, self.clip])

    @property
    def _pyo_object(self) -> pyo.PyoObject:
        return self.clip
