"""Assemble lanv.svml: presenter-generation head + composition part + generated pointer geometry.

usage: assemble.py <intro-start>:<intro-length> [output.svml] [head.svml]
The head is everything in the source before the Script (imports, clock, presenter generation).
"""
import sys, pathlib

root = pathlib.Path(__file__).resolve().parent.parent
intro_start, intro_length = sys.argv[1].split(":")
output = root / (sys.argv[2] if len(sys.argv) > 2 else "lanv.svml")
head_source = root / (sys.argv[3] if len(sys.argv) > 3 else "lanv.svml")

svml = head_source.read_text()
head = svml.split("\n  <!-- ===== 台词")[0].rstrip().removesuffix("</svml>").rstrip()
imports = """  <import from="@hypit/script@1"/>
  <import as="whisperx" from="@hypit/whisperx@1"/>
  <import as="space" from="@hypit/spatial@1"/>
  <import as="performance" from="@hypit/performance@1"/>
  <import as="sound" from="@hypit/sound@1"/>
  <import as="media-track" from="@hypit/media-track@1"/>
  <import as="typo" from="@hypit/typography-track@1"/>
  <import as="caption-fine" from="@hypit/caption-fine@1"/>
  <import as="fonts" from="@hypit/fonts-open@1"/>
  <import as="film" from="@hypit/film@1"/>
  <import as="render" from="@hypit/render-hyperframes@1"/>
  <import as="recipes" source="./recipes.svs"/>
"""
if 'from="@hypit/script@1"' not in head:
    anchor = '  <import as="time" from="@hypit/timeline-author@1"/>\n'
    head = head.replace(anchor, anchor + imports)

out = (root / "gen/pointers.out").read_text()
geometry = out.split("<!-- GEOMETRY -->\n")[1].split("<!-- ITEMS -->")[0].rstrip()
items = out.split("<!-- ITEMS -->\n")[1].rstrip()
part = (root / "gen/composition.svml.part").read_text()
part = (part.replace("__INTRO_START__", intro_start).replace("__INTRO_LENGTH__", intro_length)
        .replace("__GEOMETRY__", geometry).replace("__ITEMS__", items))
output.write_text(head + "\n" + part.rstrip() + "\n</svml>\n")
print("assembled", output.name, intro_start, intro_length)
