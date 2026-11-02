const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1080, height: 1920 });

  const storyPath = path.resolve('output/storyboard/story.html');
  const storyUrl = 'file:///' + storyPath.replace(/\\/g, '/');

  await page.goto(storyUrl, { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 1000));

  // Slide 9 is index 8 in 0-based indexing (or let's find the exact slide element)
  // Let's check slide IDs
  const slideIds = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('.slide')).map(s => s.id);
  });
  console.log('Slide IDs:', slideIds);

  // Jump to slide 9: "Most Listened Songs"
  await page.evaluate(() => {
    if (typeof window.seekToSlide === 'function') {
      window.seekToSlide(8);
    } else {
      document.querySelectorAll('.slide').forEach((s, idx) => {
        s.classList.toggle('active', idx === 8);
      });
    }
  });
  await new Promise(r => setTimeout(r, 800));
  await page.screenshot({ path: 'img/story_slide9.png' });
  fs.copyFileSync('img/story_slide9.png', 'C:/Users/alfa/.gemini/antigravity/brain/874cc975-52b6-48e1-8bda-ddc38a06826d/story_slide9.png');
  console.log('Captured story_slide9.png');

  // Jump to slide 10: "Most Listened Artists"
  await page.evaluate(() => {
    if (typeof window.seekToSlide === 'function') {
      window.seekToSlide(9);
    } else {
      document.querySelectorAll('.slide').forEach((s, idx) => {
        s.classList.toggle('active', idx === 9);
      });
    }
  });
  await new Promise(r => setTimeout(r, 800));
  await page.screenshot({ path: 'img/story_slide10.png' });
  fs.copyFileSync('img/story_slide10.png', 'C:/Users/alfa/.gemini/antigravity/brain/874cc975-52b6-48e1-8bda-ddc38a06826d/story_slide10.png');
  console.log('Captured story_slide10.png');

  // Also take a screenshot of the Web Studio live app at panel 8 and panel 9!
  const studioPage = await browser.newPage();
  await studioPage.setViewport({ width: 1440, height: 900 });
  await studioPage.goto('http://127.0.0.1:8000', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 1500));

  // Navigate to Panel 8 (Most Listened Songs)
  await studioPage.evaluate(() => {
    if (typeof switchPanel === 'function') switchPanel(8);
  });
  await new Promise(r => setTimeout(r, 800));
  await studioPage.screenshot({ path: 'scratch/studio_panel_8.png' });
  fs.copyFileSync('scratch/studio_panel_8.png', 'C:/Users/alfa/.gemini/antigravity/brain/874cc975-52b6-48e1-8bda-ddc38a06826d/studio_panel_8.png');

  // Navigate to Panel 9 (Most Listened Artists)
  await studioPage.evaluate(() => {
    if (typeof switchPanel === 'function') switchPanel(9);
  });
  await new Promise(r => setTimeout(r, 800));
  await studioPage.screenshot({ path: 'scratch/studio_panel_9.png' });
  fs.copyFileSync('scratch/studio_panel_9.png', 'C:/Users/alfa/.gemini/antigravity/brain/874cc975-52b6-48e1-8bda-ddc38a06826d/studio_panel_9.png');

  console.log('Captured studio panels 8 and 9.');
  await browser.close();
})();

