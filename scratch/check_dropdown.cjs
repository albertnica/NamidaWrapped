const puppeteer = require('puppeteer-core');
(async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: 'new'
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  await page.goto('http://127.0.0.1:8000', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 1500));
  
  await page.click('#btn-theme-selector');
  await new Promise(r => setTimeout(r, 500));

  const overlapCheck = await page.evaluate(() => {
    // Exact overlap region between dropdown and phone frame
    const testX = 920;
    const testY = 250;
    const el = document.elementFromPoint(testX, testY);
    function getStack(node) {
      const arr = [];
      while (node) {
        arr.push({ tag: node.tagName, id: node.id, class: node.className });
        node = node.parentElement;
      }
      return arr;
    }
    return {
      testX, testY,
      topElementTag: el ? el.tagName : null,
      topElementClass: el ? el.className : null,
      topElementId: el ? el.id : null,
      stack: getStack(el)
    };
  });
  console.log('overlapCheck at 920, 250:', JSON.stringify(overlapCheck, null, 2));
  
  await browser.close();
})();
