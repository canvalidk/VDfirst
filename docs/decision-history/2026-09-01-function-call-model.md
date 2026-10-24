# Function-Call Model Decision History

- Date: 2026-09-01
- Status: Records the decisions implemented on `codex/parameterized-headwords`
- Related spec: [Parameterized headwords](../../specs/2026-09-01-vd-parameterized-headwords.md)
- Implementation checkpoint: `6da2e21`

## Purpose

This document preserves the questions that produced the current VD
function-call model. It records the answer given at the time, what that answer
means, and the places where we deliberately chose a replaceable shortcut.

The discussion began by separating three operations that had been conflated:

- **Expansion** selects a dictionary entry.
- **Beta-like instantiation** supplies values to its formal parameters and
  constructs a residual.
- **R-reduction** records a person's response to that residual.

VD currently assumes no primitive delta-reduction layer. Instantiation
constructs symbols; it does not give them built-in arithmetic, physical, or
philosophical meaning.

## Chronological Questions and Answers

### 1. Is argument substitution the mechanical reduction, leaving human reduction only for operations the evaluator cannot execute?

**Question.** I initially asked whether binding arguments into a definiens
should be the mechanical reduction, while a human handled residual operations
the evaluator could not calculate.

**Answer.** This imported a primitive-computation model that VD deliberately
withholds. Beta-like substitution may mechanically construct the residual,
but there is no assumed primitive delta step that determines what the residual
means. R-reduction is an observed human response, not a fallback calculation
or a certified equivalent rewrite.

**Result.** The model became:

```text
parameterized entry + actuals
    -> beta-like instantiation
    -> residual stimulus
    -> R one observed response
```

### 2. Should reduction be classified by the transformation or by whether a machine or a human performed it?

**Question.** While trying to distinguish delta-reduction from R-reduction, I
asked whether the label should depend on the mathematical kind of
transformation or on the actor performing it.

**Answer.** The answer came as a stronger correction: remove primitive delta
from the current VD model entirely. The central distinction is not
machine-versus-human execution. Beta-like instantiation structurally builds a
residual; R records the effect that residual has on a person.

**Result.** `3 add 5` has no built-in VD result. A surrounding instruction can
change the distribution of human responses and therefore participate in the
effective symbol. Calling R-reduction “human-certified equivalence” is
incorrect.

### 3. Does one trace contain one encounter, with probabilities inferred later?

**Question.** Should each trace record the particular response produced by one
human encounter, with probabilities inferred across accumulated traces?

**Answer.** Yes. Each trace is aimed at one person. Probabilities are inferred
over multiple encounters rather than stored as the result of one trace.

**Result.** A trace stores an event, not a probability distribution. Later
analysis may estimate something like:

```text
P(response | residual, person or population, context)
```

For the present simplified protocol, results are conditioned on the response
being accepted as admissible.

### 4. If an R-response contains a dictionary headword, should it be analyzed again?

**Question.** Should a headword appearing in an observed R-response create new
demands, or should the response remain inert?

**Answer.** It should remain inert. This was chosen for ease and simplicity
while experimental testing is still distant.

**Result.** R-responses are terminal observed text. The current headword guard
is treated as an admissibility filter, and the working experimental quantity
is conditional on acceptable input. Richer encounter recording is deferred.

### 5. What marks a bound input slot inside a definiens?

**Question.** How should the evaluator distinguish a formal input from
ordinary residual prose or a dictionary headword?

**Answer.** The example supplied the syntax:

```text
inertial-acceleration_t := derivative of velocity at time t
```

The suffix `_t` declares the formal parameter `t`. The same formal appears as
a replaceable atom in the definition body.

**Result.** An authored entry headword is parsed as a signature: the text
before the first underscore is its stem, and later underscore segments are its
ordered formals.

### 6. What do bare, formal-valued, and concrete-valued calls mean?

**Question.** The supplied example implicitly raised whether all of these
forms should resolve through one entry:

```text
inertial-acceleration
inertial-acceleration_t
inertial-acceleration_3
inertial-acceleration_T
```

