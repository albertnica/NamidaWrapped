/**
 * 2026 Wrapped Web Studio Client Application.
 * Manages terminal interactive panels, instant FLAC extraction, segmented preview slices,
 * native Windows Explorer save dialog, and custom real-time video rendering.
 * Author: Antigravity
 * Python: 3.13.12 (Pipeline Backend)
 */

let appState = {
  currentPanel: 0,
  completedPanels: [],
  curation: {},
  playbackScope: 'single', // 'single' (isolated panel slice) | 'cumulative' (from 0 to current)
  maxTimelineSec: 5.0,
  currentTimeSec: 0,
  isPlaying: true,
  isDraggingSlider: false,
  previewMode: 'live', // 'live' | 'video'
  previewFps: 1,
  isRenderingLocked: false,
  isPreviewMuted: false,
  audioTrackDuration: 50.0,
  currentAudioStreamKey: null,
  miniPlayerAuditioning: false,
  miniPlayerAuditionElapsed: 0.0,
  isDraggingMiniSlider: false,
  renderPollInterval: null,
  videoSliceUrl: null,
  singleSliceUrl: null,
  slicesOrder: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
  selectedSlices: new Set([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
  telemetryBaselines: null,
  theme: { id: 'aurora', primary: '#00ff87', secondary: '#7928ca', accent: '#ff007a' }
};

// Ambient Background Theme Presets
const THEME_PRESETS = {
  aurora: {
    name: 'Spotify Aurora',
    primary: '#00ff87',
    secondary: '#7928ca',
    accent: '#ff007a',
    tertiary: '#00d4ff',
    bg_base: '#030604',
    bg_mid: '#0c2616',
    bg_outer: '#07140b'
  },
  cyberpunk: {
    name: 'Cyberpunk Neon',
    primary: '#a855f7',
    secondary: '#ff007a',
    accent: '#00f5ff',
    tertiary: '#3b82f6',
    bg_base: '#08040d',
    bg_mid: '#200833',
    bg_outer: '#10051a'
  },
  sunset: {
    name: 'Sunset Solstice',
    primary: '#ff7a00',
    secondary: '#ff0055',
    accent: '#ffb800',
    tertiary: '#7928ca',
    bg_base: '#0c0406',
    bg_mid: '#260b13',
    bg_outer: '#16060c'
  },
  midnight: {
    name: 'Midnight Abyss',
    primary: '#00d4ff',
    secondary: '#6366f1',
    accent: '#8b5cf6',
    tertiary: '#06b6d4',
    bg_base: '#030712',
    bg_mid: '#0f172a',
    bg_outer: '#070c18'
  },
  acid: {
    name: 'Acid Matrix',
    primary: '#a3e635',
    secondary: '#10b981',
    accent: '#eab308',
    tertiary: '#06b6d4',
    bg_base: '#050904',
    bg_mid: '#14240f',
    bg_outer: '#0b1408'
  }
};

// Panel Metadata Configurations
const PANELS = [
  { id: 0, name: "Your Year in Sound", tab: "1. Sound", dur: 5.0 },
  { id: 1, name: "The Big Numbers", tab: "2. Big Numbers", dur: 5.0 },
  { id: 2, name: "Listening Clock", tab: "3. Clock", dur: 5.0 },
  { id: 3, name: "Top Songs", tab: "4. Songs", dur: 5.0 },
  { id: 4, name: "Top Albums", tab: "5. Albums", dur: 5.0 },
  { id: 5, name: "Top Artists", tab: "6. Artists", dur: 5.0 },
  { id: 6, name: "Top Discoveries", tab: "7. Discoveries", dur: 5.0 },
  { id: 7, name: "Top Genres", tab: "8. Genres", dur: 5.0 },
  { id: 8, name: "Most Listened Songs", tab: "9. Listened Songs", dur: 5.0 },
  { id: 9, name: "Most Listened Artists", tab: "10. Listened Artists", dur: 5.0 }
];

document.addEventListener('DOMContentLoaded', async () => {
  initRenderPageLockGuards();
  initPhonePreviewScale();
  await fetchStatus();
  initTabs();
  initPlayerControls();
  initPanelAutoSync();
  renderPanelForm(appState.currentPanel);
  renderComposerDrawer();
  startPlaybackLoop();
});

/**
 * Initializes and switches smartphone preview mockup scaling.
 * Why: Allows users on high-res monitors to scale up the preview by 30-45% for clear readability.
 */
function initPhonePreviewScale() {
  const saved = localStorage.getItem('namida_phone_scale') || 'medium';
  setPhonePreviewScale(saved);
}

function setPhonePreviewScale(preset) {
  const root = document.documentElement;
  let scale = 0.38888889;
  let width = 420;
  let height = 746.67;

  if (preset === 'standard') {
    scale = 0.33333333;
    width = 360;
    height = 640;
  } else if (preset === 'large') {
    scale = 0.44444444;
    width = 480;
    height = 853.33;
  } else {
    preset = 'medium';
  }

  root.style.setProperty('--phone-scale', scale);
  root.style.setProperty('--phone-width', `${width}px`);
  root.style.setProperty('--phone-height', `${height}px`);

  document.querySelectorAll('.zoom-btn').forEach(btn => btn.classList.remove('active'));
  const activeBtn = document.getElementById(`btn-zoom-${width}`);
  if (activeBtn) activeBtn.classList.add('active');

  try {
    localStorage.setItem('namida_phone_scale', preset);
  } catch (e) {}
}

/**
 * Blocks keyboard and pointer events across the entire window while rendering is active.
 * Why: Guarantees the user cannot interact with inputs or trigger duplicate actions via keyboard shortcuts.
 */
function initRenderPageLockGuards() {
  const blockIfLocked = (e) => {
    if (appState.isRenderingLocked) {
      e.preventDefault();
      e.stopPropagation();
    }
  };
  window.addEventListener('keydown', blockIfLocked, true);
  window.addEventListener('keypress', blockIfLocked, true);
  window.addEventListener('submit', blockIfLocked, true);
}

/**
 * Loads current state and video URLs from backend.
 */
async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    appState.currentPanel = data.current_panel;
    appState.completedPanels = data.completed_panels || [];
    appState.curation = data.curation_data || {};
    appState.telemetryBaselines = data.telemetry_baselines || null;
    appState.videoSliceUrl = data.video_slice_url;
    appState.singleSliceUrl = data.single_slice_url;

    // Display active telemetry backup archive from files/
    if (appState.telemetryBaselines && appState.telemetryBaselines.source_archive) {
      const src = appState.telemetryBaselines.source_archive;
      const label = document.getElementById('source-archive-text');
      if (label && src.name) {
        label.textContent = `files/${src.name}`;
      }
      const pill = document.getElementById('source-archive-pill');
      if (pill && src.name) {
        pill.title = `Active backup: files/${src.name} (${src.mtime || 'latest'})\nClick to re-sync files/`;
      }
    }

    if (appState.curation && appState.curation.theme) {
      appState.theme = appState.curation.theme;
      syncThemeUI(appState.theme);
    } else {
      fetch('/api/theme').then(r => r.json()).then(t => {
        appState.theme = t;
        syncThemeUI(t);
      }).catch(() => {});
    }

    const loadedFps = parseInt(data.preview_fps || (appState.curation && appState.curation.preview_fps) || 1, 10);
    appState.previewFps = isNaN(loadedFps) ? 1 : Math.max(1, Math.min(60, loadedFps));
    syncPreviewFpsUI();

    if (appState.playbackScope === 'single') {
      appState.maxTimelineSec = 5.0;
    } else {
      appState.maxTimelineSec = data.duration_up_to_current || 5.0;
    }

    updateHeader();
    updateTabsUI();
    updateTimelineUI();
    syncVideoSource();

    if (data.is_rendering && !appState.isRenderingLocked) {
      showRenderOverlay({
        badge: 'RENDER IN PROGRESS',
        title: 'Rendering Video...',
        subtitle: 'Waiting for active Chromium & FFmpeg render task to complete',
        path: null
      });
      pollRenderStatus('Active Video Render');
    }
  } catch (err) {
    console.error('Failed to load status:', err);
  }
}

/**
 * Triggers re-synchronization with the newest backup in files/ and reloads the preview.
 * @param {Event} [e] Click event
 */
async function syncLatestBackup(e) {
  if (e && typeof e.stopPropagation === 'function') {
    e.stopPropagation();
  }
  const label = document.getElementById('source-archive-text');
  const origText = label ? label.textContent : '';
  if (label) label.textContent = 'Syncing files/...';
  try {
    const resp = await fetch('/api/studio/sync-backup?force=true', { method: 'POST' });
    const res = await resp.json();
    showToast(res.message || 'Backup synchronized', 'success');
    await fetchStatus();
    reloadIframePreview();
  } catch (err) {
    if (label) label.textContent = origText;
    showToast('Failed to sync backup: ' + err, 'error');
  }
}

/**
 * Toggles visibility of the theme dropdown menu.
 * @param {Event} [e] Click event
 */
function toggleThemeDropdown(e) {
  if (e && typeof e.stopPropagation === 'function') {
    e.stopPropagation();
  }
  const menu = document.getElementById('theme-dropdown-menu');
  if (menu) {
    menu.classList.toggle('hidden');
  }
}

// Close theme dropdown when clicking outside
document.addEventListener('click', (e) => {
  const menu = document.getElementById('theme-dropdown-menu');
  const trigger = document.getElementById('btn-theme-selector');
  if (menu && !menu.classList.contains('hidden')) {
    if (!menu.contains(e.target) && trigger && !trigger.contains(e.target)) {
      menu.classList.add('hidden');
    }
  }
});

/**
 * Applies a theme preset and sends update to the backend.
 * @param {string} themeId Identifier of the preset
 */
async function applyThemePreset(themeId) {
  const preset = THEME_PRESETS[themeId];
  if (!preset) return;

  const payload = {
    id: themeId,
    primary: preset.primary,
    secondary: preset.secondary,
    accent: preset.accent,
    tertiary: preset.tertiary,
    bg_base: preset.bg_base,
    bg_mid: preset.bg_mid,
    bg_outer: preset.bg_outer
  };

  await saveThemeToBackend(payload);
}

/**
 * Handles custom color input changes from native color pickers.
 */
async function onCustomColorInputChange() {
  const inpPri = document.getElementById('theme-inp-primary');
  const inpSec = document.getElementById('theme-inp-secondary');
  const inpAcc = document.getElementById('theme-inp-accent');

  const payload = {
    id: 'custom',
    primary: inpPri ? inpPri.value : '#00ff87',
    secondary: inpSec ? inpSec.value : '#7928ca',
    accent: inpAcc ? inpAcc.value : '#ff007a',
    tertiary: '#00d4ff',
    bg_base: '#040605',
    bg_mid: '#0f1712',
    bg_outer: '#080c09'
  };

  await saveThemeToBackend(payload);
}

/**
 * Sends theme payload to /api/theme, syncs UI indicators, and reloads iframe preview.
 * @param {Object} themeData Theme payload
 */
async function saveThemeToBackend(themeData) {
  try {
    const res = await fetch('/api/theme', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(themeData)
    });
    const updated = await res.json();
    appState.theme = updated;
    syncThemeUI(updated);

    // Reload iframe preview to immediately reflect new palette
    const iframe = document.getElementById('story-iframe');
    if (iframe) {
      const panelsParam = appState.playbackScope === 'single' ? `&panels=${appState.currentPanel}` : '';
      iframe.src = `/story?t=${Date.now()}${panelsParam}`;
    }
    showToast(`Palette applied: ${THEME_PRESETS[updated.id] ? THEME_PRESETS[updated.id].name : 'Custom Glow'}`);
  } catch (err) {
    console.error('Failed to update theme:', err);
  }
}

/**
 * Synchronizes header pill dot, label, active buttons, and color input values.
 * @param {Object} theme Theme configuration
 */
