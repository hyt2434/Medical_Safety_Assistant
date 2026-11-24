import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';

test.skip(process.env.INTAKE_REAL_E2E !== '1', 'Run via the guarded PostgreSQL integration test; no dev DB automation');
const root=resolve('../..');
const panadol='PC_43a0331111c5b1d01282b18e',alltrex='PC_74a2c1a855efd9c665d41578';
const sentence='Tôi đang uống thuốc tên "Panadol Viên Sủi", hàm lượng 500mg, dạng viên sủi, mỗi sáng một viên; Tôi đang uống thuốc tên "Alltrex", hàm lượng 2,5mg, dạng viên nén.';
function oracle(workflow_id?:string,assessment_id?:string) {
  return JSON.parse(execFileSync(process.env.E2E_PYTHON!,['-m','tests.integration.test_intake_browser_e2e'],{
    cwd:root,env:process.env,input:JSON.stringify({workflow_id,assessment_id}),encoding:'utf8'}));
}
function trace(label:string,data:unknown){console.log(label+': '+JSON.stringify(data));}
function controlTrace(label:string,data:ReturnType<typeof oracle>) {
  trace(label,{counts:data.counts,entries:data.entries.map((e:{confirmed:boolean;medication:Record<string,unknown>})=>({confirmed:e.confirmed,
    name:e.medication.name_raw,strength:e.medication.strength_raw,form:e.medication.dosage_form_raw,dose:e.medication.dose_raw})),
    matches:data.matches,assessment:{coverage:data.assessment?.checks.ddi.coverage,source_levels:data.assessment?.source_levels,
      control_pair:data.assessment?.control_pair,control_level:data.assessment?.control_level,source_hash:data.assessment?.control_source_hash}});
}
async function login(page:Page,email=process.env.UI_EMAIL!) {
  await page.goto('/login');await page.getByLabel('Email',{exact:true}).fill(email);
  await page.getByLabel('Mật khẩu',{exact:true}).fill(process.env.UI_PASSWORD!);
  await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();await expect(page).toHaveURL('/dashboard');
}
async function logout(page:Page) {
  await page.getByRole('button',{name:'Đăng xuất',exact:true}).click();
  await page.getByRole('dialog').getByRole('button',{name:'Đăng xuất',exact:true}).click();
  await expect(page.getByLabel('Email',{exact:true})).toBeVisible();
}
async function fresh(page:Page,mode:string) {
  const capability=page.waitForResponse(r=>r.url().includes('/api/v1/intake/capabilities'));
  await page.goto('/intake?mode='+mode);await capability;
  await expect(page.locator('.intake-workspace')).toHaveAttribute('aria-busy','false');
  const start=page.getByRole('button',{name:'Cuộc hội thoại mới',exact:true});
  if(await start.isVisible()) {await start.click();await expect(page.locator('.intake-workspace')).toHaveAttribute('aria-busy','false');}
}
async function addProduct(page:Page,query:string,id:string,strength:string) {
  await page.getByRole('textbox',{name:'Tìm thuốc trong danh mục',exact:true}).fill(query);
  const response=page.waitForResponse(r=>r.url().includes('/api/reference/medications?'));
  await page.getByRole('button',{name:'Tìm sản phẩm',exact:true}).click();
  const catalog=(await (await response).json()).medications;
  const product=catalog.find((p:{source_medication_id:string})=>p.source_medication_id===id);expect(product).toBeTruthy();
  await page.getByRole('button',{name:'Chọn '+product.brand_name+' — '+id,exact:true}).click();
  await page.getByLabel('Hàm lượng theo nhãn',{exact:true}).fill(strength);
  await page.getByLabel('Dạng thuốc',{exact:true}).fill(product.dosage_form || 'viên nén');
  await page.getByLabel('Liều mỗi lần',{exact:true}).fill('một viên');
  await page.getByLabel('Thời điểm dùng',{exact:true}).fill('mỗi sáng');
  const saved=page.waitForResponse(r=>r.url().endsWith('/api/v1/intake/manual'));
  await page.getByRole('button',{name:'Lưu thuốc vào bản nháp',exact:true}).click();
  const review=await (await saved).json();expect(review.state).toBe('AWAITING_CONFIRMATION');
  await expect(page.locator('.intake-workspace')).toHaveAttribute('aria-busy','false');return {review,product,catalog};
}
async function confirmAndAssess(page:Page,review:{workflow_id:string},baseline:unknown,control=true) {
  const before=oracle(review.workflow_id);expect(before.counts).toEqual(baseline);
  await page.getByRole('region',{name:'Bản nháp đã lưu trên máy chủ'}).getByRole('checkbox').check();
  const confirmation=page.waitForResponse(r=>r.url().endsWith('/api/v1/intake/confirm'));
  await page.getByRole('button',{name:'Xác nhận danh sách',exact:true}).dblclick();
  expect((await confirmation).status()).toBe(200);
  await expect(page.getByRole('button',{name:'Nhận diện và đánh giá tương tác',exact:true})).toBeEnabled();
  const assessed=page.waitForResponse(r=>r.url().endsWith('/api/v1/intake/actions'));
  await page.getByRole('button',{name:'Nhận diện và đánh giá tương tác',exact:true}).click();
  const response=await assessed;expect(response.status()).toBe(200);const result=await response.json();
  const actual=oracle(review.workflow_id,control?result.assessment_id:undefined);
  if(control) {
    expect(actual.assessment.control_level).toBe('Moderate');expect(actual.assessment.checks.ddi.coverage).toBe('PARTIAL');
    await expect(page.getByRole('region',{name:'Kết quả tương tác thực tế'})).toContainText('Moderate');
    await expect(page.getByRole('region',{name:'Kết quả tương tác thực tế'})).toContainText('PARTIAL');
    expect(actual.matches.filter((r:{status:string})=>r.status==='SELECTED').map((r:{source_id:string})=>r.source_id)).toEqual(expect.arrayContaining([panadol,alltrex]));
  }
  trace('PRECONFIRM_COUNTS_UNCHANGED',before.counts);return {result,actual};
}

