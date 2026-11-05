# Desktop redesign direction

The previous visual pass preserved correctness but did not achieve a coherent desktop composition. This pass addresses that gap; it is not a change to analytical acceptance criteria.

## Visual system

- Paper #FFFFFF, canvas #F5F6F8, ink #202D40, secondary #657185, interface accent #315C88, selection #D4A15B.
- Avenir Next for headings, controls and charts; Segoe UI / Arial fallbacks. 28 px questions, 17 px chart headings, 13–14 px body and controls, 12 px chart labels. Tabular numerals for comparison.
- Left-aligned content, compact horizontal six-module navigation, maximum 1480 px analysis width. Desktop only; no new mobile scope.
- Geographic flows are the visual signature: a large navy map, restrained blue-cyan lines and meaningful amber selection. Other charts use white surfaces. No decorative gradients, 3D or ornamental statistics cards.
- Stable country colors across all modules; labels and symbols supplement hue. Quantitative scales, samples, values, denominators and guided cases stay unchanged.

## Composition

```
Trade atlas                                  1995–2024 / CEPII
Overview | Geography | Economy | Partners | Products | Time
Question / concise context
Compact controls

M0 [ global trajectory 50% ][ country evidence 50% ]
M1 [ distance scatter 70%  ][ evidence 30%         ]
   [ geographical context / partner ranking      ]
M2 [ global scatter 64%    ][ paired evidence 36%  ]
M3 [ dark flow map 70%     ][ partner shares 30%   ]
   [ region comparison    ][ interpretation       ]
M4 [ product heatmap 55%   ][ detail comparison 45% ]
M5 [ recovery timeline    ][ finding / metrics     ]
   [ aligned structure    ][ inspected-year detail ]
Methods and complete evidence, disclosed on demand
```

## Independent critique applied

SideLens reviewed the rejected screenshots and original reference. Its strongest finding was excessive interface scaffolding, not simply the old palette. Keep the dark map; increase plotted geography and selected-flow prominence. Replace oversized intro/step/control blocks, expose both M4 charts together, and move M5 findings beside aligned timelines. Evaluate real rendered charts rather than generated raster approximations.

Review M3 and M4 at 1440×900 and 1280×800 before final propagation. Check geometry, readable labels, overlaps, full interaction states and unchanged numeric snapshots. Do not claim all content fits one screen where labels or completeness require more height.
