# CDT Reference

## ELM (Element Measurements)
Describes the outer dimensions of the framework.
Format: `ELM:XSize:YSize:ZSize:Type:Length:Measurement:Quality;`
- ELM: Command identifier
- XSize: Framework length (float)
- YSize: Framework width (float)
- ZSize: Framework height (float)
- Type: String (default 1, not implemented)
- Length: Framework length (operator info, string)
- Measurement: Element measurements (operator info, string)
- Quality: Quality (operator info, string)
Example: `ELM:16000:8969:292:1:16':9'1 1/8":3 1/2";`

## TXT (Informational Text)
Human-readable notes; ignored by machines.
Format: `TXT:Text;`
- TXT: Command identifier
- Text: Informational text (string)
Example: `TXT:Information text;`

## SPB / SPE (Sub Panel Start/End)
Defines a sub panel container for components (e.g., studs, sub-assemblies).
Format: `SPB:xSize:ySize:zSize:x:y:z:name;`
- SPB: Command identifier
- xSize: Length (float)
- ySize: Width (float)
- zSize: Height (float)
- x, y, z: Position (float)
- name: Designation (string)

End of sub panel:
Format: `SPE;`

## STA (Stud Angular)
Describes a construction piece with orientation angles (e.g., floor joist).
Format: `STA:xSize:ySize:zSize:x:y:z:av:ah:ar:type:length:measurements:quality;`
- STA: Command identifier
- xSize, ySize, zSize: Length, Width, Height (float)
- x, y, z: Position (float)
- av: Rotation around z-axis (vertical, degrees)
- ah: Rotation around x-axis (horizontal, degrees)
- ar: Rotation around y-axis (rotation, degrees)
- type: Information field (string); can affect nailing pressure or LGS profile visualization
- length: Length (string)
- measurements: Measurements (string)
- quality: Quality (string)

**STA Angles:**
- AV = Angle vertical
- AH = Angle horizontal
- AR = Angle rotation
- Order of rotation: AV → AR → AH

Example: `STA:45:8600:198:588:36:60:0:0:0:Balk:8624:48x198:C24;`

## BOI / BOO (Sheathing Inside/Outside)
Defines sheathing for the inside (BOI) and outside (BOO) of the element.
Format: `BOI1:xSize:ySize:zSize:x:y:z:toolIndex:name;` (and BOI2–BOI5, BOO1–BOO5)
- BOI1–BOI5: Sheathing layer number on inside
- BOO1–BOO5: Sheathing layer number on outside
- xSize: Length (float)
- ySize: Width (float)
- zSize: Height (float)
- x, y, z: Position (float)
- toolIndex: Integer; describes board type or operation (see index table)
  - 0 = OSB sheathing
  - 1 = Tongue and groove
  - 2 = Tongue and groove with gluing
  - 98 = Timber
  - 99 = Foil
  - 100 = Breather Membrane
  - ...
- name: Designation (string)

**ELF Handling:**
- If ELF is OUTSIDE or UP: Z for outside layer is positive, Z for inside layer is negative.
- If ELF is INSIDE or DOWN: Z for inside layer is positive, Z for outside layer is negative.

Example (ELF = OUTSIDE or UP):
`BOI1:148:8696:22:0:0:-258:0:22x148;` (Z + zSize, e.g., -250 + 22, must never be > 0)

Example (ELF = INSIDE or DOWN):
`BOI1:148:8696:22:0:0:258:0:22x148;`

## NL (Nailing Line)
Defines a nailing line from start point to endpoint.
Format: `NL:xStart:yStart:zStart:xEnd:yEnd:zEnd:nailDistance:toolIndex;`
- NL: Command identifier
- xStart, yStart, zStart: Start point (float)
- xEnd, yEnd, zEnd: End point (float)
- nailDistance: Maximum distance between nails (float)
  - Nails are placed at start/end points and evenly spaced in between, never exceeding nailDistance.
- toolIndex: Integer; describes nail type/dimension (see index table)
  - Reserved: 14, 16 (do not use)
  - 0 = Staple dimension X
  - 1 = Staple dimension Y
  - 2 = Nail dimension Z

**Remarks:**
- NL can only be defined in XY-plane (zStart == zEnd)
- Nailing lines are associated with a specific layer (BOO1–BOO5 & BOI1–BOI5) by Z-position.
  - Line should be positioned on the outer edge of the board (upper for positive Z, under for negative Z)

Example:
`NL:62.00:2284.00:96.00:62.00:2526.00:96.00:305.00:1;`

## GL (Glue Line)
Describes a glue operation from start point to end point, optionally with a sinusoidal curve.
Format: `GL:xStart:yStart:zStart:xEnd:yEnd:zEnd:amplitude:wavelength:toolIndex;`
- GL: Command identifier
- xStart, yStart, zStart: Start point (float)
- xEnd, yEnd, zEnd: End point (float)
- amplitude: Sinus wave amplitude (mm); set to 0 for straight line
- wavelength: Sinus wavelength (mm); ignored for straight line
- toolIndex: Integer; describes glue type/nozzle/material (see index table)
  - 0 = 3 mm nozzle board adhesive
  - 1 = 7 mm nozzle board adhesive
  - ...

