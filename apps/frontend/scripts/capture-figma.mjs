import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
const browser = await chromium.launch({executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const out='../../artifacts/figma/screenshots';mkdirSync(out,{recursive:true});
for(const [name,path,email,password] of [
 ['landing','/'],['login','/login'],['patient','/dashboard','mai','Mai-patient-2026'],['hcp','/hcp','an','An-hcp-2026'],['admin','/admin','ha','Ha-admin-2026'],['reviewer','/reviewer','huy','Huy-review-2026'],['support','/staff','khoa','Khoa-support-2026']]) {
 const context=await browser.newContext({viewport:{width:1440,height:1050}});
 if(email)await context.request.post('http://127.0.0.1:5185/api/auth/login',{data:{email:`${email}.demo@example.com`,password}});
 const page=await context.newPage();await page.goto(`http://127.0.0.1:5185${path}`);await page.waitForTimeout(500);await page.screenshot({path:`${out}/${name}-1440.png`,fullPage:true});
 await page.setViewportSize({width:375,height:900});await page.screenshot({path:`${out}/${name}-375.png`,fullPage:true});
 console.log(name, await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,brokenImages:[...document.images].filter(i=>!i.complete||!i.naturalWidth).map(i=>i.src)})));
 await context.close();
}
await browser.close();
