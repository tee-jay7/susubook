// HTML -> PDF via headless Chrome.
//
// Chrome is used rather than a LaTeX engine because the documents contain
// rendered SVG diagrams, PNG screenshots and wide tables, all of which it
// handles natively and identically to how they were authored.

import puppeteer from "puppeteer";
import { pathToFileURL } from "node:url";
import path from "node:path";

const [htmlPath, pdfPath] = process.argv.slice(2);
if (!htmlPath || !pdfPath) {
  console.error("usage: node render.mjs <input.html> <output.pdf>");
  process.exit(1);
}

const browser = await puppeteer.launch({ headless: "new" });
const page = await browser.newPage();

await page.goto(pathToFileURL(path.resolve(htmlPath)).href, {
  waitUntil: "networkidle0",
  timeout: 120000,
});

// Belt and braces: wait for every image to finish decoding before printing,
// or a slow SVG can be captured as a blank box.
await page.evaluate(async () => {
  await Promise.all(
    Array.from(document.images)
      .filter((img) => !img.complete)
      .map((img) => new Promise((res) => { img.onload = img.onerror = res; }))
  );
});

await page.pdf({
  path: pdfPath,
  format: "A4",
  printBackground: true,
  margin: { top: "20mm", bottom: "20mm", left: "18mm", right: "18mm" },
  displayHeaderFooter: true,
  headerTemplate: "<div></div>",
  footerTemplate: `
    <div style="width:100%;font-size:7.5pt;color:#8a969c;
                font-family:Helvetica,Arial,sans-serif;
                padding:0 18mm;display:flex;justify-content:space-between;">
      <span>SusuBook · CSCD602 Advanced Software Engineering</span>
      <span class="pageNumber"></span>
    </div>`,
});

await browser.close();
