"""Generate src/customsiq/static/harbor-scene.svg, the animated login/app background.

Original artwork drawn in code, so there is no third-party image licence to
track. Every animation shares one 5-second cycle, so the scene loops without a
seam. Run once after editing, and commit the output:

    python scripts/make_harbor_scene.py src/customsiq/static/harbor-scene.svg
"""
import random
import sys

W, H = 1600, 900
PAL = ["#c0392b", "#e67e22", "#1f7a8c", "#e1b12c", "#2e6fb7", "#7a8b99", "#8e44ad", "#16a085"]


def wave(y: float, amp: float, period: float, color: str, opacity: float, cls: str) -> str:
    d = [f"M -{period} {y}"]
    x = -period
    while x < W + 2 * period:
        d.append(f"q {period/4} {-amp} {period/2} 0 t {period/2} 0")
        x += period
    d.append(f"L {W + 2*period} {H} L -{period} {H} Z")
    return f'<path class="{cls}" d="{" ".join(d)}" fill="{color}" opacity="{opacity}"/>'


def containers(
    x0: int, y0: int, cols: int, rows: int, w: int = 34, h: int = 18, gap: int = 2, seed: int = 0
) -> str:
    rnd = random.Random(seed)
    out = []
    for r in range(rows):
        n = cols - (1 if r == rows - 1 and rnd.random() < 0.5 else 0)
        for c in range(n):
            if r == rows - 1 and rnd.random() < 0.25:
                continue
            x, y = x0 + c * (w + gap), y0 - (r + 1) * (h + gap)
            col = rnd.choice(PAL)
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{col}"/>')
            for k in range(1, 4):
                out.append(
                    f'<line x1="{x + k*w/4:.1f}" y1="{y+2}" x2="{x + k*w/4:.1f}" y2="{y+h-2}" stroke="#000" stroke-opacity=".18" stroke-width="1"/>'
                )
    return "\n".join(out)


def crane(
    x: int, boom_left: int, name: str, trolley_cls: str, hoist_cls: str, cable_cls: str
) -> str:
    top = 330
    return f"""
  <g class="crane" fill="none">
    <!-- legs and portal -->
    <rect x="{x}" y="{top+40}" width="10" height="{680-top-40}" fill="#e0a83a"/>
    <rect x="{x+110}" y="{top+40}" width="10" height="{680-top-40}" fill="#e0a83a"/>
    <rect x="{x}" y="{top+140}" width="120" height="10" fill="#c98f28"/>
    <path d="M{x+5} {top+150} L{x+115} {top+260} M{x+115} {top+150} L{x+5} {top+260}" stroke="#c98f28" stroke-width="5"/>
    <!-- boom -->
    <rect x="{boom_left}" y="{top+30}" width="{x+170-boom_left}" height="12" fill="#e0a83a"/>
    <path d="M{x+55} {top-40} L{boom_left+20} {top+30} M{x+55} {top-40} L{x+170} {top+30}" stroke="#c98f28" stroke-width="4"/>
    <rect x="{x+40}" y="{top-50}" width="30" height="80" fill="#e0a83a"/>
    <rect x="{x+75}" y="{top+44}" width="40" height="26" fill="#f4f1ea"/>
    <rect x="{x+80}" y="{top+50}" width="30" height="8" fill="#2d4a6b"/>
    <!-- trolley, cable and container on the move -->
    <g class="{trolley_cls}">
      <rect x="{x-10}" y="{top+42}" width="36" height="12" fill="#3b4a5a"/>
      <rect class="{cable_cls}" x="{x+5}" y="{top+54}" width="3" height="130" fill="#2b3440"/>
      <g class="{hoist_cls}">
        <rect x="{x-14}" y="{top+94}" width="44" height="6" fill="#2b3440"/>
        <rect x="{x-14}" y="{top+100}" width="44" height="22" fill="{name}"/>
        <line x1="{x-3}" y1="{top+102}" x2="{x-3}" y2="{top+120}" stroke="#000" stroke-opacity=".2"/>
        <line x1="{x+8}" y1="{top+102}" x2="{x+8}" y2="{top+120}" stroke="#000" stroke-opacity=".2"/>
        <line x1="{x+19}" y1="{top+102}" x2="{x+19}" y2="{top+120}" stroke="#000" stroke-opacity=".2"/>
      </g>
    </g>
  </g>"""


