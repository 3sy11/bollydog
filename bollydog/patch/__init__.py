import os
import re
import yaml
from mode.utils.imports import smart_import

# ---yaml---
pattern = re.compile(r".*?(\${\w+}).*?")


def env_var_constructor(loader, node):
    value = loader.construct_scalar(node)
    for item in pattern.findall(value):
        var_name = item.strip('${} ')
        value = value.replace(item, os.getenv(var_name, item))
    return value


def module_constructor(loader, node):
    value = loader.construct_scalar(node)
    return smart_import(value)


yaml.SafeLoader.add_constructor('!env', env_var_constructor)
yaml.SafeLoader.add_implicit_resolver('!env', pattern, None)
yaml.SafeLoader.add_constructor('!module', module_constructor)
