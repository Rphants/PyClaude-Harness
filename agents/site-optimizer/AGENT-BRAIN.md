# Site Optimizer — Agent Brain

## What I Know

### The Product
- AgentRVM: AI ringless voicemail for real estate wholesalers & investors
- VibeVoice: Self-hosted TTS on RunPod A100s, 4x cheaper than Cartesia, $0.0016/msg
- Target: wholesalers & investors (NOT realtors — explicitly corrected)
- Pricing: $10/msg pay-as-you-go, $7/msg at $2,500/mo, $5/msg at $5,000/mo

### The Site
- URL: https://agentrvm.com
- Framework: Next.js (App Router) + TypeScript + Tailwind CSS
- Hosting: Firebase Hosting (static export)
- Design: Dark theme, #FF8800 orange, white text, gradient overlays
- Hero: Background video (Veo 3.1, 8s, autoplay), left-aligned content
- Layout: Content constrained to lg:max-w-[45%] on desktop

### What Converts Wholesalers
- Pain point: Cold calling is exhausting and expensive
- Desire: More callbacks with less effort
- Proof: They need to HEAR how good the AI voice sounds
- Trust: "Other wholesalers are already using this"
- Urgency: "Limited beta spots" or "Join X others waiting"

### VibeVoice Audio Quality
- Luis Uribe's reaction: "dammmmmmmn that actually sounds very good"
- 18/18 concurrent sessions on single A100
- Emotion control parameters available (happy, calm, etc.)
- Voice cloning possible with reference audio
- Key insight: hearing is believing — audio demo is the #1 conversion lever

## Experiment Log

(No experiments yet — agent just initialized)

## Learnings

(Will accumulate as experiments run)

## Current Hypothesis

**Audio demo is the highest-impact change.** Wholesalers make decisions based on what they hear. If they can play a sample voicemail and it sounds human, the product sells itself. Every other optimization (copy, layout, CTAs) is secondary to this.

## Blockers

1. Need a VibeVoice sample .mp3 for the landing page
2. PostHog project key not yet configured
3. Site needs production deploy before any A/B test can run