def main(path: str) -> None:
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Container port at dusk: a cargo ship being loaded by gantry cranes, a customs gate and a lighthouse">
<!-- Original artwork for CustomsIQ, drawn in code (no third-party imagery).
     Every animation runs on one 5-second cycle, so the scene loops seamlessly. -->
<defs>
  <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#071830"/>
    <stop offset=".34" stop-color="#17365b"/>
    <stop offset=".52" stop-color="#40668c"/>
    <stop offset=".61" stop-color="#c9936a"/>
    <stop offset=".67" stop-color="#f1bf7c"/>
  </linearGradient>
  <linearGradient id="sea" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#2a5a82"/>
    <stop offset="1" stop-color="#071a31"/>
  </linearGradient>
  <radialGradient id="sun" cx=".5" cy=".5" r=".5">
    <stop offset="0" stop-color="#ffe2a8"/>
    <stop offset=".25" stop-color="#ffc877" stop-opacity=".9"/>
    <stop offset="1" stop-color="#ffb35c" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="beam" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#fff3c4" stop-opacity=".85"/>
    <stop offset="1" stop-color="#fff3c4" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="shade" x1="0" y1="0" x2="0" y2="1">
    <stop offset=".55" stop-color="#051226" stop-opacity="0"/>
    <stop offset="1" stop-color="#051226" stop-opacity=".55"/>
  </linearGradient>
