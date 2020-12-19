# Copyright 2018 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import os
from enum import Enum
from itertools import repeat
from typing import Iterable, TypeVar, Union, cast

from pants.engine.addresses import Address, Addresses, BuildFileAddress
from pants.engine.console import Console
from pants.engine.fs import DigestContents, FileContent, PathGlobs
from pants.engine.goal import Goal, GoalSubsystem
from pants.engine.rules import Get, MultiGet, collect_rules, goal_rule
from pants.engine.target import Target, Targets


class OutputOptions(Enum):
    RAW = "raw"
    JSON = "json"


class PeekSubsystem(GoalSubsystem):
    """Display BUILD file info to the console.

    In its most basic form, `peek` just prints the contents of a BUILD file. It can also display
    multiple BUILD files, or render normalized target metadata as JSON for consumption by other
    programs.
    """

    name = "peek"

    @classmethod
    def register_options(cls, register):
        super().register_options(register)
        register(
            "--output",
            type=OutputOptions,
            default=OutputOptions.RAW,
            help="which output style peek should use",
        )

    @property
    def output(self) -> OutputOptions:
        return cast(OutputOptions, self.options.output)


class Peek(Goal):
    subsystem_cls = PeekSubsystem


_T = TypeVar("_T")
_U = TypeVar("_U")


def _intersperse(x: _T, ys: Iterable[_U]) -> Iterable[Union[_T, _U]]:
    # Use stateful iterator to safely iterate through first item
    it = iter(ys)
    for y in it:
        yield y
        break
    for x, y in zip(repeat(x), it):
        yield x
        yield y


def _render_raw(fc: FileContent, encoding: str = "utf-8") -> str:
    dashes = "-" * len(fc.path)
    content = fc.content.decode(encoding)
    parts = [dashes, fc.path, dashes, content]
    if not content.endswith(os.linesep):
        parts.append("")
    return os.linesep.join(parts)


@goal_rule
async def peek(
    console: Console,
    subsys: PeekSubsystem,
    addresses: Addresses,
) -> Peek:
    # TODO: better options for target selection (globs, transitive, etc)?
    targets: Iterable[Target]
    targets = await Get(Targets, Addresses, addresses)
    # TODO: handle target not found exceptions better here
    build_file_addresses = await MultiGet(
        Get(BuildFileAddress, Address, t.address) for t in targets
    )
    build_file_paths = {a.rel_path for a in build_file_addresses}
    digest_contents = await Get(DigestContents, PathGlobs(build_file_paths))

    # TODO: programmatically determine correct encoding
    rendereds = map(_render_raw, digest_contents)
    for output in _intersperse(os.linesep, rendereds):
        console.print_stdout(output)

    return Peek(exit_code=0)


def rules():
    return collect_rules()
