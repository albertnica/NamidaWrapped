/**
 * Preview Engine Module
 * Captures static slide screenshots for rapid visual inspection.
 * Author: Antigravity
 */

const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

/**
 * Captures verification frames for each slide.
 * @param {Object} options Preview options
 */
async function capturePreviews(options = {}) {
  const width = options.width || 1080;
  const height = options.height || 1920;
  const chromePath = options.chromePath || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const storyPath = options.storyPath || path.resolve('output/storyboard/story.html');
  const storyUrl = storyPath.startsWith('file://') ? storyPath : 'file://' + storyPath.replace(/\\/g, '/');
  const outputDir = options.outputDir || path.resolve('output/previews');

  fs.mkdirSync(outputDir, { recursive: true });

  const browser = await puppeteer.launch({
    executablePath: chromePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: 1 });
  await page.goto(storyUrl, { waitUntil: 'networkidle0' });

  const times = options.times || [
    { name: 'slide_1_year_in_sound', t: 2.5 },
    { name: 'slide_2_big_numbers', t: 7.5 },
    { name: 'slide_3_listening_clock', t: 12.5 },
    { name: 'slide_4_top_songs', t: 17.5 },
    { name: 'slide_5_top_albums', t: 22.5 },
    { name: 'slide_6_top_artists', t: 27.5 },
    { name: 'slide_7_top_discoveries', t: 32.5 },
    { name: 'slide_8_top_genres', t: 37.5 },
    { name: 'slide_9_most_listened_songs', t: 42.5 },
    { name: 'slide_10_most_listened_artists', t: 47.5 }
  ];

  for (const s of times) {
    await page.evaluate((t) => window.seek(t), s.t);
    await new Promise((r) => setTimeout(r, 100));
    const dest = path.join(outputDir, `${s.name}.jpg`);
    await page.screenshot({ path: dest, type: 'jpeg', quality: 90 });
    console.log(`Rendered preview: ${path.basename(dest)}`);
  }

  await browser.close();
  console.log(`All slide previews saved to: ${outputDir}`);
}

module.exports = { capturePreviews };

if (require.main === module) {
  capturePreviews().catch((err) => {
    console.error('Preview capture failed:', err);
    process.exit(1);
  });
}
