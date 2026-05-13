# Iteration Loop Prompt — MelodySheet-Violin Transcription Tuning

You are running an autonomous tuning loop against the MelodySheet-Violin
transcription pipeline. The harness lives in `scripts/eval/`. Each iteration
generates synthetic violin audio, runs the v2 pipeline, compares against
ground truth, and gives you concrete failure modes to address with code edits.

## On each /loop tick, do exactly this

1. **Read state.** Inspect the tail of `scripts/eval/log.jsonl` to find the
   most-recent iteration number `N`. The next iteration is `N+1`. Open
   `scripts/eval/runs/iter_{N:04d}.json` to see per-case missed/extra notes.

2. **Stop check.** If `N >= 100` or `aggregate.mean_f1 >= 0.95` for the last
   three iterations, **do not schedule another wake-up** — the loop is done.
   Otherwise continue.

3. **Diagnose.** Look at the case with the lowest F1 and the aggregate axis
   with the largest deficit:
   - Low **recall** with high precision → onset detector misses note boundaries
     (look at `app/transcribe_mono.py` onset params, the `min_note_seconds`
     gate, and the same-pitch merge step).
   - Low **precision** with high recall → spurious notes from harmonic ghosts
     or vibrato over-segmentation.
   - High **onset MAE** → quantization grid or pYIN hop length / frame length.
   - **Octave errors** → fmin/fmax bounds, viterbi smoothing.
   - High **duration MAE** → quantization step + duration_label mapping in
     `app/rhythm.py`.

4. **Make ONE focused code change** in the relevant module
   (most likely `app/transcribe_mono.py`, `app/rhythm.py`, or
   `app/transcribe_poly.py`). Don't refactor; just adjust the parameter or
   the small block that the failure mode points to. Avoid risky cross-module
   refactors mid-loop.

5. **Re-run** the harness:
   ```
   apps/api/.venv/bin/python scripts/eval/run_iteration.py \
       --iteration {N+1} --label "<short description of change>"
   ```
   This auto-appends to `log.jsonl` and writes `runs/iter_{N+1:04d}.json`.

6. **Compare.** If `aggregate.mean_f1` improved (or stayed within 0.5 pt of the
   prior best with a justified trade-off such as halving onset MAE), keep the
   change. If it regressed by more than 2 pt of F1, **revert** the edit
   (`git checkout -- <file>`) and try a different angle next tick. Document
   what was tried in the label.

7. **Schedule next tick** via `ScheduleWakeup` with delaySeconds around 90 s
   and prompt re-set to `<<autonomous-loop-dynamic>>` so the runtime fires this
   same workflow again.

## Hard rules

- Never edit files outside `apps/api/app/` and `scripts/eval/`.
- Never run `pip install`, `git push`, or anything destructive.
- Don't introduce new top-level modules — modify what already exists.
- Don't change the test panel in `run_iteration.py`; the grading must stay
  apples-to-apples across iterations.
- If `pipeline_error` shows up in a case record, **fix it before tuning** —
  an exception is more damaging than any parameter drift.

## Budget

100 iterations max. Each tick should take well under 5 minutes wall time
(panel currently runs in ~25 s). Keep the work focused and the messages short.
