# Demo interface direction

Audience: hackathon judges and clinicians reviewing a **synthetic educational case**.
Primary job: choose a scenario, watch the actual persisted event cascade, and inspect what is and is not supported.

Palette: imaging navy `#102C3B`, deep panel `#183D4D`, operating-room mint `#BBDDD4`, signal coral `#E88A73`, chart paper `#F0F5F2`, ink `#143440`.

Type: Trebuchet MS for the large headline and organ names; Segoe UI for dense controls and audit text. Numerals use tabular figures.

Layout: a wide workbench rather than uniform cards. The left rail contains the scenario controls, the central canvas contains an original inline SVG anatomical map with four interactive organ points, and the right rail contains the currently selected finding. A full-width event strip below is the source of truth. Everything aligns left except the anatomical map.

```text
┌ navigation / synthetic status / connection ┐
│ scenario controls │ body map │ organ details │
├───────────── event timeline and scrubber ────┤
│ coverage / citations / limitations          │
```

The memorable element is the anatomical map driven by persisted council findings. The remaining interface is quiet and readable. Body shapes are diagrammatic rather than faux medical imaging. The UI never colors an organ green merely because an illustrative constant is in a typical range; unsupported response stays grey/unknown.