function syncThemeUI(theme) {
  if (!theme) return;
  const dot = document.getElementById('theme-swatch-dot');
  const label = document.getElementById('theme-name-label');
  const inpPri = document.getElementById('theme-inp-primary');
  const inpSec = document.getElementById('theme-inp-secondary');
  const inpAcc = document.getElementById('theme-inp-accent');

  const preset = THEME_PRESETS[theme.id];
  const displayName = preset ? preset.name : 'Custom Palette';

  if (dot) dot.style.background = theme.primary || '#00ff87';
  if (label) label.textContent = displayName;

  if (inpPri && theme.primary) inpPri.value = theme.primary;
  if (inpSec && theme.secondary) inpSec.value = theme.secondary;
  if (inpAcc && theme.accent) inpAcc.value = theme.accent;

  // Sync active class on preset buttons
  document.querySelectorAll('.theme-option-btn').forEach(btn => {
    if (btn.dataset.themeId === theme.id) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  // Also subtly sync studio ambient bg orbs
  const rootStyle = document.documentElement.style;
  if (theme.primary) rootStyle.setProperty('--spotify-mint', theme.primary);
}

/**
 * Synchronizes the HTML5 video element source based on current playback scope.
 * Why: Only sets initial source if empty or when force is explicitly set,
 * guaranteeing the right-side video player stays stable unless rendered or saved.
 * @param {boolean} [force=false] Whether to force reload the video source
 */
function syncVideoSource(force = false) {
  const vid = document.getElementById('slice-video');
  const src = document.getElementById('slice-video-src');
  if (!src || !vid) return;

  const currentSrc = src.getAttribute('src');
  if (!force && currentSrc && currentSrc.trim() !== '') {
    return;
  }

  let chosenUrl = null;
  if (appState.playbackScope === 'single' && appState.singleSliceUrl) {
    chosenUrl = appState.singleSliceUrl;
  } else if (appState.videoSliceUrl) {
    chosenUrl = appState.videoSliceUrl;
  }

  if (chosenUrl) {
    src.src = `${chosenUrl}?t=${Date.now()}`;
    vid.load();
  }
}

/**
 * Initializes tab event listeners.
 */
function initTabs() {
  const tabs = document.querySelectorAll('.tab-btn');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const pid = parseInt(tab.dataset.id, 10);
      switchPanel(pid);
    });
  });
}

/**
 * Automatically syncs form edits to the backend when fields lose focus or change.
 * Why: Guarantees that typing in any curation field immediately saves and recompiles the story.
 */
function initPanelAutoSync() {
  const container = document.getElementById('panel-form-container');
  if (container) {
    container.addEventListener('change', async (e) => {
      if (!e.target || !e.target.matches('input, select, textarea')) return;
      // FLAC path inputs are handled by bindFLACAutoloaders which extracts metadata first
      if (e.target.classList.contains('flac-path-input')) return;
      // Slide audio mini-player inputs handle their own real-time sync without reloading visual iframe
      if (
        e.target.id === 'inp-slide-audio-slider' ||
        e.target.id === 'inp-slide-audio-start' ||
        e.target.id === 'inp-slide-audio-path' ||
        e.target.id === 'inp-slide-audio-volume'
      ) {
        return;
      }
      await submitCurrentPanel();
    });
  }
}

function updateTabsUI() {
  const tabs = document.querySelectorAll('.tab-btn');
  tabs.forEach(tab => {
    const pid = parseInt(tab.dataset.id, 10);
    tab.classList.toggle('active', pid === appState.currentPanel);
    tab.classList.toggle('completed', appState.completedPanels.includes(pid));
  });
}

function updateHeader() {
  const p = PANELS[appState.currentPanel] || PANELS[0];
  const stepEl = document.getElementById('top-step-indicator');
  const idxEl = document.getElementById('lbl-panel-idx');
  const durEl = document.getElementById('lbl-timeline-dur');
  if (stepEl) stepEl.innerText = `Step ${p.id + 1} of ${PANELS.length}: ${p.name}`;
  if (idxEl) idxEl.innerText = `${p.id + 1}`;
  if (durEl) {
    durEl.innerText = appState.playbackScope === 'single' ? '5.0s (Solo)' : `${((p.id + 1) * 5.0).toFixed(1)}s (Total)`;
  }
}

function updateTimelineUI() {
  const slider = document.getElementById('timeline-slider');
  if (slider) {
    slider.max = appState.maxTimelineSec;
    slider.value = appState.currentTimeSec;
  }
  const timeDisplay = document.getElementById('time-display');
  if (timeDisplay) {
    timeDisplay.innerText = `${appState.currentTimeSec.toFixed(1)}s / ${appState.maxTimelineSec.toFixed(1)}s`;
  }
}

/**
 * Toggles preview scope between 'single' panel slice and 'cumulative' from start.
 * @param {'single'|'cumulative'} scope Target scope
 */
