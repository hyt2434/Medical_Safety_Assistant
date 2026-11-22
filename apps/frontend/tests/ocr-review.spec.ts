import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import type { IntakeReview, IntakeDetails, VoicePreview, MedicationFields, CatalogProduct } from '../src/api';

// HTTP fixtures test the browser contract, NOT Qwen/Whisper/Tesseract accuracy.
async function fixture(page: Page) {
  const build = 'b'.repeat(64);
  const products: CatalogProduct[] = [1, 2].map(n => ({id:'product-'+n, dataset_build:build,
    source_medication_id:'catalog-'+n, brand_name:'Lenalimid', dosage_form:'Viên nang',
    manufacturer:'Nhà sản xuất '+n, registration_token:'SDK-'+n,
    components:[{ingredient_text_raw:n === 1 ? 'Lenalidomide 5 mg' : 'Lenalidomide 10 mg'}]}));
  const med: MedicationFields = {name_raw:'Panadol Viên Sui',strength_raw:'500mg',dosage_form_raw:null,dose_raw:'1 viên',
    evidence_text:'Panadol Viên Sui 500mg',administrations:[{timing_raw:'mỗi sáng',dose_raw:'1 viên',timing_slots_raw:[]}]};
  let sequence = 1;
  let review: IntakeReview = {workflow_id:'11111111-1111-4111-8111-111111111111',revision:1,state:'COLLECTING',
    assistant_message:'Hãy nhập thông tin thuốc',entries:[],missing_blockers:[],qa_results:[]};
  let sources: IntakeDetails['entry_sources'] = {};
  let assessment: IntakeDetails['assessment'] = null;
  let voice: VoicePreview = {workflow_id:review.workflow_id,revision:1,error_code:null,retry_allowed:true,draft:null};
  const calls: {path:string;body:Record<string,unknown>}[] = [];
  let crop = '';
  const nextEntry = () => '22222222-2222-4222-8222-'+String(sequence++).padStart(12,'0');
  function add(medication: MedicationFields, selected: CatalogProduct | null, inputSource: string, replace=false) {
    const entry={entry_version_id:nextEntry(),confirmed:false,medication};
    if(replace) review.entries=[entry]; else review.entries.push(entry);
    sources[entry.entry_version_id]={input_source:inputSource,selected_product:selected ? {
      medication_id:selected.id,dataset_build:build,source_medication_id:selected.source_medication_id,
      brand_name:selected.brand_name,dosage_form:selected.dosage_form}:null};
    review={...review,revision:review.revision+1,state:'AWAITING_CONFIRMATION',assistant_message:'Hãy xem lại bản nháp',qa_results:[]};
  }
  await page.route('**/api/reference/medications?*',route=>route.fulfill({json:{medications:products,dataset_build:build}}));
  await page.route('**/api/v1/intake/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/capabilities')) return route.fulfill({json:{persistent_intake:true}});
    if(path.endsWith('/details')) return route.fulfill({json:{review,conversation_id:'conversation-fixture',
      messages:[{id:'assistant-'+review.revision,role:'ASSISTANT',text_content:review.assistant_message,input_source:'TEXT'}],
      entry_sources:sources,assessment}});
    if(route.request().method()==='GET' && path.endsWith('/voice'))
      return route.fulfill({json:{...voice,workflow_id:review.workflow_id,revision:review.revision}});
    if(path.endsWith('/ocr')) {
      crop=route.request().postData() || '';
      calls.push({path,body:{}});
      add(med,null,'OCR');
      return route.fulfill({json:{review,ocr:{medication_entries:[{extracted_name:med.name_raw}],extraction_run:{raw_output:{ocr:{text:'engine-private-diagnostic'}}}}}});
    }
    const body=route.request().postDataJSON() || {};
    calls.push({path,body});
    expect(body).not.toHaveProperty('owner'); expect(body).not.toHaveProperty('user_id');
    if(path.endsWith('/workflows')) return route.fulfill({json:review});
    expect(body.revision).toBe(review.revision);
    if(!path.endsWith('/revise')) expect(body.workflow_id).toBe(review.workflow_id);
    if(path.endsWith('/manual')) add(body.medication,products.find(p=>p.source_medication_id===body.source_medication_id)!, 'MANUAL');
    else if(path.endsWith('/entries/edit')) {
      const old=review.entries.find(e=>e.entry_version_id===body.entry_version_id)!;
      const source=sources[old.entry_version_id]; const selected=products.find(p=>p.source_medication_id===body.source_medication_id)||null;
      const entry={...old,entry_version_id:nextEntry(),confirmed:false,medication:body.medication};
      review={...review,revision:review.revision+1,state:'AWAITING_CONFIRMATION',
        entries:review.entries.map(e=>e===old?entry:e)};
      sources[entry.entry_version_id]=selected?{input_source:'MANUAL',selected_product:{medication_id:selected.id,
        dataset_build:build,source_medication_id:selected.source_medication_id,brand_name:selected.brand_name}}:source;
    } else if(path.endsWith('/confirm')) {
      expect(body.explicit_confirmation).toBe(true); expect(body.request_key).toBeTruthy();
      review={...review,revision:review.revision+1,state:'COMPLETED',entries:review.entries.map(e=>({...e,confirmed:true}))};
    } else if(path.endsWith('/actions')) {
      expect(review.state).toBe('COMPLETED'); expect(body.explicit_request).toBe(true);
      assessment={execution_status:'COMPLETED',check_results:{ddi:{execution:'COMPLETED',coverage:'PARTIAL',limitations:['Chỉ kiểm tra phạm vi có dữ liệu']}},
        findings:[{finding_type:'DDI',severity:'MODERATE',source_severity:'Moderate',explanation:'Cảnh báo có bằng chứng',evidence:{source:'DDInter fixture'}}]};
      review={...review,assessment_id:'assessment-fixture',assistant_message:'Moderate · PARTIAL'};
    } else if(path.endsWith('/revise')) {
      review={...review,workflow_id:'33333333-3333-4333-8333-333333333333',revision:1,state:'CLARIFYING',assessment_id:null,
        assistant_message:'Hãy sửa và xác nhận lại'};assessment=null;
    } else if(path==='/api/v1/intake/voice') {
      if(!body.audio_payload) return route.fulfill({json:{...voice,revision:review.revision,error_code:'INVALID_AUDIO'}});
      review={...review,revision:review.revision+1};
      voice={workflow_id:review.workflow_id,revision:review.revision,error_code:null,retry_allowed:true,
        draft:{draft_id:'44444444-4444-4444-8444-444444444444',raw_transcript:'Panadone năm trăm miligam',text:'Panadone năm trăm miligam',confidence_score:.8,language:'vi-VN'}};
      return route.fulfill({json:voice});
    } else if(path.endsWith('/voice/edit')) {
      expect(body.draft_id).toBe(voice.draft!.draft_id);
      review={...review,revision:review.revision+1}; voice={...voice,revision:review.revision,draft:{...voice.draft!,text:String(body.text)}};
      return route.fulfill({json:voice});
    } else if(path.endsWith('/voice/submit')) {
      expect(body.explicit_confirmation).toBe(true); expect(voice.draft!.text).toBe('Panadol 500 mg, hai viên');
      add({...med,name_raw:'Panadol',dosage_form_raw:'Viên nén',dose_raw:'hai viên'},null,'VOICE');voice={...voice,draft:null};
    } else if(path.endsWith('/messages')) {
      review={...review,revision:review.revision+1,assistant_message:'Không đủ bằng chứng để trả lời',qa_results:[
        {text:'Câu trả lời từ backend',status:'UNAVAILABLE',coverage:'UNASSESSED',limitations:['Chưa có nguồn phù hợp'],evidence_refs:[]}]};
    } else throw new Error('Unexpected intake request '+path);
    return route.fulfill({json:review});
  });
  return {calls,products,get review(){return review;},get crop(){return crop;}};
}
async function login(page:Page) {
  await page.addLocatorHandler(page.getByRole('button',{name:'Nhắc lại sau 7 ngày',exact:true}),async locator=>locator.click());
  await page.goto('/login');await page.getByLabel('Email',{exact:true}).fill('mai.demo@example.com');
  await page.getByLabel('Mật khẩu',{exact:true}).fill('Mai-patient-2026');
  await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();await expect(page).toHaveURL('/dashboard');
  const later=page.getByRole('button',{name:'Nhắc lại sau 7 ngày',exact:true});if(await later.isVisible()) await later.click();
}

