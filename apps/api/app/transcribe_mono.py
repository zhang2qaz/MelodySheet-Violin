from __future__ import annotations

from typing import Any


# Per-instrument pitch search bounds. Narrowing fmin/fmax dramatically improves pYIN
# accuracy and prevents octave errors that plague generic transcription models on
# bowed strings and woodwinds.
MONO_PITCH_BOUNDS: dict[str, tuple[str, str]] = {
    "violin": ("G3", "E7"),
    "vocal": ("C2", "C6"),
    "flute": ("C4", "C7"),
    "erhu": ("D4", "E7"),
}

DEFAULT_MONO_BOUNDS = ("C2", "C7")


def _resolve_bounds(target_instrument: str) -> tuple[str, str]:
    return MONO_PITCH_BOUNDS.get(target_instrument, DEFAULT_MONO_BOUNDS)


def _hz_to_midi(hz: float) -> float:
    import math

    if hz <= 0 or math.isnan(hz):
        return 0.0
    return 69.0 + 12.0 * math.log2(hz / 440.0)


def _midi_to_name(midi_number: int) -> str:
    names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    name = names[midi_number % 12]
    octave = midi_number // 12 - 1
    return f"{name}{octave}"


def transcribe_monophonic(
    audio: Any,
    sample_rate: int,
    target_instrument: str,
    *,
    min_note_seconds: float = 0.08,
) -> list[dict[str, Any]]:
    """Run pYIN + onset detection to produce monophonic note events.

    The output schema matches the existing pipeline's notes contract.
    """
    import librosa
    import numpy as np

    fmin_name, fmax_name = _resolve_bounds(target_instrument)
    fmin = float(librosa.note_to_hz(fmin_name))
    fmax = float(librosa.note_to_hz(fmax_name))

    # 128-sample hop @ 22.05 kHz = 5.8 ms per frame. This is fine-grained enough
    # to resolve 16th notes at 160 BPM (94 ms apart) through the onset_detect
    # peak-picking window. With hop=256 the default pre/post_max of 10 frames
    # gives a 116 ms half-window that swallows adjacent fast onsets.
    hop_length = 128
    # 1024 samples @ 22.05 kHz = 46 ms analysis window. The previous 2048 (93 ms)
    # is wider than a single 16th note at 160 BPM (94 ms), causing adjacent
    # notes to blur into one pYIN frame. 46 ms is still ≥9 periods at G3 (196 Hz)
    # so pitch accuracy on low strings is preserved.
    frame_length = 1024

    # Pitch tracking backend selection. CREPE (when installed) is a deep-learning
    # tracker that handles fast passages and noisy audio markedly better than
    # pYIN's viterbi-smoothed YIN — the 160 BPM 16th-note bottleneck on our test
    # panel is largely pYIN's smoothing artifact. We auto-detect; if CREPE isn't
    # importable we fall back to pYIN with no behavior change.
    backend = "pyin"
    try:
        from app import pitch_crepe

        if pitch_crepe.is_available():
            backend = "crepe"
    except Exception:
        backend = "pyin"

    if backend == "crepe":
        try:
            from app import pitch_crepe

            f0, voiced_flag, voiced_prob = pitch_crepe.predict_f0_on_hop_grid(
                audio,
                sample_rate,
                hop_length,
                model_capacity="tiny",
                confidence_threshold=0.5,
            )
            # Clip f0 outside the instrument's pitch band — CREPE has no fmin/fmax
            # parameter so we filter here.
            outside_band = (f0 < fmin) | (f0 > fmax)
            f0[outside_band] = np.nan
            voiced_flag[outside_band] = False
        except Exception:
            backend = "pyin"

    if backend == "pyin":
        f0, voiced_flag, voiced_prob = librosa.pyin(
            audio,
            fmin=fmin,
            fmax=fmax,
            sr=sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
            fill_na=np.nan,
        )

    if f0 is None or len(f0) == 0:
        return []

    # Two complementary onset channels:
    # 1) Spectral-flux (default): fires on pitch changes — the dominant signal
    #    for most articulations.
    # 2) RMS-envelope rise: catches same-pitch repeated notes, which produce
    #    almost no spectral change but a fresh amplitude attack. Without this
    #    second channel pYIN sees a single sustained note where there are
    #    really several, and recall on repeated-pitch passages collapses.
    #
    # The RMS channel is intrinsically noisy (vibrato, bow tremor). We adopt
    # an additive policy: keep ALL spectral-flux onsets, and only accept an
    # RMS-rise onset when no spectral onset already covers a ±60 ms window
    # around it. We also enforce a 120 ms global minimum spacing, which is
    # the physical floor for 16th notes at 132 BPM (the fastest case in our
    # test panel).
    onset_env = librosa.onset.onset_strength(
        y=audio, sr=sample_rate, hop_length=hop_length, aggregate=np.median
    )
    onset_frames_spec = np.atleast_1d(
        librosa.onset.onset_detect(
            onset_envelope=onset_env,
            sr=sample_rate,
            hop_length=hop_length,
            # backtrack=False keeps the onset at the spectral-flux peak. With
            # backtrack=True librosa pulls each onset back to the preceding
            # local minimum of the strength curve, which on slow violin bow
            # articulations can be 100–160 ms before the actual attack — far
            # outside the 100 ms matching tolerance.
            backtrack=False,
            units="frames",
            wait=1,
            pre_avg=10,
            post_avg=10,
            pre_max=5,
            post_max=5,
            delta=0.04,
        )
    ).astype(int)

    rms = librosa.feature.rms(y=audio, hop_length=hop_length)[0]
    rms_rise = np.maximum(0.0, np.diff(rms, prepend=rms[0]))
    onset_frames_rms = np.atleast_1d(
        librosa.onset.onset_detect(
            onset_envelope=rms_rise,
            sr=sample_rate,
            hop_length=hop_length,
            backtrack=True,
            units="frames",
            wait=2,
            pre_avg=8,
            post_avg=8,
            pre_max=8,
            post_max=8,
            delta=0.003,
        )
    ).astype(int)

    frames_per_60ms = max(1, int(0.06 * sample_rate / hop_length))
    # 90 ms minimum onset spacing: 16th notes at 167 BPM are 90 ms long; anything
    # tighter than that is almost certainly over-segmentation in violin playing.
    frames_per_90ms = max(1, int(0.09 * sample_rate / hop_length))

    # Third onset channel: pYIN f0 jumps. When the tracked pitch shifts by
    # ≥1.2 semitones between two voiced frames, that's a clear note boundary
    # even if the spectral-flux envelope hasn't fully resolved (which happens
    # on fast successive 16ths in similar registers). The 1.2-semitone
    # threshold also keeps trills (1-semitone alternation) from triggering
    # this channel; trill articulations are detected by the spectral/RMS
    # channels instead.
    f0_clean = np.where(~np.isnan(f0), f0, 0.0)
    voiced_clean = np.where(voiced_flag, 1.0, 0.0) if voiced_flag is not None else np.zeros_like(f0_clean)
    log_f0 = np.zeros_like(f0_clean)
    valid_idx = f0_clean > 0
    log_f0[valid_idx] = np.log2(f0_clean[valid_idx]) * 12.0  # semitones
    # Compare each frame's pitch to a short-window median of the previous frames,
    # so transient single-frame jitter isn't mistaken for a note boundary.
    window = 3
    onset_frames_f0: list[int] = []
    for index in range(window + 1, len(log_f0)):
        if not voiced_clean[index]:
            continue
        if not voiced_clean[index - 1]:
            # Came out of unvoiced region — let the spectral/RMS channels handle this.
            continue
        prev_window = log_f0[max(0, index - window):index]
        prev_voiced = voiced_clean[max(0, index - window):index]
        valid_prev = prev_window[prev_voiced > 0]
        if len(valid_prev) == 0:
            continue
        delta_semitones = abs(log_f0[index] - float(np.median(valid_prev)))
        if delta_semitones >= 1.2:
            onset_frames_f0.append(index)
    onset_frames_f0_arr = np.array(onset_frames_f0, dtype=int)

    accepted: list[int] = list(onset_frames_spec.tolist())
    for frame in onset_frames_rms.tolist():
        if any(abs(frame - existing) <= frames_per_60ms for existing in accepted):
            continue
        accepted.append(frame)
    # f0-jump onsets are added when they fall into a "spectral silence gap"
    # — at least 50 ms from the nearest already-accepted onset. Tightening
    # the gate (vs 120 ms) lets f0-jump fill in fast 16th-note gaps where
    # spectral flux smoothing missed an articulation. The 1.2-semitone
    # pitch threshold above keeps trill-style 1-semitone alternations out
    # of this channel.
    frames_per_50ms = max(1, int(0.05 * sample_rate / hop_length))
    for frame in onset_frames_f0_arr.tolist():
        if accepted:
            nearest_distance = min(abs(frame - existing) for existing in accepted)
            if nearest_distance < frames_per_50ms:
                continue
        accepted.append(int(frame))

    accepted.sort()
    # Enforce minimum spacing between onsets (post-hoc).
    deduped: list[int] = []
    for frame in accepted:
        if deduped and frame - deduped[-1] < frames_per_90ms:
            continue
        deduped.append(frame)
    onset_frames = np.array(deduped, dtype=int)

    # Cap the analysis window at the last "loud" frame. pYIN happily returns an
    # f0 estimate for the near-silent tail of the audio (release tail or the
    # synth's post-roll), which manifests as phantom notes after the music
    # actually ends. We define "loud enough" as ≥10% of the audio's peak RMS;
    # any onset/boundary past that frame is dropped.
    quiet_threshold = 0.1 * float(np.max(rms)) if len(rms) > 0 else 0.0
    if quiet_threshold > 0:
        loud_mask = np.where(rms >= quiet_threshold)[0]
        last_loud_frame = int(loud_mask[-1]) if len(loud_mask) > 0 else len(f0)
    else:
        last_loud_frame = len(f0)
    total_frames = min(len(f0), last_loud_frame + 1)
    onset_frames = onset_frames[onset_frames < total_frames]
    boundary_frames = sorted({0, *onset_frames.tolist(), total_frames})

    # Build segments between consecutive onsets. For each segment, take the median of
    # voiced pYIN frames as the note pitch; skip if too few voiced frames. If a
    # segment is dropped (typically the very first one: short attack ramp where
    # pYIN hasn't converged yet), the NEXT segment inherits its start frame so
    # the leading audio isn't silently lost.
    notes: list[dict[str, Any]] = []
    pending_start_frame: int | None = None
    for index in range(len(boundary_frames) - 1):
        start_frame = int(boundary_frames[index])
        end_frame = int(boundary_frames[index + 1])
        if pending_start_frame is not None:
            start_frame = pending_start_frame
            pending_start_frame = None
        if end_frame - start_frame < 2:
            continue
        segment_f0 = f0[start_frame:end_frame]
        segment_voiced = voiced_flag[start_frame:end_frame] if voiced_flag is not None else None
        segment_prob = voiced_prob[start_frame:end_frame] if voiced_prob is not None else None

        mask = ~np.isnan(segment_f0)
        if segment_voiced is not None:
            mask = mask & segment_voiced
        valid = segment_f0[mask]
        if len(valid) < max(2, int((min_note_seconds * sample_rate) / hop_length * 0.25)):
            # Mark this slice so the next segment absorbs its leading frames.
            pending_start_frame = start_frame
            continue

        median_hz = float(np.median(valid))
        if median_hz <= 0:
            continue
        midi_float = _hz_to_midi(median_hz)
        midi_number = int(round(midi_float))
        if midi_number <= 0:
            continue

        # Pull the start forward to the first frame inside the segment where RMS
        # exceeds 30 % of the segment's peak RMS. This counteracts pYIN tracking
        # f0 through the pre-attack noise floor of a quiet leading region.
        segment_rms = rms[start_frame:end_frame]
        if len(segment_rms) > 0:
            segment_peak_rms = float(np.max(segment_rms))
            attack_floor = 0.3 * segment_peak_rms
            above = np.where(segment_rms >= attack_floor)[0]
            if len(above) > 0:
                trimmed_start_frame = start_frame + int(above[0])
            else:
                trimmed_start_frame = start_frame
        else:
            trimmed_start_frame = start_frame

        start_time = float(librosa.frames_to_time(trimmed_start_frame, sr=sample_rate, hop_length=hop_length))
        end_time = float(librosa.frames_to_time(end_frame, sr=sample_rate, hop_length=hop_length))
        duration_seconds = max(end_time - start_time, 0.05)
        if duration_seconds < min_note_seconds:
            continue

        if segment_prob is not None and len(segment_prob[mask]) > 0:
            confidence = float(np.mean(segment_prob[mask]))
        else:
            confidence = 0.7

        # Track the mean RMS over the segment + the local minimum near the boundary
        # so the merge step can distinguish a real re-attack (deep RMS valley before
        # the next segment) from a pYIN artefact mid-sustain (no valley).
        segment_rms_mean = float(np.mean(rms[start_frame:end_frame])) if end_frame > start_frame else 0.0

        # Pitch-bend / glissando detection: measure how much the segment's
        # f0 deviates from its median pitch. If the trajectory shows a
        # monotonic rise/fall of more than 30 cents, mark the note with a
        # bend curve. Useful for violin slides, vocal portamento, guitar bends.
        bend_amount_cents = 0.0
        bend_direction: str | None = None
        if len(valid) >= 4:
            segment_midi = 12.0 * np.log2(np.maximum(valid, 1e-9) / 440.0) + 69.0
            # Compare first quartile median vs last quartile median
            q = max(1, len(segment_midi) // 4)
            head_midi = float(np.median(segment_midi[:q]))
            tail_midi = float(np.median(segment_midi[-q:]))
            delta_semitones = tail_midi - head_midi
            bend_amount_cents = round(delta_semitones * 100.0, 1)
            if abs(bend_amount_cents) >= 30:
                bend_direction = "up" if bend_amount_cents > 0 else "down"

        notes.append(
            {
                "start_frame": int(start_frame),
                "end_frame": int(end_frame),
                "rms_mean": round(segment_rms_mean, 6),
                "start_time": round(start_time, 4),
                "end_time": round(start_time + duration_seconds, 4),
                "pitch": _midi_to_name(midi_number),
                "midi_number": midi_number,
                "duration_seconds": round(duration_seconds, 4),
                "duration_label": "quarter",
                "confidence": round(max(0.0, min(confidence, 1.0)), 3),
                "pitch_bend_cents": bend_amount_cents,
                "pitch_bend_direction": bend_direction,
            }
        )

    # Conditional merge: two adjacent same-pitch segments could be (a) a real
    # repeated note with a clean re-attack, or (b) a pYIN artefact mid-sustain.
    # We distinguish by inspecting the RMS valley around the boundary frame:
    #   - real re-attack: RMS dips meaningfully (release tail) and rises again.
    #   - artefact      : RMS stays roughly flat across the boundary.
    # If the minimum RMS in a ±40 ms window around the boundary is at least
    # 65% of the mean RMS of the surrounding segments, the boundary is "flat"
    # and we merge. Otherwise we treat it as a real articulation and keep both.
    frames_per_40ms = max(1, int(0.04 * sample_rate / hop_length))
    merged: list[dict[str, Any]] = []
    for item in notes:
        if not merged:
            merged.append(item)
            continue
        last = merged[-1]
        gap = item["start_time"] - last["end_time"]
        if item["midi_number"] == last["midi_number"] and gap <= 0.03:
            boundary_frame = int(item["start_frame"])
            window_start = max(0, boundary_frame - frames_per_40ms)
            window_end = min(len(rms), boundary_frame + frames_per_40ms + 1)
            boundary_rms_min = float(np.min(rms[window_start:window_end])) if window_end > window_start else 0.0
            surrounding_mean = max(last["rms_mean"], item["rms_mean"], 1e-6)
            valley_ratio = boundary_rms_min / surrounding_mean

            # Rise-rate discriminator: a real re-attack shows a fast RMS rise
            # right after the boundary even when the valley is shallow (synth
            # release tails of 80 ms don't decay all the way to zero, so a
            # well-articulated repeated note can have valley_ratio of 0.7–0.9
            # but still has a clear attack peak ~40 ms later).
            rise_window_end = min(len(rms), boundary_frame + frames_per_40ms + 1)
            post_max = float(np.max(rms[boundary_frame:rise_window_end])) if rise_window_end > boundary_frame else 0.0
            rise_amount = post_max - boundary_rms_min
            has_clear_rise = rise_amount >= 0.3 * surrounding_mean

            is_flat_boundary = valley_ratio >= 0.65 and not has_clear_rise
            if is_flat_boundary:
                last["end_time"] = item["end_time"]
                last["end_frame"] = item["end_frame"]
                last["duration_seconds"] = round(last["end_time"] - last["start_time"], 4)
                last["confidence"] = round(max(last["confidence"], item["confidence"]), 3)
                last["rms_mean"] = round(max(last["rms_mean"], item["rms_mean"]), 6)
            else:
                merged.append(item)
        else:
            merged.append(item)

    # Post-merge filter: drop short notes that are clearly fragments rather
    # than real articulations. Two patterns we suppress:
    #
    # 1. Semitone jitter — note <150 ms with a ±1-semitone neighbor that's
    #    at least 2x as long (pYIN momentarily latching onto an adjacent
    #    pitch during vibrato or attack transients).
    # 2. Same-pitch fragment — note <150 ms wedged between or adjacent to a
    #    same-MIDI neighbor that's at least 2x as long (the conditional
    #    merge step couldn't merge these because the RMS valley was deep
    #    enough to look like a re-articulation, but the resulting tiny
    #    third "note" is almost always a sub-fragment of the long one).
    SHORT_FRAGMENT_LIMIT = 0.15
    NEIGHBOR_RATIO = 1.5
    LOW_CONF_FRAGMENT_LIMIT = 0.1
    LOW_CONF_THRESHOLD = 0.7
    pruned: list[dict[str, Any]] = []
    for idx, item in enumerate(merged):
        dur = float(item["duration_seconds"])
        if dur < SHORT_FRAGMENT_LIMIT:
            prev_note = merged[idx - 1] if idx > 0 else None
            next_note = merged[idx + 1] if idx + 1 < len(merged) else None
            looks_like_fragment = False
            for neighbor in (prev_note, next_note):
                if neighbor is None:
                    continue
                midi_diff = abs(int(neighbor["midi_number"]) - int(item["midi_number"]))
                if midi_diff not in (0, 1):
                    continue
                if float(neighbor["duration_seconds"]) >= dur * NEIGHBOR_RATIO:
                    looks_like_fragment = True
                    break
            if looks_like_fragment:
                continue
        # Glissando/transition fragments — very short, low-confidence pitches
        # caught between two confidently-identified notes (B4 → D5 → E5 etc.).
        # Drop them: a real note that lasts under 100 ms is almost always
        # tracked with high pYIN voiced_prob; a confidence of <0.7 with a
        # sub-100 ms duration is a passing transient.
        if dur < LOW_CONF_FRAGMENT_LIMIT and float(item.get("confidence", 1.0)) < LOW_CONF_THRESHOLD:
            continue
        pruned.append(item)

    # =====================================================================
    # PRIMARY CONFIDENCE GATE -- the most impactful single filter.
    #
    # pYIN's voiced_prob is the probability that the analysis window was
    # voiced at the tracked pitch. The pipeline already records this as
    # `confidence` in each note BUT never uses it to filter.
    #
    # Diagnostic on a real user recording (job 736fa...) found:
    #   total notes: 187
    #   median confidence: 0.29
    #   notes with conf < 0.6: 154 (82 % !!)
    # These low-confidence notes are pYIN essentially saying "I have no idea
    # if there's a real pitch here, but here's my best guess from the noise."
    # The user perceives them as 鬼音 / ghost notes -- random pitches scattered
    # all over the score that don't match what they actually played.
    #
    # 0.55 threshold rationale (from typical pYIN voicing distribution):
    #   loud sustained note            : 0.80 - 0.95   KEEP
    #   quiet but clean note           : 0.55 - 0.75   KEEP
    #   attack transient / bow noise   : 0.20 - 0.45   DROP
    #   background hiss / silence      : 0.00 - 0.20   DROP
    #
    # Safety net: if this gate happens to drop everything (e.g. a very quiet
    # recording where pYIN runs cold), fall back to a lower threshold rather
    # than returning an empty score.
    # =====================================================================
    CONFIDENCE_GATE = 0.55
    confident = [n for n in pruned if float(n.get("confidence", 1.0)) >= CONFIDENCE_GATE]
    if confident:
        pruned = confident
    else:
        # Don't strand the user with an empty score. Halve the gate and try
        # again; if still empty, return whatever survived the earlier filters.
        relaxed = [n for n in pruned if float(n.get("confidence", 1.0)) >= 0.30]
        if relaxed:
            pruned = relaxed
        # else: keep the original `pruned` so SOMETHING comes back.

    for index, note in enumerate(pruned, start=1):
        note["index"] = index
        # The bookkeeping fields aren't part of the public note schema; strip them.
        note.pop("start_frame", None)
        note.pop("end_frame", None)
        note.pop("rms_mean", None)
    return pruned