function setPlaybackScope(scope) {
  appState.playbackScope = scope;
  const btnSingle = document.getElementById('btn-scope-single');
  const btnAll = document.getElementById('btn-scope-all');
  const scopeTag = document.getElementById('lbl-scope-tag');

  if (btnSingle) btnSingle.classList.toggle('active', scope === 'single');
  if (btnAll) btnAll.classList.toggle('active', scope === 'cumulative');

  if (scope === 'single') {
    appState.maxTimelineSec = 5.0;
    if (scopeTag) scopeTag.innerHTML = `• PANEL SOLO: <b>5.0s</b>`;
  } else {
    appState.maxTimelineSec = roundNumber((appState.currentPanel + 1) * 5.0, 2);
    if (scopeTag) scopeTag.innerHTML = `• FROM START: <b>${appState.maxTimelineSec.toFixed(1)}s</b>`;
  }

  // Update live preview story bars to match scope
  const iframe = document.getElementById('story-iframe');
  if (iframe && iframe.contentWindow && typeof iframe.contentWindow.setPanels === 'function') {
    if (scope === 'single') {
      iframe.contentWindow.setPanels([appState.currentPanel]);
    } else {
      iframe.contentWindow.setPanels([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
    }
  }

  updateHeader();
  updateTimelineUI();
  seekToTime(0);
}

function roundNumber(num, dec) {
  return Math.round(num * Math.pow(10, dec)) / Math.pow(10, dec);
}

let autoRenderDebounceTimer = null;

/**
 * Automatically triggers 1 FPS isolated preview rendering for the active panel upon selection.
 * Why: Renders the active slice deterministically in ~1.0s and loads it directly into the video player.
 * @param {number} panelId Index of the panel to render
 */
function triggerAutoSliceRender(panelId) {
  if (autoRenderDebounceTimer) {
    clearTimeout(autoRenderDebounceTimer);
  }
  autoRenderDebounceTimer = setTimeout(async () => {
    try {
      const stRes = await fetch('/api/status');
      const stData = await stRes.json();
      if (stData.is_rendering) {
        return;
      }
    } catch (e) {}

    await renderIsolatedSlice(panelId);
  }, 200);
}

/**
 * Switches current active panel tab and automatically triggers 1 FPS slice render.
 * @param {number} panelId Index of the panel (0-9)
 */
async function switchPanel(panelId) {
  const prevPanel = appState.currentPanel;
  let prevPayload = null;
  if (prevPanel !== undefined && prevPanel !== null && prevPanel !== panelId) {
    try {
      prevPayload = collectCurrentPanelData(prevPanel);
    } catch (e) {}
  }

  appState.currentPanel = panelId;
  appState.miniPlayerAuditioning = false;
  appState.miniPlayerAuditionElapsed = 0.0;
  
  if (appState.playbackScope === 'single') {
    appState.maxTimelineSec = 5.0;
  } else {
    appState.maxTimelineSec = roundNumber((panelId + 1) * 5.0, 2);
  }

  updateHeader();
  updateTabsUI();
  updateTimelineUI();
  renderPanelForm(panelId);
  seekToTime(0);

  if (prevPayload !== null) {
    fetch(`/api/panels/${prevPanel}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ panel_id: prevPanel, data: prevPayload })
    }).then(r => r.json()).then(st => {
      if (st && st.completed_panels) {
        appState.completedPanels = st.completed_panels;
        updateTabsUI();
      }
    }).catch(() => {});
  }

  // Sync iframe preview to this specific panel immediately
  const iframe = document.getElementById('story-iframe');
  if (iframe) {
    const panelsParam = appState.playbackScope === 'single' ? `&panels=${panelId}` : '';
    iframe.src = `/story?t=${Date.now()}${panelsParam}`;
  }

  // Pre-load video source if slice for this panel already exists on disk
  const vid = document.getElementById('slice-video');
  const src = document.getElementById('slice-video-src');

  try {
    const res = await fetch(`/api/panels/${panelId}/goto`, { method: 'POST' });
    const data = await res.json();
    appState.singleSliceUrl = data.single_slice_url;
    appState.videoSliceUrl = data.video_slice_url;

    if (data.single_slice_url && vid && src) {
      src.src = `${data.single_slice_url}?t=${Date.now()}`;
      vid.load();
      vid.play().catch(() => {});
    }
  } catch (err) {}

  // Automatically render the isolated slice at 1 FPS for immediate visual preview
  triggerAutoSliceRender(panelId);
}

/**
 * Renders the interactive terminal prompt form corresponding to panelId.
 */
function renderPanelForm(panelId) {
  const container = document.getElementById('panel-form-container');
  if (!container) return;
  const cur = appState.curation || {};

  if (panelId === 0) {
    const sp = cur.spotify_additions || {};
    container.innerHTML = `
      <div class="form-section-title">1. Your Year in Sound</div>
      <div class="form-section-desc">Add additional Spotify listening time to merge into your annual summary totals.</div>

      <div class="form-row-2">
        <div class="form-group">
          <label class="form-label">Spotify Additional Minutes</label>
          <input type="number" class="form-input" id="inp-sp-mins" value="${sp.extra_minutes !== undefined ? sp.extra_minutes : 0}" placeholder="e.g. 5200">
        </div>
        <div class="form-group">
          <label class="form-label">Spotify Additional Plays</label>
          <input type="number" class="form-input" id="inp-sp-plays" value="${sp.extra_plays !== undefined ? sp.extra_plays : 0}" placeholder="e.g. 1850">
        </div>
      </div>

      <div class="form-row-2">
        <div class="form-group">
          <label class="form-label">Spotify Additional Unique Songs</label>
          <input type="number" class="form-input" id="inp-sp-songs" value="${sp.extra_songs !== undefined ? sp.extra_songs : 0}" placeholder="e.g. 640">
        </div>
        <div class="form-group">
          <label class="form-label">Longest Listening Streak (Days)</label>
          <input type="number" class="form-input" id="inp-sp-streak" value="${sp.streak_days !== undefined ? sp.streak_days : 103}" placeholder="103">
        </div>
      </div>
      ${renderSlideAudioWidget(panelId)}
    `;
  } else if (panelId === 1) {
    const bn = cur.big_numbers || {};
    container.innerHTML = `
      <div class="form-section-title">2. The Big Numbers</div>
      <div class="form-section-desc">Showing Daily Average & Worldwide Top 1% Dedicated Listener.</div>

      <div class="form-group">
        <label class="form-label">Daily Average Metric Note</label>
        <input type="text" class="form-input" id="inp-bn-note" value="${bn.note || 'Automated: Merged Namida + Spotify Daily Flow'}" placeholder="Custom note...">
      </div>
      <div class="form-group">
        <label class="form-label">Worldwide Listener Tier Pill</label>
        <input type="text" class="form-input" id="inp-bn-tier" value="${bn.tier || 'TOP 1% WORLDWIDE'}" placeholder="TOP 1%...">
      </div>
      ${renderSlideAudioWidget(panelId)}
    `;
  } else if (panelId === 2) {
    const clk = cur.listening_clock || {};
    const curWork = clk.workday_extra_minutes !== undefined ? clk.workday_extra_minutes : (clk.work_hours_minutes_total !== undefined ? clk.work_hours_minutes_total : 15000);
    const curSat = clk.saturday_extra_minutes !== undefined ? clk.saturday_extra_minutes : 1450;
    container.innerHTML = `
      <div class="form-section-title">3. Listening Clock (Habits & Routine)</div>
      <div class="form-section-desc">Spotify working hours (7 AM – 3 PM) ray distribution and Saturday weekly release spikes.</div>

      <div class="form-group">
        <label class="form-label">Workday Extra Minutes (Equidistributed 7:00 AM – 3:00 PM)</label>
        <input type="number" class="form-input" id="inp-clk-work" value="${curWork}" placeholder="e.g. 15000">
      </div>
      <div class="form-group">
        <label class="form-label">Saturday Extra Minutes (Weekend Releases Spike)</label>
        <input type="number" class="form-input" id="inp-clk-sat" value="${curSat}" placeholder="e.g. 1450">
      </div>
      ${renderSlideAudioWidget(panelId)}
    `;
  } else if (panelId === 3) {
    const songs = cur.top_songs || [];
    container.innerHTML = `
      <div class="form-section-title">4. Top Songs (Curated 1 to 5)</div>
      <div class="form-section-desc">Enter local audio paths. Tags & embedded front covers are extracted automatically.</div>
      <div id="songs-list-container">
        ${[0, 1, 2, 3, 4].map(i => renderCuratedItemInput('song', i + 1, songs[i] || {})).join('')}
      </div>
      ${renderSlideAudioWidget(panelId)}
    `;
    bindFLACAutoloaders('song');
  } else if (panelId === 4) {
    const albums = cur.top_albums || [];
    container.innerHTML = `
      <div class="form-section-title">5. Top Albums (Curated 1 to 5)</div>
      <div class="form-section-desc">Enter local audio paths or album titles. Cover art is resolved automatically.</div>
      <div id="albums-list-container">
        ${[0, 1, 2, 3, 4].map(i => renderCuratedItemInput('album', i + 1, albums[i] || {})).join('')}
      </div>
      ${renderSlideAudioWidget(panelId)}
    `;
    bindFLACAutoloaders('album');
  } else if (panelId === 5) {
    const artists = cur.top_artists || [];
    container.innerHTML = `
      <div class="form-section-title">6. Top Artists (Curated 1 to 5)</div>
      <div class="form-section-desc">Enter creator names. Artist portraits are resolved automatically from Namida.</div>
      <div id="artists-list-container">
        ${[0, 1, 2, 3, 4].map(i => renderSimpleCreatorInput('artist', i + 1, artists[i] || {})).join('')}
      </div>
      ${renderSlideAudioWidget(panelId)}
    `;
  } else if (panelId === 6) {
    const disc = cur.top_discoveries || [];
    container.innerHTML = `
      <div class="form-section-title">7. Top Discoveries (Curated 1 to 5)</div>
      <div class="form-section-desc">5 newly discovered artists you fell in love with this year.</div>
      <div id="discoveries-list-container">
        ${[0, 1, 2, 3, 4].map(i => renderSimpleCreatorInput('discovery', i + 1, disc[i] || {})).join('')}
      </div>
      ${renderSlideAudioWidget(panelId)}
    `;
  } else if (panelId === 7) {
    const genres = cur.top_genres || [];
    container.innerHTML = `
      <div class="form-section-title">8. Top Genres</div>
      <div class="form-section-desc">Enter your top 5 genres, representative tracks, and artists or local audio paths. Tags & artwork are extracted automatically.</div>
      <div id="genres-list-container">
        ${[0, 1, 2, 3, 4].map(i => renderGenreItemInput(i + 1, genres[i] || {})).join('')}
      </div>
      ${renderSlideAudioWidget(panelId)}
    `;
    bindFLACAutoloaders('genre');
  } else if (panelId === 8) {
    const rawTracks = (appState.telemetryBaselines && appState.telemetryBaselines.top_tracks) || [
      { rank: 1, title: "sorry im a haunted house", artist: "Savage Ga$p, KAMAARA", plays: 69, total_listen_minutes: 169.0 },
      { rank: 2, title: "WITCHCRAFT", artist: "AntXres, SCXR SOUL, Ethan Ross, Jupiluxe", plays: 68, total_listen_minutes: 167.1 },
      { rank: 3, title: "FULL SEND RMX", artist: "BLXCKBUSTA, Ethan Ross", plays: 60, total_listen_minutes: 137.9 },
      { rank: 4, title: "BACKSTAGE", artist: "GOTOU寄生獣, vodvor", plays: 59, total_listen_minutes: 106.1 },
      { rank: 5, title: "I'll Come Runnin", artist: "ILLENIUM, Zeds Dead, Mako", plays: 57, total_listen_minutes: 211.0 }
    ];

    const cardsHtml = rawTracks.slice(0, 5).map((t, idx) => {
      const thumbSrc = t.image || (t.artwork_path ? `/output/${t.artwork_path}` : DEFAULT_THUMB_SVG);
      return `
        <div class="curated-card-input" style="align-items:center;padding:12px 14px;margin-bottom:8px;background:rgba(255,255,255,0.03);border:1px solid rgba(0,255,135,0.18);">
          <div class="curated-rank" style="margin:0 12px 0 0;">${idx + 1}</div>
          <img class="curated-thumb" style="width:44px;height:44px;border-radius:8px;object-fit:cover;margin-right:12px;border:1px solid rgba(0,255,135,0.3);flex-shrink:0;" src="${thumbSrc}" alt="${t.title}" onerror="this.src=DEFAULT_THUMB_SVG">
          <div style="flex:1;min-width:0;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <div style="font-weight:700;font-size:14px;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-right:8px;">${t.title}</div>
              <span class="t-green" style="font-size:12px;font-weight:700;white-space:nowrap;">⚡ ${t.plays} plays</span>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-top:4px;">
              <div style="font-size:12px;color:#a4bba6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-right:8px;">${t.artist}</div>
              <span style="font-size:11px;color:#8fa592;white-space:nowrap;">⏱️ ${t.total_listen_minutes} minutes</span>
            </div>
          </div>
        </div>
      `;
    }).join('');

    container.innerHTML = `
      <div class="form-section-title">9. Most Listened Songs (Namida Telemetry)</div>
      <div style="display:inline-block;margin-bottom:12px;padding:3px 10px;background:rgba(0,255,135,0.1);border:1px solid rgba(0,255,135,0.3);border-radius:12px;font-size:11px;color:#00ff87;font-weight:600;">
        🔒 Automated Namida Telemetry • Read-only
      </div>
      <div class="form-section-desc">Authentic unalterable playback history directly extracted from your Namida database.</div>
      <div id="ml-songs-container">
        ${cardsHtml}
      </div>
      ${renderSlideAudioWidget(panelId)}
    `;
  } else if (panelId === 9) {
    const rawArtists = (appState.telemetryBaselines && appState.telemetryBaselines.top_artists) || [
      { artist: "GOTOU寄生獣, vodvor", plays: 675, estimated_minutes: 1445 },
      { artist: "RJ Pasin", plays: 428, estimated_minutes: 1106 },
      { artist: "Daegho", plays: 211, estimated_minutes: 566 },
      { artist: "Savage Ga$p", plays: 195, estimated_minutes: 610 },
      { artist: "MUPP", plays: 185, estimated_minutes: 331 }
    ];

    const cardsHtml = rawArtists.slice(0, 5).map((a, idx) => {
      const minsVal = a.estimated_minutes || Math.round((a.plays || 0) * 2.8);
      const avatarSrc = a.image || DEFAULT_THUMB_SVG;
      return `
        <div class="curated-card-input" style="align-items:center;padding:12px 14px;margin-bottom:8px;background:rgba(255,255,255,0.03);border:1px solid rgba(168,85,247,0.22);">
          <div class="curated-rank" style="margin:0 12px 0 0;">${idx + 1}</div>
          <img class="curated-thumb" style="border-radius:50%;width:42px;height:42px;margin-right:12px;object-fit:cover;border:1.5px solid #a855f7;" src="${avatarSrc}" alt="${a.artist}">
          <div style="flex:1;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <div style="font-weight:700;font-size:14px;color:#fff;">${a.artist}</div>
              <span class="t-green" style="font-size:12px;font-weight:700;">⚡ ${a.plays} plays</span>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-top:4px;">
              <div style="font-size:11px;color:#d8b4fe;">Top Creator</div>
              <span style="font-size:11px;color:#8fa592;">⏱️ ~${minsVal} minutes</span>
            </div>
          </div>
        </div>
      `;
    }).join('');

    container.innerHTML = `
      <div class="form-section-title">10. Most Listened Artists (Namida Telemetry)</div>
      <div style="display:inline-block;margin-bottom:12px;padding:3px 10px;background:rgba(168,85,247,0.15);border:1px solid rgba(168,85,247,0.35);border-radius:12px;font-size:11px;color:#d8b4fe;font-weight:600;">
        🔒 Automated Namida Telemetry • Read-only
      </div>
      <div class="form-section-desc">Authentic unalterable top streamed creators and photos extracted directly from Namida.</div>
      <div id="ml-artists-container">
        ${cardsHtml}
      </div>
      ${renderSlideAudioWidget(panelId)}
    `;
  }

  // Synchronize footer button text
  const btnSaveRender = document.getElementById('btn-save-render-slice');
  const btnSaveNext = document.getElementById('btn-save-next-slice');
  if (btnSaveRender && btnSaveNext) {
    if (panelId === 8 || panelId === 9) {
      btnSaveRender.innerText = '🎬 Render Slice Preview (1 FPS)';
      btnSaveNext.innerText = panelId === 9 ? 'Complete Presentation →' : 'Next Slide →';
    } else {
      btnSaveRender.innerText = '🎬 Save & Render Slice';
      btnSaveNext.innerText = 'Next Slide →';
    }
  }

  initSlideAudioMiniPlayer(panelId);
}

// Persistent real-time HTML5 Audio engine shared between Mini-Player and Live Story Preview
const studioAudio = new Audio();
studioAudio.preload = 'auto';

// Unlock audio playback on first user interaction anywhere in the studio
let audioGestureUnlocked = false;
function unlockStudioAudioOnGesture() {
  if (audioGestureUnlocked) return;
  audioGestureUnlocked = true;
  if ((appState.isPlaying || appState.miniPlayerAuditioning) && !appState.isPreviewMuted) {
    studioAudio.play().catch(() => {});
  }
}
['pointerdown', 'keydown'].forEach(evt => {
  window.addEventListener(evt, unlockStudioAudioOnGesture, { once: true, passive: true });
});

/**
 * Formats seconds into MM:SS.d string for the mini-player display.
 * @param {number} sec Time in seconds
 * @param {boolean} [withTenths=true] Whether to include tenths of a second
 * @returns {string} Formatted time string
 */
function formatTimeMMSS(sec, withTenths = true) {
  if (isNaN(sec) || !isFinite(sec) || sec < 0) sec = 0;
  const mins = Math.floor(sec / 60);
  const rem = sec - mins * 60;
  const secsInt = Math.floor(rem);
  const tenths = Math.floor((rem - secsInt + 1e-6) * 10);
  const mm = mins < 10 ? `0${mins}` : `${mins}`;
  const ss = secsInt < 10 ? `0${secsInt}` : `${secsInt}`;
  return withTenths ? `${mm}:${ss}.${tenths}` : `${mm}:${ss}`;
}

/**
 * Renders the per-slide real-time audio Mini-Player widget.
 * Why: Allows selecting a song with Windows File Explorer, scrubbing the full song timeline
 * in real time like a mini player to choose the initial instant, and playing 5 seconds from there.
 * @param {number} panelId Index of the slide (0 to 9)
 * @returns {string} HTML markup
 */
function renderSlideAudioWidget(panelId) {
  const cur = appState.curation || {};
  const slideAudioMap = cur.slide_audio || {};
  const cfg = slideAudioMap[String(panelId)] || slideAudioMap[panelId] || {};
  const audioPath = cfg.path || '';
  const defaultStart = audioPath ? 0.0 : roundNumber(panelId * 5.0, 1);
  const startSec = cfg.start_sec !== undefined ? parseFloat(cfg.start_sec) : defaultStart;
  const safeStart = isNaN(startSec) || startSec < 0 ? 0.0 : startSec;

  let rawVol = cfg.volume !== undefined ? parseFloat(cfg.volume) : 1.0;
  if (isNaN(rawVol) || rawVol < 0) rawVol = 1.0;
  const volPct = rawVol > 1.0 ? Math.min(100, Math.round(rawVol)) : Math.round(Math.max(0.0, Math.min(1.0, rawVol)) * 100);
  const volIcon = volPct === 0 ? '🔇' : (volPct < 50 ? '🔉' : '🔊');

  return `
    <div class="slide-audio-widget mini-player-card" id="slide-audio-mini-player">
      <div class="mini-player-header">
        <span class="mini-player-title">🎵 SONG MINI-PLAYER (5.0s WINDOW)</span>
        <span class="mini-player-meta-pill" id="mini-player-track-meta">Loading track...</span>
      </div>

      <div class="path-input-row">
        <input type="text" class="curated-mini-input" id="inp-slide-audio-path" 
               value="${audioPath}" placeholder="Local audio path (FLAC, MP3, M4A, WAV)...">
        <button type="button" class="btn-browse-inline" id="btn-browse-slide-audio" 
                onclick="browseSlideAudioPath()" title="Browse song with Windows File Explorer">
          📁 Browse
        </button>
      </div>

      <div class="mini-player-deck">
        <div class="mini-player-transport">
          <button type="button" class="btn-mini-play" id="btn-test-slide-audio" onclick="testCurrentSlideAudioSnippet()">
            ▶ Play 5s
          </button>

          <div class="mini-player-scrubber-wrap" title="Drag in real time to select the 5-second start instant">
            <div class="mini-player-track-bg">
              <div class="mini-player-window-box" id="mini-player-window-box"></div>
              <div class="mini-player-playhead" id="mini-player-playhead"></div>
            </div>
            <input type="range" class="mini-player-range" id="inp-slide-audio-slider"
                   min="0" max="180" step="0.1" value="${safeStart.toFixed(1)}">
          </div>
        </div>

        <div class="mini-player-controls-row">
          <div class="mini-player-time-readout">
            <span>Start: <b id="lbl-mini-start-fmt">${formatTimeMMSS(safeStart)}</b></span>
            <span>→ +5s: <b id="lbl-mini-end-fmt">${formatTimeMMSS(safeStart + 5.0)}</b></span>
            <span>/ Total: <span id="lbl-mini-total-fmt">--:--</span></span>
          </div>

          <div class="mini-player-fine-controls">
            <button type="button" class="btn-nudge" onclick="nudgeSlideAudioStart(-1.0)" title="-1.0 second">-1s</button>
            <button type="button" class="btn-nudge" onclick="nudgeSlideAudioStart(-0.5)" title="-0.5 seconds">-0.5s</button>
            <input type="number" step="0.1" min="0" class="curated-mini-input mini-start-number-input"
                   id="inp-slide-audio-start" value="${safeStart.toFixed(1)}" title="Exact start instant (seconds)">
            <button type="button" class="btn-nudge" onclick="nudgeSlideAudioStart(0.5)" title="+0.5 seconds">+0.5s</button>
            <button type="button" class="btn-nudge" onclick="nudgeSlideAudioStart(1.0)" title="+1.0 second">+1s</button>
          </div>
        </div>

        <div class="mini-player-volume-row">
          <span class="mini-vol-label" id="lbl-slide-vol-icon">${volIcon} Slide Volume</span>
          <input type="range" class="mini-vol-slider" id="inp-slide-audio-volume"
                 min="0" max="100" step="1" value="${volPct}"
                 title="Adjust audio volume for this slide (0% to 100%)">
          <span class="mini-vol-val" id="lbl-slide-audio-volume">${volPct}%</span>
        </div>
      </div>

      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span id="slide-audio-status" style="font-size:11px;color:#8fa592;">🔊 Synced in real time with Live Preview (1.0s Fade In/Out)</span>
        <span style="font-size:10px;color:#5c6e60;font-family:var(--font-mono);">REAL-TIME STREAM</span>
      </div>
    </div>
  `;
}

/**
 * Initializes the real-time Mini-Player events and loads the active slide's song metadata & stream.
 * @param {number} panelId Active panel index (0-9)
 */
function initSlideAudioMiniPlayer(panelId) {
  const pathInp = document.getElementById('inp-slide-audio-path');
  const sliderInp = document.getElementById('inp-slide-audio-slider');
  const startInp = document.getElementById('inp-slide-audio-start');
  const volInp = document.getElementById('inp-slide-audio-volume');
  if (!pathInp || !sliderInp || !startInp) return;

  const initialPath = pathInp.value.trim();
  const initialStart = parseFloat(startInp.value) || 0.0;

  loadMiniPlayerTrack(initialPath, initialStart, false);

  const getCurrentSlideVolRatio = () => {
    const v = volInp ? parseFloat(volInp.value) : 100;
    return isNaN(v) ? 1.0 : Math.max(0.0, Math.min(1.0, v / 100.0));
  };

  if (volInp) {
    volInp.addEventListener('input', () => {
      const pct = Math.max(0, Math.min(100, parseInt(volInp.value, 10) || 0));
      const lblVal = document.getElementById('lbl-slide-audio-volume');
      const lblIcon = document.getElementById('lbl-slide-vol-icon');
      if (lblVal) lblVal.textContent = `${pct}%`;
      if (lblIcon) {
        const icon = pct === 0 ? '🔇' : (pct < 50 ? '🔉' : '🔊');
        lblIcon.textContent = `${icon} Slide Volume`;
      }
      syncLiveSlideAudioState(panelId, pathInp.value.trim(), parseFloat(startInp.value) || 0, pct / 100.0);
    });

    volInp.addEventListener('change', async () => {
      const pct = Math.max(0, Math.min(100, parseInt(volInp.value, 10) || 0));
      syncLiveSlideAudioState(panelId, pathInp.value.trim(), parseFloat(startInp.value) || 0, pct / 100.0);
      await submitCurrentPanel({ skipIframeReload: true, silentToast: true });
    });
  }

  // Real-time scrubbing on range slider
  sliderInp.addEventListener('pointerdown', () => {
    appState.isDraggingMiniSlider = true;
  });

  sliderInp.addEventListener('input', () => {
    const maxStart = Math.max(0, roundNumber((appState.audioTrackDuration || 50.0) - 5.0, 1));
    const val = Math.max(0, Math.min(maxStart, parseFloat(sliderInp.value) || 0));
    sliderInp.value = val.toFixed(1);
    startInp.value = val.toFixed(1);
    syncLiveSlideAudioState(panelId, pathInp.value.trim(), val, getCurrentSlideVolRatio());
    updateMiniPlayerVisuals(val, 0);
    // Immediately seek and audition from the new start point in real time
    triggerRealtimeAuditionFromStart(val);
  });

  const finishMiniSliderDrag = async () => {
    if (appState.isDraggingMiniSlider) {
      appState.isDraggingMiniSlider = false;
    }
    const maxStart = Math.max(0, roundNumber((appState.audioTrackDuration || 50.0) - 5.0, 1));
    const val = Math.max(0, Math.min(maxStart, parseFloat(sliderInp.value) || 0));
    sliderInp.value = val.toFixed(1);
    syncLiveSlideAudioState(panelId, pathInp.value.trim(), val, getCurrentSlideVolRatio());
    await submitCurrentPanel({ skipIframeReload: true, silentToast: true });
  };

  sliderInp.addEventListener('pointerup', finishMiniSliderDrag);
  sliderInp.addEventListener('change', finishMiniSliderDrag);

  // Direct numeric input change / input
  startInp.addEventListener('input', () => {
    const maxStart = Math.max(0, roundNumber((appState.audioTrackDuration || 50.0) - 5.0, 1));
    const val = Math.max(0, Math.min(maxStart, parseFloat(startInp.value) || 0));
    sliderInp.value = val.toFixed(1);
    syncLiveSlideAudioState(panelId, pathInp.value.trim(), val, getCurrentSlideVolRatio());
    updateMiniPlayerVisuals(val, 0);
    triggerRealtimeAuditionFromStart(val);
  });

  startInp.addEventListener('change', async () => {
    const maxStart = Math.max(0, roundNumber((appState.audioTrackDuration || 50.0) - 5.0, 1));
    const val = Math.max(0, Math.min(maxStart, parseFloat(startInp.value) || 0));
    startInp.value = val.toFixed(1);
    sliderInp.value = val.toFixed(1);
    syncLiveSlideAudioState(panelId, pathInp.value.trim(), val, getCurrentSlideVolRatio());
    await submitCurrentPanel({ skipIframeReload: true });
  });

  // Manual path input edit
  pathInp.addEventListener('change', async () => {
    const newPath = pathInp.value.trim();
    const resetStart = newPath ? 0.0 : roundNumber(panelId * 5.0, 1);
    startInp.value = resetStart.toFixed(1);
    sliderInp.value = resetStart.toFixed(1);
    syncLiveSlideAudioState(panelId, newPath, resetStart, getCurrentSlideVolRatio());
    await loadMiniPlayerTrack(newPath, resetStart, true);
    await submitCurrentPanel({ skipIframeReload: true });
  });
}

/**
 * Updates in-memory curation slide_audio immediately so the 60fps preview loop sees changes with zero latency.
 */
function syncLiveSlideAudioState(panelId, pathStr, startSec, volumeRatio = null) {
  if (!appState.curation) appState.curation = {};
  if (!appState.curation.slide_audio) appState.curation.slide_audio = {};
  const existing = appState.curation.slide_audio[String(panelId)] || {};
  let resolvedVol = volumeRatio;
  if (resolvedVol === null || resolvedVol === undefined) {
    const volInp = document.getElementById('inp-slide-audio-volume');
    if (volInp) {
      resolvedVol = Math.max(0.0, Math.min(1.0, (parseFloat(volInp.value) || 100) / 100.0));
    } else if (existing.volume !== undefined) {
      resolvedVol = existing.volume;
    } else {
      resolvedVol = 1.0;
    }
  }
  appState.curation.slide_audio[String(panelId)] = {
    path: pathStr,
    start_sec: startSec,
    volume: resolvedVol
  };
}

/**
 * Loads the specified audio file (or default soundtrack) into the HTML5 Audio stream and updates metadata.
 * @param {string} audioPath Local path to song file
 * @param {number} startSec Selected initial second
 * @param {boolean} [autoPlay5s=false] Whether to immediately play 5s after loading
 */
async function loadMiniPlayerTrack(audioPath, startSec = 0.0, autoPlay5s = false) {
  const metaPill = document.getElementById('mini-player-track-meta');
  const cleanPath = (audioPath || '').trim();

  // Stream URL for the full audio file
  const streamKey = cleanPath || '__DEFAULT_SOUNDTRACK__';
  const streamUrl = `/api/audio-stream?path=${encodeURIComponent(cleanPath)}`;

  if (appState.currentAudioStreamKey !== streamKey) {
    appState.currentAudioStreamKey = streamKey;
    studioAudio.src = streamUrl;
    studioAudio.load();
  }

  // Extract metadata & exact duration (works for both custom paths and default soundtrack.aac)
  if (cleanPath) {
    const fileNameFallback = cleanPath.split(/[\\/]/).pop();
    if (metaPill) metaPill.textContent = `🎵 ${fileNameFallback}`;
  } else if (metaPill) {
    metaPill.textContent = `🎵 Default Soundtrack (soundtrack.aac)`;
    metaPill.title = 'Default Soundtrack (output/audio/soundtrack.aac)';
  }

  try {
    const res = await fetch('/api/extract-flac', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: cleanPath })
    });
    const meta = await res.json();
    if (meta && meta.valid) {
      if (cleanPath && metaPill) {
        metaPill.textContent = `🎵 ${meta.title} — ${meta.artist}`;
        metaPill.title = `${meta.title} — ${meta.artist} (${cleanPath})`;
      }
      if (meta.duration && meta.duration > 0) {
        applyTrackDurationToMiniPlayer(meta.duration, startSec);
      }
    }
  } catch (err) {}

  // Also listen to studioAudio.loadedmetadata for exact browser-decoded duration
  const onLoadedMeta = () => {
    if (studioAudio.duration && isFinite(studioAudio.duration) && studioAudio.duration > 0) {
      applyTrackDurationToMiniPlayer(studioAudio.duration, startSec);
    }
    if (autoPlay5s) {
      triggerRealtimeAuditionFromStart(startSec);
    }
  };

  if (studioAudio.readyState >= 1 && studioAudio.duration && isFinite(studioAudio.duration)) {
    onLoadedMeta();
  } else {
    studioAudio.addEventListener('loadedmetadata', onLoadedMeta, { once: true });
  }

  updateMiniPlayerVisuals(startSec, 0);
}

function applyTrackDurationToMiniPlayer(durationSec, currentStartSec) {
  appState.audioTrackDuration = Math.max(5.0, durationSec);
  const sliderInp = document.getElementById('inp-slide-audio-slider');
  const startInp = document.getElementById('inp-slide-audio-start');
  const totalEl = document.getElementById('lbl-mini-total-fmt');

  const maxStart = Math.max(0, roundNumber(appState.audioTrackDuration - 5.0, 1));
  if (sliderInp) {
    sliderInp.max = roundNumber(appState.audioTrackDuration, 1);
  }
  if (startInp) {
    startInp.max = maxStart;
  }
  if (totalEl) {
    totalEl.textContent = formatTimeMMSS(appState.audioTrackDuration, false);
  }

  const clampedStart = Math.max(0, Math.min(maxStart, currentStartSec));
  if (sliderInp) sliderInp.value = clampedStart.toFixed(1);
  if (startInp) startInp.value = clampedStart.toFixed(1);
  updateMiniPlayerVisuals(clampedStart, 0);
}

/**
 * Updates the visual 5.0s window highlight box, playhead line, and MM:SS.d labels in the Mini-Player.
 * @param {number} startSec Start instant in seconds
 * @param {number} offsetInWindow Current playback offset within the 5.0s window [0.0, 5.0]
 */
function updateMiniPlayerVisuals(startSec, offsetInWindow = 0.0) {
  const totalDur = Math.max(5.0, appState.audioTrackDuration || 50.0);
  const winBox = document.getElementById('mini-player-window-box');
  const playhead = document.getElementById('mini-player-playhead');
  const lblStart = document.getElementById('lbl-mini-start-fmt');
  const lblEnd = document.getElementById('lbl-mini-end-fmt');

  const leftPct = Math.max(0, Math.min(100, (startSec / totalDur) * 100));
  const widthPct = Math.max(1.5, Math.min(100 - leftPct, (5.0 / totalDur) * 100));

  if (winBox) {
    winBox.style.left = `${leftPct.toFixed(2)}%`;
    winBox.style.width = `${widthPct.toFixed(2)}%`;
  }

  const currentAbsSec = Math.min(totalDur, startSec + Math.max(0, Math.min(5.0, offsetInWindow)));
  const playheadPct = Math.max(0, Math.min(100, (currentAbsSec / totalDur) * 100));
  if (playhead) {
    playhead.style.left = `${playheadPct.toFixed(2)}%`;
  }

  if (lblStart) lblStart.textContent = formatTimeMMSS(startSec);
  if (lblEnd) lblEnd.textContent = formatTimeMMSS(Math.min(totalDur, startSec + 5.0));
}

/**
 * Fine-adjusts the initial instant (start_sec) by deltaSec (-1s, -0.5s, +0.5s, +1s).
 * @param {number} deltaSec Seconds delta
 */
async function nudgeSlideAudioStart(deltaSec) {
  const startInp = document.getElementById('inp-slide-audio-start');
  const sliderInp = document.getElementById('inp-slide-audio-slider');
  const pathInp = document.getElementById('inp-slide-audio-path');
  if (!startInp || !sliderInp) return;

  const maxStart = Math.max(0, roundNumber((appState.audioTrackDuration || 180) - 5.0, 1));
  const curVal = parseFloat(startInp.value) || 0;
  const nextVal = Math.max(0, Math.min(maxStart, roundNumber(curVal + deltaSec, 1)));

  startInp.value = nextVal.toFixed(1);
  sliderInp.value = nextVal.toFixed(1);
  syncLiveSlideAudioState(appState.currentPanel, pathInp ? pathInp.value.trim() : '', nextVal);
  updateMiniPlayerVisuals(nextVal, 0);
  triggerRealtimeAuditionFromStart(nextVal);
  await submitCurrentPanel({ skipIframeReload: true, silentToast: true });
}

/**
 * Immediately starts/restarts real-time 5.0s playback from startSec, synchronized with the preview.
 * @param {number} startSec Start instant in seconds
 */
function triggerRealtimeAuditionFromStart(startSec) {
  appState.miniPlayerAuditioning = true;
  appState.miniPlayerAuditionElapsed = 0.0;

  if (appState.isPreviewMuted) {
    appState.isPreviewMuted = false;
    updatePreviewAudioBtnUI();
  }

  // Also align the right-hand preview to 0.0s of the current 5s slice so visuals & audio match
  appState.currentTimeSec = 0.0;
  if (appState.previewMode === 'live') {
    const iframe = document.getElementById('story-iframe');
    if (iframe && iframe.contentWindow && typeof iframe.contentWindow.seek === 'function') {
      iframe.contentWindow.seek(0.0);
    }
  } else if (appState.previewMode === 'video') {
    const vid = document.getElementById('slice-video');
    if (vid) vid.currentTime = 0.0;
  }

  try {
    if (studioAudio.readyState >= 1) {
      studioAudio.currentTime = Math.max(0, startSec);
    }
    studioAudio.volume = 0.05;
    studioAudio.play().catch(() => {});
  } catch (e) {}

  updateMiniPlayerPlayBtnUI(true);
}

function updateMiniPlayerPlayBtnUI(isPlaying5s) {
  const btnEl = document.getElementById('btn-test-slide-audio');
  if (!btnEl) return;
  if (isPlaying5s) {
    btnEl.innerText = '⏹ Stop 5s';
    btnEl.classList.add('playing');
  } else {
    btnEl.innerText = '▶ Play 5s';
    btnEl.classList.remove('playing');
  }
}

/**
 * Toggles the 5.0-second real-time snippet playback from the selected initial instant in the Mini-Player.
 */
function testCurrentSlideAudioSnippet() {
  const startInp = document.getElementById('inp-slide-audio-start');
  const statusEl = document.getElementById('slide-audio-status');
  const startSec = startInp ? parseFloat(startInp.value) || 0 : 0;

  if (appState.miniPlayerAuditioning) {
    appState.miniPlayerAuditioning = false;
    appState.miniPlayerAuditionElapsed = 0.0;
    if (!appState.isPlaying) {
      studioAudio.pause();
    }
    updateMiniPlayerPlayBtnUI(false);
    updateMiniPlayerVisuals(startSec, 0);
    if (statusEl) statusEl.innerText = '⏹ Audition stopped';
    return;
  }

  triggerRealtimeAuditionFromStart(startSec);
}

/**
 * Opens native Windows File Explorer to pick a song for the Slide Audio Mini-Player.
 */
async function browseSlideAudioPath() {
  const pathInp = document.getElementById('inp-slide-audio-path');
  const startInp = document.getElementById('inp-slide-audio-start');
  const sliderInp = document.getElementById('inp-slide-audio-slider');
  const currentPath = pathInp ? pathInp.value.trim() : '';

  try {
    showTerminalToast('Opening Windows File Explorer to select audio track...');
    const res = await fetch('/api/browse-audio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ initial_path: currentPath || null })
    });
    const data = await res.json();
    if (data && data.selected_path) {
      if (pathInp) pathInp.value = data.selected_path;
      const newStart = 0.0;
      if (startInp) startInp.value = newStart.toFixed(1);
      if (sliderInp) sliderInp.value = newStart.toFixed(1);
      syncLiveSlideAudioState(appState.currentPanel, data.selected_path, newStart);
      await loadMiniPlayerTrack(data.selected_path, newStart, true);
      await submitCurrentPanel({ skipIframeReload: true });
      showTerminalToast(`[TRACK SELECTED] ${data.selected_path}`);
    }
  } catch (err) {
    console.error('Browse slide audio error:', err);
    showTerminalToast(`[ERROR] Failed to open Windows File Explorer: ${err.message}`, true);
  }
}

/**
 * Opens native Windows File Explorer for any curated song, album, or genre audio path input.
 * @param {'song'|'album'|'genre'} type Curated card type
 * @param {number} rank Item rank (1 to 5)
 */
async function browseCuratedAudioPath(type, rank) {
  const inp = document.querySelector(`.flac-path-input[data-type="${type}"][data-rank="${rank}"]`);
  if (!inp) return;

  try {
    showTerminalToast('Opening Windows File Explorer to select audio track...');
    const res = await fetch('/api/browse-audio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ initial_path: inp.value.trim() || null })
    });
    const data = await res.json();
    if (data && data.selected_path) {
      inp.value = data.selected_path;
      showTerminalToast(`[TRACK SELECTED] ${data.selected_path}`);
      // Also auto-fill slide audio mini-player if it has no custom song yet on this slide
      const slidePathInp = document.getElementById('inp-slide-audio-path');
      if (slidePathInp && !slidePathInp.value.trim() && rank === 1) {
        slidePathInp.value = data.selected_path;
        syncLiveSlideAudioState(appState.currentPanel, data.selected_path, 0.0);
        await loadMiniPlayerTrack(data.selected_path, 0.0, true);
      }
      // Trigger FLAC metadata & cover art extraction
      inp.dispatchEvent(new Event('change'));
    }
  } catch (err) {
    console.error('Browse curated audio error:', err);
    showTerminalToast(`[ERROR] Failed to open Windows File Explorer: ${err.message}`, true);
  }
}

const DEFAULT_THUMB_SVG = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100' fill='%2318211b'><rect width='100' height='100'/><circle cx='50' cy='50' r='20' fill='%2300ff87'/></svg>";

function renderCuratedItemInput(type, rank, data) {
  const thumb = data.artwork || DEFAULT_THUMB_SVG;
  const val1 = type === 'song' ? (data.title || '') : (data.album || '');
  const val2 = data.artist || '';
  const path = data.path || '';

  return `
    <div class="curated-card-input" id="${type}-card-${rank}">
      <div class="curated-rank">${rank}</div>
      <img class="curated-thumb" id="${type}-thumb-${rank}" src="${thumb}" alt="Art">
      <div class="curated-fields">
        <div class="path-input-row">
          <input type="text" class="curated-mini-input flac-path-input" 
                 data-type="${type}" data-rank="${rank}" 
                 value="${path}" placeholder="Local audio path (FLAC, MP3, M4A)...">
          <button type="button" class="btn-browse-inline" 
                  onclick="browseCuratedAudioPath('${type}', ${rank})"
                  title="Browse audio file with Windows File Explorer">
            📁 Browse
          </button>
        </div>
        <div style="display:flex;gap:8px;">
          <input type="text" class="curated-mini-input" style="flex:1;" id="${type}-title-${rank}" 
                 value="${val1}" placeholder="${type === 'song' ? 'Track title' : 'Album title'}">
          <input type="text" class="curated-mini-input" style="flex:1;" id="${type}-artist-${rank}" 
                 value="${val2}" placeholder="Artist name">
        </div>
      </div>
    </div>
  `;
}

function renderSimpleCreatorInput(type, rank, data) {
  const thumb = data.image || DEFAULT_THUMB_SVG;
  const name = data.name || (rank === 1 && type === 'artist' ? 'ILLENIUM' : '');
  const imgUrl = data.image || '';

  return `
    <div class="curated-card-input" id="${type}-card-${rank}">
      <div class="curated-rank">${rank}</div>
      <img class="curated-thumb" id="${type}-thumb-${rank}" src="${thumb}" alt="Avatar">
      <div class="curated-fields">
        <input type="text" class="curated-mini-input" id="${type}-name-${rank}" 
               value="${name}" placeholder="${type === 'artist' ? 'Artist Name' : 'Discovery Name'}">
        <input type="text" class="curated-mini-input" id="${type}-img-${rank}" 
               value="${imgUrl}" placeholder="Image URL or local cover path...">
      </div>
    </div>
  `;
}

function renderGenreItemInput(rank, data) {
  const g = data.genre || '';
  const s = data.song || '';
  const a = data.artist || '';
  const p = data.path || '';
  const thumb = data.artwork || DEFAULT_THUMB_SVG;
  return `
    <div class="curated-card-input" id="genre-card-${rank}" style="align-items:flex-start;padding:12px 14px;margin-bottom:8px;">
      <div class="curated-rank" style="margin-top:6px;">${rank}</div>
      <img class="curated-thumb" id="genre-thumb-${rank}" src="${thumb}" alt="Genre Art" style="margin-top:4px;">
      <div class="curated-fields" style="flex:1;">
        <div style="display:flex;gap:8px;margin-bottom:6px;">
          <input type="text" class="curated-mini-input" style="flex:1;" id="genre-name-${rank}" 
                 value="${g}" placeholder="Genre (e.g. Alternative, Melodic Bass)">
          <input type="text" class="curated-mini-input" style="flex:1;" id="genre-song-${rank}" 
                 value="${s}" placeholder="Track (e.g. my BAD!)">
          <input type="text" class="curated-mini-input" style="flex:1;" id="genre-artist-${rank}" 
                 value="${a}" placeholder="Artist (e.g. lamont4u)">
        </div>
        <div class="path-input-row">
          <input type="text" class="curated-mini-input flac-path-input" 
                 data-type="genre" data-rank="${rank}" 
                 value="${p}" placeholder="Local Audio Path (FLAC, MP3, M4A)...">
          <button type="button" class="btn-browse-inline" 
                  onclick="browseCuratedAudioPath('genre', ${rank})"
                  title="Browse audio file with Windows File Explorer">
            📁 Browse
          </button>
        </div>
      </div>
    </div>
  `;
}

function bindFLACAutoloaders(type) {
  const inputs = document.querySelectorAll(`.flac-path-input[data-type="${type}"]`);
  inputs.forEach(inp => {
    inp.addEventListener('change', async () => {
      const p = inp.value.trim();
      if (!p) return;
      const rank = inp.dataset.rank;
      try {
        const res = await fetch('/api/extract-flac', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: p })
        });
        const meta = await res.json();
        if (meta && meta.valid) {
          if (type === 'song') {
            document.getElementById(`song-title-${rank}`).value = meta.title;
            document.getElementById(`song-artist-${rank}`).value = meta.artist;
          } else if (type === 'album') {
            document.getElementById(`album-title-${rank}`).value = meta.album;
            document.getElementById(`album-artist-${rank}`).value = meta.artist;
          } else if (type === 'genre') {
            document.getElementById(`genre-song-${rank}`).value = meta.title;
            if (meta.artist) {
              document.getElementById(`genre-artist-${rank}`).value = meta.artist;
            }
          }
          if (meta.artwork) {
            const thumbEl = document.getElementById(`${type}-thumb-${rank}`);
            if (thumbEl) thumbEl.src = meta.artwork;
          }
          await submitCurrentPanel();
        }
      } catch (err) {
        console.error('Audio metadata extract error:', err);
      }
    });
  });
}

function initPlayerControls() {
  const slider = document.getElementById('timeline-slider');
  const video = document.getElementById('slice-video');
  const iframe = document.getElementById('story-iframe');

  if (iframe) {
    iframe.addEventListener('load', () => {
      try {
        if (iframe.contentWindow && typeof iframe.contentWindow.setPanels === 'function') {
          if (appState.playbackScope === 'single') {
            iframe.contentWindow.setPanels([appState.currentPanel]);
          }
        }
      } catch (e) {}
    });
  }

  if (slider) {
    slider.addEventListener('pointerdown', () => {
      appState.isDraggingSlider = true;
    });

    const stopDrag = () => {
      if (appState.isDraggingSlider) {
        appState.isDraggingSlider = false;
        seekToTime(parseFloat(slider.value));
      }
    };

    slider.addEventListener('pointerup', stopDrag);
    slider.addEventListener('change', stopDrag);

    slider.addEventListener('input', (e) => {
      seekToTime(parseFloat(e.target.value));
    });
  }

  if (video) {
    video.addEventListener('timeupdate', () => {
      if (appState.previewMode === 'video' && !appState.isDraggingSlider) {
        appState.currentTimeSec = video.currentTime;
        if (slider) slider.value = video.currentTime;
        const timeDisplay = document.getElementById('time-display');
        if (timeDisplay) {
          timeDisplay.innerText = `${video.currentTime.toFixed(1)}s / ${(video.duration || appState.maxTimelineSec).toFixed(1)}s`;
        }
      }
    });

    video.addEventListener('play', () => {
      if (appState.previewMode === 'video') {
        appState.isPlaying = true;
        const btn = document.getElementById('btn-play-pause');
        if (btn) btn.innerText = '❚❚ Pause';
      }
    });

    video.addEventListener('pause', () => {
      if (appState.previewMode === 'video') {
        appState.isPlaying = false;
        const btn = document.getElementById('btn-play-pause');
        if (btn) btn.innerText = '▶ Play';
      }
    });
  }
}

function showTerminalToast(message, isError = false) {
  const toast = document.getElementById('terminal-toast');
  if (!toast) return;
  toast.innerText = message;
  toast.className = `terminal-toast ${isError ? 'error' : ''}`;
  toast.classList.remove('hidden');

  setTimeout(() => {
    toast.classList.add('hidden');
  }, 4500);
}

/**
 * Triggers native Windows File Explorer Save dialog via backend.
 */
async function browseSavePath() {
  try {
    showTerminalToast('Opening Windows File Explorer...');
    const res = await fetch('/api/browse-path', { method: 'POST' });
    const data = await res.json();
    if (data && data.selected_path) {
      const inputEl = document.getElementById('inp-export-path');
      if (inputEl) inputEl.value = data.selected_path;
      showTerminalToast(`[PATH SELECTED] ${data.selected_path}`);
      return data.selected_path;
    }
  } catch (err) {
    console.error('File browse error:', err);
    showTerminalToast(`[ERROR] File explorer dialog failed: ${err.message}`, true);
  }
  return null;
}

async function saveCurrentPanelLocal() {
  const pid = appState.currentPanel;
  const payload = collectCurrentPanelData(pid);

  try {
    const res = await fetch(`/api/panels/${pid}/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ panel_id: pid, data: payload })
    });
    const data = await res.json();
    if (res.ok) {
      appState.curation = data.curation || appState.curation;
      showTerminalToast(`[SAVED] Panel ${pid + 1} configuration saved locally to ${data.curation_path || 'output/data/user_curation_2026.json'} (git-ignored).`);
      reloadIframePreview();
    } else {
      showTerminalToast(`[ERROR] Save failed: ${data.detail || 'Unknown error'}`, true);
    }
  } catch (err) {
    console.error('Local save error:', err);
    showTerminalToast(`[ERROR] Failed to save panel locally: ${err.message}`, true);
  }
}

