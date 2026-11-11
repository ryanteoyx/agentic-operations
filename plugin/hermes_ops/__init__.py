from importlib import import_module

from .runtime_loader import load_core


def register(ctx):
    core = load_core()
    import_module(core.__name__ + ".tools").register_tools(ctx)
    cli = import_module(core.__name__ + ".cli")
    ctx.register_cli_command(
        name="ops", help="Synthetic manufacturing operations",
        setup_fn=cli.setup_parser, handler_fn=cli.run,
    )
