from __future__ import annotations


import pyo

import walkman


class ConvolutionReverbPrologue(walkman.ConvolutionReverb):
    def _setup_pyo_object(self):
        super()._setup_pyo_object()
        # del self.convolution_reverb
        self.convolve = pyo.Convolve(
            self.audio_input.pyo_object,
            pyo.SndTable(self.impulse_path),
            size=512,
        )
        self.balance_convolve = pyo.Balance(self.convolve, self.audio_input.pyo_object)
        self.convolution_reverb.setInput(self.balance_convolve)
        self.compressor = pyo.Compress(self.convolution_reverb, thresh=-15, ratio=3)
        # To avoid crazy peaks
        self.clip = pyo.Clip(self.compressor)
        # self.internal_pyo_object_list.extend([self.compressor, self.clip])
        self.internal_pyo_object_list.extend(
            [self.convolve, self.compressor, self.clip, self.balance_convolve]
        )

    @property
    def _pyo_object(self) -> pyo.PyoObject:
        return self.clip
