const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

(async () => {
  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const browser = await puppeteer.launch({
    executablePath: chromePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  await page.goto('http://127.0.0.1:8000', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 3000));

  const dest = path.resolve('img/web_studio_preview.png');
  await page.screenshot({ path: dest, type: 'png' });
  console.log('Saved web_studio_preview.png to', dest);

  const artifactDest = 'C:/Users/alfa/.gemini/antigravity/brain/874cc975-52b6-48e1-8bda-ddc38a06826d/web_studio_preview.png';
  fs.copyFileSync(dest, artifactDest);
  console.log('Copied to artifact directory:', artifactDest);

  await browser.close();
})();

