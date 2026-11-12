# Structured arguments and choice of definition by form

- Source: Can, 12 November 2026 ("Yes, build that"), after the member-list hand probe of the same day showed three kinds of step that the hand-trace recorder accepts as unchecked readings: building the remaining list, splitting on empty or not, and dispatching on action or reaction.
- Role: lets the engine carry those steps itself. Extends `2026-09-01-vd-parameterized-headwords.md` and `2026-11-11-record-every-step.md`.
- Status: Implemented prototype. The tests are the contract.
- Related files: `application.py`, `engine.py`, `simulator.py`, `demand.py`, `prediction_set.py`, `member_list_demo.py`, `test_structured_arguments.py`
- Related ADRs: none.

---

## 1. Purpose

A call's arguments were single atoms, and every entry of a stem had the same formals, so nothing about an argument could decide which definition applied. The contribution recursion of 11 November needs both: a remaining list that shrinks, and a base case chosen when it is empty. So does dispatch on whether a member is an action or a reaction.

## 2. Scope

1. **Values.** An actual is an atom, a tagged value, or a list:

   ```text
   value := atom | atom ':' value | '[' ']' | '[' value (',' value)* ']'
   ```

   `[A:spring:s1,R:spring:s2]` is a list of two tagged values. No spaces, no underscores.
2. **Patterns.** A formal is a plain name, which accepts any value, or one of three patterns on a value's form:

   | Formal | Accepts | Binds |
   |---|---|---|
   | `[]` | the empty list | nothing |
   | `[h\|t]` | a non-empty list | `h` to its first item, `t` to the rest |
   | `TAG:x` | a value tagged `TAG` | `x` to what the tag wraps |

3. **Clauses.** Several entries may define one stem with different patterns, as function clauses do:

   ```text
   contribution_p_[]        := the zero vector
   contribution_p_[m|rest]  := impressed-force_m_p plus contribution_p_rest
   ```

4. **Choice by form.** An entry can answer a call only if every supplied argument has the form its formal requires. When that leaves one entry, the choice is forced and no person makes it. When it leaves several, a person chooses, as before.
5. **Evidence.** An entry step records every clause of the stem and which of them fit, so a forced choice and a chosen one can be told apart in the record.

## 3. Non-Goals

- A demand's result used as an argument of a later call. The list is supplied as text (§5.6).
- Nested patterns, literal-atom patterns, guards, or patterns on atoms.
- Checking arithmetic. Every response is still supplied.
- Deciding which definition applies when form does not settle it.
- Entry wording for Newton. `member_list_demo.py` holds a prototype dictionary only.

## 4. Current Behaviour

See §1. A stem had one formal list for the whole dictionary; `entry_by_call` returned every entry of the stem; the tokenizer read an argument with the atom pattern only.

## 5. Proposed Behaviour

1. **Signatures.** Entries of one stem need the same arity. Where both leave a position plain they use the same name, as before. A pattern may differ from anything. Names bound anywhere in a signature are unique.
2. **Matching.** `HeadwordSignature.matches(call)` holds when the stem agrees, the arity is respected, and each supplied actual fits its formal. Positions the call leaves unsupplied exclude nothing, so an under-applied call such as `contribution_A` is answered by every clause.
3. **Instantiation** binds the names a pattern introduces and substitutes them as formals are substituted now. A call whose arguments do not fit is refused.
4. **Tokenizer.** After an underscore the tokenizer reads a whole value. Calls with a list or tagged argument are matched before the rest, because their arguments sit between delimiters and may spell other headwords. A colon or period after an atom is still punctuation unless a value follows the colon directly.
5. **Lookup.** `Simulator.entry_indexes(call)` returns the entries that can answer the call. `Simulator.clause_indexes(call)` returns every entry of the stem. The REPL expands without asking when one entry answers; the bridge lists only answering entries as candidates.
6. **Supplying the list.** `net-force_p := haze_p plus contribution_p` leaves the list unsupplied. A person supplies the fully applied call (`contribution_A_[A:spring:s1,...]`) at that demand, which is recorded as a supplied input. From there the recursion runs on entries alone.
7. **Statements.** An entry step whose stem has clauses ruled out by form says so: "…; the form of the demand rules out E5." A choice among fitting entries still reads "…; chosen over E7."
8. **References.** A reference to a stem with several spellings counts as a reference to each spelling. A stem whose entries all have the same formals keeps its one spelling, so existing dictionaries tokenise exactly as before.
9. **`schema_version` is 5.** It adds `evidence.entry.clauses`.

