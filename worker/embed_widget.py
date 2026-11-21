#!/usr/bin/env python3
"""Copy widget.src.js into ullswater-ai.js (between the WIDGET markers) so the Worker stays a single file
that can also be pasted into the Cloudflare dashboard. Run after editing widget.src.js."""
from pathlib import Path
here = Path(__file__).resolve().parent
src = (here / "widget.src.js").read_text(encoding="utf-8")
assert "`" not in src and "${" not in src, "widget.src.js must not contain backticks or ${"
w = here / "ullswater-ai.js"
s = w.read_text(encoding="utf-8")
a, b = s.index("// WIDGET-START"), s.index("// WIDGET-END")
s = s[:a] + "// WIDGET-START (generated from widget.src.js by embed_widget.py; do not edit here)\nconst WIDGET_JS = String.raw`" + src + "`;\n" + s[b:]
w.write_text(s, encoding="utf-8")
print("widget embedded:", len(src), "chars")
