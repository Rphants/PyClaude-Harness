#!/usr/bin/env python3
"""Ad Creative Generator — Produces high-quality static ad images.

This module generates beautiful, brand-consistent ad creatives using Pillow.
Supports multiple templates: stats-card, before-after, testimonial, single-image.

Templates output:
    - 1080x1080 (feed)
    - 1080x1920 (story)
    - 1200x628 (link ad)

Usage:
    python creative_generator.py --template stats-card \
        --headline "10,000 Voicemails. Zero Phone Calls." \
        --body "Hit play. That voicemail cost $0.001 to send." \
        --output preview-001.png

    python creative_generator.py --template testimonial \
        --headline "40% callback rate." \
        --quote "This is literally the best tool I've used." \
        --author "Sarah, Texas Wholesaler" \
        --output preview-002.png
"""

from __future__ import annotations

import argparse
import json
import os
import textwrap
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow")
    exit(1)

# Brand Colors
BRAND_DARK = "#0a0a0a"          # Background
BRAND_ORANGE = "#FF8800"        # Primary accent
BRAND_LIGHT_ORANGE = "#FFB84D"  # Secondary accent
BRAND_WHITE = "#FFFFFF"         # Text
BRAND_GRAY = "#999999"          # Secondary text
BRAND_DARK_GRAY = "#333333"     # Borders/accents

# Typography
HEADLINE_SIZE = int(os.environ.get("AD_CREATIVE_HEADLINE_SIZE", "84"))
BODY_SIZE = int(os.environ.get("AD_CREATIVE_BODY_SIZE", "24"))
SMALL_SIZE = int(os.environ.get("AD_CREATIVE_SMALL_SIZE", "18"))
TINY_SIZE = int(os.environ.get("AD_CREATIVE_TINY_SIZE", "14"))
CTA_SIZE = int(os.environ.get("AD_CREATIVE_CTA_SIZE", "28"))

AGENT_DIR = Path(__file__).parent
EXPERIMENTS_DIR = AGENT_DIR / "experiments"