**Remarks:**
- GL can only be defined in XY-plane (zStart == zEnd)
- Gluing lines are associated with a specific layer (BOO1–BOO5 & BOI1–BOI5) by Z-position
  - Line should be positioned on the inner edge of the board (lower edge for positive Z, upper edge for negative Z)

## IL (Ink Line)
Describes an ink line operation from start point to end point.
Format: `IL:xStart:yStart:zStart:xEnd:yEnd:zEnd:toolIndex;`
- IL: Command identifier
- xStart, yStart, zStart: Start point (float)
- xEnd, yEnd, zEnd: End point (float)
- toolIndex: Integer; describes ink type/nozzle/material (see index table)
  - 0 = 3 mm ink line
  - 1 = 3 mm dotted ink line
  - ...

**Remarks:**
- IL can only be defined in XY-plane (zStart == zEnd)

## SL (Saw Line)
Describes a saw line operation, including inclination and tool type.
Format: `SL:xStart:yStart:zStart:xEnd:yEnd:zEnd:Inclination:toolIndex;`
- SL: Command identifier
- xStart, yStart, zStart: Start point (float); Z indicates surface of material
- xEnd, yEnd, zEnd: End point (float); ZEnd indicates saw depth
- Inclination: Saw inclination angle [1/10 deg]; 900 = 90°, 1350 = 135° (clockwise)
- toolIndex: Integer; describes sawing tool/operation (see index table)
  - 0 = Sawing tool (rough cut)
  - 1 = Sawing tool (fine cut)
  - ...

**Remarks:**
- Waste is calculated to the right-hand side of the saw line direction (relative to X/Y axis start/end)
- Saw inclination: 0° = flat, 90° = straight cut, 135° = 45° tilt right (from start to end, clockwise)

Example:
`SL:2649:7615:334:2852:7758:321:900:1;`

## ROB / RL / ROE (Routing)
Describes a routing operation from a start point (ROB), through routing points (RL), ending with ROE.

### Routing Begin (ROB)
Format: `ROB:X:Y:Z:toolIndex;`
- ROB: Command identifier
- X, Y, Z: Start point (float); Z is the surface of the board
- toolIndex: Integer; describes routing tool/operation (see index table)
  - 0 = 16 mm routing tool (15000 rpm)
  - 1 = 32 mm routing tool (7000 rpm)
  - ...
- Tool compensation and waste are calculated to the right of the vector from ROB to next RL.

### Routing Line (RL)
Format: `RL:x:y:z:radius;`
- RL: Command identifier
- x, y, z: Routing point (float); Z is tool depth in material
- radius: Float; describes a circular arc between previous point and this one
  - Negative radius = Clockwise
  - Positive radius = Counterclockwise
  - If radius = half the distance between RL points, result is a half circle
  - Radius cannot be smaller than half the distance of the routing line
  - Only describes a circular arc, not a curve

### Routing End (ROE)
Format: `ROE;`
- ROE: Command identifier

**Remarks:**
- Routing direction is always described from high Z, regardless of panel side
- Sequence: ROB (start) → RL (points) → ROE (end)
- Z values: ROB Z = lowest (surface), RL Z = highest (depth)

## CAD File Specification
- All dimensions follow the orientation of the element.
- All x (X, XSize, XEnd, etc.) are in the same direction.
- All y (Y, YSize, YEnd, etc.) are in the same direction.
- All z (Z, ZSize, ZEnd, etc.) are in the same direction.
- All positions are calculated from the bottom left-hand corner of the frame.
- Length units: millimeters (mm)
- Angles: degrees
- Float values: max two decimals; rounding is “half to even”; decimal delimiter is a point (`.`)
- Example: `BS:1948.00:36.00:198.00:0.00:0.00:60.00:Joist:1948:36x198:C24;`

## CDT File Structure
- CDT files are text files (ASCII or UTF-8) with the extension `.cdt`.
- The file must start with a header describing the outer dimensions and type of element.
- Sheathing is grouped in layers (e.g., BOI1 for first inside layer).
- Commands with multiple arguments use colon `:` as a separator; each line ends with a semicolon `;`.
- Example header: `ELM:xSize:ySize:zSize:type:length:measurement:quality;`
- The end of the file is indicated with: `EOF;`

## Coordinates
- All coordinate data are referenced to the zero point of the framework (lower left corner of the general framework).

# CDT Automation Notes
- With the provided CDT specification, we can accurately parse, duplicate, and manipulate CDT files.
- Step 1: To make an exact duplicate, read the original `.cdt` file and write a new file with identical contents and formatting.
- For sheathing logic: Full sheets should always be placed from the origin side (leftmost, x=0) in the panel.
- Next steps will address mirroring and flyover logic after duplication is confirmed.

---
## Fastener presets prior to cdt creation for refrence
Edge Spacing 6"
Field Spacing 12"
Distance from T & G Edge 1/2"
Distance from Square Edge 1/4"
Distance From Member End 3"
Provide Nailing For Blocking Yes
Nail Placement Method Break at Decking Edges
Full (GL) = Full Length Ignores Internal Decking Edges and places nails along full member length (sta)
Break at Decking Edges (NL) = leaves a gap between 'Distance from member end' fastener and edge of decking.


*This file is a backup and reference for CDT file format details. Additions will be appended as you provide more.*