/**
 * Saves and renders the video strictly according to the Custom Slices & Order settings
 * to the requested destination path on disk.
 * Why: Ensures that whenever the user clicks 'Save Video', the output file reflects the exact
 * selection, sequence, and individual slide audio configuration chosen in the Composer.
 */
async function saveVideoToPath() {
  const inputEl = document.getElementById('inp-export-path');
  let targetPath = (inputEl ? inputEl.value : '').trim();

  // If no path is entered yet, proactively open Windows File Explorer
  if (!targetPath) {
    showTerminalToast('[INFO] Opening Windows File Explorer to choose destination...');
    targetPath = await browseSavePath();
    if (!targetPath) {
      showTerminalToast('[INFO] Save Video cancelled: No destination path chosen.');
      return;
    }
  }

  // Derive slice sequence strictly from Custom Slices & Order
  const selectedOrdered = appState.slicesOrder.filter(pid => appState.selectedSlices.has(pid));
  if (selectedOrdered.length === 0) {
    showTerminalToast('[WARNING] Please select at least one slice in Custom Slices & Order before saving.', true);
    return;
  }

  const isDefault10 = selectedOrdered.length === 10 && selectedOrdered.every((pid, idx) => pid === idx);
  const totalSec = (selectedOrdered.length * 5.0).toFixed(1);
  const seqNames = selectedOrdered.map(p => `#${p + 1}`).join(' → ');
  const modeDesc = isDefault10
    ? 'Full Presentation (10 slides • 50.0s)'
    : `Custom Sequence (${selectedOrdered.length} slides • ${totalSec}s: [${seqNames}])`;

  const payload = {
    target_path: targetPath,
    render_first: true,
    selected_panels: selectedOrdered,
    fps: 25
  };

  setPreviewMode('video');
  showRenderOverlay({
    badge: isDefault10 ? 'FULL EXPORT (25 FPS)' : 'CUSTOM EXPORT (25 FPS)',
    title: 'Exporting Presentation Video',
    subtitle: `${modeDesc} • Generating full 25 FPS stream with FFmpeg`,
    path: targetPath
  });

  showTerminalToast(`[RENDERING] Building ${modeDesc} and saving to: ${targetPath}...`);

  try {
    const res = await fetch('/api/save-video', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      if (data.status === 'started' || data.status === 'rendering') {
        pollRenderStatus(`Saved Video (${modeDesc})`, `/output/${data.target_file}`);
      } else {
        hideRenderOverlay();
        showTerminalToast(`[SUCCESS] ${data.message || 'Video successfully saved.'}`);
      }
    } else {
      hideRenderOverlay();
      showTerminalToast(`[ERROR] Save video failed: ${data.detail || 'Server error'}`, true);
    }
  } catch (err) {
    console.error('Save video error:', err);
    hideRenderOverlay();
    showTerminalToast(`[ERROR] Save video request failed: ${err.message}`, true);
  }
}

