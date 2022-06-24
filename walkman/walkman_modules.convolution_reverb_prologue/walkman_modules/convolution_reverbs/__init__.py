from __future__ import annotations

import typing

import pyo
import sys

import walkman

# Please see https://cnmat.berkeley.edu/sites/default/files/patches/Picture%203_0.png
Frequency = float
Amplitude = float
DecayRate = float
ResonatorConfiguration = typing.Tuple[Frequency, Amplitude, DecayRate]
FilePath = str
SliceIndex = int
ResonanceConfigurationFilePathList = typing.List[
    typing.Union[
        typing.Tuple[Amplitude, FilePath], typing.Tuple[Amplitude, FilePath, SliceIndex]
    ]
]


class ConvolutionReverbPrologue(
    walkman.ModuleWithDecibel,
    decibel=walkman.AutoSetup(walkman.Parameter),
    audio_input=walkman.Catch(walkman.constants.EMPTY_MODULE_INSTANCE_NAME),
):
    def __init__(
        self,
        resonance_configuration_file_path_list: ResonanceConfigurationFilePathList,
        add_envelope_follower: bool = False,
        **kwargs
    ):
        sys.setcheckinterval(500)
        super().__init__(**kwargs)
        self.add_envelope_follower = add_envelope_follower
        self.resonator_configuration_tuple = (
            self.parse_resonance_configuration_file_path_list(
                resonance_configuration_file_path_list
            )
        )

    @staticmethod
    def parse_resonance_configuration_file_path_list(
        resonance_configuration_file_path_list: ResonanceConfigurationFilePathList,
    ) -> typing.Tuple[
        typing.Tuple[Amplitude, typing.Tuple[ResonatorConfiguration, ...]]
    ]:
        resonator_configuration_list = []
        for data in resonance_configuration_file_path_list:
            try:
                amplitude, resonance_configuration_file_path, slice_index = data
            except ValueError:
                amplitude, resonance_configuration_file_path = data
                slice_index = 1
            resonance_configuration_tuple = (
                ConvolutionReverbPrologue.parse_resonance_configuration_file(
                    resonance_configuration_file_path
                )
            )[::slice_index]
            resonator_configuration_list.append(
                (amplitude, resonance_configuration_tuple)
            )
        return tuple(resonator_configuration_list)

    @staticmethod
    def parse_resonance_configuration_file(
        resonance_configuration_file_path: str,
    ) -> typing.Tuple[ResonatorConfiguration, ...]:
        with open(
            resonance_configuration_file_path, "r"
        ) as resonance_configuration_file:
            configuration_content = resonance_configuration_file.read()

        resonance_configuration_list = []
        for configuration_line in configuration_content.splitlines():
            try:
                _, data = configuration_line.replace(";", "").split(",")
            except ValueError:
                continue
            frequency, amplitude, decay = (
                float(value) for value in filter(bool, data.split(" "))
            )
            resonance_configuration_list.append((frequency, amplitude, decay))
        # XXX: We need set because in the text files are duplicates.
        return tuple(set(resonance_configuration_list))

    def _setup_pyo_object(self):
        super()._setup_pyo_object()
        self.resonator_list = []
        for (
            amplitude,
            resonance_configuration_tuple,
        ) in self.resonator_configuration_tuple:
            frequency_list, amplitude_list, decay_list = (
                list(value_list) for value_list in zip(*resonance_configuration_tuple)
            )
            complex_resonator = pyo.ComplexRes(
                self.audio_input.pyo_object,
                freq=frequency_list,
                decay=decay_list,
                mul=amplitude_list,
            ).stop()
            mixed_resonator = complex_resonator.mix(1)
            if amplitude != 1:
                complex_resonator_with_applied_amplitude = mixed_resonator * amplitude
            else:
                complex_resonator_with_applied_amplitude = mixed_resonator
            self.resonator_list.append(complex_resonator_with_applied_amplitude)
            self.internal_pyo_object_list.append(complex_resonator)

        self.summed_resonator = sum(self.resonator_list)

        internal_pyo_object_list = [self.summed_resonator] + self.resonator_list
        if self.add_envelope_follower:
            self.envelope_follower = pyo.Follower(self.audio_input.pyo_object).stop()
            self.summed_resonator *= self.envelope_follower * self.amplitude_signal_to
            internal_pyo_object_list.append(self.envelope_follower)
        else:
            self.summed_resonator *= self.amplitude_signal_to

        self.internal_pyo_object_list.extend(internal_pyo_object_list)
        self._stop_without_fader()

    @property
    def _pyo_object(self) -> pyo.PyoObject:
        return self.summed_resonator
