# Gaussian Elimination

**Yash Panpaliya · E25B070658**  
M3 Linear Algebra and Calculus · Animation Video

The video solves a three by three system using row operations, pivots and back substitution. It verifies the solution `(1, 2, 3)` in the original equations.

## Project files

- `_Video.mp4` — final video, 1920 × 1080, 6:04, narrated by Yash Panpaliya.
- `_Code/` — editable Python animation, scene data, timing, final render entry point and recorded voice-over.
- `Storyboard.pdf` — six-scene storyboard.
- `Narration_Transcript.txt` — English voice-over reading script. The timings are speaking cues from the recording version.

## Rebuild

Install Python, Pillow, NumPy and FFmpeg. From the repository root, run:

```sh
uv run --with pillow --with numpy python _Code/render_submission.py
```

The script writes `Rebuilt_Video.mp4`. It uses the supplied recorded voice-over and applies the visual timing in `_Code/timing.json`.

## Sources and credits

- M3 Animation Video Project Instructions (course handout).
- OpenStax, *College Algebra 2e*, [Solving Systems with Gaussian Elimination](https://openstax.org/books/college-algebra-2e/pages/7-6-solving-systems-with-gaussian-elimination).
- OpenAI Codex assisted with the script, worked example, animation code and supporting documents. The final voice-over was recorded by Yash Panpaliya.
- Animation was produced with Pillow and FFmpeg. No music or stock visuals were used.