**Answer.** Yes. The bare call and the call supplying the formal's own spelling
both leave `t` visible. Concrete or symbolic actuals replace it while
preserving their spelling and case.

**Result.** The agreed expansions are:

```text
inertial-acceleration    -> derivative of velocity at time t
inertial-acceleration_t  -> derivative of velocity at time t
inertial-acceleration_3  -> derivative of velocity at time 3
inertial-acceleration_T  -> derivative of velocity at time T
```

### 7. Are multiple arguments positional from left to right?

**Question.** Should `force_p_t` accept `force_Earth_3` by binding `p = Earth`
and `t = 3`?

**Answer.** Yes.

**Result.** Formal and actual lists are ordered. Actual number `i` binds formal
number `i`; names do not participate in matching after the signature is
declared.

### 8. Is the model curried lambda application or one positional application?

**Question.** I asked whether a two-input function should be understood as one
fixed two-slot application or as two successive unary beta-reductions.

**Answer.** This was not answered immediately. The later decisions resolved
it operationally: one headword call carries an ordered list of supplied
actuals, and one expansion performs one flat instantiation pass. A partially
supplied result is not a closure that can later receive another argument.

**Result.** The current implementation is lambda-like substitution, but not a
curried or higher-order lambda evaluator.

### 9. Which occurrences of a formal are replaceable?

**Question.** Should every standalone `t` be replaced while a `t` inside an
ordinary larger token such as `state` remains untouched?

**Answer.** Yes.

**Result.** Substitution is token-aware rather than substring replacement.
The discussion later refined this to include whole underscore argument
segments as replaceable positions.

### 10. Are underscores always arguments, or can static underscore qualifiers coexist with calls?

**Question.** The existing Token Prop 3 guide treated underscores as glue for
static qualifiers. I asked whether every underscore suffix should instead be
an argument list, or whether both meanings should coexist under a
disambiguation rule.

**Answer.** Every underscore suffix is an argument list.

**Result.** `_` has one function in the current language. For example:

```text
canonical-force_acting-object
```

means a call/signature with stem `canonical-force` and one positional value or
formal, `acting-object`. This supersedes the static-qualifier part of Token
Prop 3.

### 11. Is under-application allowed?

**Question.** Given `force_p_t`, should `EXPAND force_Earth` substitute the
first actual and leave `t`, or remain inert until both actuals are supplied?

**Answer.** It should substitute `Earth` for `p` and leave `t` unchanged.

**Result.** Any prefix of the formal list may be supplied:

```text
force          -> p and t unchanged
force_Earth    -> p := Earth; t unchanged
force_Earth_3  -> p := Earth; t := 3
```

We call this **partial instantiation**, not lambda-calculus partial
application, because it produces an ordinary residual rather than a closure.

### 12. What happens on over-application?

**Question.** If `force` declares `[p, t]`, should
`force_Earth_3_extra` remain an unmatched inert token, or should expansion use
the first two values and retain `extra` somehow?

**Answer.** Report an error and ignore the operation for now.

**Result.** Over-application performs no expansion and no trace mutation. The
meaning of extra arguments is explicitly deferred.

### 13. Can one stem have multiple arities or formal lists?

**Question.** Must every entry for `force` declare one shared signature, or
may `force_p` and `force_p_t` be different parameterized headwords?

**Initial answer.** Arity belongs to the base, and `force_p` is a different
headword from `force_p_t`. We interpreted this as arity-indexed identities,
approximately `force/1` and `force/2`.

**Problem discovered.** If both exist, bare `EXPAND force` does not reveal
which arity was intended.

**Final answer.** The initial answer was withdrawn in favor of the least
damaging, easiest-to-replace band-aid: do not support signature or arity
overloading yet.

**Result.** One stem has one ordered formal list. Its first definition
establishes that list, and later entries for the stem must repeat it exactly.
A conflicting declaration is a definition/import error.

### 14. What is the temporary grammar for actual values?

