import click
from core.logger import ResolvLogger

@click.group()
@click.option('--project', help='Target project configuration')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.pass_context
def main(ctx, project, verbose):
    """Resolv: Autonomous Issue-to-PR CLI Agent"""
    ctx.obj = ResolvLogger(verbose=verbose)
    # Temporary config loading validation
    try:
        from config.models import load_yaml
        conf = load_yaml('config/resolv.yaml')
        ctx.obj.info(f"Loaded config: {conf['default_provider']}")
    except Exception as e:
        ctx.obj.error(f"Config load failed: {e}")
        
    ctx.obj.info(f"Initializing resolv session for project: {project}")

@main.command()
@click.argument('issue_reference')
@click.pass_obj
def run(logger, issue_reference):
    """Run Resolv on an issue reference"""
    logger.info(f"Running on issue: {issue_reference}")

if __name__ == '__main__':
    main()