class CreativeGenerator:
    """Generates ad creatives with multiple templates."""

    def __init__(self):
        """Initialize font library (try system fonts)."""
        self.fonts = self._init_fonts()

    def _init_fonts(self) -> dict[str, Any]:
        """Initialize fonts. Fall back to default if system fonts unavailable."""
        fonts = {}
        display_paths = [
            "/System/Library/Fonts/Avenir Next Condensed.ttc",
            "/System/Library/Fonts/Supplemental/Futura.ttc",
            "/System/Library/Fonts/HelveticaNeue.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        body_paths = [
            "/System/Library/Fonts/Avenir Next.ttc",
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/HelveticaNeue.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

        def load_font(candidates: list[str], size: int, label: str) -> Any:
            for path in candidates:
                try:
                    font = ImageFont.truetype(path, size)
                    print(f"  Loaded {label} font: {path}")
                    return font
                except (FileNotFoundError, OSError):
                    continue
            return ImageFont.load_default()

        fonts["headline"] = load_font(display_paths, HEADLINE_SIZE, "headline")
        fonts["body"] = load_font(body_paths, BODY_SIZE, "body")
        fonts["small"] = load_font(body_paths, SMALL_SIZE, "small")
        fonts["tiny"] = load_font(body_paths, TINY_SIZE, "tiny")
        fonts["button"] = load_font(body_paths, CTA_SIZE, "button")
        fonts["eyebrow"] = load_font(body_paths, 16, "eyebrow")

        return fonts

    def _draw_waveform(self, draw: ImageDraw.ImageDraw, x: int, y: int, width: int, height: int) -> None:
        """Draw an audio waveform visualization."""
        import random
        random.seed(42)  # Deterministic for consistency

        bar_width = 4
        bar_spacing = 2
        bars = width // (bar_width + bar_spacing)

        for i in range(bars):
            bar_x = x + i * (bar_width + bar_spacing)
            bar_height = random.randint(int(height * 0.3), height)
            bar_y = y + (height - bar_height) // 2

            draw.rectangle(
                [(bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height)],
                fill=BRAND_ORANGE,
            )

    def _wrap_text(self, text: str, max_width_chars: int = 40) -> list[str]:
        """Wrap text to fit width."""
        return textwrap.wrap(text, width=max_width_chars)

    def _size_dimensions(self, size: str) -> tuple[int, int]:
        """Map size preset to pixel dimensions."""
        if size == "feed":
            return 1080, 1080
        if size == "story":
            return 1080, 1920
        return 1200, 628

    def _fit_cover(
        self,
        source: Image.Image,
        target_width: int,
        target_height: int,
        *,
        focus_x: float = 0.5,
        focus_y: float = 0.5,
    ) -> Image.Image:
        """Resize and crop an image to cover the target area."""
        src_w, src_h = source.size
        scale = max(target_width / src_w, target_height / src_h)
        resized = source.resize((int(src_w * scale), int(src_h * scale)))
        max_left = max(0, resized.width - target_width)
        max_top = max(0, resized.height - target_height)
        left = int(max_left * max(0, min(1, focus_x)))
        top = int(max_top * max(0, min(1, focus_y)))
        return resized.crop((left, top, left + target_width, top + target_height))

    def _get_text_bbox(self, draw: ImageDraw.ImageDraw, text: str, font: Any) -> tuple[int, int, int, int]:
        """Get text bounding box (fallback for older Pillow versions)."""
        try:
            return draw.textbbox((0, 0), text, font=font)
        except AttributeError:
            # Older Pillow version
            return (0, 0, len(text) * 20, 40)

    def generate_stats_card(
        self,
        headline: str,
        body: str = "",
        stats: list[tuple[str, str]] | None = None,
        cta_text: str = "Get Early Access",
        size: str = "feed",
    ) -> Image.Image:
        """Generate a stats-card template: headline, body, 2-3 stats, CTA."""
        if size == "feed":
            width, height = 1080, 1080
        elif size == "story":
            width, height = 1080, 1920
        else:  # link-ad
            width, height = 1200, 628

        img = Image.new("RGB", (width, height), BRAND_DARK)

        # Padding
        padding = 40
        content_width = width - (padding * 2)

        # Y positions
        y_pos = padding + 60

        # Draw headline
        headline_wrapped = self._wrap_text(headline, max_width_chars=20)
        for line in headline_wrapped:
            draw.text(
                (padding, y_pos),
                line,
                fill=BRAND_ORANGE,
                font=self.fonts["headline"],
                anchor="lt",
            )
            y_pos += HEADLINE_SIZE + 10

        y_pos += 30

        # Draw body if provided
        if body:
            body_wrapped = self._wrap_text(body, max_width_chars=35)
            for line in body_wrapped:
                draw.text(
                    (padding, y_pos),
                    line,
                    fill=BRAND_WHITE,
                    font=self.fonts["body"],
                    anchor="lt",
                )
                y_pos += BODY_SIZE + 8

        y_pos += 40

        # Draw stats if provided
        if stats:
            for stat_label, stat_value in stats:
                # Stat value in orange
                draw.text(
                    (padding, y_pos),
                    stat_value,
                    fill=BRAND_ORANGE,
                    font=self.fonts["headline"],
                    anchor="lt",
                )
                y_pos += HEADLINE_SIZE + 5

                # Stat label in gray
                draw.text(
                    (padding, y_pos),
                    stat_label,
                    fill=BRAND_GRAY,
                    font=self.fonts["small"],
                    anchor="lt",
                )
                y_pos += BODY_SIZE + 30

        # Draw CTA button
        button_width = 400
        button_height = 60
        button_x = (width - button_width) // 2
        button_y = height - padding - button_height

        draw.rectangle(
            [(button_x, button_y), (button_x + button_width, button_y + button_height)],
            fill=BRAND_ORANGE,
            outline=BRAND_LIGHT_ORANGE,
            width=2,
        )
        draw.text(
            (button_x + button_width // 2, button_y + button_height // 2),
            cta_text,
            fill=BRAND_DARK,
            font=self.fonts["body"],
            anchor="mm",
        )

        return img

    def generate_before_after(
        self,
        headline: str,
        before_text: str,
        after_text: str,
        cta_text: str = "Get Early Access",
        size: str = "feed",
    ) -> Image.Image:
        """Generate a before/after split template."""
        if size == "feed":
            width, height = 1080, 1080
        elif size == "story":
            width, height = 1080, 1920
        else:  # link-ad
            width, height = 1200, 628

        img = Image.new("RGB", (width, height), BRAND_DARK)
        draw = ImageDraw.Draw(img)

        padding = 40

        # Draw headline at top
        y_pos = padding
        headline_wrapped = self._wrap_text(headline, max_width_chars=20)
        for line in headline_wrapped:
            draw.text(
                (padding, y_pos),
                line,
                fill=BRAND_ORANGE,
                font=self.fonts["headline"],
                anchor="lt",
            )
            y_pos += HEADLINE_SIZE + 10

        # Divider line
        mid_x = width // 2
        divider_y = height // 2
        draw.rectangle(
            [(mid_x - 2, padding + 100), (mid_x + 2, divider_y * 2 - padding)],
            fill=BRAND_DARK_GRAY,
        )

        # Left side: BEFORE
        y_before = padding + 120
        draw.text(
            (padding, y_before),
            "BEFORE",
            fill=BRAND_GRAY,
            font=self.fonts["small"],
            anchor="lt",
        )
        y_before += 50

        before_wrapped = self._wrap_text(before_text, max_width_chars=20)
        for line in before_wrapped:
            draw.text(
                (padding, y_before),
                line,
                fill=BRAND_WHITE,
                font=self.fonts["body"],
                anchor="lt",
            )
            y_before += BODY_SIZE + 10

        # Right side: AFTER
        y_after = padding + 120
        draw.text(
            (mid_x + padding, y_after),
            "AFTER",
            fill=BRAND_ORANGE,
            font=self.fonts["small"],
            anchor="lt",
        )
        y_after += 50

        after_wrapped = self._wrap_text(after_text, max_width_chars=20)
        for line in after_wrapped:
            draw.text(
                (mid_x + padding, y_after),
                line,
                fill=BRAND_LIGHT_ORANGE,
                font=self.fonts["body"],
                anchor="lt",
            )
            y_after += BODY_SIZE + 10

        # Draw CTA button at bottom
        button_width = 400
        button_height = 60
        button_x = (width - button_width) // 2
        button_y = height - padding - button_height

        draw.rectangle(
            [(button_x, button_y), (button_x + button_width, button_y + button_height)],
            fill=BRAND_ORANGE,
            outline=BRAND_LIGHT_ORANGE,
            width=2,
        )
        draw.text(
            (button_x + button_width // 2, button_y + button_height // 2),
            cta_text,
            fill=BRAND_DARK,
            font=self.fonts["body"],
            anchor="mm",
        )

        return img

    def generate_testimonial(
        self,
        headline: str,
        quote: str,
        author: str,
        cta_text: str = "Get Early Access",
        size: str = "feed",
    ) -> Image.Image:
        """Generate a testimonial template with quote and author."""
        if size == "feed":
            width, height = 1080, 1080
        elif size == "story":
            width, height = 1080, 1920
        else:  # link-ad
            width, height = 1200, 628

        img = Image.new("RGB", (width, height), BRAND_DARK)
        draw = ImageDraw.Draw(img)

        padding = 40
        content_width = width - (padding * 2)

        y_pos = padding + 60

        # Draw headline
        headline_wrapped = self._wrap_text(headline, max_width_chars=20)
        for line in headline_wrapped:
            draw.text(
                (padding, y_pos),
                line,
                fill=BRAND_ORANGE,
                font=self.fonts["headline"],
                anchor="lt",
            )
            y_pos += HEADLINE_SIZE + 10

        y_pos += 80

        # Draw quotation mark
        draw.text(
            (padding, y_pos),
            '"',
            fill=BRAND_ORANGE,
            font=self.fonts["headline"],
            anchor="lt",
        )
        y_pos += 40

        # Draw quote
        quote_wrapped = self._wrap_text(quote, max_width_chars=30)
        for line in quote_wrapped:
            draw.text(
                (padding + 30, y_pos),
                line,
                fill=BRAND_WHITE,
                font=self.fonts["body"],
                anchor="lt",
            )
            y_pos += BODY_SIZE + 10

        y_pos += 30

        # Draw closing quote mark
        draw.text(
            (padding + 30, y_pos),
            '"',
            fill=BRAND_ORANGE,
            font=self.fonts["headline"],
            anchor="lt",
        )

        y_pos += 60

        # Draw author
        draw.text(
            (padding, y_pos),
            f"— {author}",
            fill=BRAND_LIGHT_ORANGE,
            font=self.fonts["small"],
            anchor="lt",
        )

        # Draw CTA button at bottom
        button_width = 400
        button_height = 60
        button_x = (width - button_width) // 2
        button_y = height - padding - button_height

        draw.rectangle(
            [(button_x, button_y), (button_x + button_width, button_y + button_height)],
            fill=BRAND_ORANGE,
            outline=BRAND_LIGHT_ORANGE,
            width=2,
        )
        draw.text(
            (button_x + button_width // 2, button_y + button_height // 2),
            cta_text,
            fill=BRAND_DARK,
            font=self.fonts["body"],
            anchor="mm",
        )

        return img

    def generate_single_image(
        self,
        headline: str,
        body: str = "",
        cta_text: str = "Get Early Access",
        size: str = "feed",
    ) -> Image.Image:
        """Generate a simple single-image template: headline + body + CTA."""
        if size == "feed":
            width, height = 1080, 1080
        elif size == "story":
            width, height = 1080, 1920
        else:  # link-ad
            width, height = 1200, 628

        img = Image.new("RGB", (width, height), BRAND_DARK)
        draw = ImageDraw.Draw(img)

        padding = 40

        # Draw headline
        y_pos = (height // 2) - 150
        headline_wrapped = self._wrap_text(headline, max_width_chars=25)
        for line in headline_wrapped:
            draw.text(
                (padding, y_pos),
                line,
                fill=BRAND_ORANGE,
                font=self.fonts["headline"],
                anchor="lt",
            )
            y_pos += HEADLINE_SIZE + 15

        y_pos += 30

        # Draw body if provided
        if body:
            body_wrapped = self._wrap_text(body, max_width_chars=35)
            for line in body_wrapped:
                draw.text(
                    (padding, y_pos),
                    line,
                    fill=BRAND_WHITE,
                    font=self.fonts["body"],
                    anchor="lt",
                )
                y_pos += BODY_SIZE + 10

        # Draw CTA button
        button_width = 400
        button_height = 60
        button_x = (width - button_width) // 2
        button_y = height - padding - 80

        draw.rectangle(
            [(button_x, button_y), (button_x + button_width, button_y + button_height)],
            fill=BRAND_ORANGE,
            outline=BRAND_LIGHT_ORANGE,
            width=2,
        )
        draw.text(
            (button_x + button_width // 2, button_y + button_height // 2),
            cta_text,
            fill=BRAND_DARK,
            font=self.fonts["body"],
            anchor="mm",
        )

        return img

    def generate_hybrid_ugc(
        self,
        headline: str,
        body: str = "",
        cta_text: str = "Hear the AI voicemail",
        background_image: str = "",
        brand_label: str = "AgentRVM",
        proof_text: str = "40% callback rate",
        size: str = "feed",
    ) -> Image.Image:
        """Generate a hybrid ad: AI-generated scene + deterministic brand layout."""
        width, height = self._size_dimensions(size)

        img = Image.new("RGB", (width, height), BRAND_DARK)
        draw = ImageDraw.Draw(img)

        if size == "story":
            padding = 56
            photo_width = int(width * 0.78)
            photo_height = int(height * 0.4)
            photo_x = (width - photo_width) // 2
            photo_y = int(height * 0.48)
        elif size == "link-ad":
            padding = 36
            photo_width = int(width * 0.48)
            photo_height = int(height * 0.76)
            photo_x = width - padding - photo_width
            photo_y = (height - photo_height) // 2
        else:
            padding = 56
            photo_width = 496
            photo_height = 672
            photo_x = width - padding - photo_width
            photo_y = 164

        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, 0), (width, height)], fill="#07111c")
        for y in range(height):
            shade = int(12 + (18 * (y / max(1, height))))
            draw.line([(0, y), (width, y)], fill=(7, shade, 28))

        if background_image:
            source = Image.open(background_image).convert("RGB")
            photo = self._fit_cover(source, photo_width, photo_height, focus_x=1.0, focus_y=0.5)
            shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_draw.rounded_rectangle(
                [(photo_x + 16, photo_y + 18), (photo_x + photo_width + 16, photo_y + photo_height + 18)],
                radius=26,
                fill=(0, 0, 0, 110),
            )
            img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")
            img.paste(photo, (photo_x, photo_y))

            # Darken the edge nearest the text column for readability.
            edge = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            edge_draw = ImageDraw.Draw(edge)
            for i in range(photo_width):
                opacity = int(135 * max(0, 1 - i / (photo_width * 0.32)))
                edge_x = photo_x + i
                edge_draw.line(
                    [(edge_x, photo_y), (edge_x, photo_y + photo_height)],
                    fill=(7, 17, 28, opacity),
                )
            img = Image.alpha_composite(img.convert("RGBA"), edge).convert("RGB")
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle(
                [(photo_x, photo_y), (photo_x + photo_width, photo_y + photo_height)],
                radius=26,
                outline=(255, 255, 255, 30),
                width=2,
            )

        brand_y = padding + 10
        draw.ellipse([(padding, brand_y + 10), (padding + 16, brand_y + 26)], fill=BRAND_ORANGE)
        draw.text(
            (padding + 30, brand_y),
            brand_label,
            fill=BRAND_WHITE,
            font=self.fonts["small"],
            anchor="lt",
        )
        draw.text(
            (padding, brand_y + 38),
            "AI VOICEMAIL FOR WHOLESALERS",
            fill="#89A2B8",
            font=self.fonts["eyebrow"],
            anchor="lt",
        )

        chip_x = padding
        chip_y = padding + 88
        chip_width = 220
        chip_height = 34
        draw.rounded_rectangle(
            [(chip_x, chip_y), (chip_x + chip_width, chip_y + chip_height)],
            radius=17,
            fill="#102334",
            outline="#1A334A",
            width=1,
        )
        draw.text(
            (chip_x + 18, chip_y + chip_height // 2),
            proof_text.upper(),
            fill="#D8E6F2",
            font=self.fonts["eyebrow"],
            anchor="lm",
        )

        headline_y = padding + 142
        headline_wrapped = self._wrap_text(headline, max_width_chars=15 if size != "link-ad" else 13)
        for line in headline_wrapped:
            fill = BRAND_ORANGE if any(token in line for token in ["$", "%", "24/7", "40%"]) else BRAND_WHITE
            draw.text(
                (padding, headline_y),
                line,
                fill=fill,
                font=self.fonts["headline"],
                anchor="lt",
            )
            headline_y += HEADLINE_SIZE + 4

        cta_width = 320 if size == "link-ad" else 370
        cta_height = 66
        cta_y = headline_y + 26
        draw.rounded_rectangle(
            [(padding, cta_y), (padding + cta_width, cta_y + cta_height)],
            radius=18,
            fill=BRAND_ORANGE,
        )
        draw.text(
            (padding + cta_width // 2, cta_y + cta_height // 2),
            cta_text,
            fill=BRAND_DARK,
            font=self.fonts["button"],
            anchor="mm",
        )

        body_y = cta_y + cta_height + 34
        body_wrapped = self._wrap_text(body, max_width_chars=24 if size != "link-ad" else 20)
        for line in body_wrapped:
            draw.text(
                (padding, body_y),
                line,
                fill="#D7E2EC",
                font=self.fonts["body"],
                anchor="lt",
            )
            body_y += BODY_SIZE + 10

        waveform_y = photo_y + photo_height - 76
        self._draw_waveform(draw, photo_x + 24, waveform_y, photo_width - 48, 34)
        draw.rounded_rectangle(
            [(photo_x + 24, photo_y + 24), (photo_x + 178, photo_y + 58)],
            radius=16,
            fill=(0, 0, 0, 120),
        )
        draw.text(
            (photo_x + 101, photo_y + 41),
            "MISSED CALL",
            fill=BRAND_WHITE,
            font=self.fonts["eyebrow"],
            anchor="mm",
        )

        return img


def main():
    """CLI interface."""
    parser = argparse.ArgumentParser(description="Ad Creative Generator")
    parser.add_argument(
        "--template",
        required=True,
        choices=["stats-card", "before-after", "testimonial", "single-image", "hybrid-ugc"],
        help="Creative template type",
    )
    parser.add_argument("--headline", required=True, help="Main headline")
    parser.add_argument("--body", default="", help="Body text (for stats-card, single-image)")
    parser.add_argument("--quote", default="", help="Quote text (for testimonial)")
    parser.add_argument("--author", default="", help="Author name (for testimonial)")
    parser.add_argument("--before", default="", help="Before text (for before-after)")
    parser.add_argument("--after", default="", help="After text (for before-after)")
    parser.add_argument(
        "--stats",
        type=str,
        default="",
        help='Stats as JSON: \'[["Label 1", "Value 1"], ["Label 2", "Value 2"]]\'',
    )
    parser.add_argument("--cta", default="Get Early Access", help="CTA button text")
    parser.add_argument("--background-image", default="", help="Optional background/source image path")
    parser.add_argument("--brand-label", default="AgentRVM", help="Brand label text")
    parser.add_argument("--proof-text", default="40% callback rate", help="Small proof chip text")
    parser.add_argument(
        "--size",
        default="feed",
        choices=["feed", "story", "link-ad"],
        help="Output size",
    )
    parser.add_argument("--output", required=True, help="Output PNG path")

    args = parser.parse_args()

    # Ensure output directory exists
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = EXPERIMENTS_DIR / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate creative
    gen = CreativeGenerator()

    if args.template == "stats-card":
        stats = []
        if args.stats:
            try:
                stats = json.loads(args.stats)
            except json.JSONDecodeError:
                print(f"WARNING: Invalid stats JSON: {args.stats}")

        img = gen.generate_stats_card(
            headline=args.headline,
            body=args.body,
            stats=stats,
            cta_text=args.cta,
            size=args.size,
        )

    elif args.template == "before-after":
        img = gen.generate_before_after(
            headline=args.headline,
            before_text=args.before,
            after_text=args.after,
            cta_text=args.cta,
            size=args.size,
        )

    elif args.template == "testimonial":
        img = gen.generate_testimonial(
            headline=args.headline,
            quote=args.quote,
            author=args.author,
            cta_text=args.cta,
            size=args.size,
        )

    elif args.template == "hybrid-ugc":
        img = gen.generate_hybrid_ugc(
            headline=args.headline,
            body=args.body,
            cta_text=args.cta,
            background_image=args.background_image,
            brand_label=args.brand_label,
            proof_text=args.proof_text,
            size=args.size,
        )

    else:  # single-image
        img = gen.generate_single_image(
            headline=args.headline,
            body=args.body,
            cta_text=args.cta,
            size=args.size,
        )

    # Save image
    img.save(output_path, "PNG")
    print(f"Creative saved: {output_path}")


if __name__ == "__main__":
    main()