**Question.** Should every actual currently be one atomic
underscore-separated token, with hyphens permitted inside it but no spaces or
nested residual expressions?

**Answer.** Yes.

**Result.** These are within the current grammar:

```text
force_Earth_3
velocity_reference-frame_t
```

An underscore always begins another argument. An actual cannot itself contain
an underscore, a space, or a nested expression yet.

### 15. Does tokenization happen before or after instantiation?

**Question.** Should expansion instantiate the definition first and then run
the ordinary tokenizer, so an inserted known headword becomes a demand without
being automatically expanded?

**Answer.** Yes.

**Result.** For a known headword `kinetic-time`:

```text
EXPAND inertial-acceleration_kinetic-time
-> derivative of velocity at time {kinetic-time}
```

The new demand participates in the ordinary lazy trace. Instantiation never
interprets or eagerly evaluates the inserted value.

### 16. Are formals replaceable inside the argument positions of other calls?

**Question.** Should a formal count as replaceable both as standalone prose
and as one complete argument segment in a nested call, while remaining
untouched inside a hyphen-glued ordinary atom?

**Answer.** Yes.

**Result.** For:

```text
force_p_t := inertial-mass_p multiply inertial-acceleration_p_t
```

the complete call produces:

```text
force_Earth_3
-> inertial-mass_Earth multiply inertial-acceleration_Earth_3
```

But `p` is not replaced inside ordinary atomic text such as `state-p` or
`particle`.

### 17. Is substitution simultaneous or a sequence of text replacements?

**Question.** For `pair_x_y := x followed-by y`, should `pair_y_Z` produce
`y followed-by Z`, without the inserted `y` later being replaced as though it
were the second formal?

**Answer.** The question prompted a comparison with lambda calculus. Ordinary
curried lambda calculus reduces one application at a time, but it uses
capture-avoiding substitution and alpha-renaming. It does not perform naïve
cascading textual replacement. Multi-argument notation can use simultaneous
substitution and reach the same fully applied result.

**Result.** Actuals supplied by one VD call are substituted simultaneously.
Inserted actual text is not scanned again as a formal during the same pass:

```text
pair_y_Z -> y followed-by Z
```

### 18. Should partial instantiation preserve hidden binder identity and alpha-rename collisions?

**Question.** If a supplied actual has the same spelling as an unsupplied
formal, should VD preserve their hidden distinction as lambda calculus would,
or flatten them into one visible symbol?

**Answer.** There was no motivating example yet, so another replaceable
band-aid was requested. We chose flat semantics: no hidden binder, no closure,
and no alpha-renaming.

**Result.** All supplied bindings are applied simultaneously; unsupplied
formals remain visible; the result then becomes an ordinary residual:

```text
pair_A_B -> A followed-by B
pair_A   -> A followed-by y
pair_y   -> y followed-by y
```

The last line intentionally loses the distinction between the supplied `y`
and the still-formal `y`.

## Band-Aids and Deferred Alternatives

This section is the explicit return list. These choices were made to let the
prototype proceed without pretending that the underlying theoretical question
had been settled.

### A. One signature per stem

**Problem.** Arity-indexed headwords allow both `force/1` and `force/2`, but a
bare call `force` supplies no information with which to choose.

**Options considered.**

1. Treat `force_p` and `force_p_t` as distinct arity-indexed headwords.
2. If both exist, make bare `force` offer entries from every arity.
3. If both exist, reject bare `force` as ambiguous.
4. Temporarily permit only one signature per stem.

**Chosen band-aid.** Option 4. The first entry establishes both the arity and
the exact ordered formal list. Conflicting entries are rejected.

**Why it is replaceable.** The implementation keeps `stem`, `formals`, and
`actuals` separate. Overloading can later be added in the resolver without
changing how a selected signature is instantiated.

**Come back when.** Revisit this when a real dictionary needs two signatures
with the same stem, or when a principled meaning for bare calls under
overloading becomes clear. Also revisit whether consistency should require the
same formal names or merely the same arity.

### B. Atomic actual values only

