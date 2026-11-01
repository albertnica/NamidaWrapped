/**
 * 2026 Wrapped Deterministic Animation & Transition Engine.
 * 10-Slide Full Storyboard Orchestrator across 50.0 seconds (5.0s per slide).
 * Implements Spotify Wrapped-grade staggered layer entrance/exit animations,
 * continuous living micro-motions, and precise stage transitions driven strictly by window.seek(timeSeconds).
 * Author: Antigravity
 * Python: 3.13.12 (Pipeline Integrator)
 */

// Local hourly distribution (UTC+2 Europe/Madrid shifted, Peak dynamically loaded)
const hourlyData = (typeof window !== 'undefined' && window.CLOCK_HOURLY_DATA) || [
  66, 61, 55, 30, 25, 35, 1024, 545, 298, 251, 365, 664,
  1154, 1303, 1273, 1637, 521, 608, 983, 857, 325, 176, 89, 80
];
const maxHour = Math.max(...hourlyData) || 1;
const peakHourIndex = (typeof window !== 'undefined' && window.CLOCK_PEAK_HOUR !== undefined) ? window.CLOCK_PEAK_HOUR : 15;

// Initialize 24 clock radial rays in 680x680 stage
const raysGroup = document.getElementById('clock-rays');
if (raysGroup) {
  const cx = 340, cy = 340;
  const baseR = 138;
  const maxExt = 110;

  for (let h = 0; h < 24; h++) {
    const angle = (h / 24) * 2 * Math.PI - Math.PI / 2;
    const normVal = hourlyData[h] / maxHour;
    const targetLen = baseR + normVal * maxExt;

    // Peak hours glow with vibrant emerald
    const isPeak = (normVal >= 0.65 || h === peakHourIndex);
    const strokeColor = isPeak ? '#00ff87' : '#28382b';
    const strokeW = isPeak ? 13 : 8;

    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('id', 'clock-ray-' + h);
    line.setAttribute('x1', (cx + baseR * Math.cos(angle)).toFixed(1));
    line.setAttribute('y1', (cy + baseR * Math.sin(angle)).toFixed(1));
    line.setAttribute('x2', (cx + targetLen * Math.cos(angle)).toFixed(1));
    line.setAttribute('y2', (cy + targetLen * Math.sin(angle)).toFixed(1));
    line.setAttribute('stroke', strokeColor);
    line.setAttribute('stroke-width', strokeW);
    line.setAttribute('stroke-linecap', 'round');
    line.dataset.baseR = baseR;
    line.dataset.targetLen = targetLen;
    line.dataset.angle = angle;
    line.dataset.isPeak = isPeak ? '1' : '0';
    raysGroup.appendChild(line);
  }
}

// Populate Slide 1 EQ stream bars (28 bars)
const eqStream = document.getElementById('trio-eq-container');
if (eqStream) {
  for (let b = 0; b < 28; b++) {
    const bar = document.createElement('div');
    bar.className = 'trio-eq-bar';
    bar.id = 'trio-bar-' + b;
    eqStream.appendChild(bar);
  }
}

// Donut segment geometry constants (Circumference = 2 * PI * 38 = 238.76)
const donutSegments = [
  { id: 'donut-seg-0', len: 27.4, offset: 0.0 },
  { id: 'donut-seg-1', len: 22.9, offset: -27.4 },
  { id: 'donut-seg-2', len: 22.0, offset: -50.3 },
  { id: 'donut-seg-3', len: 17.4, offset: -72.3 },
  { id: 'donut-seg-4', len: 17.2, offset: -89.7 }
];

// Micro-meter base heights for Slide 0 bento cards (20 bars)
const microMeterBases = [
  40, 65, 100, 80, 55,
  50, 85, 100, 70, 90,
  95, 75, 60, 85, 100,
  60, 80, 70, 100, 90
];

