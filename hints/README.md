# Writing hints

Every exercise in a notebook has hints. This page is for whoever writes them.

## Why there are three tiers

A student working alone at 22:00, with nobody to ask, needs to be able to get
unstuck. Answers are deliberately open: a student who cannot check their work
against a known truth cannot learn alone. So the tiers are not a lock. They exist
so that the *smallest useful* help is easy to find, before a student reaches for
the whole answer. All three tiers are always available.

Because the answer is always reachable, an exercise that only asks a student to
"write code that produces X" teaches little. Design exercises around reading,
predicting, spotting what is wrong or explaining why. Hints then help a student
over the step they are stuck on, not hand them the exercise.

## The tiers

| Tier | Says | Contains code? |
|------|------|----------------|
| `nudge` | what to look at | no |
| `method` | the approach, in prose | no |
| `code` | the worked answer | yes |

- **nudge**: points attention, and nothing more. "Look at what type the column
  has after you read the file." It answers "where do I look?", not "what do I do?".
  A student who only needed to notice something should be done after reading it.
- **method**: describes the approach in plain sentences. "Filter to the rows from
  July, then take the mean of the speed column." No code, not even a function
  name in backticks if you can avoid it; the student should still have to turn
  the description into code.
- **code**: the worked answer, with enough explanation that the student can read
  it rather than copy it. Optional, but write it: a student who reaches the end
  of the tiers should find a complete, correct answer to compare against.

Write the nudge first. If you find it gives the approach away, it is really a
method; if the method needs code to make sense, the exercise is probably too big
and should be split.

## File layout

One file per stage, named after the stage directory: `notebooks/01-foundations/`
is covered by `hints/01-foundations.yml`. Entries are keyed by exercise id:

```yaml
foundations-mean-speed:
  nudge: Look at which column holds the speeds, and what its values are measured in.
  method: Select the speed column, then average it. Check the result against the
    values you can see in the first few rows.
  code: |
    mean_speed = df["speed_kph"].mean()
```

## Linking exercises to hints

Mark the exercise cell with the tag `exercise` and give it an id in its cell
metadata:

```json
{ "tags": ["exercise"], "cwai": { "id": "foundations-mean-speed" } }
```

The worked solution for the exercise goes in a separate cell tagged `solution`,
with its source wrapped in a `CWAI-SOLUTION` comment marker. The student
notebooks are generated from the full ones by
`scripts/build_student_notebooks.py`, which replaces every solution cell with a
stub; never edit the generated copies in `student/`.

Ids must be unique within a notebook, and should stay stable once released.

## What CI checks

- every exercise has a non-blank `nudge` and `method`;
- no tier other than `nudge`, `method` and `code` appears for an exercise;
- the committed student notebooks match what the builder produces from the full ones.
