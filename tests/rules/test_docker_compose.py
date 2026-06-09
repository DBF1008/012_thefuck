import pytest
from io import BytesIO
from thefuck.types import Command
from thefuck.rules.docker_compose import match, get_new_command


_COMPOSE_HELP = b'''\
Usage:  docker compose [OPTIONS] COMMAND

Docker Compose

Options:
      --ansi string                Control when to print ANSI control characters
      --compatibility              Run compose in backward compatibility mode
      --dry-run                    Execute command in dry run mode
      --env-file stringArray       Specify an alternate environment file
  -f, --file stringArray           Compose configuration files
      --parallel int               Control max parallelism, -1 for unlimited
      --profile stringArray        Specify a profile to enable
      --progress string            Set type of progress output
      --project-directory string   Specify an alternate working directory
  -p, --project-name string        Project name

Commands:
  build       Build or rebuild services
  config      Parse, resolve and render compose file in canonical format
  cp          Copy files/folders between a service container and the local filesystem
  create      Creates containers for a service
  down        Stop and remove containers, networks
  events      Receive real time events from containers
  exec        Execute a command in a running container
  images      List images used by the created containers
  kill        Force stop service containers
  logs        View output from containers
  ls          List running compose projects
  pause       Pause services
  port        Print the public port for a port binding
  ps          List containers
  pull        Pull service images
  push        Push service images
  restart     Restart service containers
  rm          Removes stopped service containers
  run         Run a one-off command on a service
  scale       Scale services
  start       Start services
  stop        Stop services
  top         Display the running processes
  unpause     Unpause services
  up          Create and start containers
  version     Show the Docker Compose version information
  wait        Block until the first service container stops
  watch       Watch build context for service and rebuild/refresh containers when files are updated

Run 'docker compose COMMAND --help' for more information on a command.
'''


@pytest.fixture
def compose_help(mocker):
    mock = mocker.patch('subprocess.Popen')
    mock.return_value.stdout = BytesIO(_COMPOSE_HELP)
    mock.return_value.stderr = BytesIO(b'')
    return mock


@pytest.fixture
def compose_services(mocker):
    mock = mocker.patch('subprocess.Popen')
    mock.return_value.stdout = BytesIO(b'web\ndb\nredis\nworker\n')
    mock.return_value.stderr = BytesIO(b'')
    return mock


# -- match tests --

@pytest.mark.parametrize('script, output', [
    ('docker compose pu',
     'unknown docker compose command: "pu"'),
    ('docker compose up weeb',
     'no such service: weeb'),
    ('docker compose up -z',
     "unknown shorthand flag: 'z' in -z"),
])
def test_match(script, output):
    assert match(Command(script, output))


@pytest.mark.parametrize('script, output', [
    ('docker compose up', ''),
    ('docker compose ps', 'CONTAINER ID   IMAGE   COMMAND'),
    ('docker ps', 'unknown docker compose command: "pu"'),
    ('cat compose', 'unknown docker compose command: "pu"'),
])
def test_not_match(script, output):
    assert not match(Command(script, output))


# -- get_new_command: unknown compose command --

@pytest.mark.usefixtures('no_memoize', 'compose_help')
@pytest.mark.parametrize('wrong, fixed', [
    ('pu', ['push', 'pull', 'pause']),
    ('dowm', ['down', 'rm', 'top']),
    ('strat', ['start', 'restart', 'create']),
])
def test_get_new_command_unknown_cmd(wrong, fixed):
    cmd = Command('docker compose {}'.format(wrong),
                  'unknown docker compose command: "{}"'.format(wrong))
    assert get_new_command(cmd) == ['docker compose {}'.format(x)
                                    for x in fixed]


# -- get_new_command: no such service --

@pytest.mark.usefixtures('no_memoize', 'compose_services')
@pytest.mark.parametrize('wrong, fixed', [
    ('weeb', ['web', 'worker', 'db']),
    ('redi', ['redis', 'worker', 'db']),
])
def test_get_new_command_no_such_service(wrong, fixed):
    cmd = Command('docker compose up {}'.format(wrong),
                  'no such service: {}'.format(wrong))
    assert get_new_command(cmd) == ['docker compose up {}'.format(x)
                                    for x in fixed]


# -- get_new_command: unknown shorthand flag --

def test_get_new_command_unknown_flag():
    cmd = Command('docker compose up -z',
                  "unknown shorthand flag: 'z' in -z")
    assert get_new_command(cmd) == 'docker compose up'


def test_get_new_command_unknown_flag_combined():
    cmd = Command('docker compose up -dz',
                  "unknown shorthand flag: 'z' in -dz")
    assert get_new_command(cmd) == 'docker compose up -d'
