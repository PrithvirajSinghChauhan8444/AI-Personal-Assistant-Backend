"""Local speech-to-text transcription engine using faster-whisper.

Provides deterministic, offline audio transcription for voice notes and media.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TranscriptionSegment:
    start_second: float
    end_second: float
    text: str


@dataclass(frozen=True)
class AudioTranscriptionResult:
    text: str
    language: str
    duration_seconds: float
    segments: List[TranscriptionSegment]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_whisper_model(model_size: str = "tiny", preferred_device: str = "auto"):
    """Instantiate a faster-whisper model with automatic CPU fallback."""
    from faster_whisper import WhisperModel

    devices_to_try = []
    if preferred_device == "cuda":
        devices_to_try = [("cuda", "float16"), ("cpu", "int8")]
    elif preferred_device == "cpu":
        devices_to_try = [("cpu", "int8")]
    else:
        # Auto: try cuda if available, else cpu
        try:
            import torch
            if torch.cuda.is_available():
                devices_to_try.append(("cuda", "float16"))
        except Exception:
            pass
        devices_to_try.append(("cpu", "int8"))

    last_error = None
    for device, compute_type in devices_to_try:
        try:
            return WhisperModel(model_size, device=device, compute_type=compute_type)
        except Exception as exc:
            last_error = exc
            continue

    raise RuntimeError(f"Failed to load WhisperModel: {last_error}")


def load_audio_waveform(audio_path: str):
    """Load and resample audio into a 16kHz mono float32 numpy array."""
    import numpy as np
    import soundfile as sf

    data, sample_rate = sf.read(audio_path, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)

    if sample_rate != 16000:
        import scipy.signal
        target_samples = int(len(data) * 16000 / sample_rate)
        data = scipy.signal.resample(data, target_samples).astype(np.float32)

    return data


def format_segments(raw_segments) -> List[TranscriptionSegment]:
    """Convert raw whisper segments to structured dataclasses."""
    formatted = []
    for segment in raw_segments:
        formatted.append(
            TranscriptionSegment(
                start_second=round(segment.start, 2),
                end_second=round(segment.end, 2),
                text=segment.text.strip(),
            )
        )
    return formatted


def transcribe_audio_file(
    audio_path: str,
    model_size: str = "tiny",
    beam_size: int = 5,
) -> AudioTranscriptionResult:
    """Transcribe an audio file into text using local faster-whisper with resilient fallback."""
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file does not exist: {audio_path}")

    waveform = load_audio_waveform(audio_path)

    # Try transcription; if CUDA runtime fails (e.g. missing cuBLAS .so), fallback to CPU
    try:
        model = load_whisper_model(model_size, preferred_device="auto")
        segments_gen, info = model.transcribe(waveform, beam_size=beam_size)
        segments = format_segments(segments_gen)
    except RuntimeError as exc:
        if "libcublas" in str(exc) or "CUDA" in str(exc):
            model = load_whisper_model(model_size, preferred_device="cpu")
            segments_gen, info = model.transcribe(waveform, beam_size=beam_size)
            segments = format_segments(segments_gen)
        else:
            raise

    full_text = " ".join(seg.text for seg in segments).strip()

    return AudioTranscriptionResult(
        text=full_text,
        language=info.language,
        duration_seconds=round(info.duration, 2),
        segments=segments,
    )


def main():
    parser = argparse.ArgumentParser(description="Transcribe audio file locally")
    parser.add_argument("path", help="Path to audio file")
    parser.add_argument("--model", default="tiny", help="Whisper model size")
    parser.add_argument("--json", action="store_true", help="Output full JSON")
    args = parser.parse_args()

    try:
        result = transcribe_audio_file(args.path, model_size=args.model)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.text)
    except Exception as exc:
        sys.stderr.write(f"Transcription error: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
