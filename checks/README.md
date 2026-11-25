# Self-check answers

`expected.json` holds the stored answer for every self-check a student can run.
Its shape is pinned by `expected.schema.json`, which CI validates.

**Two implementations read this file.** `src/cwai/checks.py` compares an answer
in the notebook; the site's JavaScript will compare the same answer on the
published page. They must reach the same verdict on the same entry, because a
student who sees the notebook say "wrong" and the site say "right" has learnt
nothing except that the course cannot be trusted. This page is the contract both
must implement. If you change one side, change this page and the other side.

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
- **`shape` is a two-element array**, `[rows, columns]`, and is compared against
  the result's own shape. Both elements must match exactly.
- **Strings match including case**, and including leading and trailing spaces.
  `"Leeds"` does not match `"leeds"`.
- **Numbers and booleans are different things.** `true` is not an acceptable
  answer to a `number` check, even though Python treats `True` as `1`.
- **Nothing is coerced.** Text that looks like a number (`"42"`) does not match
  a `number` entry; it is a wrong answer, and the message says so.

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