**Problem.** `_` is currently both the visible separator and the complete
argument grammar. Rich expressions would make boundaries ambiguous.

**Options considered.**

1. Permit only one atomic value per underscore segment.
2. Add quoting or bracketing for actuals containing spaces or underscores.
3. Parse nested calls or arbitrary residual expressions as arguments.

**Chosen band-aid.** Option 1. Letters, digits, and internal hyphens are
accepted; spaces, embedded underscores, and nested expressions are not.

**Why it is replaceable.** Calls are represented structurally after parsing,
so a future surface parser can produce the same `stem + actuals` structure.

**Come back when.** Revisit this when a needed actual cannot be represented by
one atomic symbol, especially when functions themselves or compound residuals
must be passed as values.

### C. Hard error on over-application

**Problem.** The current model has no agreed interpretation for actuals beyond
the declared arity.

**Options considered.**

1. Leave the entire over-applied spelling inert and unmatched.
2. Consume the declared prefix and preserve the extra suffix somehow.
3. Report an error and perform no operation.

**Chosen band-aid.** Option 3.

**Why it is replaceable.** Arity checking is isolated in call resolution. No
trace state is created before the check succeeds.

**Come back when.** Revisit this if calls become left-associated, return other
callables, or otherwise acquire a meaningful continuation for extra actuals.

### D. Flat simultaneous instantiation without binders

**Problem.** Partial instantiation can make an inserted actual and an
unsupplied formal share the same visible spelling. True lambda semantics would
preserve their binding distinction.

**Options considered.**

1. Naïve sequential text replacement. This was rejected because inserted
   actuals can be replaced again, producing cascading errors such as a
   `Z Z`-like result.
2. Lambda-style capture-avoiding substitution with alpha-renaming.
3. Preserve hidden binders or closures so partial results retain formal
   identity and can receive later arguments.
4. Perform one simultaneous token-aware substitution, leave missing formals
   visibly unchanged, and then flatten the result into an ordinary residual.

**Chosen band-aid.** Option 4.

**Why it was preferred.** Alpha-renaming would introduce arbitrary fresh
visible symbols. In VD, changing a symbol may itself change its experimental
effect. Hidden binders and closures would add a semantic layer for which there
is not yet a motivating use case.

**Known debt.** `pair_y` renders as `y followed-by y`; the system cannot later
distinguish which `y` was supplied and which was formerly a formal. Nor can the
result later receive the missing argument.

**Why it is replaceable.** The operation is isolated as structured
instantiation rather than scattered string replacement.

**Come back when.** Revisit this as soon as VD needs continued application,
higher-order values, lexical binding, or an example where the lost distinction
changes later behavior.

### E. Simplified R-response protocol

**Problem.** A real experiment may need to retain rejected, empty, malformed,
or headword-containing responses as observations, along with the precise
stimulus and encounter context.

**Options considered.**

1. Re-tokenize an R-response and create new demands.
2. Preserve every response as inert observed output and build a richer event
   dataset.
3. For the early simulator, keep R-output inert and analyze only responses
   passing the current admissibility filter.

**Chosen temporary simplification.** Option 3. Treat reported experimental
results as conditional on acceptable input.

**Known debt.** The current model does not yet represent the full sampling and
rejection process. That conditioning could bias later probability estimates if
it were mistaken for the final experimental protocol.

**Come back when.** Revisit this before experimental use. At that point, record
the exact residual shown, exact raw response, acceptance/rejection outcome,
person/session, trace address, context, and timestamp for every encounter.

## Decisions That Are Not Currently Band-Aids

The following were treated as positive working commitments rather than merely
temporary patches:

- VD assumes no primitive delta-reduction layer.
- Beta-like instantiation constructs a residual but does not interpret it.
- One trace represents one person's encounter; distributions arise across
  encounters.
- Multiple supplied actuals bind positionally from left to right.
- Substitution respects token and argument-segment boundaries.
- Instantiation precedes ordinary lazy tokenization.
- Every underscore suffix currently denotes arguments, not static qualifiers.
