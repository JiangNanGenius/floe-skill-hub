# Output - K-12 Check for Understanding (Floe guide adaptation)

Read in full before writing (SKILL.md, Step 5).

This adaptation keeps the two-document discipline of the upstream skill but uses task-workspace Markdown instead of platform-specific HTML artifact files. The upstream HTML templates and CSS are not shipped; the rules that make the two documents safe to hand out are preserved. The retained math guidance uses the same Markdown figure text description specified here.

---

## The two documents

Every check produces **two separate self-contained Markdown files** - never one combined file.

- **`cfu_[topic-slug]_student.md`** - item prompts and answer choices (or response space for constructed response), a name/date line, nothing else. No meta block, no correct-answer marker, no source label, no next-step language.
- **`cfu_[topic-slug]_teacher.md`** - meta block, focus and progression callouts, each item repeated in full, the correct answer, the interpretation guide, the what-to-look-for summary.

`[topic-slug]` is a few lowercase hyphenated words: `equivalent-fractions`. **Item text is identical across the two files** - same prompts, choices and order, figures included. Write it once and reuse it; that is what makes the student file safe to hand over unredacted.

---

## Writing the files

Write both into the task workspace. Then read them back and confirm both are present and non-trivial. If the conversation has a native document or slide tool, the same content may also be rendered with it; the Markdown files remain the source of truth.

When a figure is needed, use a short text description instead of a platform-specific image component unless the native document tool supports accessible images. In Markdown, put the description in italics immediately after the prompt and repeat the same description in both files. The description must:

- name the structure in the terms the item is read in - "4 groups of 3 dots each", not "dice";
- add what a student needs to work the item from that text alone;
- leave the item's work undone - do not name the property the question asks the student to find (the count, position, identity or comparison);
- state only what the picture carries; a comparison needs both things described.

Where the answer depends on a property only a figure carries, the stem must name that property too.

---

## No provenance or process talk

Neither file says where anything came from: no `KG` or `Training` badge, no source column, no badge in the meta block or on a callout, and no note that a lookup returned nothing. An empty progression result is a fact about the retrieval, not about the mathematics, so the guide states the prerequisite and next-step routing it does have and says nothing about the rest. Retrieved data still shapes every row; the file stops narrating it. Third-party names stay out under SKILL.md's data-use guardrail.

Both files also read as though the check simply exists. `Confirmed with teacher`, `by teacher request`, `as you asked`, and any badge holding them are the conversation showing through the artifact - as is any trace of the checks you ran before delivering. Write the focus as a fact about the mathematics - *"Two components: identifying coin values, and adding a mixed set of coins"*.

---

## Student-facing template

```markdown
# [Topic/Concept]

Name: ______________________    Date: ______________

## Item 1

[Prompt text - identical to the teacher file. Where the answer turns on a property only the
description shows, this names that property.]

*[Text description of the figure, if any. Leave the item's work undone.]*

A. [Choice A]
B. [Choice B]
C. [Choice C]
D. [Choice D]
```

For a constructed-response item, replace the choices with a few blank response lines.

---

## Teacher-facing template

```markdown
# [Topic/Concept] - Teacher Guide

| Field | Value |
|---|---|
| Grade | [grade] |
| Standard | [standard as provided or inferred] |
| Focus | [learning component, stated as a fact about the mathematics] |
| Item count | [1-3] |
| Format | [multiple choice / constructed response] |

## Focus and progression

[One short paragraph. State the prerequisite and the next-step routing. Do not narrate the retrieval.]

## Item 1

[Full item text, identical to the student file.]

**Correct answer:** [choice]

**Interpretation guide**

| Response | What it suggests | Next step |
|---|---|---|
| A | [specific misconception] | [specific next instructional move] |
| B | [specific misconception] | [specific next instructional move] |
| C | [correct] | [proceed / extend] |
| D | [specific misconception] | [specific next instructional move] |

## What to look for

[Short summary of the response patterns and the decision rule.]

---

*The standard, progression, and common errors here reflect general best practice.*
```

Include the footer only when the Learning Commons KG connector was not used. Never include a
provenance badge or a statement that a connector was unavailable.

---

## Verification

Run `references/verification.md` on the written files, not on your intended design. Fix, rewrite,
and re-run anything changed before showing either file to the teacher.
