# Ad Creative Engine — Agent Brain

## Core Insights

### Canonical Product Truth
- **What AgentRVM Actually Does**: Detects seller intent signals, prioritizes likely opportunities, and triggers fast natural outbound follow-up before slower competitors react
- **What It Does NOT Do**: It is not an answering service, it does not answer inbound calls, and it is not sold as a per-voicemail commodity
- **Winning Message**: Seller-signal intelligence plus speed to first outreach beats manual dialing and generic call workflows

### Meta Skill Stack
- **Ad Library Reconnaissance**: Study live competitor hooks, proof devices, formats, and angles before generating fresh concepts
- **Campaign Architecture**: Preserve clear Campaign -> Ad Set -> Ad Creative -> Ad lineage so testing and scaling stay interpretable
- **Objective Selection**: Match traffic, leads, messaging, or sales objectives to the actual next step we want from wholesalers
- **Creative Diversification**: Test distinct concepts first, not tiny wording edits
- **Policy Review**: Watch for housing-category and real-estate review risk before launch
- **Delivery Interpretation**: Judge CTR, click quality, lead quality, and callback potential together

### Audience Psychology (Wholesalers)
- **Pain**: Dialing blind is slow, expensive, and reactive; the real cost is reaching the seller after a faster competitor already did
- **Desire**: Know which signals matter first, trigger outreach instantly, and spend more rep time on live opportunities
- **Proof Point**: Better timing and natural outbound follow-up should lead to better callbacks
- **Decision Trigger**: "We are too late because we are still guessing" is stronger than "AI is cheap"

### Copy Angles Ranked by Expected Performance

1. **Pain of Reacting Too Late** — "Late outreach costs margin."
   - Psychology: Lost deals feel expensive and immediate
   - Why Strong: Makes timing failure concrete instead of abstract

2. **Competitive FOMO** — "First signal. First outreach."
   - Psychology: Winning depends on moving first
   - Why Strong: Frames speed as the advantage, not generic automation

3. **Callback Proof** — "The callback proves the data."
   - Psychology: Performance proof lowers skepticism
   - Why Strong: Connects signal detection to real-world response

4. **Data Advantage** — "Stop dialing blind. Start with seller intent."
   - Psychology: Operator-minded buyers want better input quality
   - Why Strong: Positions AgentRVM as a data layer, not another dialer

5. **Margin Leverage** — "One signal can become a callback."
   - Psychology: One good opportunity can justify the system
   - Why Strong: Economics support the story without turning into cheapness messaging

## Brand Foundation

### Colors
- `#FF8800` (orange) — audio metaphor, urgency, energy (PRIMARY)
- `#0a0a0a` (dark) — professional, technical, strong contrast (BACKGROUND)
- `#FFB84D` (light orange) — emphasis, secondary actions (ACCENT)
- `#FFFFFF` (white) — text on dark (TEXT)

### Typography Principles
- Headline: Condensed display font, high contrast, 72pt+, short and forceful
- Body: Clean sans serif, smaller and tighter, used as support not decoration
- CTA: Rounded orange pill with strong verb and dark text
- Preferred fonts: Avenir Next Condensed for headlines, Avenir Next or equivalent for body/UI

### Visual Style
- Dark theme (#0a0a0a background) references audio/voice/tech
- Orange accents create urgency and energy
- Whitespace is generous (40px padding minimum)
- Text is readable at mobile (1080x1920, 6pt minimum font size)

## Experiment Log

### Created (Not Yet Deployed)
1. **audio-first-001**: Curiosity angle, hook "This voicemail got a 40% callback rate."
   - Expected CPL: $7-8
   - Expected CTR: 4.5%
   - Hypothesis: Hook is irresistible + audio proves claim = lowest CPL

2. **audio-first-002**: ROI angle, hook "$0.001 per voicemail. Not a typo."
   - Expected CPL: $8-10
   - Expected CTR: 4.2%
   - Hypothesis: Math-driven appeal to cost-conscious wholesalers

3. **audio-first-003**: FOMO angle, hook "While you're dialing, your competitor's AI left 500 voicemails."
   - Expected CPL: $6-7
   - Expected CTR: 4.8%
   - Hypothesis: FOMO is proven close, audio proves speed claim

## Tools Built

### creative_generator.py
- Produces static images (PNG) in 4 templates
- Multiple sizes: 1080x1080 (feed), 1080x1920 (story), 1200x628 (link ad)
- Renders: stats-card, before-after, testimonial, single-image
- Output: Beautiful, brand-consistent images with orange accents

### video_composer.py
- Produces 15-second video ads using FFmpeg
- Timed text overlays (0-3s hook, 3-8s audio, 8-12s reveal, 12-15s CTA)
- Integrates VibeVoice audio samples
- Output: MP4 for feed and story placements

### meta_ads.py
- Full Meta Graph API v21.0 integration
- Create campaigns, ad sets, ads (all PAUSED for review)
- Pull performance insights (CPL, CTR, actions)
- Evaluate against kill/keep/scale thresholds

### evaluate.py
- Measures creative readiness (angle coverage, audio presence)
- Evaluates campaign performance (CPL, CTR, conversion rate)
- Generates composite score (0-1)
- Provides kill/keep/scale recommendations

## Performance Targets (To Hit)

### CPL Thresholds
- **Kill**: > $15 (pause immediately)
- **Keep**: $8-15 (maintain and monitor)
- **Scale**: < $8 (increase 25% every 3-4 days)
- **Ideal**: $6-8 (highly scalable)

### Expected Metrics
- **CTR**: 3.5-5% (audio-first should hit 4%+)
- **Lead Volume**: 5+ per day before deciding
- **Lead Quality**: Conversion to demo > 20%
- **ROAS**: Target 3:1 ($3 revenue per $1 spend)

## Blockers & Gaps

1. **Audio Samples**: Waiting on VibeVoice Producer agent to provide .mp3 files
   - audio-first-001.mp3 needed (5s voicemail demo)
   - audio-first-002.mp3 needed (alternative script)
   - audio-first-003.mp3 needed (different voice/tone)

2. **Meta API Access**: Requires META_ACCESS_TOKEN env var
   - Need long-lived page access token
   - Verify ads_management permission

3. **FFmpeg Installation**: video_composer.py requires FFmpeg
   - Mac: `brew install ffmpeg`
   - Linux: `apt install ffmpeg`

## Next Steps

1. Get VibeVoice samples (coordinate with vibevoice-producer agent)
2. Test creative_generator.py locally (verify image quality)
3. Test video_composer.py with sample audio (verify video quality)
4. Deploy first three audio-first ads (all PAUSED)
5. Gather 24-48 hours of data
6. Evaluate against CPL thresholds
7. Iterate: new angles, new audiences, budget scaling

## Learnings & Hypotheses

(Will accumulate as experiments run)

Current hypothesis: Audio-first ads will achieve 25-35% lower CPL than static images because:
- Audio provides proof that text cannot
- Curiosity hook creates undeniable CTA
- FOMO angle taps proven psychological trigger
- Wholesalers are already suspicious of AI; hearing it removes objection

## Launch Session Log

### 2026-04-01 — Production Launch
- Generated 3 static ad images (stats-card, testimonial, FOMO)
- Evaluated creative readiness: 3 creatives, audio-first framework ready
- Created 3 audio-first experiment specs (audio-first-001/002/003)
- Ready for deployment once VibeVoice audio samples are available
