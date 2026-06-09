import re
import subprocess
from itertools import dropwhile, takewhile, islice
from thefuck.utils import for_app, replace_command, cache, which
from thefuck.specific.sudo import sudo_support


@sudo_support
@for_app('docker')
def match(command):
    if len(command.script_parts) < 2 or command.script_parts[1] != 'compose':
        return False
    return ('unknown docker compose command' in command.output
            or 'no such service' in command.output
            or 'unknown shorthand flag' in command.output)


def _parse_compose_commands(lines):
    lines = dropwhile(lambda line: not line.startswith('Commands:'), lines)
    lines = islice(lines, 1, None)
    lines = list(takewhile(lambda line: line.strip(), lines))
    return [line.strip().split()[0] for line in lines]


def _get_compose_commands():
    proc = subprocess.Popen(['docker', 'compose', '--help'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    lines = proc.stdout.readlines() or proc.stderr.readlines()
    lines = [line.decode('utf-8') for line in lines]
    return _parse_compose_commands(lines)


if which('docker'):
    _get_compose_commands = cache(which('docker'))(_get_compose_commands)


def _get_compose_services():
    proc = subprocess.Popen(['docker', 'compose', 'config', '--services'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return [line.decode('utf-8').strip()
            for line in proc.stdout.readlines() if line.strip()]


@sudo_support
def get_new_command(command):
    if 'unknown docker compose command' in command.output:
        wrong_command = re.findall(
            r'unknown docker compose command: "(\S+)"', command.output)[0]
        return replace_command(command, wrong_command,
                               _get_compose_commands())

    if 'no such service' in command.output:
        wrong_service = re.findall(
            r'no such service: (\S+)', command.output)[0]
        return replace_command(command, wrong_service,
                               _get_compose_services())

    if 'unknown shorthand flag' in command.output:
        match = re.search(
            r"unknown shorthand flag: '(\w)' in -(\w+)", command.output)
        if match:
            bad_char = match.group(1)
            full_flag = match.group(2)
            if len(full_flag) == 1:
                return re.sub(r'\s+-' + re.escape(full_flag), '',
                              command.script, count=1)
            else:
                fixed_flag = full_flag.replace(bad_char, '', 1)
                return command.script.replace('-' + full_flag,
                                              '-' + fixed_flag)