const weekHeights = (typeof window !== 'undefined' && window.CLOCK_WEEK_HEIGHTS) || {
  'eq-sun': 175,
  'eq-mon': 125,
  'eq-tue': 130,
  'eq-wed': 235,
  'eq-thu': 165,
  'eq-fri': 155,
  'eq-sat': 195
};
const peakDayBarId = (typeof window !== 'undefined' && window.CLOCK_PEAK_DAY_ID) || 'eq-wed';

// Dynamic active panel sequence (default: all 10 panels in natural order)
let activePanels = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];

/**
 * Initializes and dynamically updates the top story progress bars and footer dots
 * to match exactly the number of panels being rendered.
 * @param {Array<number>} panels Array of panel indices (0-9)
 */
function initStoryboardPanels(panels) {
  if (Array.isArray(panels) && panels.length > 0) {
    const valid = panels.map(p => parseInt(p, 10)).filter(p => !isNaN(p) && p >= 0 && p <= 9);
    if (valid.length > 0) {
      activePanels = valid;
    }
  }

  // Populate exactly activePanels.length progress bars at the top
  const barsContainer = document.querySelector('.story-bars');
  if (barsContainer) {
    barsContainer.innerHTML = '';
    for (let i = 0; i < activePanels.length; i++) {
      const bar = document.createElement('div');
      bar.className = 'story-bar';
      const fill = document.createElement('div');
      fill.className = 'story-bar-fill';
      fill.id = 'pbar-' + i;
      bar.appendChild(fill);
      barsContainer.appendChild(bar);
    }
  }

  // Populate exactly activePanels.length footer dots at the bottom
  const dotsContainer = document.querySelector('.footer-dots');
  if (dotsContainer) {
    dotsContainer.innerHTML = '';
    for (let i = 0; i < activePanels.length; i++) {
      const dot = document.createElement('div');
      dot.className = 'f-dot';
      dot.id = 'fdot-' + i;
      dotsContainer.appendChild(dot);
    }
  }
}

