"""cli-anything-intelwatch - CLI harness for Intelwatch."""

import sys
import subprocess
import click

@click.command(context_settings=dict(
    ignore_unknown_options=True,
    allow_extra_args=True,
))
@click.pass_context
def main(ctx):
    """CLI-Anything harness for Intelwatch.
    
    Zero friction. Full context. Competitive intelligence, M&A due diligence, and OSINT.
    """
    # Simply forward everything to `npx intelwatch`
    cmd = ["npx", "intelwatch"] + ctx.args
    
    try:
        # We use subprocess.call to forward stdin/stdout/stderr automatically
        sys.exit(subprocess.call(cmd))
    except FileNotFoundError:
        click.secho(
            "Error: 'npx' command not found. Please ensure Node.js is installed "
            "(https://nodejs.org/) and available in your PATH.",
            fg="red", err=True
        )
        sys.exit(1)

if __name__ == "__main__":
    main()
