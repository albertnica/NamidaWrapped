/**
 * Video Rendering Engine Module
 * Uses Puppeteer to step deterministic animation time and pipes frames to FFmpeg image2pipe.
 * Author: Antigravity
 */

const puppeteer = require('puppeteer-core');
const { spawn, execFile } = require('child_process');
const { promisify } = require('util');
const execFileAsync = promisify(execFile);
const path = require('path');
const fs = require('fs');

/**
 * Builds composite multi-track audio soundtrack matching the active panels.
 * Why: Each 5.0s slide can have its own local audio path and start second with 1.0s fade in and 1.0s fade out.
 * @param {Array<number>} panels Panel indices sequence
 * @param {Object} slideAudio Mapping from panel ID to { path, start_sec }
 * @param {string} defaultSoundtrack Default fallback audio path
 * @param {string} tempDir Directory to store temporary audio slices
 * @returns {Promise<string>} Path to combined AAC soundtrack
 */
async function prepareCompositeAudio(panels, slideAudio, defaultSoundtrack, tempDir) {
  fs.mkdirSync(tempDir, { recursive: true });
  const segmentFiles = [];

  for (let i = 0; i < panels.length; i++) {
    const pid = panels[i];
    const cfg = (slideAudio && slideAudio[String(pid)]) || (slideAudio && slideAudio[pid]) || {};
    let trackPath = cfg.path && fs.existsSync(cfg.path) ? cfg.path : defaultSoundtrack;
    let startSec = cfg.start_sec !== undefined ? parseFloat(cfg.start_sec) : (trackPath === defaultSoundtrack ? pid * 5.0 : 0.0);
    if (isNaN(startSec) || startSec < 0) startSec = 0.0;

    let rawVol = cfg.volume !== undefined ? parseFloat(cfg.volume) : 1.0;
    if (isNaN(rawVol) || rawVol < 0) rawVol = 1.0;
    if (rawVol > 1.0) rawVol = rawVol / 100.0;
    const vol = Math.max(0.0, Math.min(1.0, rawVol));
    const afFilter = `volume=${vol.toFixed(3)},afade=t=in:st=0:d=1,afade=t=out:st=4:d=1`;

    const segPath = path.join(tempDir, `seg_${pid}_${i}_${Date.now()}.aac`);
    const args = [
      '-y',
      '-ss', startSec.toFixed(2),
      '-t', '5.0',
      '-i', trackPath,
      '-af', afFilter,
      '-c:a', 'aac',
      '-b:a', '192k',
      segPath
    ];

    try {
      await execFileAsync('ffmpeg', args, { windowsHide: true });
      segmentFiles.push(segPath);
    } catch (err) {
      console.warn(`[Warning] Failed to slice audio for panel ${pid}, falling back to default:`, err.message);
      try {
        const fbArgs = [
          '-y',
          '-ss', String((pid * 5.0).toFixed(2)),
          '-t', '5.0',
          '-i', defaultSoundtrack,
          '-af', afFilter,
          '-c:a', 'aac',
          '-b:a', '192k',
          segPath
        ];
        await execFileAsync('ffmpeg', fbArgs, { windowsHide: true });
        segmentFiles.push(segPath);
      } catch (err2) {
        console.error(`[Error] Fallback audio slice failed:`, err2.message);
      }
    }
  }

  if (segmentFiles.length === 1) {
    return segmentFiles[0];
  }

  if (segmentFiles.length === 0) {
    return defaultSoundtrack;
  }

  // Concat all segments
  const concatListPath = path.join(tempDir, `concat_${Date.now()}.txt`);
  const listContent = segmentFiles.map(f => `file '${f.replace(/\\/g, '/')}'`).join('\n');
  fs.writeFileSync(concatListPath, listContent, 'utf-8');

  const combinedPath = path.join(tempDir, `combined_${Date.now()}.aac`);
  await execFileAsync('ffmpeg', [
    '-y',
    '-f', 'concat',
    '-safe', '0',
    '-i', concatListPath,
    '-c:a', 'copy',
    combinedPath
  ], { windowsHide: true });

  return combinedPath;
}

/**
 * Renders full vertical story video.
 * @param {Object} options Rendering options
 * @param {string} options.storyPath Absolute file URL or path to story.html
 * @param {string} options.outputPath Target MP4 output path
 * @param {string} [options.legacyPath] Optional legacy output path copy
 * @param {string} options.soundtrackPath Audio track file path
 * @param {number} [options.fps=25] Frames per second
 * @param {number} [options.durationSec=28.5] Duration in seconds
 * @param {number} [options.width=1080] Video width
 * @param {number} [options.height=1920] Video height
 * @param {string} [options.chromePath] Chrome executable path
 */
