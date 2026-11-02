const puppeteer = require('puppeteer-core');
const path = require('path');

(async () => {
  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const browser = await puppeteer.launch({
    executablePath: chromePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  console.log('Capturing Web Studio interface...');
  const studioPage = await browser.newPage();
  await studioPage.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  await studioPage.goto('http://127.0.0.1:8000', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 2500));

  // Ensure Panel 0 (Step 1) is cleanly rendered and iframe is loaded
  await studioPage.evaluate(() => {
    if (typeof switchPanel === 'function') {
      appState.currentPanel = 0;
      updateHeader();
      updateTabsUI();
      renderPanelForm(0);
      const iframe = document.getElementById('story-iframe');
      if (iframe) iframe.src = `/story?t=${Date.now()}&panels=0`;
    }
  });
  await new Promise(r => setTimeout(r, 1500));
  await studioPage.screenshot({ path: path.resolve('img/web_studio_preview.png'), type: 'png' });
  console.log('Successfully saved img/web_studio_preview.png');

  await studioPage.close();
  await browser.close();
})();
