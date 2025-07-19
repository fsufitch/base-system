import logging
import shlex
import socket
import subprocess
from dataclasses import dataclass

# import ansible_runner
import click

from filipstack.paths import AnsiblePaths, get_executable_path

LOG = logging.getLogger(__name__)


@dataclass
class Config:
    paths: AnsiblePaths = AnsiblePaths()
    quiet: bool = False
    verbosity: int = 0

    @property
    def ansible_verbosity(self) -> int:
        if self.quiet or self.verbosity == 0:
            return 0
        elif self.verbosity == 1:
            return 3
        elif self.verbosity >= 2:
            return 4
        raise ValueError(f"Invalid verbosity level: {self.verbosity}")

    @classmethod
    def of(cls, ctx: click.Context) -> "Config":
        ctx.ensure_object(cls)
        obj = ctx.find_object(cls)
        if not isinstance(obj, cls):
            raise TypeError(f"Expected {cls.__name__}, got {type(obj).__name__}")
        return obj


@click.group(
    name="filipstack",
    help="Filipstack CLI for managing/provisioning Filip's systems.",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Enable verbose output. Specify twice for debug output.",
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    help="Suppress all output except errors.",
    default=False,
)
@click.option(
    "-p",
    "--path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Specify a custom base data directory for Filipstack.",
)
@click.pass_context
def main(ctx: click.Context, verbose: int, quiet: bool, path: str | None):
    if verbose and quiet:
        raise click.UsageError(
            "Cannot use both --verbose and --quiet options together."
        )

    config = Config.of(ctx)

    config.paths = ctx.with_resource(AnsiblePaths(path))
    config.quiet = quiet
    config.verbosity = verbose
    init_logging(config)


@main.command(
    name="ansible",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.argument(
    "cmd",
    type=click.Choice(
        [
            "community",
            "config",
            "console",
            "doc",
            "galaxy",
            "inventory",
            "playbook",
            "pull",
            "runner",
            "test",
            "vault",
        ]
    ),
)
@click.option("--no-defaults", is_flag=True, help="Disable default arguments.")
@click.pass_context
def ansible_passthrough(
    ctx: click.Context,
    cmd: str,
    no_defaults: bool,
):
    config = Config.of(ctx)

    ansible_cmd = f"ansible-{cmd}"
    LOG.info(f"Using ansible command: {ansible_cmd}")

    ansible_args = []
    if not no_defaults:
        if config.ansible_verbosity:
            ansible_args.append(f"-{'v' * (config.ansible_verbosity)}")
        if cmd in ["console", "doc", "inventory", "playbook", "pull"]:
            ansible_args.append("--inventory")
            ansible_args.append(str(config.paths.inventory))
    ansible_args.extend(ctx.args)
    LOG.info("Using ansible arguments: %s", ansible_args)

    subprocess.run(
        [ansible_cmd] + ansible_args,
        env={
            "ANSIBLE_NOCOWS": "1",
        },
        check=True,
        shell=True,
    )

    # _, err, code = ansible_runner.run_command(f"ansible-{cmd}", ansible_args)
    # if code:
    #     LOG.error("Ansible command failed with error: %s", err)
    #     LOG.error("Ansible said: %s", err)
    #     raise click.ClickException(
    #         f"Ansible command '{ansible_cmd}' failed. See logs for details."
    #     )


def _get_hostname():
    try:
        return socket.getfqdn()
    except Exception as e:
        LOG.error("Failed to get hostname: %s", e)
        return "localhost"


@main.command(
    name="run",
    help="Run an Ansible playbook against specified hosts. Defaults to local host if none specified.",
)
@click.argument(
    "host_limit",
    type=str,
    nargs=-1,
    required=False,
)
@click.pass_context
def ansible_remote(ctx: click.Context, host_limit: list[str]):
    if not host_limit:
        my_hostname = _get_hostname()
        LOG.warning(
            "Targeting local host by default (it's better to be explicit if you can): %s",
            my_hostname,
        )
        host_limit = [my_hostname]

    config = Config.of(ctx)

    ansible_playbook = get_executable_path("ansible-playbook")

    cmd = [
        ansible_playbook,
        "-i",
        str(config.paths.inventory),
        "--limit",
        ",".join(host_limit),
        str(config.paths.main_playbook),
    ]

    if config.ansible_verbosity:
        cmd.append(f"-{'v' * (config.ansible_verbosity)}")

    LOG.info("Running Ansible playbook with command: %s", shlex.join(cmd))

    result = subprocess.run(
        cmd,
        env={
            "ANSIBLE_NOCOWS": "1",
        },
    )

    if result.returncode != 0:
        LOG.error(
            "Ansible playbook execution failed with return code: %d", result.returncode
        )
        raise click.ClickException(
            "Ansible playbook execution failed. See logs for details."
        )


def init_logging(config: Config):
    if config.quiet:
        logging.getLogger(__package__).setLevel(logging.ERROR)
    else:
        log_level = logging.DEBUG if config.verbosity >= 2 else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        LOG.info("Logging initialized at level: %s", logging.getLevelName(log_level))


if __name__ == "__main__":
    main()