function collectCurrentPanelData(pid) {
  const slideAudioPath = document.getElementById('inp-slide-audio-path')?.value || '';
  const slideAudioStart = parseFloat(document.getElementById('inp-slide-audio-start')?.value || 0);
  const slideAudioVolEl = document.getElementById('inp-slide-audio-volume');
  const slideAudioVolPct = slideAudioVolEl ? parseFloat(slideAudioVolEl.value) : 100;
  const slideAudioVolRatio = isNaN(slideAudioVolPct)
    ? 1.0
    : Math.max(0.0, Math.min(1.0, slideAudioVolPct / 100.0));
  const slideAudioData = {
    path: slideAudioPath.trim(),
    start_sec: isNaN(slideAudioStart) || slideAudioStart < 0 ? 0.0 : slideAudioStart,
    volume: Number(slideAudioVolRatio.toFixed(3))
  };

  if (pid === 0) {
    const minsVal = parseInt(document.getElementById('inp-sp-mins')?.value, 10);
    const playsVal = parseInt(document.getElementById('inp-sp-plays')?.value, 10);
    const songsVal = parseInt(document.getElementById('inp-sp-songs')?.value, 10);
    const streakVal = parseInt(document.getElementById('inp-sp-streak')?.value, 10);
    return {
      extra_minutes: isNaN(minsVal) ? 0 : minsVal,
      extra_plays: isNaN(playsVal) ? 0 : playsVal,
      extra_songs: isNaN(songsVal) ? 0 : songsVal,
      streak_days: isNaN(streakVal) ? 103 : streakVal,
      slide_audio: slideAudioData
    };
  } else if (pid === 1) {
    return {
      note: document.getElementById('inp-bn-note')?.value || '',
      tier: document.getElementById('inp-bn-tier')?.value || '',
      slide_audio: slideAudioData
    };
  } else if (pid === 2) {
    const rawWork = document.getElementById('inp-clk-work')?.value;
    const rawSat = document.getElementById('inp-clk-sat')?.value;
    const workVal = parseInt(rawWork, 10);
    const satVal = parseInt(rawSat, 10);
    return {
      workday_extra_minutes: isNaN(workVal) ? 0 : workVal,
      saturday_extra_minutes: isNaN(satVal) ? 0 : satVal,
      slide_audio: slideAudioData
    };
  } else if (pid === 3) {
    const songs = [];
    for (let i = 1; i <= 5; i++) {
      songs.push({
        rank: i,
        title: document.getElementById(`song-title-${i}`)?.value || `Track ${i}`,
        artist: document.getElementById(`song-artist-${i}`)?.value || 'Artist',
        artwork: document.getElementById(`song-thumb-${i}`)?.src || '',
        path: document.querySelector(`.flac-path-input[data-type="song"][data-rank="${i}"]`)?.value || ''
      });
    }
    return { top_songs: songs, slide_audio: slideAudioData };
  } else if (pid === 4) {
    const albums = [];
    for (let i = 1; i <= 5; i++) {
      albums.push({
        rank: i,
        album: document.getElementById(`album-title-${i}`)?.value || `Album ${i}`,
        artist: document.getElementById(`album-artist-${i}`)?.value || 'Artist',
        artwork: document.getElementById(`album-thumb-${i}`)?.src || '',
        path: document.querySelector(`.flac-path-input[data-type="album"][data-rank="${i}"]`)?.value || ''
      });
    }
    return { top_albums: albums, slide_audio: slideAudioData };
  } else if (pid === 5) {
    const artists = [];
    for (let i = 1; i <= 5; i++) {
      artists.push({
        rank: i,
        name: document.getElementById(`artist-name-${i}`)?.value || (i === 1 ? 'ILLENIUM' : `Artist ${i}`),
        image: document.getElementById(`artist-img-${i}`)?.value || document.getElementById(`artist-thumb-${i}`)?.src || ''
      });
    }
    return { top_artists: artists, slide_audio: slideAudioData };
  } else if (pid === 6) {
    const disc = [];
    for (let i = 1; i <= 5; i++) {
      disc.push({
        rank: i,
        name: document.getElementById(`discovery-name-${i}`)?.value || `Discovery ${i}`,
        image: document.getElementById(`discovery-img-${i}`)?.value || document.getElementById(`discovery-thumb-${i}`)?.src || ''
      });
    }
    return { top_discoveries: disc, slide_audio: slideAudioData };
  } else if (pid === 7) {
    const genres = [];
    for (let i = 1; i <= 5; i++) {
      genres.push({
        rank: i,
        genre: document.getElementById(`genre-name-${i}`)?.value || `Genre ${i}`,
        song: document.getElementById(`genre-song-${i}`)?.value || `Track ${i}`,
        artist: document.getElementById(`genre-artist-${i}`)?.value || '',
        path: document.querySelector(`.flac-path-input[data-type="genre"][data-rank="${i}"]`)?.value || '',
        artwork: document.getElementById(`genre-thumb-${i}`)?.src || ''
      });
    }
    return { top_genres: genres, slide_audio: slideAudioData };
  } else if (pid === 8) {
    return { slide_audio: slideAudioData };
  } else if (pid === 9) {
    return { slide_audio: slideAudioData };
  }
  return { slide_audio: slideAudioData };
}

