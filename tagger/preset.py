"""Module for Tagger, to save and load presets."""
import os
import json
import string
import re

from typing import Tuple, List, Dict
from pathlib import Path
from gradio.context import Context

PresetDict = Dict[str, Dict[str, any]]


# Copied from https://github.com/AUTOMATIC1111/stable-diffusion-webui/blob/master/modules/images.py#L319-L339
invalid_filename_chars = '<>:"/\\|?*\n\r\t'
invalid_filename_prefix = ' '
invalid_filename_postfix = ' .'
re_nonletters = re.compile(r'[\s' + string.punctuation + ']+')
re_pattern = re.compile(r"(.*?)(?:\[([^\[\]]+)\]|$)")
re_pattern_arg = re.compile(r"(.*)<([^>]*)>$")
max_filename_part_length = 128
NOTHING_AND_SKIP_PREVIOUS_TEXT = object()


def sanitize_filename_part(text, replace_spaces=True):
    if text is None:
        return None

    if replace_spaces:
        text = text.replace(' ', '_')

    text = text.translate({ord(x): '_' for x in invalid_filename_chars})
    text = text.lstrip(invalid_filename_prefix)[:max_filename_part_length]
    text = text.rstrip(invalid_filename_postfix)
    return text


class Preset:
    """Preset class for Tagger, to save and load presets."""
    base_dir: Path
    default_filename: str
    default_values: PresetDict
    components: List[object]

    def __init__(
        self,
        base_dir: os.PathLike,
        default_filename='default.json'
    ) -> None:
        self.base_dir = Path(base_dir)
        self.default_filename = default_filename
        self.default_values = self.load(default_filename)[1]
        self.components = []

    def component(self, component_class: object, **kwargs) -> object:
        # find all the top components from the Gradio context and create a path
        parent = Context.block
        paths = [kwargs['label']]

        while parent is not None:
            if hasattr(parent, 'label'):
                paths.insert(0, parent.label)

            parent = parent.parent

        path = '/'.join(paths)

        component = component_class(**{
            **kwargs,
            **self.default_values.get(path, {})
        })

        component.path = path

        self.components.append(component)
        return component

    def load(self, filename: str) -> Tuple[str, PresetDict]:
        if not filename.endswith('.json'):
            filename += '.json'

        path = self.base_dir.joinpath(sanitize_filename_part(filename))
        configs = {}

        if path.is_file():
            configs = json.loads(path.read_text(encoding='utf-8'))

        return path, configs

    def save(self, filename: str, *values) -> Tuple:
        path, configs = self.load(filename)

        for index, component in enumerate(self.components):
            config = configs.get(component.path, {})
            config['value'] = values[index]

            for attr in ['visible', 'min', 'max', 'step']:
                if hasattr(component, attr):
                    config[attr] = config.get(attr, getattr(component, attr))

            configs[component.path] = config

        self.base_dir.mkdir(0o777, True, True)
        path.write_text(json.dumps(configs, indent=4), encoding='utf-8')

        return 'successfully saved the preset'

    def apply(self, filename: str) -> Tuple:
        values = self.load(filename)[1]
        outputs = []

        for component in self.components:
            config = values.get(component.path, {})

            if 'value' in config and hasattr(component, 'choices'):
                if config['value'] not in component.choices:
                    config['value'] = None

            outputs.append(component.update(**config))

        return (*outputs, 'successfully loaded the preset')

    def list(self) -> List[str]:
        presets = [
            p.name
            for p in self.base_dir.glob('*.json')
            if p.is_file()
        ]

        if len(presets) < 1:
            presets.append(self.default_filename)

        return presets
