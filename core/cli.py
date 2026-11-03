import click

@click.group()
@click.option('--project', help='Target project configuration')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
def main(project, verbose):
    """Resolv: Autonomous Issue-to-PR CLI Agent"""
    click.echo(f"Resolv initialized for project: {project}")

if __name__ == '__main__':
    main()
