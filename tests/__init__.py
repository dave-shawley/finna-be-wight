import os


def setup_package():
    with open('build/test-environment', 'r') as env_file:
        for line in env_file:
            if '#' in line:
                line = line[:line.index('#')]
            name, sep, value = line.partition('=')
            name, value = name.strip(), value.strip()
            if name and sep:
                if value.startswith('"', "'") and value[0] == value[-1]:
                    value = value[1:-1].strip()
                if value:
                    os.environ[name] = value
                else:
                    os.environ.pop(name, None)
