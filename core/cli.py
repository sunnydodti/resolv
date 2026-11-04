import click
from core.logger import ResolvLogger

@click.group()
@click.option('--project', help='Target project configuration')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.pass_context
def main(ctx, project, verbose):
    """Resolv: Autonomous Issue-to-PR CLI Agent"""
    ctx.obj = ResolvLogger(verbose=verbose)
    ctx.obj.info(f"Initializing resolv session for project: {project}")

if __name__ == '__main__':
    main()