</defs>
<style>
  .cloud {{ animation: drift 5s ease-in-out infinite alternate; }}
  .cloud.b {{ animation-duration: 5s; animation-direction: alternate-reverse; }}
  @keyframes drift {{ from {{ transform: translateX(0); }} to {{ transform: translateX(36px); }} }}
  .w1 {{ animation: flow 5s linear infinite; }}
  .w2 {{ animation: flow2 5s linear infinite; }}
  .w3 {{ animation: flow3 5s linear infinite; }}
  @keyframes flow {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-240px); }} }}
  @keyframes flow2 {{ from {{ transform: translateX(-160px); }} to {{ transform: translateX(0); }} }}
  @keyframes flow3 {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-120px); }} }}
  .ship {{ transform-box: fill-box; transform-origin: 50% 80%; animation: bob 5s ease-in-out infinite; }}
  @keyframes bob {{
    0%, 100% {{ transform: translateY(0) rotate(0deg); }}
    25% {{ transform: translateY(4px) rotate(.35deg); }}
    75% {{ transform: translateY(-3px) rotate(-.3deg); }}
  }}
  .tug {{ transform-box: fill-box; transform-origin: 50% 90%; animation: tug 5s ease-in-out infinite; }}
  @keyframes tug {{
    0%, 100% {{ transform: translate(0, 0) rotate(0deg); }}
    50% {{ transform: translate(26px, 3px) rotate(-1.2deg); }}
  }}
  .trolley {{ animation: trolley 5s ease-in-out infinite; }}
  @keyframes trolley {{ 0%, 100% {{ transform: translateX(0); }} 35%, 65% {{ transform: translateX(-190px); }} }}
  .hoist {{ animation: hoist 5s ease-in-out infinite; }}
  @keyframes hoist {{ 0%, 38%, 62%, 100% {{ transform: translateY(0); }} 50% {{ transform: translateY(92px); }} }}
  .cable {{ transform-box: fill-box; transform-origin: 50% 0; animation: cable 5s ease-in-out infinite; }}
  @keyframes cable {{ 0%, 38%, 62%, 100% {{ transform: scaleY(.31); }} 50% {{ transform: scaleY(1); }} }}
  .trolley2 {{ animation: trolley2 5s ease-in-out infinite; }}
  @keyframes trolley2 {{ 0%, 100% {{ transform: translateX(0); }} 45%, 55% {{ transform: translateX(-150px); }} }}
  .hoist2 {{ animation: hoist2 5s ease-in-out infinite; }}
  @keyframes hoist2 {{ 0%, 12%, 88%, 100% {{ transform: translateY(0); }} 50% {{ transform: translateY(60px); }} }}
  .cable2 {{ transform-box: fill-box; transform-origin: 50% 0; animation: cable2 5s ease-in-out infinite; }}
  @keyframes cable2 {{ 0%, 12%, 88%, 100% {{ transform: scaleY(.31); }} 50% {{ transform: scaleY(.77); }} }}
  .beam {{ transform-box: fill-box; transform-origin: 0 50%; animation: beam 5s ease-in-out infinite; }}
  @keyframes beam {{ 0%, 100% {{ opacity: .15; transform: scaleX(.6); }} 50% {{ opacity: .75; transform: scaleX(1); }} }}
  .lamp {{ animation: lamp 5s ease-in-out infinite; }}
  @keyframes lamp {{ 0%, 100% {{ opacity: .5; }} 50% {{ opacity: 1; }} }}
  .barrier {{ transform-box: fill-box; transform-origin: 0 50%; animation: barrier 5s ease-in-out infinite; }}
  @keyframes barrier {{ 0%, 20%, 80%, 100% {{ transform: rotate(0deg); }} 40%, 60% {{ transform: rotate(-62deg); }} }}
  .truck {{ animation: truck 5s ease-in-out infinite; }}
  @keyframes truck {{ 0%, 30% {{ transform: translateX(0); opacity: 1; }} 70% {{ transform: translateX(-150px); opacity: 1; }} 85% {{ transform: translateX(-190px); opacity: 0; }} 86%, 100% {{ transform: translateX(60px); opacity: 0; }} }}
  .gulls {{ animation: gulls 5s ease-in-out infinite; }}
  @keyframes gulls {{ 0%, 100% {{ transform: translate(0, 0); }} 50% {{ transform: translate(40px, -14px); }} }}
  .flap {{ transform-box: fill-box; transform-origin: 50% 100%; animation: flap .625s ease-in-out infinite alternate; }}
  @keyframes flap {{ from {{ transform: scaleY(1); }} to {{ transform: scaleY(.45); }} }}
  .glint {{ animation: glint 5s ease-in-out infinite; }}
  .glint.b {{ animation-delay: -2.5s; }}
  @keyframes glint {{ 0%, 100% {{ opacity: .15; }} 50% {{ opacity: .55; }} }}
  .signal {{ animation: signal 5s steps(1) infinite; }}
  @keyframes signal {{ 0%, 40% {{ fill: #e74c3c; }} 40.01%, 60% {{ fill: #2ecc71; }} 60.01%, 100% {{ fill: #e74c3c; }} }}
  @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
</style>

<rect width="{W}" height="{H}" fill="url(#sky)"/>
<circle cx="1040" cy="585" r="230" fill="url(#sun)"/>
<circle cx="1040" cy="585" r="46" fill="#ffe7b5" opacity=".95"/>

<g fill="#dfe8f3" opacity=".09">
  <g class="cloud"><ellipse cx="260" cy="170" rx="150" ry="26"/><ellipse cx="330" cy="152" rx="90" ry="24"/></g>
  <g class="cloud b"><ellipse cx="880" cy="120" rx="190" ry="24"/><ellipse cx="960" cy="104" rx="100" ry="22"/></g>
  <g class="cloud"><ellipse cx="1380" cy="210" rx="160" ry="22"/></g>
</g>

<!-- distant shore -->
<path d="M0 600 L0 572 L60 572 L60 556 L110 556 L110 578 L190 578 L190 548 L230 548 L230 566 L320 566 L320 584 L420 584 L420 574 L520 574 L520 590 L1600 590 L1600 600 Z" fill="#2b4868" opacity=".75"/>

<!-- sea -->
<rect y="598" width="{W}" height="{H-598}" fill="url(#sea)"/>
<rect class="glint" x="1000" y="620" width="80" height="4" rx="2" fill="#ffd38c"/>
<rect class="glint b" x="1010" y="640" width="60" height="3" rx="1.5" fill="#ffd38c"/>
<rect class="glint" x="990" y="664" width="100" height="3" rx="1.5" fill="#ffd38c"/>
{wave(626, 5, 240, "#2f6591", .55, "w1")}

<!-- lighthouse on the headland -->
<path d="M0 640 Q90 600 200 628 L260 660 L0 660 Z" fill="#14283f"/>
<polygon class="beam" points="118,468 520,410 520,530" fill="url(#beam)"/>
<g>
  <polygon points="100,640 136,640 128,480 108,480" fill="#f2efe8"/>
  <polygon points="104,600 132,600 131,580 105,580" fill="#c0392b"/>
  <polygon points="106,540 130,540 129,520 107,520" fill="#c0392b"/>
  <rect x="104" y="462" width="28" height="20" fill="#2b3440"/>
  <rect class="lamp" x="108" y="465" width="20" height="14" fill="#ffe9a8"/>
  <polygon points="100,462 136,462 118,446" fill="#c0392b"/>
</g>

<!-- quay, stacks and customs gate -->
<rect x="1060" y="676" width="560" height="40" fill="#15263b"/>
<rect x="1060" y="676" width="560" height="5" fill="#2d4764"/>
{containers(1330, 676, 7, 3, seed=3)}
<g>
  <rect x="1500" y="600" width="90" height="76" fill="#e9edf2"/>
  <rect x="1500" y="592" width="90" height="12" fill="#0b2545"/>
  <text x="1545" y="601" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="9" font-weight="700" fill="#e1b12c" letter-spacing="1.5">CUSTOMS</text>
  <rect x="1512" y="616" width="28" height="20" fill="#9fc3e2"/>
  <rect x="1550" y="616" width="28" height="20" fill="#9fc3e2"/>
  <rect x="1532" y="646" width="22" height="30" fill="#34506f"/>
  <circle class="signal" cx="1496" cy="626" r="5" fill="#e74c3c"/>
  <rect x="1486" y="640" width="8" height="36" fill="#34506f"/>
  <g class="barrier"><rect x="1490" y="640" width="120" height="6" fill="#f4f1ea"/><rect x="1520" y="640" width="14" height="6" fill="#c0392b"/><rect x="1560" y="640" width="14" height="6" fill="#c0392b"/></g>
</g>
<g class="truck">
  <rect x="1420" y="646" width="64" height="24" fill="#1f7a8c"/>
  <rect x="1484" y="652" width="20" height="18" fill="#e9edf2"/>
  <circle cx="1432" cy="672" r="5" fill="#111"/><circle cx="1472" cy="672" r="5" fill="#111"/><circle cx="1496" cy="672" r="5" fill="#111"/>
</g>

<!-- the ship alongside -->
<g class="ship">
  <path d="M560 672 L1110 672 L1096 736 Q1080 744 1040 744 L620 744 Q590 742 574 716 Z" fill="#12263f"/>
  <path d="M574 716 Q590 742 620 744 L1040 744 Q1080 744 1096 736 L1100 718 Z" fill="#a8322a"/>
  <rect x="560" y="672" width="550" height="4" fill="#e9edf2" opacity=".85"/>
  <text x="700" y="704" font-family="Segoe UI, Arial, sans-serif" font-size="15" font-weight="700" letter-spacing="3" fill="#e9edf2" opacity=".85">CIQ EXPRESS</text>
  {containers(612, 672, 11, 4, seed=11)}
  <rect x="1020" y="578" width="70" height="94" fill="#eef1f5"/>
  <rect x="1012" y="570" width="86" height="12" fill="#dfe4ea"/>
  <rect x="1026" y="590" width="58" height="8" fill="#2d4a6b"/>
  <rect x="1026" y="608" width="58" height="6" fill="#2d4a6b" opacity=".7"/>
  <rect x="1026" y="624" width="58" height="6" fill="#2d4a6b" opacity=".7"/>
  <rect x="1058" y="540" width="18" height="32" fill="#a8322a"/>
  <rect x="1058" y="540" width="18" height="6" fill="#12263f"/>
</g>

<!-- gantry cranes -->
{crane(1170, 900, "#e67e22", "trolley", "hoist", "cable")}
{crane(1360, 1100, "#2e6fb7", "trolley2", "hoist2", "cable2")}

<!-- tug -->
<g class="tug">
  <path d="M330 742 L440 742 L430 760 L342 760 Z" fill="#a8322a"/>
  <rect x="360" y="722" width="44" height="20" fill="#eef1f5"/>
  <rect x="366" y="727" width="32" height="6" fill="#2d4a6b"/>
  <rect x="388" y="708" width="10" height="14" fill="#12263f"/>
</g>

{wave(740, 7, 160, "#1d4a72", .8, "w2")}
{wave(790, 9, 120, "#123a60", .9, "w3")}

<g class="gulls" fill="none" stroke="#0b1d33" stroke-width="3" stroke-linecap="round">
  <path class="flap" d="M420 300 q12 -12 24 0 q12 -12 24 0"/>
  <path class="flap" d="M480 330 q9 -9 18 0 q9 -9 18 0"/>
  <path class="flap" d="M395 350 q8 -8 16 0 q8 -8 16 0"/>
</g>

<rect width="{W}" height="{H}" fill="url(#shade)"/>
</svg>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(svg)


if __name__ == "__main__":
    main(sys.argv[1])
