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

Structured arguments (prototype, 12 November 2026).  An actual is a value::

    value := atom | atom ':' value | '[' ']' | '[' value (',' value)* ']'

so ``[A:spring:s1,R:spring:s2]`` is a list of two tagged values.  A formal
is a plain name, which accepts any value, or one of three patterns::

    []        the empty list
    [h|t]     a non-empty list; h is bound to its first item, t to the rest
    TAG:x     a value tagged TAG; x is bound to what the tag wraps

Several entries may then define one stem with different patterns, and the
form of a call's arguments decides which of them can answer it.  Values and
patterns contain no spaces and no underscores.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


ARGUMENT_ATOM_PATTERN = r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*"
FORMAL_ATOM_PATTERN = r"[A-Za-z]+(?:[A-Za-z0-9]*)(?:-[A-Za-z0-9]+)*"
ARGUMENT_ATOM_RE = re.compile(rf"^(?:{ARGUMENT_ATOM_PATTERN})$")
FORMAL_ATOM_RE = re.compile(rf"^(?:{FORMAL_ATOM_PATTERN})$")
_ATOM_AT = re.compile(ARGUMENT_ATOM_PATTERN)
_CONS_RE = re.compile(rf"^\[({FORMAL_ATOM_PATTERN})\|({FORMAL_ATOM_PATTERN})\]$")
_TAG_RE = re.compile(rf"^({ARGUMENT_ATOM_PATTERN}):({FORMAL_ATOM_PATTERN})$")


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
    """Two entries give one stem signatures that cannot stand together."""

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


# ── Values ──────────────────────────────────────────────────────────


def scan_value(text: str, pos: int = 0) -> int | None:
    """End index of the longest value starting at ``pos``, or None.

    A tag needs a value straight after its colon, so ``p: next`` scans as
    the atom ``p`` and leaves the colon alone.
    """

    if pos < len(text) and text[pos] == "[":
        cursor = pos + 1
        if cursor < len(text) and text[cursor] == "]":
            return cursor + 1
        while True:
            end = scan_value(text, cursor)
            if end is None or end >= len(text):
                return None
            if text[end] == "]":
                return end + 1
            if text[end] != ",":
                return None
            cursor = end + 1
    atom = _ATOM_AT.match(text, pos)
    if atom is None:
        return None
    end = atom.end()
    if end < len(text) and text[end] == ":":
        inner = scan_value(text, end + 1)
        if inner is not None:
            return inner
    return end


def is_value(text: str) -> bool:
    """Whether the whole of ``text`` is one value."""

    return bool(text) and scan_value(text) == len(text)


def list_items(text: str) -> tuple[str, ...] | None:
    """The top-level items of a list value, or None when it is not a list."""

    if not is_value(text) or not text.startswith("["):
        return None
    items: list[str] = []
    cursor = 1
    while text[cursor] != "]":
        end = scan_value(text, cursor)
        items.append(text[cursor:end])
        cursor = end + 1 if text[end] == "," else end
    return tuple(items)


def tagged_value(text: str) -> tuple[str, str] | None:
    """``(tag, inner)`` for a tagged value, or None."""

    if not is_value(text) or text.startswith("["):
        return None
    atom = _ATOM_AT.match(text)
    if atom.end() == len(text):
        return None
    return atom.group(0), text[atom.end() + 1:]


def format_list(items: tuple[str, ...]) -> str:
    return "[" + ",".join(items) + "]"


