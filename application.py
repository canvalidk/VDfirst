"""Parameterized-headword parsing and flat instantiation.

An authored headword is a signature::

    force_p_t

The text before the first underscore is the stem; following underscore
segments are positional formal parameters.  A residual may demand that
signature with zero, some, or all actuals::

    force
    force_Earth
    force_Earth_3

This module deliberately implements *flat partial instantiation*, not
lambda-calculus closures.  Actuals supplied by one call are substituted
simultaneously.  Unsupplied formals remain visible ordinary symbols.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


ARGUMENT_ATOM_PATTERN = r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*"
FORMAL_ATOM_PATTERN = r"[A-Za-z]+(?:[A-Za-z0-9]*)(?:-[A-Za-z0-9]+)*"
ARGUMENT_ATOM_RE = re.compile(rf"^(?:{ARGUMENT_ATOM_PATTERN})$")
FORMAL_ATOM_RE = re.compile(rf"^(?:{FORMAL_ATOM_PATTERN})$")


class HeadwordApplicationError(ValueError):
    """Base class for invalid parameterized-headword operations."""


class HeadwordArityError(HeadwordApplicationError):
    """A call supplies more actuals than its signature accepts."""

    def __init__(self, call: str, stem: str, expected: int, supplied: int):
        self.call = call
        self.stem = stem
        self.expected = expected
        self.supplied = supplied
        super().__init__(
            f"'{call}' supplies {supplied} arguments to '{stem}', "
            f"which accepts {expected}"
        )


class HeadwordSignatureConflictError(HeadwordApplicationError):
    """Two entries give one stem different temporary signatures."""

    def __init__(
        self,
        stem: str,
        existing_formals: tuple[str, ...],
        new_formals: tuple[str, ...],
    ):
        self.stem = stem
        self.existing_formals = existing_formals
        self.new_formals = new_formals
        super().__init__(
            f"headword stem '{stem}' already has signature "
            f"{_format_signature(stem, existing_formals)!r}; "
            f"cannot also define {_format_signature(stem, new_formals)!r}"
        )


def _format_signature(stem: str, formals: tuple[str, ...]) -> str:
    return stem + "".join(f"_{formal}" for formal in formals)


@dataclass(frozen=True)
class HeadwordSignature:
    """The stem and positional formals declared by an entry headword."""

    stem: str
    formals: tuple[str, ...] = ()

    @classmethod
    def parse(cls, text: str) -> "HeadwordSignature":
        if not isinstance(text, str):
            raise TypeError("headword signature must be a string")
        if not text or text != text.strip():
            raise HeadwordApplicationError(
                "headword signature must be non-empty with no outer whitespace"
            )

        stem, *formals = text.split("_")
        if not stem:
            raise HeadwordApplicationError(
                f"invalid headword signature {text!r}: empty stem"
            )
        if any(not FORMAL_ATOM_RE.fullmatch(formal) for formal in formals):
            raise HeadwordApplicationError(
                f"invalid headword signature {text!r}: formal parameters "
                "must be non-empty letter-led atoms containing only letters, "
                "digits, and internal hyphens"
            )
        if len(set(formals)) != len(formals):
            raise HeadwordApplicationError(
                f"invalid headword signature {text!r}: formal parameters "
                "must be unique"
            )
        return cls(stem, tuple(formals))

    @property
    def arity(self) -> int:
        return len(self.formals)

    @property
    def text(self) -> str:
        return _format_signature(self.stem, self.formals)

    def call(self, actuals: tuple[str, ...] = ()) -> "HeadwordCall":
        call = HeadwordCall(self.stem, actuals)
        self.check(call)
        return call

    def check(self, call: "HeadwordCall") -> None:
        if call.stem != self.stem:
            raise HeadwordApplicationError(
                f"call stem {call.stem!r} does not match signature "
                f"stem {self.stem!r}"
            )
        if call.arity > self.arity:
            raise HeadwordArityError(
                call.text,
                self.stem,
                self.arity,
                call.arity,
            )


@dataclass(frozen=True)
class HeadwordCall:
    """A headword stem with zero or more supplied positional actuals."""

    stem: str
    actuals: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.stem:
            raise HeadwordApplicationError("headword call has an empty stem")
        if any(not ARGUMENT_ATOM_RE.fullmatch(actual) for actual in self.actuals):
            raise HeadwordApplicationError(
                f"invalid headword call {self.text!r}: arguments must be "
                "non-empty atoms containing only letters, digits, and "
                "internal hyphens"
            )

    @classmethod
    def parse(cls, text: str) -> "HeadwordCall":
        if not isinstance(text, str):
            raise TypeError("headword call must be a string")
        if not text or text != text.strip():
            raise HeadwordApplicationError(
                "headword call must be non-empty with no outer whitespace"
            )
        stem, *actuals = text.split("_")
        return cls(stem, tuple(actuals))

    @property
    def arity(self) -> int:
        return len(self.actuals)

    @property
    def text(self) -> str:
        return self.stem + "".join(f"_{actual}" for actual in self.actuals)


def instantiate_definition(
    definition: str,
    signature: HeadwordSignature,
    call: HeadwordCall,
) -> str:
    """Flatly instantiate ``definition`` with the actuals in ``call``.

    Replacement is simultaneous and case-sensitive.  A formal is replaced
    when it is a standalone prose atom or a complete underscore argument
    segment.  Hyphens glue atoms, so a formal is not replaced inside a
    larger hyphenated or alphanumeric token.  Backtick-escaped spans remain
    literal and are left untouched for the tokenizer to unescape later.
    """

    signature.check(call)
    substitutions = dict(zip(signature.formals, call.actuals))
    if not substitutions:
        return definition

    alternatives = "|".join(
        re.escape(formal)
        for formal in sorted(substitutions, key=len, reverse=True)
    )
    pattern = re.compile(
        rf"(?<![A-Za-z0-9-])(?:{alternatives})(?![A-Za-z0-9-])"
    )

    def replace_unescaped(segment: str) -> str:
        return pattern.sub(lambda match: substitutions[match.group(0)], segment)

    chunks = definition.split("`")
    return "`".join(
        chunk if index % 2 else replace_unescaped(chunk)
        for index, chunk in enumerate(chunks)
    )
