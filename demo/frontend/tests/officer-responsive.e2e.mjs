const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
import assert from 'node:assert/strict';
import fs from 'node:fs';
// Run only against an isolated synthetic server, never against production.
// PLAYWRIGHT_MODULE, CHROMIUM_EXECUTABLE, OFFICER_E2E_PASSWORD,
// OFFICER_E2E_APPLICATION_ID, OFFICER_E2E_BASE_URL, E2E_OUTPUT_DIR.
const E = process.env.E2E_OUTPUT_DIR;
assert.ok(E, 'Set E2E_OUTPUT_DIR to a private artifact directory');
fs.mkdirSync(E + '/screenshots', { recursive: true, mode: 0o700 });
fs.mkdirSync(E + '/results', { recursive: true, mode: 0o700 });
const host = process.env.OFFICER_E2E_BASE_URL || 'http://127.0.0.1:5173';
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(host).hostname), 'Synthetic loopback server required');
const mode = 'responsive', port = new URL(host).port;
assert.ok(process.env.OFFICER_E2E_PASSWORD, 'Synthetic officer password required');
const actors = { application_id: Number(process.env.OFFICER_E2E_APPLICATION_ID) };
assert.ok(Number.isSafeInteger(actors.application_id) && actors.application_id > 0);
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE,headless:true,args:['--no-sandbox']});
const c=await browser.newContext(),p=await c.newPage(),errors=[];p.on('pageerror',e=>errors.push(String(e)));
await c.route('**/*',r=>['127.0.0.1','localhost'].includes(new URL(r.request().url()).hostname)||/^(data|blob):/.test(r.request().url())?r.continue():r.abort());
await p.goto(host+'/officer');await p.getByLabel('담당자 비밀번호').fill(process.env.OFFICER_E2E_PASSWORD);await p.getByRole('button',{name:'로그인',exact:true}).click();await p.getByRole('button',{name:'로그아웃',exact:true}).waitFor();
async function ink(){await p.waitForFunction(()=>[...document.querySelectorAll('.viewer canvas')].some(c=>{const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=0;i<d.length;i+=64)if(d[i+3]&&Math.min(d[i],d[i+1],d[i+2])<230)n++;return n>100}),{},{timeout:20000})}
async function measure(){return p.evaluate(()=>{const box=e=>{if(!e)return null;const r=e.getBoundingClientRect(),s=getComputedStyle(e);return{x:r.x,y:r.y,width:r.width,height:r.height,scrollWidth:e.scrollWidth,clientWidth:e.clientWidth,overflowX:s.overflowX,minWidth:s.minWidth,grid:s.gridTemplateColumns}};return{viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio},document:{scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth},elements:Object.fromEntries(['.review','.review__split','.review__left','.review__right','.viewer__bar','.viewer__stage','.decision textarea','.decision__actions','.alist__tabs','.alist__bar','.alist__panel'].map(s=>[s,box(document.querySelector(s))])),toolbar:[...document.querySelectorAll('.viewer__bar button')].map(e=>({label:e.getAttribute('aria-label'),...box(e)})),canvas:[...document.querySelectorAll('.viewer canvas')].map(e=>({...box(e),pixelWidth:e.width,pixelHeight:e.height})),outside:[...document.querySelectorAll('body *')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&r.right>innerWidth+1&&!e.closest('.viewer__stage,.alist__panel,.sheet6,.review__tabs')}).slice(0,15).map(e=>({tag:e.tagName,class:e.className,...box(e)}))}})}
const rows=[];
for(const [width,height] of [[320,700],[360,800],[375,812],[390,844],[430,932],[768,1024],[1024,768],[1280,800],[1440,900]]){
 await p.setViewportSize({width,height});await p.goto(host+'/officer');await p.locator('.alist__table').waitFor();await p.waitForTimeout(200);const list=await measure();await p.screenshot({path:`${E}/screenshots/${mode}-${port}-${width}-list.png`,fullPage:true});
 await p.goto(host+`/officer/review/${actors.application_id}`);await p.getByRole('navigation',{name:'작성서식',exact:true}).waitFor();await p.getByRole('navigation',{name:'작성서식',exact:true}).getByRole('button').first().click();await ink();await p.waitForTimeout(200);const detail=await measure();
 assert.ok(list.document.scrollWidth <= width + 1, `List overflow at ${width}`);
 assert.ok(detail.document.scrollWidth <= width + 1, `Review overflow at ${width}`);
 assert.ok(detail.elements['.viewer__stage'].scrollWidth <= detail.elements['.viewer__stage'].clientWidth + 1, `Fit overflow at ${width}`);
 assert.ok(detail.elements['.review__right'].width > 150, `Review panel collapsed at ${width}`);
 assert.ok(detail.elements['.decision textarea'].width > 100, `Memo collapsed at ${width}`);
 const bar = detail.elements['.viewer__bar'];
 assert.ok(detail.toolbar.every(t => t.x >= bar.x && t.x + t.width <= bar.x + bar.width + 1 && t.width >= 44 && t.height >= 44), `Toolbar clipped at ${width}`);
 await p.getByLabel('검토 메모').fill('Synthetic responsive regression, unsaved');
 await p.getByRole('navigation',{name:'작성서식',exact:true}).getByRole('button').last().click();await ink();
 assert.equal(await p.getByLabel('검토 메모').inputValue(), 'Synthetic responsive regression, unsaved');
 await p.getByRole('button',{name:'확대',exact:true}).click();await ink();
 const zoomed = await measure();assert.ok(zoomed.document.scrollWidth <= width + 1, `Zoom leaked out of stage at ${width}`);
 await p.getByRole('button',{name:'너비 맞춤',exact:true}).click();await ink();
 await p.screenshot({path:`${E}/screenshots/${mode}-${port}-${width}-detail.png`,fullPage:true});
 rows.push({width,height,list,detail});fs.writeFileSync(`${E}/results/${mode}-${port}-matrix.json`,JSON.stringify({chromium:browser.version(),rows,errors},null,2));console.log(width,list.document.scrollWidth,detail.document.scrollWidth,'right',Math.round(detail.elements['.review__right'].x),'bar',detail.elements['.viewer__bar'].scrollWidth);
}
// Keyboard regression: a wide paper-table action must fit the visible review panel.
await p.setViewportSize({ width: 320, height: 700 });
const failureId = Number(process.env.OFFICER_E2E_FAILURE_APPLICATION_ID || actors.application_id);
await p.goto(host + `/officer/review/${failureId}`);
await p.getByLabel('검토 메모').waitFor();
if (process.env.OFFICER_E2E_FAILURE_APPLICATION_ID) {
  assert.equal(await p.locator('.verdict__reasons').getAttribute('open'), '');
  assert.ok(await p.locator('.verdict__reasons .reasons li').count() > 0);
}
await p.getByRole('button', { name: '처음으로', exact: true }).focus();
let controls = 0;
for (let i = 0; i < 80; i++) {
  await p.keyboard.press('Tab');
  const f = await p.evaluate(() => {
    const e = document.activeElement, r = e.getBoundingClientRect(), css = getComputedStyle(e);
    return { tag: e.tagName, left: r.left, right: r.right, visible: e.matches(':focus-visible'),
      outline: parseFloat(css.outlineWidth), style: css.outlineStyle, viewport: innerWidth };
  });
  if (f.tag === 'BODY') break; // Focus has left the document for browser chrome.
  assert.ok(f.left >= -2 && f.right <= f.viewport + 2, `Focus clipped: ${JSON.stringify(f)}`);
  assert.ok(f.visible && f.outline > 0 && f.style !== 'none', `Focus invisible: ${JSON.stringify(f)}`);
  controls++;
}
assert.ok(controls > 15, 'Expected document, viewer and decision controls');
await p.keyboard.press('Shift+Tab');
assert.notEqual(await p.evaluate(() => document.activeElement.tagName), 'BODY');
fs.writeFileSync(`${E}/results/keyboard-${port}.json`, JSON.stringify({ controls, tab: true, shiftTab: true }));
assert.deepEqual(errors, []);
await browser.close();
