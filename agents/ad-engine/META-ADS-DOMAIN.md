# Meta Ads Domain Playbook

## Purpose

This file gives the ad-engine domain-specific Facebook and Instagram Ads judgment.
It should be loaded before generating concepts, copy, or deployment objects for Meta.

## Platform Truth

- Meta is not just a copy channel. Creative, offer framing, and landing-page alignment determine delivery quality.
- The ad object model matters: Campaign -> Ad Set -> Ad Creative -> Ad.
- Preserve IDs, status, and experiment lineage so winners can be scaled and losers can be killed without ambiguity.
- If fidelity matters, keep at least one control ad where the creative is intentionally fixed and easy to compare.

## What Good Meta Testing Looks Like

- Test a small number of clearly different concepts, not tiny wording tweaks first.
- Hold the audience and offer steady while testing concept or hook changes.
- Name assets and experiments so concept, angle, and status are obvious from IDs alone.
- Launch new assets paused when possible, review, then activate deliberately.
- Favor clean experiment design over dumping too many ads into one learning phase.

## Required Meta Skills

- Ad Library reconnaissance: inspect live competitors, collect hook patterns, creative formats, proof devices, and offer structures before generating fresh concepts.
- Objective selection: choose among traffic, leads, messaging, calling, or sales based on the actual downstream action we want.
- Campaign architecture: structure campaign, ad set, creative, and ad objects so testing is interpretable and winners are easy to scale.
- Creative diversification: vary concept, proof style, and format instead of making trivial copy edits.
- Placement awareness: adapt assets for feed, story, reels, and other placements without breaking the hook.
- Lead-path design: decide when the ad should send people to site, instant form, calling, or messaging.
- Policy and review discipline: inspect special-ad-category risk, ad-quality risk, and creative-policy risk before launch.
- Delivery interpretation: read CTR, CPC, lead quality, and delivery signals together instead of overreacting to one metric.
- Scale and kill logic: preserve winners, cut weak concepts, and avoid resetting learning unnecessarily.

## Core Creative Heuristics

- The first line must stop the scroll. Hooks should feel expensive to ignore.
- One strong claim plus one proof element beats a long explanation.
- Native-feeling, operator-authentic creative usually beats polished SaaS stock energy for this audience.
- The visual must support the hook, not repeat it word-for-word.
- Keep one main idea per ad. If the ad is about seller signals, do not also try to sell every other feature.
- If audio is used, it is proof of natural outbound follow-up, not the entire brand identity.

## Copy Heuristics For AgentRVM

- Lead with seller-signal intelligence, speed to first outreach, callback quality, and team leverage.
- Use voicemail as proof of action, not as the whole product category.
- Make reacting too late feel expensive.
- Favor concrete language: seller signal, callback, first outreach, competitor, margin, dialing blind.
- Avoid vague language: platform, solution, smarter teams, innovative AI, seamless workflow.
- Avoid false product framing: AgentRVM does not answer inbound calls and is not an answering service.

## Real Estate / Housing Review

- Meta applies special restrictions to ads related to housing, employment, credit, and social issues.
- AgentRVM sells software to real estate wholesalers, not housing inventory directly.
- Still, real-estate language can trigger extra review. Before launch, inspect the ad and landing page for wording that could make the offer look like housing inventory, brokerage, mortgage, or rental promotion.
- When in doubt, review the latest special-ad-category guidance before launch.

## Creative Formats To Prioritize

- Static image control ads for fast concept testing.
- Audio-first proof ads once the voicemail sample is strong enough to carry the claim.
- Multiple aspect ratios matter; keep square, feed, and vertical adaptations in mind.
- Preserve negative space so platform crops and expansions do not destroy the message.

## Metrics That Matter

- Creative quality metrics: thumb-stop strength, CTR, outbound click quality, hook clarity.
- Funnel metrics: landing-page view rate, lead quality, cost per lead, qualified callback rate.
- Business metrics: demos booked, revenue influence, time-to-first-response advantage.
- Do not optimize only for cheap clicks if the lead quality is poor.

## Operating Guardrails

- Keep a control variant with minimal automated mutation so the agent can compare its own creative against platform-assisted variants.
- Log every concept, headline, primary text, proof device, and audience pairing.
- Kill weak concepts fast, but do not confuse low spend with no potential if delivery never stabilized.
- Reuse winning structures, not just winning words.

## Sources To Ingest

- Meta Marketing API: https://developers.facebook.com/docs/marketing-apis/
- Meta Ad Library: https://www.facebook.com/ads/library/
- Meta Advantage+ Creative: https://www.facebook.com/business/ads/meta-advantage-plus/creative
- Meta Creative Strategy: https://www.facebook.com/business/ads/ad-creative
- Meta Advertising Standards: https://transparency.fb.com/policies/ad-standards/