# ── Formals ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FormalPattern:
    """One formal of a signature: a plain name or a pattern on a value's form."""

    text: str
    kind: str  # 'name' | 'empty' | 'cons' | 'tag'
    names: tuple[str, ...] = ()
    tag: str = ""

    @classmethod
    def parse(cls, text: str) -> "FormalPattern | None":
        if FORMAL_ATOM_RE.fullmatch(text):
            return cls(text, "name", (text,))
        if text == "[]":
            return cls(text, "empty")
        cons = _CONS_RE.fullmatch(text)
        if cons:
            return cls(text, "cons", (cons.group(1), cons.group(2)))
        tag = _TAG_RE.fullmatch(text)
        if tag:
            return cls(text, "tag", (tag.group(2),), tag.group(1))
        return None

    def bind(self, actual: str) -> tuple[tuple[str, str], ...] | None:
        """The names this formal binds for ``actual``, or None when the form does not fit."""

        if self.kind == "name":
            return ((self.names[0], actual),)
        if self.kind == "tag":
            split = tagged_value(actual)
            if split is None or split[0] != self.tag:
                return None
            return ((self.names[0], split[1]),)
        items = list_items(actual)
        if items is None:
            return None
        if self.kind == "empty":
            return () if not items else None
        if not items:
            return None
        return ((self.names[0], items[0]), (self.names[1], format_list(items[1:])))


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
        patterns = [FormalPattern.parse(formal) for formal in formals]
        if any(pattern is None for pattern in patterns):
            raise HeadwordApplicationError(
                f"invalid headword signature {text!r}: formal parameters "
                "must be non-empty letter-led atoms containing only letters, "
                "digits, and internal hyphens, or one of the patterns "
                "[], [h|t] and TAG:x"
            )
        names = [name for pattern in patterns for name in pattern.names]
        if len(set(names)) != len(names):
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

    @property
    def patterns(self) -> tuple[FormalPattern, ...]:
        return tuple(FormalPattern.parse(formal) for formal in self.formals)

    @property
    def is_patterned(self) -> bool:
        """Whether any formal constrains the form of its argument."""
        return any(pattern.kind != "name" for pattern in self.patterns)

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

    def bindings(self, call: "HeadwordCall") -> tuple[tuple[str, str], ...] | None:
        """The name/value pairs the call's actuals supply, or None when a
        supplied actual does not have the form its formal requires.

        Positions the call leaves unsupplied bind nothing and exclude nothing.
        """

        self.check(call)
        bound: list[tuple[str, str]] = []
        for pattern, actual in zip(self.patterns, call.actuals):
            pairs = pattern.bind(actual)
            if pairs is None:
                return None
            bound.extend(pairs)
        return tuple(bound)

    def matches(self, call: "HeadwordCall") -> bool:
        """Whether this signature can answer the call: same stem, arity
        respected, and every supplied actual of the required form."""

        return (
            call.stem == self.stem
            and call.arity <= self.arity
            and self.bindings(call) is not None
        )

    def compatible_with(self, other: "HeadwordSignature") -> bool:
        """Whether two entries may define the same stem.

        They need the same arity.  Where both leave a position plain they
        must use the same name; a pattern may differ from anything.
        """

        if self.arity != other.arity:
            return False
        return all(
            mine.kind != "name" or theirs.kind != "name" or mine.text == theirs.text
            for mine, theirs in zip(self.patterns, other.patterns)
        )


@dataclass(frozen=True)
class HeadwordCall:
    """A headword stem with zero or more supplied positional actuals."""

    stem: str
    actuals: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.stem:
            raise HeadwordApplicationError("headword call has an empty stem")
        if any(not is_value(actual) for actual in self.actuals):
            raise HeadwordApplicationError(
                f"invalid headword call {self.text!r}: arguments must be "
                "non-empty atoms containing only letters, digits, and "
                "internal hyphens, or lists and tagged values built from them"
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

    A pattern formal binds the names inside it: ``[h|t]`` binds the first
    item and the rest of a list, ``TAG:x`` what the tag wraps.  A call
    whose supplied actuals do not have the required form is refused.
    """

    bound = signature.bindings(call)
    if bound is None:
        raise HeadwordApplicationError(
            f"{call.text!r} does not have the form {signature.text!r} requires"
        )
    substitutions = dict(bound)
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