test('four inputs use real API/Auth/PostgreSQL and Qwen/Whisper/Tesseract, with source control and isolation',async({page,context})=>{
  test.setTimeout(600000);
  await page.addLocatorHandler(page.getByRole('button',{name:'Nhắc lại sau 7 ngày',exact:true}),async locator=>locator.click());
  await login(page);
  // Explicit non-first duplicate choice, including a real Module 2 lookup.
  await fresh(page,'manual');let baseline=oracle().counts;
  await page.getByRole('textbox',{name:'Tìm thuốc trong danh mục',exact:true}).fill('Lenalimid');
  const search=page.waitForResponse(r=>r.url().includes('/api/reference/medications?'));
  await page.getByRole('button',{name:'Tìm sản phẩm',exact:true}).click();
  const duplicates=(await (await search).json()).medications;
  const duplicateIds=duplicates.map((p:{source_medication_id:string})=>p.source_medication_id);
  expect(duplicateIds).toEqual(expect.arrayContaining(['PC_010cdfd04f615a42914b4719','PC_03b9ee6ccfefa60db000d48f',
    'PC_3cae488026778623c1b9c223','PC_6108f0758c3df7cff2609ff0','PC_f55e22692f69802f49539fe6']));
  expect(new Set(duplicateIds).size).toBe(duplicateIds.length);
  const selectedIndex=duplicates.findIndex((p:{components:{ingredient_text_raw:string}[]},index:number)=>index>0&&
    p.components.some(c=>/\d+(?:[.,]\d+)?\s*mg/i.test(c.ingredient_text_raw)));
  expect(selectedIndex).toBeGreaterThan(0);
  const selected=duplicates[selectedIndex];expect(selected.id).not.toBe(duplicates[0].id);
  const strength=(selected.components.map((c:{ingredient_text_raw:string})=>c.ingredient_text_raw).join(' ').match(/\d+(?:[.,]\d+)?\s*mg/i)||[])[0];
  expect(strength).toBeTruthy();
  const duplicate=await addProduct(page,'Lenalimid',selected.source_medication_id,strength);
  const duplicateResult=await confirmAndAssess(page,duplicate.review,baseline,false);
  expect(duplicateResult.actual.matches.some((m:{status:string;product_id:string})=>m.status==='SELECTED'&&m.product_id===selected.id)).toBe(true);
  trace('REAL_MANUAL_NONFIRST_PRODUCT',{index:selectedIndex,source_id:selected.source_medication_id,product_id:selected.id,matches:duplicateResult.actual.matches});

  await fresh(page,'manual');baseline=oracle().counts;
  await addProduct(page,'Panadol',panadol,'500 mg');const manual=await addProduct(page,'Alltrex',alltrex,'2,5 mg');
  const manualResult=await confirmAndAssess(page,manual.review,baseline);
  controlTrace('REAL_MANUAL_CONTROL',manualResult.actual);

  // Revised content creates a fresh workflow/version and hides the old assessment.
  await page.getByRole('button',{name:'Sửa danh sách đã xác nhận',exact:true}).click();
  await expect(page.getByRole('region',{name:'Kết quả tương tác thực tế'})).toHaveCount(0);
  await page.getByLabel('Liều mỗi lần #1',{exact:true}).fill('hai viên');
  const edit=page.waitForResponse(r=>r.url().endsWith('/api/v1/intake/entries/edit'));
  await page.getByRole('button',{name:'Lưu thay đổi thuốc 1',exact:true}).click();
  const revised=await (await edit).json();expect(revised.entries[0].confirmed).toBe(false);
  expect(oracle(revised.workflow_id).entries[0].medication.dose_raw).toBe('hai viên');
  await page.getByRole('button',{name:'Hủy yêu cầu hiện tại',exact:true}).click();
  await expect(page.locator('.intake-workspace')).toHaveAttribute('aria-busy','false');

  await fresh(page,'chat');baseline=oracle().counts;
  await page.getByLabel('Tin nhắn',{exact:true}).fill('Thuốc X có hàm lượng bao nhiêu?');
  const question=page.waitForResponse(r=>r.url().endsWith('/api/v1/intake/messages'));
  await page.getByRole('button',{name:'Gửi tin nhắn',exact:true}).click();
  const questionReview=await (await question).json();expect(questionReview.entries).toHaveLength(0);
  trace('REAL_QUESTION_ROUTE',{input:'Thuốc X có hàm lượng bao nhiêu?',state:questionReview.state,entries:questionReview.entries.length});
  await expect(page.locator('.intake-workspace')).toHaveAttribute('aria-busy','false');
  // Keep the QA case separate from a new medication declaration, as in the CLI acceptance.
  await page.getByRole('button',{name:'Hủy yêu cầu hiện tại',exact:true}).click();
  await expect(page.locator('.intake-workspace')).toHaveAttribute('aria-busy','false');
  await fresh(page,'chat');
  await page.getByLabel('Tin nhắn',{exact:true}).fill(sentence);
  const chat=page.waitForResponse(r=>r.url().endsWith('/api/v1/intake/messages'));
  await page.getByRole('button',{name:'Gửi tin nhắn',exact:true}).click();const chatResponse=await chat;
  expect(chatResponse.status()).toBe(200);const chatReview=await chatResponse.json();
  trace('REAL_QWEN_REVIEW_BEFORE_CONFIRM',chatReview);
  expect(chatReview.state).toBe('AWAITING_CONFIRMATION');expect(chatReview.entries).toHaveLength(2);
  trace('REAL_QWEN_INPUT_AND_EXTRACTION',{input:sentence,entries:chatReview.entries});
  const chatResult=await confirmAndAssess(page,chatReview,baseline);controlTrace('REAL_CHAT_CONTROL',chatResult.actual);

  await fresh(page,'voice');baseline=oracle().counts;
  const wav=resolve(root,'data/samples/voice/panadol_vi_tts.wav');
  await page.getByLabel('Tải âm thanh',{exact:true}).setInputFiles(wav);
  const speech=page.waitForResponse(r=>r.url().endsWith('/api/v1/intake/voice'));
  await page.getByRole('button',{name:'Chuyển thành văn bản',exact:true}).click();
  const speechResponse=await speech;expect(speechResponse.status()).toBe(200);const preview=await speechResponse.json();
  expect(preview.error_code).toBeNull();await expect(page.getByTestId('raw-transcript')).toHaveText(preview.draft.raw_transcript);
  trace('REAL_WHISPER_BEFORE_EDIT',{original:'Tôi đang uống Panadol năm trăm miligam, dạng viên nén, mỗi sáng một viên.',synthetic_voice:true,transcript:preview.draft.raw_transcript});
  await page.getByLabel('Bản chép lời để gửi',{exact:true}).fill(sentence);
  await page.getByLabel('Tải âm thanh',{exact:true}).setInputFiles({name:'empty.wav',mimeType:'audio/wav',buffer:Buffer.alloc(0)});
  await page.getByRole('button',{name:'Chuyển thành văn bản',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('INVALID_AUDIO');
  await expect(page.getByLabel('Bản chép lời để gửi',{exact:true})).toHaveValue(sentence);
  const submit=page.waitForResponse(r=>r.url().endsWith('/api/v1/intake/voice/submit'));
  await page.getByRole('button',{name:'Đã xem transcript — gửi vào chatbot',exact:true}).click();
  const voiceReview=await (await submit).json();expect(voiceReview.state).toBe('AWAITING_CONFIRMATION');
  const voiceResult=await confirmAndAssess(page,voiceReview,baseline);
  expect(voiceResult.actual.inputs.every((input:{payload:Record<string,unknown>})=>!input.payload.object_locator)).toBe(true);
  expect(voiceResult.actual.inputs.some((input:{payload:{audio_sha256?:string}})=>input.payload.audio_sha256===createHash('sha256').update(readFileSync(wav)).digest('hex'))).toBe(true);
  expect(voiceResult.actual.inputs.some((input:{payload:{voice?:{raw_transcript:string;text:string}}})=>input.payload.voice?.raw_transcript===preview.draft.raw_transcript&&input.payload.voice.text===sentence)).toBe(true);
  controlTrace('REAL_VOICE_CORRECTED_CONTROL',voiceResult.actual);

  await fresh(page,'image');baseline=oracle().counts;
  await page.getByLabel('Chọn ảnh toa thuốc',{exact:true}).setInputFiles(process.env.UI_OCR_IMAGE!);
  const image=page.waitForResponse(r=>r.url().endsWith('/ocr'));
  await page.getByRole('button',{name:'Đọc thông tin từ ảnh',exact:true}).click();
  const imageResponse=await image;expect(imageResponse.status()).toBe(200);const imageResult=await imageResponse.json();
  expect(imageResult.review.entries).toHaveLength(2);trace('REAL_TESSERACT_BEFORE_EDIT',imageResult.review.entries);
  let ocrReview=imageResult.review;
  for(const [index,name,strength,form] of [[1,'Panadol Viên Sủi','500 mg','viên sủi'],[2,'Alltrex','2,5 mg','viên nén']] as const) {
    await page.getByLabel('Tên thuốc #'+index,{exact:true}).fill(name);
    await page.getByLabel('Hàm lượng #'+index,{exact:true}).fill(strength);
    await page.getByLabel('Dạng thuốc #'+index,{exact:true}).fill(form);
    await page.getByLabel('Liều mỗi lần #'+index,{exact:true}).fill('một viên');
    const saved=page.waitForResponse(r=>r.url().endsWith('/api/v1/intake/entries/edit'));
    await page.getByRole('button',{name:'Lưu thay đổi thuốc '+index,exact:true}).click();ocrReview=await (await saved).json();
    await expect(page.locator('.intake-workspace')).toHaveAttribute('aria-busy','false');
  }
  await expect(page.getByLabel('Tên thuốc #1',{exact:true})).toHaveValue('Panadol Viên Sủi');
  const ocrResult=await confirmAndAssess(page,ocrReview,baseline);controlTrace('REAL_OCR_CONTROL',ocrResult.actual);
  const privateWorkflow=ocrReview.workflow_id;
  // An actual second patient cannot read the first patient's workflow, and the UI is scoped by account.
  await logout(page);await login(page,process.env.UI_OTHER_EMAIL!);
  expect((await page.request.get('/api/v1/intake/workflows/'+privateWorkflow+'/details')).status()).toBe(404);
  await page.goto('/intake?mode=manual');await expect(page.getByLabel('Tên thuốc #1',{exact:true})).toHaveCount(0);
  await logout(page);await login(page,process.env.UI_UNLINKED_EMAIL!);
  await page.goto('/intake');await expect(page.getByText('Chưa có quyền nhập thuốc hoặc liên kết hồ sơ Core.',{exact:false})).toBeVisible();
  expect((await page.request.post('/api/v1/intake/workflows',{data:{}})).status()).toBe(403);
  await context.clearCookies();await page.reload();await expect(page.getByLabel('Email',{exact:true})).toBeVisible();
  trace('REAL_BROWSER_ISOLATION',{other_owner:404,missing_link:403,expired_session:'login',direct_microphone:'not tested; uploaded synthetic WAV instead'});
});
