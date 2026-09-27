# Trilha lo-fi suave + efeitos de interface sincronizados com events.json
import json, sys
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

SR = 44100
DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 102.0
N = int(SR * DUR)
rng = np.random.default_rng(7)
L = np.zeros(N); R = np.zeros(N)

def mtof(m): return 440 * 2 ** ((m - 69) / 12)
def lp(x, f, o=2): return sosfilt(butter(o, f, 'low', fs=SR, output='sos'), x)
def hp(x, f, o=2): return sosfilt(butter(o, f, 'high', fs=SR, output='sos'), x)
def bp(x, lo, hi, o=2): return sosfilt(butter(o, [lo, hi], 'band', fs=SR, output='sos'), x)
def add(sig, t, gain=1.0, pan=0.0):
    i = int(t * SR)
    if i >= N or i + len(sig) <= 0: return
    s = sig[:max(0, N - i)]
    L[i:i + len(s)] += s * gain * (1 - pan) ** .5 / 1.0
    R[i:i + len(s)] += s * gain * (1 + pan) ** .5 / 1.0

def env(n, a, d):  # ataque linear, decaimento exponencial
    t = np.arange(n) / SR
    e = np.exp(-t / d)
    na = max(1, int(a * SR)); e[:na] *= np.linspace(0, 1, na)
    return e

BPM = 92; BEAT = 60 / BPM; BAR = 4 * BEAT
# Dmaj9 – Bm9 – Gmaj7 – A6/9 (quente e tranquilo)
CHORDS = [[50, 57, 61, 64, 66], [47, 54, 57, 61, 62], [43, 50, 54, 57, 62], [45, 52, 54, 59, 61]]
ROOTS = [38, 35, 31, 33]

# seções: tempos (s) em que a bateria some (intro, interlúdios, encerramento)
DRUM_OFF = [(0, 3.6), (48.8, 51.3), (78.4, 80.9), (95.8, DUR)]
def drums_on(t): return not any(a <= t < b for a, b in DRUM_OFF)

# --- pad
t_all = np.arange(N) / SR
pad = np.zeros(N)
nbars = int(DUR / BAR) + 1
for b in range(nbars):
    ch = CHORDS[b % 4]
    s0 = int(b * BAR * SR); n = int(BAR * SR * 1.08)
    tt = np.arange(n) / SR
    seg = np.zeros(n)
    for m in ch[1:]:
        for det in (-0.08, 0.08):
            f = mtof(m + 12) * (1 + det / 100)
            ph = rng.uniform(0, 6.28)
            seg += np.sin(2 * np.pi * f * tt + ph) + .3 * np.sin(4 * np.pi * f * tt + ph)
    e = np.minimum(1, tt / 0.6) * np.minimum(1, (n / SR - tt) / 0.5)
    seg *= e
    end = min(N, s0 + n); pad[s0:end] += seg[:end - s0]
pad = lp(pad, 1800) * 0.022
L += pad; R += pad

# --- piano elétrico (arpejo)
def epiano(f, dur=1.6, vel=1.0):
    n = int(dur * SR); tt = np.arange(n) / SR
    s = np.sin(2 * np.pi * f * tt) + .35 * np.sin(2 * np.pi * 2 * f * tt) * np.exp(-tt / .25) \
        + .12 * np.sin(2 * np.pi * 7.1 * f * tt) * np.exp(-tt / .04)
    s *= 1 + .12 * np.sin(2 * np.pi * 4.5 * tt)  # trêmolo
    return s * env(n, .004, .55) * vel
PATTERN = [0, 2, 3, 4, 3, 2, 1, 3]
for b in range(nbars):
    ch = CHORDS[b % 4]
    for k, idx in enumerate(PATTERN):
        t = b * BAR + k * BEAT / 2
        if t >= DUR - .5: break
        vel = .9 if k % 2 == 0 else .6
        f = mtof(ch[idx] + 12)
        add(epiano(f, vel=vel), t + rng.uniform(0, .012), .05, pan=(idx - 2) * .18)

# --- baixo
def bass(f, dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    s = np.tanh(1.6 * np.sin(2 * np.pi * f * tt)) * env(n, .01, .5)
    return lp(s, 400)
for b in range(nbars):
    r = ROOTS[b % 4]
    for off, d in ((0, 1.2), (2.5 * BEAT, .8)):
        t = b * BAR + off
        if t < 3.6 or t > DUR - 4: continue
        add(bass(mtof(r), d), t, .16)

# --- bateria
def kick():
    n = int(.35 * SR); tt = np.arange(n) / SR
    f = 50 + 90 * np.exp(-tt / .03)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, .001, .12)
