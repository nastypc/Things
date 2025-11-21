# Adjustment Pipeline Overview

- Automates CDT sheathing alignment so exterior boards match actual measured lengths while keeping structural footprint intact.
- Preserves the original ELM span, trimming or extending only sheathing as needed to eliminate Randek warnings and collisions.
- Applies the 27-inch rule for the trailing BOO1 panel: short gaps are trimmed; larger gaps promote a full-sheet flyover beyond the ELM.
- Positions every flyover on the outboard (non-origin) edge so the squaring reference remains untouched.
- Nudges structural members just enough (about 1 mm) to clear overlaps without altering long-span joists that provide support.
- Regenerates nail lines, glue lines, and metadata with two-decimal precision to reflect real material thickness stacks.
- Rebuilds glue lines as continuous runs with start/end offsets so the applicator stays clear of panel edges.
- Emits warnings when adjustments exceed expected tolerances so manual review can target remaining problem spots.