async function submitCurrentPanel(options = {}) {
  const { skipIframeReload = false, silentToast = false } = options;
  const pid = appState.currentPanel;
  const payload = collectCurrentPanelData(pid);

  try {
    const res = await fetch(`/api/panels/${pid}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ panel_id: pid, data: payload })
    });
    const status = await res.json();
    appState.curation = status.curation_data;
    appState.completedPanels = status.completed_panels;
    updateTabsUI();
    if (!silentToast) {
      showTerminalToast(`[UPDATED] Panel ${pid + 1} updated and preview recompiled.`);
    }
    if (!skipIframeReload) {
      reloadIframePreview();
    }
  } catch (err) {
    console.error('Submission failed:', err);
  }
}

async function confirmAndNext() {
  await submitCurrentPanel();
  const pid = appState.currentPanel;
  if (pid < 9) {
    await switchPanel(pid + 1);
  }
}

/**
 * Saves current panel configuration and triggers isolated MP4 slice render.
 */
async function saveAndRenderSlice() {
  await submitCurrentPanel();
  await saveCurrentPanelLocal();
  await renderIsolatedSlice(appState.currentPanel);
}

/**
 * Saves current panel configuration and advances directly to the next slide.
 */
async function saveAndNextSlice() {
  await confirmAndNext();
}

function navigatePanel(delta) {
  const target = appState.currentPanel + delta;
  if (target >= 0 && target <= 9) {
    switchPanel(target);
  }
}

/**
 * Synchronizes the Global Preview FPS selector and numeric input with appState.previewFps.
 */
function syncPreviewFpsUI() {
  const fps = Math.max(1, Math.min(60, parseInt(appState.previewFps, 10) || 1));
  const selEl = document.getElementById('sel-preview-fps');
  const inpEl = document.getElementById('inp-preview-fps');

  if (inpEl) {
    inpEl.value = fps;
  }
  if (selEl) {
    const presetValues = ['1', '5', '10', '15', '24', '25', '30', '60'];
    if (presetValues.includes(String(fps))) {
      selEl.value = String(fps);
    }
  }
}

/**
 * Handles changes from the Preview FPS preset dropdown.
 * @param {string} val Selected FPS value
 */
async function onPreviewFpsSelectChange(val) {
  const parsed = parseInt(val, 10);
  if (!isNaN(parsed)) {
    await setGlobalPreviewFps(parsed);
  }
}

/**
 * Handles changes from the custom numeric Preview FPS input.
 * @param {string} val Entered FPS value
 */
async function onPreviewFpsInputChange(val) {
  const parsed = parseInt(val, 10);
  const clamped = isNaN(parsed) ? 1 : Math.max(1, Math.min(60, parsed));
  await setGlobalPreviewFps(clamped);
}

/**
 * Updates and persists the global preview framerate across Live Story and Rendered MP4 previews.
 * @param {number} fps Target framerate (1 to 60 FPS)
 */
async function setGlobalPreviewFps(fps) {
  const clamped = Math.max(1, Math.min(60, parseInt(fps, 10) || 1));
  appState.previewFps = clamped;
  if (appState.curation) {
    appState.curation.preview_fps = clamped;
  }
  syncPreviewFpsUI();

  try {
    await fetch('/api/preview-fps', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fps: clamped })
    });
    showTerminalToast(`[PREVIEW FPS] Global preview framerate set to ${clamped} FPS.`);
  } catch (err) {
    console.error('Failed to persist preview FPS:', err);
  }
}

/**
 * Displays the full-page blocking glassmorphic rendering modal and locks the entire studio UI.
 * Why: Prevents concurrent actions, tab switches, or form edits while Chromium & FFmpeg are rendering.
 * @param {Object} options Rendering display configuration
 * @param {string} [options.badge='RENDERING'] Pill category tag
 * @param {string} [options.title='Rendering Video'] Main bold headline
 * @param {string} [options.subtitle=''] Explanatory secondary text
 * @param {string|null} [options.path=null] Target export file path
 */
function showRenderOverlay({ badge = 'RENDERING', title = 'Rendering Video', subtitle = '', path = null } = {}) {
  const overlay = document.getElementById('render-overlay');
  const badgeEl = document.getElementById('render-badge-text');
  const titleEl = document.getElementById('render-status-title');
  const subtitleEl = document.getElementById('render-status-subtitle');
  const destContainer = document.getElementById('render-dest-container');
  const pathEl = document.getElementById('render-status-path');
  const legacyMsg = document.getElementById('render-status-msg');
  const studioLayout = document.querySelector('.studio-layout');

  appState.isRenderingLocked = true;
  appState.miniPlayerAuditioning = false;
  if (typeof studioAudio !== 'undefined' && !studioAudio.paused) {
    studioAudio.pause();
  }
  const vid = document.getElementById('slice-video');
  if (vid && !vid.paused) {
    vid.pause();
  }
  if (document.activeElement && typeof document.activeElement.blur === 'function') {
    document.activeElement.blur();
  }

  document.body.classList.add('is-rendering-locked');
  if (studioLayout) {
    studioLayout.setAttribute('inert', '');
    studioLayout.setAttribute('aria-busy', 'true');
  }

  if (badgeEl) badgeEl.textContent = badge;
  if (titleEl) titleEl.textContent = title;
  if (subtitleEl) subtitleEl.textContent = subtitle;
  if (legacyMsg) legacyMsg.textContent = `${title}: ${subtitle}`;

  if (destContainer && pathEl) {
    if (path && path.trim()) {
      pathEl.textContent = path.trim();
      destContainer.classList.remove('hidden');
    } else {
      destContainer.classList.add('hidden');
    }
  }

  if (overlay) overlay.classList.remove('hidden');
}

/**
 * Hides the full-page rendering lock overlay and restores interactivity upon completion or error.
 */
function hideRenderOverlay() {
  const overlay = document.getElementById('render-overlay');
  const studioLayout = document.querySelector('.studio-layout');

  appState.isRenderingLocked = false;
  document.body.classList.remove('is-rendering-locked');
  if (studioLayout) {
    studioLayout.removeAttribute('inert');
    studioLayout.removeAttribute('aria-busy');
  }

  if (overlay) overlay.classList.add('hidden');
}

/**
 * Renders ONLY the isolated 5.0s clip for the current panel at the configured global Preview FPS.
 */
async function renderIsolatedSlice(panelId = null) {
  const pid = panelId !== null ? panelId : appState.currentPanel;
  const fps = Math.max(1, Math.min(60, appState.previewFps || 1));
  const totalFrames = Math.round(5.0 * fps);
  setPreviewMode('video');
  const pName = PANELS[pid] ? PANELS[pid].name : `Slide #${pid + 1}`;
  showRenderOverlay({
    badge: `PREVIEW (${fps} FPS)`,
    title: `Rendering Slide #${pid + 1}`,
    subtitle: `${pName} • 5.0s preview (${totalFrames} frames @ ${fps} FPS)`,
    path: null
  });

  try {
    const res = await fetch(`/api/panels/${pid}/render-isolated`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fps })
    });
    const data = await res.json();
    pollRenderStatus(`Panel ${pid + 1} slice (${fps} FPS)`, `/output/${data.target_file || `slices/wrapped_slice_single_${pid}.mp4`}`);
  } catch (err) {
    console.error('Slice render error:', err);
    hideRenderOverlay();
  }
}

