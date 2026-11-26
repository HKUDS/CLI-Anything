"""Script, ScriptableObject, menu, test, build and package commands.

The host CLI calls ``register(cli, run)``. ``run`` has the host contract
``run(ctx, "<group>.<action>", PascalCaseArg=value)`` and owns transport,
output and exit codes; this module only builds Click commands.
"""

import click


def register(cli, run):
    """Attach automation commands to an existing cli_anything Click group."""

    script = click.Group("script", help="Inspect and edit C# scripts with hash-guarded bounds.")

    @script.command("info")
    @click.argument("script_path")
    @click.pass_context
    def script_info(ctx, script_path):
        """Show metadata for a MonoScript (.cs) asset: class, GUID, size and SHA-256."""
        run(ctx, "script.info", ScriptPath=script_path)

    @script.command("read")
    @click.argument("script_path")
    @click.option("--start-line", type=click.IntRange(min=1), default=1, show_default=True,
                  help="First 1-based line to return.")
    @click.option("--line-count", type=click.IntRange(min=0), default=0, show_default=True,
                  help="Number of lines to return; 0 returns to the end.")
    @click.option("--max-bytes", type=click.IntRange(min=1, max=2000000), default=200000, show_default=True,
                  help="UTF-8 byte cap for the returned text.")
    @click.pass_context
    def script_read(ctx, script_path, start_line, line_count, max_bytes):
        """Read a .cs asset as text, with line and byte bounds."""
        run(ctx, "script.read", ScriptPath=script_path, StartLine=start_line,
            LineCount=line_count, MaxBytes=max_bytes)

    @script.command("edit")
    @click.argument("script_path")
    @click.option("--expected-sha256", required=True,
                  help="SHA-256 of the current file, from script info or script read.")
    @click.option("--start-line", type=click.IntRange(min=1), required=True,
                  help="First changed line, 1-based.")
    @click.option("--start-column", type=click.IntRange(min=1), required=True,
                  help="First changed column, 1-based UTF-16 code units.")
    @click.option("--end-line", type=click.IntRange(min=1), required=True,
                  help="Line after the last changed character, or the same line.")
    @click.option("--end-column", type=click.IntRange(min=1), required=True,
                  help="Exclusive end column; end_line/end_column may be line_count+1/1 for EOF.")
    @click.option("--new-text", default="", help="Replacement text; empty deletes the range.")
    @click.pass_context
    def script_edit(ctx, script_path, expected_sha256, start_line, start_column,
                    end_line, end_column, new_text):
        """Replace one bounded range after verifying --expected-sha256; compilation is not proven."""
        run(ctx, "script.edit", ScriptPath=script_path, ExpectedSha256=expected_sha256,
            Edits=[{
                "StartLine": start_line,
                "StartColumn": start_column,
                "EndLine": end_line,
                "EndColumn": end_column,
                "NewText": new_text,
            }])

    @script.command("validate")
    @click.argument("script_path")
    @click.pass_context
    def script_validate(ctx, script_path):
        """Report file checks; compile validation of one file is unavailable in Unity."""
        run(ctx, "script.validate", ScriptPath=script_path)

    @script.command("search")
    @click.argument("pattern")
    @click.option("--under", default="Assets", show_default=True,
                  help="Project-relative Assets/ folder or .cs file to search.")
    @click.option("--limit", type=click.IntRange(min=1, max=500), default=100, show_default=True,
                  help="Maximum matches to return.")
    @click.option("--max-files", type=click.IntRange(min=1, max=20000), default=5000, show_default=True,
                  help="Maximum .cs files to scan.")
    @click.option("--ignore-case", is_flag=True, help="Match case-insensitively.")
    @click.pass_context
    def script_search(ctx, pattern, under, limit, max_files, ignore_case):
        """Search .cs file contents with a .NET regular expression."""
        run(ctx, "script.search", Pattern=pattern, Under=under, Limit=limit,
            MaxFiles=max_files, IgnoreCase=ignore_case)

    scriptable_object = click.Group("scriptable-object",
                                    help="Inspect or create ScriptableObject assets.")

    @scriptable_object.command("types")
    @click.option("--filter", "name_filter", default="",
                  help="Case-insensitive substring of the namespace-qualified type name.")
    @click.option("--limit", type=click.IntRange(min=1, max=1000), default=100, show_default=True)
    @click.pass_context
    def scriptable_object_types(ctx, name_filter, limit):
        """List instantiable ScriptableObject types loaded in the Editor."""
        run(ctx, "scriptable-object.types", Filter=name_filter, Limit=limit)

    @scriptable_object.command("inspect")
    @click.argument("asset_path")
    @click.option("--depth", type=click.IntRange(min=0, max=16), default=2, show_default=True,
                  help="Serialized property nesting depth to descend.")
    @click.option("--limit", type=click.IntRange(min=1, max=2000), default=200, show_default=True,
                  help="Maximum serialized properties to return.")
    @click.pass_context
    def scriptable_object_inspect(ctx, asset_path, depth, limit):
        """Dump a .asset ScriptableObject's type and serialized fields."""
        run(ctx, "scriptable-object.inspect", AssetPath=asset_path, Depth=depth, Limit=limit)

    @scriptable_object.command("create")
    @click.argument("type_name")
    @click.argument("asset_path")
    @click.pass_context
    def scriptable_object_create(ctx, type_name, asset_path):
        """Create a new .asset inside an existing Assets/ folder; never overwrites."""
        run(ctx, "scriptable-object.create", TypeName=type_name, AssetPath=asset_path)

    menu = _editor_menu(run)
    editor = cli.commands.get("editor")
    if editor is None:
        editor = click.Group("editor", help="Query or control the Editor.")
        cli.add_command(editor, "editor")
    if "menu" not in editor.commands:
        editor.add_command(menu)

    test = click.Group("test", help="Run Unity Test Framework tests and poll their jobs.")

    @test.command("run")
    @click.option("--mode", type=click.Choice(["EditMode", "PlayMode"], case_sensitive=False),
                  default="EditMode", show_default=True,
                  help="Test mode; run the two modes as separate jobs.")
    @click.option("--test-name", "test_names", multiple=True, help="Full test name to run; repeatable.")
    @click.option("--group-name", "group_names", multiple=True, help="Test group regex; repeatable.")
    @click.option("--category", "category_names", multiple=True, help="NUnit category; repeatable.")
    @click.option("--assembly", "assembly_names", multiple=True, help="Test assembly name; repeatable.")
    @click.pass_context
    def test_run(ctx, mode, test_names, group_names, category_names, assembly_names):
        """Start an asynchronous test run and print its job ID."""
        run(ctx, "test.run", Mode=mode, TestNames=list(test_names),
            GroupNames=list(group_names), CategoryNames=list(category_names),
            AssemblyNames=list(assembly_names))

    @test.command("job")
    @click.argument("job_id", required=False, default="")
    @click.option("--details", "include_details", is_flag=True,
                  help="Include stack traces for failed tests.")
    @click.pass_context
    def test_job(ctx, job_id, include_details):
        """Show test job status and counts; omit JOB_ID for the latest run."""
        run(ctx, "test.job", JobId=job_id, IncludeDetails=include_details)

    build = click.Group("build", help="Inspect build settings and run explicit player builds.")

    @build.command("info")
    @click.pass_context
    def build_info(ctx):
        """Show the active target, player settings and Build Settings scenes."""
        run(ctx, "build.info")

    @build.command("targets")
    @click.pass_context
    def build_targets(ctx):
        """List known BuildTarget values with module availability."""
        run(ctx, "build.targets")

    @build.command("start")
    @click.argument("target")
    @click.argument("output_path")
    @click.option("--scene", "scene_paths", multiple=True,
                  help="Assets/... unity scene; repeatable. Defaults to enabled Build Settings scenes.")
    @click.option("--development/--release", default=False, show_default=True)
    @click.option("--allow-debugging/--no-allow-debugging", default=False, show_default=True)
    @click.pass_context
    def build_start(ctx, target, output_path, scene_paths, development, allow_debugging):
        """Queue a player build and print its job ID; run build job JOB_ID to poll."""
        run(ctx, "build.start", Target=target, OutputPath=output_path,
            ScenePaths=list(scene_paths), Development=development,
            AllowDebugging=allow_debugging)

    @build.command("job")
    @click.argument("job_id", required=False, default="")
    @click.pass_context
    def build_job(ctx, job_id):
        """Show a build job's state, report summary and errors."""
        run(ctx, "build.job", JobId=job_id)

    @build.command("cancel")
    @click.argument("job_id", required=False, default="")
    @click.pass_context
    def build_cancel(ctx, job_id):
        """Cancel a queued build; Unity cannot cancel a running BuildPlayer."""
        run(ctx, "build.cancel", JobId=job_id)

    package = click.Group("package", help="List packages and start explicit add/remove requests.")

    @package.command("list")
    @click.option("--offline/--online", default=True, show_default=True,
                  help="List from the local package cache instead of the registry.")
    @click.option("--include-indirect/--direct-only", default=False, show_default=True,
                  help="Include indirect dependencies.")
    @click.pass_context
    def package_list(ctx, offline, include_indirect):
        """Start an asynchronous package listing and print its job ID."""
        run(ctx, "package.list", Offline=offline, IncludeIndirect=include_indirect)

    @package.command("add")
    @click.argument("identifier")
    @click.pass_context
    def package_add(ctx, identifier):
        """Queue a package add; IDENTIFIER is a UPM name, name@version, git URL or local path."""
        run(ctx, "package.add", Identifier=identifier)

    @package.command("remove")
    @click.argument("name")
    @click.pass_context
    def package_remove(ctx, name):
        """Queue a package removal by name without @version."""
        run(ctx, "package.remove", Name=name)

    @package.command("job")
    @click.argument("job_id", required=False, default="")
    @click.pass_context
    def package_job(ctx, job_id):
        """Show a package request's state and result; omit JOB_ID for the latest request."""
        run(ctx, "package.job", JobId=job_id)

    for group in (script, scriptable_object, test, build, package):
        cli.add_command(group, group.name)


def _editor_menu(run):
    @click.command("menu")
    @click.argument("menu_path")
    @click.pass_context
    def command(ctx, menu_path):
        """Execute an Editor menu item by its exact path; explicit invocation only."""
        run(ctx, "menu.execute", MenuPath=menu_path)
    return command
