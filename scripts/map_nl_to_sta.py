from pathlib import Path
import re
import sys


def parse_sta(path):
    out=[]
    lines=Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    for line in lines:
        s=line.strip()
        if s.startswith('STA:') or s.startswith('STB:'):
            parts=s.rstrip(';').split(':')
            try:
                x=float(parts[4].strip())
                y=float(parts[5].strip())
                out.append({'x':x,'y':y,'raw':s})
            except Exception:
                nums=[float(t) for t in re.findall(r'-?\d+(?:\.\d+)?', s)[:6]]
                if len(nums)>=6:
                    out.append({'x':nums[3],'y':nums[4],'raw':s})
    return out


def parse_nl(path):
    out=[]
    lines=Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    for i,line in enumerate(lines):
        s=line.strip()
        if s.startswith('NL:'):
            parts=s.rstrip(';').split(':')
            try:
                x1=float(parts[1].strip()); y1=float(parts[2].strip()); z1=float(parts[3].strip())
                x2=float(parts[4].strip()); y2=float(parts[5].strip()); z2=float(parts[6].strip())
            except Exception:
                nums=[float(t) for t in re.findall(r'-?\d+(?:\.\d+)?', s)[:6]]
                if len(nums)>=6:
                    x1,y1,z1,x2,y2,z2=nums[:6]
                else:
                    continue
            out.append({'i':len(out)+1,'x1':x1,'y1':y1,'x2':x2,'y2':y2,'raw':s})
    return out


def parse_sheets(path):
    out=[]
    lines=Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    for line in lines:
        s=line.strip()
        if s.startswith('BOO') or s.startswith('BOI'):
            parts=s.rstrip(';').split(':')
            try:
                x_size=float(parts[1].strip()); y_size=float(parts[2].strip()); x=float(parts[4].strip())
                out.append({'x':x,'x_size':x_size,'y_size':y_size,'raw':s})
            except Exception:
                nums=[float(t) for t in re.findall(r'-?\d+(?:\.\d+)?', s)[:5]]
                if len(nums)>=5:
                    out.append({'x':nums[3],'x_size':nums[0],'y_size':nums[1],'raw':s})
    return out


def nearest_sta(x,stas):
    best=None; bd=None; idx=None
    for i,s in enumerate(stas, start=1):
        d=abs(s['x']-x)
        if bd is None or d<bd:
            best=s; bd=d; idx=i
    return idx,best,bd


def sheet_for_x(x,sheets):
    for i,s in enumerate(sheets, start=1):
        if s['x']-1e-6 <= x <= s['x']+s['x_size']+1e-6:
            return i,s
    return None,None


def report(path):
    print(f"\nFile: {path}")
    stas=parse_sta(path)
    nls=parse_nl(path)
    sheets=parse_sheets(path)
    print(f"Parsed {len(stas)} STA, {len(nls)} NL, {len(sheets)} sheets")
    for nl in nls:
        xm=(nl['x1']+nl['x2'])/2.0
        ym=(nl['y1']+nl['y2'])/2.0
        sta_idx,sta,dist=nearest_sta(xm,stas) if stas else (None,None,None)
        sheet_idx,sheet=sheet_for_x(xm,sheets)
        print(f"NL#{nl['i']:02d}: start=({nl['x1']:.2f},{nl['y1']:.2f}) end=({nl['x2']:.2f},{nl['y2']:.2f}) mid=({xm:.2f},{ym:.2f}) -> STA#{sta_idx} x={sta['x'] if sta else None:.2f} dist={dist:.2f} sheet={sheet_idx}")


if __name__=='__main__':
    if len(sys.argv)<2:
        print('Usage: map_nl_to_sta.py <cdtfile> [more files...]')
        sys.exit(2)
    for p in sys.argv[1:]:
        report(p)
