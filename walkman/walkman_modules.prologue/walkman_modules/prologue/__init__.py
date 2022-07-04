from __future__ import annotations

import os
import typing
import sys

import numpy as np
import pyo

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


class Resonator(
    walkman.ModuleWithDecibel,
    decibel=walkman.AutoSetup(walkman.Parameter),
    audio_input=walkman.Catch(walkman.constants.EMPTY_MODULE_INSTANCE_NAME),
):
    def __init__(
        self,
        resonance_configuration_file_path_list: ResonanceConfigurationFilePathList,
        **kwargs,
    ):
        # http://ajaxsoundstudio.com/pyodoc/perftips.html#adjust-the-interpreter-s-check-interval
        sys.setcheckinterval(500)
        super().__init__(**kwargs)
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
                Resonator.parse_resonance_configuration_file(
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
        # XXX: It's better to apply amplitude on input instead
        # on resonators, for less sudden fade in.
        self.audio_input_with_applied_decibel = (
            self.audio_input.pyo_object * self.amplitude_signal_to
        )
        self.resonator_list = []
        for (
            amplitude,
            resonance_configuration_tuple,
        ) in self.resonator_configuration_tuple:
            frequency_list, amplitude_list, decay_list = (
                list(value_list) for value_list in zip(*resonance_configuration_tuple)
            )
            complex_resonator = pyo.ComplexRes(
                self.audio_input_with_applied_decibel,
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

        internal_pyo_object_list = [
            self.summed_resonator,
            self.audio_input_with_applied_decibel,
        ] + self.resonator_list

        self.internal_pyo_object_list.extend(internal_pyo_object_list)

    @property
    def _pyo_object(self) -> pyo.PyoObject:
        return self.summed_resonator


SOUNDFILE_DIRECTORY_PATH = "soundfiles"


class SnareResonator(Resonator):
    SOUNDFILE_PATH_LIST = [
        f"{SOUNDFILE_DIRECTORY_PATH}/{soundfile_path}"
        for soundfile_path in os.listdir(SOUNDFILE_DIRECTORY_PATH)
    ]
    SOUNDFILE_COUNT = len(SOUNDFILE_PATH_LIST)

    def __init__(
        self,
        threshold_decibel_minima: float = -65,
        threshold_decibel_maxima: float = -40,
        snare_sample_maxima_amplitude: float = 1,
        **kwargs,
    ):
        self.threshold_list = [
            walkman.utilities.decibel_to_amplitude_ratio(decibel)
            for decibel in np.linspace(
                threshold_decibel_minima,
                threshold_decibel_maxima,
                num=self.SOUNDFILE_COUNT,
                dtype=float,
            )
        ]
        self.snare_sample_maxima_amplitude = snare_sample_maxima_amplitude
        super().__init__(**kwargs)

    def _setup_pyo_object(self):
        super()._setup_pyo_object()
        self.soundfile_table_list = [
            pyo.SndTable(soundfile_path) for soundfile_path in self.SOUNDFILE_PATH_LIST
        ]
        self.soundfile_player_list = [
            pyo.Looper(
                soundfile_table,
                dur=soundfile_table.getDur(),
                mul=self.amplitude_signal_to,
            )
            for soundfile_table in self.soundfile_table_list
        ]
        self.mixer = pyo.Mixer(outs=self.SOUNDFILE_COUNT, time=0.1)
        for soundfile_player_index, soundfile_player in enumerate(
            self.soundfile_player_list
        ):
            self.mixer.addInput(soundfile_player_index, soundfile_player)

        self.resonator_mixer_index = soundfile_player_index + 1
        self.mixer.addInput(self.resonator_mixer_index, self.summed_resonator)

        def set_summed_resonator_amplitude(amplitude: float):
            for output_index in range(self.SOUNDFILE_COUNT):
                self.mixer.setAmp(self.resonator_mixer_index, output_index, amplitude)

        def get_play_soundfile_function(sound_file_index: int):
            def function():
                self.soundfile_player_list[sound_file_index].play()
                self.mixer.setAmp(
                    sound_file_index,
                    sound_file_index,
                    self.snare_sample_maxima_amplitude,
                )

            if sound_file_index == 0:
                base_function = function

                def function():
                    base_function()
                    set_summed_resonator_amplitude(1)

            return function

        def get_stop_soundfile_function(sound_file_index: int):
            def function():
                self.soundfile_player_list[sound_file_index].stop()
                self.mixer.setAmp(sound_file_index, sound_file_index, 0)

            if sound_file_index == 0:
                base_function = function

                def function():
                    base_function()
                    set_summed_resonator_amplitude(0)

            return function

        self.envelope_follower = pyo.Follower(self.audio_input.pyo_object).stop()

        self.envelope_follower_decibel = pyo.AToDB(self.envelope_follower)
        self.envelope_printer = pyo.Print(
            self.envelope_follower_decibel, message="ENVELOPE FOLLOWER (dB)"
        )

        self.envelope_follower_with_portamento = pyo.Port(
            self.envelope_follower, risetime=0.02, falltime=0.1
        )

        self.snare_resonator = (
            walkman.Mixer.PyoObjectMixer([channel[0] for channel in self.mixer])
            * self.envelope_follower_with_portamento
        )

        # XXX: I use amplitude instead of decibel, because I assume the Thresh
        # object acts weird for negative values (and decibel would be negative values).
        self.play_threshold = pyo.Thresh(
            self.envelope_follower, threshold=self.threshold_list, dir=0
        )
        self.stop_threshold = pyo.Thresh(
            self.envelope_follower, threshold=self.threshold_list, dir=1
        )
        self.play_trigger_function_list = [
            pyo.TrigFunc(
                self.play_threshold[soundfile_index],
                get_play_soundfile_function(soundfile_index),
            )
            for soundfile_index in range(self.SOUNDFILE_COUNT)
        ]
        self.stop_trigger_function_list = [
            pyo.TrigFunc(
                self.stop_threshold[soundfile_index],
                get_stop_soundfile_function(soundfile_index),
            )
            for soundfile_index in range(self.SOUNDFILE_COUNT)
        ]

        self.internal_pyo_object_list.extend(
            [
                self.envelope_follower,
                self.envelope_follower_decibel,
                self.envelope_follower_with_portamento,
                self.snare_resonator,
                self.mixer,
                self.play_threshold,
                self.stop_threshold,
                self.envelope_printer,
            ]
            + self.soundfile_player_list
            + self.play_trigger_function_list
            + self.stop_trigger_function_list
        )

    @property
    def _pyo_object(self) -> pyo.PyoObject:
        return self.snare_resonator
