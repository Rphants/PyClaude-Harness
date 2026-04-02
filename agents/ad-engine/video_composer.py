#!/usr/bin/env python3
"""Video Composer — Produces audio-first video ads using FFmpeg.

Composes short-form video ads with:
    - Background image or color
    - VibeVoice audio track
    - Timed text overlays
    - Audio waveform visualization
    - Professional transitions

15-second format structure:
    0-3s: Hook text overlay
    3-8s: Audio plays with waveform animation, main text overlay
    8-12s: Reveal text ("That was AI. Not a person.")
    12-15s: CTA text overlay + button

Outputs:
    - 1080x1080 MP4 (feed)
    - 1080x1920 MP4 (story)

Usage:
    python video_composer.py \
        --audio sample.mp3 \
        --hook "This voicemail got a 40% callback rate." \
        --main "Press play. It's not what you think..." \
        --reveal "That was AI. Not a person." \
        --cta "Get Early Access" \
        --output video-001.mp4
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

AGENT_DIR = Path(__file__).parent
EXPERIMENTS_DIR = AGENT_DIR / "experiments"

# Brand colors
BRAND_DARK = "0a0a0a"
BRAND_ORANGE = "FF8800"
BRAND_LIGHT_ORANGE = "FFB84D"
BRAND_WHITE = "FFFFFF"


class VideoComposer:
    """Composes video ads using FFmpeg."""

    def __init__(self, dry_run: bool = False):
        """Initialize composer.

        Args:
            dry_run: If True, print ffmpeg commands instead of running them.
        """
        self.dry_run = dry_run
        self._check_ffmpeg()

    def _check_ffmpeg(self) -> None:
        """Verify FFmpeg is installed."""
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("ERROR: FFmpeg not installed or not in PATH")
            print("Install with: brew install ffmpeg  # macOS")
            print("             apt install ffmpeg   # Linux")
            print("             choco install ffmpeg # Windows")
            sys.exit(1)

    def _run_cmd(self, cmd: list[str]) -> None:
        """Run a shell command."""
        if self.dry_run:
            print(" ".join(cmd))
        else:
            subprocess.run(cmd, check=True, capture_output=True)

    def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio duration in seconds using ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1:noprint_wrappers=1",
                    audio_path,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return float(result.stdout.strip())
        except (FileNotFoundError, ValueError, subprocess.CalledProcessError):
            # Default to 5 seconds if we can't get duration
            return 5.0

    def compose(
        self,
        audio_path: str | None = None,
        hook_text: str = "",
        main_text: str = "",
        reveal_text: str = "That was AI. Not a person.",
        cta_text: str = "Get Early Access",
        output_path: str = "video.mp4",
        size: str = "feed",  # feed or story
    ) -> None:
        """Compose a video ad.

        Args:
            audio_path: Path to .mp3 audio file
            hook_text: Text to show 0-3s (hook)
            main_text: Text to show 3-8s (during audio)
            reveal_text: Text to show 8-12s
            cta_text: Call-to-action text 12-15s
            output_path: Output MP4 file path
            size: "feed" (1080x1080) or "story" (1080x1920)
        """
        if size == "feed":
            width, height = 1080, 1080
        else:  # story
            width, height = 1080, 1920

        # Ensure output directory exists
        output_path = Path(output_path)
        if not output_path.is_absolute():
            output_path = EXPERIMENTS_DIR / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get audio duration if provided
        audio_duration = self._get_audio_duration(audio_path) if audio_path else 5.0

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Step 1: Generate background color video (15 seconds)
            bg_video = tmpdir_path / "bg.mp4"
            self._create_background_video(bg_video, width, height, 15.0)

            # Step 2: Create text overlay filter_complex
            # We'll use drawtext filter for overlays at different times
            filters = self._build_filter_complex(
                width=width,
                height=height,
                hook_text=hook_text,
                main_text=main_text,
                reveal_text=reveal_text,
                cta_text=cta_text,
                audio_duration=audio_duration,
            )

            # Step 3: Compose final video
            cmd = ["ffmpeg", "-i", str(bg_video)]

            # Add audio if provided
            if audio_path and Path(audio_path).exists():
                cmd.extend(["-i", audio_path])

            # Apply filters
            cmd.extend(["-vf", filters])

            # Add audio mapping if audio was provided
            if audio_path and Path(audio_path).exists():
                cmd.extend(["-c:a", "aac", "-c:v", "libx264", "-pix_fmt", "yuv420p"])
                cmd.extend(["-shortest"])
            else:
                cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p"])

            # Output settings
            cmd.extend(["-y", str(output_path)])

            # Run FFmpeg
            try:
                self._run_cmd(cmd)
                print(f"Video saved: {output_path}")
            except subprocess.CalledProcessError as e:
                print(f"ERROR: FFmpeg failed: {e}")
                raise

    def _create_background_video(self, output_path: Path, width: int, height: int, duration: float) -> None:
        """Create a solid background color video."""
        cmd = [
            "ffmpeg",
            "-f",
            "lavfi",
            "-i",
            f"color=c=#{BRAND_DARK}:s={width}x{height}:d={duration}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(output_path),
        ]
        self._run_cmd(cmd)

    def _build_filter_complex(
        self,
        width: int,
        height: int,
        hook_text: str = "",
        main_text: str = "",
        reveal_text: str = "",
        cta_text: str = "",
        audio_duration: float = 5.0,
    ) -> str:
        """Build FFmpeg filter_complex for text overlays.

        Timeline:
            0-3s: hook_text (center, large, orange)
            3-8s: main_text (center, medium, white) + waveform suggestion
            8-12s: reveal_text (center, medium, orange)
            12-15s: cta_text (center, medium, orange) + box
        """

        filters = []

        # Calculate positions (centered, with padding)
        text_x = f"(w-text_w)/2"
        text_y_top = int(height * 0.2)
        text_y_mid = int(height * 0.45)
        text_y_bottom = int(height * 0.7)

        # Hook text: 0-3s, orange, large, fade in
        if hook_text:
            hook_filter = (
                f"drawtext="
                f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"text='{_escape_text(hook_text)}':"
                f"fontsize=56:"
                f"fontcolor=#{BRAND_ORANGE}:"
                f"x={text_x}:"
                f"y={text_y_top}:"
                f"enable='between(t,0,3)'"
            )
            filters.append(hook_filter)

        # Main text: 3-8s, white
        if main_text:
            main_filter = (
                f"drawtext="
                f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
                f"text='{_escape_text(main_text)}':"
                f"fontsize=36:"
                f"fontcolor=#{BRAND_WHITE}:"
                f"x={text_x}:"
                f"y={text_y_mid}:"
                f"enable='between(t,3,8)'"
            )
            filters.append(main_filter)

        # Reveal text: 8-12s, orange
        if reveal_text:
            reveal_filter = (
                f"drawtext="
                f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"text='{_escape_text(reveal_text)}':"
                f"fontsize=48:"
                f"fontcolor=#{BRAND_ORANGE}:"
                f"x={text_x}:"
                f"y={text_y_mid}:"
                f"enable='between(t,8,12)'"
            )
            filters.append(reveal_filter)

        # CTA text: 12-15s, orange
        if cta_text:
            cta_filter = (
                f"drawtext="
                f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"text='{_escape_text(cta_text)}':"
                f"fontsize=40:"
                f"fontcolor=#{BRAND_DARK}:"
                f"x={text_x}:"
                f"y={text_y_bottom}:"
                f"enable='between(t,12,15)'"
            )
            filters.append(cta_filter)

        # Join all filters
        return ",".join(filters) if filters else "null"


def _escape_text(text: str) -> str:
    """Escape text for FFmpeg drawtext filter."""
    # Replace single quotes and special characters
    text = text.replace("'", "\\'")
    text = text.replace("\\", "\\\\")
    text = text.replace("[", "\\[")
    text = text.replace("]", "\\]")
    return text


def main():
    """CLI interface."""
    parser = argparse.ArgumentParser(description="Video Ad Composer")
    parser.add_argument("--audio", help="Path to .mp3 audio file")
    parser.add_argument("--hook", default="", help="Hook text (0-3s)")
    parser.add_argument("--main", default="", help="Main text (3-8s)")
    parser.add_argument("--reveal", default="", help="Reveal text (8-12s)")
    parser.add_argument("--cta", default="Get Early Access", help="CTA text (12-15s)")
    parser.add_argument("--output", required=True, help="Output MP4 path")
    parser.add_argument("--size", default="feed", choices=["feed", "story"], help="Output size")
    parser.add_argument("--dry-run", action="store_true", help="Print commands instead of running")

    args = parser.parse_args()

    composer = VideoComposer(dry_run=args.dry_run)
    composer.compose(
        audio_path=args.audio,
        hook_text=args.hook,
        main_text=args.main,
        reveal_text=args.reveal,
        cta_text=args.cta,
        output_path=args.output,
        size=args.size,
    )


if __name__ == "__main__":
    main()
