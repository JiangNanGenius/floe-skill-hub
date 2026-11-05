---
name: onboarding
description: Build a role-based onboarding plan for a new hire from supplied details - pre-start checklist, Day 1 and Week 1 schedules, access and equipment requests that stop at human approval, and 30/60/90-day goals. Guide-only; it does not provision accounts, grant access or create calendar events.
---

# Onboarding

## Floe guide adaptation (read first)

- Adapted for Floe from the Apache-2.0 upstream skill recorded in `references/PROVENANCE.md`. The pre-start checklist, Day 1 and Week 1 schedules, key-contacts table, tools-access table and 30/60/90-day goal structure are retained; the HRIS, knowledge-base and calendar connector paths and the slash-command invocation are removed.
- Bring the new hire's details as pasted text or a workspace file: name or initials, role, team, start date, manager, buddy, and the systems and equipment the role needs. No HRIS, knowledge base, chat or calendar service is connected or implied.
- The output is a workspace onboarding plan. The guide does not provision accounts, grant or request access, order equipment, or create calendar events; every access and equipment line is a request a named human approves and actioned outside the guide.
- Repository attention and repository-wide commit activity are not evidence about this skill's content freshness. The upstream path history is recorded in `references/PROVENANCE.md`; the content has been stable since 2026-03-13 and no fresher claim is made.

**Important**: Onboarding plans handle personal data and access decisions. Access grants follow the organization's approval policy and are executed by IT or the system owner; this guide only lists what to request, who approves, and what cannot be decided here.

## Input contract

Provide, or state that a value is missing:

| Input | Why it is needed |
| --- | --- |
| New hire name (or initials in shared copies) and role | Anchors the plan; role drives the checklists |
| Team and start date | Dates the pre-start and Day 1 sections |
| Manager and onboarding buddy | Named owners for the human steps; do not invent them |
| Systems and tools the role needs, with required access level | Feeds the access table; each row needs a named approver |
| Equipment needs (laptop, monitor, peripherals) | Feeds the equipment requests; ordering stays with procurement/IT |
| Relevant SOPs, compliance training and key documents | Feeds Week 1 reading; without them the list is UNKNOWN |
| Working pattern and time zone | Schedules Day 1 sensibly; without it times are local/UNKNOWN |
| 30/60/90 expectations from the manager | Seeds the goals sections; otherwise drafted as proposals |

If an input is absent, write **UNKNOWN** and say what it would change. Never invent a buddy, an approver, a training assignment or a goal; propose them and mark the owner who must confirm.

## Privacy and evidence rules

1. Use initials or the form of name the organization approves for circulated plans; full legal names are not needed for a checklist.
2. Access levels come from the role's supplied needs, not from copying an existing employee's access (that can over-grant).
3. Separate facts (start date, role) from proposals (buddy suggestion, first task) and mark proposals as proposals.
4. Never claim an account was created, access granted, equipment ordered or a meeting scheduled. Every such line is a request with a named approver.
5. Keep government identifiers, addresses and personal documents out of the plan; reference where they are handled (HR process), not their values.

## Step 1 - Confirm the role profile

Restate role, team, start date, manager and buddy from the input. If the buddy or manager is missing, propose how to choose one and mark it **proposal - owner must confirm**.

## Step 2 - Pre-start checklist (all before Day 1)

- [ ] Welcome note with start date, time and logistics (owner: manager)
- [ ] Access requests submitted for the role's systems (owner: IT/system owner per the access table)
- [ ] Equipment ordered (owner: procurement/IT)
- [ ] Added to team calendar and recurring meetings (owner: manager or team coordinator)
- [ ] Buddy assigned (owner: manager)
- [ ] Workspace or remote setup instructions prepared (owner: IT/facilities)
- [ ] Compliance training scheduled (owner: HR)

Every checklist item names its human owner; nothing is marked automatic.

## Step 3 - Access and equipment table

| System / item | Access level needed | Requested by | Approver (named human) | Status |
| --- | --- | --- | --- | --- |
| [from the role's supplied list] | [least privilege for the role] | Manager | System owner / IT lead | to request |

Access rules:

- Least privilege per role; "same as person X" is not an access level.
- Production data, admin/superuser and payment-related access each need an explicit approver role; when no approver is supplied, the row is **blocked - approver UNKNOWN**.
- Approval and provisioning happen in the organization's process; the guide does not submit, escalate or remind.

## Step 4 - Day 1 schedule

| Time | Activity | With |
| --- | --- | --- |
| 9:00 | Welcome and orientation | Manager |
| 10:00 | IT setup and tool walkthrough | IT / buddy |
| 11:00 | Team introductions | Team |
| 12:00 | Welcome lunch | Manager + team |
| 13:30 | Company overview and values | Manager |
| 15:00 | Role expectations and 30/60/90 plan | Manager |
| 16:00 | Free time to explore tools and docs | Self |

Adjust times to the supplied working pattern and time zone; mark the schedule **local time** when the time zone is unknown.

## Step 5 - Week 1, 30/60/90 and key contacts

- **Week 1:** complete required compliance training; read the key documents supplied for the role; 1:1 with each team member; shadow key meetings; first small task or project; end-of-week check-in with manager.
- **30-day goals:** 2-3 goals aligned to the role, marked as manager-supplied or proposed.
- **60-day goals:** 2 goals.
- **90-day goals:** 2 goals.
- **Key contacts:** manager, buddy, IT contact, HR contact - roles with the names the input supplied, never invented.

## Floe output contract

A synthetic example is in [`assets/examples/input.md`](assets/examples/input.md), its machine-readable facts are in [`assets/examples/figures.json`](assets/examples/figures.json), and the expected output shape is in [`assets/examples/expected-output.md`](assets/examples/expected-output.md). They are synthetic examples, not executed results.

Produce these sections in order:

1. **Plan header** - new hire reference, role, team, start date, manager, buddy.
2. **Pre-start checklist** - every item with a named human owner.
3. **Access and equipment table** - least-privilege levels, named approvers, blocked rows with the missing approver.
4. **Day 1 schedule** - time-zone labeled.
5. **Week 1 plan.**
6. **30/60/90-day goals** - marked supplied or proposed.
7. **Key contacts table.**
8. **Open items for humans** - what must be confirmed, requested or ordered, and by whom.
9. **Claim boundary** - what the plan does not do.

If a section cannot be completed from the input, write it with **UNKNOWN** and the missing input. Do not omit the section.

## Quality checks before returning

- Every access row has a named approver or is blocked with the missing approver named.
- No account, grant, order or calendar event is claimed as done.
- Buddy, approvers and goals are supplied or marked proposals - none invented.
- Personal data is minimized; no identifiers or document values appear.
- The schedule states its time-zone basis.

## Scope and limitations

- Works only from user-supplied details; it does not connect to an HRIS, knowledge base, chat or calendar.
- Does not provision accounts, grant or request access, order equipment, schedule meetings or send welcome notes.
- Does not set compensation, determine benefits, run background checks or make hiring decisions.
- Access decisions belong to the named approvers and the organization's policy; the guide lists requests only.
- Synthetic examples use invented people and teams. No real personal data is included.