async function renderVideo(options = {}) {
  const fps = options.fps || 25;
  const width = options.width || 1080;
  const height = options.height || 1920;
  const chromePath = options.chromePath || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

  // Resolve active panels sequence
  let panels = options.panels;
  if (!panels || !Array.isArray(panels) || panels.length === 0) {
    if (options.panelId !== undefined) {
      panels = [options.panelId];
    } else if (options.segments && options.segments.length > 0) {
      panels = options.segments.map(s => s.panelId !== undefined ? s.panelId : 0);
    } else {
      panels = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];
    }
  }

  const slideDurationSec = 5.0;
  const totalDurationSec = panels.length * slideDurationSec;
  const totalFrames = Math.floor(totalDurationSec * fps);

  const storyPath = options.storyPath || path.resolve('output/storyboard/story.html');
  const storyUrl = storyPath.startsWith('file://') ? storyPath : 'file://' + storyPath.replace(/\\/g, '/');
  const outputPath = options.outputPath || path.resolve(`output/renders/wrapped_${new Date().getFullYear()}.mp4`);
  const soundtrackPath = options.soundtrackPath || path.resolve('output/audio/soundtrack.aac');

  console.log(`[1/4] Initializing Video Render Engine...`);
  console.log(`      Resolution : ${width}x${height} (9:16 Vertical)`);
  console.log(`      Framerate  : ${fps} FPS`);
  console.log(`      Panels     : [${panels.join(', ')}] (${panels.length} slide(s))`);
  console.log(`      Duration   : ${totalDurationSec.toFixed(2)}s (${totalFrames} frames)`);
  console.log(`      Output     : ${outputPath}`);

  fs.mkdirSync(path.dirname(outputPath), { recursive: true });

  // Prepare per-slide audio with 1s fade-in and 1s fade-out
  console.log(`[2/4] Preparing per-slide audio tracks (5.0s with 1.0s in/out fades)...`);
  const tempAudioDir = path.resolve('output/audio/temp_audio');
  let compositeAudioPath = soundtrackPath;
  try {
    compositeAudioPath = await prepareCompositeAudio(panels, options.slideAudio, soundtrackPath, tempAudioDir);
  } catch (audioErr) {
    console.warn(`[Warning] Could not prepare composite audio, using default soundtrack: ${audioErr.message}`);
  }

  // Spawn FFmpeg with composite audio and frame stream
  console.log(`[3/4] Spawning FFmpeg process...`);
  const ffmpegArgs = [
    '-y',
    '-f', 'image2pipe',
    '-vcodec', 'mjpeg',
    '-r', String(fps),
    '-i', '-', // stdin stream
    '-i', compositeAudioPath,
    '-c:v', 'libx264',
    '-preset', 'fast',
    '-crf', '18',
    '-pix_fmt', 'yuv420p',
    '-c:a', 'aac',
    '-b:a', '192k',
    '-t', String(totalDurationSec),
    outputPath
  ];

  const ffmpeg = spawn('ffmpeg', ffmpegArgs, { windowsHide: true });
  ffmpeg.stderr.on('data', (data) => {
    const str = data.toString();
    if (str.includes('Error') || str.includes('fatal')) {
      console.error('FFmpeg error:', str);
    }
  });

  // Launch Chrome
  console.log(`[3/4] Launching headless Chrome & streaming frames...`);
  const browser = await puppeteer.launch({
    executablePath: chromePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
  });

  const page = await browser.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: 1 });
  await page.goto(storyUrl, { waitUntil: 'networkidle0' });

  // Configure story DOM with active panels sequence (sets exact number of top bars)
  await page.evaluate((activePanels) => {
    if (typeof window.setPanels === 'function') {
      window.setPanels(activePanels);
    }
  }, panels);

  const startTime = Date.now();
  for (let f = 0; f < totalFrames; f++) {
    const t = f / fps;
    await page.evaluate((timeSec) => window.seek(timeSec), t);

    const buffer = await page.screenshot({ type: 'jpeg', quality: 85 });
    const canWrite = ffmpeg.stdin.write(buffer);
    if (!canWrite) {
      await new Promise((resolve) => ffmpeg.stdin.once('drain', resolve));
    }

    if ((f + 1) % 50 === 0 || f === totalFrames - 1) {
      const pct = (((f + 1) / totalFrames) * 100).toFixed(1);
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      process.stdout.write(`\r      Progress: ${f + 1}/${totalFrames} frames (${pct}%) [${elapsed}s elapsed]`);
    }
  }

  console.log('\n      Closing stream and finalizing video...');
  ffmpeg.stdin.end();
  await browser.close();

  await new Promise((resolve) => ffmpeg.on('close', resolve));

  if (options.legacyPath && fs.existsSync(outputPath)) {
    fs.copyFileSync(outputPath, options.legacyPath);
  }

  console.log(`[SUCCESS] Video rendered successfully at: ${outputPath}`);
  return outputPath;
}

module.exports = { renderVideo };

if (require.main === module) {
  renderVideo().catch((err) => {
    console.error('Render failure:', err);
    process.exit(1);
  });
}
