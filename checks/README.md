# Self-check answers

`expected.json` holds the stored answer for every self-check a student can run.
Its shape is pinned by `expected.schema.json`, which CI validates.

**One implementation reads this file.** `src/cwai/checks.py` compares an answer
in the notebook. The published site does not compare anything itself: it shows
the output the notebook produced when the site ran it. So a student sees the same
verdict in the notebook and on the page. This page is the specification of that
implementation. If you change the comparison, change this page and the tests.

## The comparison contract

An entry is `{"type": ..., "value": ...}`, with an optional `tolerance`.

| `type`   | `value` is                  | Compared by |
|----------|-----------------------------|-------------|
| `number` | a JSON number               | absolute difference, within `tolerance` |
| `string` | a JSON string               | exact equality |
| `list`   | a JSON array                | exact equality, in order |
| `shape`  | an array of two integers    | exact equality against the result's `(rows, columns)` |

The rules, in full:

- **`tolerance` applies to `number` only.** It is an absolute tolerance, not a
  relative one: the answer passes when `abs(found - expected) <= tolerance`.
  When an entry gives no `tolerance`, use `1e-6`. The schema **rejects**
  `tolerance` on any other type, so CI fails the day someone writes it on a
  list; do not implement a tolerance for lists, strings or shapes, because the
  Python side does not have one.
- **Lists are order-sensitive and compared exactly.** `[1, 2]` does not match
  `[2, 1]`, and no tolerance is applied to the numbers inside a list. Sort the
  list in the notebook if the order should not matter.
- **A `list` entry accepts any sequence, not one exact type.** Before comparing,
  the comparison turns anything with a `tolist()` method, and any tuple, into a
  plain list, so a tuple `(1, 2, 3)`, a numpy array and a pandas Series all match
  `[1, 2, 3]`.
- **`shape` is a two-element array**, `[rows, columns]`, and both elements must
  match exactly.
- **A `shape` entry accepts either a result carrying its own shape or a bare
  pair.** The comparison reads `value.shape` when there is one and compares
  `value` itself when there is not, so a DataFrame matches and so do a plain
  `[3, 2]` and `(3, 2)`. One edge: a numpy array *is* a pair but carries its own
  `.shape` of `(2,)`, so `np.array([3, 2])` is read as that shape and fails. Pass
  a list or a tuple.
- **Strings match including case**, and including leading and trailing spaces.
  `"Leeds"` does not match `"leeds"`.
- **Numbers and booleans are different things.** `true` is not an acceptable
  answer to a `number` check, even though Python treats `True` as `1`.
- **Nothing is coerced.** Text that looks like a number (`"42"`) does not match
  a `number` entry; it is a wrong answer, and the message says so.

## The three states of a check

A check result is in one of three states. Each has its own mark, so the states
can be told apart without colour.

| State | Mark | Meaning |
|-------|------|---------|
| right | `✓` | The answer matches. |
| wrong | `✗` | The student gave an answer and it does not match. |
| not attempted yet | `○` | The student has not answered yet. |

The third state exists because the published site runs the student notebooks with
every exercise unanswered. Those exercises must read as "not attempted yet",
never as wrong.

- **`UNATTEMPTED` is the sentinel.** It is `Ellipsis`, the value of `...`. An
  untouched answer stub holds this value. Notebooks and tests refer to it by
  name instead of writing `...`.
- **`check(name, UNATTEMPTED)` returns a result with `attempted=False`.** Its
  `passed` is `False`, so `bool(result)` is `False` and code that tests for a
  tick never counts a blank as a pass. It renders as
  `○ name: not attempted yet. Replace the ... with your answer, then run the cell again.`
  It never uses `✗` or the word "failed".
- **The name is checked first.** An unknown check name raises
  `UnknownCheckError` even when the answer is `UNATTEMPTED`, because a wrong name
  is a mistake in the course material, not a blank answer.
- **`expect_columns` and `expect_shape` return quietly for `UNATTEMPTED`.**
  `expect_shape` still raises `ValueError` when given neither `rows=` nor
  `cols=`, because that is an authoring mistake.
- **`check_slice(name, value, slice_id)` follows the same rules** for the
  per-slice handoff check. It computes the expected value from the named slice
  and metric in `cwai.slices` instead of reading `expected.json`, then uses the
  same comparison, so the same value gets the same verdict. An unknown `slice_id`
  raises `UnknownSliceError`. An unknown metric name raises `UnknownCheckError`.

## Writing an entry

Key entries by the check name the notebook passes to `check()`, which is also
what the student reads in the failure message, so make it recognisable:

```json
{
  "foundations-mean-speed": {"type": "number", "value": 31.4, "tolerance": 0.05},
  "foundations-busiest-day": {"type": "string", "value": "Friday"},
  "foundations-subset-shape": {"type": "shape", "value": [412, 16]}
}
```

Give a `tolerance` whenever the answer comes out of floating-point arithmetic
and the student's route to it may differ from yours. Leave it out when the
answer is exact, such as a count.

## What CI checks

- `expected.json` validates against `expected.schema.json`;
- every entry's `type` is one the comparator supports;
- the schema rejects an unsupported type, and rejects `tolerance` on any type
  but `number`.
