const puppeteer = require('puppeteer-core');
const fs = require('fs');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: 'new'
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  await page.goto('http://127.0.0.1:8000', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 2000));

  // Directly render panel form 8 without auto-triggering background video slice render
  await page.evaluate(() => {
    appState.currentPanel = 8;
    updateHeader();
    updateTabsUI();
    renderPanelForm(8);
    const iframe = document.getElementById('story-iframe');
    if (iframe) iframe.src = `/story?t=${Date.now()}&panels=8`;
  });
  await new Promise(r => setTimeout(r, 1200));
  await page.screenshot({ path: 'scratch/live_studio_panel8.png' });
  fs.copyFileSync('scratch/live_studio_panel8.png', 'C:/Users/alfa/.gemini/antigravity/brain/874cc975-52b6-48e1-8bda-ddc38a06826d/live_studio_panel8.png');

  // Directly render panel form 9
  await page.evaluate(() => {
    appState.currentPanel = 9;
    updateHeader();
    updateTabsUI();
    renderPanelForm(9);
    const iframe = document.getElementById('story-iframe');
    if (iframe) iframe.src = `/story?t=${Date.now()}&panels=9`;
  });
  await new Promise(r => setTimeout(r, 1200));
  await page.screenshot({ path: 'scratch/live_studio_panel9.png' });
  fs.copyFileSync('scratch/live_studio_panel9.png', 'C:/Users/alfa/.gemini/antigravity/brain/874cc975-52b6-48e1-8bda-ddc38a06826d/live_studio_panel9.png');

  // Also test dropdown menu position and z-index on Panel 9
  await page.click('#btn-theme-selector');
  await new Promise(r => setTimeout(r, 600));
  await page.screenshot({ path: 'scratch/live_studio_dropdown.png' });
  fs.copyFileSync('scratch/live_studio_dropdown.png', 'C:/Users/alfa/.gemini/antigravity/brain/874cc975-52b6-48e1-8bda-ddc38a06826d/live_studio_dropdown.png');

  await browser.close();
  console.log('Finished capturing live panels and dropdown.');
})();
