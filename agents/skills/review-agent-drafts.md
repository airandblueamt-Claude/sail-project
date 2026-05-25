---
title: Review agent-drafted GPU requests
use_when: A reviewer (admin / manager / technician) asks "what's in
          the queue", "any pending drafts", "what did the AI draft",
          "show me agent requests", or similar.
audience: reviewers only — silently fall back to a general status
          summary if the user role is `employee`.
---

## Steps

1. **List the queue.** Call:

       find_gpu_requests(source='agent', status='open')

   That returns the agent-drafted requests still waiting on a human
   decision. If `count == 0`, tell the reviewer the inbox is empty
   and stop here.

2. **Surface confidence.** Each row carries an `agent_confidence`
   between 0 and 1. Sort the reply so low-confidence drafts are
   flagged first — those need the most human judgement. Quote the
   confidence as a percentage.

3. **Drill into one** when the reviewer asks. Use:

       get_gpu_request(request_number='GPU-YYYY-NNNN')

   That returns the full structured payload: VM groups, GPU options,
   workloads, phases, contributions, networking/access fields,
   document metadata, and any linked tickets.

4. **Highlight the source doc.** Drafts have a `document` field block
   (in `fields.document`) holding the original source's title /
   date / prepared_by / email_from / classification. Mention it so
   the reviewer knows what to check against.

5. **Point them at the review URL** to actually approve or reject:
   `/gpu/requests/<NUMBER>`. The page has a "Record response" form
   with decision (`approved` / `approved_with_conditions` /
   `rejected`), fit notes, allocated asset tags, response notes.

## Don'ts

- Don't approve or reject anything yourself — read-only.
- Don't paraphrase the extraction. If the reviewer asks "what does
  it say about networking", quote the actual `fields.networking`
  values returned by the tool, not your guess.
- Don't summarise more than 5 drafts in one reply — link the rest
  via `/gpu/requests/?source=agent` instead of dumping them.

## Quick reply template

> {N} agent-drafted requests pending review (lowest confidence first):
>
> - **GPU-2026-0001** · *new_infra* · OrbitronAI BYOC — `92%`
> - **GPU-2026-0003** · *compute_partnership* · ThakaaMed — `78%`
>
> Open any of them at `/gpu/requests/<NUM>` to review. Tell me which
> one you want me to summarise.