/**
 * Renders the full cumulative presentation up to current panel at the configured global Preview FPS.
 */
async function renderCurrentSlice() {
  const pid = appState.currentPanel;
  const fps = Math.max(1, Math.min(60, appState.previewFps || 1));
  const durSec = (pid + 1) * 5.0;
  const totalFrames = Math.round(durSec * fps);
  setPreviewMode('video');
  const pName = PANELS[pid] ? PANELS[pid].name : `Slide #${pid + 1}`;
  showRenderOverlay({
    badge: `PREVIEW (${fps} FPS)`,
    title: `Rendering up to Slide #${pid + 1}`,
    subtitle: `${pName} • ${durSec.toFixed(1)}s preview (${totalFrames} frames @ ${fps} FPS)`,
    path: null
  });

  try {
    const res = await fetch(`/api/panels/${pid}/render-slice`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fps })
    });
    const data = await res.json();
    pollRenderStatus(`Cumulative to Panel ${pid + 1} (${fps} FPS)`, `/output/${data.target_file || `slices/wrapped_slice_panel_${pid}.mp4`}`);
  } catch (err) {
    console.error('Cumulative render error:', err);
    hideRenderOverlay();
  }
}

function pollRenderStatus(label, targetUrl = null) {
  if (appState.renderPollInterval) clearInterval(appState.renderPollInterval);
  appState.renderPollInterval = setInterval(async () => {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      if (!data.is_rendering) {
        clearInterval(appState.renderPollInterval);
        hideRenderOverlay();
        
        appState.videoSliceUrl = data.video_slice_url;
        appState.singleSliceUrl = data.single_slice_url;

        const vid = document.getElementById('slice-video');
        const src = document.getElementById('slice-video-src');
        if (src && vid) {
          const finalUrl = targetUrl || data.video_slice_url;
          if (finalUrl) {
            src.src = `${finalUrl}?t=${Date.now()}`;
            vid.muted = true; // Real-time studioAudio drives synchronized preview sound
            vid.load();
            vid.play().catch(() => {});
          }
        }
        showTerminalToast(`[RENDER COMPLETE] ${label} rendered successfully.`);
      }
    } catch (err) {
      console.error(err);
    }
  }, 350);
}

function setPreviewMode(mode) {
  appState.previewMode = mode;
  const btnLive = document.getElementById('btn-mode-live');
  const btnVid = document.getElementById('btn-mode-video');
  const liveContainer = document.getElementById('live-player-container');
  const vidContainer = document.getElementById('video-player-container');

  if (btnLive) btnLive.classList.toggle('active', mode === 'live');
  if (btnVid) btnVid.classList.toggle('active', mode === 'video');
  if (liveContainer) liveContainer.classList.toggle('hidden', mode !== 'live');
  if (vidContainer) vidContainer.classList.toggle('hidden', mode !== 'video');

  const vid = document.getElementById('slice-video');
  if (mode === 'video' && vid) {
    vid.muted = true;
    vid.play().catch(() => {});
  } else if (mode === 'live' && vid) {
    vid.pause();
  }
}

function reloadIframePreview() {
  const iframe = document.getElementById('story-iframe');
  if (iframe) {
    const panelsParam = appState.playbackScope === 'single' ? `&panels=${appState.currentPanel}` : '';
    iframe.src = `/story?t=${Date.now()}${panelsParam}`;
  }
}

/**
 * Toggles mute/unmute for the real-time preview audio.
 */
function togglePreviewAudioMute() {
  appState.isPreviewMuted = !appState.isPreviewMuted;
  updatePreviewAudioBtnUI();
  if (appState.isPreviewMuted) {
    studioAudio.pause();
  } else if (appState.isPlaying || appState.miniPlayerAuditioning) {
    studioAudio.play().catch(() => {});
  }
}

function updatePreviewAudioBtnUI() {
  const btn = document.getElementById('btn-preview-audio');
  if (!btn) return;
  if (appState.isPreviewMuted) {
    btn.innerText = '🔇 Mute';
    btn.classList.remove('active');
    btn.classList.add('muted');
  } else {
    btn.innerText = '🔊 Audio';
    btn.classList.add('active');
    btn.classList.remove('muted');
  }
}

/**
 * Seeks deterministic animation or video element to local time.
 * @param {number} sec Timeline progress in seconds
 */
function seekToTime(sec) {
  appState.currentTimeSec = Math.max(0, Math.min(appState.maxTimelineSec, sec));
  
  if (appState.previewMode === 'live') {
    const iframe = document.getElementById('story-iframe');
    if (iframe && iframe.contentWindow && typeof iframe.contentWindow.seek === 'function') {
      iframe.contentWindow.seek(appState.currentTimeSec);
    }
  } else if (appState.previewMode === 'video') {
    const vid = document.getElementById('slice-video');
    if (vid && Math.abs(vid.currentTime - appState.currentTimeSec) > 0.08) {
      vid.currentTime = appState.currentTimeSec;
    }
  }

  const slider = document.getElementById('timeline-slider');
  const timeDisplay = document.getElementById('time-display');
  if (slider) slider.value = appState.currentTimeSec;
  if (timeDisplay) {
    timeDisplay.innerText = `${appState.currentTimeSec.toFixed(1)}s / ${appState.maxTimelineSec.toFixed(1)}s`;
  }
}