## 6. Data Model

- `application.FormalPattern(text, kind, names, tag)`, `kind` in `name`, `empty`, `cons`, `tag`.
- `application.scan_value`, `is_value`, `list_items`, `tagged_value`.
- `HeadwordSignature.patterns`, `is_patterned`, `bindings(call)`, `matches(call)`, `compatible_with(other)`.
- `demand.EntryUse.clauses: tuple[tuple[int, str], ...]`, every entry of the stem with its authored headword. `candidates` are those that fit.

## 7. Commands / API

No new commands. `VDInstance.clauses_for_call`, `Simulator.clause_indexes`. `member_list_demo.py [--steps|--json]`.

## 8. Test Contract

`test_structured_arguments.py`:

- values, malformed values, scanning, and taking lists and tags apart;
- patterns, signatures with patterns, matching, compatibility and instantiation;
- structured calls as single demands; a headword spelled inside an argument is not a demand; punctuation after an atom; references to a stem with several spellings; conflicting clauses refused;
- the form of the argument decides which definition answers; evidence lists every clause; a plain clause beside a pattern leaves a choice to the person;
- the member-list scene reproduces the hand-recorded answers (−23/10 and −24/5 m/s²), with every split and dispatch forced by form and the list as the only membership input;
- the REPL and the bridge see the same choice.

All earlier tests pass unchanged apart from two schema-number assertions and one evidence comparison. With a fixed hash seed, the engine computes the same tokens, laws and houses as before for `newton.py` and for the website's two Newton source extracts.

## 9. Provisional Decisions

Prototype choices, to be thought about later. None is settled.

1. **The syntax.** Colon for tags, brackets and commas for lists, no spaces. Chosen because none of it was legal after an underscore before, so nothing existing changes meaning.
2. **Patterns live in the headword.** One stem then has several spellings. The alternative is one spelling with the condition in the definition's prose, which a person reads and the engine cannot.
3. **Static analysis sees spellings as separate headwords.** The graph, law detection and the supported check are untouched; a reference fans out to every spelling. A law whose headword has several spellings has not been examined.
4. **The list is supplied as a call.** It enters where `contribution_p` is demanded without it. Whether membership belongs there, or behind an interaction-set wall whose result is then passed on, needs results as arguments (§10).
5. **Member tags.** `A:` and `R:` for action and reaction, and a kind tag such as `spring:` inside, are this prototype's reading of the 15 August member-named force laws.
6. **Forced choice and judged choice share one step kind.** They differ in evidence and wording only. This narrows provisional decision 4 of the 11 November segment: the forced half is now told apart; the judged half is as it was.

## 10. Open Questions

- **Results as arguments.** The engine passes text, not values. So the list is typed by a person, and the action value of one spring is supplied twice when two objects' traces both need it. The hand probe delivered one value to both.
- **Order.** The hand probe checked that every order of the list gives the same answer. Here responses are scripted, so another order has no responses to draw on.
- **Under-application with patterns.** An unsupplied position excludes nothing. Whether a clause should be offered before the argument that would rule it out exists is open.
- **Identity across spellings** in the graph and in law-houses (§9.3).
- **Law order between runs.** While checking this change against the old engine, the old engine's list of laws and houses came out in a different order from one run to the next (set iteration order). Unrelated to this segment and left alone.

## 11. For the website

- Headword strings may now contain `[`, `]`, `|`, `:` and `,`.
- `holes[].candidates` lists only the entries whose form fits the demand.
- `evidence.entry.clauses` lists every entry of the stem as `[index, headword]`; those not in `candidates` were ruled out by form.
- Accept `schema_version` 5.