def snap():
    n = int(.25 * SR)
    return bp(rng.standard_normal(n), 900, 4000) * env(n, .001, .06)
def hat():
    n = int(.06 * SR)
    return hp(rng.standard_normal(n), 7000) * env(n, .001, .015)
duck = np.ones(N)
for b in range(nbars):
    for k in range(8):
        t = b * BAR + k * BEAT / 2
        if t >= DUR or not drums_on(t): continue
        if k in (0, 5):
            add(kick(), t, .42)
            i = int(t * SR); n = min(N - i, int(.3 * SR))
            duck[i:i + n] = np.minimum(duck[i:i + n], 1 - .35 * np.exp(-np.arange(n) / SR / .09))
        if k in (2, 6): add(snap(), t, .10, pan=.1)
        add(hat(), t + (0.018 if k % 2 else 0), .05 if k % 2 else .08, pan=-.3)
L *= duck; R *= duck

# --- efeitos de interface
def tap():
    n = int(.05 * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * 1500 * tt) * .6 + hp(rng.standard_normal(n), 3000) * .3) * env(n, .0005, .012)
def key():
    n = int(.03 * SR)
    return hp(rng.standard_normal(n), 2500) * env(n, .0005, .006)
def whoosh(d=.55, lo=300, hi=3500):
    n = int(d * SR); x = rng.standard_normal(n)
    out = np.zeros(n); seg = n // 12
    for j in range(12):
        c = lo + (hi - lo) * (j / 11)
        out[j * seg:(j + 1) * seg + seg] = bp(x[j * seg:(j + 1) * seg + seg], c * .7, min(c * 1.4, 18000))[:len(out[j * seg:(j + 1) * seg + seg])]
    e = np.sin(np.pi * np.linspace(0, 1, n)) ** 2
    return out * e
def pop():
    n = int(.09 * SR); tt = np.arange(n) / SR
    f = 500 + 900 * tt / .09
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, .002, .03)
def ding(f1=1318, f2=1760):
    out = np.zeros(int(.6 * SR))
    for k, f in enumerate((f1, f2)):
        n = int(.45 * SR); tt = np.arange(n) / SR
        s = np.sin(2 * np.pi * f * tt) * env(n, .002, .12)
        i = int(k * .09 * SR); out[i:i + n] += s
    return out
def boom():
    n = int(1.0 * SR); tt = np.arange(n) / SR
    return np.sin(2 * np.pi * (45 + 30 * np.exp(-tt / .1)) * tt) * env(n, .005, .35)
def shimmer():
    out = np.zeros(int(3.5 * SR))
    for k, m in enumerate([74, 78, 81, 85, 88]):
        s = epiano(mtof(m), 3.0, 1.0)
        i = int(k * .07 * SR); out[i:i + len(s)] += s
    return out

evs = json.load(open(sys.argv[2] if len(sys.argv) > 2 else 'events.json'))
for e in evs:
    t = e['t'] / 1000; ty = e['type']
    if ty == 'tap': add(tap(), t + .1, .22)
    elif ty == 'key': add(key(), t, .07, pan=rng.uniform(-.2, .2))
    elif ty == 'whoosh': add(whoosh(), t - .1, .07)
    elif ty == 'pop': add(pop(), t, .12)
    elif ty == 'send': add(whoosh(.3, 800, 5000), t, .08); add(pop(), t + .05, .1)
    elif ty == 'recv': add(ding(), t, .09)
    elif ty == 'inter': add(whoosh(.9, 200, 2000), t - .2, .1); add(boom(), t, .25)
    elif ty == 'outro': add(shimmer(), t, .06); add(boom(), t, .2)

# final: fade in/out, normalização suave
fade_in = int(.8 * SR); fade_out = int(3.0 * SR)
for ch in (L, R):
    ch[:fade_in] *= np.linspace(0, 1, fade_in)
    ch[-fade_out:] *= np.linspace(1, 0, fade_out) ** 1.5
st = np.stack([L, R], 1)
st = np.tanh(st / np.max(np.abs(st)) * 1.2) * .89
wavfile.write('audio.wav', SR, (st * 32767).astype(np.int16))
print('ok', DUR, len(evs), 'eventos')