function togglePlayPause() {
  const btn = document.getElementById('btn-play-pause');
  if (appState.previewMode === 'live') {
    appState.isPlaying = !appState.isPlaying;
    if (btn) btn.innerText = appState.isPlaying ? '❚❚ Pause' : '▶ Play';
  } else {
    const vid = document.getElementById('slice-video');
    if (vid) {
      if (vid.paused) {
        vid.muted = true;
        vid.play().catch(() => {});
        appState.isPlaying = true;
        if (btn) btn.innerText = '❚❚ Pause';
      } else {
        vid.pause();
        appState.isPlaying = false;
        if (btn) btn.innerText = '▶ Play';
      }
    }
  }

  if (!appState.isPlaying && !appState.miniPlayerAuditioning) {
    studioAudio.pause();
  }
}

function restartPlayback() {
  seekToTime(0);
  const startInp = document.getElementById('inp-slide-audio-start');
  const startSec = startInp ? parseFloat(startInp.value) || 0 : 0;
  if (studioAudio.readyState >= 1) {
    studioAudio.currentTime = Math.max(0, startSec);
  }
  const btn = document.getElementById('btn-play-pause');
  if (appState.previewMode === 'live') {
    appState.isPlaying = true;
    if (btn) btn.innerText = '❚❚ Pause';
  } else {
    const vid = document.getElementById('slice-video');
    if (vid) {
      vid.muted = true;
      vid.currentTime = 0;
      vid.play().catch(() => {});
      appState.isPlaying = true;
      if (btn) btn.innerText = '❚❚ Pause';
    }
  }
}

/**
 * Synchronizes the real-time HTML5 Audio stream with the current 5.0s window,
 * applying 1.0s fade-in and 1.0s fade-out and updating the Mini-Player playhead at 60 FPS.
 */
function syncRealtimeAudioFrame() {
  if (appState.isRenderingLocked) {
    if (!studioAudio.paused) {
      studioAudio.pause();
    }
    return;
  }

  const startInp = document.getElementById('inp-slide-audio-start');
  const startSec = startInp ? Math.max(0, parseFloat(startInp.value) || 0) : 0;

  // Keep the video element muted so studioAudio provides instant real-time audio without double-play
  const vid = document.getElementById('slice-video');
  if (vid && !vid.muted) {
    vid.muted = true;
  }

  const isVideoActivelyPlaying = appState.previewMode === 'video' && vid && !vid.paused && vid.readyState >= 2;
  const isLiveActivelyPlaying = appState.previewMode === 'live' && appState.isPlaying;
  const isPreviewRunning = !appState.isDraggingSlider && (isLiveActivelyPlaying || isVideoActivelyPlaying);
  const shouldPlayAudio = !appState.isPreviewMuted && (appState.miniPlayerAuditioning || isPreviewRunning);

  let offsetIn5s = 0.0;
  if (appState.miniPlayerAuditioning) {
    offsetIn5s = Math.max(0, Math.min(5.0, appState.miniPlayerAuditionElapsed));
  } else {
    offsetIn5s = Math.max(0, Math.min(5.0, (appState.currentTimeSec || 0) % 5.0));
  }

  updateMiniPlayerVisuals(startSec, offsetIn5s);

  if (!shouldPlayAudio) {
    if (!studioAudio.paused) {
      studioAudio.pause();
    }
    return;
  }

  // Real-time 1.0s fade-in (0.0s -> 1.0s) and 1.0s fade-out (4.0s -> 5.0s) scaled by per-slide volume
  let fadeVol = 1.0;
  if (offsetIn5s < 1.0) {
    fadeVol = Math.max(0.02, offsetIn5s / 1.0);
  } else if (offsetIn5s > 4.0) {
    fadeVol = Math.max(0.02, (5.0 - offsetIn5s) / 1.0);
  }
  const volEl = document.getElementById('inp-slide-audio-volume');
  let slideVol = 1.0;
  if (volEl) {
    const rawPct = parseFloat(volEl.value);
    slideVol = isNaN(rawPct) ? 1.0 : Math.max(0.0, Math.min(1.0, rawPct / 100.0));
  } else {
    const pid = appState.currentPanelId;
    const savedVol = appState.curation?.slide_audio?.[String(pid)]?.volume;
    if (savedVol !== undefined && savedVol !== null && !isNaN(Number(savedVol))) {
      slideVol = Math.max(0.0, Math.min(1.0, Number(savedVol)));
    }
  }
  studioAudio.volume = Math.max(0, Math.min(1, fadeVol * slideVol));

  const targetTrackSec = startSec + offsetIn5s;
  if (studioAudio.readyState >= 1) {
    const maxDur = (studioAudio.duration && isFinite(studioAudio.duration)) ? studioAudio.duration : 500;
    const clampedTarget = Math.max(0, Math.min(Math.max(0, maxDur - 0.05), targetTrackSec));
    if (Math.abs(studioAudio.currentTime - clampedTarget) > 0.32) {
      try {
        studioAudio.currentTime = clampedTarget;
      } catch (e) {}
    }
    if (studioAudio.paused) {
      studioAudio.play().catch(() => {});
    }
  }

  const statusEl = document.getElementById('slide-audio-status');
  if (statusEl) {
    const volPctText = Math.round(slideVol * 100);
    statusEl.innerText = `🔊 Live: ${formatTimeMMSS(targetTrackSec)} (${offsetIn5s.toFixed(1)}s / 5.0s • Vol ${volPctText}% • 1.0s Fade)`;
  }
}

function startPlaybackLoop() {
  let lastTime = performance.now();
  function loop(now) {
    const dt = (now - lastTime) / 1000;
    lastTime = now;

    if (appState.isRenderingLocked) {
      requestAnimationFrame(loop);
      return;
    }

    if (appState.miniPlayerAuditioning) {
      appState.miniPlayerAuditionElapsed += dt;
      if (appState.miniPlayerAuditionElapsed >= 5.0) {
        appState.miniPlayerAuditioning = false;
        appState.miniPlayerAuditionElapsed = 0.0;
        updateMiniPlayerPlayBtnUI(false);
        if (!appState.isPlaying) {
          studioAudio.pause();
        }
      }
    }

    if (appState.isPlaying && appState.previewMode === 'live' && !appState.isDraggingSlider) {
      let nextTime = appState.currentTimeSec + dt;
      if (nextTime >= appState.maxTimelineSec) {
        nextTime = 0.0; // Loop seamlessly within the active panel slice
      }
      seekToTime(nextTime);
    }

    syncRealtimeAudioFrame();
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
}

// ==========================================
// CUSTOM COMPOSER & INDIVIDUAL SLICES SUITE
// ==========================================

function toggleComposerDrawer() {
  const drawer = document.getElementById('composer-drawer');
  const btn = document.getElementById('btn-toggle-composer');
  if (!drawer) return;
  const isOpen = drawer.classList.toggle('open');
  if (btn) btn.innerText = isOpen ? 'Custom Slices & Order ▲' : 'Custom Slices & Order ▼';
}

function renderComposerDrawer() {
  const listEl = document.getElementById('slices-order-list');
  if (!listEl) return;

  const total = appState.slicesOrder.length;
  let html = '';

  appState.slicesOrder.forEach((pid, idx) => {
    const p = PANELS[pid];
    const isChecked = appState.selectedSlices.has(pid);
    html += `
      <div class="slice-order-row ${isChecked ? '' : 'disabled'}">
        <input type="checkbox" ${isChecked ? 'checked' : ''} onchange="toggleSliceSelected(${pid})">
        <span class="slice-badge">#${idx + 1}</span>
        <span class="slice-title">${p.name}</span>
        <span class="slice-dur">5.0s</span>
        <div class="slice-arrows">
          <button class="slice-arrow-btn" ${idx === 0 ? 'disabled' : ''} onclick="moveSliceOrder(${idx}, -1)" title="Move earlier">▲</button>
          <button class="slice-arrow-btn" ${idx === total - 1 ? 'disabled' : ''} onclick="moveSliceOrder(${idx}, 1)" title="Move later">▼</button>
        </div>
      </div>
    `;
  });

  listEl.innerHTML = html;
  updateComposerSummary();
}

function updateComposerSummary() {
  const summaryEl = document.getElementById('composer-summary');
  if (!summaryEl) return;
  const count = appState.slicesOrder.filter(pid => appState.selectedSlices.has(pid)).length;
  const dur = (count * 5.0).toFixed(1);
  summaryEl.innerText = `Selected: ${count} slice(s) (${dur}s total)`;
}

function toggleSliceSelected(pid) {
  if (appState.selectedSlices.has(pid)) {
    if (appState.selectedSlices.size <= 1) {
      showTerminalToast('[WARNING] At least one slice must remain selected.', true);
      renderComposerDrawer();
      return;
    }
    appState.selectedSlices.delete(pid);
  } else {
    appState.selectedSlices.add(pid);
  }
  renderComposerDrawer();
}

function moveSliceOrder(index, delta) {
  const targetIndex = index + delta;
  if (targetIndex < 0 || targetIndex >= appState.slicesOrder.length) return;
  
  const temp = appState.slicesOrder[index];
  appState.slicesOrder[index] = appState.slicesOrder[targetIndex];
  appState.slicesOrder[targetIndex] = temp;
  
  renderComposerDrawer();
}

function resetSlicesOrder() {
  appState.slicesOrder = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];
  appState.selectedSlices = new Set([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
  renderComposerDrawer();
  showTerminalToast('[RESET] Storyboard order and selections restored to defaults.');
}

/**
 * Renders the custom selected storyboard sequence in real time.
 */
async function renderCustomSequence() {
  const selectedOrdered = appState.slicesOrder.filter(pid => appState.selectedSlices.has(pid));
  if (selectedOrdered.length === 0) {
    showTerminalToast('[ERROR] Please select at least one slice to render.', true);
    return;
  }

  const inputEl = document.getElementById('inp-export-path');
  const targetPath = (inputEl ? inputEl.value : '').trim();

  setPreviewMode('video');
  const seqNames = selectedOrdered.map(p => `#${p + 1}`).join(' → ');
  const isExport = Boolean(targetPath && targetPath.trim());
  const fps = isExport ? 25 : Math.max(1, Math.min(60, appState.previewFps || 1));
  showRenderOverlay({
    badge: isExport ? 'CUSTOM EXPORT (25 FPS)' : `CUSTOM PREVIEW (${fps} FPS)`,
    title: 'Rendering Custom Storyboard',
    subtitle: `${selectedOrdered.length} slides (${(selectedOrdered.length * 5.0).toFixed(1)}s • ${isExport ? '25 FPS' : `${fps} FPS preview`}): [${seqNames}]`,
    path: targetPath || null
  });

  try {
    const res = await fetch('/api/render-custom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        selected_panels: selectedOrdered,
        target_path: targetPath ? targetPath : null,
        fps
      })
    });
    const data = await res.json();
    if (res.ok) {
      pollRenderStatus(`Custom Storyboard [${seqNames}] (${fps} FPS)`, `/output/${data.target_file || 'renders/wrapped_custom_export.mp4'}`);
    } else {
      showTerminalToast(`[ERROR] Custom render failed: ${data.detail || 'Server error'}`, true);
      hideRenderOverlay();
    }
  } catch (err) {
    console.error('Custom sequence render error:', err);
    showTerminalToast(`[ERROR] Request failed: ${err.message}`, true);
    hideRenderOverlay();
  }
}

/**
 * Renders the full 50.0s presentation covering all 10 slides.
 */
async function renderFullVideo() {
  setPreviewMode('video');
  showRenderOverlay({
    badge: 'FULL EXPORT (25 FPS)',
    title: 'Rendering Complete Story',
    subtitle: 'All 10 slides • 50.0s (1,250 frames @ 25 FPS)',
    path: null
  });

  try {
    const res = await fetch('/api/render-full', { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      pollRenderStatus('Full Presentation', `/output/${data.target_file}`);
    } else {
      hideRenderOverlay();
      showTerminalToast(`[ERROR] Full render failed: ${data.detail || 'Server busy'}`, true);
    }
  } catch (err) {
    console.error('Full render error:', err);
    hideRenderOverlay();
    showTerminalToast(`[ERROR] Full render request failed: ${err.message}`, true);
  }
}

/**
 * Saves current panel state and shuts down the detached background Studio server.
 */
async function shutdownStudioServer() {
  const btn = document.getElementById('btn-shutdown-studio');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏻ Stopping...';
  }
  try {
    appState.miniPlayerAuditioning = false;
    appState.isPlaying = false;
    studioAudio.pause();
    await submitCurrentPanel({ skipIframeReload: true, silentToast: true });
  } catch (err) {}

  try {
    await fetch('/api/shutdown', { method: 'POST' });
  } catch (err) {}

  showTerminalToast('✓ Background Studio server stopped. You may close this tab.');
  if (btn) {
    btn.textContent = '⏻ Studio Offline';
  }
}

