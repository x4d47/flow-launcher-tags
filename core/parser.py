from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol, Self

from core.lexer import Lexer, Token, TokenType


class ParserError(ValueError):
    pass


class Command(Protocol):
    pass


class EmptyCommand(Command):
    pass


@dataclass(frozen=True)
class GetProgramsByTag(Command):
    tag_name: str


@dataclass(frozen=True)
class AddTag(Command):
    tag_name: str
    program_name: str


@dataclass(frozen=True)
class RemoveTag(Command):
    tag_name: str
    program_name: str


class AutocompleteType(Enum):
    COMMAND = auto()
    TAG = auto()
    PROGRAM = auto()
    ADD_TAG_PROGRAM = auto()
    REMOVE_TAG_PROGRAM = auto()
    NOTHING = auto()


@dataclass(frozen=True)
class AutocompleteContext:
    type: list[AutocompleteType]
    prefix: str
    args: dict[str, str]


@dataclass(frozen=True)
class ParserResult:
    command: Command | None
    autocomplete_context: AutocompleteContext


class GrammarNodeType(Enum):
    ROOT = auto()
    SPACE = auto()
    TAG = auto()
    PROGRAM = auto()
    OP_ADD = auto()
    OP_REM = auto()

    @property
    def token_type(self) -> TokenType:
        mapping = {
            GrammarNodeType.ROOT: TokenType.NOTHING,
            GrammarNodeType.SPACE: TokenType.SPACE,
            GrammarNodeType.TAG: TokenType.IDENTIFIER,
            GrammarNodeType.PROGRAM: TokenType.IDENTIFIER,
            GrammarNodeType.OP_ADD: TokenType.OP_ADD,
            GrammarNodeType.OP_REM: TokenType.OP_REM,
        }
        return mapping[self]


class GrammarNode:
    def __init__(
        self,
        command: type[Command],
        node_type: GrammarNodeType,
        autocomplete_type_list: list[AutocompleteType],
        is_last: bool = False,
    ) -> None:
        self.command: type[Command] = command
        self.semantic_role: str = node_type.name
        self.expected_token_type: TokenType = node_type.token_type
        self.autocomplete_type_list: list[AutocompleteType] = autocomplete_type_list
        self.is_last: bool = is_last
        self.children: list[Self] = []

    def add_child(self, child_node: Self):
        self.children.append(child_node)

    def add_child_and_return(self, child_node: Self) -> Self:
        self.children.append(child_node)
        return self.children[-1]

    def next_node(self, token_type: TokenType) -> Self | None:
        for child in self.children:
            if token_type == child.expected_token_type:
                return child

        return None

    def set_last(self):
        self.is_last = True


# fmt: off
grammar: GrammarNode = GrammarNode(
    EmptyCommand, GrammarNodeType.ROOT, [AutocompleteType.COMMAND, AutocompleteType.TAG]
)

grammar.add_child_and_return(
    GrammarNode(GetProgramsByTag,        GrammarNodeType.TAG,    [AutocompleteType.TAG])
).set_last()
grammar.add_child(GrammarNode(AddTag,    GrammarNodeType.OP_ADD, [AutocompleteType.TAG]))
grammar.add_child(GrammarNode(RemoveTag, GrammarNodeType.OP_REM, [AutocompleteType.TAG]))

(
grammar.next_node(TokenType.OP_ADD)
    .add_child_and_return(GrammarNode(AddTag, GrammarNodeType.SPACE,   [AutocompleteType.TAG])) # pyright: ignore[reportOptionalMemberAccess]
    .add_child_and_return(GrammarNode(AddTag, GrammarNodeType.TAG,     [AutocompleteType.TAG]))
    .add_child_and_return(GrammarNode(AddTag, GrammarNodeType.SPACE,   [AutocompleteType.ADD_TAG_PROGRAM]))
    .add_child_and_return(GrammarNode(AddTag, GrammarNodeType.PROGRAM, [AutocompleteType.ADD_TAG_PROGRAM]))
    .set_last()
)

(
grammar.next_node(TokenType.OP_REM)
    .add_child_and_return(GrammarNode(RemoveTag, GrammarNodeType.SPACE,   [AutocompleteType.TAG])) # pyright: ignore[reportOptionalMemberAccess]
    .add_child_and_return(GrammarNode(RemoveTag, GrammarNodeType.TAG,     [AutocompleteType.TAG]))
    .add_child_and_return(GrammarNode(RemoveTag, GrammarNodeType.SPACE,   [AutocompleteType.REMOVE_TAG_PROGRAM]))
    .add_child_and_return(GrammarNode(RemoveTag, GrammarNodeType.PROGRAM, [AutocompleteType.REMOVE_TAG_PROGRAM]))
    .set_last()
)
# fmt: on


class Parser:
    def __init__(self) -> None:
        self.current_grammar_node: GrammarNode = grammar
        self.command_args: dict[str, str] = {}
        self.current_token: Token = Token(TokenType.NOTHING, "")

    def parse_token(self, token: Token) -> None:
        if token.type == TokenType.NOTHING:
            return

        next_node = self.current_grammar_node.next_node(token.type)

        if not next_node:
            return

        self.current_grammar_node = next_node

        self.current_token = token

        match self.current_grammar_node.semantic_role:
            case GrammarNodeType.TAG.name:
                self.command_args["tag_name"] = token.value
            case GrammarNodeType.PROGRAM.name:
                self.command_args["program_name"] = token.value
            case _:
                pass

    @property
    def autocomplete_context(self) -> AutocompleteContext:
        if self.current_grammar_node.semantic_role.startswith("OP_"):
            prefix = ""
        else:
            prefix = (
                self.current_token.value.strip()
            )  # strip() in case the value is space

        return AutocompleteContext(
            self.current_grammar_node.autocomplete_type_list,
            prefix,
            self.command_args.copy(),
        )

    def get_result(self) -> ParserResult:
        command_cls = self.current_grammar_node.command

        if self.current_grammar_node.is_last:
            command = command_cls(**self.command_args)
        else:
            command = None

        return ParserResult(command, self.autocomplete_context)


def parse_input(input: str) -> ParserResult:
    lexer = Lexer(input)
    parser = Parser()

    for token in lexer.tokens:
        print(token)
        parser.parse_token(token)

    return parser.get_result()