// Auto-initialize from URL query if present (e.g., ?panels=3 or ?panels=3,0,5,2)
try {
  const urlParams = new URLSearchParams(window.location.search);
  const panelsQuery = urlParams.get('panels');
  if (panelsQuery) {
    const parsed = panelsQuery.split(',').map(s => parseInt(s.trim(), 10));
    initStoryboardPanels(parsed);
  } else {
    initStoryboardPanels([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
  }
} catch (e) {
  initStoryboardPanels([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
}

window.setPanels = function(panels) {
  initStoryboardPanels(panels);
  refreshTargetStats();
  window.seek(0);
};

// Read initial telemetry targets for seamless dynamic count-ups
const targetStats = {
  plays: 12425,
  mins: 32575,
  tracks: 2708,
  streak: 103,
};

/**
 * Re-reads dynamic telemetry targets from data-target attributes.
 * Why: Guarantees count-up animations accurately reflect the most recent HTML data-target values.
 */
function refreshTargetStats() {
  const elListens = document.getElementById('val-listens');
  const elTime = document.getElementById('val-time');
  const elTracks = document.getElementById('val-tracks');
  const elDays = document.getElementById('val-days');

  if (elListens && elListens.dataset && elListens.dataset.target) {
    targetStats.plays = parseInt(elListens.dataset.target, 10);
  }
  if (elTime && elTime.dataset && elTime.dataset.target) {
    targetStats.mins = parseInt(elTime.dataset.target, 10);
  }
  if (elTracks && elTracks.dataset && elTracks.dataset.target) {
    targetStats.tracks = parseInt(elTracks.dataset.target, 10);
  }
  if (elDays && elDays.dataset && elDays.dataset.target) {
    targetStats.streak = parseInt(elDays.dataset.target, 10);
  }
}
refreshTargetStats();

/**
 * Value clamping utility.
 * Why: Restricts interpolation input domain strictly to [min, max] to prevent out-of-range transforms.
 * @param {number} val Input value
 * @param {number} [min=0] Minimum value
 * @param {number} [max=1] Maximum value
 * @returns {number} Clamped value
 */
function clamp(val, min = 0, max = 1) {
  return Math.max(min, Math.min(max, val));
}

/**
 * Cubic ease-out interpolation curve.
 * Why: Provides physical deceleration for organic element arrivals.
 * @param {number} x Normalized linear progress in [0, 1]
 * @returns {number} Interpolated value with fast initial velocity and smooth stop
 */
function easeOutCubic(x) {
  return 1 - Math.pow(1 - x, 3);
}

/**
 * Cubic ease-in interpolation curve.
 * Why: Produces accelerating departure for seamless transition exits.
 * @param {number} x Normalized linear progress in [0, 1]
 * @returns {number} Interpolated value accelerating from rest
 */
function easeInCubic(x) {
  return x * x * x;
}

/**
 * Back ease-out overshoot curve.
 * Why: Produces organic mechanical elasticity for popping cards and hero badges into view.
 * @param {number} x Normalized linear progress in [0, 1]
 * @returns {number} Interpolated value with subtle overshoot before settling
 */
function easeOutBack(x) {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
}

/**
 * Thousands separator number formatter.
 * Why: Formats integers with comma separators for clean editorial presentation.
 * @param {number} num Numeric value to format
 * @returns {string} Locale-formatted numeric string with comma separators
 */
function formatNumber(num) {
  return num.toLocaleString('en-US');
}

/**
 * Universal element-level layer orchestrator for transitions.
 * Why: Applies coordinated staggered entrance and exit motion to titles, hero cards,
 * sub-grids, and footer chips so transitions feel deliberate, fluid, and cinematic.
 * @param {HTMLElement} slideEl Parent slide container
 * @param {number} timeInSlide Relative time within current slide in seconds
 * @param {number} exitProgress Normalized exit phase progress in [0, 1]
 */
function animateSlideLayers(slideEl, timeInSlide, exitProgress) {
  const titleEl = slideEl.querySelector('.anim-title');
  const heroEl = slideEl.querySelector('.anim-hero');
  const subEl = slideEl.querySelector('.anim-sub');
  const footEl = slideEl.querySelector('.anim-foot');

  const exitEase = easeInCubic(exitProgress);

  if (titleEl) {
    const tIn = easeOutCubic(clamp(timeInSlide / 0.50));
    const tOut = easeInCubic(clamp(exitProgress / 0.80));
    titleEl.style.opacity = (tIn * (1 - tOut)).toFixed(3);
    titleEl.style.transform = `translateY(${((1 - tIn) * -26 - tOut * 32).toFixed(1)}px)`;
  }

  if (heroEl) {
    const hIn = easeOutBack(clamp((timeInSlide - 0.06) / 0.54));
    const hOut = easeInCubic(clamp(exitProgress / 0.85));
    heroEl.style.opacity = (clamp(timeInSlide / 0.40) * (1 - hOut)).toFixed(3);
    heroEl.style.transform = `scale(${(0.92 + 0.08 * hIn - 0.06 * hOut).toFixed(3)}) translateY(${(-hOut * 24).toFixed(1)}px)`;
  }

  if (subEl) {
    const sIn = easeOutCubic(clamp((timeInSlide - 0.14) / 0.50));
    const sOut = easeInCubic(clamp((exitProgress - 0.04) / 0.80));
    subEl.style.opacity = (sIn * (1 - sOut)).toFixed(3);
    subEl.style.transform = `translateY(${((1 - sIn) * 32 + sOut * 34).toFixed(1)}px)`;
  }

  if (footEl) {
    const fIn = easeOutCubic(clamp((timeInSlide - 0.22) / 0.45));
    const fOut = easeInCubic(clamp(exitProgress / 0.70));
    footEl.style.opacity = (fIn * (1 - fOut)).toFixed(3);
    footEl.style.transform = `translateY(${((1 - fIn) * 18 + fOut * 20).toFixed(1)}px)`;
  }
}

const wavePath = document.getElementById('wave-path');
const waveArea = document.getElementById('wave-area');
const waveDot = document.getElementById('wave-dot');
const waveLength = wavePath ? wavePath.getTotalLength() : 1100;
if (wavePath) {
  wavePath.style.strokeDasharray = waveLength;
}

const orb1 = document.querySelector('.orb-1');
const orb2 = document.querySelector('.orb-2');
const orb3 = document.querySelector('.orb-3');
const orb4 = document.querySelector('.orb-4');

/**
 * Deterministic frame seeker for video rendering and interactive scrubbing.
 * Why: Puppeteer calls this function frame-by-frame (e.g. t = frame / fps)
 * to freeze and render exact animation states without audio drift or frame drops.
 * @param {number} t Global timeline progress in seconds [0.0, 38.0]
 */
window.seek = function(t) {
  // Ambient liquid background subtle movement
  if (orb1) {
    orb1.style.transform = `translate(${(Math.sin(t * 0.4) * 45).toFixed(1)}px, ${(Math.cos(t * 0.5) * 35).toFixed(1)}px)`;
  }
  if (orb2) {
    orb2.style.transform = `translate(${(Math.cos(t * 0.35) * 45).toFixed(1)}px, ${(Math.sin(t * 0.45) * 35).toFixed(1)}px)`;
  }
  if (orb3) {
    orb3.style.transform = `translate(${(Math.sin(t * 0.3) * -40).toFixed(1)}px, ${(Math.cos(t * 0.4) * 40).toFixed(1)}px)`;
  }
  if (orb4) {
    orb4.style.transform = `translate(${(Math.cos(t * 0.45) * 35).toFixed(1)}px, ${(Math.sin(t * 0.35) * 40).toFixed(1)}px)`;
  }

  const numPanels = activePanels.length;
  const slideDur = 5.0;
  const totalDuration = numPanels * slideDur;

  // Active step index determination across dynamic activePanels sequence
  let stepIndex = Math.min(numPanels - 1, Math.max(0, Math.floor(t / slideDur)));
  if (t >= totalDuration) stepIndex = numPanels - 1;

  const activePanelId = activePanels[stepIndex];
  const timeInSlide = Math.max(0, Math.min(slideDur, t - stepIndex * slideDur));

  // Entrance and exit phase normalization (0.65s enter, 0.55s exit)
  const enterDur = 0.65;
  const exitDur = 0.55;
  const enterProg = clamp(timeInSlide / enterDur);
  const enterEase = easeOutCubic(enterProg);

  const exitStartTime = Math.max(0, slideDur - exitDur);
  const exitProg = clamp((timeInSlide - exitStartTime) / exitDur);
  const exitEase = easeInCubic(exitProg);

  // Story top progress bars (matching exactly numPanels segments) and footer dots
  for (let i = 0; i < numPanels; i++) {
    const pbar = document.getElementById('pbar-' + i);
    if (pbar) {
      if (i < stepIndex) {
        pbar.style.width = '100%';
      } else if (i === stepIndex) {
        const segProg = clamp(timeInSlide / slideDur);
        pbar.style.width = (segProg * 100).toFixed(1) + '%';
      } else {
        pbar.style.width = '0%';
      }
    }

    const dot = document.getElementById('fdot-' + i);
    if (dot) {
      if (i === stepIndex) {
        dot.classList.add('active');
      } else {
        dot.classList.remove('active');
      }
    }
  }

  // Toggle slide visibility across all 10 slide containers (#slide-0 through #slide-9)
  for (let sId = 0; sId < 10; sId++) {
    const s = document.getElementById('slide-' + sId);
    if (s) {
      if (sId === activePanelId) {
        s.style.display = 'flex';
        // Elegant physical container drift
        const containerY = ((1 - enterEase) * 26 - exitEase * 32).toFixed(1);
        s.style.transform = `translateY(${containerY}px)`;
        s.style.opacity = (enterEase * (1 - exitEase)).toFixed(3);

        // Coordinate multi-layer element physics
        animateSlideLayers(s, timeInSlide, exitProg);
      } else {
        s.style.display = 'none';
        s.style.opacity = '0';
      }
    }
  }

  // Map activePanelId to activeIndex so all slide-specific animations execute seamlessly
  const activeIndex = activePanelId;

  // ==========================================
  // SLIDE 0: Overview (Waveform & Dancing Bento)
  // ==========================================
  if (activeIndex === 0) {
    const waveProg = Math.min(1, timeInSlide / 1.3);
    const waveEase = easeOutCubic(waveProg);
    if (wavePath) {
      wavePath.style.strokeDashoffset = waveLength * (1 - waveEase);
      if (waveArea) {
        waveArea.style.opacity = (waveEase * 0.9 * (1 - exitEase)).toFixed(2);
      }
      if (waveDot) {
        const curDist = waveLength * waveEase;
        const pt = wavePath.getPointAtLength(curDist);
        waveDot.setAttribute('cx', pt.x);
        waveDot.setAttribute('cy', pt.y);
        waveDot.setAttribute('opacity', waveProg > 0.03 && waveProg < 0.98 && exitProg < 0.8 ? '1' : '0');
      }
    }

    // Dynamic count-up calculations
    const numProg = Math.min(1, timeInSlide / 0.95);
    const numEase = easeOutCubic(numProg);

    const vListens = Math.round(targetStats.plays * numEase);
    const totMins = Math.round(targetStats.mins * numEase);
    const h = Math.floor(totMins / 60);
    const m = totMins % 60;
    const vTracks = Math.round(targetStats.tracks * numEase);
    const vDays = Math.round(targetStats.streak * numEase);

    const elListens = document.getElementById('val-listens');
    const elTime = document.getElementById('val-time');
    const elTracks = document.getElementById('val-tracks');
    const elDays = document.getElementById('val-days');

    if (elListens) elListens.innerText = formatNumber(vListens);
    if (elTime) elTime.innerText = `${h}h ${m < 10 ? '0' : ''}${m}m`;
    if (elTracks) elTracks.innerText = formatNumber(vTracks);
    if (elDays) elDays.innerText = formatNumber(vDays);

    // Living animation: 20 micro-meter bars dance dynamically
    for (let b = 0; b < 20; b++) {
      const bmb = document.getElementById('bmb-' + b);
      if (bmb) {
        const baseH = microMeterBases[b];
        const bounce = Math.sin(t * 9.5 + b * 0.75) * 22;
        const liveH = Math.max(15, Math.min(100, Math.round(baseH + bounce)));
        bmb.style.height = `${liveH}%`;
      }
    }
  }

  // ==========================================
  // SLIDE 1: Core Trio (The Big Numbers)
  // ==========================================
  if (activeIndex === 1) {
    const numEase = easeOutCubic(Math.min(1, timeInSlide / 0.95));
    const minVal = Math.round(targetStats.mins * numEase);
    const totVal = Math.round(targetStats.plays * numEase);
    const distVal = Math.round(targetStats.tracks * numEase);

    const elHeroMin = document.getElementById('trio-hero-min');
    const elTwinTot = document.getElementById('twin-tot-val');
    const elTwinDist = document.getElementById('twin-dist-val');

    if (elHeroMin) {
      elHeroMin.innerHTML = `${formatNumber(minVal)} <span style="font-size:46px;color:#1ed760;font-weight:700;">MINUTES</span>`;
    }
    if (elTwinTot) elTwinTot.innerText = formatNumber(totVal);
    if (elTwinDist) elTwinDist.innerText = formatNumber(distVal);

    // Living animation: 28 EQ stream bars bouncing with rhythm
    for (let b = 0; b < 28; b++) {
      const bEl = document.getElementById('trio-bar-' + b);
      if (bEl) {
        const waveH = 14 + 32 * (0.5 + 0.5 * Math.sin(t * 8.5 + b * 0.45));
        bEl.style.height = `${waveH.toFixed(1)}px`;
      }
    }

    // Hero card subtle breathing scale
    const heroCard = document.getElementById('s1-hero');
    if (heroCard && exitProg === 0) {
      const breath = (1 + 0.008 * Math.sin(t * 2.5)).toFixed(3);
      heroCard.style.transform = `scale(${breath})`;
    }
  }

  // ==========================================
  // SLIDE 2: Listening Clock (Radial Sweep & EQ)
  // ==========================================
  if (activeIndex === 2) {
    const centerDisc = document.getElementById('clock-center-pill');
    if (centerDisc) {
      const discProg = Math.min(1, timeInSlide / 0.6);
      const discScale = (0.5 + 0.5 * easeOutBack(discProg) - 0.08 * exitEase).toFixed(3);
      centerDisc.style.transform = `translate(-50%, -50%) scale(${discScale})`;
      centerDisc.style.opacity = (Math.min(1, timeInSlide / 0.2) * (1 - exitEase)).toFixed(3);
    }

    const cx = 340, cy = 340;
    for (let h = 0; h < 24; h++) {
      const line = document.getElementById('clock-ray-' + h);
      if (line) {
        const rayStart = (h / 24) * 0.60;
        const rayProg = clamp((timeInSlide - rayStart) / 0.35);
        const rayEase = easeOutCubic(rayProg);

        const baseR = parseFloat(line.dataset.baseR);
        const targetLen = parseFloat(line.dataset.targetLen);
        const angle = parseFloat(line.dataset.angle);
        const isPeak = line.dataset.isPeak === '1';

        // Living undulation on rays between transitions
        const rayPulse = (isPeak && exitProg === 0) ? Math.sin(t * 8.5 + h * 0.5) * 6 : 0;
        const curLen = baseR + (targetLen - baseR) * rayEase + rayPulse;

        line.setAttribute('x2', (cx + curLen * Math.cos(angle)).toFixed(1));
        line.setAttribute('y2', (cy + curLen * Math.sin(angle)).toFixed(1));
        line.setAttribute('opacity', (rayEase * (1 - exitEase)).toFixed(2));
      }
    }

    // Weekday equalizer bars
    let dayIdx = 0;
    for (const [barId, targetH] of Object.entries(weekHeights)) {
      const el = document.getElementById(barId);
      if (el) {
        const barProg = clamp((timeInSlide - (0.20 + dayIdx * 0.06)) / 0.40);
        const barEase = easeOutCubic(barProg);
        const currentH = Math.round(targetH * barEase * (1 - exitEase * 0.5));
        el.style.height = `${currentH}px`;
      }
      dayIdx++;
    }

    // Dynamic peak day glowing pulse
    const peakBar = document.getElementById(peakDayBarId);
    if (peakBar && exitProg === 0) {
      const glowRad = 12 + 6 * Math.sin(t * 5.0);
      peakBar.style.filter = `drop-shadow(0 0 ${glowRad.toFixed(1)}px rgba(0, 255, 135, 0.7))`;
    }
  }

  // ==========================================
  // SLIDE 3: Top Songs (Spinning Vinyl & Stagger)
  // ==========================================
  if (activeIndex === 3) {
    // Continuous living vinyl rotation
    const vinylDisc = document.getElementById('vinyl-disc');
    if (vinylDisc) {
      const rotDeg = (timeInSlide * 48).toFixed(1);
      vinylDisc.style.transform = `rotate(${rotDeg}deg) translateX(30px)`;
    }

    // Staggered track cards entrance & exit
    for (let tIdx = 1; tIdx <= 4; tIdx++) {
      const card = document.getElementById('t-card-' + tIdx);
      if (card) {
        const tEntryDelay = 0.12 + tIdx * 0.07;
        const tProg = clamp((timeInSlide - tEntryDelay) / 0.45);
        const tEase = easeOutCubic(tProg);

        const tExitProg = clamp((exitProg - (4 - tIdx) * 0.06) / 0.75);
        const tExitEase = easeInCubic(tExitProg);

        card.style.opacity = (tEase * (1 - tExitEase)).toFixed(3);
        card.style.transform = `translateX(${((1 - tEase) * 35 + tExitEase * 40).toFixed(1)}px)`;
      }
    }
  }

  // ==========================================
  // SLIDE 4: Top Albums (Spinning Vinyl & Stagger)
  // ==========================================
  if (activeIndex === 4) {
    const vinylDiscAlb = document.getElementById('vinyl-disc-alb');
    if (vinylDiscAlb) {
      const rotDeg = (timeInSlide * 48).toFixed(1);
      vinylDiscAlb.style.transform = `rotate(${rotDeg}deg) translateX(30px)`;
    }

    for (let aIdx = 1; aIdx <= 4; aIdx++) {
      const card = document.getElementById('alb-card-' + aIdx);
      if (card) {
        const aDelay = 0.12 + aIdx * 0.07;
        const aProg = clamp((timeInSlide - aDelay) / 0.45);
        const aEase = easeOutCubic(aProg);

        const aExitProg = clamp((exitProg - (4 - aIdx) * 0.06) / 0.75);
        const aExitEase = easeInCubic(aExitProg);

        card.style.opacity = (aEase * (1 - aExitEase)).toFixed(3);
        card.style.transform = `translateX(${((1 - aEase) * 35 + aExitEase * 40).toFixed(1)}px)`;
      }
    }
  }

  // ==========================================
  // SLIDE 5: Top Artists (Avatar Pulse & Stagger)
  // ==========================================
  if (activeIndex === 5) {
    const artHero = document.getElementById('art-hero');
    if (artHero && exitProg === 0) {
      const breath = (1 + 0.012 * Math.sin(t * 3.0)).toFixed(3);
      artHero.style.transform = `scale(${breath})`;
    }

    for (let arIdx = 1; arIdx <= 4; arIdx++) {
      const card = document.getElementById('art-card-' + arIdx);
      if (card) {
        const arDelay = 0.12 + arIdx * 0.07;
        const arProg = clamp((timeInSlide - arDelay) / 0.45);
        const arEase = easeOutCubic(arProg);

        const arExitProg = clamp((exitProg - (4 - arIdx) * 0.06) / 0.75);
        const arExitEase = easeInCubic(arExitProg);

        card.style.opacity = (arEase * (1 - arExitEase)).toFixed(3);
        card.style.transform = `translateX(${((1 - arEase) * 35 + arExitEase * 40).toFixed(1)}px)`;
      }
    }
  }

  // ==========================================
  // SLIDE 6: Top Discoveries (Avatar Pulse & Stagger)
  // ==========================================
  if (activeIndex === 6) {
    const discHero = document.getElementById('disc-hero');
    if (discHero && exitProg === 0) {
      const breath = (1 + 0.012 * Math.sin(t * 3.0)).toFixed(3);
      discHero.style.transform = `scale(${breath})`;
    }

    for (let dIdx = 1; dIdx <= 4; dIdx++) {
      const card = document.getElementById('disc-card-' + dIdx);
      if (card) {
        const dDelay = 0.12 + dIdx * 0.07;
        const dProg = clamp((timeInSlide - dDelay) / 0.45);
        const dEase = easeOutCubic(dProg);

        const dExitProg = clamp((exitProg - (4 - dIdx) * 0.06) / 0.75);
        const dExitEase = easeInCubic(dExitProg);

        card.style.opacity = (dEase * (1 - dExitEase)).toFixed(3);
        card.style.transform = `translateX(${((1 - dEase) * 35 + dExitEase * 40).toFixed(1)}px)`;
      }
    }
  }

  // ==========================================
  // SLIDE 7: Top Genres (Donut Wipe & Anthem Cards)
  // ==========================================
  if (activeIndex === 7) {
    const donutRing = document.getElementById('donut-svg-ring');
    if (donutRing) {
      const donutBreath = (1 + 0.015 * Math.sin(t * 2.2)).toFixed(3);
      const donutWobble = (Math.sin(t * 1.5) * 4).toFixed(1);
      donutRing.style.transform = `scale(${donutBreath}) rotate(${donutWobble}deg)`;
    }

    const donutWipeProg = clamp(timeInSlide / 0.85);
    const donutWipeEase = easeOutCubic(donutWipeProg);

    donutSegments.forEach(seg => {
      const circleEl = document.getElementById(seg.id);
      if (circleEl) {
        const activeLen = (seg.len * donutWipeEase).toFixed(1);
        const remain = (238.76 - activeLen).toFixed(1);
        circleEl.setAttribute('stroke-dasharray', `${activeLen} ${remain}`);
      }
    });

    for (let gIdx = 0; gIdx < 5; gIdx++) {
      const card = document.getElementById('g-anthem-' + gIdx);
      if (card) {
        const gDelay = 0.14 + gIdx * 0.07;
        const gProg = clamp((timeInSlide - gDelay) / 0.45);
        const gEase = easeOutCubic(gProg);

        const gExitProg = clamp((exitProg - gIdx * 0.05) / 0.75);
        const gExitEase = easeInCubic(gExitProg);

        card.style.opacity = (gEase * (1 - gExitEase)).toFixed(3);
        card.style.transform = `translateX(${((1 - gEase) * 30 + gExitEase * 35).toFixed(1)}px)`;
      }
    }
  }

  // ==========================================
  // SLIDE 8: Most Listened Songs (Spinning Vinyl & Stagger)
  // ==========================================
  if (activeIndex === 8) {
    const vinylDiscMlt = document.getElementById('vinyl-disc-mlt');
    if (vinylDiscMlt) {
      const rotDeg = (timeInSlide * 48).toFixed(1);
      vinylDiscMlt.style.transform = `rotate(${rotDeg}deg) translateX(30px)`;
    }

    for (let tIdx = 1; tIdx <= 4; tIdx++) {
      const card = document.getElementById('mlt-card-' + tIdx);
      if (card) {
        const tEntryDelay = 0.12 + tIdx * 0.07;
        const tProg = clamp((timeInSlide - tEntryDelay) / 0.45);
        const tEase = easeOutCubic(tProg);

        const tExitProg = clamp((exitProg - (4 - tIdx) * 0.06) / 0.75);
        const tExitEase = easeInCubic(tExitProg);

        card.style.opacity = (tEase * (1 - tExitEase)).toFixed(3);
        card.style.transform = `translateX(${((1 - tEase) * 35 + tExitEase * 40).toFixed(1)}px)`;
      }
    }
  }

  // ==========================================
  // SLIDE 9: Most Listened Artists (Avatar Pulse & Stagger)
  // ==========================================
  if (activeIndex === 9) {
    const mlaHero = document.getElementById('mla-hero');
    if (mlaHero && exitProg === 0) {
      const breath = (1 + 0.012 * Math.sin(t * 3.0)).toFixed(3);
      mlaHero.style.transform = `scale(${breath})`;
    }

    for (let arIdx = 1; arIdx <= 4; arIdx++) {
      const card = document.getElementById('mla-card-' + arIdx);
      if (card) {
        const arDelay = 0.12 + arIdx * 0.07;
        const arProg = clamp((timeInSlide - arDelay) / 0.45);
        const arEase = easeOutCubic(arProg);

        const arExitProg = clamp((exitProg - (4 - arIdx) * 0.06) / 0.75);
        const arExitEase = easeInCubic(arExitProg);

        card.style.opacity = (arEase * (1 - arExitEase)).toFixed(3);
        card.style.transform = `translateX(${((1 - arEase) * 35 + arExitEase * 40).toFixed(1)}px)`;
      }
    }
  }
};

// Initial state seek
window.seek(0);
