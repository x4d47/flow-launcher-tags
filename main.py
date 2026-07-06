import logging
import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Callable, override

from flowlauncher.FlowLauncher import FlowLauncher
from flowlauncher.FlowLauncherAPI import FlowLauncherAPI

from flowlauncher_types import FlowLauncherResult
from lexer import CommandKeyword, Lexer
from parser import (
    AddTag,
    AutocompleteContext,
    AutocompleteType,
    Command,
    GetProgramsByTag,
    Parser,
    ParserError,
    RemoveTag,
)
from program_manager import ProgramManager
from programs import Program
from tag_manager import TagManager

logging.basicConfig(
    filename="plugin.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

appdata = os.environ.get("APPDATA")

PLUGIN_KEYWORD = "tag"
PLUGIN_DATADIR = (
    (Path(appdata) / "FlowLauncher" / "Cache" / "Plugins" / "Tags")
    if appdata
    else Path(".")
)


class TagsPlugin(FlowLauncher):
    def __init__(self):
        self.new_query: str

        self.command_registry: dict[
            Command, Callable[..., FlowLauncherResult | None]
        ] = {
            GetProgramsByTag: self.get_programs_by_tag,
            AddTag: self.add_tag,
            RemoveTag: self.remove_tag,
        }

        try:
            self.program_manager: ProgramManager = ProgramManager.from_file(
                PLUGIN_DATADIR / "programs.json"
            )
            logger.info("Loaded programs from file")
        except (
            Exception
        ) as e:  # todo: should differentiate access problems from file unexistence
            logger.exception("Failed to load programs from file: %s", e)
            self.program_manager = ProgramManager.from_os()
            self.program_manager.to_file(PLUGIN_DATADIR / "programs.json")

        try:
            self.tag_manager: TagManager = TagManager.from_file(
                PLUGIN_DATADIR / "tags.json"
            )
            logger.info("Loaded tags from file")
        except Exception as e:
            logger.exception("Failed to load tags from file: %s", e)
            self.tag_manager = TagManager()

        super().__init__()

    @override
    def query(self, param: str = "") -> list[FlowLauncherResult]:
        logger.info("Query: %s", param)

        results: list[FlowLauncherResult] = []

        lexer = Lexer(param)
        parser = Parser()

        try:
            for token in lexer.tokens:
                parser.parse_token(token)

            parser_result = parser.get_result()
        except ParserError as e:
            logger.exception("Parser error: %s", e)
            return [e.as_flowlauncher_result()]

        results.extend(self.autocomplete(parser_result.autocomplete_context))

        return results

    @override
    def context_menu(self, data):
        return [
            {
                "Title": "Hello World Python's Context menu",
                "SubTitle": "Press enter to open Flow the plugin's repo in GitHub",
                "IcoPath": "Images/app.png",
                "JsonRPCAction": {
                    "method": "open_url",
                    "parameters": [
                        "https://github.com/Flow-Launcher/Flow.Launcher.Plugin.HelloWorldPython"
                    ],
                },
            }
        ]

    def open_url(self, url: str):
        _ = webbrowser.open(url)

    def launch_program(self, path: str):
        _ = subprocess.Popen(path)

    def autocomplete_command(self) -> list[FlowLauncherResult]:
        SCORE: int = 100  # big enough for commands to appear at the top of a list

        return [
            {
                "Title": "Add tag",
                "QuerySuggestionText": "type tag name or select from the list",
                "IcoPath": "Images/transparent.png",
                "JsonRPCAction": {
                    "method": "Flow.Launcher.ChangeQuery",
                    "parameters": [
                        f"{PLUGIN_KEYWORD} {CommandKeyword.ADD_TAG} ",
                        False,
                    ],
                    "dontHideAfterAction": True,
                },
                "Score": SCORE,
            },
            {
                "Title": "Remove tag",
                "QuerySuggestionText": "type tag name or select from the list",
                "IcoPath": "Images/transparent.png",
                "JsonRPCAction": {
                    "method": "Flow.Launcher.ChangeQuery",
                    "parameters": [
                        f"{self.new_query} {CommandKeyword.REMOVE_TAG} ",
                        False,
                    ],
                    "dontHideAfterAction": True,
                },
                "Score": SCORE,
            },
        ]

    def autocomplete_tag(self, prefix: str) -> list[FlowLauncherResult]:
        results: list[FlowLauncherResult] = []

        for tag in self.tag_manager.tags:
            if tag.startswith(prefix):
                results.append(
                    {
                        "Title": f"{tag}",
                        "IcoPath": "Images/transparent.png",
                        "QuerySuggestionText": f"{tag}",
                        "JsonRPCAction": {
                            "method": "Flow.Launcher.ChangeQuery",
                            "parameters": [f"{self.new_query} {tag} ", False],
                            "dontHideAfterAction": True,
                        },
                    }
                )

        return results

    def autocomplete(self, context: AutocompleteContext) -> list[FlowLauncherResult]:
        result: list[FlowLauncherResult] = []

        match context.type:
            case [AutocompleteType.TAG, AutocompleteType.COMMAND]:
                self.new_query = f"{PLUGIN_KEYWORD}"
                result = [
                    *self.autocomplete_command(),
                    *self.autocomplete_tag(context.prefix),
                ]
            case _:
                pass

        return result

    def get_programs_by_tag(self) -> FlowLauncherResult:
        return FlowLauncherResult()

    def add_tag(self, tag: str, program_name: str):
        program: Program | None = self.program_manager.find_one(program_name)

        if program is not None:
            self.tag_manager.add(program, tag)

            FlowLauncherAPI.show_msg(
                "Success", f"Assigned tag '{tag}' to program '{program_name}'"
            )

            self.tag_manager.to_file(
                PLUGIN_DATADIR / "tags.json"
            )  # todo: catch possible exception
        else:
            FlowLauncherAPI.show_msg(
                "Cannot assign tag", f"Program '{program}' not found."
            )

    def remove_tag(self, _tag: str, _program_name: str):
        pass


if __name__ == "__main__":
    _ = TagsPlugin()
