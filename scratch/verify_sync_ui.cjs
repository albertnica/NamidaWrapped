const puppeteer = require('C:\\Users\\alfa\\Desktop\\Scripts\\NamidaWrapped\\node_modules\\puppeteer-core');
const path = require('path');

async function testSyncUI() {
  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const browser = await puppeteer.launch({
    executablePath: chromePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });

  console.log('Navigating to http://127.0.0.1:8000 ...');
  await page.goto('http://127.0.0.1:8000', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 2000));

  const dest = 'C:\\Users\\alfa\\.gemini\\antigravity\\brain\\874cc975-52b6-48e1-8bda-ddc38a06826d\\verify_sync_ui.png';
  await page.screenshot({ path: dest, fullPage: true });
  console.log('Saved screenshot to:', dest);

  await browser.close();
}

testSyncUI().catch(err => {
  console.error(err);
  process.exit(1);
});