test('persisted OCR edits, revision and confirmation precede explicit safety requests (HTTP fixtures)',async({page})=>{
  const state=await fixture(page);await login(page);await page.goto('/intake');
  await page.getByLabel('Chọn ảnh toa thuốc',{exact:true}).setInputFiles('public/assets/prescription-sample.png');
  await page.getByRole('button',{name:'Đọc thông tin từ ảnh',exact:true}).click();
  const pane=page.getByRole('region',{name:'Bản nháp đã lưu trên máy chủ'});
  const confirm=pane.getByRole('button',{name:'Xác nhận danh sách',exact:true});
  await expect(confirm).toBeDisabled();
  await page.getByLabel('Tên thuốc #1',{exact:true}).fill('Panadol Viên Sủi');
  await page.getByLabel('Dạng thuốc #1',{exact:true}).fill('Viên sủi');
  await page.getByLabel('Liều mỗi lần #1',{exact:true}).fill('một viên');
  await page.getByRole('button',{name:'Lưu thay đổi thuốc 1',exact:true}).click();
  await pane.getByRole('checkbox').check();await expect(confirm).toBeEnabled();
  await page.getByLabel('Thời điểm #1',{exact:true}).fill('mỗi sáng sau ăn');await expect(confirm).toBeDisabled();
  expect(state.calls.some(c=>c.path.endsWith('/confirm')||c.path.endsWith('/actions'))).toBe(false);
  await page.getByRole('button',{name:'Lưu thay đổi thuốc 1',exact:true}).click();
  await pane.getByRole('checkbox').check();await confirm.dblclick();
  await expect(page.getByRole('button',{name:'Nhận diện và đánh giá tương tác',exact:true})).toBeEnabled();
  expect(state.calls.filter(c=>c.path.endsWith('/confirm'))).toHaveLength(1);
  expect(state.calls.filter(c=>c.path.endsWith('/actions'))).toHaveLength(0);
  await page.getByRole('button',{name:'Nhận diện và đánh giá tương tác',exact:true}).click();
  await expect(page.getByRole('region',{name:'Kết quả tương tác thực tế'})).toContainText('PARTIAL');
  await expect(page.getByRole('region',{name:'Kết quả tương tác thực tế'})).toContainText('không có nghĩa là an toàn');
  await page.getByRole('button',{name:'Sửa danh sách đã xác nhận',exact:true}).click();
  await expect(page.getByRole('region',{name:'Kết quả tương tác thực tế'})).toHaveCount(0);
  await page.getByLabel('Liều mỗi lần #1',{exact:true}).fill('hai viên');
  await page.getByRole('button',{name:'Lưu thay đổi thuốc 1',exact:true}).click();
  expect(state.review.entries[0].confirmed).toBe(false);
  expect(state.review.entries[0].medication.administrations?.[0].timing_raw).toBe('mỗi sáng sau ăn');
});

test('crop coordinates reach Core OCR without exposing engine diagnostics (HTTP fixtures)',async({page})=>{
  const state=await fixture(page);await login(page);await page.goto('/intake');
  await page.getByLabel('Chọn ảnh toa thuốc',{exact:true}).setInputFiles('public/assets/prescription-sample.png');
  await page.getByText('Chọn vùng cần đọc',{exact:false}).click();
  await page.getByRole('button',{name:'Điều chỉnh bằng bàn phím',exact:true}).click();
  await page.getByLabel('Phải',{exact:true}).fill('62');
  await page.getByRole('button',{name:'Đọc thông tin từ ảnh',exact:true}).click();
  await expect(page.getByLabel('Tên thuốc #1',{exact:true})).toHaveValue('Panadol Viên Sui');
  expect(state.crop).toContain('name="region"');expect(state.crop).toContain('"right":0.62');
  await expect(page.getByText('engine-private-diagnostic',{exact:false})).toHaveCount(0);
});

test('manual catalog preserves second product and build through form edits; double click sends once (HTTP fixtures)',async({page})=>{
  const state=await fixture(page);await login(page);await page.goto('/intake?mode=manual');
  await page.getByLabel('Tìm thuốc trong danh mục',{exact:true}).fill('Lenalimid');
  await page.getByRole('button',{name:'Tìm sản phẩm',exact:true}).click();
  await expect(page.getByRole('button',{name:/^Chọn Lenalimid/})).toHaveCount(2);
  await expect(page.getByRole('button',{name:'Lưu thuốc vào bản nháp',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Chọn Lenalimid — catalog-2',exact:true}).click();
  await page.getByLabel('Hàm lượng theo nhãn',{exact:true}).fill('10 mg');
  await page.getByLabel('Liều mỗi lần',{exact:true}).fill('một viên');
  await page.getByRole('button',{name:'Lưu thuốc vào bản nháp',exact:true}).dblclick();
  await expect(page.getByLabel('Tên thuốc #1',{exact:true})).toHaveValue('Lenalimid');
  const saved=state.calls.filter(c=>c.path.endsWith('/manual'));
  expect(saved).toHaveLength(1);expect(saved[0].body.source_medication_id).toBe('catalog-2');expect(saved[0].body.dataset_build).toBe('b'.repeat(64));
  await page.getByLabel('Liều mỗi lần #1',{exact:true}).fill('hai viên');
  await page.getByRole('button',{name:'Lưu thay đổi thuốc 1',exact:true}).click();
  await expect.poll(()=>state.review.entries[0].medication.dose_raw).toBe('hai viên');
  expect(state.calls.at(-1)!.body.source_medication_id).toBe('catalog-2');
  expect(state.calls.some(c=>c.path.endsWith('/actions'))).toBe(false);
});

test('Voice retains editable transcript after invalid audio and submits the reviewed text (HTTP fixtures)',async({page})=>{
  const state=await fixture(page);await login(page);await page.goto('/intake?mode=voice');
  await page.getByLabel('Tải âm thanh',{exact:true}).setInputFiles({name:'fixture.wav',mimeType:'audio/wav',buffer:Buffer.from('HTTP fixture, not real audio')});
  await page.getByRole('button',{name:'Chuyển thành văn bản',exact:true}).click();
  await expect(page.getByTestId('raw-transcript')).toHaveText('Panadone năm trăm miligam');
  await page.getByLabel('Bản chép lời để gửi',{exact:true}).fill('Panadol 500 mg, hai viên');
  await page.getByLabel('Tải âm thanh',{exact:true}).setInputFiles({name:'empty.wav',mimeType:'audio/wav',buffer:Buffer.alloc(0)});
  await page.getByRole('button',{name:'Chuyển thành văn bản',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('INVALID_AUDIO');
  await expect(page.getByLabel('Bản chép lời để gửi',{exact:true})).toHaveValue('Panadol 500 mg, hai viên');
  await page.getByRole('button',{name:'Đã xem transcript — gửi vào chatbot',exact:true}).dblclick();
  await expect(page.getByLabel('Liều mỗi lần #1',{exact:true})).toHaveValue('hai viên');
  expect(state.calls.filter(c=>c.path.endsWith('/voice/submit'))).toHaveLength(1);
  expect(state.calls.some(c=>c.path.endsWith('/confirm')||c.path.endsWith('/actions'))).toBe(false);
});

test('chat renders backend QA and does not create a local medication draft; expiry clears medical UI (HTTP fixtures)',async({page})=>{
  const state=await fixture(page);await login(page);await page.goto('/chat');
  await page.getByLabel('Tin nhắn',{exact:true}).fill('Thuốc X có hàm lượng bao nhiêu?');
  await page.getByRole('button',{name:'Gửi tin nhắn',exact:true}).click();
  await expect(page.getByRole('region',{name:'Câu trả lời có nguồn'})).toContainText('UNASSESSED');
  await expect(page.getByLabel('Tên thuốc #1',{exact:true})).toHaveCount(0);
  expect(state.review.entries).toHaveLength(0);
  await page.route('**/api/v1/intake/messages',route=>route.fulfill({status:401,json:{error:{message:'Phiên đã hết hạn'}}}));
  await page.getByLabel('Tin nhắn',{exact:true}).fill('Bổ sung thông tin');
  await page.getByRole('button',{name:'Gửi tin nhắn',exact:true}).click();
  await expect(page.getByLabel('Email',{exact:true})).toBeVisible();
  await expect(page.getByRole('region',{name:'Bản nháp đã lưu trên máy chủ'})).toHaveCount(0);
});

test('API failures and denied microphone retain input and never display sample safety results (HTTP fixtures)',async({page})=>{
  await page.addInitScript(()=>{Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia:()=>Promise.reject(new DOMException('denied','NotAllowedError'))}})});
  await fixture(page);await login(page);await page.goto('/intake?mode=voice');
  await page.getByRole('button',{name:'Thu âm',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Microphone');
  await page.getByRole('button',{name:'Chatbot',exact:true}).click();
  await page.getByLabel('Tin nhắn',{exact:true}).fill('Dữ liệu chưa gửi được');
  await page.route('**/api/v1/intake/messages',route=>route.fulfill({status:503,json:{error:{message:'Máy chủ đang bận'}}}));
  await page.getByRole('button',{name:'Gửi tin nhắn',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Máy chủ đang bận');
  await expect(page.getByLabel('Tin nhắn',{exact:true})).toHaveValue('Dữ liệu chưa gửi được');
  await expect(page.getByRole('region',{name:'Kết quả tương tác thực tế'})).toHaveCount(0);
});
